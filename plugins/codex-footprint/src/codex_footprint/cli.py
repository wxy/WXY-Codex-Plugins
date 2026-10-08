from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

from . import __version__
from .config import data_directory, validate_config, OBSERVER, THRESHOLDS, RETENTION
from .service import operate, handle_hook


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Codex Footprint — independent development storage growth monitor')
    parser.add_argument('--version',action='version',version=__version__)
    sub = parser.add_subparsers(dest='command',required=True)
    for name in ('status','scan','report','explain','cleanup-plan'):
        p = sub.add_parser(name)
        p.add_argument('--workspace')
        if name not in ('status','scan'):
            p.add_argument('--session-id')
            p.add_argument('--turn-id')
            p.add_argument('--limit',type=int,default=20)
        if name=='explain': p.add_argument('--path')
    sub.add_parser('hook')
    sub.add_parser('serve')
    init = sub.add_parser('init-config')
    init.add_argument('--root',action='append',required=True)
    init.add_argument('--output')
    package = sub.add_parser('package')
    package.add_argument('--profile',choices=['local'],default='local')
    package.add_argument('--output',required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    if command=='hook':
        try:
            raw = sys.stdin.buffer.read(1024*1024+1)
            if len(raw)>1024*1024: raise ValueError('Hook input exceeds 1 MiB')
            handle_hook(json.loads(raw))
        except Exception as exc:
            print(f'codex-footprint: observation skipped ({type(exc).__name__}: {exc})',file=sys.stderr)
        return 0  # No stdout, decision, permission rewrite, or exit 2.
    try:
        if command=='serve':
            from .mcp import serve
            serve()
            return 0
        if command=='package':
            from .packaging import build
            value = build(args['profile'],args['output'])
        elif command=='init-config':
            output = Path(args['output']).expanduser().resolve() if args.get('output') else Path(os.environ.get('CODEX_FOOTPRINT_CONFIG',str(data_directory()/'config.json'))).expanduser().resolve()
            roots = []
            for index,text in enumerate(args['root']):
                path = Path(text).expanduser()
                if not path.is_absolute(): raise ValueError('Roots must be absolute paths')
                roots.append({'id':f'root-{index+1}','path':str(path.resolve())})
            value = {'version':1,'enabled':True,'roots':roots,'observer':OBSERVER,'thresholds':THRESHOLDS,'retention':RETENTION,'exclude_names':[]}
            validate_config(value, data_directory(), output)
            output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with output.open('x') as stream:
                stream.write(json.dumps(value,indent=2)+'\n')
            value = {'config_path':str(output),'roots':roots,'note':'Explicit configuration saved. Does not install hooks or enable a plugin.'}
        else:
            args = {key:value for key,value in args.items() if value is not None}
            if 'limit' in args and not 1<=args['limit']<=100: raise ValueError('limit must be between 1 and 100')
            value = operate(command,args)
        print(json.dumps(value,indent=2,ensure_ascii=False))
        return 0
    except (ValueError,OSError,sqlite3.Error) as exc:
        print(f'codex-footprint: {exc}',file=sys.stderr)
        return 1
