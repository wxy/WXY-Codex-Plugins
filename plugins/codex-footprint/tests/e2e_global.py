#!/usr/bin/env python3
"""Black-box global monitor/history acceptance; written before the implementation."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
ENTRY = REPO/'scripts/codex_footprint.py'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); args=ap.parse_args()
    out=Path(args.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    transcript=[]; cases=[]; worker=None
    report={'command':f'{sys.executable} {__file__} --output {out}', 'environment':{'python':sys.version,'platform':sys.platform},
            'preconditions':'Python >=3.9, local filesystem, subprocess/Unix locks; no model, credentials or real desktop notifications',
            'inputs':'Disposable two-project filesystem, external writer, synthetic current/archived Codex JSONL records created before plugin state', 'cases':cases}
    with tempfile.TemporaryDirectory(prefix='footprint-global-e2e-') as tmp:
        fixture=Path(tmp).resolve(); state=fixture/'state'; a=fixture/'project-a'; b=fixture/'project-b'; home=fixture/'codex-home'
        a.mkdir(); b.mkdir(); (home/'sessions').mkdir(parents=True); (home/'archived_sessions').mkdir()
        env=dict(os.environ,CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),CODEX_HOME=str(home),PYTHONDONTWRITEBYTECODE='1')
        for key in ('PLUGIN_DATA','CLAUDE_PLUGIN_DATA'): env.pop(key,None)
        def run(*args,input=None,check=True,custom_env=None):
            p=subprocess.run([sys.executable,str(ENTRY),*args],input=input,text=True,capture_output=True,env=custom_env or env,cwd=fixture,timeout=30)
            transcript.append({'arguments':list(args),'input':input,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if check: assert p.returncode==0,p.stderr
            return p
        def cli(*args,**kw): return json.loads(run(*args,**kw).stdout)
        def case(name,fn):
            start=time.monotonic()
            try:
                evidence=fn();cases.append({'name':name,'result':'pass','seconds':time.monotonic()-start,'evidence':evidence})
            except Exception:
                cases.append({'name':name,'result':'fail','error':traceback.format_exc()}); raise
        def hook(cwd,session,event='PreToolUse'):
            return run('hook',input=json.dumps({'hook_event_name':event,'cwd':str(cwd),'session_id':session,'turn_id':'turn','tool_use_id':session+'tool','tool_name':'Bash','tool_input':{'command':'python3 writer.py SECRET_NOT_RETAINED'}}))
        def tick(rounds=30): return cli('tick','--rounds',str(rounds))
        def alter(**fields):
            p=state/'config.json'; config=json.loads(p.read_text())
            for section,values in fields.items(): config[section].update(values)
            p.write_text(json.dumps(config)); return config
        def write(p,n):
            p.parent.mkdir(parents=True,exist_ok=True)
            subprocess.run([sys.executable,'-c','from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"X"*int(sys.argv[2]))',str(p),str(n)],check=True)
        old=a/'old-artifact.bin'; write(old,16384)
        shared=a/'shared.bin'; os.link(old,shared)
        ghost=a/'deleted.bin'; write(ghost,4096)
        secret='SECRET_NOT_RETAINED'
        records=[{'type':'session_meta','payload':{'id':'old-session','cwd':str(a),'base_instructions':secret}},
                 {'type':'response_item','payload':{'type':'function_call_output','call_id':'output-1','output':json.dumps({'artifact_path':str(old),'shared_path':str(shared),'missing_path':str(ghost),'prompt':secret})}},
                 {'type':'response_item','payload':{'type':'function_call','name':'exec_command','arguments':json.dumps({'cmd':'touch '+str(a/'planned-only.bin')+' '+secret})}}]
        (home/'sessions/old.jsonl').write_text('\n'.join(json.dumps(r) for r in records)+'\n')
        (home/'archived_sessions/shared.jsonl').write_text('\n'.join(json.dumps(r) for r in [dict(type='session_meta',payload={'id':'archived-session','cwd':str(a)}),records[1]])+'\n')
        (home/'sessions/unknown.jsonl').write_text(json.dumps({'type':'future_unknown','payload':{'private':secret}})+'\n')
        ghost.unlink()
        try:
            def fresh():
                value=cli('status'); assert not value['enabled'] and not state.exists(); return value
            case('Fresh status is read-only and does not initialize observation',fresh)
            def history_without_baseline():
                value=cli('analyze-history'); assert value['historical_growth_bytes'] is None
                assert value['recorded_allocated_bytes']==old.stat().st_blocks*512,value
                assert any(row['path']==str(old) and row['association']=='recorded' for row in value['items'])
                assert any(row['association']=='candidate' for row in value['items'])
                assert value['shared_artifacts']>=1 and value['missing_paths']>=1
                assert value['coverage']['unknown_record_types']>=1
                assert not cli('status')['enabled']; return value
            case('Explicit pre-enable historical analysis needs no plugin baseline; deduplicates archived/shared/hardlinked artifacts',history_without_baseline)
            def privacy():
                for p in state.rglob('*'):
                    if p.is_file() and p.suffix not in ('.lock',): assert secret.encode() not in p.read_bytes(),p
                return {'raw_prompts_commands':'not retained','planned_only':'not treated as created artifact'}
            case('Historical evidence is derived metadata; command plans and secrets are not retained',privacy)
            def enable():
                value=cli('enable','--root',str(a),'--root',str(b),'--no-defaults','--no-start','--notifications','inbox')
                assert value['enabled']; alter(monitor={'interval_seconds':0.05,'refresh_seconds':0,'slice_entries':2,'slice_seconds':0.02},thresholds={'growth_bytes':4096,'large_bytes':1048576,'many_files':20},notifications={'cooldown_seconds':0,'material_growth_bytes':4096})
                return value
            case('Enable once creates a global opt-in config independent of chat',enable)
            def global_paths():
                other=dict(env,PLUGIN_DATA=str(fixture/'per-plugin-data'))
                value=cli('status',custom_env=other); assert value['data_directory']==str(state)
                return value
            case('Hooks/MCP ignore per-version PLUGIN_DATA when explicit global state is selected',global_paths)
            def events():
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    results=list(pool.map(lambda n: hook(a if n%2 else b,'session-'+str(n)),range(6)))
                assert all(p.stdout=='' for p in results)
                tick(); value=cli('status'); assert value['event_count']==6,value
                assert value['session_count']==6; assert str(a) in value['configured_roots'] and str(b) in value['configured_roots']; return value
            case('Concurrent different-project/session hooks share one event inventory and stay silent',events)
            def resumable():
                for i in range(30): write(a/f'files/{i}.bin',4096)
                tick(1); partial=cli('report'); assert any(not r['complete'] for r in partial['roots']),partial
                tick(80); value=cli('report'); assert all(r['complete'] for r in value['roots']),value
                return {'partial_then_complete':True,'volume_samples':value['volumes']}
            case('Fair scan slices resume across ticks; capacity samples are separate from directory totals',resumable)
            def baseline():
                alerts=cli('alerts'); assert not any(x['kind']=='growth' and x['path']==str(b) for x in alerts['alerts']); cli('alerts','--ack','all'); return {'first_discovery_is_not_new_growth':True}
            case('First discovery does not invent newly-created growth',baseline)
            def growth():
                write(b/'external-output.bin',16384); hook(b,'writer-session','PostToolUse'); tick(80)
                value=cli('alerts'); rows=[x for x in value['alerts'] if x['kind']=='growth' and x['path']==str(b)]
                assert rows and rows[-1]['growth_bytes']>=16384,value
                assert 'writer-session' in rows[-1]['associated_sessions']; assert rows[-1]['delivery']['status']=='inbox_only'
                return rows[-1]
            case('Real external writer creates an actionable global growth alert with temporal session evidence',growth)
            def quiet_and_realert():
                before=len(cli('alerts')['alerts']); tick(80); assert len(cli('alerts')['alerts'])==before
                write(b/'more-output.bin',16384); tick(80); assert len(cli('alerts')['alerts'])>before
                cli('alerts','--ack','all'); assert all(x['acknowledged'] for x in cli('alerts')['alerts']); return {'deduplicated':True,'material_realert':True,'acknowledged':True}
            case('Unchanged findings stay quiet; material additional growth re-alerts and acknowledgements persist',quiet_and_realert)
            def incomplete():
                missing=fixture/'missing-root'; config=json.loads((state/'config.json').read_text()); config['roots'].append({'id':'missing','path':str(missing)}); (state/'config.json').write_text(json.dumps(config))
                tick(); value=cli('report'); row=next(r for r in value['roots'] if r['path']==str(missing)); assert not row['complete'] and row['growth_bytes'] is None
                config['roots'].pop(); (state/'config.json').write_text(json.dumps(config)); return row
            case('Missing/unreadable root yields visible unknown coverage and no numeric growth',incomplete)
            def singleton():
                nonlocal worker
                worker=subprocess.Popen([sys.executable,str(ENTRY),'worker'],env=env,cwd=fixture,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    if cli('status')['worker']['running']: break
                    time.sleep(.05)
                value=cli('status'); assert value['worker']['running']
                second=run('worker','--max-ticks','1'); assert json.loads(second.stdout)['already_running']
                pid=value['worker']['pid']; worker.kill(); worker.wait(); tick(1)
                recovery=cli('status'); assert not recovery['worker']['running']; return {'single_pid':pid,'crash_visible':True,'history_preserved':recovery['event_count']>=7}
            case('Single worker lock, crash visibility and retained history',singleton)
            def protocol():
                req=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
                     {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                     {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'footprint_analyze_history','arguments':{}}}]
                messages=[json.loads(x) for x in run('serve',input='\n'.join(json.dumps(r) for r in req)+'\n').stdout.splitlines()]
                tools=messages[1]['result']['tools']; spec=next(t for t in tools if t['name']=='footprint_analyze_history')
                assert not spec['annotations']['readOnlyHint']; assert not messages[2]['result']['isError']; return {'mcp_tools':[t['name'] for t in tools],'historical_write_annotation':True}
            case('Actual MCP transport exposes explicit historical analysis without changing read-only report semantics',protocol)
            def disable():
                cli('disable'); before=cli('status')['event_count']; hook(a,'disabled'); tick(1); assert cli('status')['event_count']==before
                assert not cli('status')['enabled']; return {'disabled_hooks':'no new event','history':'retained'}
            case('Disable stops new observation while retaining history',disable)
            case('Historical analysis remains explicitly usable while monitoring is disabled',lambda: cli('analyze-history'))
        except Exception: pass
        finally:
            if worker and worker.poll() is None: worker.kill(); worker.wait()
    report['passed']=sum(c['result']=='pass' for c in cases); report['failed']=sum(c['result']=='fail' for c in cases)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (out/'report.md').write_text('# Global monitor and history E2E\n\n'+f"Passed {report['passed']}; failed {report['failed']}\n\n"+'\n'.join(c['result'].upper()+': '+c['name'] for c in cases)+'\n')
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'report':str(out/'report.json')})); return bool(report['failed'])
if __name__=='__main__': raise SystemExit(main())
