"""Bounded shallow cache discovery; queries consume retained metadata only."""
from __future__ import annotations
import json
import os
from pathlib import Path
import stat
import time

DEVELOPMENT_NAMES=frozenset(('Codex','Homebrew','pip','python3','com.apple.python',
    'org.swift.swiftpm','node-gyp','npm','yarn','pnpm','CocoaPods','Carthage',
    'com.github.GitHubClient','com.github.GitHubClient.ShipIt','com.openai.codex',
    'com.openai.sky.CUAService','com.apple.dt.Xcode','com.apple.dt.Xcode.ITunesSoftwareService'))
LIMIT=256

def parent():
    return Path.home()/'Library/Caches'

def discover(exclude_names=()):
    root=parent();value={'path':str(root),'checked_at':time.time(),'policy':'development-cache-children-v1',
        'roots':[],'gaps':[],'outside_development_scope_count':0,'excluded_directory_count':0,'discovery_complete':True,
        'note':'Only named development cache children are monitored independently. Other readable application caches are outside this automatic scope; gap occupancy/growth is unknown.'}
    def gap(path,reason,exc=None):
        value['gaps'].append({'path':str(path),'reason':reason,'error_kind':type(exc).__name__ if exc else None,
                              'errno':getattr(exc,'errno',None),'allocated_bytes':None,'growth_bytes':None})
    try:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            with os.scandir(fd) as entries:
                for i,entry in enumerate(entries):
                    if i>=LIMIT:
                        value['discovery_complete']=False;gap(root,'discovery_limit');break
                    child=root/entry.name;development=entry.name in DEVELOPMENT_NAMES
                    if entry.name in exclude_names:
                        value['excluded_directory_count']+=1;continue
                    try:
                        info=entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):
                            if development:gap(child,'symlink_not_followed')
                            continue
                        if not stat.S_ISDIR(info.st_mode):continue
                        if development:value['roots'].append(str(child))
                        # Probe metadata access only. Never ask for or change permissions.
                        inner=os.open(entry.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                        try:
                            with os.scandir(inner) as probe:next(probe,None)
                        finally:os.close(inner)
                        if not development:value['outside_development_scope_count']+=1
                    except OSError as exc:gap(child,'unreadable',exc)
        finally:os.close(fd)
    except OSError as exc:
        value['discovery_complete']=False;gap(root,'unreadable',exc)
    value['roots'].sort();value['gaps'].sort(key=lambda r:r['path'])
    return value

def needed(paths):
    root=parent()
    return any(Path(p)==root or Path(p) in root.parents for p in paths)

def partition(paths,record):
    """Carve the cache subtree out of broader roots, preserving child roots."""
    root=parent();paths=[p for p in paths if Path(p)!=root]
    return list(dict.fromkeys(paths+record['roots']))

def exclusions(path,record):
    root=parent()
    return [str(root)] if record and Path(path) in root.parents else []

def coalesce(paths,parts,record):
    all_parts={parts[p] for p in paths}
    cache_parts=parent().parts
    def covered(p):
        for n in range(1,len(parts[p])):
            ancestor=parts[p][:n]
            if ancestor not in all_parts:continue
            # Broader roots omit Caches, so they cannot subsume its children.
            if record and parts[p][:len(cache_parts)]==cache_parts and ancestor==cache_parts[:n] and n<len(cache_parts):continue
            return True
        return False
    return [p for p in paths if not covered(p)]

def remember(store,record):
    from .summaries import day_for
    day=day_for(record['checked_at'])
    store.db.execute('INSERT OR REPLACE INTO cache_coverage VALUES(?,?)',(day,json.dumps(record)))
    for gap in record['gaps']:
        store.db.execute('INSERT INTO daily_gaps VALUES(?,?,?) ON CONFLICT(day,path) DO UPDATE SET ts=max(ts,excluded.ts)',(day,gap['path'],record['checked_at']))

def retained(store,config,day=None):
    if not store.db or not store.db.execute("SELECT 1 FROM sqlite_master WHERE name='cache_coverage'").fetchone():return None
    row=store.db.execute('SELECT payload FROM cache_coverage WHERE day=?',(day,)).fetchone() if day else store.db.execute('SELECT payload FROM cache_coverage ORDER BY day DESC LIMIT 1').fetchone()
    if not row:return None
    value=json.loads(row[0])
    if not in_scope(value,config):return None
    value['stale']=time.time()-value['checked_at']>max(300,2*config['monitor']['reconcile_seconds']) if not day else False
    return value

def in_scope(record,config):
    from .storage_scope import series_for
    # This known cache anchor can disappear between observations. Its existing
    # Library parent still identifies the selected disk without probing children.
    return bool(series_for(record['path'],config) or series_for(Path(record['path']).parent,config))

def coverage(store,config,day=None):
    value=retained(store,config,day)
    return {'development_caches':value} if value else {}
