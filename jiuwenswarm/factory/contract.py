"""Versioned greedy-continuation contracts. Freezing is an operator action."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

CONTRACTS = Path(__file__).parent / 'contracts'
OUTCOMES = {'ok', 'config_rejected', 'measurement_failed', 'candidate_failed',
            'wrong_target', 'bad_digest', 'cancelled', 'upload_pending'}


class ContractFrozen(ValueError):
    pass


class Contract(dict):
    path: Path


def load(contract_id):
    path = Path(contract_id)
    if '/' not in str(contract_id) and not str(contract_id).endswith('.json'):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', str(contract_id)):
            raise ValueError('Invalid contract identifier')
        path = CONTRACTS / (str(contract_id) + '.json')
    result = Contract(json.loads(path.read_text()))
    result.path = path.resolve()
    if result['version'] < 1 or result['tolerance'] != 'byte-identical stdout':
        raise ValueError('Unsupported contract version or tolerance')
    return result


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def reference_info(contract):
    return contract.get('reference') or dict(contract.get('reference_image', {}),
                                            stdout_sha256=None, frozen_at=None, run_ref=None)


def freeze(path, reference_run):
    """Write the reference once, under a process lock; return the frozen contract."""
    path = Path(path)
    if '/' not in str(path) and path.suffix != '.json':
        raise ValueError('freeze requires an explicit contract path')
    contract = load(path)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = load(contract.path)
        if reference_info(current).get('stdout_sha256') is not None:
            raise ContractFrozen('Contract is frozen; create a version+1 contract file')
        if (reference_run.get('execution_outcome') != 'ok' or
                reference_run.get('evidence_completeness') != 'complete' or
                reference_run.get('image_id') != reference_info(current).get('image_id')):
            raise ValueError('Reference requires a successful complete run of the pinned reference image')
        sha = reference_run.get('stdout_sha256', '')
        if not re.fullmatch(r'[a-f0-9]{64}', sha):
            raise ValueError('Reference stdout SHA256 is required')
        current['reference'] = reference_info(current)
        current['reference'].update(stdout_sha256=sha,
            frozen_at=datetime.now(timezone.utc).isoformat(), run_ref=reference_run['run_ref'])
        atomic_json(current.path, current)
        contract.clear()
        contract.update(current)
        return contract


def evaluate(contract, run):
    outcome = run.get('execution_outcome', 'measurement_failed')
    if outcome not in OUTCOMES:
        raise ValueError('Unknown execution outcome')
    complete = run.get('evidence_completeness') == 'complete'
    details = dict(run.get('details', {}))
    correctness = 'not_evaluated'
    reference = reference_info(contract).get('stdout_sha256')
    if outcome == 'ok' and complete and reference and run.get('stdout_sha256'):
        correctness = 'pass' if reference == run['stdout_sha256'] else 'fail'
        if correctness == 'fail':
            outcome = 'candidate_failed'
    elif outcome == 'ok':
        details['unscored_reason'] = 'reference_unfrozen' if not reference else 'incomplete_evidence'
    return dict(execution_outcome=outcome, correctness=correctness,
                evidence_completeness='complete' if complete else 'partial', details=details)
