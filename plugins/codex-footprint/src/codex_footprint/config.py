from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

OBSERVER = {'max_entries': 100000, 'max_seconds': 2, 'bucket_depth': 1, 'top_files': 20}
THRESHOLDS = {'large_bytes': 1024**3, 'growth_bytes': 256*1024**2,
              'rapid_bytes_per_second': 64*1024**2, 'many_files': 10000, 'sustained_intervals': 3}
RETENTION = {'max_snapshots': 500, 'max_events': 5000}


def is_under(path, parent):
    return path == parent or parent in path.parents


def data_directory():
    explicit = os.environ.get('CODEX_FOOTPRINT_DATA') or os.environ.get('PLUGIN_DATA')
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))).expanduser().resolve() / 'codex-footprint'


def number(value, name, low, high, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not low <= value <= high:
        raise ValueError(f'{name} must be {"an integer" if integer else "a number"} between {low} and {high}')
    return value


def merge_known(raw, defaults, name):
    if not isinstance(raw, dict) or set(raw) - set(defaults):
        raise ValueError(f'Unknown or invalid {name} settings')
    return dict(defaults, **raw)


def load_config(cwd=None):
    data = data_directory()
    config_path = Path(os.environ.get('CODEX_FOOTPRINT_CONFIG', str(data/'config.json'))).expanduser().resolve()
    if not config_path.is_file():
        return {'enabled':False, 'data_dir':data, 'config_path':config_path, 'roots':[]}
    if config_path.stat().st_size > 1024*1024:
        raise ValueError('Configuration exceeds 1 MiB')
    raw = json.loads(config_path.read_text())
    return validate_config(raw, data, config_path, cwd)


def validate_config(raw, data, config_path, cwd=None):
    if not isinstance(raw, dict) or set(raw)-{'version','enabled','roots','observer','thresholds','retention','exclude_names'}:
        raise ValueError('Unknown configuration fields')
    if raw.get('version') != 1 or type(raw.get('enabled', False)) is not bool:
        raise ValueError('Configuration requires version 1 and boolean enabled')
    if not raw.get('enabled'):
        return {'enabled':False, 'data_dir':data, 'config_path':config_path, 'roots':[]}
    cwd = Path(cwd or os.getcwd()).resolve()
    roots = []
    if not isinstance(raw.get('roots'), list) or not 1 <= len(raw['roots']) <= 16:
        raise ValueError('Configure between 1 and 16 explicit roots')
    for root in raw['roots']:
        if not isinstance(root, dict) or set(root)-{'id','path','enabled'}:
            raise ValueError('Invalid root')
        if type(root.get('enabled', True)) is not bool:
            raise ValueError('Root enabled must be boolean')
        if not root.get('enabled', True):
            continue
        identifier, text = root.get('id'), root.get('path')
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 64 or not isinstance(text, str):
            raise ValueError('Root requires a short id and absolute path or $CWD')
        path = cwd if text == '$CWD' else Path(text).expanduser()
        if not path.is_absolute():
            raise ValueError('Root paths must be absolute or $CWD')
        if path.is_symlink():
            raise ValueError('Symlink roots are not supported')
        path = path.resolve()
        if path == Path(path.anchor) or path == Path.home().resolve():
            raise ValueError('Choose a development directory rather than a disk or home root')
        if is_under(path, data):
            raise ValueError('Observer state cannot be a scan root')
        if any(identifier == r['id'] or is_under(path, r['path']) or is_under(r['path'], path) for r in roots):
            raise ValueError('Root ids must be unique and paths must not overlap')
        roots.append({'id':identifier, 'path':path})
    if not roots:
        raise ValueError('At least one root must be enabled')
    obs = merge_known(raw.get('observer', {}), OBSERVER, 'observer')
    number(obs['max_entries'], 'max_entries', 1, 200000, True)
    number(obs['max_seconds'], 'max_seconds', 0.01, 5)
    number(obs['bucket_depth'], 'bucket_depth', 1, 3, True)
    number(obs['top_files'], 'top_files', 1, 100, True)
    thresholds = merge_known(raw.get('thresholds', {}), THRESHOLDS, 'thresholds')
    for key in thresholds:
        number(thresholds[key], key, 1, 10**15, key != 'rapid_bytes_per_second')
    number(thresholds['sustained_intervals'], 'sustained_intervals', 2, 30, True)
    retention = merge_known(raw.get('retention', {}), RETENTION, 'retention')
    number(retention['max_snapshots'], 'max_snapshots', 2, 2000, True)
    number(retention['max_events'], 'max_events', 2, 20000, True)
    if retention['max_events'] < retention['max_snapshots']:
        raise ValueError('max_events must be at least max_snapshots')
    excludes = raw.get('exclude_names', [])
    if not isinstance(excludes,list) or len(excludes)>100 or any(not isinstance(s,str) or not s or '/' in s for s in excludes):
        raise ValueError('exclude_names must contain at most 100 directory or file names')
    identity = {'roots':[{'id':r['id'],'path':str(r['path'])} for r in roots],
                'observer':obs, 'exclude_names':sorted(excludes), 'data_dir':str(data), 'accounting_version':1}
    scope = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return {'enabled':True, 'data_dir':data, 'config_path':config_path, 'roots':roots,
            'observer':obs, 'thresholds':thresholds, 'retention':retention, 'exclude_names':excludes, 'scope':scope}
