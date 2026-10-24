#!/usr/bin/env python3
"""CLI acceptance for the six review follow-ups; no personal monitoring state."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile

PLUGIN=Path(__file__).resolve().parents[1]
ENTRY=PLUGIN/'scripts/codex_footprint.py'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--case');args=ap.parse_args()
    report={'command':[sys.executable,str(Path(__file__).resolve()),'--output',args.output],
            'environment':{'platform':sys.platform,'python':sys.version,'euid':os.geteuid()},
            'preconditions':'Unix metadata, subprocess workers and SQLite; no personal config or service changes.',
            'inputs':'Temporary project trees, real lifecycle events, retained complete/partial records, ZIP output.',
            'failure_model':['cooled urgent walker fills the reserved slot','same-day failed attempt hides an old complete endpoint','today inventory contaminates a historical day','rolling retention erases historical partial evidence','archive omits the documented browser driver','native-only expectations run on polling/root hosts'],
            'cases':[]}
    def case(name,fn):
        if args.case and name!=args.case:return
        with tempfile.TemporaryDirectory(prefix='footprint-review-followups-') as directory:
            tmp=Path(directory).resolve();root=tmp/'project';root.mkdir();state=tmp/'state';home=tmp/'home';home.mkdir();workers=[]
            env=dict(os.environ,CODEX_HOME=str(home),CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),CODEX_FOOTPRINT_PANEL_PORT='0',PYTHONDONTWRITEBYTECODE='1')
            def cli(*argv):
                r=subprocess.run([sys.executable,str(ENTRY),*argv],cwd=tmp,env=env,text=True,capture_output=True,timeout=30)
                assert r.returncode==0,r.stderr[:1200]
                return json.loads(r.stdout)
            def cfg(**sections):
                path=state/'config.json';value=json.loads(path.read_text())
                for key,item in sections.items():
                    if isinstance(item,dict):value.setdefault(key,{}).update(item)
                    else:value[key]=item
                path.write_text(json.dumps(value))
            def wait(fn,seconds=10):
                end=time.monotonic()+seconds
                while time.monotonic()<end:
                    value=fn()
                    if value:return value
                    time.sleep(.15)
                raise AssertionError('condition not reached within %ss'%seconds)
            def hook(path):
                value={'hook_event_name':'UserPromptSubmit','cwd':str(path),'session_id':'fixture'}
                r=subprocess.run([sys.executable,str(ENTRY),'hook'],input=json.dumps(value),cwd=tmp,env=env,text=True,capture_output=True,timeout=10)
                assert r.returncode==0,r.stderr
            try:
                cli('enable','--root',str(root),'--no-defaults','--no-start','--notifications','inbox')
                result=fn(tmp,root,state,cli,cfg,wait,hook,workers,env)
                report['cases'].append({'name':name,'result':'pass','evidence':result})
            except Exception:report['cases'].append({'name':name,'result':'fail','error':traceback.format_exc()})
            finally:
                for worker in workers:
                    if worker.poll() is None:worker.terminate()
                    try:worker.wait(timeout=5)
                    except subprocess.TimeoutExpired:worker.kill();worker.wait(timeout=5)
        assert not tmp.exists()
    def cooled(tmp,root,state,cli,cfg,wait,hook,workers,env):
        soft,_=resource.getrlimit(resource.RLIMIT_NOFILE);capacity=max(1,min(8,(int(soft)-64)//132))
        busy=[]
        for i in range(capacity):
            folder=tmp/('busy-%02d'%i);folder.mkdir();busy.append(folder)
            for j in range(1000):(folder/str(j)).write_bytes(b'x')
        cfg(roots=[{'path':str(p)} for p in busy],monitor={'event_backend':'polling'})
        cli('tick','--rounds','100')
        old=busy[-1]
        with sqlite3.connect(state/'global.sqlite3') as db:baseline=db.execute('SELECT ts FROM baselines WHERE path=?',(str(old),)).fetchone()[0]
        cfg(monitor={'slice_entries':1,'scan_interval_seconds':0.2})
        worker=subprocess.Popen([sys.executable,str(ENTRY),'worker'],cwd=tmp,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);workers.append(worker)
        wait(lambda:cli('status')['worker'].get('progress',{}).get('active_cycles',0)>=max(1,capacity-1))
        hook(old)
        wait(lambda:cli('status')['worker']['progress']['active_cycles']==capacity)
        # Exercise the actual 60-second lifecycle window, without replacing the clock or runtime.
        time.sleep(61)
        assert cli('status')['worker']['progress']['pending_roots']>0
        (root/'base').write_bytes(b'x'*4096);hook(root);began=time.monotonic()
        def done():
            return next((r for r in cli('status')['roots'] if r['path']==str(root) and r.get('complete')),None)
        wait(done,8)
        assert cli('status')['worker']['progress']['preempted_incomplete_walks']>0
        with sqlite3.connect(state/'global.sqlite3') as db:assert db.execute('SELECT ts FROM baselines WHERE path=?',(str(old),)).fetchone()[0]==baseline
        assert cli('status')['worker']['progress']['active_cycles']<=capacity
        return {'real_hot_window_seconds':60,'next_project_seconds':time.monotonic()-began,'old_complete_baseline_preserved':True,'cursor_capacity':capacity}
    case('cooled_urgent_walker_does_not_block_next_project',cooled)
    def stale(tmp,root,state,cli,*_):
        cli('tick','--rounds','10');value=cli('status')['roots'][0];old=time.time()-10000;value.update(measured_at=old)
        partial=dict(value,complete=False,finished=True,measured_at=time.time(),error_count=1)
        with sqlite3.connect(state/'global.sqlite3') as db:
            db.execute('UPDATE baselines SET ts=?,payload=? WHERE path=?',(old,json.dumps(value),str(root)))
            db.execute('UPDATE inventory SET payload=? WHERE path=?',(json.dumps(partial),str(root)))
        s=cli('status');r=s['roots'][0]
        assert r['stale'] and r['coverage_status']=='partial',r
        assert r['last_complete_at']==old and r['measurement_age_seconds']>9000,r
        assert r['latest_attempt_at']==partial['measured_at'],r
        assert str(root) in s['coverage']['stale_roots'] and str(root) in s['coverage']['partial_roots']
        return {'old_complete_remains_stale':True,'failed_attempt_is_separate':True}
    case('recent_partial_attempt_does_not_refresh_complete_age',stale)
    def history(tmp,root,state,cli,*_):
        cli('tick','--rounds','10');value=cli('status')['roots'][0]
        yesterday=(dt.date.today()-dt.timedelta(days=1)).isoformat();begin=dt.datetime.combine(dt.date.fromisoformat(yesterday),dt.time()).timestamp()
        def observation(row):
            with sqlite3.connect(state/'global.sqlite3') as db:db.execute('INSERT INTO observations(path,ts,payload) VALUES(?,?,?)',(str(root),row['measured_at'],json.dumps(row)))
        observation(dict(value,measured_at=begin+10));observation(dict(value,measured_at=begin+86390))
        partial=dict(value,complete=False,finished=True,error_count=1,measured_at=time.time())
        with sqlite3.connect(state/'global.sqlite3') as db:db.execute('UPDATE inventory SET payload=? WHERE path=?',(json.dumps(partial),str(root)))
        assert str(root) not in cli('daily-report','--day',yesterday)['coverage']['partial_roots'],'today failure contaminated yesterday'
        observation(dict(partial,measured_at=begin+500))
        with sqlite3.connect(state/'global.sqlite3') as db:db.execute('UPDATE inventory SET payload=? WHERE path=?',(json.dumps(value),str(root)))
        assert str(root) in cli('daily-report','--day',yesterday)['coverage']['partial_roots'],'yesterday failure lost after current success'
        with sqlite3.connect(state/'global.sqlite3') as db:db.execute('DELETE FROM observations')
        report=cli('daily-report','--day',yesterday)
        assert str(root) in report['coverage']['partial_roots'],'retention erased historical failure'
        assert report['full_disk_scan_triggered'] is False
        assert report['coverage']['full_day'] is False
        return {'requested_day_isolated':True,'partial_evidence_survives_retention':True}
    case('historical_partial_coverage_uses_requested_day',history)
    def package(tmp,root,state,cli,*_):
        result=cli('package','--output',str(tmp/'bundle'))
        with zipfile.ZipFile(result['archive']) as z:
            name='codex-footprint/tests/e2e_dashboard_browser.mjs';content=z.read(name)
        assert hashlib.sha256(content).digest()==hashlib.sha256((PLUGIN/'tests/e2e_dashboard_browser.mjs').read_bytes()).digest()
        return {'documented_browser_driver_packaged':True}
    case('package_contains_browser_acceptance_driver',package)
    def reliability(tmp,root,state,cli,cfg,wait,hook,workers,env,native=False):
        name='native_local_burst_preserves_unrelated_root' if native else 'production_budget_61_roots_and_external_growth'
        target=tmp/'reliability.json'
        r=subprocess.run([sys.executable,str(PLUGIN/'tests/e2e_monitor_reliability.py'),'--output',str(target),'--case',name,'--event-backend','polling'],env=env,cwd=tmp,text=True,capture_output=True,timeout=40)
        d=json.loads(target.read_text()) if target.exists() else {}
        assert r.returncode==0,(r.stderr or r.stdout,d)

        if native:assert d['skipped']==1 and d['passed']==0,d
        else:assert d['passed']==1 and d['failed']==0,d
        return {'forced_polling':True,'skipped':d.get('skipped',0),'passed':d['passed']}
    case('polling_production_expectations_are_bounded',reliability)
    case('native_acceptance_reports_skip_for_polling',lambda *a:reliability(*a,native=True))
    report['passed']=sum(c['result']=='pass' for c in report['cases']);report['failed']=len(report['cases'])-report['passed']
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'report':str(out)}));return int(report['failed']!=0)
if __name__=='__main__':raise SystemExit(main())
