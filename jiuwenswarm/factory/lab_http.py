"""The lab mailbox over HTTP, so the factory and a lab agent can sit on different machines.

``serve`` exposes one mailbox directory (``lab_mailbox``). ``RemoteMailbox`` is a client
with the same methods as ``Mailbox``, so the lab manager and every lab agent work
unchanged against a local directory or a remote address. Typical use is between two
machines on a private network such as Tailscale, which encrypts the traffic::

    # on the machine that keeps the mailbox
    jiuwenswarm-factory lab-server --host 100.x.y.z --port 8790 \\
        --factory-token-file ~/.config/jiuwenswarm-factory/factory.token \\
        --lab-token-file ~/.config/jiuwenswarm-factory/lab.token
    # on the factory machine and on the lab machine
    export FACTORY_LAB_MAILBOX=http://100.x.y.z:8790 FACTORY_LAB_TOKEN=<its token>

Two tokens give the two sides different rights: only the factory token may open requests
and post factory messages; only the lab token may post lab messages. Either may read and
upload files. Files are content addressed: an upload is installed only when the whole
content hashes to the digest it was sent under, uploads and downloads resume after a
broken connection, and a client checks every download against its digest.

Routes (JSON unless noted)::

    GET  /v1/health
    GET  /v1/requests
    GET  /v1/requests/<id>/package          PUT (factory) writes it once
    GET  /v1/requests/<id>/messages         POST {type, body, files} posts one message
    HEAD /v1/requests/<id>/files/<sha256>   size, or 404 with X-Partial-Size
    GET  /v1/requests/<id>/files/<sha256>   bytes; honours Range
    PUT  /v1/requests/<id>/files/<sha256>?size=N&offset=K   one chunk of an upload
"""
from __future__ import annotations

import argparse
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import urllib.parse

from .lab_mailbox import (BLOCK, FORMAT, REQUEST_ID, SHA256, Mailbox, MailboxError, _stamp, canonical,
                          check_reference, fold, sha256_file)

CHUNK = 64 << 20            # upload chunk: one broken connection loses at most this much
MAX_JSON = 32 << 20         # package or message body
MAX_FILE = 256 << 30        # one attachment; an engine image is a few GiB
ROUTE = re.compile(r'^/v1/requests/(?P<id>[^/]+)(?:/(?P<what>package|messages|files)(?:/(?P<sha>[^/]+))?)?$')


def read_token(value=None, path=None, env='FACTORY_LAB_TOKEN'):
    """A token given directly, from a file, from ``$FACTORY_LAB_TOKEN`` or ``$FACTORY_LAB_TOKEN_FILE``."""
    if value:
        return value.strip()
    path = path or os.environ.get(env + '_FILE')
    if path:
        return Path(path).expanduser().read_text(encoding='utf-8').strip()
    return (os.environ.get(env) or '').strip() or None


