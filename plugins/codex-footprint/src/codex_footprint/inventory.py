"""Incremental metadata walks; open-directory state lives only in the elected worker."""
from __future__ import annotations
import heapq
import os
from pathlib import Path
import stat
import time


def files(root, excluded, exclude_names=()):
    """Yield metadata/errors with bounded depth; never follow a path symlink."""
    root=Path(root)
    def walk(fd,path,device,depth):
        if depth>64:
            yield ('error',{'kind':'depth_limit','path':str(path)}); return
        try:
            with os.scandir(fd) as entries:
                for entry in entries:
                    child=path/entry.name
                    if entry.name in exclude_names or any(child==p or p in child.parents for p in excluded):
                        yield ('skip',{}); continue
                    try:
                        info=entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode): yield ('skip',{}); continue
                        if info.st_dev!=device:
                            yield ('error',{'kind':'cross_device','path':str(child)}); continue
                        if stat.S_ISDIR(info.st_mode):
                            yield ('directory',{})
                            inner=os.open(entry.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                            try: yield from walk(inner,child,device,depth+1)
                            finally: os.close(inner)
                        elif stat.S_ISREG(info.st_mode):
                            yield ('file',{'path':str(child),'allocated_bytes':getattr(info,'st_blocks',0)*512,
                                          'logical_bytes':info.st_size,'inode':[info.st_dev,info.st_ino], 'links':info.st_nlink})
                    except OSError as exc: yield ('error',{'kind':type(exc).__name__,'path':str(child)})
        except OSError as exc: yield ('error',{'kind':type(exc).__name__,'path':str(path)})
    try:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: yield from walk(fd,root,os.fstat(fd).st_dev,0)
        finally: os.close(fd)
    except OSError as exc: yield ('error',{'kind':type(exc).__name__,'path':str(root)})


class Cycle:
    def __init__(self,path,state,exclude_names=()):
        self.path=Path(path); self.iterator=files(path,[Path(state)],exclude_names); self.hardlinks=set(); self.top=[]
        self.row={'path':str(path),'started_at':time.time(),'measured_at':None,'complete':False,'finished':False,
                  'allocated_bytes':0,'logical_bytes':0,'file_count':0,'entries_visited':0,'errors':[],'error_count':0,'top_files':[]}
    def step(self,count,deadline):
        for _ in range(count):
            if time.monotonic()>=deadline: break
            try: kind,item=next(self.iterator)
            except StopIteration:
                self.row.update(finished=True,complete=self.row['error_count']==0,measured_at=time.time()); break
            self.row['entries_visited']+=1
            if kind=='error':
                self.row['error_count']+=1
                if len(self.row['errors'])<20: self.row['errors'].append(item)
            if kind!='file': continue
            self.row['file_count']+=1
            key=tuple(item['inode'])
            if item['links']>1:
                if key in self.hardlinks: continue
                # A malicious tree can create arbitrarily many hardlinks: fail coverage rather than grow without bound.
                if len(self.hardlinks)>=200000:
                    self.row['error_count']+=1; continue
                self.hardlinks.add(key)
            self.row['allocated_bytes']+=item['allocated_bytes']; self.row['logical_bytes']+=item['logical_bytes']
            value=(item['allocated_bytes'],item['path'],item['logical_bytes'])
            if len(self.top)<20: heapq.heappush(self.top,value)
            elif value>self.top[0]: heapq.heapreplace(self.top,value)
        self.row['top_files']=[{'allocated_bytes':n,'path':p,'logical_bytes':size} for n,p,size in sorted(self.top,reverse=True)]
        return dict(self.row)
    def close(self): self.iterator.close()
