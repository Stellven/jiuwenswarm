"""Explicit public source/declaration joins for root-approved calibration plans.

Returns a narrow projection for a separate OS-root publication owner. This code
never traverses private references, publishes an inbox, invokes a worker, signs,
or establishes security qualification/readiness.
"""
import hashlib
import re
from pathlib import Path

from .calibration import PLAN_SCHEMA, _scope, prepare_calibration_plan
from .candidate_bindings import bind_candidate, binding_id
from .mutation import child_declaration
from .profiles import safe_path
from .records import encoded
from .session_policy import validate_private, _contracts
from .targets.ranking_preparation import require_custodian_store

PROVENANCE_SCHEMA = 'urn:ai4r:private:rsi-calibration-material-provenance:1'


def prepare_calibration_materials(store, *, plan_ref, approved_plan_refs, parent_body_refs):
    """Return immutable ``({ref, bytes}, ...)`` only; no publication authority.

    The host's exact plan allowlist authorizes this projection. Parent body pins
    must cover exactly the original declaration, never an open-ended ref list.
    Original typed context bytes may contain opaque private refs; none are read
    recursively or included as materials.
    """
    require_custodian_store(store)
    if encoded(plan_ref) not in {encoded(pin) for pin in approved_plan_refs}:
        raise ValueError('Root-pinned independent calibration material approval required')
    plan = store.get(plan_ref); validate_private(PLAN_SCHEMA, plan)
    refs = {name: plan[name] for name in ('preparation_ref', 'review_ref', 'target_ref',
             'fixture_manifest_ref', 'session_ref', 'worker_profile_ref')}
    prep, target, _, session, _ = _scope(store, **refs)
    current = prepare_calibration_plan(store, **refs, invocation_wall_s=plan['invocation_wall_s'],
        evidence_wall_s=plan['evidence_wall_s'], wall_s=plan['wall_s'])
    if current != plan_ref:
        raise ValueError('Frozen calibration material scope changed')
    parent = store.get(prep['parent_declaration_ref'])
    _contracts().validate('capsule-declaration', parent)
    original = {row['path']: row['sha256'] for row in parent['identity']['body']}
    if (not isinstance(parent_body_refs, dict) or set(parent_body_refs) != set(original)
            or len(original) != len(parent['identity']['body'])):
        raise ValueError('Exact original public parent body closure required')
    for path, pin in parent_body_refs.items():
        safe_path(path)
        raw = store.read(pin)
        if pin['sha256'] != original[path] or hashlib.sha256(raw).hexdigest() != original[path]:
            raise ValueError('Original public parent body bytes differ')
    if parent_body_refs[prep['mutable_path']] != target['parent_ref']:
        raise ValueError('Original helper body pin differs from the frozen target')

    materials = {}
    def include(pin, raw=None):
        data = store.read(pin) if raw is None else raw
        if not isinstance(data, bytes) or hashlib.sha256(data).hexdigest() != pin['sha256']:
            raise ValueError('Explicit public material bytes differ')
        old = materials.get(pin['id'])
        item = {'ref': dict(pin), 'bytes': data}
        if old is not None and old != item:
            raise ValueError('Public material identity is ambiguous')
        materials[pin['id']] = item

    # Finite typed closure only: never follow target.calibration_ref,
    # session.chain_root_ref, fixture refs, review evidence, or arbitrary JSON.
    for pin in (plan['session_ref'], plan['target_ref'], plan['worker_profile_ref'], prep['parent_declaration_ref']):
        include(pin)
    for path in sorted(parent_body_refs):
        include(parent_body_refs[path])
    materializer_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    versions = set()
    for control in sorted(prep['children'], key=lambda row: row['id']):
        candidate = control['body_ref']
        identity = hashlib.sha256(encoded([plan_ref['sha256'], plan['session_ref'], candidate])).hexdigest()
        version = parent['identity']['version_label'] + '.cal' + identity[:12]
        if not re.fullmatch('[a-z0-9][a-z0-9._-]{0,31}', version) or version in versions:
            raise ValueError('Frozen parent version cannot express distinct calibration children')
        versions.add(version)
        provenance = {'schema': 'ai4r-rsi-calibration-material-provenance:1',
            'purpose': 'PLANTED_CALIBRATION_CONTROL', 'generator_source_sha256': prep['generator_ref']['sha256'],
            'materializer_source_sha256': materializer_sha, 'plan_sha256': plan_ref['sha256'],
            'source_sha256': candidate['sha256'], 'session_ref': plan['session_ref'],
            'target_ref': plan['target_ref'], 'parent_declaration_ref': prep['parent_declaration_ref'],
            'generating_model': None}
        validate_private(PROVENANCE_SCHEMA, provenance)
        provenance_ref = store.put(provenance)
        body = dict(original); body[prep['mutable_path']] = candidate['sha256']
        lineage = {'parent': prep['parent_declaration_ref'], 'co_parents': [], 'relation': 'supersedes',
            'builder': 'rsi_workbench', 'build_trigger': session['session_id'], 'context_capsules': [],
            'diagnosis_inputs': [], 'builder_ref': provenance_ref,
            'provenance': {'generating_model': None, 'prompt_ref': provenance_ref, 'trajectory_ref': provenance_ref}}
        child = child_declaration(parent, body_hashes=body, version_label=version,
            carrier=parent['identity']['carrier'], lineage=lineage, validate=_contracts().validate)
        declaration_ref = store.put(child)
        binding_ref = bind_candidate(store, session_ref=plan['session_ref'], candidate_ref=candidate,
                                     declaration_ref=declaration_ref)
        include(candidate); include(provenance_ref); include(declaration_ref); include(binding_ref)
        include({'id': binding_id(plan['session_ref'], candidate), 'sha256': binding_ref['sha256']}, store.read(binding_ref))
    # A separate publication owner installs exactly these bytes after review.
    # No private projection manifest or disclosure decision is included.
    return tuple(materials[key] for key in sorted(materials))
