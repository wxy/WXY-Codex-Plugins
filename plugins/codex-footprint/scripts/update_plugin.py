#!/usr/bin/env python3
"""Upgrade only Codex Footprint, restoring old-chat hook paths before returning."""
from __future__ import annotations
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import uuid


def valid(root):
    try:
        return (root/'scripts/codex_footprint.py').is_file() and json.loads((root/'.codex-plugin/plugin.json').read_text())['name']=='codex-footprint'
    except (OSError,ValueError,KeyError):return False


def main():
    codex=shutil.which('codex')
    if not codex:raise OSError('Codex CLI is required')
    profile=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))).expanduser().resolve()
    cache=profile/'plugins/cache/wxy-codex-plugins/codex-footprint'
    versions=sorted([p for p in cache.iterdir() if re.fullmatch(r'\d+\.\d+\.\d+(?:[+.-][\w.-]+)?',p.name)],key=lambda p:(p.is_symlink(),p.name)) if cache.exists() else []
    previous=next((p for p in sorted(versions,key=lambda p:tuple(int(n) for n in p.name.split('+')[0].split('-')[0].split('.')),reverse=True) if valid(p)),None)
    receipt={'compatibility_entries':[],'stable_runtime_updated':False,'service_restarted':False}
    with tempfile.TemporaryDirectory(prefix='footprint-upgrade-backup-') as temporary:
        backup=Path(temporary)/'previous'
        if previous:shutil.copytree(previous,backup,ignore=shutil.ignore_patterns('__pycache__','artifacts','dist'))
        runtime=None
        try:
            process=subprocess.run([codex,'--no-daemon','plugin','add','codex-footprint@wxy-codex-plugins','--json'],capture_output=True,text=True,timeout=120)
            if process.returncode:raise OSError('Codex installation failed: '+process.stderr[:500])
            installed=json.loads(process.stdout)
            runtime=Path(installed['installedPath']).resolve()
            if runtime.parent!=cache.resolve() or not valid(runtime):raise OSError('Invalid installed runtime receipt')
            receipt['installed']=installed
        except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:
            receipt['error']=str(exc)
            if previous:
                if not valid(previous):shutil.copytree(backup,previous,dirs_exist_ok=True)
                runtime=previous.resolve()
        finally:
            if runtime:
                for old in versions:
                    entry=old/'scripts/codex_footprint.py'
                    if entry.is_file():continue
                    entry.parent.mkdir(parents=True,exist_ok=True)
                    tmp=entry.with_name('.compat-'+uuid.uuid4().hex)
                    tmp.write_text('#!/usr/bin/env python3\n"""Forward an existing chat to the current installed plugin."""\nimport runpy\nrunpy.run_path('+repr(str(runtime/'scripts/codex_footprint.py'))+',run_name="__main__")\n')
                    os.replace(tmp,entry)
                    receipt['compatibility_entries'].append(old.name)
                data=Path(os.environ.get('CODEX_FOOTPRINT_DATA',str(Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'codex-footprint'))).expanduser().resolve()
                pointer=data/'runtime'
                if pointer.is_symlink() and (pointer.resolve()==cache.resolve() or cache.resolve() in pointer.resolve().parents):
                    tmp=pointer.with_name('.runtime-'+uuid.uuid4().hex);tmp.symlink_to(runtime,target_is_directory=True);os.replace(tmp,pointer)
                    receipt['stable_runtime_updated']=True
                    agent=Path.home()/'Library/LaunchAgents/xingyu.wang.codexfootprint.plist'
                    if sys.platform=='darwin' and agent.exists():
                        value=plistlib.loads(agent.read_bytes())
                        if value.get('Label')=='xingyu.wang.codexfootprint' and Path(value.get('EnvironmentVariables',{}).get('CODEX_FOOTPRINT_DATA','/')).resolve()==data:
                            p=subprocess.run(['/bin/launchctl','kickstart','-k','gui/'+str(os.getuid())+'/xingyu.wang.codexfootprint'],capture_output=True,text=True,timeout=15)
                            receipt['service_restarted']=p.returncode==0
                            if p.returncode:receipt['service_error']=p.stderr[:500]
    receipt['temporary_backup_removed']=not Path(temporary).exists()
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    return 1 if 'error' in receipt or 'service_error' in receipt else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError) as exc:
        print('codex-footprint update: '+str(exc),file=sys.stderr);raise SystemExit(1)
