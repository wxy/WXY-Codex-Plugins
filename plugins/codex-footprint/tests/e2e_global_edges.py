#!/usr/bin/env python3
"""Black-box failure/compatibility scenarios, added before their corresponding fixes."""
import argparse, json, os
from pathlib import Path
import subprocess, sys, tempfile, time, traceback
ENTRY=Path(__file__).resolve().parents[1]/'scripts/codex_footprint.py'
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);out=Path(p.parse_args().output).resolve();out.mkdir(parents=True,exist_ok=True)
    cases=[];transcript=[];report={'command':f'{sys.executable} {__file__} --output {out}','preconditions':'Python >=3.9; disposable filesystem; subprocess support; no credentials/model/real notifications','inputs':'Legacy database, explicit globals, symlink/invalid roots, unsupported historical records, worker crash/restart and external writer','cases':cases}
    def case(name,fn):
        with tempfile.TemporaryDirectory(prefix='footprint-edges-') as d:
            root=Path(d).resolve();work=root/'work';work.mkdir();state=root/'state';codex=root/'codex';codex.mkdir()
            env=dict(os.environ,CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),CODEX_HOME=str(codex),PYTHONDONTWRITEBYTECODE='1')
            def run(*args,env_override=None,check=True,input=None):
                r=subprocess.run([sys.executable,str(ENTRY),*args],text=True,input=input,capture_output=True,env=env_override or env,cwd=root,timeout=20)
                transcript.append({'args':args,'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'input':input})
                if check:assert r.returncode==0,r.stderr
                return json.loads(r.stdout) if r.returncode==0 and r.stdout.strip() else r
            try:
                start=time.monotonic();value=fn(root,work,state,env,run);cases.append({'name':name,'result':'pass','seconds':time.monotonic()-start,'evidence':value})
            except Exception:cases.append({'name':name,'result':'fail','error':traceback.format_exc()})
    def global_default(root,work,state,env,run):
        other=dict(env,XDG_STATE_HOME=str(root/'xdg'),PLUGIN_DATA=str(root/'version-specific'))
        other.pop('CODEX_FOOTPRINT_DATA');other.pop('CODEX_FOOTPRINT_CONFIG')
        value=run('status',env_override=other);assert value['data_directory']==str(root/'xdg/codex-footprint');assert not (root/'xdg').exists();return value
    case('Stable default state ignores per-plugin PLUGIN_DATA and queries remain read-only',global_default)
    def legacy(root,work,state,env,run):
        (work/'old.bin').write_bytes(b'X'*4096);run('init-config','--root',str(work));run('scan')
        db=state/'footprint.sqlite3';original=db.read_bytes();run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox')
        assert db.read_bytes()==original;assert (state/'config.json.v1-backup').exists()
        oldenv=dict(env,CODEX_FOOTPRINT_CONFIG=str(state/'config.json.v1-backup'))
        value=run('report',env_override=oldenv);assert value['allocated_bytes']>=4096;return {'legacy_database':'unchanged','v1_query':value}
    case('Global enable preserves legacy config/database and original snapshot query',legacy)
    def disguised_home(root,work,state,env,run):
        value=run('enable','--root',str(Path.home()/'not-existing/..'),'--no-defaults','--no-start',check=False)
        assert hasattr(value,'returncode') and value.returncode!=0;return {'home_alias':'rejected'}
    case('Canonical root/home aliases are rejected before traversal',disguised_home)
    def sym(root,work,state,env,run):
        outside=root/'outside';outside.mkdir();(outside/'private.bin').write_bytes(b'SECRET'*100)
        (work/'linked').symlink_to(outside,target_is_directory=True)
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox');run('tick','--rounds','20');value=run('report')
        assert value['roots'][0]['allocated_bytes']==0;return value
    case('Metadata observer does not follow child symlinks',sym)
    def malformed(root,work,state,env,run):
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox')
        path=state/'config.json';raw=json.loads(path.read_text());raw['misspelled_setting']=1;path.write_text(json.dumps(raw))
        value=run('hook',input=json.dumps({'hook_event_name':'PreToolUse','session_id':'s','cwd':str(work),'tool_input':{'command':'SECRET'}}))
        assert value.returncode==0 and value.stdout=='' and value.stderr
        assert not (state/'spool').exists();return {'invalid_configuration':'fail-open without event recording'}
    case('Invalid configuration cannot block Codex or persist sensitive hook input',malformed)
    def exclusions(root,work,state,env,run):
        (work/'ignore').mkdir();(work/'ignore/private.bin').write_bytes(b'X'*4096)
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox');path=state/'config.json';raw=json.loads(path.read_text());raw['exclude_names']=['ignore'];path.write_text(json.dumps(raw))
        run('tick','--rounds','20');value=run('report');assert value['roots'][0]['allocated_bytes']==0;return value
    case('Global exclusions are applied to actual directory traversal',exclusions)
    def history_budget(root,work,state,env,run):
        folder=Path(env['CODEX_HOME'])/'sessions';folder.mkdir()
        (folder/'a.jsonl').write_text('\n'.join(json.dumps({'type':'session_meta','payload':{'id':str(i),'cwd':str(work)}}) for i in range(20))+'\n')
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox');path=state/'config.json';raw=json.loads(path.read_text());raw['history']['max_records']=1;path.write_text(json.dumps(raw))
        value=run('analyze-history');assert not value['coverage']['complete'];assert value['historical_growth_bytes'] is None;return value
    case('Historical parsing budget is visible and never invents growth',history_budget)
    def worker_recovery(root,work,state,env,run):
        run('enable','--root',str(work),'--no-defaults','--notifications','inbox')
        pid=None
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                status=run('status')
                if status['worker']['running']:pid=status['worker']['pid'];break
                time.sleep(.05)
            assert pid
            os.kill(pid,9)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and run('status')['worker']['running']:time.sleep(.05)
            payload=json.dumps({'hook_event_name':'PreToolUse','session_id':'recovery','cwd':str(work),'tool_name':'Bash'})
            run('hook',input=payload)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                status=run('status')
                if status['worker']['running'] and status['worker']['pid']!=pid:break
                time.sleep(.05)
            assert status['worker']['running'] and status['worker']['pid']!=pid;pid=status['worker']['pid'];return {'restarted_by_trusted_hook':True}
        finally:
            run('disable')
            if pid:
                try:os.kill(pid,9)
                except ProcessLookupError:pass
    case('A later trusted lifecycle event restarts a crashed global worker',worker_recovery)
    def idle_growth(root,work,state,env,run):
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox')
        path=state/'config.json';raw=json.loads(path.read_text());raw['monitor'].update(interval_seconds=.05,refresh_seconds=.05,slice_entries=20,autostart=True);raw['thresholds']['growth_bytes']=4096;path.write_text(json.dumps(raw))
        run('hook',input=json.dumps({'hook_event_name':'PreToolUse','session_id':'long-tool','cwd':str(work),'tool_name':'Bash'}))
        pid=None
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                status=run('status');pid=status['worker']['pid']
                if status['snapshot_count']>=1:break
                time.sleep(.05)
            subprocess.run([sys.executable,'-c','from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"X"*16384)',str(work/'external.bin')],check=True)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                alerts=run('alerts')['alerts']
                if any(x['kind']=='growth' for x in alerts):break
                time.sleep(.05)
            row=next(x for x in alerts if x['kind']=='growth');assert 'long-tool' in row['associated_sessions']
            (Path(env['CODEX_HOME'])/'config.toml').write_text('[plugins."codex-footprint@wxy-codex-plugins"]\nenabled = false\n')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and run('status')['worker']['running']:time.sleep(.05)
            assert not run('status')['worker']['running']
            return {'no_post_tool_event_needed':True,'host_disable_stops_worker':True}
        finally:
            run('disable')
            if pid:
                try:os.kill(pid,9)
                except ProcessLookupError:pass
    case('Independent polling captures a long tool writer; host plugin disable stops observation',idle_growth)
    def notification_probe(root,work,state,env,run):
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox')
        value=run('test-notification');assert value['status']=='inbox_only';assert run('alerts')['alerts']==[];return value
    case('Notification acceptance probe is separate from production findings',notification_probe)
    def changed_scope(root,work,state,env,run):
        (work/'ignore').mkdir();(work/'ignore/old.bin').write_bytes(b'X'*16384)
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox');run('tick','--rounds','20')
        path=state/'config.json';raw=json.loads(path.read_text());raw['exclude_names']=['ignore'];raw['thresholds']['growth_bytes']=4096;path.write_text(json.dumps(raw))
        (work/'new.bin').write_bytes(b'X'*4096);run('tick','--rounds','20');value=run('report')
        assert value['roots'][0]['growth_bytes'] is None;assert run('alerts')['alerts']==[]
        return {'changed_measurement_scope':'new baseline, unknown growth'}
    case('Changing exclusions invalidates the previous measurement baseline',changed_scope)
    def manual_scan(root,work,state,env,run):
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox');run('tick','--rounds','20')
        (work/'new.bin').write_bytes(b'X'*8192);pid=None
        try:
            value=run('scan');assert value['queued']
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                report=run('report');status=run('status');pid=status['worker']['pid']
                if report['roots'] and report['roots'][0]['allocated_bytes']>=8192:break
                time.sleep(.05)
            assert report['roots'][0]['allocated_bytes']>=8192
            return {'explicit_scan':'refreshes despite automatic startup disabled'}
        finally:
            run('disable')
            if pid:
                try:os.kill(pid,9)
                except ProcessLookupError:pass
    case('Explicit scan enqueues a real refresh and starts the worker when needed',manual_scan)
    def event_retention(root,work,state,env,run):
        run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox')
        path=state/'config.json';raw=json.loads(path.read_text());raw['retention'].update(max_snapshots=2,max_events=3);path.write_text(json.dumps(raw))
        for i in range(5):run('hook',input=json.dumps({'hook_event_name':'PreToolUse','session_id':str(i),'cwd':str(work),'tool_name':'Bash'}))
        run('tick','--rounds','20');value=run('status');assert value['event_count']==3;return value
    case('Configured global event retention is enforced',event_retention)
    def many_roots(root,work,state,env,run):
        roots=[]
        for i in range(70):
            child=work/str(i);child.mkdir();roots+=['--root',str(child)]
            for j in range(20):(child/str(j)).write_bytes(b'X')
        run('enable',*roots,'--no-defaults','--no-start','--notifications','inbox')
        path=state/'config.json';raw=json.loads(path.read_text());raw['monitor']['slice_seconds']=.9;path.write_text(json.dumps(raw))
        value=run('tick');visited=sum(r['entries_visited'] for r in value['roots'])
        assert 600<=visited<=1000;assert any(r['finished'] for r in value['roots'])
        return {'entries_in_one_tick':visited,'budget':1000,'root_count':70}
    case('Many discovered roots share the full bounded slice without starving initial inventory',many_roots)
    report.update(passed=sum(c['result']=='pass' for c in cases),failed=sum(c['result']=='fail' for c in cases),environment={'python':sys.version,'platform':sys.platform})
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(out/'transcript.json').write_text(json.dumps(transcript,ensure_ascii=False,indent=2)+'\n');(out/'report.md').write_text('# Global edge-case E2E\n\n'+'\n'.join(c['result'].upper()+': '+c['name'] for c in cases)+'\n')
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'report':str(out/'report.json')}));return bool(report['failed'])
if __name__=='__main__':raise SystemExit(main())
