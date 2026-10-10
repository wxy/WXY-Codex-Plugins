#!/usr/bin/env python3
"""CLI/MCP black-box regression cases for PR #2's scope/coverage/notice findings."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback

ENTRY=Path(os.environ.get('CODEX_FOOTPRINT_TEST_ENTRY',str(Path(__file__).resolve().parents[1]/'scripts/codex_footprint.py'))).resolve()
PRIMARY='/System/Volumes/Data' if sys.platform=='darwin' else '/'
OUTSIDE='/Volumes/footprint-review-unselected'
SELECTED='/Volumes/footprint-review-selected'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    report={'command':[sys.executable,str(Path(__file__).resolve()),'--output',str(output)],'environment':{'python':sys.version,'platform':sys.platform},'preconditions':'Python/SQLite and CLI subprocesses. No network, model, personal scans or OS notifications. Linux-specific case bootstraps the real CLI with sys.platform=linux on this host; it is not native Linux filesystem acceptance.','inputs':'Per-case temporary disabled-autostart config/state and workspace; seeded inventory/capacity/alerts/daily metadata; MCP newline JSON; real hook subprocesses.','cases':[]}
    def case(name,fn):
        with tempfile.TemporaryDirectory(prefix='footprint-review-e2e-') as directory:
            tmp=Path(directory).resolve();work=tmp/'workspace';work.mkdir();state=tmp/'state'
            env=dict(os.environ,CODEX_HOME=str(tmp/'profile'),CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),PYTHONDONTWRITEBYTECODE='1')
            def run(*argv,input=None,entry=ENTRY):
                p=subprocess.run([sys.executable,str(entry),*argv],env=env,input=input,text=True,capture_output=True,timeout=20)
                assert p.returncode==0 and not p.stderr,(argv,p.stderr,p.stdout)
                return json.loads(p.stdout) if p.stdout.strip() else None
            run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox')
            run('daily-report')  # Initialize metadata tables without traversing artifacts.
            def config(**values):
                p=state/'config.json';r=json.loads(p.read_text())
                for k,v in values.items():
                    if isinstance(v,dict):r[k].update(v)
                    else:r[k]=v
                p.write_text(json.dumps(r))
            def seed():
                now=time.time();root={'path':str(work),'allocated_bytes':8192,'complete':True,'finished':True,'growth_bytes':None,'top_files':[],'storage_volume':PRIMARY,'measured_at':now}
                outside=dict(root,path=OUTSIDE+'/project',allocated_bytes=10**12,storage_volume=OUTSIDE)
                with sqlite3.connect(state/'global.sqlite3') as db:
                    for row in (root,outside):db.execute('INSERT OR REPLACE INTO inventory VALUES(?,?)',(row['path'],json.dumps(row)))
                    for path,dev in ((PRIMARY,Path(PRIMARY).stat().st_dev),(OUTSIDE,99123)):
                        row={'path':path,'device':dev,'available_bytes':50000000000,'total_bytes':100000000000,'sampled_at':now}
                        db.execute('INSERT OR REPLACE INTO volumes VALUES(?,?)',(path,json.dumps(row)))
                        db.execute('INSERT OR REPLACE INTO volume_minutes VALUES(?,?,?,?)',(dev,int(now//60),now,json.dumps(row)))
                return root,outside
            def alert(path):return {'path':path,'kind':'growth','growth_bytes':999999,'latest_at':time.time()}
            def insert_alerts(rows):
                with sqlite3.connect(state/'global.sqlite3') as db:
                    for row in rows:db.execute('INSERT INTO alerts(fingerprint,ts,payload) VALUES(?,?,?)',('fixture',time.time(),json.dumps(row)))
            def hook():return run('hook',input=json.dumps({'hook_event_name':'PreToolUse','session_id':'review-fixture','cwd':str(work),'tool_name':'Bash'}))
            try:report['cases'].append({'name':name,'result':'pass','evidence':fn(tmp,work,state,env,run,config,seed,alert,insert_alerts,hook)})
            except Exception:report['cases'].append({'name':name,'result':'fail','error':traceback.format_exc()})
        assert not tmp.exists()
    def linux(tmp,work,state,env,run,config,seed,alert,insert_alerts,hook):
        wrapper=tmp/'linux-cli.py';wrapper.write_text('import sys,runpy\nsys.platform="linux"\nrunpy.run_path('+repr(str(ENTRY))+',run_name="__main__")\n')
        config(roots=[],monitor={'development_volume':SELECTED});root,outside=seed()
        with sqlite3.connect(state/'global.sqlite3') as db:
            db.execute('DELETE FROM volumes WHERE path=?',(PRIMARY,))
            row={'path':'/','device':Path('/').stat().st_dev,'available_bytes':50,'total_bytes':100,'sampled_at':time.time()-10}
            db.execute('INSERT OR REPLACE INTO volumes VALUES(?,?)',('/',json.dumps(row)))
            db.execute('INSERT OR REPLACE INTO volumes VALUES(?,?)',(SELECTED,json.dumps(dict(row,path=SELECTED,device=99124,sampled_at=time.time()))))
        insert_alerts([alert(OUTSIDE+'/missing.bin')])
        status=run('status',entry=wrapper);assert [v['path'] for v in status['volumes']]==['/',SELECTED],status['volumes']
        assert OUTSIDE+'/project' not in [r['path'] for r in status['roots']]
        assert not run('alerts',entry=wrapper)['alerts']
        value=run('dashboard',entry=wrapper)
        assert all(p['path']=='/' for p in value['capacity_charts'][0]['history']),value['capacity_charts'][0]['history']
        return {'linux_cli_branch_simulation':True,'missing_external_alerts_and_capacity_excluded':True,'offline_selected_mount_retained':True}
    case('missing_external_paths_do_not_become_system_data_linux_branch',linux)
    def responses(tmp,work,state,env,run,config,seed,alert,insert_alerts,hook):
        seed()
        for command in ('report','explain','cleanup-plan'):
            value=run(command);rows=value.get('roots',value.get('plans'));assert [r['path'] for r in rows]==[str(work)],(command,rows)
            if 'volumes' in value:assert [v['path'] for v in value['volumes']]==[PRIMARY]
        assert not run('explain','--path',OUTSIDE+'/project')['roots']
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}}]
        for i,name in enumerate(('footprint_report','footprint_explain','footprint_cleanup_plan'),2):messages.append({'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':name,'arguments':{}}})
        p=subprocess.run([sys.executable,str(ENTRY),'serve'],env=env,input=''.join(json.dumps(m)+'\n' for m in messages),text=True,capture_output=True,timeout=20)
        assert p.returncode==0 and not p.stderr,p.stderr
        for reply in [json.loads(s) for s in p.stdout.splitlines()][1:]:
            value=reply['result']['structuredContent'];assert [r['path'] for r in value.get('roots',value.get('plans'))]==[str(work)],value
        with sqlite3.connect(state/'global.sqlite3') as db:assert db.execute('SELECT count(*) FROM inventory').fetchone()[0]==2
        return {'cli_and_three_mcp_responses_consistent':True,'retained_outside_inventory_preserved':True}
    case('report_explain_cleanup_cli_and_mcp_apply_same_scope',responses)
    def coverage(tmp,work,state,env,run,config,seed,alert,insert_alerts,hook):
        root,outside=seed();day=dt.datetime.now().date()-dt.timedelta(days=1);start=dt.datetime.combine(day,dt.time()).timestamp();end=dt.datetime.combine(day+dt.timedelta(days=1),dt.time()).timestamp()
        root=dict(root,window_complete=True,baseline_at=start,latest_at=end-30)
        base={'day':day.isoformat(),'roots':[root,dict(outside,window_complete=False)],'volumes':[],'alerts':[],'window_start_at':start,'window_end_at':end,'coverage':{'full_day':False,'roots_without_complete_endpoints':[OUTSIDE+'/pending']}}
        def inspect(value):
            with sqlite3.connect(state/'global.sqlite3') as db:db.execute('INSERT OR REPLACE INTO daily_reports VALUES(?,?)',(day.isoformat(),json.dumps(value)))
            result=next(r for r in run('dashboard')['daily_reports'] if r['day']==day.isoformat())
            with sqlite3.connect(state/'global.sqlite3') as db:assert json.loads(db.execute('SELECT payload FROM daily_reports WHERE day=?',(day.isoformat(),)).fetchone()[0])==value
            return result['coverage']['full_day']
        assert inspect(base) is True,'filtered complete closed-day roots remain incorrectly incomplete'
        for value in (dict(base,roots=[dict(root,window_complete=False)]),dict(base,coverage={'full_day':True,'roots_without_complete_endpoints':[str(work)]}),dict(base,window_end_at=end-3600),dict(base,roots=[]),dict(base,window_end_at=None)):
            assert inspect(value) is False,value
        return {'closed_day_recomputed_after_projection':True,'selected_gaps_partial_day_empty_and_unknown_windows_stay_incomplete':True,'saved_metadata_unchanged':True}
    case('daily_coverage_recomputed_after_scope_projection',coverage)
    def notices(tmp,work,state,env,run,config,seed,alert,insert_alerts,hook):
        seed();insert_alerts([alert(SELECTED+'/old')]);assert hook() is None
        config(monitor={'development_volume':SELECTED})
        rows=run('alerts')['alerts'];assert len(rows)==1 and rows[0]['codex_delivery']['status']=='pending_active_chat',rows
        notice=hook();assert notice and 'systemMessage' in notice
        assert run('alerts')['alerts'][0]['codex_delivery']['status']=='emitted_to_hook_visibility_unverified'
        assert hook() is None
        insert_alerts([alert(OUTSIDE+'/skipped'),alert(str(work))]);assert hook()
        config(monitor={'development_volume':OUTSIDE})
        rows=run('alerts')['alerts'];skipped=next(r for r in rows if r['path']==OUTSIDE+'/skipped');assert skipped['codex_delivery']['status']=='pending_active_chat',rows
        assert hook() and hook() is None
        return {'scope_change_revisits_skipped_alerts':True,'mixed_batches_preserve_actual_emission_ids':True,'no_duplicate_actual_emissions':True}
    case('skipped_notice_cursor_is_not_emission_proof',notices)
    def legacy(tmp,work,state,env,run,config,seed,alert,insert_alerts,hook):
        seed();insert_alerts([alert(str(work))]);(state/'codex-notice.json').write_text(json.dumps({'last_id':1,'ids':[],'emitted_at':time.time()}))
        assert run('alerts')['alerts'][0]['codex_delivery']['status']=='pending_active_chat'
        assert hook() and hook() is None
        insert_alerts([alert(OUTSIDE+'/excluded-'+str(i)) for i in range(110)]+[alert(str(work))])
        assert hook() is None;assert hook(),'eligible alert after first excluded 100 must remain reachable'
        assert hook() is None
        return {'legacy_empty_ids_not_claimed_delivered':True,'bounded_batches_make_progress_past_100_excluded':True}
    case('legacy_notice_receipt_and_bounded_batch_progress',legacy)
    def counts(tmp,work,state,env,run,config,seed,alert,insert_alerts,hook):
        seed();insert_alerts([alert(str(work)) for _ in range(130)]+[alert(OUTSIDE+'/excluded') for _ in range(20)])
        with sqlite3.connect(state/'global.sqlite3') as db:db.execute('UPDATE alerts SET acknowledged=1 WHERE id<=10')
        value=run('dashboard');series=next(s for s in value['capacity_charts'] if s['volume']['path']==PRIMARY)
        assert len(value['alerts'])==100 and series['pending_alerts']==120,(len(value['alerts']),series['pending_alerts'])
        return {'recent_details_capped_at_100':True,'all_120_pending_selected_findings_counted':True,'acknowledged_and_excluded_not_counted':True}
    case('per_disk_pending_count_exceeds_detail_limit',counts)
    report['temporary_process_files_removed']=True;report['result']='pass' if all(c['result']=='pass' for c in report['cases']) else 'fail'
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'result':report['result'],'cases':[{'name':c['name'],'result':c['result']} for c in report['cases']],'report':str(output/'report.json')}));return report['result']!='pass'
if __name__=='__main__':raise SystemExit(main())
