#!/usr/bin/env python3
"""Test-first CLI acceptance for independent development-cache baselines."""
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
import urllib.request

ENTRY=Path(__file__).resolve().parents[1]/'scripts/codex_footprint.py'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    report={'command':[sys.executable,str(Path(__file__).resolve()),'--output',args.output],
            'environment':{'platform':sys.platform,'python':sys.version,'euid':os.geteuid()},
            'inputs':'Disposable HOME/Library/Caches, actual CLI walks and denied Unix directories; seeded historical metadata only for report-day isolation.',
            'acceptance_limit':'No personal directories, service, TCC settings or notification permissions changed. Unix denial fixture does not simulate macOS TCC approval.',
            'failure_model':['one denied sibling prevents every baseline','parent/event roots collapse split caches','nested denial becomes exact growth','queries rediscover filesystem','historical reports inherit current gaps','symlinks or discovery limits hide gaps','upgrade mixes broad and split accounting'], 'cases':[]}
    def case(name,fn):
        with tempfile.TemporaryDirectory(prefix='footprint-cache-e2e-') as directory:
            tmp=Path(directory).resolve();home=tmp/'home';cache=home/'Library/Caches';cache.mkdir(parents=True)
            state=tmp/'state';codex=home/'.codex';codex.mkdir()
            env=dict(os.environ,HOME=str(home),CODEX_HOME=str(codex),CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),PYTHONDONTWRITEBYTECODE='1',CODEX_FOOTPRINT_PANEL_PORT='0')
            def cli(*argv,input=None):
                p=subprocess.run([sys.executable,str(ENTRY),*argv],cwd=tmp,env=env,text=True,input=input,capture_output=True,timeout=30)
                assert p.returncode==0,p.stderr[:1500]
                return json.loads(p.stdout) if p.stdout.strip() else None
            def cfg(**sections):
                path=state/'config.json';v=json.loads(path.read_text())
                for k,x in sections.items():
                    if isinstance(x,dict):v.setdefault(k,{}).update(x)
                    else:v[k]=x
                path.write_text(json.dumps(v))
            try:
                cli('enable','--root',str(cache),'--no-defaults','--no-start','--notifications','inbox')
                cfg(monitor={'event_backend':'polling','refresh_seconds':0},exclude_names=['Cellar'])
                evidence=fn(tmp,cache,state,cli,cfg)
                report['cases'].append({'name':name,'result':'pass','evidence':evidence})
            except Exception:report['cases'].append({'name':name,'result':'fail','error':traceback.format_exc()})
            finally:
                for path in tmp.rglob('*'):
                    if path.is_dir() and not path.is_symlink():path.chmod(0o700)
        assert not tmp.exists()
    def split(tmp,cache,state,cli,cfg):
        if os.geteuid()==0:raise RuntimeError('Run as ordinary macOS user for the denial acceptance')
        for n in ('pip','com.apple.dt.Xcode','CloudKit','OtherApp'):(cache/n).mkdir()
        (cache/'pip/base').write_bytes(b'x'*8192);(cache/'CloudKit').chmod(0)
        s=cli('tick','--rounds','40');rows={r['path']:r for r in s['roots']}
        assert str(cache) not in rows and rows[str(cache/'pip')]['complete'] and rows[str(cache/'com.apple.dt.Xcode')]['complete'],rows
        assert str(cache/'OtherApp') not in rows
        c=s['coverage']['development_caches'];assert c['gaps'][0]['path']==str(cache/'CloudKit') and c['gaps'][0]['allocated_bytes'] is None,c
        assert c['outside_development_scope_count']==1
        (cache/'pip/growth').write_bytes(b'z'*65536)
        s=cli('tick','--rounds','40');r=next(r for r in s['roots'] if r['path']==str(cache/'pip'))
        assert r['growth_bytes']>=65536 and r['baseline_at'],r
        daily=cli('daily-report');assert not daily['coverage']['full_day'] and str(cache/'CloudKit') in daily['coverage']['partial_roots']
        assert daily['coverage']['development_caches']['gaps']
        return {'independent_growth_bytes':r['growth_bytes'],'protected_gap_retained':True,'unrelated_cache_out_of_scope':True}
    case('readable_siblings_build_independent_baselines',split)
    def ancestor(tmp,cache,state,cli,cfg):
        (cache/'pip').mkdir();(cache/'pip/cache.bin').write_bytes(b'x'*8192)
        library=cache.parent;(library/'other.bin').write_bytes(b'x'*4096)
        cfg(roots=[{'path':str(library)}])
        cli('hook',input=json.dumps({'hook_event_name':'UserPromptSubmit','cwd':str(cache),'session_id':'cache-fixture'}))
        s=cli('tick','--rounds','40');rows={r['path']:r for r in s['roots']}
        assert set(rows)=={str(library),str(cache/'pip')},rows
        assert rows[str(library)]['file_count']==1 and rows[str(cache/'pip')]['file_count']==1,rows
        assert rows[str(library)]['excluded_paths']==[str(cache)]
        return {'ancestor_excludes_cache_subtree':True,'broad_hook_does_not_collapse_children':True}
    case('explicit_ancestor_and_parent_hook_do_not_double_count',ancestor)
    def explicit_cache(tmp,cache,state,cli,cfg):
        custom=cache/'OtherApp';custom.mkdir();(cache/'pip').mkdir()
        library=cache.parent;(library/'outside.bin').write_bytes(b'x'*4096)
        combinations=([custom],[library,custom],[custom,library],[cache,custom],[custom,cache])
        for i,paths in enumerate(combinations):
            cfg(roots=[{'path':str(p)} for p in paths])
            cli('tick','--rounds','40')
            before=next(r for r in cli('status')['roots'] if r['path']==str(custom))
            (custom/('growth-%s'%i)).write_bytes(b'z'*65536)
            cli('hook',input=json.dumps({'hook_event_name':'UserPromptSubmit','cwd':str(library),'session_id':'explicit-cache-fixture'}))
            s=cli('tick','--rounds','40');rows={r['path']:r for r in s['roots']}
            assert str(custom) in rows and rows[str(custom)]['complete'],rows
            assert rows[str(custom)]['growth_bytes']>=65536,rows[str(custom)]
            assert rows[str(custom)]['measurement_scope']==before['measurement_scope']
            assert rows[str(library)]['file_count']==1 and rows[str(library)]['excluded_paths']==[str(cache)]
        return {'configured_root_combinations':len(combinations),'custom_cache_remains_comparable':True,'no_ancestor_double_count':True}
    case('explicit_nondefault_cache_survives_broad_hooks_and_config_order',explicit_cache)
    def nested(tmp,cache,state,cli,cfg):
        (cache/'pip/denied').mkdir(parents=True);(cache/'python3').mkdir();(cache/'pip/denied').chmod(0)
        s=cli('tick','--rounds','40');rows={r['path']:r for r in s['roots']}
        assert not rows[str(cache/'pip')]['complete'] and rows[str(cache/'pip')]['growth_bytes'] is None
        assert rows[str(cache/'python3')]['complete']
        with sqlite3.connect(state/'global.sqlite3') as db:assert not db.execute('SELECT 1 FROM baselines WHERE path=?',(str(cache/'pip'),)).fetchone()
        return {'nested_failure_isolated':True}
    case('nested_denial_stays_partial_without_poisoning_sibling',nested)
    def readonly(tmp,cache,state,cli,cfg):
        (cache/'pip').mkdir();before=cli('tick','--rounds','40')['coverage']['development_caches']
        cache.rename(cache.with_name('moved-caches'))
        for cmd in ('status','report','dashboard','daily-report'):
            after=cli(cmd)['coverage']['development_caches'];assert after['checked_at']==before['checked_at'],(cmd,after)
        cli('disable');assert cli('status')['coverage']['development_caches']['checked_at']==before['checked_at']
        return {'all_queries_use_retained_metadata':True,'disabled_monitor_not_resumed':True}
    case('queries_never_rediscover_caches',readonly)
    def history(tmp,cache,state,cli,cfg):
        (cache/'pip').mkdir();cli('tick','--rounds','40')
        yesterday=(dt.date.today()-dt.timedelta(days=1)).isoformat()
        assert 'development_caches' not in cli('daily-report','--day',yesterday)['coverage']
        with sqlite3.connect(state/'global.sqlite3') as db:
            raw=json.loads(db.execute('SELECT payload FROM cache_coverage ORDER BY day DESC LIMIT 1').fetchone()[0])
            raw['checked_at']=dt.datetime.combine(dt.date.fromisoformat(yesterday),dt.time(12)).timestamp()
            raw['gaps']=[{'path':str(cache/'CloudKit'),'reason':'unreadable','allocated_bytes':None}]
            db.execute('INSERT INTO cache_coverage VALUES(?,?)',(yesterday,json.dumps(raw)))
        cli('daily-report');old=cli('daily-report','--day',yesterday)
        assert old['coverage']['development_caches']['gaps'] and not cli('status')['coverage']['development_caches']['gaps']
        return {'daily_gap_snapshot_is_owned_by_its_day':True}
    case('historical_reports_do_not_inherit_current_topology',history)
    def bounded(tmp,cache,state,cli,cfg):
        target=tmp/'target';target.mkdir();(cache/'pip').symlink_to(target,target_is_directory=True)
        for i in range(270):(cache/('other-%03d'%i)).mkdir()
        c=cli('tick','--rounds','40')['coverage']['development_caches']
        assert not c['discovery_complete'] and any(g['reason']=='discovery_limit' for g in c['gaps']),c
        assert len(c['roots'])<=256 and not any(r['path']==str(target) for r in cli('status')['roots'])
        return {'discovery_limit_visible':True,'symlink_not_followed':True}
    case('bounded_discovery_and_no_symlink_following',bounded)
    def upgrade(tmp,cache,state,cli,cfg):
        (cache/'pip').mkdir();cli('tick','--rounds','40')
        with sqlite3.connect(state/'global.sqlite3') as db:
            row=json.loads(db.execute('SELECT payload FROM inventory LIMIT 1').fetchone()[0]);row.update(path=str(cache),complete=False,finished=True,allocated_bytes=999999999,growth_bytes=None,error_count=9)
            db.execute('INSERT INTO inventory VALUES(?,?)',(str(cache),json.dumps(row)))
            db.execute('INSERT INTO observations(path,ts,payload) VALUES(?,?,?)',(str(cache),time.time(),json.dumps(row)))
        cli('tick','--rounds','40')
        assert str(cache) not in [r['path'] for r in cli('daily-report')['roots']]
        assert str(cache) not in [r['path'] for r in cli('status')['roots']]
        return {'legacy_parent_retired_from_current_totals':True,'historical_observation_preserved':True}
    case('upgrade_retires_broad_parent_without_deleting_history',upgrade)
    def recovery(tmp,cache,state,cli,cfg):
        (cache/'pip').mkdir();(cache/'CloudKit').mkdir();(cache/'CloudKit').chmod(0)
        cfg(roots=[],discovery=True)
        assert cli('tick','--rounds','40')['coverage']['development_caches']['gaps']
        (cache/'CloudKit').chmod(0o700)
        (cache/'python3').mkdir();(cache/'pip').rmdir()
        s=cli('tick','--rounds','40')
        assert not s['coverage']['development_caches']['gaps']
        assert str(cache/'pip') not in [r['path'] for r in s['roots']]
        assert next(r for r in s['roots'] if r['path']==str(cache/'python3'))['complete']
        assert str(cache/'CloudKit') in cli('daily-report')['coverage']['partial_roots']
        return {'default_discovery_split':True,'removed_root_retired':True,'resolved_gap_does_not_erase_day_evidence':True}
    case('default_discovery_and_permission_recovery',recovery)
    def missing(tmp,cache,state,cli,cfg):
        (cache/'pip').mkdir();cfg(roots=[],discovery=True)
        cli('tick','--rounds','40');cache.rename(cache.with_name('moved-caches'))
        c=cli('tick','--rounds','40')['coverage']['development_caches']
        assert not c['discovery_complete'] and c['gaps'][0]['path']==str(cache) and not c['roots'],c
        return {'missing_parent_visible_after_background_reconcile':True}
    case('missing_cache_parent_is_a_gap_not_stale_success',missing)
    def excluded(tmp,cache,state,cli,cfg):
        (cache/'pip').mkdir();(cache/'CloudKit').mkdir();(cache/'CloudKit').chmod(0)
        cfg(exclude_names=['CloudKit'])
        c=cli('tick','--rounds','40')['coverage']['development_caches']
        assert not c['gaps'] and c['excluded_directory_count']==1,c
        cfg(exclude_names=['Caches'])
        before=cli('status')['coverage']['development_caches']['checked_at']
        cli('tick','--rounds','40');assert cli('status')['coverage']['development_caches']['checked_at']==before
        return {'user_exclusions_are_respected_before_access_probe':True}
    case('excluded_cache_directories_are_not_probed',excluded)
    def browser(tmp,cache,state,cli,cfg):
        (cache/'pip').mkdir();(cache/'CloudKit').mkdir();(cache/'CloudKit').chmod(0)
        cli('tick','--rounds','40');cli('daily-report')
        env=dict(os.environ,HOME=str(cache.parents[1]),CODEX_HOME=str(cache.parents[1]/'.codex'),CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),PYTHONDONTWRITEBYTECODE='1')
        proc=subprocess.Popen([sys.executable,str(ENTRY),'panel','--port','0'],cwd=tmp,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            url=None
            for _ in range(100):
                info=state/'panel.json'
                if info.exists():url=json.loads(info.read_text())['url'];break
                time.sleep(.05)
            assert url,'fixture panel did not start'
            with urllib.request.urlopen(url+'api/dashboard') as response:assert json.load(response)['coverage']['development_caches']['gaps']
            out=tmp/'browser-report.json'
            p=subprocess.run(['node',str(ENTRY.parents[1]/'tests/e2e_cache_dashboard.mjs'),url,str(out)],text=True,capture_output=True,timeout=45)
            assert p.returncode==0,p.stdout+p.stderr
            return json.loads(out.read_text())
        finally:
            proc.terminate();proc.wait(timeout=5)
    case('narrow_panel_exposes_cache_gaps_in_three_views',browser)
    report.update(passed=sum(c['result']=='pass' for c in report['cases']),failed=sum(c['result']=='fail' for c in report['cases']))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'report':str(out)}));return bool(report['failed'])

if __name__=='__main__':raise SystemExit(main())
