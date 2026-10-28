"""Trace, packet-review and semantic-verifier stages, reusing the product's own code.

* trace: ``checks/trace.py check_trace`` (pure, offline).
* packet review: ``checks/packet_review.py review`` (science review packets only).
* semantic: ``gate.SemanticVerifier.review`` builds the prompt (pinned profile
  instructions + criteria, subject declaration + exact output bytes only, never
  inputs, traces or the request: design decision D20) and ``gate.assemble_assessment``
  parses the reply. Then ``checks/verifier.verifier_predicates`` recomputes the
  mechanical predicates (declaration_pin_matches, output_hash_matches,
  criterion_coverage_exact, verdict_follows_findings, schema checks). All three
  run unchanged against the in-memory store; nothing is reimplemented.
"""
from __future__ import annotations

import base64
import inspect
import json

from jiuwenswarm.research.checks.packet_review import review as packet_review
from jiuwenswarm.research.checks.trace import check_trace
from jiuwenswarm.research.checks.verifier import verifier_predicates
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.gate import SemanticVerifier
from jiuwenswarm.research.state import json_bytes

from .loader import Capsule

REVIEW_PACKET_KEYS = {'findings', 'blockers', 'completeness', 'plausibility'}


def verifier_plan(capsule: Capsule) -> dict:
    """Which verifier stages this capsule carries, and why. Decided by the declaration."""
    d = capsule.declaration
    kinds = {c['kind'] for c in d['guarantees']['checks']}
    uses_model = bool(d['needs']['injects'])
    if 'semantic' in kinds:
        semantic = (True, 'declaration lists semantic checks')
    elif uses_model:
        semantic = (True, 'model-based capsule (declares a model dependency)')
    else:
        semantic = (False, 'deterministic capsule')
    trace = any(p['name'] == 'trace' for p in d['ports']['outputs'])
    return {'deterministic': True, 'deterministic_checks': [c['id'] for c in d['guarantees']['checks']],
            'trace': trace, 'trace_why': 'declares a trace output port' if trace else 'no output port carries a trace manifest',
            'semantic': semantic[0], 'semantic_why': semantic[1]}


def run_trace(outputs: dict) -> dict | None:
    """Return a stage report, or None when no output carries a trace manifest.

    A trace output is {manifest, blobs: {sha256: base64}, policy, artifact (optional)}.
    """
    carried = outputs.get('trace')
    if not isinstance(carried, dict) or 'manifest' not in carried:
        return None
    blobs = {k: base64.b64decode(v) for k, v in (carried.get('blobs') or {}).items()}
    artifact = carried.get('artifact')
    result = check_trace(carried['manifest'], blobs, carried.get('policy') or {},
                         artifact.encode('utf-8') if isinstance(artifact, str) else None)
    return result


def run_packet_review(capsule: Capsule, outputs: dict) -> dict | None:
    """Packet review applies to science review packets; other outputs are not its subject."""
    reports = {}
    for name, value in outputs.items():
        if isinstance(value, dict) and REVIEW_PACKET_KEYS <= set(value):
            reports[name] = packet_review(value, capsule.declaration)
    return reports or None


async def _call(model, prompt: str) -> str:
    result = model(prompt)
    if inspect.isawaitable(result):
        result = await result
    return result


async def run_semantic(capsule: Capsule, outputs: dict, raws: dict, model) -> dict:
    """One review per output port. Raises ResearchError on an unusable reply."""
    store, asset = capsule.store, capsule.asset
    declaration_ref = asset['declaration_ref']
    profile = store.read_record(asset['profile_ref'], contract_id='checking-profile')
    reviews = {}
    for port, raw in raws.items():
        output_ref = store.put_blob(raw, media_type='application/json')
        criteria = [c for c in profile['criteria'] if c['target_port'] in (None, port)]
        context_ref = store.put_blob(json_bytes({'schema': 'portable-review-context:1', 'port': port,
                                                 'criteria': [c['criterion_id'] for c in criteria],
                                                 'declaration_sha256': declaration_ref['sha256'],
                                                 'output_sha256': output_ref['sha256']}))

        async def invoke(payload, system=None):
            return await _call(model, (system or '') + '\n\n' + payload)

        assessment_ref = await SemanticVerifier(store).review(declaration_ref, output_ref, asset['profile_ref'],
                                                              context_ref, port, invoke)
        contract = {'inputs': [{'name': 'subject_declaration', 'artifact_refs': [declaration_ref]},
                               {'name': 'subject_output', 'artifact_refs': [output_ref]}]}
        predicates = verifier_predicates(store, contract, assessment_ref, criteria, declaration_ref, output_ref)
        assessment = store.read_record(assessment_ref)
        reviews[port] = {'verdict': assessment['verdict'], 'findings': [
            {'criterion_id': f['criterion_id'], 'outcome': f['outcome'], 'reason': f['reason']} for f in assessment['findings']],
            'uncertainties': assessment['uncertainties'], 'limitations': assessment['limitations'],
            'required_correction': assessment['required_correction'], 'predicates': predicates,
            'output_sha256': output_ref['sha256']}
    return reviews


def judge(reviews: dict) -> tuple[str, str] | None:
    """(code, reason) when the reviews do not clear delivery, else None."""
    for port, review in reviews.items():
        broken = [k for k, ok in review['predicates'].items() if not ok]
        if broken:
            return 'verifier_predicate_failed', '%s: mechanical predicate(s) failed: %s' % (port, ', '.join(broken))
        bad = [f for f in review['findings'] if f['outcome'] != 'PASS']
        if bad:
            return 'semantic_' + ('fail' if any(f['outcome'] == 'FAIL' for f in bad) else 'not_passed'), \
                '%s: ' % port + '; '.join('%s %s: %s' % (f['criterion_id'], f['outcome'], f['reason']) for f in bad)
    return None
