#!/usr/bin/env python3
"""Real Codex CLI upgrade and shell-hook startup failure acceptance."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/'plugins/codex-footprint'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    report={'command':[sys.executable,str(Path(__file__).resolve()),'--output',str(out)],'environment':{'python':sys.version,'platform':sys.platform},'preconditions':'Compatible real Codex CLI and writable system temporary directory; no credentials/model or personal configuration changes.','inputs':'Disposable marketplace upgraded from manifest 0.2.0 to current source version; missing cache and crashing startup fixtures; unrelated cache sentinel.','cases':[]}
    def case(name,fn):
        try:report['cases'].append({'name':name,'result':'pass','evidence':fn()})
        except Exception:report['cases'].append({'name':name,'result':'fail','error':traceback.format_exc()})
    with tempfile.TemporaryDirectory(prefix='footprint-upgrade-e2e-') as tmp:
        tmp=Path(tmp)
        command=json.loads((PLUGIN/'hooks/hooks.json').read_text())['hooks']['PreToolUse'][0]['hooks'][0]['command']
        def missing():
            p=subprocess.run(command,shell=True,env=dict(os.environ,PLUGIN_ROOT=str(tmp/'missing')),capture_output=True,text=True)
            assert p.returncode==0 and not p.stdout and not p.stderr,(p.returncode,p.stderr)
            return {'missing_old_cache_is_silent_and_nonblocking':True}
        case('missing_hook_cache',missing)
        def crash():
            root=tmp/'crash';(root/'scripts').mkdir(parents=True)
            (root/'scripts/codex_footprint.py').write_text('raise RuntimeError("injected startup failure")\n')
            p=subprocess.run(command,shell=True,env=dict(os.environ,PLUGIN_ROOT=str(root)),capture_output=True,text=True)
            assert p.returncode==0 and not p.stdout,(p.returncode,p.stderr)
            return {'python_startup_failure_is_nonblocking':True}
        case('hook_startup_failure',crash)
        def upgrade():
            codex=shutil.which('codex');assert codex
            profile=tmp/'profile';state=tmp/'state';profile.mkdir();state.mkdir()
            env=dict(os.environ,CODEX_HOME=str(profile),CODEX_FOOTPRINT_DATA=str(state),PYTHONDONTWRITEBYTECODE='1')
            market=tmp/'market';shutil.copytree(PLUGIN,market/'plugin',ignore=shutil.ignore_patterns('__pycache__','artifacts','dist'))
            catalog=market/'.agents/plugins';catalog.mkdir(parents=True)
            (catalog/'marketplace.json').write_text(json.dumps({'name':'wxy-codex-plugins','plugins':[{'name':'codex-footprint','source':{'source':'local','path':'./plugin'},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'}}]}))
            manifest=market/'plugin/.codex-plugin/plugin.json';v=json.loads(manifest.read_text());version=v['version'];v['version']='0.2.0';manifest.write_text(json.dumps(v))
            def run(argv):
                p=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=40)
                assert p.returncode==0,(argv,p.stderr,p.stdout[:500]);return p.stdout
            run([codex,'--no-daemon','plugin','marketplace','add',str(market),'--json'])
            initial=json.loads(run([codex,'--no-daemon','plugin','add','codex-footprint@wxy-codex-plugins','--json']))
            old=Path(initial['installedPath'])
            (old.parent/'0.1.0').symlink_to(old.name,target_is_directory=True)
            (state/'runtime').symlink_to(old,target_is_directory=True)
            sentinel=profile/'plugins/cache/unrelated/sentinel';sentinel.parent.mkdir(parents=True);sentinel.write_text('preserve')
            before_config=(profile/'config.toml').read_bytes()
            v['version']=version;manifest.write_text(json.dumps(v))
            receipt=json.loads(run([sys.executable,str(PLUGIN/'scripts/update_plugin.py')]))
            assert receipt['installed']['version']==version
            for ver in ('0.2.0','0.1.0'):
                entry=old.parent/ver/'scripts/codex_footprint.py'
                assert run([sys.executable,str(entry),'--version']).strip()==version
                hook=subprocess.run([sys.executable,str(entry),'hook'],env=env,input=json.dumps({'hook_event_name':'SessionStart','session_id':'old-chat','cwd':str(tmp)}),capture_output=True,text=True)
                assert hook.returncode==0 and not hook.stdout
            assert (state/'runtime').resolve()==Path(receipt['installed']['installedPath']).resolve()
            assert sentinel.read_text()=='preserve' and (profile/'config.toml').read_bytes()==before_config
            assert not (state/'config.json').exists() and not (state/'global.sqlite3').exists()
            return {'real_cli_version_upgrade':True,'old_chat_entries_forward':True,'stable_runtime_updated':True,'unrelated_plugin_and_config_preserved':True,'observation_stays_inactive':True}
        case('real_cli_upgrade',upgrade)
    report['temporary_process_files_removed']=not tmp.exists()
    report['result']='pass' if all(c['result']=='pass' for c in report['cases']) else 'fail'
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'result':report['result'],'report':str(out/'report.json')}))
    return report['result']!='pass'
if __name__=='__main__':raise SystemExit(main())
