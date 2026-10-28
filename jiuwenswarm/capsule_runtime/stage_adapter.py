"""Store-free adapter that makes a pipeline stage capsule (Intent) portable.

The product runs Intent through ``compiler.register_compiler_capsules``, a run store and
the runner. Here the same release is built with ``prepare_compiler_assets`` against an
in-memory store (so it passes the same catalog pins), the same carrier ``execute`` runs on
a ctx with ``input_ref``/``read_blob``/``read_json``/``model``, and the product's own
``compiler_checks`` and semantic profile judge the output. Nothing here reimplements a check.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.state import json_bytes

from .loader import Capsule, MemoryStore, sha256

INTENT_VERSION = 'm1-8'
INTENT_ID = 'intent.compiler'
ALIASES = {'research.intent': INTENT_ID}
MAX_DOCUMENTS = 64

# Intent-stage checks that need pipeline custody, so they cannot be evidenced outside it.
NOT_APPLICABLE = [
    {'check': 'exact_identity', 'part': 'pinned invocation completed observably (observation outcome and observed_runtime)',
     'status': 'not_applicable_outside_pipeline',
     'why': 'needs the runner\'s invocation-observation record; the runtime enforces its own wall time and model-call limit instead'},
    {'check': 'host_contract, host_identity, host_limits, host_authority',
     'status': 'not_applicable_outside_pipeline', 'why': 'host checks read run records, library standing and the sealed subnode contract'},
    {'check': 'internal_acceptance, external_output, aggregate_limits',
     'status': 'not_applicable_outside_pipeline', 'why': 'node finalization and gate decisions belong to the run store'},
]


class StageStore(MemoryStore):
    """In-memory content-addressed store with the product's ref rules (id ``blob:<sha256>``)."""

    def __init__(self, seed: 'StageStore | None' = None):
        super().__init__()
        if seed is not None:
            self.blobs.update(seed.blobs)

    def put_blob(self, data: bytes, *, media_type: str = 'application/octet-stream', provenance=None, record_id=None, **_):
        digest = sha256(data)
        self.blobs[digest] = data
        return {'id': record_id or 'blob:' + digest, 'sha256': digest}

    def read_blob(self, ref):
        validate('Ref', ref)
        data = self.blobs.get(ref['sha256'])
        if data is None:
            raise ResearchError('evidence_unavailable', 'Unknown captured reference')
        return data

    def iter_records(self, **_):
        return iter(())


class StageCtx:
    """What the Intent carrier touches: model, input_ref, read_blob, read_json, contract."""

    def __init__(self, store, model, contract, input_refs):
        self.store, self.model, self.contract, self._refs = store, model, contract, input_refs

    def input_ref(self, port):
        if port not in self._refs:
            raise ResearchError('input_binding', 'Missing or duplicate named input')
        return self._refs[port]

    def read_blob(self, ref):
        return self.store.read_blob(ref)

    def read_json(self, ref):
        return self.store.read_record(ref)


