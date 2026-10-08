"""Machine-global lifecycle spool, singleton worker, bounded inventory and alerts."""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

from . import __version__
from .config import data_directory, OBSERVER, THRESHOLDS, RETENTION, number
from .global_store import GlobalStore
from .inventory import Cycle

MONITOR={'interval_seconds':2,'refresh_seconds':60,'slice_entries':1000,'slice_seconds':0.05,'autostart':True}
NOTIFICATIONS={'backend':'desktop','cooldown_seconds':3600,'material_growth_bytes':256*1024**2,'minimum_free_bytes':10*1024**3}
HISTORY={'max_files':2000,'max_records':100000,'max_seconds':10,'max_entries':100000}


def atomic(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'w') as f: json.dump(value,f,ensure_ascii=False)
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


def merged(raw,default,label):
    if not isinstance(raw,dict) or set(raw)-set(default):raise ValueError('Unknown '+label+' settings')
    return dict(default,**raw)


def normalize(raw,data,path):
    allowed={'version','enabled','roots','discovery','monitor','notifications','history','thresholds','retention','observer','exclude_names'}
    if set(raw)-allowed or raw.get('version')!=2 or type(raw.get('enabled')) is not bool:raise ValueError('Invalid global config')
    config={'version':2,'enabled':raw['enabled'],'data_dir':data,'config_path':path,
            'monitor':merged(raw.get('monitor',{}),MONITOR,'monitor'),
            'notifications':merged(raw.get('notifications',{}),NOTIFICATIONS,'notifications'),
            'history':merged(raw.get('history',{}),HISTORY,'history'),
            'thresholds':merged(raw.get('thresholds',{}),THRESHOLDS,'thresholds'),
            'retention':merged(raw.get('retention',{}),RETENTION,'retention'),
            'observer':merged(raw.get('observer',{}),OBSERVER,'observer')}
    m=config['monitor']; number(m['interval_seconds'],'interval_seconds',0.01,3600); number(m['refresh_seconds'],'refresh_seconds',0,86400)
    number(m['slice_entries'],'slice_entries',1,10000,True); number(m['slice_seconds'],'slice_seconds',0.001,1)
    if type(m['autostart']) is not bool:raise ValueError('autostart must be boolean')
    n=config['notifications']
    if n['backend'] not in ('desktop','inbox'):raise ValueError('notifications backend must be desktop or inbox')
    number(n['minimum_free_bytes'],'minimum_free_bytes',1,10**15,True)
    number(n['cooldown_seconds'],'cooldown_seconds',0,604800); number(n['material_growth_bytes'],'material_growth_bytes',1,10**15,True)
    for k,v in config['thresholds'].items():number(v,k,1,10**15,k!='rapid_bytes_per_second')
    for k,v in config['history'].items():number(v,k,1,1000000,k!='max_seconds')
    number(config['history']['max_seconds'],'history.max_seconds',1,10)
    for k,v in config['retention'].items():number(v,k,2,20000,True)
    discovery=raw.get('discovery',True)
    if type(discovery) is not bool:raise ValueError('discovery must be boolean')
    config['discovery']=discovery; candidates=[]
    if not isinstance(raw.get('roots',[]),list):raise ValueError('roots must be a list')
    for root in raw.get('roots',[]):
        if not isinstance(root,dict) or set(root)-{'id','path','enabled'} or not isinstance(root.get('path'),str):raise ValueError('Invalid root')
        if type(root.get('enabled',True)) is not bool:raise ValueError('Invalid root enabled')
        if root.get('enabled',True):candidates.append(root['path'])
    exclusions=raw.get('exclude_names',[])
    if not isinstance(exclusions,list) or any(not isinstance(x,str) or '/' in x or not x for x in exclusions):raise ValueError('Invalid exclusions')
    config['exclude_names']=exclusions
    roots=[]
    for text in candidates:
        candidate=Path(text).expanduser()
        if not candidate.is_absolute() or candidate==Path(candidate.anchor) or candidate==Path.home() or candidate.is_symlink():raise ValueError('Choose a real development directory; global capacity is sampled separately')
        p=candidate.resolve()
        if p==Path(p.anchor) or p==Path.home():raise ValueError('Choose a development directory rather than disk/home')
        if p==data or data in p.parents:continue
        if any(p==r or r in p.parents for r in roots):continue
        roots=[r for r in roots if p not in r.parents]; roots.append(p)
    if len(roots)>256:raise ValueError('Root discovery limit exceeded')
    config['roots']=[{'id':hashlib.sha256(str(p).encode()).hexdigest()[:16],'path':p} for p in roots]
    config['scope']=hashlib.sha256(json.dumps([str(p) for p in sorted(roots)]).encode()).hexdigest()
    return config


