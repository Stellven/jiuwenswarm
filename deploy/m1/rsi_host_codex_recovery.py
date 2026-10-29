"""Root-only stopped host policy repair; original unknowns are never rewritten.

Plan reads exact operator-pinned JSON evidence. Apply records an immutable claim,
archives original configuration, installs a separately qualified policy and
publishes completion last. Neither operation calls a model or releases a native
lease. A missing completion blocks serve through verify_recovery_complete.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile

ROOT = Path('/var/lib/ai4r-rsi-host-codex')
RUN = Path('/run/ai4r-rsi-host-codex')
QUALIFICATION = Path('/var/lib/ai4r-rsi-host-codex-qualification.json')
KINDS = frozenset(('old_qualification', 'new_qualification', 'old_profile',
    'local_cessation', 'windows_cessation', 'old_no_tools_proof', 'new_no_tools_proof', 'authorization'))
SOURCE_PATHS = frozenset(('research/local_model_codex.py', 'research/local_model_relay.py',
    'research/local_models.py', 'research_rsi/host_codex_backend.py', 'research/resources/host_codex/model_catalog.json'))
PURPOSE = 'exact_new_bounded_screening_run'
CLAIM_FIELDS = frozenset(('schema', 'successor_policy_sha256', 'disposition_sha256', 'plan_sha256',
    'prior_profile_sha256', 'successor_profile_sha256', 'prior_qualification_sha256',
    'successor_qualification_sha256', 'request_id', 'recorded_at'))
APPLIED_FIELDS = frozenset(('schema', 'claim_sha256', 'successor_policy_sha256',
    'disposition_sha256', 'profile_sha256', 'recorded_at'))


def need(value):
    if not value:
        raise ValueError('Exact stopped Root recovery proof or unchanged configuration required')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hashed(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def document(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value); value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite recovery JSON')))


def dated(value):
    need(isinstance(value, str))
    when = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(when.tzinfo is not None)
    return when


def safe(path):
    path = Path(path)
    need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)))
    return path


def custody(path, *, directory=False, uid=0, gid=0, mode=0o600):
    path = safe(path); info = path.lstat()
    need((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
        and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, mode)
        and (directory or info.st_nlink == 1))
    return path


def read(path, *, limit=2 * 1024 * 1024, protected=True, **kw):
    path = custody(path, **kw) if protected else safe(path)
    need(path.is_file() and not path.is_symlink())
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit)
    return raw


def _directory(path):
    path = safe(path)
    if not path.exists():
        path.mkdir(mode=0o700); os.chown(path, 0, 0); os.chmod(path, 0o700)
    custody(path, directory=True, mode=0o700)


def _sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def write_new(path, raw, *, uid=0, gid=0, mode=0o600):
    path = safe(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        os.fchown(stream.fileno(), uid, gid); os.fchmod(stream.fileno(), mode)
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    _sync(path.parent)


def replace(path, raw, *, gid=0, mode=0o600):
    path = safe(path)
    fd, temporary = tempfile.mkstemp(prefix='.recovery-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchown(stream.fileno(), 0, gid); os.fchmod(stream.fileno(), mode)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path); _sync(path.parent)
    finally: Path(temporary).unlink(missing_ok=True)


@contextmanager
def runtime_lock(root=ROOT):
    """Shared by serve and apply; ownership is the actual flock, never a PID file."""
    import fcntl
    need(os.name == 'posix' and os.geteuid() == 0)
    custody(root, directory=True, mode=0o700)
    path = safe(Path(root) / 'runtime.lock')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        custody(path)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally: os.close(fd)


def verify_recovery_complete(root=ROOT):
    """Every immutable claim must have its exact published completion and disposition."""
    root = custody(root, directory=True, mode=0o700)
    claims = root / 'recovery-claims'; applied = root / 'recovery-applied'
    names = []
    for directory in (claims, applied):
        if not os.path.lexists(directory): names.append(set()); continue
        custody(directory, directory=True, mode=0o700)
        values = {p.name for p in directory.iterdir()}
        need(all(re.fullmatch(r'[0-9a-f]{64}\.json', name) for name in values))
        names.append(values)
    need(names[0] == names[1])
    for name in names[0]:
        raw = read(claims / name); claim = document(raw); completion = document(read(applied / name))
        need(set(claim) == CLAIM_FIELDS and claim['schema'] == 'ai4r-host-codex-recovery-claim:1'
            and set(completion) == APPLIED_FIELDS and completion['schema'] == 'ai4r-host-codex-recovery-applied:1'
            and claim['successor_policy_sha256'] == completion['successor_policy_sha256'] == name[:-5]
            and completion['claim_sha256'] == digest(raw)
            and completion['disposition_sha256'] == claim['disposition_sha256']
            and completion['profile_sha256'] == claim['successor_profile_sha256'])
        for key in CLAIM_FIELDS - {'schema', 'request_id', 'recorded_at'}: need(hashed(claim[key]))
        dated(claim['recorded_at']); dated(completion['recorded_at'])
        stem = digest(claim['request_id'].encode())
        receipt = read(root / 'relay/reconciliations' / (stem + '.json'), limit=65536)
        need(digest(receipt) == claim['disposition_sha256'])


def policy(value):
    need(isinstance(value, dict) and set(value) == {'schema', 'model', 'reasoning_effort',
        'binding_sha256', 'qualification_sha256', 'source_sha256', 'sha256'}
        and value['schema'] == 'ai4r-rsi-host-codex-policy:1'
        and value['model'] == 'gpt-6.1-sol' and value['reasoning_effort'] == 'medium'
        and set(value['source_sha256']) == SOURCE_PATHS
        and all(hashed(v) for v in value['source_sha256'].values())
        and all(hashed(value[k]) for k in ('binding_sha256', 'qualification_sha256', 'sha256'))
        and value['sha256'] == digest(encoded({k: v for k, v in value.items() if k != 'sha256'})))


def no_tools(qualification, proof, sources):
    need(qualification.get('schema') == 'ai4r-rsi-host-codex-no-tools:1'
        and qualification.get('native_version') == '0.163.0'
        and qualification.get('model') == 'gpt-6.1-sol' and qualification.get('reasoning_effort') == 'medium'
        and qualification.get('tool_names') == []
        and all(type(qualification.get(k)) is int and qualification[k] == 0
                for k in ('tools_count', 'functions_count', 'additional_tools_count'))
        and qualification.get('helper_sha256') == sources['research/local_model_codex.py']
        and qualification.get('model_catalog_sha256') == sources['research/resources/host_codex/model_catalog.json']
        and proof.get('schema') == 'ai4r-offline-native-tools-wire-proof:1'
        and proof.get('helper_source_sha256') == qualification['helper_sha256']
        and proof.get('native_binary_sha256') == qualification.get('binary_sha256')
        and proof.get('real_auth_or_account_files_used') is False and proof.get('real_generation_performed') is False)
    cases = proof.get('cases'); need(isinstance(cases, list) and bool(cases))
    for case in cases:
        need(case.get('real_provider_called') is False and case.get('account_rpc_sent') is False
            and case.get('resolved_model') == 'gpt-6.1-sol' and case.get('resolved_effort') == 'medium'
            and case.get('catalog_source_sha256') == qualification['model_catalog_sha256'])
        requests = case.get('http_requests'); need(isinstance(requests, list) and bool(requests))
        for request in requests:
            need(request.get('model') == 'gpt-6.1-sol' and request.get('reasoning_effort') == 'medium'
                and request.get('tools') == [] and request.get('additional_tools') == []
                and all(type(request.get(k)) is int and request[k] == 0 for k in ('tools_count', 'functions_count'))
                and request.get('recursive_tool_locations') == [] and request.get('actual_system_guard_present') is True
                and request.get('exact_public_user_present') is True
                and all(request.get(k) is False for k in ('authorization_present', 'cookie_present', 'proxy_authorization_present')))


def build_review(*, row, diagnostic_raw, evidence, prior_policy, successor_policy):
    """Pure exact-identity join. No file, model, ledger or clock effects."""
    need(set(evidence) == KINDS and all(isinstance(v, bytes) and len(v) <= 2 * 1024 * 1024 for v in evidence.values()))
    ident, payload_sha, result_raw = row
    need(isinstance(ident, str) and bool(ident) and hashed(payload_sha) and isinstance(result_raw, str))
    result = document(result_raw); need(result.get('outcome') == 'outcome_unknown')
    diagnostic = document(diagnostic_raw); values = {k: document(v) for k, v in evidence.items()}
    policy(prior_policy); policy(successor_policy)
    need(prior_policy['sha256'] != successor_policy['sha256']
        and prior_policy['binding_sha256'] == successor_policy['binding_sha256'])
    old = values['old_profile']; oldq = values['old_qualification']; newq = values['new_qualification']
    need(set(old) == {'schema', 'catalog', 'session', 'policy_sha256', 'qualification'}
        and old['schema'] == 'ai4r-rsi-host-codex:1' and old['policy_sha256'] == prior_policy['sha256']
        and old['qualification'] == oldq and prior_policy['qualification_sha256'] == digest(evidence['old_qualification'])
        and successor_policy['qualification_sha256'] == digest(evidence['new_qualification'])
        and oldq['binary_sha256'] == newq['binary_sha256']
        and oldq['model_catalog_sha256'] == newq['model_catalog_sha256'])
    for prefix, source in (('old', prior_policy), ('new', successor_policy)):
        q = values[prefix + '_qualification']; proof = values[prefix + '_no_tools_proof']
        need(q['proof_sha256'] == digest(evidence[prefix + '_no_tools_proof']))
        no_tools(q, proof, source['source_sha256'])
    need(diagnostic.get('schema') == 'ai4r-backend-receipt:1'
        and diagnostic.get('request_id') == ident and diagnostic.get('payload_sha256') == payload_sha
        and diagnostic.get('backend_kind') == 'host-codex-app-server'
        and diagnostic.get('binding_sha256') == prior_policy['binding_sha256'])
    local = values['local_cessation']; windows = values['windows_cessation']
    cid = local.get('owned_container_id'); start = local.get('original_start', {})
    need(local.get('schema') == 'ai4r-rsi-cloud-native-host-cessation-observation:1'
        and isinstance(cid, str) and hashed(cid) and start.get('owner_pid') == 1
        and start.get('pid_namespace') == local.get('prior_pid_namespace')
        and local.get('matching_processes') == local.get('matching_native_container_ids') == local.get('process_scan_errors') == []
        and local.get('identity_receipt', {}).get('container_id') == cid)
    events = local.get('lifecycle_events'); need(isinstance(events, list))
    for action in ('create', 'start', 'die', 'destroy'):
        matches = [e for e in events if e.get('Action') == action]
        need(len(matches) == 1 and matches[0].get('Actor', {}).get('ID') == cid)
    need(windows.get('schema') == 'ai4r-rsi-host-windows-scoped-process-observation:1'
        and windows.get('status') == 'OBSERVED' and type(windows.get('owned_process_count')) is int
        and windows['owned_process_count'] == 0 and windows.get('processes') == []
        and windows.get('remote_termination_inferred') is False)
    auth = values['authorization']
    need(set(auth) == {'schema', 'actor', 'request_id', 'prior_policy_sha256', 'successor_policy_sha256',
        'purpose', 'authorization', 'recorded_at'}
        and auth['schema'] == 'ai4r-host-codex-recovery-authorization:1' and auth['actor'] == 'os:0:root'
        and auth['request_id'] == ident and auth['prior_policy_sha256'] == prior_policy['sha256']
        and auth['successor_policy_sha256'] == successor_policy['sha256'] and auth['purpose'] == PURPOSE
        and isinstance(auth['authorization'], str) and 0 < len(auth['authorization']) <= 4096)
    at = dated(auth['recorded_at'])
    need(at >= dated(local['observed_at']) and at >= dated(windows['observed_at_utc']))
    receipt = dict(schema='ai4r-host-codex-abandonment:1', request_id=ident, payload_sha256=payload_sha,
        result_sha256=digest(result_raw.encode()), diagnostic_sha256=digest(diagnostic_raw),
        prior_policy_sha256=prior_policy['sha256'], successor_policy_sha256=successor_policy['sha256'],
        prior_qualification_sha256=digest(evidence['old_qualification']),
        successor_qualification_sha256=digest(evidence['new_qualification']), actor='os:0:root',
        authorization=auth['authorization'], purpose=PURPOSE, provider_termination='UNPROVEN',
        original_outcome='outcome_unknown', automatic_replay=False, prior_budget_preserved=True,
        recorded_at=auth['recorded_at'], evidence_refs=[{'kind': k, 'sha256': digest(evidence[k])} for k in sorted(KINDS)])
    new_profile = dict(old, qualification=newq, policy_sha256=successor_policy['sha256'])
    review = {'schema': 'ai4r-host-codex-recovery-review:1', 'request_id': ident,
        'prior_policy_sha256': prior_policy['sha256'], 'successor_policy_sha256': successor_policy['sha256'],
        'disposition_sha256': digest(encoded(receipt)), 'prior_profile_sha256': digest(evidence['old_profile']),
        'successor_profile_sha256': digest(encoded(new_profile)), 'prior_qualification_sha256': digest(evidence['old_qualification']),
        'successor_qualification_sha256': digest(evidence['new_qualification']), 'evidence_refs': receipt['evidence_refs'],
        'provider_termination': 'UNPROVEN', 'original_outcome_preserved': True, 'catalog_and_session_preserved': True,
        'native_lease_released': False, 'recorded_at': auth['recorded_at']}
    return {'review': review, 'receipt': receipt, 'new_profile': encoded(new_profile), 'evidence': evidence}


def _rows(path):
    custody(path)
    for suffix in ('-wal', '-journal'):
        companion = Path(str(path) + suffix); need(not companion.exists() or companion.stat().st_size == 0)
    db = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    try: return db.execute("SELECT id,digest,result FROM requests WHERE result IS NULL OR json_extract(result,'$.outcome')='outcome_unknown'").fetchall()
    finally: db.close()


def _file_sha(path):
    custody(path)
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024): value.update(chunk)
    return value.hexdigest()


def prepare(input_path, *, root=ROOT, run=RUN, qualification=QUALIFICATION):
    need(os.name == 'posix' and os.geteuid() == 0)
    root, run, qualification = Path(root), Path(run), Path(qualification)
    custody(root, directory=True, mode=0o700); custody(run, directory=True, gid=13000, mode=0o710)
    verify_recovery_complete(root)
    input_raw = read(input_path, limit=65536); config = document(input_raw)
    need(set(config) == {'schema', 'request_id', 'prior_policy', 'successor_policy_sha256', 'inputs'}
        and config['schema'] == 'ai4r-host-codex-recovery-input:1'
        and set(config['inputs']) == KINDS - {'old_profile', 'old_qualification'})
    evidence = {'old_profile': read(root / 'profile.json'), 'old_qualification': read(qualification, mode=0o400)}
    for kind, pin in config['inputs'].items():
        need(set(pin) == {'path', 'sha256'} and hashed(pin['sha256']))
        raw = read(pin['path'], protected=False); need(digest(raw) == pin['sha256'])
        evidence[kind] = encoded(document(raw)) if kind == 'new_qualification' else raw
    old = document(evidence['old_profile']); catalog = read(run / 'catalog.json', gid=13000, mode=0o640)
    session = read(run / 'session.json', uid=12001, gid=12001, mode=0o400)
    runtime_qualification = read(run / 'qualification.json', gid=13000, mode=0o640)
    need(document(catalog) == old['catalog'] and document(session) == old['session']
        and document(runtime_qualification) == old['qualification'])
    from jiuwenswarm.research_rsi.host_codex_backend import validate_host_catalog, validate_qualification, descriptor
    validate_host_catalog(old['catalog']); newq = validate_qualification(document(evidence['new_qualification']), old['catalog'])
    binding = {key: old['catalog'][key] for key in ('gateway_id', 'backend', 'transport')}
    binding['model'] = old['catalog']['models'][0]; binding['binding_sha256'] = digest(encoded(binding))
    binding['host_qualification_sha256'] = digest(encoded(newq)); successor = descriptor(binding)
    need(successor['sha256'] == config['successor_policy_sha256'])
    rows = _rows(root / 'relay/requests.sqlite3')
    need(len(rows) == 1 and rows[0][0] == config['request_id'] and rows[0][2] is not None)
    diagnostic = read(root / 'relay/backend-receipts' / (digest(config['request_id'].encode()) + '.json'), limit=16384)
    prepared = build_review(row=rows[0], diagnostic_raw=diagnostic, evidence=evidence,
        prior_policy=config['prior_policy'], successor_policy=successor)
    prepared.update(catalog_raw=catalog, session_raw=session, runtime_qualification_raw=runtime_qualification, input_raw=input_raw,
        ledger_sha256=_file_sha(root / 'relay/requests.sqlite3'), row=rows[0])
    prepared['review'].update(input_sha256=digest(input_raw), recovery_helper_sha256=digest(Path(__file__).read_bytes()),
        catalog_sha256=digest(catalog), session_file_sha256=digest(session),
        runtime_qualification_before_sha256=digest(runtime_qualification), relay_ledger_sha256=prepared['ledger_sha256'])
    return prepared


def _stopped(root, run, prepared):
    need(not os.path.lexists(run / 'model.sock'))
    prior_ns = document(prepared['evidence']['local_cessation'])['prior_pid_namespace']
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid(): continue
        try:
            need(os.readlink(path / 'ns/pid') != prior_ns)
            command = (path / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError): continue
        need(not (b'serve' in command and any(p.endswith(b'/deploy/m1/rsi_host_codex.py') for p in command)))
        need(not any(b'Diskless native Codex host helper.' in p for p in command))
    observed = dated(document(prepared['evidence']['windows_cessation'])['observed_at_utc'])
    need(0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= 300)


def apply(input_path, review_sha256, *, root=ROOT, run=RUN, qualification=QUALIFICATION):
    root, run, qualification = Path(root), Path(run), Path(qualification)
    need(hashed(review_sha256))
    with runtime_lock(root):
        prepared = prepare(input_path, root=root, run=run, qualification=qualification)
        review = prepared['review']; need(digest(encoded(review)) == review_sha256)
        _stopped(root, run, prepared)
        successor = review['successor_policy_sha256']; name = successor + '.json'
        for directory in ('recovery-claims', 'recovery-applied', 'recovery-archives'):
            _directory(root / directory)
        archive = root / 'recovery-archives' / successor; need(not archive.exists()); _directory(archive)
        for name_, raw in (('profile.before.json', prepared['evidence']['old_profile']),
            ('qualification.before.json', prepared['evidence']['old_qualification']),
            ('qualification.runtime.before.json', prepared['runtime_qualification_raw']),
            ('catalog.before.json', prepared['catalog_raw']), ('session.before.json', prepared['session_raw']),
            ('operator-input.json', prepared['input_raw']), ('review.json', encoded(review))):
            write_new(archive / name_, raw)
        claim = {key: review[key] for key in CLAIM_FIELDS - {'schema', 'plan_sha256'}}
        claim.update(schema='ai4r-host-codex-recovery-claim:1', plan_sha256=review_sha256)
        claim_raw = encoded(claim); write_new(root / 'recovery-claims' / name, claim_raw)
        relay = root / 'relay'; _directory(relay / 'recovery-evidence'); _directory(relay / 'reconciliations')
        for raw in prepared['evidence'].values():
            target = relay / 'recovery-evidence' / (digest(raw) + '.json')
            if target.exists(): need(read(target) == raw)
            else: write_new(target, raw)
        receipt_raw = encoded(prepared['receipt'])
        write_new(relay / 'reconciliations' / (digest(review['request_id'].encode()) + '.json'), receipt_raw)
        # Validate the actual published closure using the relay owner without
        # opening its constructor/database or issuing any ledger SQL.
        from jiuwenswarm.research.local_model_relay import LocalModelRelay
        validator = object.__new__(LocalModelRelay)
        validator.runtime = relay; validator.recovery_policy_sha256 = successor
        validator._validate_disposition(*prepared['row'])
        replace(qualification, prepared['evidence']['new_qualification'], mode=0o400)
        replace(run / 'qualification.json', prepared['evidence']['new_qualification'], gid=13000, mode=0o640)
        replace(root / 'profile.json', prepared['new_profile'])
        need(read(run / 'catalog.json', gid=13000, mode=0o640) == prepared['catalog_raw']
            and read(run / 'session.json', uid=12001, gid=12001, mode=0o400) == prepared['session_raw']
            and _file_sha(relay / 'requests.sqlite3') == prepared['ledger_sha256'])
        completion = dict(schema='ai4r-host-codex-recovery-applied:1', claim_sha256=digest(claim_raw),
            successor_policy_sha256=successor, disposition_sha256=digest(receipt_raw),
            profile_sha256=digest(prepared['new_profile']), recorded_at=review['recorded_at'])
        write_new(root / 'recovery-applied' / name, encoded(completion)); verify_recovery_complete(root)
        return {'status': 'APPLIED_UNKNOWN_PRESERVED', 'successor_policy_sha256': successor,
            'disposition_sha256': digest(receipt_raw), 'provider_termination': 'UNPROVEN', 'native_lease_released': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('plan', 'apply')); parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--review-sha256')
    args = parser.parse_args()
    if args.operation == 'plan':
        with runtime_lock(ROOT):
            value = prepare(args.input)['review']
        result = {'status': 'REVIEW_REQUIRED_NO_EFFECT', 'review_sha256': digest(encoded(value)), 'review': value}
    else: result = apply(args.input, args.review_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
