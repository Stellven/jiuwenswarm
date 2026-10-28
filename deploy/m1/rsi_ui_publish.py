"""Publish a finite stopped-run CC review view; never opens private ledgers.

Only exact explicitly named OriginalBytes parent-source exports and a pinned
external stop checkpoint are read. No Core store is opened or recovered; no
model, fixture, Library, readiness or controller operation is invoked.
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import sys
import types

from jiuwenswarm.research_records.original_bytes import OriginalBytes
# Do not execute server.rsi.__init__: its legacy Harness exports initialize
# application logging/plugins. The Root publisher loads only these fixed pure
# files from the installed jiuwenswarm package, under a private module namespace.
_package = importlib.util.find_spec('jiuwenswarm')
_root = Path(next(iter(_package.submodule_search_locations)))
# Reusing the fixed namespace preserves exception/class identity when several
# independent Root publishers are loaded in one process.
_name = '_ai4r_cc_ui_publish'
if _name not in sys.modules:
    _pure = types.ModuleType(_name)
    _pure.__path__ = [str(_root / 'server/rsi')]
    sys.modules[_name] = _pure
_projection_name = _name + '.cc_rsi_projection'
if _projection_name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_projection_name, _root / 'server/rsi/cc_rsi_projection.py')
    _projection = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _projection
    _spec.loader.exec_module(_projection)
_projection = sys.modules[_projection_name]
MAX_PUBLIC_BYTES = _projection.MAX_PUBLIC_BYTES
validate_publication = _projection.validate_publication

PUBLIC_ROOT = Path('/var/lib/ai4r-rsi-source-public')
OUTPUT = Path('/run/ai4r-rsi-ui/publication.json')
REVIEW_ROOT = Path('/var/lib/ai4r-rsi-review-public')
MAX_PROGRESS_BYTES = 16384


def need(condition):
    if not condition:
        raise ValueError('Finite public CC source/checkpoint prerequisite differs')


def stopped_projection(public, source_ref, checkpoint_bytes, checkpoint_sha256, generation):
    """Pure projection for the current stopped-before-candidate case only.

    Later candidate sessions require a separate explicit typed publication join;
    never infer candidate bodies from raw history, arbitrary Refs or filenames.
    """
    need(hashlib.sha256(checkpoint_bytes).hexdigest() == checkpoint_sha256 and len(checkpoint_bytes) <= 65536)
    checkpoint = json.loads(checkpoint_bytes)
    need(checkpoint.get('schema') == 'ai4r-rsi-host-stopped-checkpoint:1'
         and checkpoint.get('candidate_started') is False
         and checkpoint.get('diagnosis_proposal_calls') == 0
         and checkpoint.get('relay_socket_present') is False
         and checkpoint.get('relay_session_preserved') is True
         and checkpoint.get('unknown_reclassified') is False)
    counts = checkpoint['rsi_ledger']['counts']
    need(set(counts) == {'completed', 'outcome_unknown'}
         and all(type(counts[key]) is int and counts[key] >= 0 for key in counts)
         and counts['outcome_unknown'] > 0)
    observed = checkpoint['observed_at']
    need(isinstance(observed, str) and datetime.fromisoformat(observed.replace('Z', '+00:00')).tzinfo is not None)
    source = public.get(source_ref)
    need(source['schema'] == 'ai4r-rsi-parent-source-export:1' and source['status'] == 'NOT_ADMISSION'
         and source['stage'] == 'screening')
    from jiuwenswarm.research.contracts import validate
    parent = public.get(source['parent_declaration_ref'])
    validate('capsule-declaration', parent)
    identity = parent['identity']
    target = identity['name'] + '@' + identity['version_label']
    # First supported workbench target: declared ranking helper, never its
    # carrier, rubric, hidden evaluation closure or any arbitrary body path.
    need(target == 'research.screening@m1-4' and parent['evolution']['rsi'] == 'propose'
         and any(selector.startswith('files:') and fnmatch.fnmatchcase('ranking_parent.txt', selector[6:])
                 for selector in parent['evolution']['may_change']))
    body_ref = source['parent_body_refs']['ranking_parent.txt']
    need(any(row['path'] == 'ranking_parent.txt' and row['sha256'] == body_ref['sha256'] for row in identity['body'])
         and body_ref in source['public_original_refs'])
    body = public.read(body_ref)
    need(len(body) <= 262144 and hashlib.sha256(body).hexdigest() == body_ref['sha256'])
    body = body.decode('utf8', errors='strict')
    blocked = {'allowed': False, 'blocker': 'Stopped with unresolved model delivery; no new inference is permitted.'}
    operator = {'allowed': False, 'blocker': 'Authenticated human operator broker is not installed.'}
    parent_id = 'parent:' + body_ref['sha256']
    evidence = {'id': 'stopped-checkpoint:' + generation, 'sha256': checkpoint_sha256}
    blocker = 'Setup/calibration stopped with an unknown model call. Provider termination is unproven; protected state is preserved.'
    revision = hashlib.sha256(json.dumps([source_ref, evidence], sort_keys=True).encode('utf8')).hexdigest()
    view = {'snapshot': {
        'schema_version': '1', 'revision': revision, 'generated_at': observed,
        'availability': 'BLOCKED', 'blocker': blocker,
        'targets': [{'id': target, 'name': target + ' · ranking helper', 'parent_hash': body_ref['sha256'],
                     'active_hash': None, 'run': blocked}],
        'runs': [{'id': generation, 'target_id': target, 'stage': 'setup/calibration', 'status': 'outcome_unknown',
                  'blockers': [blocker, 'No diagnosis, proposal or candidate was started. Timing/noise and final readiness remain unavailable.'],
                  'budget': {'elapsed_seconds': None, 'limit_seconds': None, 'setup_calls': counts['completed'],
                             'diagnosis_calls': 0, 'proposal_calls': 0, 'generation_call_limit': 2, 'cost': None, 'currency': None},
                  'activity': [{'id': 'stopped:' + checkpoint_sha256, 'at': observed, 'stage': 'setup/calibration',
                                'status': 'outcome_unknown', 'summary': f"Cumulative setup/smoke ledger: {counts['completed']} completed, {counts['outcome_unknown']} unknown. No capsule was produced. Counts span the dedicated RSI runtime; they are not candidate-generation calls."}]}],
        'nodes': [{'id': parent_id, 'target_id': target, 'run_id': None, 'parent_id': None, 'hash': body_ref['sha256'],
                   'label': 'Captured target parent · ranking helper', 'evaluation_status': 'Unavailable',
                   'admission_status': 'Unavailable (source export is NOT_ADMISSION)', 'activation_status': 'Unavailable',
                   'correctness': None, 'speed': None, 'noise': None, 'evidence_refs': [source_ref, source['parent_declaration_ref'], evidence],
                   'operator_receipts': [],
                   'admit': operator, 'activate': operator}]},
        'candidates': [{'node_id': parent_id, 'candidate_hash': body_ref['sha256'], 'path': 'ranking_parent.txt',
                        'parent_code': body, 'candidate_code': body, 'rationale': None,
                        'blocker': 'Captured parent source only; this source export contains no candidate code or measured improvement.'}]}
    return validate_publication(view)


def publish(value):
    need(os.name == 'posix' and os.geteuid() == 0)
    raw = json.dumps(validate_publication(value), sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')
    need(len(raw) <= MAX_PUBLIC_BYTES)
    OUTPUT.parent.mkdir(mode=0o755, exist_ok=True)
    for path in (OUTPUT.parent, *OUTPUT.parent.parents):
        meta = path.lstat()
        need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0 and not meta.st_mode & 0o022)
    fd, temporary = tempfile.mkstemp(prefix='.publication-', dir=OUTPUT.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, OUTPUT)
        directory = os.open(OUTPUT.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'status': 'PUBLISHED_READ_ONLY', 'sha256': hashlib.sha256(raw).hexdigest(), 'revision': value['snapshot']['revision']}


def append_review_grant(value, grant_path):
    """Root explicitly authorizes future exact Ref positions and signing key.

    The OriginalBytes owner must first publish this finite approved closure.
    No workbench/store directory or browser-chosen path is accepted here.
    """
    need(os.name == 'posix' and os.geteuid() == 0 and grant_path.is_absolute())
    fd = os.open(grant_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        meta = os.fstat(fd)
        need(stat.S_ISREG(meta.st_mode) and meta.st_uid == 0 and meta.st_nlink == 1
             and not meta.st_mode & 0o022 and meta.st_size <= 131072)
        with os.fdopen(fd, 'rb', closefd=False) as stream: grant = json.loads(stream.read(131073))
    finally: os.close(fd)
    need(set(grant) == {'schema', 'approved_refs', 'sessions', 'custodian_public_key', 'custodian_key_id'}
         and grant['schema'] == 'ai4r-cc-rsi-review-grant:1'
         and isinstance(grant['sessions'], list) and len(grant['sessions']) <= 64
         and isinstance(grant['custodian_key_id'], str) and 0 < len(grant['custodian_key_id']) <= 128)
    key = base64.b64decode(grant['custodian_public_key'] + '=' * (-len(grant['custodian_public_key']) % 4), altchars=b'-_', validate=True)
    need(len(key) == 32)
    from _ai4r_cc_ui_publish.cc_rsi_publication import ApprovedOriginals, append_session
    publications = [OriginalBytes(root) for root in (PUBLIC_ROOT, REVIEW_ROOT)]
    def read(pin):
        found = [public for public in publications if public.index().get(pin['id']) == pin['sha256']]
        need(bool(found))
        raw = found[0].read(pin)
        need(all(public.read(pin) == raw for public in found[1:]))
        return raw
    approved = ApprovedOriginals(read, grant['approved_refs'])
    for row in grant['sessions']:
        need(set(row) == {'session_ref', 'result_ref', 'operator_receipt_refs'}
             and isinstance(row['operator_receipt_refs'], list) and len(row['operator_receipt_refs']) <= 64)
        value = append_session(value, approved, session_ref=row['session_ref'], result_ref=row['result_ref'],
                               public_key=key, key_id=grant['custodian_key_id'], operator_receipt_refs=row['operator_receipt_refs'])
    return value


def append_progress_grant(value, grant_path, expected_sha256):
    """Read only a SHA-pinned, Root-owned finite operational observation.

    No ledger, controller, model, Core database or private record store is read.
    The operator supplies the already observed aggregates in this separate file.
    """
    need(os.name == 'posix' and os.geteuid() == 0 and grant_path.is_absolute())
    _projection._hash(expected_sha256)
    for path in (grant_path, *grant_path.parents):
        meta = path.lstat()
        need(not stat.S_ISLNK(meta.st_mode))
        if path != grant_path:
            need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0 and not meta.st_mode & 0o022)
    fd = os.open(grant_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        meta = os.fstat(fd)
        need(stat.S_ISREG(meta.st_mode) and meta.st_uid == 0 and meta.st_nlink == 1
             and stat.S_IMODE(meta.st_mode) in (0o600, 0o640) and meta.st_size <= MAX_PROGRESS_BYTES)
        with os.fdopen(fd, 'rb', closefd=False) as stream: raw = stream.read(MAX_PROGRESS_BYTES + 1)
    finally: os.close(fd)
    need(len(raw) <= MAX_PROGRESS_BYTES and hashlib.sha256(raw).hexdigest() == expected_sha256)
    def pairs(items):
        result = {}
        for key, item in items:
            need(key not in result)
            result[key] = item
        return result
    def nonfinite(_): raise ValueError('Nonfinite operational progress JSON is unavailable')
    progress = json.loads(raw.decode('utf8', errors='strict'), object_pairs_hook=pairs, parse_constant=nonfinite)
    from _ai4r_cc_ui_publish.cc_rsi_publication import append_progress
    return append_progress(value, progress, {'id': 'root-progress:' + expected_sha256, 'sha256': expected_sha256})


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--source-id', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--checkpoint-sha256', required=True)
    parser.add_argument('--generation', required=True)
    parser.add_argument('--session-grant', type=Path, help='Optional Root-owned finite future-session review grant')
    parser.add_argument('--progress-grant', type=Path, help='Optional Root-owned finite live aggregate observation')
    parser.add_argument('--progress-sha256', help='Required exact SHA256 when supplying --progress-grant')
    args = parser.parse_args()
    need(os.name == 'posix' and os.geteuid() == 0 and re.fullmatch('[a-z0-9][a-z0-9_-]{0,47}', args.generation)
         and args.checkpoint.is_absolute() and (args.progress_grant is None) == (args.progress_sha256 is None))
    with args.checkpoint.open('rb') as stream:
        raw = stream.read(65537)
    value = stopped_projection(OriginalBytes(PUBLIC_ROOT), {'id': args.source_id, 'sha256': args.source_sha256},
                               raw, args.checkpoint_sha256, args.generation)
    if args.progress_grant is not None:
        value = append_progress_grant(value, args.progress_grant, args.progress_sha256)
    if args.session_grant is not None:
        value = append_review_grant(value, args.session_grant)
    print(json.dumps(publish(value), sort_keys=True))


if __name__ == '__main__':
    main()