def discover(config):
    candidates=[]
    home=Path.home();codex=Path(os.environ.get('CODEX_HOME',str(home/'.codex')))
    candidates += [str(p) for p in (codex,home/'Library/Developer',home/'Library/Caches',home/'.cache',home/'.npm',home/'.gradle',home/'.cargo',Path('/usr/local/Cellar'),Path('/opt/homebrew/Cellar')) if p.is_dir() and not p.is_symlink()]
    develop=home/'develop'
    if develop.is_dir():
        with os.scandir(develop) as entries:
            for i,item in enumerate(entries):
                if i>=256:break
                if item.is_dir(follow_symlinks=False):candidates.append(item.path)
    value={'version':2,'enabled':True,'discovery':False,'roots':[{'path':p} for p in candidates]}
    return [str(r['path']) for r in normalize(value,config['data_dir'],config['config_path'])['roots']]


def load():
    from .config import load_config
    return load_config()


def host_disabled():
    path=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'config.toml'
    try:
        if path.stat().st_size>1024*1024:return False
        text=path.read_text()
        try:
            import tomllib
            return tomllib.loads(text).get('plugins',{}).get('codex-footprint@wxy-codex-plugins',{}).get('enabled') is False
        except ImportError:
            import re
            section=re.search(r'(?ms)^\[plugins\."codex-footprint@wxy-codex-plugins"\]\s*\n(.*?)(?=^\[|\Z)',text)
            return bool(section and re.search(r'(?m)^enabled\s*=\s*false\s*(?:#.*)?$',section[1]))
    except (OSError,ValueError):return False


def enable(roots=(),defaults=True,start=True,backend='desktop'):
    data=data_directory(); path=Path(os.environ.get('CODEX_FOOTPRINT_CONFIG',str(data/'config.json'))).expanduser().resolve()
    if path.exists():
        raw=json.loads(path.read_text())
        # Preserve a version-1 config before upgrading its semantics; its SQLite database is untouched.
        if raw.get('version')==1:
            backup=path.with_name(path.name+'.v1-backup')
            if not backup.exists():atomic(backup,raw)
        elif raw.get('version')!=2:raise ValueError('Unsupported existing configuration')
    else:raw={}
    value={'version':2,'enabled':True,'roots':[{'id':'explicit-'+str(i),'path':str(Path(p).expanduser())} for i,p in enumerate(roots)],
           'discovery':defaults,'monitor':dict(MONITOR,autostart=start),'notifications':dict(NOTIFICATIONS,backend=backend)}
    if raw.get('version')==2:
        value=dict(raw,enabled=True)
        if roots:value['roots']=[{'id':'explicit-'+str(i),'path':str(Path(p).expanduser())} for i,p in enumerate(roots)]
        value['monitor']=dict(MONITOR,**raw.get('monitor',{}),autostart=start) if 'autostart' not in raw.get('monitor',{}) else dict(raw['monitor'],autostart=start)
        value['notifications']=dict(NOTIFICATIONS,**raw.get('notifications',{}));value['notifications']['backend']=backend
    for key,default in (('monitor',MONITOR),('notifications',NOTIFICATIONS),('thresholds',THRESHOLDS),('history',HISTORY),('observer',OBSERVER),('retention',RETENTION)):
        value[key]=dict(default,**value.get(key,{}))
    value.setdefault('exclude_names',[])
    normalize(value,data,path); atomic(path,value)
    if start:ensure_worker(load())
    return status(load())


