#!/usr/bin/env python3
"""Real native events, durable chart history and nonblocking hook delivery acceptance."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

ENTRY=Path(os.environ.get('CODEX_FOOTPRINT_TEST_ENTRY',str(Path(__file__).resolve().parents[1]/'scripts/codex_footprint.py'))).resolve()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--case');args=ap.parse_args()
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    report={'command':[sys.executable,str(Path(__file__).resolve()),'--output',str(out)],'environment':{'python':sys.version,'platform':sys.platform},'preconditions':'macOS public FSEvents for native cases; local filesystem, subprocesses, loopback; no personal state or native notifications','inputs':'Generated temporary Unicode project roots, external writes/rename/delete, excluded directories, eight days of minute capacity samples and concurrent hook clients','runtime_entry':str(ENTRY),'cases':[]}
    if args.case:report['command']+=['--case',args.case]
    def case(name,fn):
        if args.case and args.case!=name:return
        with tempfile.TemporaryDirectory(prefix='footprint-events-e2e-') as directory:
            tmp=Path(directory).resolve();work=tmp/'项目';work.mkdir();state=tmp/'state';home=tmp/'home';home.mkdir();processes=[]
            env=dict(os.environ,CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),CODEX_HOME=str(home),CODEX_FOOTPRINT_PANEL_PORT='0',PYTHONDONTWRITEBYTECODE='1')
            def run(*argv,input=None):
                p=subprocess.run([sys.executable,str(ENTRY),*argv],env=env,input=input,text=True,capture_output=True,timeout=20)
                assert p.returncode==0,p.stderr
                return json.loads(p.stdout) if p.stdout.strip() else None
            def configure(**sections):
                path=state/'config.json';r=json.loads(path.read_text())
                for k,v in sections.items():
                    if isinstance(v,dict):r.setdefault(k,{}).update(v)
                    else:r[k]=v
                path.write_text(json.dumps(r))
            def wait(fn,seconds=15):
                end=time.monotonic()+seconds
                while time.monotonic()<end:
                    value=fn()
                    if value:return value
                    time.sleep(.1)
                raise AssertionError('condition not reached within %ss'%seconds)
            def start(descriptor_limit=None,hard_descriptor_limit=None):
                def restrict():
                    import resource
                    resource.setrlimit(resource.RLIMIT_NOFILE,(descriptor_limit,hard_descriptor_limit or resource.getrlimit(resource.RLIMIT_NOFILE)[1]))
                p=subprocess.Popen([sys.executable,str(ENTRY),'worker'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,preexec_fn=restrict if descriptor_limit else None);processes.append(p)
                wait(lambda:run('status')['worker']['running']);return p
            def root(path=work):return next((r for r in run('status')['roots'] if r['path']==str(path)),{})
            def count(path=work):
                with sqlite3.connect(state/'global.sqlite3') as db:return db.execute('SELECT count(*) FROM observations WHERE path=?',(str(path),)).fetchone()[0]
            def write(path,size):
                subprocess.run([sys.executable,'-c','import sys;from pathlib import Path;Path(sys.argv[1]).write_bytes(b"X"*int(sys.argv[2]))',str(path),str(size)],check=True)
            run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox')
            start_time=time.monotonic()
            try:
                evidence=fn(tmp,work,state,env,run,configure,wait,start,root,count,write)
                report['cases'].append({'name':name,'result':'pass','seconds':time.monotonic()-start_time,'evidence':evidence})
            except Exception:report['cases'].append({'name':name,'result':'fail','error':traceback.format_exc()})
            finally:
                for p in processes:
                    if p.poll() is None:p.terminate()
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
        assert not tmp.exists()
    def native(tmp,work,state,env,run,cfg,wait,start,root,count,write):
        cfg(monitor={'event_backend':'auto','reconcile_seconds':3600,'interval_seconds':.1,'refresh_seconds':.2},exclude_names=['ignored'],thresholds={'growth_bytes':65536})
        (work/'ignored').mkdir();write(work/'base',4096);start()
        wait(lambda:root().get('complete'))
        s=run('status')['worker']['progress']['filesystem_events'];assert s['backend']=='fsevents' and s['healthy'],s
        time.sleep(1.5);before=count();time.sleep(1.2);assert count()==before, 'quiet directory was rescanned'
        write(work/'ignored/excluded',100000);time.sleep(1.8);assert count()==before,'excluded change triggered scan'
        write(work/'growth',131072);wait(lambda:root().get('allocated_bytes',0)>=135168)
        assert any(a['kind']=='growth' for a in run('alerts')['alerts'])
        count_before=count()
        for i in range(30):write(work/('burst-%d'%i),4096)
        wait(lambda:root().get('file_count',0)>=32)
        assert count()-count_before<20,'event burst caused excessive full-root scans'
        assert run('status')['history_analysis_count']==0
        return {'native_stream':s,'quiet_and_excluded_paths_idle':True,'external_growth_detected':True,'burst_coalesced':True}
    case('native_idle_external_growth_exclusions_burst',native)
    def descriptors(tmp,work,state,env,run,cfg,wait,start,root,count,write):
        roots=[work]
        for i in range(59):
            p=tmp/('root-%02d'%i);p.mkdir();roots.append(p)
        cfg(roots=[{'path':str(p)} for p in roots],monitor={'event_backend':'auto','reconcile_seconds':3600,'interval_seconds':.1,'refresh_seconds':.2})
        start(descriptor_limit=256)
        wait(lambda:root().get('complete'))
        status=run('status')['worker']['progress']['filesystem_events']
        assert status['backend']=='fsevents' and status['healthy'] and status['watched_roots']==60,status
        write(roots[-1]/'external-growth',16384);wait(lambda:root(roots[-1]).get('allocated_bytes',0)>=16384)
        return {'inherited_soft_descriptor_limit':256,'native_watch_roots':60,'external_growth_detected':True,'stream':status}
    case('native_many_roots_low_descriptor_limit',descriptors)
    def hard_descriptors(tmp,work,state,env,run,cfg,wait,start,root,count,write):
        roots=[work]
        for i in range(59):
            p=tmp/('root-%02d'%i);p.mkdir();roots.append(p)
        cfg(roots=[{'path':str(p)} for p in roots],monitor={'event_backend':'auto','reconcile_seconds':3600,'interval_seconds':.1,'refresh_seconds':.2})
        start(descriptor_limit=256,hard_descriptor_limit=256);wait(lambda:root().get('complete'))
        status=run('status')['worker']['progress']['filesystem_events']
        assert status['backend']=='polling' and not status['healthy'],status
        write(work/'fallback-growth',16384);wait(lambda:root().get('allocated_bytes',0)>=16384)
        return {'hard_descriptor_limit':256,'fallback':'polling','external_growth_detected':True}
    case('native_hard_descriptor_ceiling_polling',hard_descriptors)
    def scope(tmp,work,state,env,run,cfg,wait,start,root,count,write):
        cfg(monitor={'event_backend':'auto','reconcile_seconds':3600,'interval_seconds':.1,'refresh_seconds':.2});start();wait(lambda:root().get('complete'))
        new=tmp/'another';new.mkdir();write(new/'artifact',4096)
        run('hook',input=json.dumps({'hook_event_name':'PreToolUse','session_id':'new-scope','cwd':str(new),'tool_name':'Bash'}))
        wait(lambda:root(new).get('complete'));write(new/'growth',65536);wait(lambda:root(new).get('allocated_bytes',0)>=69632)
        moved=tmp/'moved';work.rename(moved);wait(lambda:root().get('finished') and not root().get('complete'))
        work.mkdir();write(work/'recreated',8192);wait(lambda:root().get('complete') and root().get('allocated_bytes',0)>=8192)
        return {'dynamic_root_observed':True,'root_rename_incomplete':True,'recreated_root_recovered':True}
    case('native_dynamic_scope_root_rename_recreation',scope)
    def polling(tmp,work,state,env,run,cfg,wait,start,root,count,write):
        cfg(monitor={'event_backend':'polling','interval_seconds':.1,'refresh_seconds':.2});start();wait(lambda:root().get('complete'))
        assert run('status')['worker']['progress']['filesystem_events']['backend']=='polling'
        write(work/'fallback',8192);wait(lambda:root().get('allocated_bytes',0)>=8192)
        return {'explicit_polling_detects_external_writes':True}
    case('explicit_polling_fallback',polling)
    def retention(tmp,work,state,env,run,cfg,wait,start,root,count,write):
        run('tick');cfg(retention={'max_snapshots':2});now=time.time();device=run('status')['volumes'][0]['device'];bucket=int(now//60)
        with sqlite3.connect(state/'global.sqlite3') as db:
            for i in range(1600):
                ts=(bucket-i)*60
                row={'path':'/fixture-volume','device':device,'available_bytes':40000000000+i*1000000,'sampled_at':ts,'total_bytes':250000000000}
                db.execute('INSERT OR REPLACE INTO volume_minutes VALUES(?,?,?,?)',(device,bucket-i,ts,json.dumps(row)))
            row={'path':'/old','device':device,'available_bytes':1,'sampled_at':now-8*86400}
            db.execute('INSERT OR REPLACE INTO volume_minutes VALUES(?,?,?,?)',(device,int(row['sampled_at']//60),row['sampled_at'],json.dumps(row)))
        run('tick','--rounds','8');dashboard=run('dashboard');assert dashboard['chart_window']['requested_range']=='24h';assert dashboard['chart_window']['samples']>500
        assert dashboard['volume_history'][-1]['sampled_at']-dashboard['volume_history'][0]['sampled_at']>23*3600
        with sqlite3.connect(state/'global.sqlite3') as db:
            assert db.execute('SELECT count(*) FROM volume_minutes').fetchone()[0]>=1500
            assert db.execute('SELECT min(ts) FROM volume_minutes').fetchone()[0]>now-7*86400
        return {'minute_history_survives_short_snapshot_retention':True,'default_range':'24h','samples':dashboard['chart_window']['samples'],'old_samples_expired':True}
    case('seven_day_volume_history_and_chart_window',retention)
    def notice(tmp,work,state,env,run,cfg,wait,start,root,count,write):
        cfg(monitor={'event_backend':'polling','interval_seconds':.1,'refresh_seconds':.2},thresholds={'growth_bytes':4096});p=start();wait(lambda:root().get('complete'))
        write(work/'growth',16384);wait(lambda:run('alerts')['alerts']);p.terminate();p.wait(timeout=5)
        payload=json.dumps({'hook_event_name':'PreToolUse','session_id':'chat-a','cwd':str(work),'tool_name':'Bash','tool_input':{'command':'SECRET_COMMAND'}})
        def hook(i):
            r=subprocess.run([sys.executable,str(ENTRY),'hook'],env=env,input=payload,text=True,capture_output=True);assert r.returncode==0;return json.loads(r.stdout) if r.stdout else None
        with ThreadPoolExecutor(max_workers=6) as pool:outputs=list(pool.map(hook,range(6)))
        emitted=[x for x in outputs if x];assert len(emitted)==1,outputs
        r=emitted[0];assert set(r)=={'systemMessage','hookSpecificOutput'} and r['hookSpecificOutput']['hookEventName']=='PreToolUse'
        assert 'Codex Footprint' in r['systemMessage'] and 'additionalContext' in r['hookSpecificOutput'];assert 'SECRET_COMMAND' not in json.dumps(r)
        assert hook(7) is None
        alerts=run('alerts')['alerts'];assert all(a['codex_delivery']['status']=='emitted_to_hook_visibility_unverified' for a in alerts)
        assert not any(a['acknowledged'] for a in alerts)
        return {'one_nonblocking_notice_across_six_clients':True,'no_permission_or_input_rewrite':True,'user_acknowledgement_unchanged':True}
    case('codex_hook_notice_concurrent_dedup',notice)
    def quiet(tmp,work,state,env,run,cfg,wait,start,root,count,write):
        cfg(monitor={'event_backend':'polling','interval_seconds':.1,'refresh_seconds':.2},thresholds={'growth_bytes':4096},notifications={'codex_context':False});p=start();wait(lambda:root().get('complete'));write(work/'growth',16384);wait(lambda:run('alerts')['alerts']);p.terminate();p.wait(timeout=5)
        payload=json.dumps({'hook_event_name':'PostToolUse','session_id':'chat-a','cwd':str(work),'tool_name':'Bash'})
        assert run('hook',input=payload) is None
        cfg(notifications={'codex_context':True});run('alerts','--ack','all');assert run('hook',input=payload) is None
        run('disable');assert run('hook',input=payload) is None
        return {'disabled_delivery_and_acknowledged_alerts_quiet':True}
    case('codex_notice_opt_out_ack_disable',quiet)
    report['temporary_process_files_removed']=True;report['result']='pass' if report['cases'] and all(r['result']=='pass' for r in report['cases']) else 'fail'
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'result':report['result'],'cases':[{k:r[k] for k in ('name','result')} for r in report['cases']],'report':str(out/'report.json')}));return report['result']!='pass'
if __name__=='__main__':raise SystemExit(main())
