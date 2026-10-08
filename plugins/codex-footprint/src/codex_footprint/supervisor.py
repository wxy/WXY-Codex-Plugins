"""Explicit macOS user-service installation; no privileged daemon."""
from __future__ import annotations
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time

LABEL = 'xingyu.wang.codexfootprint'


def plan(config):
    data = config['data_dir']
    plist = {'Label': LABEL, 'ProgramArguments': [sys.executable, str(data/'runtime/scripts/codex_footprint.py'), 'supervise'],
             'RunAtLoad': True, 'KeepAlive': {'SuccessfulExit': False}, 'ThrottleInterval': 10,
             'EnvironmentVariables': {'CODEX_FOOTPRINT_DATA': str(data), 'CODEX_FOOTPRINT_CONFIG': str(config['config_path']),
                                      'CODEX_HOME': str(Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))).expanduser()),
                                      'PYTHONDONTWRITEBYTECODE': '1'},
             'StandardOutPath': '/dev/null', 'StandardErrorPath': '/dev/null'}
    return {'label': LABEL, 'install_performed': False, 'supported': sys.platform=='darwin', 'plist': plist,
            'path': str(Path.home()/'Library/LaunchAgents'/ (LABEL+'.plist')),
            'note': 'Unexpected exits restart after throttling; disabled monitoring exits successfully. No root service.'}


def install(config):
    if sys.platform != 'darwin':
        raise ValueError('Login service installation currently supports macOS only')
    result = plan(config)
    target = Path(result['path'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and plistlib.loads(target.read_bytes()).get('Label') != LABEL:
        raise ValueError('Refusing to overwrite an unrelated service')
    data = config['data_dir']
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    runtime = data/'runtime'
    if runtime.exists() and not runtime.is_symlink():
        raise ValueError('Runtime pointer must not replace an ordinary directory')
    link = data/('.runtime-'+str(os.getpid()))
    link.symlink_to(Path(__file__).resolve().parents[2], target_is_directory=True)
    os.replace(link, runtime)
    domain = 'gui/'+str(os.getuid())
    subprocess.run(['/bin/launchctl', 'bootout', domain+'/'+LABEL], capture_output=True, timeout=10)
    target.write_bytes(plistlib.dumps(result['plist']))
    os.chmod(target, 0o600)
    p = subprocess.run(['/bin/launchctl', 'bootstrap', domain, str(target)], capture_output=True, text=True, timeout=15)
    if p.returncode:
        raise OSError('launchctl bootstrap failed: '+p.stderr[:500])
    return dict(result, install_performed=True)


def remove(config):
    if sys.platform != 'darwin':
        raise ValueError('Login service removal currently supports macOS only')
    target = Path(plan(config)['path'])
    subprocess.run(['/bin/launchctl', 'bootout', 'gui/'+str(os.getuid())+'/'+LABEL], capture_output=True, timeout=10)
    if target.exists():
        if plistlib.loads(target.read_bytes()).get('Label') != LABEL:
            raise ValueError('Refusing to remove an unrelated service')
        target.unlink()
    return {'label': LABEL, 'removed': True, 'history_preserved': True}


def supervise():
    from .monitor import load, worker, host_disabled
    while True:
        config = load()
        if not config['enabled'] or host_disabled():
            return {'enabled': False}
        value = worker()
        if value.get('already_running'):
            time.sleep(2)
            continue
        if not value.get('enabled'):
            return value
        raise OSError('Worker exited unexpectedly; launchd will restart the service')
