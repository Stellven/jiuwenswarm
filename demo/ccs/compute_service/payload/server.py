"""Synthetic HTTP computation, independent of the CC tool stdin protocol."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import platform
from urllib.parse import parse_qs, urlparse

FACTOR = 2


def runtime():
    release = None
    path = Path('/etc/os-release')
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('PRETTY_NAME='):
                release = line.split('=', 1)[1].strip('"\'')
                break
    return {'platform': platform.platform(), 'python': platform.python_version(), 'os_release': release}


class API(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlparse(self.path)
        if request.path == '/health':
            result, status = {'status': 'ok'}, 200
        elif request.path == '/compute':
            try:
                value = float(parse_qs(request.query)['x'][0]) * FACTOR
                if not math.isfinite(value):
                    raise ValueError('Finite result required')
                result, status = {'value': value, 'factor': FACTOR, 'runtime': runtime()}, 200
            except (KeyError, ValueError, OverflowError):
                result, status = {'error': 'Supply finite numeric x'}, 400
        else:
            result, status = {'error': 'Unknown endpoint'}, 404
        body = json.dumps(result, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), API).serve_forever()
