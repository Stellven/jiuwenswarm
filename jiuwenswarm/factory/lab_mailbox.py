"""The lab mailbox (``factory.lab-mailbox/1``): how the factory and a lab agent talk.

One directory per lab request::

    <root>/requests/<request_id>/package.json         the sealed lab package (written once)
    <root>/requests/<request_id>/messages/<from>-<seq>.json
    <root>/requests/<request_id>/files/<sha256>        content-addressed attachments

Each side only ever creates its own message files (``factory-000001.json``,
``lab-000001.json``) and never rewrites one, so the directory can be copied or synced
between machines in both directions without conflicts. A message becomes visible only
when complete: it is written to a temporary name and then hard-linked into place, which
fails if the name is taken.

Message types by sender:

    factory  request, question, cancel
    lab      accepted, rejected, progress, answer, report, failed, cancelled

The state of a request is folded from the lab's messages in order, plus whether the
factory asked to cancel. Questions and answers never change the state, and can be sent
at any time, including after the report.

The same mailbox can be reached over HTTP (``lab_http``): ``open_mailbox`` returns a local
``Mailbox`` for a directory and a ``RemoteMailbox`` for an ``http(s)://`` address, and both
offer the same methods.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

FORMAT = 'factory.lab-mailbox/1'
MESSAGE = 'factory.lab-message/1'
SENDERS = {'factory': {'request', 'question', 'cancel'},
           'lab': {'accepted', 'rejected', 'progress', 'answer', 'report', 'failed', 'cancelled'}}
TERMINAL = {'rejected', 'reported', 'failed', 'cancelled'}
# lab message type -> (states it may follow, resulting state)
LAB_TRANSITIONS = {
    'accepted': ({'requested', 'cancel_requested'}, 'accepted'),
    'rejected': ({'requested', 'cancel_requested'}, 'rejected'),
    'progress': ({'accepted', 'running', 'cancel_requested'}, 'running'),
    'report': ({'accepted', 'running', 'cancel_requested'}, 'reported'),
    'failed': ({'requested', 'accepted', 'running', 'cancel_requested'}, 'failed'),
    'cancelled': ({'requested', 'accepted', 'running', 'cancel_requested'}, 'cancelled'),
}
NAME = re.compile(r'^(factory|lab)-(\d{6})\.json$')
REQUEST_ID = re.compile(r'^labreq-[a-f0-9]{16,64}$')
SHA256 = re.compile(r'^[a-f0-9]{64}$')
FILE_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
BLOCK = 1 << 20


class MailboxError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def default_root(home=None):
    configured = os.environ.get('FACTORY_LAB_MAILBOX')
    if configured:
        return Path(configured).expanduser()
    from .telemetry import home_path
    return home_path(home) / 'lab-mailbox'


def open_mailbox(spec=None, home=None, token=None):
    """A mailbox for a directory or an ``http(s)://`` address (``$FACTORY_LAB_MAILBOX`` by default)."""
    spec = str(spec or os.environ.get('FACTORY_LAB_MAILBOX') or default_root(home))
    if spec.startswith(('http://', 'https://')):
        from .lab_http import RemoteMailbox
        return RemoteMailbox(spec, token)
    return Mailbox(spec)


def sha256_file(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(BLOCK), b''):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def fold(request_id, messages, invalid=()):
    """The thread of a request from its messages: state, answers and open questions."""
    state, ignored, answered = 'requested', [], {}
    cancel = False
    lab = sorted((m for m in messages if m['sender'] == 'lab'), key=lambda m: m['seq'])
    for message in [m for m in messages if m['sender'] == 'factory'] + lab:
        kind = message['type']
        if message['sender'] == 'factory':
            cancel = cancel or kind == 'cancel'
            continue
        if kind == 'answer':
            question = message['body'].get('question')
            if question and question not in answered:
                answered[question] = message['id']
            continue
        allowed, result = LAB_TRANSITIONS[kind]
        current = 'cancel_requested' if cancel and state in {'requested', 'accepted', 'running'} else state
        if current in allowed:
            state = result
        else:
            ignored.append(dict(id=message['id'], reason=f'{kind} is not allowed while {current}'))
    if cancel and state not in TERMINAL:
        state = 'cancel_requested'
    questions = [m['id'] for m in messages if m['type'] == 'question']
    return dict(request_id=request_id, state=state, messages=messages, invalid=list(invalid), ignored=ignored,
                answered=answered, open_questions=[q for q in questions if q not in answered])