def disable():
    config=load();path=config['config_path']
    if path.exists():
        raw=json.loads(path.read_text());raw['enabled']=False;atomic(path,raw)
    return status(load())


def worker_health(data):
    file=Path(data)/'worker.json';health={'running':False,'pid':None,'version':None,'last_tick':None}
    try:health.update(json.loads(file.read_text()))
    except (OSError,ValueError):return health
    lock=Path(data)/'worker.lock'
    try:
        with lock.open('r') as f:
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);health['running']=False
            except BlockingIOError:health['running']=True
    except OSError:health['running']=False
    health['heartbeat_stale']=bool(health['running'] and health.get('last_tick') and time.time()-health['last_tick']>60)
    return health


def ensure_worker(config,force=False):
    if not config['enabled'] or host_disabled() or config.get('version')!=2 or (not force and not config['monitor']['autostart']):return
    data=config['data_dir'];data.mkdir(parents=True,exist_ok=True,mode=0o700)
    if worker_health(data)['running']:return
    entry=Path(__file__).resolve().parents[2]/'scripts/codex_footprint.py'
    env=dict(os.environ,CODEX_FOOTPRINT_DATA=str(data),CODEX_FOOTPRINT_CONFIG=str(config['config_path']),PYTHONDONTWRITEBYTECODE='1')
    # A race may spawn two processes; the held worker lock elects exactly one and the loser exits.
    with open(os.devnull,'wb') as sink:
        subprocess.Popen([sys.executable,str(entry),'worker'],stdin=subprocess.DEVNULL,stdout=sink,stderr=sink,env=env,start_new_session=True,close_fds=True)


def enqueue(config,metadata,cwd):
    if host_disabled():return
    event=dict(metadata,cwd=str(Path(cwd).resolve()),created_at=time.time(),id=uuid.uuid4().hex)
    atomic(config['data_dir']/'spool'/(event['id']+'.json'),event);ensure_worker(config)


def status(config):
    data=config['data_dir'];health=worker_health(data)
    with GlobalStore(data) as store:
        sessions=store.db.execute('SELECT count(DISTINCT session) FROM events').fetchone()[0] if store.db else 0
        return {'schema_version':2,'enabled':config['enabled'],'config_path':str(config['config_path']),'data_directory':str(data),
                'configured_roots':sorted(set([str(r['path']) for r in config['roots']]+[r['path'] for r in store.payloads('inventory')])), 'worker':health,
                'event_count':store.count('events'),'session_count':sessions,'snapshot_count':store.count('observations'),'history_analysis_count':store.count('history_runs'),
                'integrity':store.db.execute('PRAGMA quick_check').fetchone()[0] if store.db else 'not_initialized',
                'roots':store.payloads('inventory'),'volumes':store.payloads('volumes'),
                'pending_events':len(list((data/'spool').glob('*.json'))) if (data/'spool').exists() else 0,
                'notification_backend':config.get('notifications',NOTIFICATIONS)['backend'],'notification_visibility':'unverified; OS settings may suppress desktop notifications',
                'coverage':{'hosts':'supported local Codex lifecycle events','process_ownership':False,'filesystem':'discovered roots; cross-device and unreadable paths are gaps','restart_recovery':'next trusted hook/explicit enable restarts a stopped worker'},
                'deletion_supported':False,'process_attribution_supported':False,'ui_supported':False,
                'legacy_history_preserved':(data/'footprint.sqlite3').exists()}