class IntentStage:
    """Intent release ``m1-8`` as a portable capability."""

    NOT_APPLICABLE = NOT_APPLICABLE

    def __init__(self, version: str = INTENT_VERSION):
        self.version = version
        self.input_ports = [
            {'name': 'request', 'required': True, 'schema_ref': 'text',
             'description': 'The user\'s research request, plain text (non-empty).',
             'schema': {'type': 'string', 'minLength': 1}},
            {'name': 'documents', 'required': False, 'schema_ref': 'text-documents',
             'description': 'Supplied source documents as extracted text. Each is {"name": str, "text": str}.',
             'schema': {'type': 'array', 'maxItems': MAX_DOCUMENTS, 'items': {
                 'type': 'object', 'additionalProperties': False, 'required': ['text'],
                 'properties': {'name': {'type': 'string'}, 'text': {'type': 'string', 'minLength': 1}}}}},
            {'name': 'prior_plan_outcome', 'required': False, 'schema_ref': 'plan-outcome',
             'description': 'Optional plan-outcome record (outcome must be plan_infeasible) from an earlier infeasible plan.',
             'schema': {'type': 'object'}}]

    # --- build and pins --------------------------------------------------
    def _prepare(self):
        from jiuwenswarm.capsule_runtime.engine import run_sync
        from jiuwenswarm.research.compiler import prepare_compiler_assets
        store = StageStore()
        assets = run_sync(prepare_compiler_assets(store, intent_version=self.version))
        return store, assets['intent']

    @staticmethod
    def _module_bytes_match(asset) -> None:
        """The imported carrier and shared helper must be the pinned bytes (the catalog hashes the package files)."""
        from jiuwenswarm.research.capsules import _common, intent_m1_8
        pins = {intent_m1_8: 'research/capsules/intent_m1_8.py', _common: 'research/capsules/_common.py'}
        for module, path in pins.items():
            wanted = asset['body_refs'][path]['sha256']
            if sha256(Path(module.__file__).read_bytes()) != wanted:
                raise ResearchError('asset_integrity', 'Imported module differs from its pinned release: ' + path)

    @staticmethod
    def release_hash(asset) -> str:
        return sha256(json_bytes(asset))

    def verify_pins(self) -> str:
        """Rebuild the release with the product's own catalog checks; return its hash."""
        _, asset = self._prepare()
        self._module_bytes_match(asset)
        return self.release_hash(asset)

    def load(self) -> Capsule:
        capsule = Capsule(key=INTENT_ID, capability_id=INTENT_ID, version=self.version, root=Path(__file__).parent,
                          module='intent_m1_8', package='jiuwenswarm.research')
        try:
            store, asset = self._prepare()
            self._module_bytes_match(asset)
        except ResearchError as error:
            capsule.status, capsule.reason, capsule.refusal_code = 'refused', error.message, error.code
            return capsule
        from jiuwenswarm.research.capsules.intent_m1_8 import execute
        declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
        capsule.declaration, capsule.store, capsule.asset = declaration, store, asset
        self._asset, self._seed = asset, store
        capsule.release_hash = self.release_hash(asset)
        capsule.release = {'kind': 'pipeline-stage', 'files': {r['path']: r['sha256'] for r in declaration['identity']['body']}}
        capsule.execute, capsule.check = execute, self.check
        capsule.wall_s = float(declaration['budget']['per_call']['wall_s'])
        capsule.stage, capsule.input_ports = self, self.input_ports
        capsule.semantic_required = True
        return capsule

    # --- inputs -----------------------------------------------------------
    def validate_port(self, name: str, value) -> None:
        if name == 'request':
            if not isinstance(value, str) or not value.strip():
                raise ResearchError('validation', 'A nonempty original request is required')
        elif name == 'documents':
            if not isinstance(value, list) or len(value) > MAX_DOCUMENTS:
                raise ResearchError('validation', 'documents must be a list of at most %d items' % MAX_DOCUMENTS)
            for item in value:
                if (not isinstance(item, dict) or set(item) - {'name', 'text'} or not isinstance(item.get('text'), str)
                        or not item['text'].strip() or not isinstance(item.get('name', ''), str)):
                    raise ResearchError('validation', 'Each document needs nonempty "text" and optional string "name"')
        elif name == 'prior_plan_outcome':
            validate('plan-outcome', value)
            if value.get('outcome') != 'plan_infeasible':
                raise ResearchError('validation', 'Prior outcome is not a plan infeasibility')

    def bind(self, inputs: dict, model, base_contract: dict):
        """Plain inputs -> blobs and a qualified-intake record, as ``intake.qualify_intake`` makes them."""
        store = StageStore(self._seed)
        request = inputs['request']
        request_ref = store.put_blob(request.encode('utf-8'), media_type='text/plain;charset=utf-8')
        sources = [store.put_blob(d['text'].encode('utf-8'), media_type='text/plain;charset=utf-8') for d in inputs.get('documents') or []]
        marker = store.put_blob(b'portable runtime: no pipeline profile, workspace or input directory')
        record = {'schema_version': '2.0.0', 'id': 'intake:' + sha256(json_bytes(inputs))[:32], 'request_ref': request_ref,
                  'source_refs': sources, 'offset_basis': 'Unicode code points', 'resource_refs': [], 'upload_refs': [],
                  'rejected_inputs': [], 'user_id': 'portable', 'profile_ref': marker, 'workspace_ref': marker,
                  'input_directory_ref': marker}
        if inputs.get('prior_plan_outcome') is not None:
            record['prior_plan_outcome_ref'] = store.put_record('plan-outcome', inputs['prior_plan_outcome'])
        intake_ref = store.put_record('qualified-intake', record)
        intake = store.read_record(intake_ref)
        contract = dict(base_contract)
        contract['inputs'] = [{'name': 'request', 'contract_id': 'qualified-intake:field-contract:2', 'version': '2.0.0',
                               'required': True, 'artifact_refs': [intake_ref]}]
        contract['outputs'] = [{'name': 'intent', 'contract_id': 'urn:jiuwenswarm:m1-design:intent-ir:1.0.0',
                                'version': '1.0.0', 'required': True}]
        contract['input_refs'] = [intake_ref]
        ctx = StageCtx(store, model, contract, {'request': intake_ref})
        return ctx, {'request': intake}, SimpleNamespace(store=store, intake_ref=intake_ref, contract=contract)

    # --- checks -------------------------------------------------------------
    def check(self, ctx, inputs, outputs):
        """The product's own ``compiler_checks`` (intent_schema, source_spans, exact_identity)."""
        from jiuwenswarm.research.checks.compiler import compiler_checks
        return compiler_checks(ctx, inputs, outputs)

    def verify_ctx(self, call, output_refs):
        contract = {'bindings': [{'declaration_ref': self._asset['declaration_ref']}], 'input_refs': call.contract['input_refs']}
        return SimpleNamespace(store=call.store, contract=contract, output_refs=output_refs, observation=None)

    # --- admission ------------------------------------------------------------
    def admission_cases(self):
        calibration = Path(__file__).parents[1] / 'research' / 'resources' / 'calibration'
        request = (calibration / 'request.txt').read_text('utf-8')
        ref = {'id': 'blob:' + hashlib.sha256(request.encode('utf-8')).hexdigest(), 'sha256': hashlib.sha256(request.encode('utf-8')).hexdigest()}
        reply = reply_from_fixture(json.loads((calibration / 'intent_ir.json').read_text('utf-8')), ref)
        return {'positive': [{'request': request}], 'worker_halts': [], 'model_reply': json.dumps(reply)}

    @staticmethod
    def mutations():
        def rebind(outputs):
            changed = json.loads(json.dumps(outputs))
            changed['intent']['request_ref'] = {'id': 'blob:' + '0' * 64, 'sha256': '0' * 64}
            return changed

        def stretch(outputs):
            changed = json.loads(json.dumps(outputs))
            for value in _walk(changed):
                if isinstance(value, dict) and {'source_ref', 'start', 'end'} <= set(value):
                    value['end'] = 10 ** 6
                    break
            return changed
        return {'identity': rebind, 'span': stretch}


def _walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def reply_from_fixture(value, request_ref):
    """Point every placeholder Ref in a fixture Intent at the real request blob."""
    if isinstance(value, dict):
        if set(value) == {'id', 'sha256'}:
            return dict(request_ref)
        return {k: reply_from_fixture(v, request_ref) for k, v in value.items()}
    if isinstance(value, list):
        return [reply_from_fixture(v, request_ref) for v in value]
    return value


def load_stage_capsules() -> dict[str, Capsule]:
    stage = IntentStage()
    capsule = stage.load()
    return {capsule.key: capsule}