def check_message(sender, kind, body, thread):
    """Raise unless ``sender`` may post ``kind`` on a request in this thread."""
    if sender not in SENDERS or kind not in SENDERS[sender]:
        raise MailboxError(f'{sender} may not send {kind}')
    if not isinstance(body, (dict, type(None))):
        raise MailboxError('Message body must be an object')
    state = thread['state']
    if sender == 'factory':
        if kind == 'request' and any(m['type'] == 'request' for m in thread['messages']):
            raise MailboxError('The request message is already posted')
        if kind != 'request' and not any(m['type'] == 'request' for m in thread['messages']):
            raise MailboxError('Post the request first')
        if kind == 'cancel' and state in TERMINAL:
            raise MailboxError(f'Request is already {state}')
    elif kind == 'answer':
        question = (body or {}).get('question')
        if question not in {m['id'] for m in thread['messages'] if m['type'] == 'question'}:
            raise MailboxError('An answer must name a question id of this request')
        if question in thread['answered']:
            raise MailboxError('That question is already answered')
    else:
        allowed, _ = LAB_TRANSITIONS[kind]
        if state not in allowed:
            raise MailboxError(f'A lab cannot send {kind} while the request is {state}')


def check_reference(reference):
    if (not isinstance(reference, dict) or not FILE_NAME.fullmatch(str(reference.get('name', '')))
            or not SHA256.fullmatch(str(reference.get('sha256', '')))
            or not isinstance(reference.get('size'), int) or reference['size'] < 0):
        raise MailboxError('A file reference needs name, sha256 and size')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _install(directory, name, data):
    """Create ``directory/name`` with ``data`` only if the name is free; never overwrite."""
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=directory, prefix='.pending-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, directory / name)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _stamp(path):
    # A file counts as checked only while its size and modification time stay the same.
    status = os.stat(path)
    return str(path), status.st_size, status.st_mtime_ns