def notify(config,payload):
    backend=config.get('notifications',NOTIFICATIONS)['backend']
    if backend=='inbox':return {'status':'inbox_only','visible':False}
    if sys.platform!='darwin':return {'status':'unsupported_platform','visible':False}
    title='Codex Footprint'
    body=f"开发存储值得关注：{payload['kind']}，变化 {(payload.get('growth_bytes') or 0)/1024**2:.1f} MiB。可在 Codex 中查询存储提醒。"
    if payload['kind']=='disk_pressure':body=f"磁盘可用空间约 {payload['available_bytes']/1024**3:.1f} GiB。此为全盘容量信号，来源尚未归因。"
    if payload['kind']=='acceptance_probe':body='这是一条 Codex Footprint 通知验收提醒，不是实际磁盘增长告警。'
    script='on run argv\n display notification (item 2 of argv) with title (item 1 of argv)\nend run'
    try:
        p=subprocess.run(['/usr/bin/osascript','-e',script,title,body],text=True,capture_output=True,timeout=5)
        return {'status':'command_accepted_visibility_unverified' if p.returncode==0 else 'delivery_failed','visible':None,'exit_code':p.returncode}
    except (OSError,subprocess.TimeoutExpired) as exc:return {'status':'delivery_failed','visible':False,'error_kind':type(exc).__name__}


def issue(store,config,row,baseline):
    if not row['complete'] or not baseline or not baseline['complete'] or row.get('measurement_scope')!=baseline.get('measurement_scope'):return
    growth=row['allocated_bytes']-baseline['allocated_bytes'];elapsed=max(0.001,row['measured_at']-baseline['measured_at']); thresholds=config['thresholds']
    added=row['file_count']-baseline['file_count']
    kinds=[]
    if growth>=thresholds['growth_bytes']:kinds.append('growth')
    if growth>0 and growth/elapsed>=thresholds['rapid_bytes_per_second']:kinds.append('rapid_growth')
    if added>=thresholds['many_files']:kinds.append('many_files')
    if baseline['allocated_bytes']<thresholds['large_bytes']<=row['allocated_bytes']:kinds.append('large_occupancy')
    prior=[json.loads(x[0]) for x in store.db.execute('SELECT payload FROM observations WHERE path=? ORDER BY id DESC LIMIT ?',(row['path'],int(thresholds['sustained_intervals'])+1))]
    if len(prior)>=thresholds['sustained_intervals']+1 and prior[0]['allocated_bytes']-prior[-1]['allocated_bytes']>=thresholds['growth_bytes'] and all(a['complete'] and b['complete'] and a.get('measurement_scope')==row.get('measurement_scope') and b.get('measurement_scope')==row.get('measurement_scope') and a['allocated_bytes']>b['allocated_bytes'] for a,b in zip(prior,prior[1:])):kinds.append('sustained_growth')
    sessions=sorted({session for session,cwd in store.db.execute('SELECT DISTINCT session,cwd FROM events WHERE ts>=?',(baseline['measured_at']-3600,)) if session and (cwd==row['path'] or Path(row['path']) in Path(cwd).parents)})
    for kind in kinds:
        fingerprint=hashlib.sha256((row['path']+'|'+kind).encode()).hexdigest()
        last=store.db.execute('SELECT ts,payload FROM alerts WHERE fingerprint=? ORDER BY id DESC LIMIT 1',(fingerprint,)).fetchone()
        if last:
            previous=json.loads(last[1]);material=(row['allocated_bytes']-previous['allocated_bytes']>=config['notifications']['material_growth_bytes'] or row['file_count']-previous.get('file_count',row['file_count'])>=thresholds['many_files'])
            if time.time()-last[0]<config['notifications']['cooldown_seconds'] or not material:continue
        payload={'path':row['path'],'kind':kind,'allocated_bytes':row['allocated_bytes'],'growth_bytes':growth,'file_count_change':added,'file_count':row['file_count'],
                 'baseline_at':baseline['measured_at'],'latest_at':row['measured_at'],'associated_sessions':sessions[:100],
                 'attribution':'temporal correlation; not exclusive ownership','coverage_complete':True,
                 'recommendation':'Query footprint_explain/cleanup_plan and verify the owning tool; no cleanup is executed.'}
        payload['delivery']=notify(config,payload)
        store.db.execute('INSERT INTO alerts(fingerprint,ts,payload) VALUES(?,?,?)',(fingerprint,time.time(),json.dumps(payload)))


