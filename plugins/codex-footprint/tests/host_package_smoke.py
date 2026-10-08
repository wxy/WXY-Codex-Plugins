#!/usr/bin/env python3
"""Parse and install only in a temporary Codex profile; never touch personal settings."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

REPO=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default=str(REPO/'artifacts/host-package'))
    args=parser.parse_args()
    output=Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    codex=shutil.which('codex')
    if not codex:
        raise SystemExit('Codex CLI required; this optional smoke test is separate from the transport E2E')
    report={'command':f'python3 tests/host_package_smoke.py --output {output}',
            'preconditions':'Compatible Codex CLI; local source; isolated disposable Codex profile; no account/model calls',
            'input':str(REPO),'steps':[],'started_at':time.time(),
            'acceptance_limit':'Package parsing/local installation only, not live lifecycle trust/delivery or official approval'}
    with tempfile.TemporaryDirectory(prefix='codex-footprint-host-package-') as directory:
        profile=Path(directory)/'codex-profile'
        profile.mkdir()
        # This uses Codex's documented profile location for an isolated child process;
        # the parent environment and the user's personal profile are unchanged.
        env=dict(os.environ,CODEX_HOME=str(profile))
        for arguments in (['--version'],
                          ['--no-daemon','plugin','marketplace','add',str(REPO),'--json'],
                          ['--no-daemon','plugin','add','codex-footprint@codex-footprint-local','--json']):
            proc=subprocess.run([codex,*arguments],env=env,cwd=REPO,text=True,capture_output=True,timeout=25)
            report['steps'].append({'arguments':arguments,'code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode: break
        report['result']='pass' if len(report['steps'])==3 and all(r['code']==0 for r in report['steps']) else 'fail'
    report['finished_at']=time.time()
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':report['result'],'report':str(output/'report.json')}))
    return report['result']!='pass'

if __name__=='__main__': raise SystemExit(main())