class Mailbox:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self._verified = set()

    # ---- layout -----------------------------------------------------------------------
    def _dir(self, request_id):
        if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
            raise MailboxError('Invalid lab request id')
        return self.root / 'requests' / request_id

    def requests(self):
        base = self.root / 'requests'
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir() if REQUEST_ID.fullmatch(p.name) and (p / 'package.json').is_file())

    # ---- writing ----------------------------------------------------------------------
    def open_request(self, request_id, package):
        """Write the package once. Re-opening with the same package is a no-op."""
        directory = self._dir(request_id)
        data = (canonical(package) + '\n').encode('utf-8')
        target = directory / 'package.json'
        if target.is_file():
            if target.read_bytes() != data:
                raise MailboxError('Lab request id already names a different package')
            return False
        try:
            _install(directory, 'package.json', data)
        except FileExistsError:
            if target.read_bytes() != data:
                raise MailboxError('Lab request id already names a different package') from None
            return False
        return True

    def package(self, request_id):
        path = self._dir(request_id) / 'package.json'
        if not path.is_file():
            raise MailboxError('Unknown lab request')
        return json.loads(path.read_text(encoding='utf-8'))

    def attach(self, request_id, source, name, media_type='application/octet-stream'):
        """Copy a file into the request's content store in one pass; return its file reference."""
        if not FILE_NAME.fullmatch(name or ''):
            raise MailboxError('Invalid attachment name')
        files = self._dir(request_id) / 'files'
        files.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=files, prefix='.pending-')
        digest, size = hashlib.sha256(), 0
        try:
            with os.fdopen(fd, 'wb') as output, Path(source).open('rb') as stream:
                for block in iter(lambda: stream.read(BLOCK), b''):
                    digest.update(block)
                    size += len(block)
                    output.write(block)
            sha = digest.hexdigest()
            try:
                os.link(temporary, files / sha)
            except FileExistsError:
                pass
        finally:
            Path(temporary).unlink(missing_ok=True)
        self._verified.add(_stamp(files / sha))
        return dict(name=name, sha256=sha, size=size, media_type=media_type)

    def file_size(self, request_id, sha256):
        """Size of a stored attachment, or None. A partial upload is not stored."""
        if not SHA256.fullmatch(sha256 or ''):
            raise MailboxError('Invalid file digest')
        path = self._dir(request_id) / 'files' / sha256
        return path.stat().st_size if path.is_file() else None

    def partial_size(self, request_id, sha256):
        if not SHA256.fullmatch(sha256 or ''):
            raise MailboxError('Invalid file digest')
        path = self._dir(request_id) / 'files' / f'.partial-{sha256}'
        return path.stat().st_size if path.is_file() else 0

    def receive(self, request_id, sha256, size, offset, stream, length, limit=None):
        """Append ``length`` bytes at ``offset`` of an upload; install it once complete.

        Uploads resume: a client asks for ``partial_size`` and sends the rest. The file is
        installed under its digest only after the whole content hashes to ``sha256``.
        Returns the bytes received so far.
        """
        if self.file_size(request_id, sha256) is not None:
            return size
        if not isinstance(size, int) or size < 0 or (limit is not None and size > limit):
            raise MailboxError('File size is missing or over the limit')
        files = self._dir(request_id) / 'files'
        files.mkdir(parents=True, exist_ok=True)
        partial = files / f'.partial-{sha256}'
        have = partial.stat().st_size if partial.is_file() else 0
        if offset != have or length < 0 or offset + length > size:
            raise MailboxError(f'Upload offset {offset} does not continue the {have} bytes received')
        with partial.open('ab') as output:
            left = length
            while left:
                block = stream.read(min(BLOCK, left))
                if not block:
                    raise MailboxError('Upload ended early')
                output.write(block)
                left -= len(block)
            output.flush()
            os.fsync(output.fileno())
        have += length
        if have == size:
            digest, _ = sha256_file(partial)
            if digest != sha256:
                partial.unlink(missing_ok=True)
                raise MailboxError('Uploaded content does not match its digest')
            try:
                os.link(partial, files / sha256)
            except FileExistsError:
                pass
            partial.unlink(missing_ok=True)
            self._verified.add(_stamp(files / sha256))
        return have

    def file_path(self, request_id, reference):
        """Path of an attachment after checking its size and digest (once per process)."""
        check_reference(reference)
        path = self._dir(request_id) / 'files' / reference['sha256']
        if not path.is_file():
            raise MailboxError(f'Attachment {reference.get("name")!r} is missing')
        key = _stamp(path)
        if key[1] != reference['size'] or key not in self._verified:
            digest, size = sha256_file(path)
            if digest != reference['sha256'] or size != reference['size']:
                raise MailboxError(f'Attachment {reference.get("name")!r} differs from its digest')
            self._verified.add(key)
        return path

    def post(self, request_id, sender, kind, body=None, files=()):
        """Append one message and return it. Checks the sender, the state and the files first."""
        check_message(sender, kind, body, self.thread(request_id))
        for reference in files:
            check_reference(reference)
            if self.file_size(request_id, reference['sha256']) != reference['size']:
                raise MailboxError(f'File {reference["name"]!r} is not uploaded to this request')
        directory = self._dir(request_id) / 'messages'
        for _ in range(1000):
            seq = 1 + max((int(m.group(2)) for m in map(NAME.match, os.listdir(directory))
                           if m and m.group(1) == sender), default=0) if directory.is_dir() else 1
            message = dict(schema=MESSAGE, request_id=request_id, id=f'{sender}-{seq:06d}', seq=seq,
                           sender=sender, type=kind, at=now(), body=body or {}, files=list(files))
            try:
                _install(directory, f'{sender}-{seq:06d}.json', (canonical(message) + '\n').encode('utf-8'))
                return message
            except FileExistsError:
                continue
        raise MailboxError('Could not allocate a message number')

    # ---- reading ----------------------------------------------------------------------
    def messages(self, request_id):
        """All well-formed messages in posting order, and the files that are not."""
        directory = self._dir(request_id) / 'messages'
        good, bad = [], []
        if not directory.is_dir():
            return good, bad
        for name in sorted(os.listdir(directory)):
            match = NAME.match(name)
            if name.startswith('.'):
                continue
            if not match:
                bad.append(dict(file=name, reason='not a message file name'))
                continue
            try:
                message = json.loads((directory / name).read_text(encoding='utf-8'))
                sender, seq = match.group(1), int(match.group(2))
                if (message.get('schema') != MESSAGE or message.get('request_id') != request_id
                        or message.get('sender') != sender or message.get('seq') != seq
                        or message.get('id') != f'{sender}-{seq:06d}'
                        or message.get('type') not in SENDERS[sender]
                        or not isinstance(message.get('body'), dict) or not isinstance(message.get('files'), list)):
                    raise ValueError('fields do not match the file name or the message format')
                good.append(message)
            except (OSError, ValueError) as exc:
                bad.append(dict(file=name, reason=str(exc)[:200]))
        good.sort(key=lambda m: (m['at'], m['sender'] != 'factory', m['seq']))
        return good, bad

    def thread(self, request_id):
        return fold(request_id, *self.messages(request_id))

    def latest(self, request_id, kind):
        found = [m for m in self.messages(request_id)[0] if m['type'] == kind]
        return found[-1] if found else None
