"""Separate global schema: preserves the original footprint.sqlite3 unchanged."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid


class GlobalStore:
    def __init__(self,data,writable=False):
        self.path=Path(data)/'global.sqlite3'; self.db=None
        if not writable and not self.path.exists(): return
        if writable:
            self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if not self.path.exists():
                temporary=self.path.with_name('.global-init-'+uuid.uuid4().hex)
                initial=sqlite3.connect(temporary,timeout=3)
                try:
                    os.chmod(temporary,0o600)
                    initial.executescript('''
                CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,ts REAL NOT NULL,session TEXT,cwd TEXT,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS inventory(path TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY,path TEXT NOT NULL,ts REAL NOT NULL,payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS observations_root ON observations(path,id);
                CREATE TABLE IF NOT EXISTS volumes(path TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS volume_history(id INTEGER PRIMARY KEY,ts REAL NOT NULL,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY,fingerprint TEXT NOT NULL,ts REAL NOT NULL,acknowledged INTEGER NOT NULL DEFAULT 0,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS history_runs(id INTEGER PRIMARY KEY,ts REAL NOT NULL,payload TEXT NOT NULL);
                PRAGMA user_version=1;
                    ''');initial.commit();initial.close()
                    # Readers must never observe an empty/partially initialized database.
                    try:os.link(temporary,self.path)
                    except FileExistsError:pass
                finally:
                    initial.close();temporary.unlink(missing_ok=True)
            self.db=sqlite3.connect(self.path,timeout=3)
            if self.db.execute('PRAGMA user_version').fetchone()[0]!=1:self.close();raise ValueError('Unsupported global history schema')
        else:
            self.db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True,timeout=3)
            if self.db.execute('PRAGMA user_version').fetchone()[0]!=1: self.close(); raise ValueError('Unsupported global history schema')
    def close(self):
        if self.db: self.db.close(); self.db=None
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def payloads(self,table):
        if not self.db:return []
        if table not in {'inventory','volumes','history_runs'}:raise ValueError('Invalid query')
        suffix=' ORDER BY id DESC LIMIT 1' if table=='history_runs' else ''
        return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM '+table+suffix)]
    def count(self,table):
        if table not in {'events','observations','alerts','history_runs'}:raise ValueError('Invalid count')
        return self.db.execute('SELECT count(*) FROM '+table).fetchone()[0] if self.db else 0
    def alerts(self):
        if not self.db:return []
        return [dict(json.loads(p),id=i,acknowledged=bool(a)) for i,a,p in self.db.execute('SELECT id,acknowledged,payload FROM alerts ORDER BY id DESC LIMIT 100')]
    def prune(self,limit=500,event_limit=5000):
        for table in ('observations','volume_history','alerts','history_runs'):
            self.db.execute('DELETE FROM '+table+' WHERE id NOT IN (SELECT id FROM '+table+' ORDER BY id DESC LIMIT ?)',(limit,))
        self.db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY ts DESC LIMIT ?)',(event_limit,))
        self.db.commit()
