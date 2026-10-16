#!/usr/bin/env python3
"""CLI/worker acceptance for production budgets, durable baselines and coverage."""
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

ENTRY = Path(__file__).resolve().parents[1] / 'scripts/codex_footprint.py'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--case')
    args = parser.parse_args()
    report = {'command': [sys.executable, str(Path(__file__).resolve()), '--output', args.output],
              'environment': {'python': sys.version, 'platform': sys.platform},
              'preconditions': 'Local Unix metadata, worker subprocesses and SQLite; no personal state or desktop notifications.',
              'inputs': 'Disposable 61-root file trees; external writes; legacy complete/partial/pruned monitor metadata; permission gaps.',
              'cases': []}
    if args.case:
        report['command'] += ['--case', args.case]

    def case(name, fn):
        if args.case and args.case != name:
            return
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='footprint-reliability-e2e-') as directory:
            tmp = Path(directory).resolve()
            root = tmp / 'project'
            root.mkdir()
            state = tmp / 'state'
            home = tmp / 'home'
            home.mkdir()
            env = dict(os.environ, CODEX_FOOTPRINT_DATA=str(state), CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),
                       CODEX_HOME=str(home), CODEX_FOOTPRINT_PANEL_PORT='0', PYTHONDONTWRITEBYTECODE='1')
            processes = []

            def cli(*argv):
                p = subprocess.run([sys.executable, str(ENTRY), *argv], env=env, cwd=tmp,
                                   capture_output=True, text=True, timeout=30)
                assert p.returncode == 0, p.stderr[:1500]
                return json.loads(p.stdout)

            def configure(**sections):
                path = state/'config.json'
                value = json.loads(path.read_text())
                for key, item in sections.items():
                    if isinstance(item, dict):
                        value.setdefault(key, {}).update(item)
                    else:
                        value[key] = item
                path.write_text(json.dumps(value))

            def start():
                p = subprocess.Popen([sys.executable, str(ENTRY), 'worker'], env=env, cwd=tmp,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(p)
                return p

            def wait(fn, seconds=20):
                until = time.monotonic()+seconds
                while time.monotonic() < until:
                    result = fn()
                    if result:
                        return result
                    time.sleep(.15)
                raise AssertionError('condition not reached within %ss' % seconds)

            def row():
                return next((r for r in cli('status')['roots'] if r['path'] == str(root)), {})

            cli('enable', '--root', str(root), '--no-defaults', '--no-start', '--notifications', 'inbox')
            blocked = root/'protected'
            try:
                evidence = fn(tmp, root, state, cli, configure, start, wait, row)
                report['cases'].append({'name': name, 'result': 'pass', 'seconds': time.monotonic()-started, 'evidence': evidence})
            except Exception:
                report['cases'].append({'name': name, 'result': 'fail', 'error': traceback.format_exc()})
            finally:
                if blocked.exists():
                    blocked.chmod(0o700)
                for p in processes:
                    if p.poll() is None:
                        p.terminate()
                    try:
                        p.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        p.wait(timeout=5)
        assert not tmp.exists(), 'temporary process files survived'

    def production(tmp, root, state, cli, cfg, start, wait, row):
        roots = [root]
        for i in range(60):
            p = tmp/('cold-%02d' % i)
            p.mkdir()
            (p/'base').write_bytes(b'x'*4096)
            roots.append(p)
        for i in range(5000):
            (root/('base-%05d' % i)).write_bytes(b'x')
        cfg(roots=[{'path': str(p)} for p in roots], thresholds={'growth_bytes': 65536})
        began = time.monotonic()
        start()
        status = wait(lambda: (s if len([r for r in s['roots'] if r.get('complete')]) == 61 else None)
                      if (s := cli('status')) else None, 20)
        elapsed = time.monotonic()-began
        assert status['worker']['running']
        subprocess.run([sys.executable, '-c', 'from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"z"*131072)',
                        str(root/'growth')], check=True)
        wait(lambda: any(a.get('growth_bytes', 0) >= 131072 for a in cli('alerts')['alerts']), 20)
        assert cli('status')['history_analysis_count'] == 0
        return {'roots': 61, 'files_in_hot_root': 5000, 'baseline_seconds': elapsed,
                'production_slice_seconds': .02, 'production_interval_seconds': 2,
                'external_writer_growth_alert': True}
    case('production_budget_61_roots_and_external_growth', production)

    def late_hot(tmp, root, state, cli, cfg, start, wait, row):
        busy=[]
        for i in range(8):
            path=tmp/('a-busy-%d'%i)
            path.mkdir()
            for j in range(200):
                (path/str(j)).write_bytes(b'x')
            busy.append(path)
        (root/'base').write_bytes(b'x'*4096)
        cfg(roots=[{'path':str(p)} for p in busy+[root]],monitor={'slice_entries':1,'event_backend':'polling'})
        start()
        wait(lambda:cli('status')['worker'].get('progress',{}).get('active_cycles',0)>=4)
        began=time.monotonic()
        event={'hook_event_name':'UserPromptSubmit','cwd':str(root),'session_id':'active-session'}
        env=dict(os.environ,CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),CODEX_HOME=str(tmp/'home'),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([sys.executable,str(ENTRY),'hook'],input=json.dumps(event),text=True,capture_output=True,env=env,timeout=10)
        assert result.returncode==0,result.stderr
        value=wait(lambda:row().get('complete'),5)
        status=cli('status')
        assert status['event_count']==1
        assert status['worker']['progress']['pending_roots']>0,'busy trees completed before hot-root admission was tested'
        return {'hot_root_seconds':time.monotonic()-began,'other_roots_still_pending':True,'real_lifecycle_spool':True}
    case('late_active_project_is_not_blocked_by_large_roots',late_hot)

    def native_local(tmp, root, state, cli, cfg, start, wait, row):
        quiet=tmp/'quiet'
        quiet.mkdir()
        cfg(roots=[{'path':str(root)},{'path':str(quiet)}],monitor={'refresh_seconds':0,'reconcile_seconds':3600},thresholds={'growth_bytes':65536})
        start()
        wait(lambda:len(cli('status')['roots'])==2 and all(r['complete'] for r in cli('status')['roots']))
        def count():
            with sqlite3.connect(state/'global.sqlite3') as db:
                return db.execute('SELECT count(*) FROM observations WHERE path=?',(str(quiet),)).fetchone()[0]
        time.sleep(1.5)
        before=count()
        for i in range(160):
            folder=root/('branch-%d'%(i%8))
            folder.mkdir(exist_ok=True)
            (folder/('write-%d'%i)).write_bytes(b'x'*4096)
        wait(lambda:any(a.get('growth_bytes',0)>=65536 for a in cli('alerts')['alerts']))
        time.sleep(1.5)
        assert cli('status')['worker']['progress']['filesystem_events']['backend']=='fsevents'
        assert count()==before,'local native event invalidated an unrelated root'
        return {'native_stream':True,'coalesced_local_writes':160,'quiet_root_not_rescanned':True}
    case('native_local_burst_preserves_unrelated_root', native_local)

    def baseline(tmp, root, state, cli, cfg, start, wait, row):
        (root/'base').write_bytes(b'x'*4096)
        cli('tick', '--rounds', '10')
        before = row()
        partial = dict(before, complete=False, allocated_bytes=0, error_count=1,
                       errors=[{'kind': 'FileNotFoundError', 'path': str(root/'vanished')}])
        with sqlite3.connect(state/'global.sqlite3') as db:
            db.execute('DELETE FROM observations')
            db.execute('INSERT INTO observations(path,ts,payload) VALUES(?,?,?)', (str(root), time.time(), json.dumps(partial)))
        (root/'growth').write_bytes(b'y'*65536)
        cli('tick', '--rounds', '10')
        after = row()
        assert after['growth_bytes'] == 65536, after
        assert after['baseline_at'] == before['measured_at'], after
        return {'history_pruned': True, 'partial_intervening_row': True, 'growth_bytes': after['growth_bytes']}
    case('pruned_history_and_partial_preserve_complete_baseline', baseline)

    def rollover(tmp, root, state, cli, cfg, start, wait, row):
        (root/'base').write_bytes(b'x'*4096)
        cli('tick', '--rounds', '10')
        before = row()
        yesterday = dt.datetime.combine(dt.date.today(), dt.time()).timestamp()-3600
        before.update(measured_at=yesterday, started_at=yesterday-1)
        with sqlite3.connect(state/'global.sqlite3') as db:
            db.execute('DELETE FROM observations')
            db.execute('DELETE FROM daily_roots')
            db.execute('DROP TABLE IF EXISTS baselines')  # Emulate a pre-upgrade store.
            db.execute('INSERT INTO observations(path,ts,payload) VALUES(?,?,?)', (str(root), yesterday, json.dumps(before)))
            db.execute('INSERT OR REPLACE INTO inventory VALUES(?,?)', (str(root), json.dumps(before)))
        (root/'growth').write_bytes(b'y'*32768)
        cli('tick', '--rounds', '10')
        daily = cli('daily-report')
        value = next(r for r in daily['roots'] if r['path'] == str(root))
        assert value['growth_bytes'] is None, 'cross-day bytes presented as same-day growth'
        assert value['cross_day_growth_bytes'] == 32768, value
        assert value['cross_day_baseline_at'] == yesterday, value
        assert value['comparison_status'] == 'cross_day', value
        assert daily['coverage']['cross_day_comparable_roots'] == 1, daily['coverage']
        return {'same_day_growth_unknown': True, 'cross_day_growth_bytes': 32768, 'legacy_store_migrated': True}
    case('day_rollover_exposes_cross_day_comparison', rollover)

    def stale(tmp, root, state, cli, cfg, start, wait, row):
        cli('tick', '--rounds', '10')
        old = row()
        old['measured_at'] = time.time()-10000
        with sqlite3.connect(state/'global.sqlite3') as db:
            db.execute('UPDATE inventory SET payload=? WHERE path=?', (json.dumps(old), str(root)))
        value = row()
        assert value['stale'] is True, value
        assert str(root) in cli('status')['coverage']['stale_roots']
        return {'old_success_not_presented_as_fresh': True}
    case('stale_success_is_visible_in_status', stale)

    def archived_day(tmp, root, state, cli, cfg, start, wait, row):
        cli('tick','--rounds','10')
        value=row()
        day=(dt.date.today()-dt.timedelta(days=1)).isoformat()
        midnight=dt.datetime.combine(dt.date.fromisoformat(day),dt.time()).timestamp()
        first=dict(value,measured_at=midnight+30,started_at=midnight,allocated_bytes=0)
        last=dict(value,measured_at=midnight+86400-30,started_at=midnight+86400-60,allocated_bytes=4096)
        with sqlite3.connect(state/'global.sqlite3') as db:
            db.execute('INSERT OR REPLACE INTO daily_roots VALUES(?,?,?,?)',(day,str(root),json.dumps(first),json.dumps(last)))
        result=cli('daily-report','--day',day)
        assert result['coverage']['full_day'] is True,result['coverage']
        assert result['roots'][0]['stale'] is False,'closed historical coverage marked as currently overdue'
        return {'closed_day_coverage_preserved':True,'not_a_current_refresh_failure':True}
    case('closed_historical_day_is_not_overdue',archived_day)

    def permission(tmp, root, state, cli, cfg, start, wait, row):
        blocked = root/'protected'
        blocked.mkdir()
        (blocked/'private').write_bytes(b'x'*4096)
        blocked.chmod(0)
        cli('tick', '--rounds', '10')
        value = row()
        assert value['finished'] and not value['complete'] and value['growth_bytes'] is None, value
        assert value['coverage_status'] == 'partial', value
        assert value['error_count'] > 0
        return {'protected_subtree_remains_gap': True, 'no_invented_growth': True}
    case('permission_gap_remains_explicit', permission)

    def scope(tmp, root, state, cli, cfg, start, wait, row):
        (root/'old').write_bytes(b'x'*4096)
        cli('tick', '--rounds', '10')
        cfg(exclude_names=['old'])
        cli('tick', '--rounds', '10')
        assert row()['growth_bytes'] is None, row()
        daily = cli('daily-report')
        value = next(r for r in daily['roots'] if r['path'] == str(root))
        assert value['growth_bytes'] is None and value.get('cross_day_growth_bytes') is None, value
        return {'scope_change_not_compared': True}
    case('changed_scope_never_invents_growth', scope)

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(c['result'] == 'pass' for c in report['cases'])
    report.update(passed=passed,failed=len(report['cases'])-passed)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({'passed': passed, 'failed': len(report['cases'])-passed, 'report': str(path)}))
    return int(passed != len(report['cases']))


if __name__ == '__main__':
    raise SystemExit(main())
