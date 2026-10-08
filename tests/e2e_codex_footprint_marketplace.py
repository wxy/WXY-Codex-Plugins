#!/usr/bin/env python3
"""Black-box WXY marketplace -> installed plugin -> real filesystem/MCP E2E."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO/'plugins/codex-footprint'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', default=str(REPO/'test-artifacts/codex-footprint'))
    args=parser.parse_args()
    output=Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report={'command':f'{sys.executable} tests/e2e_codex_footprint_marketplace.py --output {output}',
            'preconditions':'Compatible Codex CLI and Python >=3.9; local filesystems; disposable profile; no model or credentials',
            'inputs':{'marketplace':str(REPO),'plugin':'codex-footprint@wxy-codex-plugins'},
            'steps':[],'started_at':time.time(),'result':'fail',
            'acceptance_limit':'Catalog, host installation, installed core E2E. Host hook trust/delivery and user observation roots are separate.'}
    source=subprocess.run(['git','-C',str(REPO),'rev-parse','HEAD'],text=True,capture_output=True)
    report['source_head']=source.stdout.strip()
    try:
        catalog=json.loads((REPO/'.agents/plugins/marketplace.json').read_text())
        entries=[r for r in catalog['plugins'] if r['name']=='codex-footprint']
        assert catalog['name']=='wxy-codex-plugins' and len(entries)==1
        assert entries[0]['source']['path']=='./plugins/codex-footprint'
        assert {r['name'] for r in catalog['plugins']} >= {'codex-daydream','codex-pr-title-hook','codex-footprint'}
        manifest=json.loads((PLUGIN/'.codex-plugin/plugin.json').read_text())
        assert manifest['name']=='codex-footprint' and 'independent' in manifest['description'].lower()
        assert (PLUGIN/'hooks/hooks.json').is_file() and (PLUGIN/'.mcp.json').is_file()
        assert not (PLUGIN/'.git').exists()
        codex=shutil.which('codex')
        assert codex, 'Codex CLI required'
        with tempfile.TemporaryDirectory(prefix='wxy-footprint-e2e-') as directory:
            temporary=Path(directory)
            profile=temporary/'codex-profile'
            profile.mkdir()
            state=temporary/'unconfigured-state'
            env=dict(os.environ,CODEX_HOME=str(profile),CODEX_FOOTPRINT_DATA=str(state),
                     CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),PYTHONDONTWRITEBYTECODE='1')
            def run(arguments, timeout=30):
                proc=subprocess.run(arguments,env=env,cwd=REPO,text=True,capture_output=True,timeout=timeout)
                report['steps'].append({'arguments':arguments,'code':proc.returncode,'stdout_sha256':hashlib.sha256(proc.stdout.encode()).hexdigest(),'stderr_excerpt':proc.stderr[:500]})
                assert proc.returncode==0, proc.stderr or proc.stdout
                return proc
            run([codex,'--version'])
            run([codex,'--no-daemon','plugin','marketplace','add',str(REPO),'--json'])
            installed=json.loads(run([codex,'--no-daemon','plugin','add','codex-footprint@wxy-codex-plugins','--json']).stdout)
            cache=Path(installed['installedPath'])
            assert installed['version']==manifest['version']
            digests={}
            for relative in ['.codex-plugin/plugin.json','.mcp.json','hooks/hooks.json','scripts/codex_footprint.py','scripts/update_plugin.py',
                             'src/codex_footprint/observer.py','src/codex_footprint/engine.py','src/codex_footprint/service.py',
                             'src/codex_footprint/monitor.py','src/codex_footprint/global_store.py','src/codex_footprint/inventory.py','src/codex_footprint/historical.py','src/codex_footprint/summaries.py','src/codex_footprint/panel.py','src/codex_footprint/supervisor.py','assets/dashboard.html']:
                a=hashlib.sha256((PLUGIN/relative).read_bytes()).hexdigest()
                b=hashlib.sha256((cache/relative).read_bytes()).hexdigest()
                assert a==b, relative
                digests[relative]=a
            report['source_installed_sha256']=digests
            status=json.loads(run([sys.executable,str(cache/'scripts/codex_footprint.py'),'status']).stdout)
            assert status['enabled'] is False and status['snapshot_count']==0 and not state.exists()
            report['unconfigured_installation']='inactive, no observation state created'
            run([sys.executable,str(cache/'tests/e2e.py'),'--output',str(output/'installed-e2e')],timeout=45)
            core=json.loads((output/'installed-e2e/report.json').read_text())
            assert core['failed']==0 and core['passed']>=19
            report['installed_core_results']={'passed':core['passed'],'failed':core['failed']}
            for suite in ('e2e_global','e2e_global_edges','e2e_monitor_dashboard'):
                run([sys.executable,str(cache/('tests/'+suite+'.py')),'--output',str(output/suite)],timeout=90)
                result=json.loads((output/suite/'report.json').read_text())
                assert result.get('failed',0)==0 and result.get('result','pass')=='pass'
                report[suite]={'passed':result.get('passed',len(result.get('cases',[]))),'failed':result.get('failed',0)}
            report['installation']=installed
            run([sys.executable,str(REPO/'tests/e2e_footprint_safe_upgrade.py'),'--output',str(output/'safe-upgrade')],timeout=90)
            upgrade=json.loads((output/'safe-upgrade/report.json').read_text())
            assert upgrade['result']=='pass'
            report['safe_upgrade']={'passed':len(upgrade['cases']),'failed':0}
        report['temporary_profile_removed']=not temporary.exists()
        report['result']='pass'
    except Exception:
        report['error']=traceback.format_exc()
    report['finished_at']=time.time()
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'report.md').write_text('# WXY Codex Footprint marketplace E2E\n\n'
        +f"Result: **{report['result'].upper()}**\n\nSource: `{report['source_head']}`\n\nCommand: `{report['command']}`\n\n"
        +f"Preconditions: {report['preconditions']}\n\nInputs: {report['inputs']}\n\n"
        +f"Installed core: {report.get('installed_core_results','not reached')}\n\n{report['acceptance_limit']}\n"
        +(f"\n```\n{report['error']}\n```\n" if 'error' in report else ''))
    print(json.dumps({'result':report['result'],'report':str(output/'report.json')}))
    return report['result']!='pass'

if __name__=='__main__': raise SystemExit(main())
