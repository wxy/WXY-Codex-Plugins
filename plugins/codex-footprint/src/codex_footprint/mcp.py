"""Minimal MCP stdio transport: JSON-RPC lines, initialization and seven tools."""
from __future__ import annotations
import json
import sqlite3
import sys

from . import __version__
from .service import operate

VERSIONS = {'2024-11-05','2025-03-26','2025-06-18'}
MAX_LINE = 1024*1024
WORKSPACE = {'workspace':{'type':'string','description':'Absolute Codex workspace path. Needed when configuration uses $CWD.'}}
TASK = dict(WORKSPACE,session_id={'type':'string'},turn_id={'type':'string'},limit={'type':'integer','minimum':1,'maximum':100})
SPECS = {
    'footprint_analyze_history':('analyze-history','Explicitly analyze existing Codex session-associated occupancy, including pre-enable artifacts. Reads local historical evidence and writes a derived index; no deletion.',{'limit':{'type':'integer','minimum':1,'maximum':100}}),
    'footprint_alerts':('alerts','Read meaningful global findings and delivery status; optionally acknowledge all or one numeric finding ID.',{'ack':{'type':'string','description':'Optional: all, or a numeric finding ID. Updates only local acknowledgement metadata.'}}),
    'footprint_status':('status','Read observer configuration, coverage capabilities and history status.',WORKSPACE),
    'footprint_scan':('scan','Request a bounded background refresh of discovered/configured development roots. Global mode returns queued status, not a completed snapshot.',WORKSPACE),
    'footprint_report':('report','Read retained inventory/growth and latest explicit historical result. Global session filtering is path association, not exclusive per-turn ownership; legacy task baselines remain supported.',TASK),
    'footprint_explain':('explain','Explain retained occupancy and growth evidence for a directory; does not inspect file contents.',dict(TASK,path={'type':'string'})),
    'footprint_cleanup_plan':('cleanup-plan','Recommend owner-tool review of heavy hitters; cannot execute cleanup or guarantee reclaimed space.',TASK),
}


def tools():
    return [{'name':name,'description':description,
             'inputSchema':{'type':'object','properties':props,'additionalProperties':False},
             'annotations':{'readOnlyHint':operation not in ('scan','analyze-history','alerts'),'destructiveHint':False,
                            'idempotentHint':operation not in ('scan','analyze-history','alerts'),'openWorldHint':False}}
            for name,(operation,description,props) in SPECS.items()]


def validate_arguments(name, args):
    if name not in SPECS or not isinstance(args,dict):
        raise ValueError('Unknown tool or invalid arguments')
    props = SPECS[name][2]
    if set(args)-set(props): raise ValueError('Unknown arguments')
    for key,value in args.items():
        if props[key]['type']=='string' and (not isinstance(value,str) or not 1<=len(value)<=4096):
            raise ValueError(f'Invalid {key}')
        if key=='limit' and (type(value) is not int or not 1<=value<=100):
            raise ValueError('limit must be an integer between 1 and 100')
    if 'turn_id' in args and 'session_id' not in args:
        raise ValueError('turn_id requires session_id')


def serve():
    initialized = False
    while True:
        raw = sys.stdin.buffer.readline(MAX_LINE+1)
        if not raw: return
        if len(raw)>MAX_LINE:
            # Drain the oversized line without allocating it in memory.
            while raw and not raw.endswith(b'\n'):
                raw = sys.stdin.buffer.readline(MAX_LINE+1)
            emit({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Message exceeds 1 MiB'}})
            continue
        identifier = None
        try:
            try: request = json.loads(raw)
            except (ValueError,UnicodeError):
                emit({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Invalid JSON'}})
                continue
            if not isinstance(request,dict) or request.get('jsonrpc')!='2.0' or not isinstance(request.get('method'),str):
                emit({'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid request'}})
                continue
            identifier = request.get('id')
            if 'id' not in request:
                continue  # Notifications receive no response.
            if type(identifier) not in (int,str):
                emit({'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid request id'}})
                continue
            method = request['method']
            params = request.get('params',{})
            if not isinstance(params,dict): raise ValueError('params must be an object')
            if method=='initialize':
                requested = params.get('protocolVersion')
                result = {'protocolVersion':requested if requested in VERSIONS else '2025-06-18',
                          'serverInfo':{'name':'codex-footprint','version':__version__},
                          'capabilities':{'tools':{'listChanged':False}},
                          'instructions':'Independent developer plugin for Codex. Observations are temporal correlations, not proven process ownership. Never interpret findings as authorization to delete.'}
                initialized = True
            elif method=='ping': result = {}
            elif not initialized:
                raise ValueError('Initialize before using tools')
            elif method=='tools/list': result = {'tools':tools()}
            elif method=='tools/call':
                name,args = params.get('name'),params.get('arguments',{})
                validate_arguments(name,args)
                try:
                    value = operate(SPECS[name][0],args)
                    result = {'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],
                              'structuredContent':value,'isError':False}
                except (ValueError,OSError,sqlite3.Error) as exc:
                    result = {'content':[{'type':'text','text':str(exc)}],'isError':True}
            else:
                emit({'jsonrpc':'2.0','id':identifier,'error':{'code':-32601,'message':'Method not found'}})
                continue
            emit({'jsonrpc':'2.0','id':identifier,'result':result})
        except (ValueError,TypeError) as exc:
            emit({'jsonrpc':'2.0','id':identifier,'error':{'code':-32602,'message':str(exc)}})
        except Exception:
            # Keep stdout valid protocol JSON; unexpected tracebacks never leak into it.
            print('codex-footprint: unexpected MCP error',file=sys.stderr)
            emit({'jsonrpc':'2.0','id':identifier,'error':{'code':-32603,'message':'Internal error'}})


def emit(value):
    print(json.dumps(value,ensure_ascii=False),flush=True)
