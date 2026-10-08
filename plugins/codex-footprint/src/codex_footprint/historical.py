"""Explicit, bounded, read-only reconstruction of local Codex path evidence."""
from __future__ import annotations
import json
import os
from pathlib import Path
import stat
import time

from .config import data_directory
from .global_store import GlobalStore
from .inventory import files

DEFAULTS={'max_files':2000,'max_records':100000,'max_seconds':10,'max_entries':100000}
PATH_KEYS={'path','file_path','artifact_path','archive','output_path','worktree_path','workspace_path','shared_path','missing_path','installedPath','workspaceDirectory','download_path'}


def structured_paths(value,depth=0):
    if depth>12:return []
    found=[]
    if isinstance(value,str):
        if len(value)>1024*1024:return []
        try:return structured_paths(json.loads(value),depth+1)
        except (ValueError,RecursionError):return []
    if isinstance(value,dict):
        for key,item in value.items():
            if key in PATH_KEYS and isinstance(item,str) and len(item)<=4096 and Path(item).expanduser().is_absolute():found.append(str(Path(item).expanduser()))
            if key not in {'prompt','instructions','base_instructions','cmd','command','arguments','input','env','environment'}:found+=structured_paths(item,depth+1)
    elif isinstance(value,list):
        for item in value[:1000]:found+=structured_paths(item,depth+1)
    return found


