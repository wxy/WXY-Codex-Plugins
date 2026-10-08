"""Bounded metadata-only observer. Does not open regular files or follow symlinks."""
from __future__ import annotations
import heapq
import os
from pathlib import Path
import stat
import time

from .config import is_under


def observe(config):
    settings = config['observer']
    started = time.monotonic()
    deadline = started + settings['max_seconds']
    visited, inodes = 0, set()
    results = []
    for root in config['roots']:
        path = root['path']
        row = {'id':root['id'],'path':str(path),'status':'ok','complete':True,
               'allocated_bytes':0,'logical_bytes':0,'file_count':0,'unique_files':0,
               'hardlink_duplicates':0,'symlinks_skipped':0,'excluded_entries':0,
               'cross_device_skipped':0,'errors':[],'buckets':{},'top_files':[]}
        largest = []
        def error(kind, at):
            row['complete'] = False
            if len(row['errors']) < 20:
                row['errors'].append({'kind':kind,'path':str(at)})
        def walk(fd, folder, depth, device):
            nonlocal visited
            if depth > 64:
                error('depth_limit', folder)
                return
            try:
                with os.scandir(fd) as entries:
                    for entry in entries:
                        if visited >= settings['max_entries'] or time.monotonic() >= deadline:
                            error('budget_exhausted', folder)
                            return
                        visited += 1
                        child = folder / entry.name
                        if entry.name in config['exclude_names'] or is_under(child, config['data_dir']):
                            row['excluded_entries'] += 1
                            continue
                        try:
                            info = entry.stat(follow_symlinks=False)
                            if stat.S_ISLNK(info.st_mode):
                                row['symlinks_skipped'] += 1
                            elif info.st_dev != device:
                                row['cross_device_skipped'] += 1
                                error('cross_device', child)
                            elif stat.S_ISDIR(info.st_mode):
                                child_fd = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                                try:
                                    walk(child_fd, child, depth+1, device)
                                finally:
                                    os.close(child_fd)
                            elif stat.S_ISREG(info.st_mode):
                                relative = child.relative_to(path)
                                bucket_path = path.joinpath(*relative.parts[:-1][:settings['bucket_depth']])
                                key = str(bucket_path)
                                bucket = row['buckets'].setdefault(key, {'path':key,'allocated_bytes':0,'logical_bytes':0,'file_count':0})
                                row['file_count'] += 1
                                bucket['file_count'] += 1
                                identity = (info.st_dev, info.st_ino)
                                if identity in inodes:
                                    row['hardlink_duplicates'] += 1
                                    continue
                                inodes.add(identity)
                                allocated = getattr(info,'st_blocks',0)*512 if hasattr(info,'st_blocks') else info.st_size
                                row['unique_files'] += 1
                                row['allocated_bytes'] += allocated
                                row['logical_bytes'] += info.st_size
                                bucket['allocated_bytes'] += allocated
                                bucket['logical_bytes'] += info.st_size
                                item = (allocated, str(child), info.st_size)
                                if len(largest) < settings['top_files']:
                                    heapq.heappush(largest, item)
                                elif item > largest[0]:
                                    heapq.heapreplace(largest,item)
                        except OSError as exc:
                            error(type(exc).__name__, child)
                        if visited >= settings['max_entries'] or time.monotonic() >= deadline:
                            # A boundary at exactly the final entry is conservative: coverage may be incomplete.
                            error('budget_exhausted', folder)
                            return
            except OSError as exc:
                error(type(exc).__name__, folder)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                walk(fd, path, 0, os.fstat(fd).st_dev)
            finally:
                os.close(fd)
        except OSError as exc:
            row['status'] = 'missing' if isinstance(exc,FileNotFoundError) else 'unreadable'
            error(type(exc).__name__,path)
        row['top_files'] = [{'allocated_bytes':n,'path':p,'logical_bytes':logical}
                            for n,p,logical in sorted(largest,reverse=True)]
        results.append(row)
    return {'schema_version':1,'scope':config['scope'],'created_at':time.time(),
            'duration_seconds':time.monotonic()-started,'entries_visited':visited,
            'complete':all(row['complete'] for row in results), 'roots':results,
            'accounting':'allocated_file_blocks; hardlinks deduplicated across roots; no clone/APFS shared-extent accounting',
            'consistency':'live traversal, not an atomic filesystem snapshot'}
