"""Seven-day minute history; bounded chart payload preserving bucket extrema."""
import json
import time
import sqlite3

RANGES={'1h':3600,'24h':86400,'7d':7*86400}

def read(store,device,window='24h',volume_path=None):
    if window not in RANGES:raise ValueError('Unsupported chart range')
    now=time.time();meta={'requested_range':window,'requested_from':now-RANGES[window],'requested_to':now,'samples':0,'resolution_seconds':60,'available_since':None}
    if not store.db or device is None:return [],meta
    selected_paths=volume_path if isinstance(volume_path,list) else [volume_path] if volume_path else []
    if store.db.execute("SELECT 1 FROM sqlite_master WHERE name='volume_minutes'").fetchone():
        # A boot/remount changes st_dev. The selected canonical mount and retained path aliases identify the series.
        lower=int((now-RANGES[window])//60)
        if selected_paths:
            marks=','.join('?' for _ in selected_paths)
            try:
                rows=[json.loads(p) for (p,) in store.db.execute("SELECT payload FROM volume_minutes WHERE json_extract(payload,'$.path') IN ("+marks+") AND bucket>=? AND ts<=? ORDER BY ts",(*selected_paths,lower,now))]
                first=store.db.execute("SELECT min(ts) FROM volume_minutes WHERE json_extract(payload,'$.path') IN ("+marks+")",selected_paths).fetchone()
            except sqlite3.OperationalError:
                # Older SQLite builds without JSON functions still have a bounded metadata fallback.
                rows=[json.loads(p) for (p,) in store.db.execute('SELECT payload FROM volume_minutes WHERE bucket>=? AND ts<=? ORDER BY ts',(lower,now))]
                rows=[r for r in rows if r.get('path') in selected_paths]
                first=(rows[0]['sampled_at'],) if rows else (None,)
        else:
            rows=[json.loads(p) for (p,) in store.db.execute('SELECT payload FROM volume_minutes WHERE device=? AND bucket>=? AND ts<=? ORDER BY ts',(device,lower,now))]
            first=store.db.execute('SELECT min(ts) FROM volume_minutes WHERE device=?',(device,)).fetchone()
        meta['available_since']=first[0] if first else None
    else:
        rows=[json.loads(p) for (p,) in store.db.execute('SELECT payload FROM volume_history WHERE ts>=? AND ts<=? ORDER BY id',(now-RANGES[window],now))]
        rows=[r for r in rows if r.get('path') in selected_paths] if volume_path else [r for r in rows if r.get('device')==device]
        meta['available_since']=rows[0]['sampled_at'] if rows else None
    rows=[r for r in rows if isinstance(r.get('available_bytes'),(int,float)) and meta['requested_from']<=r['sampled_at']<=now]
    # Device IDs can overlap in a minute during remount; retain the latest sample once.
    rows=list({int(r['sampled_at']//60):r for r in rows}.values())
    meta['samples']=len(rows)
    meta['gaps']=[{'from':a['sampled_at'],'to':b['sampled_at']} for a,b in zip(rows,rows[1:]) if b['sampled_at']-a['sampled_at']>300]
    if len(rows)<=720:return rows,meta
    groups={};width=max(1,(rows[-1]['sampled_at']-rows[0]['sampled_at'])/360)
    for row in rows:groups.setdefault(int((row['sampled_at']-rows[0]['sampled_at'])/width),[]).append(row)
    selected={rows[0]['sampled_at']:rows[0],rows[-1]['sampled_at']:rows[-1]}
    for group in groups.values():
        for row in (min(group,key=lambda r:r['available_bytes']),max(group,key=lambda r:r['available_bytes'])):selected[row['sampled_at']]=row
    return sorted(selected.values(),key=lambda r:r['sampled_at']),meta