def analyze(config,args=None):
    args=args or {};settings=config.get('history',DEFAULTS);data=config['data_dir']
    home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))).expanduser().resolve()
    started=time.monotonic();deadline=started+settings['max_seconds']
    coverage={'adapters':['Codex JSONL session_meta, turn_context, function_call_output and custom_tool_call_output'],'complete':True,'source_directories':[],'files_read':0,'records_read':0,'unknown_record_types':0,'invalid_records':0,'oversized_lines':0,'errors':[],'entries_visited':0,'budgets':settings}
    references={};seen_sources=set();missing=0;shared=0
    def gap(kind,path=None):
        coverage['complete']=False
        if len(coverage['errors'])<30:coverage['errors'].append({'kind':kind,'path':str(path) if path else None})
    def add(path,session,association,source,line):
        p=Path(path).expanduser()
        if not p.is_absolute() or p==Path(p.anchor) or p==Path.home():return
        # A historical record is untrusted data. No symlink traversal or requests to scan root/home.
        if p.is_symlink():gap('symlink_reference_skipped',p);return
        try:p=p.resolve()
        except OSError:gap('unresolvable_reference',p);return
        if p==Path(p.anchor) or p==Path.home() or p==data or data in p.parents:return
        if len(references)>=10000 and str(p) not in references:gap('reference_budget');return
        row=references.setdefault(str(p),{'path':str(p),'association':association,'sessions':set(),'evidence':[]})
        if association=='recorded':row['association']='recorded'
        if session:row['sessions'].add(session)
        if len(row['evidence'])<10:row['evidence'].append({'source_file':str(source),'line':line,'kind':association})
    for folder in (home/'sessions',home/'archived_sessions'):
        if not folder.is_dir():continue
        coverage['source_directories'].append(str(folder))
        for dirpath,dirs,names in os.walk(folder,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(dirpath)/d).is_symlink()]
            for name in names:
                if not name.endswith('.jsonl'):continue
                source=Path(dirpath)/name
                if source.is_symlink():gap('symlink_source',source);continue
                if coverage['files_read']>=settings['max_files'] or time.monotonic()>=deadline:gap('history_budget',source);break
                coverage['files_read']+=1;session=None
                try:
                    with source.open('rb') as stream:
                        number=0
                        while time.monotonic()<deadline and coverage['records_read']<settings['max_records']:
                            raw=stream.readline(1024*1024+1)
                            if not raw:break
                            number+=1;coverage['records_read']+=1
                            if len(raw)>1024*1024:
                                coverage['oversized_lines']+=1;gap('oversized_record',source)
                                while raw and not raw.endswith(b'\n'):raw=stream.readline(1024*1024)
                                continue
                            try:record=json.loads(raw)
                            except (ValueError,UnicodeError,RecursionError):coverage['invalid_records']+=1;gap('invalid_record',source);continue
                            if not isinstance(record,dict):gap('invalid_record',source);continue
                            payload=record.get('payload',{})
                            if not isinstance(payload,dict):continue
                            kind=record.get('type')
                            if kind=='session_meta':
                                value=payload.get('id') or payload.get('session_id')
                                if isinstance(value,str) and len(value)<=256:session=value;seen_sources.add(value)
                                cwd=payload.get('cwd')
                                if isinstance(cwd,str):add(cwd,session,'candidate',source,number)
                            elif kind=='turn_context':
                                cwd=payload.get('cwd')
                                if isinstance(cwd,str):add(cwd,session,'candidate',source,number)
                            elif kind=='response_item':
                                if payload.get('type') in ('function_call_output','custom_tool_call_output'):
                                    for path in structured_paths(payload.get('output')):add(path,session,'recorded',source,number)
                                # Commands, messages and planned patches are intentionally not treated as created artifacts.
                            elif kind not in ('event_msg','compacted','session_end'):
                                coverage['unknown_record_types']+=1;gap('unknown_record_type',source)
                        if time.monotonic()>=deadline or coverage['records_read']>=settings['max_records']:gap('history_budget',source)
                except OSError as exc:gap(type(exc).__name__,source)
            if not coverage['complete'] and (time.monotonic()>=deadline or coverage['files_read']>=settings['max_files'] or coverage['records_read']>=settings['max_records']):break
        if time.monotonic()>=deadline:break
    if not coverage['source_directories']:gap('no_supported_history_sources',home)
    # Strong links are measured first; candidates share a global inode set so parent/nested/shared bytes never inflate totals.
    inode_owners={};items=[];totals={'recorded':0,'candidate':0,'unattributed':0};logical={'recorded':0,'candidate':0,'unattributed':0}
    for reference in sorted(references.values(),key=lambda r:(r['association']!='recorded',r['path'].count(os.sep),r['path'])):
        p=Path(reference['path']);row=dict(reference,sessions=sorted(reference['sessions']),allocated_bytes=0,logical_bytes=0,file_count=0,shared_bytes=0,complete=True)
        try:
            info=p.lstat()
            if stat.S_ISREG(info.st_mode):iterator=iter([('file',{'path':str(p),'allocated_bytes':getattr(info,'st_blocks',0)*512,'logical_bytes':info.st_size,'inode':[info.st_dev,info.st_ino]})])
            elif stat.S_ISDIR(info.st_mode):iterator=files(p,[data])
            else:gap('unsupported_reference',p);continue
        except FileNotFoundError:missing+=1;continue
        except OSError as exc:gap(type(exc).__name__,p);continue
        for kind,item in iterator:
            if time.monotonic()>=deadline or coverage['entries_visited']>=settings['max_entries']:
                row['complete']=False;gap('measurement_budget',p);break
            coverage['entries_visited']+=1
            if kind=='error':row['complete']=False;gap(item['kind'],item['path']);continue
            if kind!='file':continue
            row['file_count']+=1;key=tuple(item['inode']);n=item['allocated_bytes']
            if key in inode_owners:
                row['shared_bytes']+=n;shared+=1;continue
            inode_owners[key]=p;row['allocated_bytes']+=n;row['logical_bytes']+=item['logical_bytes']
        if hasattr(iterator,'close'):iterator.close()
        totals[row['association']]+=row['allocated_bytes'];logical[row['association']]+=row['logical_bytes'];items.append(row)
        if time.monotonic()>=deadline:break
    result={'schema_version':2,'kind':'explicit_historical_occupancy','measured_at':time.time(),'historical_growth_bytes':None,
            'recorded_allocated_bytes':totals['recorded'],'candidate_allocated_bytes':totals['candidate'],'unattributed_allocated_bytes':None,
            'current_measured_unique_allocated_bytes':sum(totals.values()),'logical_bytes':logical,
            'items':sorted(items,key=lambda r:r['allocated_bytes'],reverse=True)[:args.get('limit',100)],'coverage':coverage,
            'missing_paths':missing,'shared_artifacts':shared,'sessions_found':len(seen_sources),
            'association_note':'Recorded links establish references to surviving paths, not creation or exclusive ownership; candidates are excluded from recorded subtotal.',
            'accounting':'allocated file blocks; global inode deduplication; partial coverage is a lower bound; APFS shared extents are not exact reclaimable bytes',
            'execution_supported':False,'reclaim_bytes':None,'elapsed_seconds':time.monotonic()-started}
    with GlobalStore(data,True) as store:
        cursor=store.db.execute('INSERT INTO history_runs(ts,payload) VALUES(?,?)',(time.time(),json.dumps(result)))
        result['analysis_id']=cursor.lastrowid;store.prune(config.get('retention',{'max_snapshots':500})['max_snapshots'],config.get('retention',{}).get('max_events',5000))
    return result
