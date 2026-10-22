#!/usr/bin/env python3
"""CLI acceptance for persistent runtime pinning and safe version handoff."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback

PLUGIN=Path(__file__).resolve().parents[1]
ENTRY=PLUGIN/'scripts/codex_footprint.py'
VERSION=json.loads((PLUGIN/'.codex-plugin/plugin.json').read_text())['version']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    report={'command':[sys.executable,str(Path(__file__).resolve()),'--output',args.output],
            'preconditions':'macOS/Unix with lsof; disposable profile, state, worker subprocesses; no login-service changes or native notifications.',
            'inputs':'Existing stale baseline table with newer retained inventory; evicted plugin cache; detached old worker; unrelated lock-holder PID.',
            'failure_model':['cache eviction must not remove the stable CLI','existing baseline table may lag a legacy writer','old detached worker holds the singleton lock after service restart','unrelated or stale PID must not be signalled','disabled monitoring must remain disabled','copies/pointers must be staged before activation'],
            'cases':[]}
    def case(name,fn):
        with tempfile.TemporaryDirectory(prefix='footprint-runtime-e2e-') as directory:
            tmp=Path(directory).resolve();state=tmp/'state';profile=tmp/'profile';profile.mkdir()
            root=tmp/'project';root.mkdir();processes=[]
            env=dict(os.environ,CODEX_HOME=str(profile),CODEX_FOOTPRINT_DATA=str(state),
                     CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),CODEX_FOOTPRINT_PANEL_PORT='0',PYTHONDONTWRITEBYTECODE='1')
            def run(*argv,entry=ENTRY,check=True):
                p=subprocess.run([sys.executable,str(entry),*argv],env=env,cwd=tmp,capture_output=True,text=True,timeout=25)
                if check:assert p.returncode==0,p.stderr[:1000]
                return json.loads(p.stdout) if check else p
            def start(entry,command='worker'):
                p=subprocess.Popen([sys.executable,str(entry),command],env=env,cwd=tmp,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(p);return p
            def wait(fn):
                end=time.monotonic()+12
                while time.monotonic()<end:
                    value=fn()
                    if value:return value
                    time.sleep(.1)
                raise AssertionError('worker condition not reached')
            def clone(name):
                target=tmp/'cache'/name
                shutil.copytree(PLUGIN,target,ignore=shutil.ignore_patterns('__pycache__','dist','artifacts','tests','docs'))
                return target
            try:
                run('enable','--root',str(root),'--no-defaults','--no-start','--notifications','inbox')
                evidence=fn(tmp,root,state,run,start,wait,clone,processes,env)
                report['cases'].append({'name':name,'result':'pass','evidence':evidence})
            except Exception:
                report['cases'].append({'name':name,'result':'fail','error':traceback.format_exc()})
            finally:
                for p in processes:
                    if p.poll() is None:p.terminate()
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
        assert not tmp.exists()
    def stale(tmp,root,state,run,*_):
        (root/'base').write_bytes(b'x'*4096)
        before=run('tick','--rounds','10')['roots'][0]
        old=dict(before,allocated_bytes=0,measured_at=before['measured_at']-86400)
        with sqlite3.connect(state/'global.sqlite3') as db:
            db.execute('UPDATE baselines SET ts=?,payload=? WHERE path=?',(old['measured_at'],json.dumps(old),str(root)))
            db.execute('DELETE FROM observations')
            # No recovery receipt: emulate newer tables left behind by an older active writer.
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_migrations'").fetchone():
                db.execute('DELETE FROM runtime_migrations')
        (root/'growth').write_bytes(b'y'*65536)
        after=run('tick','--rounds','10')['roots'][0]
        assert after['growth_bytes']==65536,after
        assert after['baseline_at']==before['measured_at'],after
        return {'existing_table_reconciled':True,'growth_bytes':after['growth_bytes']}
    case('existing_baselines_recover_newer_complete_inventory',stale)
    def pin(tmp,root,state,run,start,wait,clone,*_):
        cache=clone('codex-footprint')
        result=run('prepare-runtime',entry=cache/'scripts/codex_footprint.py')
        target=(state/'runtime').resolve()
        assert cache not in target.parents and target!=cache
        cache.rename(tmp/'evicted-cache')
        p=run('--version',entry=state/'runtime/scripts/codex_footprint.py',check=False)
        assert p.returncode==0 and p.stdout.strip()==VERSION,p.stderr
        assert not (state/'global.sqlite3').exists()
        assert json.loads((state/'config.json').read_text())['monitor']['autostart'] is False
        return {'stable_cli_survives_cache_eviction':True,'monitor_not_started':True}
    case('pinned_runtime_survives_plugin_cache_eviction',pin)
    def handoff(tmp,root,state,run,start,wait,clone,*_):
        old=clone('old-codex-footprint')
        version=old/'src/codex_footprint/__init__.py'
        version.write_text(version.read_text().replace(VERSION,'0.0.0'))
        p=start(old/'scripts/codex_footprint.py')
        wait(lambda:run('status')['worker'].get('version')=='0.0.0')
        run('prepare-runtime')
        supervisor=start(state/'runtime/scripts/codex_footprint.py','supervise')
        current=wait(lambda:(s if s['worker'].get('version')==VERSION and s['worker']['pid']!=p.pid else None) if (s:=run('status')) else None)
        assert p.wait(timeout=5) is not None
        assert supervisor.poll() is None
        return {'old_pid_retired':True,'new_worker_running':current['worker']['running'],'version':VERSION}
    case('supervisor_replaces_detached_old_worker',handoff)
    def unrelated(tmp,root,state,run,start,wait,clone,processes,env):
        lock=state/'worker.lock'
        code='import fcntl,time,sys;f=open(sys.argv[1],"a+");fcntl.flock(f,fcntl.LOCK_EX);time.sleep(20)'
        p=subprocess.Popen([sys.executable,'-c',code,str(lock)],env=env);processes.append(p);time.sleep(.2)
        (state/'worker.json').write_text(json.dumps({'pid':p.pid,'version':'0.0.0','last_tick':time.time()}))
        result=run('supervise',check=False)
        assert result.returncode!=0 and p.poll() is None
        return {'unrelated_process_preserved':True}
    case('version_handoff_refuses_unrelated_lock_holder',unrelated)
    def vm_scope(tmp,root,state,run,*_):
        vm=Path('/System/Volumes/VM')
        if sys.platform!='darwin' or not vm.is_dir():return {'not_applicable':True}
        value=run('enable','--root',str(vm),'--no-defaults','--no-start','--notifications','inbox')
        assert str(vm) in value['configured_roots'],value['configured_roots']
        assert value['snapshot_count']==0,'admission test must not scan real swap files'
        return {'internal_vm_volume_admitted':True,'metadata_only_no_scan':True}
    case('internal_vm_volume_admission',vm_scope)
    report['passed']=sum(c['result']=='pass' for c in report['cases']);report['failed']=len(report['cases'])-report['passed']
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'report':str(out)}))
    return int(report['failed']!=0)
if __name__=='__main__':raise SystemExit(main())
