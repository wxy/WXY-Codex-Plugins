#!/usr/bin/env python3
"""Black-box acceptance: real hooks, filesystem writes, CLI and MCP stdio."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / 'scripts/codex_footprint.py'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(REPO / 'artifacts/e2e'))
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'command': f'{sys.executable} tests/e2e.py --output {output}',
              'environment': {'python': sys.version, 'platform': platform.platform()},
              'preconditions': 'Python >=3.9, local filesystem, no network or credentials',
              'inputs': 'Synthetic allocated files, hardlink, sparse file, symlink and subprocess writer; generated below',
              'cases': [], 'started_at': time.time()}
    source = subprocess.run(['git','-C',str(REPO),'rev-parse','HEAD'],capture_output=True,text=True)
    report['source'] = {'repository':str(REPO),'head':source.stdout.strip() if source.returncode==0 else None}
    transcript = []
    with tempfile.TemporaryDirectory(prefix='codex-footprint-e2e-') as directory:
        fixture = Path(directory)
        root = fixture / 'workspace with spaces'
        root.mkdir()
        data = fixture / 'state'
        config_path = fixture / 'config.json'
        config = {'version': 1, 'enabled': True, 'roots': [{'id': 'workspace', 'path': str(root)}],
                  'observer': {'max_entries': 20000, 'max_seconds': 2, 'bucket_depth': 1, 'top_files': 10},
                  'thresholds': {'large_bytes': 131072, 'growth_bytes': 65536,
                                 'rapid_bytes_per_second': 1, 'many_files': 8, 'sustained_intervals': 2},
                  'retention': {'max_snapshots': 100, 'max_events': 200}}
        config_path.write_text(json.dumps(config))
        env = dict(os.environ, CODEX_FOOTPRINT_DATA=str(data), CODEX_FOOTPRINT_CONFIG=str(config_path),
                   PLUGIN_ROOT=str(REPO), PLUGIN_DATA=str(data), PYTHONDONTWRITEBYTECODE='1')

        def run(*arguments, input=None, check=True, custom_env=None):
            proc = subprocess.run([sys.executable, str(CLI), *arguments], input=input,
                                  text=True, capture_output=True, env=custom_env or env,
                                  cwd=root, timeout=15)
            transcript.append({'argv': list(arguments), 'input': input, 'code': proc.returncode,
                               'stdout': proc.stdout, 'stderr': proc.stderr})
            if check and proc.returncode:
                raise AssertionError(proc.stderr or proc.stdout)
            return proc

        def json_run(*arguments):
            return json.loads(run(*arguments).stdout)

        hooks = None

        def hook(event, turn='turn-1', tool='tool-1', **extra):
            payload = dict(hook_event_name=event, cwd=str(root), session_id='session-1',
                           turn_id=turn, tool_use_id=tool, tool_name='Bash',
                           tool_input={'command': 'python3 writer.py SECRET_SHOULD_NOT_BE_SAVED'}, **extra)
            handler = hooks['hooks'][event][0]['hooks'][0]
            proc = subprocess.run(handler['command'], shell=True, input=json.dumps(payload),
                                  text=True, capture_output=True, env=env, cwd=root, timeout=15)
            transcript.append({'event': event, 'code': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr})
            assert proc.returncode == 0 and proc.stdout == '', proc

        def write(path, size):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('wb') as stream:
                stream.write(b'F' * size)

        def case(name, fn):
            start = time.monotonic()
            try:
                detail = fn()
                report['cases'].append({'name': name, 'result': 'pass', 'seconds': time.monotonic()-start, 'evidence': detail})
            except Exception:
                report['cases'].append({'name': name, 'result': 'fail', 'seconds': time.monotonic()-start,
                                        'error': traceback.format_exc()})
                raise

        try:
            def packaging():
                nonlocal hooks
                manifest = json.loads((REPO / '.codex-plugin/plugin.json').read_text())
                assert manifest['name'] == 'codex-footprint'
                assert 'independent' in manifest['description'].lower()
                hooks = json.loads((REPO / 'hooks/hooks.json').read_text())
                assert {'SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop', 'SessionEnd', 'Interrupt'} <= set(hooks['hooks'])
                assert json.loads((REPO / '.mcp.json').read_text())['mcpServers']['codex-footprint']['command'] == 'python3'
                return {'name': manifest['name'], 'events': list(hooks['hooks'])}
            case('Local package and hook commands', packaging)

            def config_initialization():
                target = fixture / 'new-config.json'
                result = json_run('init-config', '--root', str(root), '--output', str(target))
                assert Path(result['config_path']).is_file()
                before = target.read_bytes()
                proc = run('init-config', '--root', str(root), '--output', str(target), check=False)
                assert proc.returncode != 0 and target.read_bytes()==before
                invalid = fixture / 'invalid-config.json'
                proc = run('init-config', '--root', '/', '--output', str(invalid), check=False)
                assert proc.returncode != 0 and not invalid.exists()
                proc = run('init-config', '--root', str(root), '--root', str(root / 'build'), '--output', str(invalid), check=False)
                assert proc.returncode != 0 and not invalid.exists()
                return {'valid_scope':'created','existing_config':'preserved','disk_and_overlapping_scopes':'rejected before writing'}
            case('Configuration initialization validates scope and preserves existing files', config_initialization)

            def baseline():
                write(root / 'historical/cache.bin', 262144)
                hook('SessionStart')
                result = json_run('report')
                assert result['baseline_available'] is False
                assert result['heavy_hitters'][0]['historical_bytes'] >= 262144
                assert result['heavy_hitters'][0]['growth_bytes'] is None
                return result
            case('First snapshot identifies historical heavy hitters without invented growth', baseline)

            def task_growth():
                hook('UserPromptSubmit')
                hook('PreToolUse')
                writer = "from pathlib import Path; p=Path('build/output.bin'); p.parent.mkdir(exist_ok=True); p.write_bytes(b'X'*196608)"
                subprocess.run([sys.executable, '-c', writer], cwd=root, check=True)
                hook('PostToolUse')
                hook('Stop')
                result = json_run('report', '--session-id', 'session-1', '--turn-id', 'turn-1')
                assert result['baseline_available'] is True
                assert result['growth_bytes'] >= 196608
                target = next(row for row in result['heavy_hitters'] if row['path'].endswith('/build'))
                assert target['growth_bytes'] >= 196608
                assert result['attribution']['level'] == 'temporal_correlation'
                assert result['attribution']['process_verified'] is False
                assert result['tool_windows'][0]['tool_use_id'] == 'tool-1'
                assert result['tool_windows'][0]['growth_bytes'] >= 196608
                return result
            case('Codex task hooks bracket real external-process growth', task_growth)

            def missing_baseline():
                hook('PostToolUse', turn='orphan-turn', tool='orphan-tool')
                result = json_run('report', '--session-id', 'session-1', '--turn-id', 'orphan-turn')
                assert result['baseline_available'] is False and result['growth_bytes'] is None
                assert result['tool_windows'][0]['before_snapshot_id'] is None
                assert result['tool_windows'][0]['growth_bytes'] is None
                return result
            case('Missing task/tool baselines stay unknown rather than substituting history', missing_baseline)

            def shrinking():
                write(root / 'shrinking/output.bin', 262144)
                hook('UserPromptSubmit', turn='shrink-turn')
                write(root / 'shrinking/output.bin', 131072)
                hook('Stop', turn='shrink-turn')
                result = json_run('report', '--session-id', 'session-1', '--turn-id', 'shrink-turn')
                assert result['growth_bytes'] <= -131072
                target = next(row for row in result['heavy_hitters'] if row['path'].endswith('/shrinking'))
                assert 'large_growth' not in target['signals'] and 'sustained_growth' not in target['signals']
                return result
            case('Shrinking artifacts report signed change and reset growth signals', shrinking)

            def steady_growth():
                for n in (2, 3):
                    json_run('scan')
                    write(root / 'build/output.bin', 196608 + n * 65536)
                    json_run('scan')
                result = json_run('report')
                assert any('sustained_growth' in row['signals'] for row in result['heavy_hitters'])
                for i in range(12):
                    write(root / f'many/{i}.txt', 10)
                json_run('scan')
                result = json_run('report')
                assert any('many_files' in row['signals'] for row in result['heavy_hitters'])
                return result
            case('Sustained accumulation and many-file signals', steady_growth)

            def links_and_sparse():
                write(root / 'links/a.bin', 131072)
                os.link(root / 'links/a.bin', root / 'links/b.bin')
                outside = fixture / 'outside'
                write(outside / 'secret.bin', 1048576)
                (root / 'escape').symlink_to(outside, target_is_directory=True)
                with (root / 'sparse.bin').open('wb') as stream:
                    stream.truncate(16 * 1024 * 1024)
                result = json_run('scan')
                scan = result['snapshot']['roots'][0]
                assert scan['hardlink_duplicates'] == 1 and scan['symlinks_skipped'] == 1
                assert scan['logical_bytes'] > scan['allocated_bytes']
                assert not any('secret.bin' in row['path'] for row in scan['top_files'])
                return scan
            case('Hardlink deduplication, symlink boundary, allocated vs logical size', links_and_sparse)

            def mcp():
                requests = [
                    {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'e2e','version':'1'}}},
                    {'jsonrpc':'2.0','method':'notifications/initialized'},
                    {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                    {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'footprint_status','arguments':{}}},
                    {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'footprint_report','arguments':{}}},
                    {'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'footprint_explain','arguments':{'path':str(root / 'build')}}},
                    {'jsonrpc':'2.0','id':6,'method':'tools/call','params':{'name':'footprint_cleanup_plan','arguments':{}}},
                    {'jsonrpc':'2.0','id':7,'method':'tools/call','params':{'name':'footprint_scan','arguments':{}}},
                    {'jsonrpc':'2.0','id':8,'method':'tools/call','params':{'name':'delete','arguments':{}}},
                    {'jsonrpc':'2.0','id':9,'method':'tools/call','params':{'name':'footprint_report','arguments':{'limit':True}}},
                    {'jsonrpc':'2.0','id':10,'method':'tools/call','params':{'name':'footprint_scan','arguments':{'root':'/'}}},
                    {'jsonrpc':'2.0','id':11,'method':'ping'},
                ]
                before = hashlib.sha256((root / 'build/output.bin').read_bytes()).hexdigest()
                proc = run('serve', input='\n'.join(json.dumps(r) for r in requests)+'\n')
                responses = [json.loads(line) for line in proc.stdout.splitlines()]
                by_id = {r['id']:r for r in responses}
                assert len(responses) == 11
                assert {'footprint_status','footprint_scan','footprint_report','footprint_explain','footprint_cleanup_plan','footprint_analyze_history','footprint_alerts'} <= {t['name'] for t in by_id[2]['result']['tools']}
                for i in range(3, 8):
                    assert not by_id[i]['result'].get('isError'), by_id[i]
                assert by_id[6]['result']['structuredContent']['execution_supported'] is False
                assert by_id[8]['error']['code'] == -32602
                assert by_id[9]['error']['code'] == -32602
                assert by_id[10]['error']['code'] == -32602
                assert before == hashlib.sha256((root / 'build/output.bin').read_bytes()).hexdigest()
                return responses
            case('MCP handshake, all seven tools, input rejection and non-destructive plan', mcp)

            def incomplete():
                config['observer']['max_entries'] = 2
                config_path.write_text(json.dumps(config))
                snapshot = json_run('scan')['snapshot']
                assert snapshot['complete'] is False
                result = json_run('report')
                assert result['growth_bytes'] is None and result['coverage']['complete'] is False
                config['observer']['max_entries'] = 20000
                config_path.write_text(json.dumps(config))
                return result
            case('Budget exhaustion never produces numeric growth or reclaim claims', incomplete)

            def overlap():
                config['roots'].append({'id':'nested','path':str(root / 'build')})
                config_path.write_text(json.dumps(config))
                proc = run('scan', check=False)
                assert proc.returncode != 0 and 'overlap' in proc.stderr.lower()
                hook('PreToolUse')  # observer configuration failures must not block the user's command
                config['roots'].pop()
                config_path.write_text(json.dumps(config))
                return {'cli_error':proc.stderr, 'hook':'fail-open'}
            case('Overlapping roots rejected; hook failures remain fail-open', overlap)

            def missing():
                config['roots'].append({'id':'missing','path':str(fixture / 'missing')})
                config_path.write_text(json.dumps(config))
                snapshot = json_run('scan')['snapshot']
                assert snapshot['complete'] is False
                assert snapshot['roots'][1]['status'] == 'missing'
                config['roots'].pop()
                config_path.write_text(json.dumps(config))
                return snapshot
            case('Missing root is unknown coverage rather than zero occupancy', missing)

            def scope_and_read_only():
                other = fixture / 'other-workspace'
                other.mkdir()
                original = config['roots']
                config['roots'] = [{'id':'other','path':str(other)}]
                config_path.write_text(json.dumps(config))
                result = json_run('report')
                assert result['baseline_available'] is False and result['growth_bytes'] is None
                fresh_data = fixture / 'read-only-state'
                read_env = dict(env, CODEX_FOOTPRINT_DATA=str(fresh_data))
                proc = run('status',custom_env=read_env)
                assert json.loads(proc.stdout)['snapshot_count']==0 and not fresh_data.exists()
                proc = run('report',custom_env=read_env)
                assert json.loads(proc.stdout)['heavy_hitters']==[] and not fresh_data.exists()
                config['roots'] = original
                config_path.write_text(json.dumps(config))
                return {'changed_scope':result,'fresh_queries':'no state created'}
            case('Scope changes isolate history; query tools do not initialize state', scope_and_read_only)

            def self_exclusion():
                inside = root / 'observer-state'
                inside_env = dict(env, CODEX_FOOTPRINT_DATA=str(inside))
                proc = run('scan',custom_env=inside_env)
                snapshot = json.loads(proc.stdout)['snapshot']
                assert snapshot['roots'][0]['excluded_entries']>=1
                assert not any(str(inside) in row['path'] for row in snapshot['roots'][0]['top_files'])
                return {'self_observation':'excluded','coverage_complete':snapshot['complete']}
            case('Observer metadata is excluded even when stored inside a configured root', self_exclusion)

            def concurrent_hooks():
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                    list(pool.map(lambda i: hook('PreToolUse', turn=f'parallel-{i}', tool=f'parallel-tool-{i}'), range(6)))
                result = json_run('status')
                assert result['snapshot_count'] >= 15
                assert result['integrity'] == 'ok'
                return result
            case('Concurrent hook processes serialize SQLite snapshots', concurrent_hooks)

            def privacy():
                contents = (data / 'footprint.sqlite3').read_bytes()
                assert b'SECRET_SHOULD_NOT_BE_SAVED' not in contents
                hook('SessionEnd')
                hook('Interrupt')
                proc = run('hook', input='{bad json', check=False)
                assert proc.returncode == 0 and proc.stdout == '' and proc.stderr
                return {'command_prompt_transcript_contents':'not persisted', 'malformed_hook':'fail-open'}
            case('Minimal event metadata and malformed hook fail-open', privacy)

            def disabled():
                env_without_config = dict(env, CODEX_FOOTPRINT_DATA=str(fixture / 'disabled-state'),
                                          CODEX_FOOTPRINT_CONFIG=str(fixture / 'absent.json'))
                proc = run('hook', input=json.dumps({'hook_event_name':'SessionStart','cwd':str(root),'session_id':'disabled'}), custom_env=env_without_config)
                assert proc.stdout == '' and not (fixture / 'disabled-state').exists()
                return {'without_configuration':'no scan and no state created'}
            case('Fresh install is inactive until explicit scope configuration', disabled)

            def retention():
                config['retention'] = {'max_snapshots': 4, 'max_events': 6}
                config_path.write_text(json.dumps(config))
                for i in range(7):
                    hook('PreToolUse', tool=f'retention-{i}')
                status = json_run('status')
                assert status['snapshot_count'] <= 4 and status['event_count'] <= 6
                return status
            case('Bounded history retention', retention)

            def local_package():
                local = json_run('package', '--profile', 'local', '--output', str(fixture / 'local'))
                with zipfile.ZipFile(local['archive']) as archive:
                    names = archive.namelist()
                    assert 'codex-footprint/hooks/hooks.json' in names
                    assert 'codex-footprint/.mcp.json' in names
                    assert 'codex-footprint/.agents/plugins/marketplace.json' in names
                    assert 'codex-footprint/docs/distribution.md' in names
                    archive.extractall(fixture / 'unpacked')
                packaged = fixture / 'unpacked/codex-footprint'
                proc = subprocess.run([sys.executable, str(packaged / 'scripts/codex_footprint.py'), 'report'],
                                      text=True, capture_output=True, env=env, cwd=root, timeout=15)
                assert proc.returncode == 0, proc.stderr
                assert 'heavy_hitters' in json.loads(proc.stdout)
                second = json_run('package', '--output', str(fixture / 'local-again'))
                assert local['sha256']==second['sha256']
                return {'local_packaged_cli':'passed','complete_hooks_and_mcp':'included','reproducible_sha256':local['sha256']}
            case('Complete relocatable local package and reproducible archive', local_package)
        except Exception:
            pass
    report['finished_at'] = time.time()
    report['passed'] = sum(c['result']=='pass' for c in report['cases'])
    report['failed'] = sum(c['result']=='fail' for c in report['cases'])
    (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    (output / 'transcript.json').write_text(json.dumps(transcript, indent=2, ensure_ascii=False)+'\n')
    lines = ['# Codex Footprint end-to-end report', '', f"Passed: {report['passed']}; Failed: {report['failed']}", '',
             f"Command: `{report['command']}`", '', f"Environment: {report['environment']}", '',
             f"Preconditions: {report['preconditions']}", '', f"Inputs: {report['inputs']}", '']
    for c in report['cases']:
        lines.append(f"- {c['result'].upper()}: {c['name']} ({c['seconds']:.3f}s)")
        if c.get('error'): lines.extend(['', '```', c['error'], '```'])
    (output / 'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'report':str(output / 'report.json')}))
    return bool(report['failed'])

if __name__ == '__main__':
    raise SystemExit(main())
