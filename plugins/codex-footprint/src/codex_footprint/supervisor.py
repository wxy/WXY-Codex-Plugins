"""Explicit macOS user-service installation; no privileged daemon."""
from __future__ import annotations
import json
import hashlib
import shutil
import signal
import tempfile
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time

from . import __version__

LABEL = 'xingyu.wang.codexfootprint'


def prepare(config):
    """Pin only executable/runtime resources outside the evictable plugin cache."""
    source=Path(__file__).resolve().parents[2]
    data=config['data_dir'];data.mkdir(parents=True,exist_ok=True,mode=0o700)
    pointer=data/'runtime'
    if pointer.exists() and not pointer.is_symlink():
        raise ValueError('Runtime pointer must not replace an ordinary directory')
    files=[]
    for folder in ('src','scripts','assets','config','hooks','.codex-plugin'):
        for path in (source/folder).rglob('*'):
            if '__pycache__' in path.parts or path.suffix=='.pyc':continue
            if path.is_symlink():raise ValueError('Runtime source contains a symlink')
            if path.is_file():files.append(path.relative_to(source))
    files.sort()
    if Path('scripts/codex_footprint.py') not in files:raise ValueError('Missing runtime entrypoint')
    def digest(root):
        h=hashlib.sha256()
        for relative in files:
            path=root/relative
            if path.is_symlink() or not path.is_file():raise ValueError('Invalid pinned runtime')
            payload=path.read_bytes()
            h.update(str(relative).encode());h.update(str(len(payload)).encode());h.update(payload)
        return h.hexdigest()
    fingerprint=digest(source)
    versions=data/'runtime-versions';versions.mkdir(exist_ok=True,mode=0o700)
    if versions.is_symlink():raise ValueError('Runtime versions directory must be real')
    target=versions/(__version__+'-'+fingerprint[:16])
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix='.runtime-stage-',dir=versions) as temporary:
            stage=Path(temporary)/'runtime';stage.mkdir(mode=0o700)
            for relative in files:
                destination=stage/relative;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source/relative,destination)
            if digest(stage)!=fingerprint:raise ValueError('Runtime changed during staging')
            try:os.rename(stage,target)
            except OSError:
                if not target.is_dir() or digest(target)!=fingerprint:raise
    if target.is_symlink() or digest(target)!=fingerprint:raise ValueError('Pinned runtime fingerprint mismatch')
    link=data/('.runtime-'+str(os.getpid()))
    try:
        link.symlink_to(target,target_is_directory=True)
        os.replace(link,pointer)
    finally:
        if link.is_symlink():link.unlink()
    return {'runtime':str(target),'stable_entry':str(pointer/'scripts/codex_footprint.py'),
            'version':__version__,'cache_independent':True,'worker_started':False}


def retire_old_worker(config, health):
    """Only terminate the recorded old runtime that also owns this state's lock."""
    pid=health.get('pid')
    if not isinstance(pid,int) or pid<=1 or pid==os.getpid():raise ValueError('Invalid old worker PID')
    command=subprocess.run(['/bin/ps','-p',str(pid),'-o','command='],capture_output=True,text=True,timeout=5)
    text=command.stdout.strip()
    if command.returncode or 'codex_footprint.py' not in text or not any(' '+mode in text for mode in ('worker','supervise')):
        raise ValueError('Refusing to signal an unrelated process')
    lsof=shutil.which('lsof') or '/usr/sbin/lsof'
    lock=(config['data_dir']/'worker.lock').resolve()
    opened=subprocess.run([lsof,'-a','-p',str(pid),'-Fn','--',str(lock)],capture_output=True,text=True,timeout=10)
    if opened.returncode or ('n'+str(lock)) not in opened.stdout.splitlines():
        raise ValueError('Old worker does not own the expected lock file')
    os.kill(pid,signal.SIGTERM)
    from .monitor import worker_health
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        current=worker_health(config['data_dir'])
        if not current['running'] or current.get('pid')!=pid:return
        time.sleep(.1)
    raise OSError('Old worker did not release the state lock')



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
    prepared = prepare(config)
    domain = 'gui/'+str(os.getuid())
    subprocess.run(['/bin/launchctl', 'bootout', domain+'/'+LABEL], capture_output=True, timeout=10)
    target.write_bytes(plistlib.dumps(result['plist']))
    os.chmod(target, 0o600)
    p = subprocess.run(['/bin/launchctl', 'bootstrap', domain, str(target)], capture_output=True, text=True, timeout=15)
    if p.returncode:
        raise OSError('launchctl bootstrap failed: '+p.stderr[:500])
    return dict(result, install_performed=True, runtime=prepared['runtime'], cache_independent=True)


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
    from .monitor import load, worker, host_disabled, worker_health
    while True:
        config = load()
        if not config['enabled'] or host_disabled():
            return {'enabled': False}
        health=worker_health(config['data_dir'])
        if health['running'] and health.get('version')!=__version__:
            retire_old_worker(config,health)
        value = worker()
        if value.get('already_running'):
            time.sleep(2)
            continue
        if not value.get('enabled'):
            return value
        raise OSError('Worker exited unexpectedly; launchd will restart the service')
