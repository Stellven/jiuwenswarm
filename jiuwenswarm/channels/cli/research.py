"""Native ordinary-client research subcommands; no local research engine."""
from __future__ import annotations

import argparse
import asyncio
import getpass
import hashlib
import json
import os
import re
import stat
import sys
import time
import uuid
import warnings
import zipfile
import codecs
from contextlib import ExitStack
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit, urlunsplit, quote

import httpx


SESSION_SCHEMA = 'ai4r-research-cli-session:1'
DEFAULT_FIELDS = {'account_id', 'workspace_id', 'configuration_ref', 'plan_source', 'profile_id'}


def _native_origin(origin):
    if not isinstance(origin, str) or not origin or any(c.isspace() or ord(c) < 32 for c in origin) or '\\' in origin:
        raise ValueError('one native app origin is required')
    parsed = urlsplit(origin)
    if (parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password
            or parsed.path not in {'', '/'} or parsed.query or parsed.fragment or not parsed.hostname):
        raise ValueError('one native app origin is required')
    _ = parsed.port  # Refuse malformed ports before constructing a transport.
    return urlunsplit((parsed.scheme, parsed.netloc, '', '', ''))


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate session field')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid session number')))
    except RecursionError:
        raise ValueError('session input is too deeply nested') from None


def _private_file(info):
    if (os.name != 'posix' or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.geteuid() or info.st_nlink != 1):
        raise ValueError('session credentials require a current-owner0600 regular file')


def _read_private(path, maximum=32768):
    if os.name != 'posix':
        raise ValueError('protected session file custody is unavailable on this platform')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        _private_file(before)
        if before.st_size > maximum:
            raise ValueError('protected session input is too large')
        raw = handle.read(maximum + 1)
        after = os.fstat(handle.fileno())
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or len(raw) != before.st_size):
            raise ValueError('protected session input changed during read')
        return raw


def _session_value(value):
    if not isinstance(value, dict) or set(value) != {'token', 'defaults'}:
        raise ValueError('invalid bootstrap response')
    token, defaults = value['token'], value['defaults']
    if not isinstance(token, str) or re.fullmatch(r'[A-Za-z0-9_-]{20,256}', token) is None:
        raise ValueError('invalid session credential')
    if not isinstance(defaults, dict) or set(defaults) != DEFAULT_FIELDS:
        raise ValueError('invalid server defaults')
    for name in ('account_id', 'workspace_id', 'profile_id'):
        entry = defaults[name]
        if entry is None and name != 'account_id':
            continue
        if not isinstance(entry, str) or not entry or any(ord(c) < 32 for c in entry):
            raise ValueError('invalid server identity')
    ref = defaults['configuration_ref']
    if ref is not None and (not isinstance(ref, dict) or set(ref) != {'id', 'sha256'}
            or not isinstance(ref['id'], str) or not ref['id'] or not isinstance(ref['sha256'], str)
            or re.fullmatch(r'[a-f0-9]{64}', ref['sha256']) is None):
        raise ValueError('invalid server configuration Ref')
    if defaults['plan_source'] not in (None, 'static', 'planned'):
        raise ValueError('invalid server plan selection')
    return value


def _load_session(path):
    value = _strict_json(_read_private(path))
    if not isinstance(value, dict) or set(value) != {'schema', 'origin', 'token', 'defaults'} or value['schema'] != SESSION_SCHEMA:
        raise ValueError('invalid local session format')
    origin = _native_origin(value['origin'])
    if origin != value['origin']:
        raise ValueError('noncanonical local session origin')
    _session_value({key: value[key] for key in ('token', 'defaults')})
    return value


