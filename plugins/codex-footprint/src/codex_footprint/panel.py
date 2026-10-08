"""Local read-only dashboard; fixed routes, no filesystem investigation."""
from __future__ import annotations
import hashlib
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit

from .global_store import GlobalStore


def snapshot(config):
    from .monitor import status
    result = status(config)
    value = {k: result.get(k) for k in ('worker', 'enabled', 'roots', 'volumes', 'coverage')}
    value.update(read_only=True, generated_at=time.time(), daily_reports=[], alerts=[], volume_history=[], latest_historical_analysis=None)
    with GlobalStore(config['data_dir']) as store:
        if not store.db:
            return value
        value['alerts'] = store.alerts()
        if store.db.execute("SELECT 1 FROM sqlite_master WHERE name='daily_reports'").fetchone():
            value['daily_reports'] = [json.loads(p) for (p,) in store.db.execute('SELECT payload FROM daily_reports ORDER BY day DESC LIMIT 14')]
        value['volume_history'] = list(reversed([json.loads(p) for (p,) in store.db.execute('SELECT payload FROM volume_history ORDER BY id DESC LIMIT 120')]))
        history = store.payloads('history_runs')
        if history:
            row = history[0]
            value['latest_historical_analysis'] = {k: row.get(k) for k in ('measured_at', 'items')}
            for item in value['latest_historical_analysis']['items'] or []:
                item.update(measured_at=row.get('measured_at'),finished=True)
            value['latest_historical_analysis']['coverage'] = {'complete': row.get('coverage', {}).get('complete', False)}
    for row in value['roots'] or []:
        if row.get('measured_at') and row.get('started_at'):
            row['duration_seconds'] = row['measured_at']-row['started_at']
    return value


class Panel:
    def __init__(self, config, port=8766):
        self.config = config
        self.info_path = config['data_dir'] / 'panel.json'
        owner = self
        html = (Path(__file__).resolve().parents[2] / 'assets/dashboard.html').read_bytes()
        code = re.search(rb'<script>(.*?)</script>', html, re.S).group(1)
        sha = base64.b64encode(hashlib.sha256(code).digest()).decode()
        csp = "default-src 'none'; script-src 'sha256-"+sha+"'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def send(self, code, body=b'', mime='text/plain; charset=utf-8'):
                self.send_response(code)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Security-Policy', csp)
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('X-Frame-Options', 'DENY')
                self.end_headers()
                self.wfile.write(body)
            def do_GET(self):
                expected = '127.0.0.1:'+str(owner.server.server_port)
                if self.headers.get('Host') != expected or self.headers.get('Origin') not in (None, 'http://'+expected):
                    return self.send(403)
                path = urlsplit(self.path).path
                if path == '/':
                    return self.send(200, html, 'text/html; charset=utf-8')
                if path == '/api/dashboard':
                    try:
                        from .monitor import load
                        body = json.dumps(snapshot(load()), ensure_ascii=False).encode()
                        return self.send(200, body, 'application/json; charset=utf-8')
                    except Exception:
                        return self.send(503, b'Monitor data is temporarily unavailable')
                self.send(404)
            def do_POST(self): self.send(405)
            def do_PUT(self): self.send(405)
            def do_DELETE(self): self.send(405)
            def do_PATCH(self): self.send(405)
        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.server.daemon_threads = True
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)+'/'
        from .monitor import atomic
        atomic(self.info_path, {'pid': os.getpid(), 'url': self.url, 'started_at': time.time(), 'read_only': True})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name='footprint-panel')
        self.thread.start()
    def close(self):
        self.server.shutdown()
        self.server.server_close()
        try:
            if json.loads(self.info_path.read_text()).get('pid') == os.getpid():
                self.info_path.unlink()
        except (OSError, ValueError):
            pass


def serve(config, port=8766):
    panel = Panel(config, port)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        panel.close()


def info(config):
    try:
        value = json.loads((config['data_dir'] / 'panel.json').read_text())
        os.kill(value['pid'], 0)
        return value
    except (OSError, ValueError, KeyError):
        return {'url': None, 'read_only': True}
