from __future__ import annotations
from contextlib import contextmanager
import os
from pathlib import Path
import shlex
import sqlite3

from .config import load_config
from .engine import report, explain, cleanup_plan
from .store import Store

EVENTS = {'SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','Stop','SessionEnd','Interrupt'}
FAMILIES = {'python','python3','node','npm','pnpm','yarn','xcodebuild','swift','cargo','go','make','cmake','docker','git','uv'}


def event_metadata(payload):
    if not isinstance(payload,dict) or payload.get('hook_event_name') not in EVENTS:
        raise ValueError('Unsupported hook event')
    result = {'event':payload['hook_event_name']}
    for field in ('session_id','turn_id','tool_use_id','tool_name'):
        value = payload.get(field)
        if value is not None and (not isinstance(value,str) or len(value)>256):
            raise ValueError(f'Invalid hook {field}')
        result[field] = value
    if not result['session_id']:
        raise ValueError('Hook requires session_id')
    command = payload.get('tool_input',{})
    command = command.get('command','') if isinstance(command,dict) else ''
    if isinstance(command,str) and len(command)<65536:
        try:
            tokens = shlex.split(command)
            name = Path(tokens[0]).name if tokens else ''
            result['command_family'] = name if name in FAMILIES else 'other'
        except ValueError:
            result['command_family'] = 'other'
    return result


@contextmanager
def history(config, writable=False):
    path = config['data_dir'] / 'footprint.sqlite3'
    if not writable and not path.exists():
        yield None
        return
    if writable:
        store = Store(config)
    else:
        # Read-only queries never initialize state or change schema/journal settings.
        store = Store.__new__(Store)
        store.config,store.path = config,path
        store.db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=3)
        if store.db.execute('PRAGMA user_version').fetchone()[0]!=1:
            store.close()
            raise ValueError('Unsupported history schema version')
    try:
        yield store
    finally:
        store.close()


def operate(name, args=None):
    args = args or {}
    workspace = args.get('workspace')
    if workspace is not None and (not isinstance(workspace,str) or not Path(workspace).is_absolute()):
        raise ValueError('workspace must be an absolute path')
    config = load_config(workspace)
    if name in ('analyze-history','alerts','test-notification','daily-report','dashboard') or config.get('version') == 2 or (not config['enabled'] and (config['data_dir']/'global.sqlite3').exists()):
        from .monitor import operate as global_operate
        return global_operate(name,args)
    if name=='status':
        result = {'schema_version':1,'enabled':config['enabled'],'config_path':str(config['config_path']),
                  'data_directory':str(config['data_dir']),'deletion_supported':False,
                  'process_attribution_supported':False,'ui_supported':False,
                  'snapshot_count':0,'event_count':0,'integrity':'not_initialized',
                  'scope':config.get('scope'),'configured_roots':[str(r['path']) for r in config['roots']]}
        if config['enabled']:
            with history(config) as store:
                if store: result.update(store.status())
        return result
    if not config['enabled']:
        raise ValueError('Observer disabled: create an explicit configuration first (init-config --root PATH)')
    if name=='scan':
        with history(config,True) as store:
            snapshot = store.capture({'event':'Manual'})
        return {'schema_version':1,'snapshot':snapshot}
    with history(config) as store:
        snapshots = store.snapshots() if store else []
    result = report(snapshots,config['thresholds'],args.get('session_id'),args.get('turn_id'),args.get('limit',20))
    if name=='report': return result
    if name=='explain': return explain(result,args.get('path'))
    if name=='cleanup-plan': return cleanup_plan(result)
    raise ValueError('Unknown operation')


def handle_hook(payload):
    metadata = event_metadata(payload)
    cwd = payload.get('cwd')
    if not isinstance(cwd,str) or not Path(cwd).is_absolute():
        raise ValueError('Hook cwd must be an absolute path')
    config = load_config(cwd)
    if not config['enabled']: return
    if 'codex' in (metadata.get('tool_name') or '').lower() and 'footprint' in (metadata.get('tool_name') or '').lower():
        return  # Avoid recording observation of the observer's own MCP tools.
    if config.get('version') == 2:
        from .monitor import enqueue
        enqueue(config,metadata,cwd)
        return
    with history(config,True) as store:
        store.capture(metadata,scan=metadata['event'] not in {'SessionEnd','Interrupt'})