def _connect_session(args):
    origin = _native_origin(args.origin or os.getenv('JIUWENSWARM_M1_ORIGIN'))
    if args.session_file is None or args.token_file is not None or os.name != 'posix':
        raise ValueError('a new protected session file is required')
    if args.bootstrap_file:
        offered = _read_private(args.bootstrap_file, 4096).decode('ascii').rstrip('\r\n')
    elif sys.stdin.isatty():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                offered = getpass.getpass('One-use bootstrap URL: ')
        except getpass.GetPassWarning:
            raise ValueError('non-echoed bootstrap input is unavailable; use a private bootstrap file') from None
    else:
        offered = sys.stdin.readline(4097).rstrip('\r\n')
    prefix = origin + '/#research_bootstrap='
    if (not offered.startswith(prefix) or len(offered) > 4096
            or re.fullmatch(r'[A-Za-z0-9_-]{20,256}', offered[len(prefix):]) is None):
        raise ValueError('an exact same-origin one-use bootstrap URL is required')
    challenge = offered[len(prefix):]
    # Reserve the final private identity before consuming a one-use challenge.
    fd = os.open(args.session_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    created = os.fstat(fd)
    saved = False
    try:
        os.fchmod(fd, 0o600)
        _private_file(os.fstat(fd))
        with httpx.Client(base_url=origin, timeout=30, follow_redirects=False, trust_env=False) as connection:
            with connection.stream('POST', '/auth/research/bootstrap', headers={'Origin': origin}, json={'challenge': challenge}) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError('unsupported bootstrap response')
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    body.extend(chunk)
                    if len(body) > 32768:
                        raise ValueError('bootstrap response is too large')
                grant = _session_value(_strict_json(body))
        session = {'schema': SESSION_SCHEMA, 'origin': origin, **grant}
        raw = (json.dumps(session, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n').encode('ascii')
        with os.fdopen(fd, 'wb') as handle:
            fd = None
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        saved = True
    finally:
        if fd is not None:
            os.close(fd)
        if not saved:
            try:
                actual = args.session_file.lstat()
                if (actual.st_dev, actual.st_ino) == (created.st_dev, created.st_ino):
                    args.session_file.unlink()
            except FileNotFoundError:
                pass


class _PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # A mistakenly supplied bootstrap URL must not be echoed by argparse.
        super().error('invalid research options; use --help for supported arguments')


def completion_exit_code(value: dict) -> int:
    return 1 if value.get('status') in {'halted', 'partial', 'paused'} else 0


def _segment(value):
    if not isinstance(value, str) or not value or value in {'.', '..'}:
        raise ValueError('one opaque resource identity is required')
    return quote(value, safe='')


def _contract(kind, value):
    from jiuwenswarm.research.contracts import ResearchError, validate
    try:
        validate(kind, value)
    except ResearchError:
        raise ValueError('unsupported research input or response contract') from None
    return value


def _upload_scope(value):
    if (not isinstance(value, str) or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', value) is None
            or value in {'.', '..'}):
        raise ValueError('an initialized workspace or explicit upload scope is required')
    return value


def _local_file(stack, path):
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise ValueError('a readable regular input file is required')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    stream = stack.enter_context(os.fdopen(descriptor, 'rb'))
    actual = os.fstat(stream.fileno())
    if not stat.S_ISREG(actual.st_mode) or (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
        raise ValueError('local input changed before read')
    return stream


def _file_identity(stream):
    value = os.fstat(stream.fileno())
    return tuple(getattr(value, key) for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def _attachment(stack, kind, path):
    name = path.name
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name) is None:
        raise ValueError('attachment filename is unsupported')
    suffix = path.suffix.lower()
    if (kind == 'docs' and suffix not in {'.txt', '.md', '.pdf'}
            or kind == 'repo' and suffix != '.zip'):
        raise ValueError('attachment type is unsupported')
    stream = _local_file(stack, path)
    identity = _file_identity(stream)
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder('utf-8')('strict') if kind == 'docs' and suffix in {'.txt', '.md'} else None
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
        if decoder is not None:
            decoder.decode(chunk)
    if decoder is not None:
        decoder.decode(b'', final=True)
    if _file_identity(stream) != identity:
        raise ValueError('attachment changed during validation')
    stream.seek(0)
    if kind == 'repo':
        # Match upload-time archive confinement without extracting or changing
        # bytes. PDF extraction remains solely the protected server's job.
        try:
            with zipfile.ZipFile(stream) as archive:
                names = set()
                for entry in archive.infolist():
                    member = entry.filename
                    normalized = member.replace('\\', '/')
                    parts = PurePosixPath(normalized)
                    if (not member or parts.is_absolute() or PureWindowsPath(member).drive or '..' in parts.parts
                            or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1
                            or normalized in names or '\x00' in member):
                        raise ValueError('repository archive contains an unsupported member')
                    names.add(normalized)
        except (zipfile.BadZipFile, RuntimeError):
            raise ValueError('repository attachment requires a readable ZIP') from None
        stream.seek(0)
    return {'kind': kind, 'name': name, 'stream': stream, 'identity': identity,
            'content_sha256': digest.hexdigest(), 'size_bytes': identity[2]}


def _offered_uploads(values):
    uploads = []
    identities = set()
    for raw in values:
        value = _strict_json(raw)
        if isinstance(value, dict):
            _contract('Ref', value)
            identity = value['id']
        elif isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_.:-]{0,63}', value):
            identity = value
        else:
            raise ValueError('captured upload Ref or quoted upload ID required')
        if re.fullmatch(r'[a-z][a-z0-9_.:-]{0,63}', identity) is None:
            raise ValueError('captured upload identity is unsupported')
        if identity in identities:
            raise ValueError('duplicate uploaded input')
        identities.add(identity)
        uploads.append(value)
    return uploads


def _captured_upload(value, source, scope, account_id=None):
    _contract('client-upload', value)
    if (value['status'] != 'uploaded' or value['scope_id'] != scope or value['kind'] != source['kind']
            or value['filename'] != source['name'] or account_id is not None and value['user_id'] != account_id
            or value['resource_type'] != {'docs': 'reference_document', 'repo': 'project_asset', 'datasets': 'validation_data'}[source['kind']]
            or value['stored_path'] != '/'.join(('workspace', 'input', source['kind'], scope, source['name']))
            or (value['text_sha256'] is not None) != (source['kind'] == 'docs') or value['deleted_at'] is not None):
        raise ValueError('upload response belongs to another input or scope')
    return value['id']  # qualify_intake resolves this authenticated upload ID.


def _recovery(request_id, uploads, intake_ref, upload_unknown, *, interrupted=False, scope=None):
    value = {'status': 'interrupted' if interrupted else 'unavailable', 'request_id': request_id,
             'message': 'Research operation failed; inspect request, scope and readiness.'}
    if uploads:
        value['retained_upload_refs'] = uploads
    if scope is not None and (uploads or upload_unknown):
        value['upload_scope'] = scope
    if intake_ref is not None:
        value['qualified_intake_ref'] = intake_ref
    if upload_unknown:
        value['upload_delivery_unknown'] = True
        value['message'] = 'Upload delivery is uncertain; inspect uploads in this workspace before uploading again.'
    return value


class ResearchClient:
    def __init__(self, origin: str, token: str, *, transport=None, expected_instance=None):
        self.origin, self.token, self.expected_instance = _native_origin(origin), token, expected_instance
        self.client = httpx.Client(base_url=self.origin, headers={'Authorization': 'Bearer ' + token},
                                   transport=transport, timeout=30, follow_redirects=False, trust_env=False)

    def close(self):
        self.client.close()

    def request(self, method: str, path: str, **kwargs):
        if not path.startswith('/api/v1/') or path.startswith('//'):
            raise ValueError('unsupported or foreign research path')
        target = httpx.URL(self.origin).join(path)
        base = httpx.URL(self.origin)
        if (target.scheme, target.host, target.port) != (base.scheme, base.host, base.port) or not target.path.startswith('/api/v1/') or target.fragment:
            raise ValueError('unsupported normalized research path')
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def readiness(self):
        value = self.request('GET', '/api/v1/readiness')
        if not isinstance(value, dict) or value.get('client_contract_version') != '1.0.0' or (self.expected_instance and value.get('instance_id') != self.expected_instance):
            raise ValueError('native target or client contract mismatch')
        return value

    async def qualify(self, prompt: str, workspace_id: str, upload_refs=()):
        from websockets.asyncio.client import connect
        from websockets.exceptions import WebSocketException
        parsed = urlsplit(self.origin)
        url = urlunsplit(('wss' if parsed.scheme == 'https' else 'ws', parsed.netloc, '/ws', '', ''))
        request_id = 'intake:' + uuid.uuid4().hex
        try:
            async with connect(url, additional_headers={'Authorization': 'Bearer ' + self.token}) as ws:
                await ws.send(json.dumps({'type': 'req', 'id': request_id, 'method': 'chat.send',
                                         'params': {'content': prompt, 'workspace_id': workspace_id, 'upload_refs': list(upload_refs)}}))
                async with asyncio.timeout(30):
                    async for raw in ws:
                        value = json.loads(raw)
                        if not isinstance(value, dict):
                            raise ValueError('native research qualification response is unsupported')
                        if value.get('type') == 'res' and value.get('id') == request_id:
                            payload = value.get('payload')
                            if not value.get('ok') or not isinstance(payload, dict) or not payload.get('intake_ref'):
                                raise ValueError('native research intake was refused')
                            return payload['intake_ref']
        except WebSocketException:
            raise ValueError('native research qualification transport failed') from None
        raise ValueError('native qualification ended without an intake')

    def upload(self, source, scope):
        if _file_identity(source['stream']) != source['identity']:
            raise ValueError('attachment changed after validation')
        source['stream'].seek(0)
        source['upload_started'] = True
        return self.request('POST', '/api/v1/inputs/' + source['kind'],
                            files={'file': (source['name'], source['stream'])}, data={'scope_id': scope})

    def submit(self, submission):
        ready = self.readiness()
        if not ready.get('ready'):
            raise ValueError('native target is not ready')
        try:
            return self.request('POST', '/api/v1/runs', json=submission)
        except (httpx.TransportError, httpx.HTTPStatusError) as original:
            if isinstance(original, httpx.HTTPStatusError) and original.response.status_code < 500:
                raise
            # Reconciliation may establish delivery; POST is never retried here.
            try:
                found = self.request('GET', '/api/v1/runs', params={'client_request_id': submission['client_request_id']})
                if not isinstance(found, dict) or not found.get('run_id') or found.get('client_request_id') != submission['client_request_id']:
                    raise original
                return found
            except httpx.HTTPError:
                raise original

    def export_bytes(self, run_id, audience='researcher'):
        response = self.client.get('/api/v1/runs/' + _segment(run_id) + '/export',
                                   params={'audience': audience}, headers={'Accept': 'application/zip'})
        response.raise_for_status()
        if 'application/zip' not in response.headers.get('content-type', ''):
            raise ValueError('supported export representation is unavailable')
        return response.content


def build_parser():
    parser = _PrivateArgumentParser(prog='jiuwenswarm research')
    parser.add_argument('--origin')
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--session-file', type=Path, help='Use a protected session created by research connect')
    parser.add_argument('--expected-instance')
    commands = parser.add_subparsers(dest='operation', required=True)
    connect = commands.add_parser('connect', help='Save a one-use bootstrap session and server defaults')
    connect.add_argument('--origin', default=argparse.SUPPRESS)
    connect.add_argument('--session-file', type=Path, default=argparse.SUPPRESS)
    connect.add_argument('--bootstrap-file', type=Path, help='Read the one-use URL from a private0600 file; otherwise read stdin without echo')
    commands.add_parser('readiness'); commands.add_parser('doctor')
    submit = commands.add_parser('submit')
    submit.add_argument('--workspace'); submit.add_argument('--configuration-ref')
    source = submit.add_mutually_exclusive_group(required=True)
    source.add_argument('--prompt'); source.add_argument('--prompt-file', type=Path); source.add_argument('--intake-ref')
    submit.add_argument('--client-request-id', default=None); submit.add_argument('--plan-source', choices=['static', 'planned'])
    submit.add_argument('--interaction-mode', choices=['headless', 'interactive'], default='headless')
    submit.add_argument('--profile-id'); submit.add_argument('--wait', action='store_true')
    submit.add_argument('--upload-ref', action='append', default=[], help='Existing upload Ref JSON or JSON-quoted upload ID')
    submit.add_argument('--document', action='append', type=Path, default=[], help='Attach a TXT, Markdown or text-layer PDF file; repeatable')
    submit.add_argument('--repository', action='append', type=Path, default=[], help='Attach a project ZIP archive; repeatable')
    submit.add_argument('--dataset', action='append', type=Path, default=[], help='Attach a validation data file or baseline snapshot; repeatable')
    for name in ['status', 'export', 'cancel']:
        cmd = commands.add_parser(name); cmd.add_argument('run_id')
        if name == 'cancel': cmd.add_argument('--request-id', required=True)
        if name == 'export':
            cmd.add_argument('--audience', choices=['researcher', 'reviewer'], default='researcher')
            cmd.add_argument('--output', type=Path, help='Write the authorized original-byte ZIP to a new file')
    upload = commands.add_parser('upload'); upload.add_argument('kind', choices=['docs', 'repo', 'datasets']); upload.add_argument('file', type=Path); upload.add_argument('--scope', help='Defaults to the saved initialized workspace')
    uploads = commands.add_parser('uploads'); uploads.add_argument('--scope', help='Defaults to the saved initialized workspace')
    delete = commands.add_parser('delete-upload'); delete.add_argument('upload_id')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.operation == 'connect':
        try:
            _connect_session(args)
            print(json.dumps({'status': 'connected'}))
            return 0
        except KeyboardInterrupt:
            return 130
        except (httpx.HTTPError, OSError, ValueError, TimeoutError, EOFError):
            print(json.dumps({'status': 'unavailable', 'request_id': None,
                              'message': 'Research connection failed; supply --origin (JIUWENSWARM_M1_ORIGIN), the app one-use bootstrap URL and a new protected --session-file.'}), file=sys.stderr)
            return 3
    origin = args.origin or os.getenv('JIUWENSWARM_M1_ORIGIN')
    token_file = args.token_file or os.getenv('JIUWENSWARM_M1_TOKEN_FILE')
    if args.session_file is None and (not origin or not token_file):
        print(json.dumps({'status': 'unavailable', 'request_id': None,
                          'message': 'Research origin and protected token file are required; set --origin (JIUWENSWARM_M1_ORIGIN) and --token-file (JIUWENSWARM_M1_TOKEN_FILE).'}), file=sys.stderr)
        return 3
    client = None
    request_id = None
    retained_uploads = []
    qualified_intake_ref = None
    pending_upload = None
    recovery_scope = None
    local_files = ExitStack()
    try:
        defaults = {}
        if args.session_file is not None:
            if args.token_file is not None:
                raise ValueError('select either a saved session or legacy token file')
            session = _load_session(args.session_file)
            if args.origin is not None and _native_origin(args.origin) != session['origin']:
                raise ValueError('saved session belongs to another origin')
            origin, token, defaults = session['origin'], session['token'], session['defaults']
        else:
            path = Path(token_file)
            info = path.stat()
            if path.is_symlink() or not stat.S_ISREG(info.st_mode) or (os.name == 'posix' and (info.st_mode & 0o077 or info.st_uid != os.geteuid())):
                raise ValueError('token file must have protected ownership/mode')
            token = path.read_text(encoding='ascii').strip()
        client = ResearchClient(origin, token, expected_instance=args.expected_instance)
        operation = args.operation
        if operation in {'readiness', 'doctor'}: result = client.readiness()
        elif operation == 'status': result = client.request('GET', '/api/v1/runs/' + _segment(args.run_id))
        elif operation == 'export':
            if args.output:
                data = client.export_bytes(args.run_id, args.audience)
                with args.output.open('xb') as output:
                    output.write(data)
                result = {'run_id': args.run_id, 'export': str(args.output), 'bytes': len(data)}
            else:
                result = client.request('GET', '/api/v1/runs/' + _segment(args.run_id) + '/export', params={'audience': args.audience})
        elif operation == 'cancel': result = client.request('POST', '/api/v1/runs/' + _segment(args.run_id) + '/cancel', json={'request_id': args.request_id})
        elif operation == 'uploads':
            scope = _upload_scope(args.scope if args.scope is not None else defaults.get('workspace_id'))
            result = client.request('GET', '/api/v1/inputs', params={'scope_id': scope})
        elif operation == 'delete-upload': result = client.request('DELETE', '/api/v1/inputs/' + _segment(args.upload_id))
        elif operation == 'upload':
            scope = _upload_scope(args.scope if args.scope is not None else defaults.get('workspace_id'))
            recovery_scope = scope
            source = _attachment(local_files, args.kind, args.file)
            client.readiness()  # Same target/version check; uploading does not start a run.
            pending_upload = source
            result = client.upload(source, scope)
            retained_uploads.append(_captured_upload(result, source, scope, defaults.get('account_id')))
            pending_upload = None
            if (result['content_sha256'] != source['content_sha256'] or result['size_bytes'] != source['size_bytes']
                    or _file_identity(source['stream']) != source['identity']):
                raise ValueError('captured attachment differs from the prevalidated bytes')
        elif operation == 'submit':
            workspace = args.workspace if args.workspace is not None else defaults.get('workspace_id')
            configuration = _strict_json(args.configuration_ref) if args.configuration_ref is not None else defaults.get('configuration_ref')
            plan_source = args.plan_source if args.plan_source is not None else defaults.get('plan_source', 'static')
            profile = args.profile_id if args.profile_id is not None else defaults.get('profile_id')
            if not workspace or configuration is None or plan_source not in {'static', 'planned'}:
                raise ValueError('an initialized server workspace and configuration are required')
            _contract('Ref', configuration)
            selected_request_id = args.client_request_id or 'request:' + uuid.uuid4().hex
            if re.fullmatch(r'[a-z][a-z0-9_.:-]{0,63}', selected_request_id) is None:
                raise ValueError('submission identity is unsupported')
            request_id = selected_request_id
            if profile is not None and (not isinstance(profile, str) or re.fullmatch(r'[a-z][a-z0-9_.:-]{0,63}', profile) is None):
                raise ValueError('profile identity is unsupported')
            offered = _offered_uploads(args.upload_ref)
            attachments = [('docs', path) for path in args.document] + [('repo', path) for path in args.repository] + [('datasets', path) for path in args.dataset]
            if len(offered) + len(attachments) > 64:
                raise ValueError('qualified intake supports at most64 uploaded inputs')
            if args.intake_ref and (attachments or offered):
                raise ValueError('attachments cannot modify an already qualified intake')
            if args.intake_ref:
                ref = _contract('Ref', _strict_json(args.intake_ref))
            else:
                prompt = args.prompt if args.prompt is not None else _local_file(local_files, args.prompt_file).read().decode('utf-8')
                if not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError('a nonempty original prompt is required')
                prompt.encode('utf-8', errors='strict')
                scope = _upload_scope(workspace) if attachments else workspace
                recovery_scope = scope if attachments else None
                # Open/read every input and validate all names/types/archives
                # before the first upload or native intake side effect.
                sources = [_attachment(local_files, kind, path) for kind, path in attachments]
                names = [(source['kind'], source['name']) for source in sources]
                hashes = [source['content_sha256'] for source in sources]
                if len(names) != len(set(names)) or len(hashes) != len(set(hashes)):
                    raise ValueError('duplicate attachment input or upload filename')
                if sources and client.readiness().get('ready') is not True:
                    raise ValueError('native target is not ready')
                for source in sources:
                    pending_upload = source
                    uploaded = client.upload(source, scope)
                    upload_id = _captured_upload(uploaded, source, scope, defaults.get('account_id'))
                    retained_uploads.append(upload_id)
                    pending_upload = None
                    if (uploaded['content_sha256'] != source['content_sha256'] or uploaded['size_bytes'] != source['size_bytes']
                            or _file_identity(source['stream']) != source['identity']):
                        raise ValueError('captured attachment differs from the prevalidated bytes')
                    offered.append(upload_id)
                ref = _contract('Ref', asyncio.run(client.qualify(prompt, workspace, offered)))
            if re.fullmatch(r'[a-z][a-z0-9_.:-]{0,63}', ref['id']) is None:
                raise ValueError('qualified intake identity is unsupported')
            qualified_intake_ref = ref
            submission = {'schema_version': '1.0.0', 'id': request_id, 'client_request_id': request_id,
                          'workspace_id': workspace, 'account_id': '', 'intake_ref': ref,
                          'configuration_ref': configuration, 'plan_source': plan_source,
                          'interaction_mode': args.interaction_mode}
            if profile: submission['profile_id'] = profile
            result = client.submit(submission)
            while args.wait and result.get('status') == 'in_progress':
                time.sleep(1)
                result = client.request('GET', '/api/v1/runs/' + _segment(result['run_id']))
        else:
            raise ValueError('unsupported operation')
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return completion_exit_code(result) if isinstance(result, dict) else 0
    except KeyboardInterrupt:
        if retained_uploads or qualified_intake_ref is not None or pending_upload is not None:
            print(json.dumps(_recovery(request_id, retained_uploads, qualified_intake_ref,
                bool(pending_upload and pending_upload.get('upload_started')), interrupted=True, scope=recovery_scope)), file=sys.stderr)
        return 130  # local interruption never issues a cancellation
    except (httpx.HTTPError, OSError, ValueError, TimeoutError) as error:
        unknown = bool(pending_upload and pending_upload.get('upload_started'))
        if isinstance(error, httpx.HTTPStatusError) and error.response.status_code < 500:
            unknown = False
        print(json.dumps(_recovery(request_id, retained_uploads, qualified_intake_ref, unknown, scope=recovery_scope)), file=sys.stderr)
        return 3
    finally:
        local_files.close()
        if client is not None: client.close()
