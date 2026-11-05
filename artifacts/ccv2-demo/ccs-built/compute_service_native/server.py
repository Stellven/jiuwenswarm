"""Synthetic multiplication HTTP service. Performs no model inference."""

import argparse
import json
import math
import platform
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def runtime_metadata():
    release = None
    try:
        for line in Path('/etc/os-release').read_text(encoding='utf-8').splitlines():
            if line.startswith('PRETTY_NAME='):
                release = line.split('=', 1)[1].strip().strip('\"').strip("'")
                break
    except OSError:
        pass
    return {'platform': platform.platform(), 'python': platform.python_version(),
            'os_release': release}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, body):
        data = json.dumps(body, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/health':
            self.send_json(200, {'status': 'ok'})
        elif url.path == '/compute':
            try:
                query = parse_qs(url.query, keep_blank_values=True)
                if len(query.get('x', [])) != 1:
                    raise ValueError('one x required')
                x = float(query['x'][0])
                value = x * 2
                if not math.isfinite(x) or not math.isfinite(value):
                    raise ValueError('input and result must be finite')
            except (ValueError, OverflowError):
                self.send_json(400, {'error': 'x must be one finite number with a finite doubled result'})
                return
            self.send_json(200, {'value': value, 'factor': 2, 'runtime': runtime_metadata()})
        else:
            self.send_json(404, {'error': 'not found'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        server.serve_forever()
