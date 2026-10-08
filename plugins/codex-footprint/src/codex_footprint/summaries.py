"""Daily derived metadata. Never traverses artifact or session directories."""
from __future__ import annotations
import datetime as dt
import json
import time

from .global_store import GlobalStore


def day_for(timestamp):
    return dt.datetime.fromtimestamp(timestamp).date().isoformat()


def compact(row):
    return {k: row.get(k) for k in ('path', 'measured_at', 'started_at', 'allocated_bytes',
            'file_count', 'complete', 'measurement_scope')}


def remember(store, row, previous=None):
    if not row.get('complete') or not row.get('measured_at'):
        return
    day = day_for(row['measured_at'])
    old = store.db.execute('SELECT first_payload,last_payload FROM daily_roots WHERE day=? AND path=?', (day, row['path'])).fetchone()
    value = compact(row)
    if old:
        first, last = map(json.loads, old)
        if value['measured_at'] < first['measured_at']:
            first = value
        if value['measured_at'] > last['measured_at']:
            last = value
    else:
        first = last = value
        if previous and previous.get('complete') and previous.get('measured_at') and day_for(previous['measured_at']) == day:
            first = compact(previous)
    store.db.execute('INSERT OR REPLACE INTO daily_roots VALUES(?,?,?,?)',
                     (day, row['path'], json.dumps(first), json.dumps(last)))


def generate(config, requested_day=None):
    now = time.time()
    day = requested_day or day_for(now)
    try:
        date = dt.date.fromisoformat(day)
    except (ValueError, TypeError):
        raise ValueError('day must be YYYY-MM-DD')
    if date.isoformat() != day or date > dt.datetime.now().date():
        raise ValueError('day must be a current or past YYYY-MM-DD date')
    start = dt.datetime.combine(date, dt.time.min).timestamp()
    end = dt.datetime.combine(date + dt.timedelta(days=1), dt.time.min).timestamp()
    with GlobalStore(config['data_dir'], True) as store:
        # Backfill only retained monitor metadata, including upgrades from 0.2.0.
        for (payload,) in store.db.execute('SELECT payload FROM observations ORDER BY id').fetchall():
            remember(store, json.loads(payload))
        roots = []
        for path, first_raw, last_raw in store.db.execute('SELECT path,first_payload,last_payload FROM daily_roots WHERE day=?', (day,)):
            first, last = json.loads(first_raw), json.loads(last_raw)
            comparable = (last['measured_at'] > first['measured_at'] and
                          first.get('measurement_scope') and first['measurement_scope'] == last.get('measurement_scope'))
            roots.append(dict(last, growth_bytes=last['allocated_bytes']-first['allocated_bytes'] if comparable else None,
                              baseline_at=first['measured_at'], latest_at=last['measured_at'],
                              observed_seconds=last['measured_at']-first['measured_at'],
                              finished=True, window_complete=bool(comparable and first['measured_at']<=start+60 and last['measured_at']>=end-60)))
        known = {r['path']: r for r in store.payloads('inventory')}
        included = {r['path'] for r in roots}
        pending = sorted(set(known) - included) if day == day_for(now) else []
        alerts = [a for a in store.alerts() if start <= a.get('latest_at', a.get('sampled_at', 0)) < end]
        result = {'schema_version': 3, 'report_id': 'daily-'+day, 'day': day, 'generated_at': now,
                  'window_start_at': start, 'window_end_at': min(end, now), 'timezone': time.tzname[-1],
                  'roots': sorted(roots, key=lambda r: r['allocated_bytes'], reverse=True),
                  'alerts': alerts, 'volumes': store.payloads('volumes'),
                  'coverage': {'full_day': bool(roots and now>=end and not pending and all(r['window_complete'] for r in roots)),
                               'measured_roots': len(roots), 'roots_without_complete_endpoints': pending,
                               'note': 'Growth covers each displayed observed interval. Missing/changed/partial endpoints stay unknown.'},
                  'root_totals_additive': False, 'full_disk_scan_triggered': False, 'history_analysis_triggered': False,
                  'attribution': 'Temporal/path associations; shared roots and session totals must not be added.'}
        store.db.execute('INSERT OR REPLACE INTO daily_reports VALUES(?,?)', (day, json.dumps(result)))
        cutoff = (dt.datetime.now().date()-dt.timedelta(days=90)).isoformat()
        store.db.execute('DELETE FROM daily_roots WHERE day<?', (cutoff,))
        store.db.execute('DELETE FROM daily_reports WHERE day<?', (cutoff,))
        store.db.commit()
        return result


def due(config):
    now = dt.datetime.now()
    if now.hour < 21:
        return
    day = now.date().isoformat()
    due_at = now.replace(hour=21, minute=0, second=0, microsecond=0).timestamp()
    with GlobalStore(config['data_dir']) as store:
        exists = store.db and store.db.execute("SELECT 1 FROM sqlite_master WHERE name='daily_reports'").fetchone()
        row = store.db.execute('SELECT payload FROM daily_reports WHERE day=?', (day,)).fetchone() if exists else None
    if not row or json.loads(row[0])['generated_at'] < due_at:
        generate(config, day)
