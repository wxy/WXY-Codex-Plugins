"""Selected system/development volumes; metadata checks only, no directory walks."""
import copy
from pathlib import Path
import sys


def primary_path():
    return Path('/System/Volumes/Data') if sys.platform == 'darwin' else Path('/')


def _device(path):
    p = Path(path).expanduser().resolve()
    if sys.platform == 'darwin' and str(p).startswith('/Volumes/'):
        mount = Path(*p.parts[:3])
        if not mount.exists():
            return None
    while True:
        try:
            return p.stat().st_dev
        except FileNotFoundError:
            if p == p.parent:
                return None
            p = p.parent


def capacity_paths(config):
    if '_capacity_paths' in config:
        return config['_capacity_paths']
    paths = [primary_path()]
    declared = config.get('monitor', {}).get('development_volume')
    candidate = Path(declared) if declared else Path.home()/'develop' if config.get('discovery') else None
    if candidate:
        try:
            p = candidate.expanduser().resolve()
            if str(p).startswith('/Volumes/'):
                mount = Path(*p.parts[:3])
            elif _device(p) != primary_path().stat().st_dev:
                while not p.exists() and p != p.parent:
                    p = p.parent
                device = p.stat().st_dev
                while p != p.parent and p.parent.stat().st_dev == device:
                    p = p.parent
                mount = p
            else:
                mount = primary_path()
            if mount not in paths:
                paths.append(mount)
        except (OSError, RuntimeError):
            pass
    config['_capacity_paths'] = paths
    return paths


def monitored_path(path, config):
    try:
        device = _device(path)
        if device is None:
            return False
        for mount in capacity_paths(config):
            try:
                if device == mount.stat().st_dev:
                    return True
            except OSError:
                pass
    except (OSError, RuntimeError, ValueError, TypeError):
        pass
    return False


def series_for(path, config):
    try:
        p = Path(path).expanduser().resolve()
        for mount in capacity_paths(config):
            if p == mount or (mount != Path('/') and mount in p.parents):
                return str(mount)
        device = _device(p)
        for mount in capacity_paths(config):
            try:
                if device == mount.stat().st_dev:
                    return str(mount)
            except OSError:
                pass
    except (OSError, RuntimeError, ValueError, TypeError):
        pass
    return None


def current_volumes(rows, config):
    groups = {}
    for row in rows:
        key = series_for(row.get('path'), config)
        if key:
            groups.setdefault(key, []).append(row)
    result = []
    for mount in capacity_paths(config):
        key = str(mount)
        if key not in groups:
            continue
        latest = max(groups[key], key=lambda r: r.get('sampled_at', 0))
        result.append(dict(latest, path=key, history_paths=sorted({key, *(r['path'] for r in groups[key])}),
                           label='内置盘' if mount == primary_path() else mount.name+' 开发盘'))
    return result


def scoped_report(report, config):
    value = copy.deepcopy(report)
    value['roots'] = [row for row in value.get('roots', []) if series_for(row.get('path'), config)]
    value['alerts'] = [row for row in value.get('alerts', []) if series_for(row.get('path'), config)]
    value['volumes'] = current_volumes(value.get('volumes', []), config)
    coverage = value.setdefault('coverage', {})
    coverage['measured_roots'] = len(value['roots'])
    coverage['roots_without_complete_endpoints'] = [p for p in coverage.get('roots_without_complete_endpoints', []) if series_for(p, config)]
    coverage['storage_scope'] = 'system_and_development_volumes'
    if not value['roots']:
        coverage['full_day'] = False
    return value