def volume_rows(roots):
    # statvfs capacity is independent of traversal and directory accounting. Same-device samples coalesce.
    found={};paths=[Path('/System/Volumes/Data') if sys.platform=='darwin' else Path('/')]+[Path(p) for p in roots]
    for p in paths:
        try:
            info=p.stat();v=os.statvfs(p)
            if info.st_dev not in found:found[info.st_dev]={'path':str(p),'device':info.st_dev,'total_bytes':v.f_blocks*v.f_frsize,'available_bytes':v.f_bavail*v.f_frsize,'sampled_at':time.time(),'source':'statvfs; filesystem capacity, not sum of artifact blocks'}
        except OSError:continue
    return list(found.values())


class Runner:
    def __init__(self,config):
        import resource
        self.config=config;self.cycles={};self.completed={};self.last_volume=0;self.cursor=0
        self.exclusions=tuple(sorted(config['exclude_names']))
        limit=resource.getrlimit(resource.RLIMIT_NOFILE)[0]
        self.max_active=max(1,min(8,(int(limit)-64)//65)) if limit>0 else 2
        self.discovery_paths=[];self.discovery_at=0
    def close(self):
        for cycle in self.cycles.values():cycle.close()
    def step(self):
        config=load();self.config=config
        if not config['enabled'] or host_disabled() or config.get('version')!=2:return {'enabled':False}
        data=config['data_dir']
        exclusions=tuple(sorted(config['exclude_names']))
        request=data/'refresh.request'
        if exclusions!=self.exclusions or request.exists():
            self.close();self.cycles.clear();self.completed.clear();self.exclusions=exclusions
            request.unlink(missing_ok=True)
        with GlobalStore(data,True) as store:
            spool=data/'spool'
            if spool.exists():
                for i,p in enumerate(spool.glob('*.json')):
                    if i>=1000:break
                    try:
                        if p.stat().st_size>16384:raise ValueError('oversized event')
                        event=json.loads(p.read_text());cwd=Path(event['cwd'])
                        if not cwd.is_absolute():raise ValueError('invalid cwd')
                        store.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?)',(event['id'],event['created_at'],event.get('session_id'),str(cwd),json.dumps(event)))
                        store.db.commit();p.unlink()
                    except (ValueError,KeyError,OSError):
                        # Preserve bounded failure evidence; do not persist an untrusted event's raw text.
                        p.unlink(missing_ok=True)
            paths=[str(r['path']) for r in config['roots']]
            if config['discovery']:
                if time.time()-self.discovery_at>=60:
                    self.discovery_paths=discover(config);self.discovery_at=time.time()
                paths+=self.discovery_paths
            for (cwd,) in store.db.execute('SELECT DISTINCT cwd FROM events ORDER BY ts DESC LIMIT 256'):
                p=Path(cwd)
                if p==Path(p.anchor) or p==Path.home() or p==data or data in p.parents or p.is_symlink():continue
                if any(p==Path(r) or Path(r) in p.parents for r in paths):continue
                paths=[r for r in paths if p not in Path(r).parents];paths.append(cwd)
            paths=[p for p in dict.fromkeys(paths) if not set(Path(p).parts).intersection(config['exclude_names'])]
            # Compact nesting after dynamic discovery; root totals still are not additive across hardlinks/time windows.
            paths=[p for p in paths if not any(Path(q) in Path(p).parents for q in paths if q!=p)]
            for (old_path,) in store.db.execute('SELECT path FROM inventory').fetchall():
                if old_path not in paths:store.db.execute('DELETE FROM inventory WHERE path=?',(old_path,))
            # Excluded names are applied by path boundaries discovered during the walk, not shell patterns.
            for key in list(self.cycles):
                if key not in paths:self.cycles.pop(key).close()
            deadline=time.monotonic()+config['monitor']['slice_seconds']
            remaining=config['monitor']['slice_entries']
            count=max(1,remaining//max(1,min(len(paths),self.max_active)))
            ordered=sorted(paths,key=lambda p:self.completed.get(p,0))
            if ordered:
                offset=self.cursor%len(ordered);ordered=ordered[offset:]+ordered[:offset];self.cursor+=1
            for path in ordered:
                if path not in self.cycles and len(self.cycles)<self.max_active and time.time()-self.completed.get(path,0)>=config['monitor']['refresh_seconds']:
                    self.cycles[path]=Cycle(path,data,config['exclude_names'])
                cycle=self.cycles.get(path)
                if not cycle:continue
                before=cycle.row['entries_visited']
                row=cycle.step(min(count,remaining),deadline)
                remaining-=row['entries_visited']-before
                row['measurement_scope']=hashlib.sha256(json.dumps({'path':path,'state':str(data),'exclude_names':exclusions,'accounting':1},sort_keys=True).encode()).hexdigest()
                old=store.db.execute('SELECT payload FROM observations WHERE path=? ORDER BY id DESC LIMIT 1',(path,)).fetchone()
                previous=json.loads(old[0]) if old else None
                row['growth_bytes']=row['allocated_bytes']-previous['allocated_bytes'] if row['finished'] and row['complete'] and previous and previous['complete'] and previous.get('measurement_scope')==row['measurement_scope'] else None
                store.db.execute('INSERT OR REPLACE INTO inventory VALUES(?,?)',(path,json.dumps(row)))
                if row['finished']:
                    store.db.execute('INSERT INTO observations(path,ts,payload) VALUES(?,?,?)',(path,time.time(),json.dumps(row)))
                    issue(store,config,row,previous);self.completed[path]=time.time();self.cycles.pop(path).close()
                if remaining<=0 or time.monotonic()>=deadline:break
            if time.time()-self.last_volume>=max(1,config['monitor']['interval_seconds']):
                for row in volume_rows(paths):
                    old=store.db.execute('SELECT payload FROM volumes WHERE path=?',(row['path'],)).fetchone()
                    previous=json.loads(old[0]) if old else None
                    row['available_change_bytes']=row['available_bytes']-previous['available_bytes'] if previous else None
                    row['baseline_at']=previous['sampled_at'] if previous else None
                    if row['available_bytes']<config['notifications']['minimum_free_bytes']:
                        fingerprint='volume-pressure-'+str(row['device'])
                        last=store.db.execute('SELECT ts,payload FROM alerts WHERE fingerprint=? ORDER BY id DESC LIMIT 1',(fingerprint,)).fetchone()
                        if not last or (time.time()-last[0]>=config['notifications']['cooldown_seconds'] and row['available_bytes']<=json.loads(last[1])['available_bytes']-config['notifications']['material_growth_bytes']):
                            finding=dict(row,kind='disk_pressure',associated_sessions=[],growth_bytes=None,attribution='unattributed machine capacity pressure',recommendation='Request explicit historical occupancy analysis; no cleanup is executed.')
                            finding['delivery']=notify(config,finding)
                            store.db.execute('INSERT INTO alerts(fingerprint,ts,payload) VALUES(?,?,?)',(fingerprint,time.time(),json.dumps(finding)))
                    store.db.execute('INSERT OR REPLACE INTO volumes VALUES(?,?)',(row['path'],json.dumps(row)))
                    store.db.execute('INSERT INTO volume_history(ts,payload) VALUES(?,?)',(time.time(),json.dumps(row)))
                self.last_volume=time.time()
            store.prune(config['retention']['max_snapshots'],config['retention']['max_events'])
        return {'enabled':True,'roots':len(paths),'active_cycles':len(self.cycles),'completed_roots':len(self.completed),'pending_roots':sum(p not in self.completed for p in paths)}


def worker(max_ticks=None):
    config=load();data=config['data_dir']
    if not config['enabled'] or host_disabled() or config.get('version')!=2:return {'enabled':False}
    data.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (data/'worker.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'already_running':True}
        runner=Runner(config);ticks=0
        try:
            while True:
                try:
                    result=runner.step();ticks+=1
                    atomic(data/'worker.json',{'pid':os.getpid(),'version':__version__,'last_tick':time.time(),'last_error':None,'progress':result})
                    if not result['enabled'] or (max_ticks and ticks>=max_ticks):break
                    time.sleep(runner.config['monitor']['interval_seconds'])
                except Exception as exc:
                    atomic(data/'worker.json',{'pid':os.getpid(),'version':__version__,'last_tick':time.time(),'last_error':type(exc).__name__})
                    break
        finally:runner.close()
        return {'ticks':ticks,'enabled':load()['enabled']}


def tick(rounds=1):
    config=load();data=config['data_dir']
    if not config['enabled'] or host_disabled() or config.get('version')!=2:return {'enabled':False}
    data.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (data/'worker.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'already_running':True}
        runner=Runner(config)
        try:
            for _ in range(rounds):
                result=runner.step()
                if result.get('active_cycles')==0 and result.get('pending_roots',0)==0:break
        finally:runner.close()
    return status(load())


def operate(name,args=None):
    args=args or {};config=load();data=config['data_dir']
    if name=='status':return status(config)
    if name=='test-notification':return notify(config,{'kind':'acceptance_probe'})
    if name=='scan':
        if not config['enabled'] or host_disabled():return {'schema_version':2,'queued':False,'reason':'observer disabled','observer':status(config)}
        atomic(data/'refresh.request',{'requested_at':time.time()});ensure_worker(config,force=True)
        return {'schema_version':2,'queued':True,'observer':status(config)}
    if name=='analyze-history':
        from .historical import analyze
        return analyze(config,args)
    if name=='alerts':
        ack=args.get('ack')
        with GlobalStore(data,bool(ack)) as store:
            if ack and store.db:
                if ack=='all':store.db.execute('UPDATE alerts SET acknowledged=1')
                else:store.db.execute('UPDATE alerts SET acknowledged=1 WHERE id=?',(int(ack),))
                store.db.commit()
            return {'schema_version':2,'alerts':store.alerts()}
    with GlobalStore(data) as store:
        roots=store.payloads('inventory');history=store.payloads('history_runs');volumes=store.payloads('volumes')
    associations={}
    with GlobalStore(data) as store:
        if store.db:
            for (session,cwd) in store.db.execute('SELECT DISTINCT session,cwd FROM events'):
                for row in roots:
                    if session and (cwd==row['path'] or Path(row['path']) in Path(cwd).parents):associations.setdefault(row['path'],set()).add(session)
    for row in roots:row['associated_sessions']=sorted(associations.get(row['path'],set()))
    if args.get('session_id'):roots=[r for r in roots if args['session_id'] in r['associated_sessions']]
    if args.get('turn_id'):roots=[]  # Global walks cannot isolate concurrent per-turn byte ownership.
    if name=='cleanup-plan':
        return {'schema_version':2,'execution_supported':False,'reclaim_bytes':None,'plans':[{'path':r['path'],'allocated_bytes':r['allocated_bytes'],'complete':r['complete'],'steps':['Verify the owning project/tool and active users.','Review exact artifacts using the owner tool.','Request separate explicit authorization for any cleanup.']} for r in roots[:args.get('limit',20)]]}
    if args.get('path'):roots=[r for r in roots if r['path']==args['path'] or str(Path(args['path'])) in [f['path'] for f in r.get('top_files',[])]]
    return {'schema_version':2,'roots':sorted(roots,key=lambda r:r['allocated_bytes'],reverse=True)[:args.get('limit',20)],
            'volumes':volumes,'latest_historical_analysis':history[0] if history else None,
            'root_totals_additive':False,'attribution':'temporal/path association, not exclusive process ownership',
            'execution_supported':False,'reclaim_bytes':None,
            'session_filter':args.get('session_id'),'session_filter_supported':True,'session_growth_bytes':None,
            'turn_filter_supported':False,'turn_growth_bytes':None,
            'note':'Global inventory. Overlapping session windows and shared hardlinks prevent adding root/session totals. Query alerts for associated session evidence.'}
