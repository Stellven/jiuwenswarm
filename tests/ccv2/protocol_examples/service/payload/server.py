"""Synthetic deployable product. It does not implement CC's tool stdin protocol."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from urllib.parse import parse_qs, urlparse

FACTOR = 1


class API(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlparse(self.path)
        if request.path == '/health':
            result, status = {'ready': True}, 200
        elif request.path == '/compute':
            try:
                value = float(parse_qs(request.query)['x'][0])
                if not math.isfinite(value * FACTOR):
                    raise ValueError('Finite result required')
                result, status = {'value': value * FACTOR, 'factor': FACTOR}, 200
            except (KeyError, ValueError):
                result, status = {'error': 'Supply numeric x'}, 400
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
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), API).serve_forever()
