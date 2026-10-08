#!/usr/bin/env python3
"""Black-box acceptance written before monitor/panel runtime implementation."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import resource
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'scripts/codex_footprint.py'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--case')
    args = ap.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {'command': [sys.executable, str(Path(__file__).resolve()), '--output', str(out)],
              'environment': {'python': sys.version, 'platform': sys.platform},
              'preconditions': 'Local Unix filesystem, subprocesses and loopback HTTP; no real notification or login service changes.',
              'inputs': 'Generated disposable project metadata, externally written blocks and local session fixtures; all process files removed at exit.',
              'cases': []}
    if args.case:
        report['command'] += ['--case', args.case]
    processes = []
    with tempfile.TemporaryDirectory(prefix='footprint-dashboard-e2e-') as tmp:
        tmp = Path(tmp).resolve()
        state = tmp / 'state'
        home = tmp / 'codex-home'
        home.mkdir()
        env = dict(os.environ, CODEX_FOOTPRINT_DATA=str(state), CODEX_FOOTPRINT_CONFIG=str(state / 'config.json'),
                   CODEX_HOME=str(home), CODEX_FOOTPRINT_PANEL_PORT='0', PYTHONDONTWRITEBYTECODE='1')
        def run(*cmd, check=True, input=None):
            p = subprocess.run([sys.executable, str(ENTRY), *cmd], env=env, cwd=tmp,
                               capture_output=True, text=True, input=input, timeout=40)
            if check and p.returncode:
                raise AssertionError({'args': cmd, 'exit': p.returncode, 'stderr': p.stderr[:1500]})
            return p
        def cli(*cmd):
            return json.loads(run(*cmd).stdout)
        def config(**sections):
            p = state / 'config.json'
            value = json.loads(p.read_text())
            for name, fields in sections.items():
                value.setdefault(name, {}).update(fields)
            p.write_text(json.dumps(value))
        def wait_for(fn, seconds=15):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                value = fn()
                if value:
                    return value
                time.sleep(.1)
            raise AssertionError('Condition not reached in %.1f seconds' % seconds)
        def case(name, fn):
            if args.case and args.case != name:
                return
            start = time.monotonic()
            try:
                evidence = fn()
                report['cases'].append({'name': name, 'result': 'pass', 'seconds': time.monotonic() - start, 'evidence': evidence})
            except Exception:
                report['cases'].append({'name': name, 'result': 'fail', 'seconds': time.monotonic() - start, 'error': traceback.format_exc()})

        projects = [tmp / ('project-%02d' % n) for n in range(8)]
        for p in projects:
            p.mkdir()
        for n in range(2500):
            (projects[0] / ('file-%04d' % n)).write_bytes(b'x')
        cli('enable', *[part for p in projects for part in ('--root', str(p))], '--no-defaults', '--no-start', '--notifications', 'inbox')
        try:
            def fair():
                # Test entry-budget reuse independently of the conservative production time slice.
                config(monitor={'slice_entries':1000,'slice_seconds':.2})
                value = cli('tick', '--rounds', '6')
                config(monitor={'slice_entries':5000,'slice_seconds':.02})
                row = next(r for r in value['roots'] if r['path'] == str(projects[0]))
                assert row['complete'], {'entries': row['entries_visited'], 'expected_files': 2500}
                assert row['file_count'] == 2500
                return {'roots': 8, 'generated_files': 2500, 'max_rounds': 6, 'entries_visited': row['entries_visited'], 'fixture_entry_budget':1000,'fixture_slice_seconds':.2}
            case('fair_budget', fair)

            def background():
                config(monitor={'interval_seconds': .05, 'refresh_seconds': .2},
                       thresholds={'growth_bytes': 65536}, notifications={'cooldown_seconds': 0, 'material_growth_bytes': 65536})
                proc = subprocess.Popen([sys.executable, str(ENTRY), 'worker'], env=env, cwd=tmp,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(proc)
                wait_for(lambda: cli('status')['worker']['running'])
                wait_for(lambda: next((r for r in cli('status')['roots'] if r['path'] == str(projects[1]) and r['complete']), None))
                started = time.monotonic()
                subprocess.run([sys.executable, '-c', 'from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"X"*262144)', str(projects[1] / 'external.bin')], check=True)
                alert = wait_for(lambda: next((a for a in cli('alerts')['alerts'] if a['path'] == str(projects[1]) and a['kind'] == 'growth'), None))
                assert alert['growth_bytes'] >= 262144
                assert cli('status')['history_analysis_count'] == 0
                proc.terminate(); proc.wait(timeout=5)
                return {'detection_seconds': time.monotonic() - started, 'growth_bytes': alert['growth_bytes'], 'automatic_history_analysis': False}
            case('background_growth', background)

            def daily():
                first = cli('daily-report')
                second = cli('daily-report')
                assert first['day'] == second['day']
                assert first['report_id'] == second['report_id']
                assert first['full_disk_scan_triggered'] is False
                assert first['history_analysis_triggered'] is False
                assert 'coverage' in first and 'roots' in first
                assert cli('status')['history_analysis_count'] == 0
                return {'report_id': first['report_id'], 'day': first['day'], 'idempotent': True, 'roots': len(first['roots'])}
            case('daily_summary', daily)

            def daily_retention():
                before = cli('daily-report')
                config(retention={'max_snapshots': 2})
                cli('tick', '--rounds', '20')
                after = cli('daily-report')
                assert len(after['roots']) >= len(before['roots'])
                assert after['report_id'] == before['report_id']
                assert after['coverage']['full_day'] is False
                return {'daily_roots_survive_observation_pruning': True, 'full_day_not_fabricated': True}
            case('daily_retention', daily_retention)

            def panel():
                proc = subprocess.Popen([sys.executable, str(ENTRY), 'panel', '--port', '0'], env=env, cwd=tmp,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(proc)
                def address():
                    p = state / 'panel.json'
                    if p.exists():
                        value = json.loads(p.read_text())
                        if value.get('url') and value.get('pid') == proc.pid:
                            return value['url']
                url = wait_for(address)
                with urllib.request.urlopen(url, timeout=3) as response:
                    html = response.read().decode()
                    assert 'Codex Footprint' in html and 'Content-Security-Policy' in response.headers
                with urllib.request.urlopen(url + 'api/dashboard', timeout=3) as response:
                    body = json.load(response)
                    assert body['read_only'] is True and 'daily_reports' in body and 'roots' in body
                for path, method, headers, expected in [('/', 'POST', {}, 405), ('/../../config.json', 'GET', {}, 404), ('/api/dashboard', 'GET', {'Host': 'evil.invalid'}, 403), ('/api/dashboard', 'GET', {'Origin': 'https://evil.invalid'}, 403)]:
                    request = urllib.request.Request(url.rstrip('/') + path, method=method, headers=headers)
                    try:
                        urllib.request.urlopen(request, timeout=3)
                        raise AssertionError('Unexpected request accepted: ' + path)
                    except urllib.error.HTTPError as e:
                        assert e.code == expected, (path, e.code, expected)
                proc.terminate(); proc.wait(timeout=5)
                return {'html_and_live_data': True, 'post_traversal_host_origin_rejected': True, 'full_disk_scan_triggered': False}
            case('read_only_panel', panel)

            def service_plan():
                value = cli('service-plan')
                assert value['label'] == 'xingyu.wang.codexfootprint'
                assert value['install_performed'] is False
                assert value['plist']['RunAtLoad'] is True
                assert value['plist']['KeepAlive']['SuccessfulExit'] is False
                assert value['plist']['ThrottleInterval'] >= 10
                assert value['plist']['ProgramArguments'][-1] == 'supervise'
                return {'login_recovery_plan': True, 'no_personal_service_installed_by_test': True}
            case('service_plan', service_plan)

            def protocol():
                requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},
                            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'footprint_daily_summary','arguments':{}}},
                            {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'footprint_dashboard','arguments':{}}},
                            {'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'footprint_daily_summary','arguments':{'day':'2999-01-01'}}}]
                by_id={r['id']:r for r in map(json.loads,run('serve',input='\n'.join(map(json.dumps,requests))+'\n').stdout.splitlines())}
                specs={t['name']:t for t in by_id[2]['result']['tools']}
                assert len(specs)==9 and not specs['footprint_daily_summary']['annotations']['readOnlyHint']
                assert specs['footprint_dashboard']['annotations']['readOnlyHint']
                assert not by_id[3]['result']['isError'] and not by_id[4]['result']['isError']
                assert by_id[5]['result']['isError']
                assert cli('status')['history_analysis_count']==0
                yesterday=(datetime.date.today()-datetime.timedelta(days=1)).isoformat()
                empty=cli('daily-report','--day',yesterday)
                assert not empty['roots'] and not empty['coverage']['full_day']
                return {'mcp_tools':9,'annotations_and_future_date_rejection':True,'no_fabricated_missing_history':True}
            case('mcp_daily_dashboard', protocol)

            def idle_cpu():
                roots=[tmp/('idle-%03d'%n) for n in range(200)]
                for path in roots:path.mkdir()
                cli('enable',*[part for path in roots for part in ('--root',str(path))],'--no-defaults','--no-start','--notifications','inbox')
                config(monitor={'interval_seconds':.02,'refresh_seconds':3600})
                before=resource.getrusage(resource.RUSAGE_CHILDREN)
                run('worker','--max-ticks','8')
                after=resource.getrusage(resource.RUSAGE_CHILDREN)
                cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
                assert cpu<1.0, {'cpu_seconds':cpu,'budget_seconds':1.0,'ticks':8,'empty_roots':200}
                return {'cpu_seconds':cpu,'budget_seconds':1.0,'ticks':8,'empty_roots':200,'scope':'local regression budget; not a whole-machine CPU promise'}
            case('idle_cpu_budget', idle_cpu)

            def supervisor_disabled():
                cli('disable')
                p = run('supervise')
                value = json.loads(p.stdout)
                assert not value['enabled']
                assert p.returncode == 0
                return {'intentional_disable_success_exit': True}
            case('supervisor_disable', supervisor_disabled)
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait(timeout=5)
    report['temporary_process_files_removed'] = not tmp.exists()
    report['result'] = 'pass' if report['cases'] and all(c['result'] == 'pass' for c in report['cases']) else 'fail'
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'result': report['result'], 'cases': [{k:c[k] for k in ('name','result')} for c in report['cases']], 'report': str(out / 'report.json')}))
    return 0 if report['result'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
