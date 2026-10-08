"""Seven-day minute history; bounded chart payload preserving bucket extrema."""
import json
import time

RANGES={'1h':3600,'24h':86400,'7d':7*86400}

def read(store,device,window='24h'):
    if window not in RANGES:raise ValueError('Unsupported chart range')
    now=time.time();meta={'requested_range':window,'requested_from':now-RANGES[window],'requested_to':now,'samples':0,'resolution_seconds':60,'available_since':None}
    if not store.db or device is None:return [],meta
    if store.db.execute("SELECT 1 FROM sqlite_master WHERE name='volume_minutes'").fetchone():
        rows=[json.loads(p) for (p,) in store.db.execute('SELECT payload FROM volume_minutes WHERE device=? AND bucket>=? AND ts<=? ORDER BY bucket',(device,int((now-RANGES[window])//60),now))]
        first=store.db.execute('SELECT ts FROM volume_minutes WHERE device=? ORDER BY bucket LIMIT 1',(device,)).fetchone()
        meta['available_since']=first[0] if first else None
    else:
        rows=[json.loads(p) for (p,) in store.db.execute('SELECT payload FROM volume_history WHERE ts>=? AND ts<=? ORDER BY id',(now-RANGES[window],now))]
        rows=[r for r in rows if r.get('device')==device]
        meta['available_since']=rows[0]['sampled_at'] if rows else None
    rows=[r for r in rows if isinstance(r.get('available_bytes'),(int,float)) and meta['requested_from']<=r['sampled_at']<=now]
    meta['samples']=len(rows)
    if len(rows)<=720:return rows,meta
    groups={};width=max(1,(rows[-1]['sampled_at']-rows[0]['sampled_at'])/360)
    for row in rows:groups.setdefault(int((row['sampled_at']-rows[0]['sampled_at'])/width),[]).append(row)
    selected={rows[0]['sampled_at']:rows[0],rows[-1]['sampled_at']:rows[-1]}
    for group in groups.values():
        for row in (min(group,key=lambda r:r['available_bytes']),max(group,key=lambda r:r['available_bytes'])):selected[row['sampled_at']]=row
    return sorted(selected.values(),key=lambda r:r['sampled_at']),meta