# ---- server ----------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    server_version = 'factory-lab-mailbox/1'
    protocol_version = 'HTTP/1.1'

    # plumbing
    def log_message(self, fmt, *args):
        if self.server.log:
            self.server.log('%s %s' % (self.address_string(), fmt % args))

    def _send(self, status, value=None, headers=None):
        data = (canonical(value) + '\n').encode() if value is not None else b''
        self.send_response(status)
        if value is not None:
            self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        for key, item in (headers or {}).items():
            self.send_header(key, str(item))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def _error(self, status, message):
        self._send(status, dict(error=message))

    def _role(self):
        header = self.headers.get('Authorization', '')
        token = header[7:].strip() if header.startswith('Bearer ') else ''
        for role, expected in self.server.tokens.items():
            if expected and token and hmac.compare_digest(token.encode(), expected.encode()):
                return role
        return None

    def _json_body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > MAX_JSON:
            raise MailboxError('JSON body is missing or too large')
        return json.loads(self.rfile.read(length))

    def _drain(self):
        # Keep the connection usable after an early error on a request with a body.
        length = int(self.headers.get('Content-Length') or 0)
        if 0 < length <= MAX_JSON:
            self.rfile.read(length)
        else:
            self.close_connection = True

    def _route(self):
        parsed = urllib.parse.urlsplit(self.path)
        match = ROUTE.match(parsed.path)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        if match:
            request_id, what, sha = match.group('id'), match.group('what'), match.group('sha')
            if not REQUEST_ID.fullmatch(request_id) or (sha is not None and (what != 'files' or not SHA256.fullmatch(sha))):
                raise MailboxError('Invalid request id or file digest')
            return parsed.path, request_id, what, sha, query
        return parsed.path, None, None, None, query

    def _handle(self, method):
        role = self._role()
        if role is None:
            if method in {'PUT', 'POST'}:
                self._drain()
            return self._error(401, 'A valid bearer token is required')
        mailbox = self.server.mailbox
        try:
            path, request_id, what, sha, query = self._route()
            if path == '/v1/health' and method == 'GET':
                return self._send(200, dict(format=FORMAT, role=role))
            if path == '/v1/requests' and method == 'GET':
                return self._send(200, dict(requests=mailbox.requests()))
            if request_id is None or what is None:
                if method in {'PUT', 'POST'}:
                    self._drain()
                return self._error(404, 'No such route')
            if what == 'package':
                if method == 'GET':
                    return self._send(200, mailbox.package(request_id))
                if method == 'PUT':
                    if role != 'factory':
                        self._drain()
                        return self._error(403, 'Only the factory opens requests')
                    created = mailbox.open_request(request_id, self._json_body())
                    return self._send(201 if created else 200, dict(created=created))
            if what == 'messages' and sha is None:
                if method == 'GET':
                    good, bad = mailbox.messages(request_id)
                    return self._send(200, dict(messages=good, invalid=bad))
                if method == 'POST':
                    body = self._json_body()
                    if body.get('sender', role) != role:
                        return self._error(403, f'This token posts as {role}')
                    with self.server.post_lock:
                        message = mailbox.post(request_id, role, body.get('type'), body.get('body'), body.get('files') or [])
                    return self._send(201, message)
            if what == 'files' and sha is not None:
                if method in {'GET', 'HEAD'}:
                    return self._file(mailbox, request_id, sha, method)
                if method == 'PUT':
                    length = int(self.headers.get('Content-Length') or -1)
                    if length < 0 or length > CHUNK * 4:
                        self.close_connection = True
                        return self._error(411, 'Send each chunk with a Content-Length up to 256 MiB')
                    try:
                        size, offset = int(query['size']), int(query.get('offset', 0))
                    except (KeyError, ValueError):
                        self._drain()
                        return self._error(400, 'size and offset query parameters are required')
                    try:
                        with self.server.file_lock(request_id, sha):
                            have = mailbox.receive(request_id, sha, size, offset, self.rfile, length, self.server.max_file)
                    except MailboxError:
                        self.close_connection = True
                        raise
                    return self._send(200, dict(received=have, complete=have == size))
            if method in {'PUT', 'POST'}:
                self._drain()
            return self._error(405, 'Method not allowed here')
        except MailboxError as exc:
            status = 404 if 'Unknown lab request' in str(exc) else 409
            return self._error(status, str(exc))
        except (ValueError, TypeError) as exc:
            return self._error(400, str(exc)[:500])

    def _file(self, mailbox, request_id, sha, method):
        size = mailbox.file_size(request_id, sha)
        if size is None:
            return self._send(404, dict(error='No such file', partial=mailbox.partial_size(request_id, sha)),
                              {'X-Partial-Size': mailbox.partial_size(request_id, sha)})
        start, end = 0, size - 1
        ranged = self.headers.get('Range', '')
        match = re.fullmatch(r'bytes=(\d+)-(\d*)', ranged)
        if match:
            start = int(match.group(1))
            end = min(int(match.group(2)), size - 1) if match.group(2) else size - 1
            if start >= size and size:
                return self._send(416, dict(error='Range not satisfiable'), {'Content-Range': f'bytes */{size}'})
        length = max(0, end - start + 1)
        self.send_response(206 if match else 200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(length))
        self.send_header('Accept-Ranges', 'bytes')
        if match:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if method == 'HEAD':
            return None
        with (mailbox.root / 'requests' / request_id / 'files' / sha).open('rb') as stream:
            stream.seek(start)
            left = length
            while left:
                block = stream.read(min(BLOCK, left))
                if not block:
                    break
                self.wfile.write(block)
                left -= len(block)
        return None

    def do_GET(self):
        self._handle('GET')

    def do_HEAD(self):
        self._handle('HEAD')

    def do_PUT(self):
        self._handle('PUT')

    def do_POST(self):
        self._handle('POST')


class MailboxServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, mailbox, tokens, max_file=MAX_FILE, log=None):
        if not any(tokens.values()):
            raise ValueError('The lab mailbox server needs at least one token')
        self.mailbox, self.tokens, self.max_file, self.log = mailbox, tokens, max_file, log
        self.post_lock = threading.Lock()
        self._locks, self._locks_guard = {}, threading.Lock()
        super().__init__(address, _Handler)

    def file_lock(self, request_id, sha):
        with self._locks_guard:
            return self._locks.setdefault((request_id, sha), threading.Lock())


def serve(root, host='127.0.0.1', port=8790, factory_token=None, lab_token=None, log=print):
    server = MailboxServer((host, port), Mailbox(root), dict(factory=factory_token, lab=lab_token), log=log)
    if log:
        log(f'lab mailbox {Path(root).expanduser()} on http://{host}:{server.server_port}/v1')
    return server


# ---- client ----------------------------------------------------------------------------
class RemoteError(MailboxError):
    pass


class RemoteMailbox:
    """``Mailbox`` methods over HTTP. Downloads are cached and checked against their digest."""

    def __init__(self, url, token=None, cache=None, timeout_s=120.0, retries=5):
        parsed = urllib.parse.urlsplit(url.rstrip('/'))
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            raise ValueError('The lab mailbox address must be http(s)://host:port')
        self.url, self.scheme, self.host = url.rstrip('/'), parsed.scheme, parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        self.base = parsed.path.rstrip('/')
        self.token = read_token(token)
        if not self.token:
            raise ValueError('A lab mailbox address needs a token ($FACTORY_LAB_TOKEN or $FACTORY_LAB_TOKEN_FILE)')
        self.cache = Path(cache or os.environ.get('FACTORY_LAB_CACHE')
                          or Path(tempfile.gettempdir()) / 'factory-lab-cache').expanduser()
        self.timeout_s, self.retries = timeout_s, retries
        self.root = self.url  # where the mailbox is, for messages and logs
        self._verified = set()

    # plumbing
    def _connection(self):
        kind = http.client.HTTPSConnection if self.scheme == 'https' else http.client.HTTPConnection
        return kind(self.host, self.port, timeout=self.timeout_s)

    def _headers(self, extra=None):
        return {'Authorization': f'Bearer {self.token}', **(extra or {})}

    def _call(self, method, path, value=None, ok=(200, 201)):
        data = (canonical(value)).encode() if value is not None else None
        headers = self._headers({'Content-Type': 'application/json'} if data is not None else {})
        for attempt in range(self.retries):
            connection = self._connection()
            try:
                connection.request(method, self.base + path, body=data, headers=headers)
                response = connection.getresponse()
                body = response.read()
                if response.status in ok:
                    return json.loads(body) if body else None
                try:
                    message = json.loads(body).get('error') or body.decode()[:300]
                except ValueError:
                    message = body.decode(errors='replace')[:300]
                if response.status >= 500 and attempt + 1 < self.retries:
                    time.sleep(min(30, 2 ** attempt))
                    continue
                raise RemoteError(f'{method} {path}: {response.status} {message}')
            except (OSError, http.client.HTTPException) as exc:
                if attempt + 1 >= self.retries or method == 'POST':
                    raise RemoteError(f'{method} {path}: {type(exc).__name__}: {exc}') from None
                time.sleep(min(30, 2 ** attempt))
            finally:
                connection.close()
        raise RemoteError(f'{method} {path}: no response')

    # Mailbox interface
    def health(self):
        return self._call('GET', '/v1/health')

    def requests(self):
        return self._call('GET', '/v1/requests')['requests']

    def open_request(self, request_id, package):
        return self._call('PUT', f'/v1/requests/{request_id}/package', package)['created']

    def package(self, request_id):
        try:
            return self._call('GET', f'/v1/requests/{request_id}/package')
        except RemoteError as exc:
            if ': 404 ' in str(exc):
                raise MailboxError('Unknown lab request') from None
            raise

    def messages(self, request_id):
        result = self._call('GET', f'/v1/requests/{request_id}/messages')
        return result['messages'], result['invalid']

    def thread(self, request_id):
        return fold(request_id, *self.messages(request_id))

    def latest(self, request_id, kind):
        found = [m for m in self.messages(request_id)[0] if m['type'] == kind]
        return found[-1] if found else None

    def post(self, request_id, sender, kind, body=None, files=()):
        files = list(files)
        for reference in files:
            check_reference(reference)
        return self._call('POST', f'/v1/requests/{request_id}/messages',
                          dict(sender=sender, type=kind, body=body or {}, files=files))

    def _head(self, request_id, sha):
        connection = self._connection()
        try:
            connection.request('HEAD', f'{self.base}/v1/requests/{request_id}/files/{sha}', headers=self._headers())
            response = connection.getresponse()
            response.read()
            if response.status == 200:
                return int(response.getheader('Content-Length')), 0
            if response.status == 404:
                return None, int(response.getheader('X-Partial-Size') or 0)
            raise RemoteError(f'HEAD file: {response.status}')
        finally:
            connection.close()

    def file_size(self, request_id, sha256):
        return self._head(request_id, sha256)[0]

    def attach(self, request_id, source, name, media_type='application/octet-stream', progress=None):
        """Upload a file (resuming a partial upload) and return its file reference."""
        reference = dict(name=name, media_type=media_type)
        sha, size = sha256_file(source)
        reference.update(sha256=sha, size=size)
        check_reference(reference)
        failures = 0
        while True:
            try:
                complete, offset = self._head(request_id, sha)
                if complete is not None:
                    return reference
                with Path(source).open('rb') as stream:
                    stream.seek(offset)
                    while offset < size or size == 0:
                        length = min(CHUNK, size - offset)
                        connection = self._connection()
                        try:
                            connection.putrequest('PUT', f'{self.base}/v1/requests/{request_id}/files/{sha}?size={size}&offset={offset}')
                            for key, item in self._headers({'Content-Type': 'application/octet-stream',
                                                            'Content-Length': str(length)}).items():
                                connection.putheader(key, item)
                            connection.endheaders()
                            left = length
                            while left:
                                block = stream.read(min(BLOCK, left))
                                if not block:
                                    raise RemoteError('The file changed while uploading')
                                connection.send(block)
                                left -= len(block)
                            response = connection.getresponse()
                            body = json.loads(response.read() or b'{}')
                        finally:
                            connection.close()
                        if response.status != 200:
                            raise RemoteError(f'upload {name}: {response.status} {body.get("error")}')
                        offset = body['received']
                        if progress:
                            progress(name, offset, size)
                        if body.get('complete'):
                            return reference
                        stream.seek(offset)
            except (OSError, http.client.HTTPException, RemoteError) as exc:
                failures += 1
                if failures >= self.retries or (isinstance(exc, RemoteError) and ': 409 ' in str(exc)):
                    raise RemoteError(f'upload {name}: {exc}') from None
                time.sleep(min(30, 2 ** failures))

    def file_path(self, request_id, reference, progress=None):
        """Download an attachment into the local cache (resuming) and check its digest."""
        check_reference(reference)
        sha, size = reference['sha256'], reference['size']
        target = self.cache / request_id / sha
        if target.is_file() and target.stat().st_size == size:
            if _stamp(target) in self._verified or sha256_file(target)[0] == sha:
                self._verified.add(_stamp(target))
                return target
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f'.partial-{sha}')
        failures = 0
        while True:
            have = partial.stat().st_size if partial.is_file() else 0
            if have > size:
                partial.unlink()
                have = 0
            try:
                if have < size:
                    connection = self._connection()
                    try:
                        connection.request('GET', f'{self.base}/v1/requests/{request_id}/files/{sha}',
                                           headers=self._headers({'Range': f'bytes={have}-'} if have else {}))
                        response = connection.getresponse()
                        if response.status == 404:
                            response.read()
                            raise MailboxError(f'Attachment {reference["name"]!r} is missing')
                        if response.status not in (200, 206):
                            raise RemoteError(f'download {reference["name"]}: {response.status}')
                        mode = 'ab' if response.status == 206 else 'wb'
                        with partial.open(mode) as output:
                            for block in iter(lambda: response.read(BLOCK), b''):
                                output.write(block)
                                if progress:
                                    progress(reference['name'], output.tell(), size)
                    finally:
                        connection.close()
                elif not partial.exists():
                    partial.write_bytes(b'')
                digest, got = sha256_file(partial)
                if got != size or digest != sha:
                    partial.unlink(missing_ok=True)
                    raise MailboxError(f'Attachment {reference["name"]!r} differs from its digest')
                os.replace(partial, target)
                self._verified.add(_stamp(target))
                return target
            except (OSError, http.client.HTTPException, RemoteError) as exc:
                failures += 1
                if failures >= self.retries:
                    raise RemoteError(f'download {reference["name"]}: {exc}') from None
                time.sleep(min(30, 2 ** failures))


