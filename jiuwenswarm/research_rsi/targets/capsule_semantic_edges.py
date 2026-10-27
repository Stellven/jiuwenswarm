"""Supplementary semantic edge cases: an extra, data-driven correctness gate.

Ported from Codex's ``capsule_semantic_edges.py``. The cases live in each
capsule's ``fixtures/semantic_edges.json`` (literal or derived packets, an
optional ``since_version``) and are built by the same generic case builder as
the benchmark. They are outside the timed benchmark; dispatchers run parent
and candidate once per case and apply the benchmark's correctness contract
(``capsule_benchmark.judge``): exact parent bytes where the parent passes the
checker, checker authority where it does not, exact parent error identity on
malformed cases. Only installed parent code executes in this process.
"""
from __future__ import annotations

import copy
import hashlib
import json
from types import SimpleNamespace

from ..records import encoded
from .capsule_benchmark import _drive, _error, build_cases, need
from .capsules import _carrier, semantic_edges_spec

SPEC_SCHEMA = 'ai4r-rsi-capsule-semantic-edges:1'


def _spec(name):
    spec = semantic_edges_spec(name)
    need(spec is not None, 'NO_SEMANTIC_EDGE_SPEC_FOR_TARGET')
    need(set(spec) <= {'schema', 'capsule_name', 'split', 'notes', 'cases'} and spec.get('schema') == SPEC_SCHEMA
         and spec.get('capsule_name') == name and isinstance(spec.get('cases'), list) and spec['cases'],
         'CLOSED_SEMANTIC_EDGE_SPEC_REQUIRED')
    return spec


def latest_version(name):
    return max(row.get('since_version', 1) for row in _spec(name)['cases'])


def semantic_edge_fixtures(name, version=None):
    """Fresh cases ``{id, split, packet, malformed}`` up to ``version`` (default latest)."""
    spec = _spec(name)
    version = latest_version(name) if version is None else version
    need(type(version) is int and 1 <= version <= latest_version(name), 'KNOWN_SEMANTIC_EDGE_VERSION_REQUIRED')
    return build_cases(spec['cases'], split=spec.get('split', 'supplementary'), version=version)


def semantic_protocol(name, version=None):
    fixtures = semantic_edge_fixtures(name, version)
    return {'schema': 'ai4r-rsi-capsule-supplementary-protocol:%d' % (version or latest_version(name)),
            'capsule_name': name, 'fixture_sha256': hashlib.sha256(encoded(fixtures)).hexdigest(),
            'fixture_count': len(fixtures), 'iterations': 1, 'warmups': 0,
            'scope': 'parent-relative correctness contract on supplementary edges; outside the timed objective'}


def semantic_parent_expectations(name, version=None):
    """Installed-parent oracle in Codex's shape (outputs/errors and original checks)."""
    version = latest_version(name) if version is None else version
    execute, check, _ = _carrier(name)
    rows = []
    for fixture in semantic_edge_fixtures(name, version):
        packet = fixture['packet']; before = copy.deepcopy(packet)
        try:
            raw = _drive(execute, packet)
        except Exception as error:
            row = {'id': fixture['id'], 'error': _error(error)}
        else:
            checks = check(SimpleNamespace(output_refs={}), {'packet': before}, {'result': json.loads(raw)})
            row = {'id': fixture['id'], 'output_sha256': hashlib.sha256(raw).hexdigest(), 'original_checks': checks,
                   'baseline_checker_discrepancy': any(value['outcome'] != 'PASS' for value in checks)}
        need(packet == before, 'INSTALLED_PARENT_MUTATED_INPUT')
        rows.append({**row, 'input_sha256': hashlib.sha256(encoded(before)).hexdigest()})
    return {'schema': f'ai4r-rsi-supplementary-parent-expectations:{version}', 'capsule_name': name,
            'fixture_sha256': hashlib.sha256(encoded(semantic_edge_fixtures(name, version))).hexdigest(),
            'scope': 'supplementary exact parent differential only; outside frozen proof', 'rows': rows}
