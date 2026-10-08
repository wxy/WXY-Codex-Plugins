from __future__ import annotations
from contextlib import contextmanager
import json
import os
import sqlite3
import time

from .observer import observe


class Store:
    def __init__(self, config):
        self.config = config
        data = config['data_dir']
        data.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = data / 'footprint.sqlite3'
        self.db = sqlite3.connect(self.path, timeout=3)
        os.chmod(self.path,0o600)
        # Rollback journaling permits truly read-only reopen with macOS system SQLite.
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('PRAGMA busy_timeout=3000')
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0,1):
            self.db.close()
            raise ValueError('Unsupported history schema version')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, created_at REAL NOT NULL, scope TEXT NOT NULL,
              session_id TEXT, turn_id TEXT, tool_use_id TEXT, event TEXT NOT NULL,
              tool_name TEXT, command_family TEXT);
            CREATE TABLE IF NOT EXISTS snapshots (
              id INTEGER PRIMARY KEY, event_id INTEGER REFERENCES events(id), scope TEXT NOT NULL,
              payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS events_task ON events(session_id,turn_id);
            CREATE INDEX IF NOT EXISTS snapshots_scope ON snapshots(scope,id);
            PRAGMA user_version=1;
        ''')
        self.db.commit()

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def capture(self, event, scan=True):
        with self.transaction():
            cursor = self.db.execute('INSERT INTO events(created_at,scope,session_id,turn_id,tool_use_id,event,tool_name,command_family) VALUES(?,?,?,?,?,?,?,?)',
                       (time.time(),self.config['scope'],event.get('session_id'),event.get('turn_id'),
                        event.get('tool_use_id'),event['event'],event.get('tool_name'),event.get('command_family')))
            event_id = cursor.lastrowid
            snapshot = None
            if scan:
                snapshot = observe(self.config)
                cursor = self.db.execute('INSERT INTO snapshots(event_id,scope,payload) VALUES(?,?,?)',
                              (event_id,self.config['scope'],json.dumps(snapshot)))
                snapshot['id'] = cursor.lastrowid
            retention = self.config['retention']
            self.db.execute('DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT ?)',
                            (retention['max_snapshots'],))
            # Keep event rows referenced by a retained snapshot, within the max of both limits.
            self.db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?) AND id NOT IN (SELECT event_id FROM snapshots)',
                            (retention['max_events'],))
        return snapshot

    def snapshots(self):
        query = '''SELECT s.id,s.payload,e.created_at,e.session_id,e.turn_id,e.tool_use_id,e.event,e.tool_name,e.command_family
                   FROM snapshots s JOIN events e ON e.id=s.event_id WHERE s.scope=? ORDER BY s.id'''
        rows = []
        for sid,payload,at,session,turn,tool,event,name,family in self.db.execute(query,(self.config['scope'],)):
            item = json.loads(payload)
            item['id'] = sid
            item['event'] = {'created_at':at,'session_id':session,'turn_id':turn,'tool_use_id':tool,
                             'event':event,'tool_name':name,'command_family':family}
            rows.append(item)
        return rows

    def status(self):
        return {'snapshot_count':self.db.execute('SELECT count(*) FROM snapshots').fetchone()[0],
                'event_count':self.db.execute('SELECT count(*) FROM events').fetchone()[0],
                'integrity':self.db.execute('PRAGMA quick_check').fetchone()[0],
                'history_bytes':sum(p.stat().st_size for p in self.path.parent.glob('footprint.sqlite3*') if p.is_file())}