# ---- command line ----------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(prog='lab-server', description='Serve a lab mailbox over HTTP.')
    parser.add_argument('--mailbox', help='mailbox directory (default: $FACTORY_LAB_MAILBOX or $FACTORY_HOME/lab-mailbox)')
    parser.add_argument('--home', help='factory home, for the default mailbox directory')
    parser.add_argument('--host', default='127.0.0.1', help='address to listen on, for example the Tailscale address')
    parser.add_argument('--port', type=int, default=int(os.environ.get('FACTORY_LAB_PORT', '8790')))
    parser.add_argument('--factory-token-file', help='token that may open requests and post factory messages')
    parser.add_argument('--lab-token-file', help='token that may post lab messages')
    parser.add_argument('--max-file-gib', type=float, default=MAX_FILE / (1 << 30))
    args = parser.parse_args(argv)
    from .lab_mailbox import default_root
    root = args.mailbox or os.environ.get('FACTORY_LAB_MAILBOX') or default_root(args.home)
    if str(root).startswith(('http://', 'https://')):
        raise SystemExit('lab-server serves a directory; --mailbox is a path here')
    tokens = dict(factory=read_token(path=args.factory_token_file, env='FACTORY_LAB_FACTORY_TOKEN'),
                  lab=read_token(path=args.lab_token_file, env='FACTORY_LAB_LAB_TOKEN'))
    if not any(tokens.values()):
        raise SystemExit('Give --factory-token-file and --lab-token-file (or $FACTORY_LAB_FACTORY_TOKEN/$FACTORY_LAB_LAB_TOKEN)')
    if tokens['factory'] and tokens['factory'] == tokens['lab']:
        raise SystemExit('The factory and lab tokens must differ')
    Path(root).expanduser().mkdir(parents=True, exist_ok=True)
    server = MailboxServer((args.host, args.port), Mailbox(root), tokens, int(args.max_file_gib * (1 << 30)),
                           log=lambda line: print(line, file=sys.stderr, flush=True))
    print(json.dumps(dict(mailbox=str(Path(root).expanduser()), url=f'http://{args.host}:{server.server_port}',
                          roles=[r for r, t in tokens.items() if t])), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

