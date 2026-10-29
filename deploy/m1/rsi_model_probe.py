"""One explicit connectivity turn with private native traces; no RSI acceptance.

Run as the isolated controller UID in its selected backend's container topology.
The account and evidence mounts are separate. An attempt is never replayed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

ROOT = Path('/var/lib/ai4r-rsi-model-probe')
MARKER = 'RSI_MODEL_CONNECTIVITY_OK'


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def create(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class Evidence:
    def __init__(self):
        for name in ('records', 'blobs'):
            (ROOT / 'evidence' / name).mkdir(mode=0o700)
        self.events = 0

    def record(self, kind, value):
        identifier = kind + ':' + uuid.uuid4().hex
        data = encoded(value)
        digest = hashlib.sha256(data).hexdigest()
        create(ROOT / 'evidence/records' / (identifier.replace(':', '-') + '.json'), data)
        if kind == 'native-governed-trace-event':
            self.events += 1
        return {'id': identifier, 'sha256': digest}

    def blob(self, data):
        digest = hashlib.sha256(data).hexdigest()
        path = ROOT / 'evidence/blobs' / digest
        if path.exists():
            if path.is_symlink() or path.read_bytes() != data:
                raise ValueError('Evidence collision')
        else:
            create(path, data)
        return {'id': 'blob:' + digest, 'sha256': digest}


async def probe(backend):
    if os.geteuid() != 12001 or os.getegid() != 12001:
        raise ValueError('Private controller identity required')
    for name in ('account', 'evidence'):
        path = ROOT / name
        metadata = path.lstat()
        if (not stat.S_ISDIR(metadata.st_mode) or path.is_symlink()
                or metadata.st_uid != 12001 or metadata.st_gid != 12001
                or stat.S_IMODE(metadata.st_mode) != 0o700):
            raise ValueError('Private controller mounts required')
    identifier = uuid.uuid4().hex
    model = 'gpt-6-luna' if backend == 'codex' else 'Qwen3.8-27B-NVFP4'
    create(ROOT / 'evidence/attempt.json', encoded({'schema': 'rsi-connectivity-attempt:1',
        'id': identifier, 'backend': backend, 'model': model,
        'purpose': 'connectivity_only', 'operational_qualification': False}))
    evidence = Evidence()
    contract = evidence.record('diagnostic-model-contract', {
        'schema': 'rsi-connectivity-contract:1', 'purpose': 'connectivity_only',
        'model': model, 'tools': [], 'timeout_s': 120,
        'operational_authority': False, 'RSI_session': False})
    started = evidence.record('diagnostic-model-call-start', {
        'schema': 'rsi-connectivity-call-start:1', 'attempt_id': identifier,
        'contract_ref': contract, 'requested_model': model})
    scope = {name: 'connectivity:' + identifier for name in
        ('run_id', 'node_id', 'subnode_id', 'attempt_id', 'execution_id', 'invocation_id', 'call_id')}
    scope.update(contract_ref=contract, model_call_start_ref=started)
    if backend == 'codex':
        from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
        service = SubscriptionService(ROOT / 'account')
    else:
        from jiuwenswarm.research_rsi.spark_backend import SparkSubscriptionService
        service = SparkSubscriptionService(ROOT / 'account')
    service.set_governed_trace_writer(evidence.record, evidence.blob)
    service.set_account_observer(evidence.record)
    result = None
    try:
        result = await service.invoke_governed_traced(scope,
            'Return exactly ' + MARKER + '. Do not use tools.', model=model, timeout_s=120,
            system='This is a single connectivity diagnostic. Return only the requested marker. Tools are unavailable.')
        if result['identity']['effective'] != model or result['text'].strip() != MARKER:
            evidence.record('diagnostic-unexpected-output', result)
            raise ValueError('Unexpected connectivity response')
        summary = {'schema': 'rsi-connectivity-result:1', 'status': 'CONNECTED',
            'backend': backend, 'model': model, 'native_trace_ref': result['native_trace_ref'],
            'native_trace_events': evidence.events, 'usage': result['usage'],
            'response_sha256': hashlib.sha256(result['text'].encode()).hexdigest(),
            'operational_qualification': False, 'RSI_session_started': False}
    except Exception as error:
        reason = str(error)
        summary = {'schema': 'rsi-connectivity-result:1', 'status': 'FAILED_NO_REPLAY',
            'backend': backend, 'model': model,
            'reason': reason if re.fullmatch('[A-Z][A-Z_]{1,79}', reason) else 'CONNECTIVITY_PROBE_FAILED',
            'native_trace_ref': getattr(error, 'native_trace_ref', None),
            'native_trace_events': evidence.events,
            'operational_qualification': False, 'RSI_session_started': False}
    finally:
        await service.transport.close()
    create(ROOT / 'evidence/result.json', encoded(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend', choices=('codex', 'spark'))
    args = parser.parse_args()
    os.umask(0o077)
    try:
        result = asyncio.run(probe(args.backend))
    except (ValueError, OSError):
        result = {'status': 'BLOCKED', 'reason': 'Private fresh connectivity mounts are required'}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'CONNECTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
