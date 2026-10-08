"""Heavy hitters and evidence-based explanations over retained snapshots."""
from __future__ import annotations

ATTRIBUTION = {'level':'temporal_correlation','process_verified':False,
               'caveat':'Growth occurred in observed hook windows. Concurrent writers and background descendants are not uniquely attributable to Codex.'}


def flatten(snapshot):
    if snapshot is None:
        return {}
    return {path:dict(bucket,root_id=root['id']) for root in snapshot['roots'] for path,bucket in root['buckets'].items()}


def total(snapshot):
    return sum(root['allocated_bytes'] for root in snapshot['roots'])


def delta(before, after):
    if before is None or not before['complete'] or not after['complete']:
        return None
    return total(after)-total(before)


def report(snapshots, thresholds, session_id=None, turn_id=None, limit=20):
    if turn_id and not session_id:
        raise ValueError('turn_id requires session_id')
    selected = [s for s in snapshots if (not session_id or s['event']['session_id']==session_id)
                and (not turn_id or s['event']['turn_id']==turn_id)]
    if not selected:
        return {'schema_version':1,'baseline_available':False,'growth_bytes':None,'heavy_hitters':[],
                'coverage':{'complete':False,'reason':'No retained snapshots for this scope/task'},
                'attribution':ATTRIBUTION,'tool_windows':[]}
    current = selected[-1]
    if session_id:
        baseline_events = {'UserPromptSubmit'} if turn_id else {'SessionStart'}
        baseline = next((s for s in selected if s['event']['event'] in baseline_events),None)
    else:
        baseline = selected[0] if len(selected)>1 else None
    if baseline and baseline['id']==current['id']:
        baseline = None
    comparable = baseline is not None and baseline['complete'] and current['complete']
    first = flatten(baseline)
    last = flatten(current)
    elapsed = current['created_at']-baseline['created_at'] if baseline else 0
    streaks = {}
    history_maps = [(snapshot, flatten(snapshot)) for snapshot in selected]
    for (a, a_map), (b, b_map) in zip(history_maps, history_maps[1:]):
        if not (a['complete'] and b['complete']):
            streaks.clear()
            continue
        for path in set(a_map)|set(b_map):
            change = b_map.get(path, {}).get('allocated_bytes', 0)-a_map.get(path, {}).get('allocated_bytes', 0)
            if change > 0: streaks[path] = streaks.get(path, 0)+1
            elif change < 0: streaks[path] = 0
    candidates = []
    for path in set(first)|set(last):
        item = last.get(path,{'path':path,'root_id':first[path]['root_id'],'allocated_bytes':0,'logical_bytes':0,'file_count':0}) if path not in last else last[path]
        previous = first.get(path,{'allocated_bytes':0})
        growth = item['allocated_bytes']-previous['allocated_bytes'] if comparable else None
        rate = growth/elapsed if growth is not None and elapsed>0 else None
        signals = []
        if item['allocated_bytes'] >= thresholds['large_bytes']:
            signals.append('large_occupancy')
        if growth is not None and growth >= thresholds['growth_bytes']:
            signals.append('large_growth')
        if rate is not None and growth>0 and rate >= thresholds['rapid_bytes_per_second']:
            signals.append('rapid_growth')
        if item['file_count'] >= thresholds['many_files']:
            signals.append('many_files')
        streak = streaks.get(path, 0)
        if streak >= thresholds['sustained_intervals']:
            signals.append('sustained_growth')
        if signals:
            candidates.append(dict(item,growth_bytes=growth,bytes_per_second=rate,signals=signals,
                                   historical_bytes=previous['allocated_bytes'] if baseline else item['allocated_bytes'],
                                   sustained_positive_intervals=streak, occupancy_is_lower_bound=not current['complete']))
    candidates.sort(key=lambda r:(max(r['growth_bytes'] or 0,0),r['allocated_bytes'],r['file_count']),reverse=True)
    windows = []
    for end in selected:
        e = end['event']
        if e['event']!='PostToolUse' or not e['tool_use_id']:
            continue
        starts = [s for s in selected if s['id']<end['id'] and s['event']['event']=='PreToolUse'
                  and s['event']['tool_use_id']==e['tool_use_id'] and s['event']['session_id']==e['session_id']
                  and s['event']['turn_id']==e['turn_id']]
        start = starts[-1] if starts else None
        windows.append({'session_id':e['session_id'],'turn_id':e['turn_id'],'tool_use_id':e['tool_use_id'],
                        'tool_name':e['tool_name'],'command_family':e['command_family'],
                        'before_snapshot_id':start['id'] if start else None,'after_snapshot_id':end['id'],
                        'growth_bytes':delta(start,end), 'attribution':'temporal_correlation',
                        'overlap_possible':True})
    return {'schema_version':1,'scope':current['scope'],'baseline_available':comparable,
            'baseline_snapshot_id':baseline['id'] if baseline else None,'latest_snapshot_id':current['id'],
            'observed_at':current['created_at'],'elapsed_seconds':elapsed,
            'allocated_bytes':total(current),'growth_bytes':delta(baseline,current),
            'coverage':{'complete':current['complete'],'baseline_complete':baseline['complete'] if baseline else None,
                        'roots':[{'id':r['id'],'status':r['status'],'complete':r['complete'],'errors':r['errors']} for r in current['roots']]},
            'accounting':current['accounting'],'consistency':current['consistency'],
            'heavy_hitters':candidates[:limit],'total_heavy_hitters':len(candidates),
            'top_files':[item for root in current['roots'] for item in root['top_files']],
            'attribution':ATTRIBUTION,'tool_windows':windows[-50:],
            'history_note':'Only retained snapshots with the same configured scope are comparable; tool windows may overlap and must not be added together.'}


def explain(result, path=None):
    hitters = result['heavy_hitters']
    if path:
        hitters = [r for r in hitters if r['path']==path]
    return {'schema_version':1,'matched':bool(hitters),'findings':hitters,
            'evidence':{'baseline_snapshot_id':result.get('baseline_snapshot_id'),
                        'latest_snapshot_id':result.get('latest_snapshot_id'),'coverage':result['coverage']},
            'attribution':ATTRIBUTION,
            'interpretation':'Signals describe observed occupancy and growth, not garbage, verified ownership, inactivity, or safe deletability.'}


def cleanup_plan(result):
    items = []
    for hitter in result['heavy_hitters']:
        items.append({'path':hitter['path'],'observed_allocated_bytes':hitter['allocated_bytes'],
                      'signals':hitter['signals'],'action':'review_with_owner_tool',
                      'steps':['Verify the directory owner and whether any build/task/process is using it.',
                               'Check whether it contains source, deliverables, shared caches or irreplaceable data.',
                               'If disposal is wanted, choose the owning tool\'s supported management workflow and obtain explicit user authorization.'],
                      'estimated_reclaim_bytes':None,'safe_to_delete':False})
    return {'schema_version':1,'mode':'recommend','execution_supported':False,'items':items,
            'evidence_snapshot_id':result.get('latest_snapshot_id'),'coverage':result['coverage'],
            'note':'No deletion, shell commands, process termination, or reclaim promise. File blocks are not physical free-space recovery on APFS/clones/hardlinks.'}
