"""Store-free adapter that makes pipeline stage capsules (Intent, Requirements, ...) portable.

The product runs a stage through its registration function, a run store and the runner.
Here the same release is built with the product's own prepare function against an in-memory
store (so it passes the same catalog pins), the same carrier ``execute`` runs on a ctx with
``input_ref``/``read_blob``/``read_json``/``model``, and the product's own checks and semantic
profile judge the output. Nothing here reimplements a check.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.state import json_bytes

from .loader import Capsule, MemoryStore, sha256

INTENT_VERSION = 'm1-8'
INTENT_ID = 'intent.compiler'
REQUIREMENTS_VERSION = 'm1-9'
REQUIREMENTS_ID = 'requirements.compiler'
EVALUATION_ID = 'research.evaluation'
SCREENING_ID = 'research.screening'
ALIASES = {'research.intent': INTENT_ID, 'research.requirements': REQUIREMENTS_ID}
MAX_DOCUMENTS = 64
# The product's default policy (local_profile.py capture): the only one the fixed compiler accepts.
DEFAULT_POLICY = {'schema_version': '1.0.0', 'id': 'portable.defaults', 'hardware_profile': 'single_gpu', 'automatic_retries': 0}

# Checks that need pipeline custody (run records, gates), so they cannot be evidenced outside it.
NOT_APPLICABLE = [
    {'check': 'exact_identity', 'part': 'pinned invocation completed observably (observation outcome and observed_runtime)',
     'status': 'not_applicable_outside_pipeline',
     'why': 'needs the runner\'s invocation-observation record; the runtime enforces its own wall time and model-call limit instead'},
    {'check': 'host_contract, host_identity, host_limits, host_authority',
     'status': 'not_applicable_outside_pipeline', 'why': 'host checks read run records, library standing and the sealed subnode contract'},
    {'check': 'internal_acceptance, external_output, aggregate_limits',
     'status': 'not_applicable_outside_pipeline', 'why': 'node finalization and gate decisions belong to the run store'},
]

DOCUMENTS_PORT = {'name': 'documents', 'required': False, 'schema_ref': 'text-documents',
                  'description': 'Supplied source documents as extracted text. Each is {"name": str, "text": str}.',
                  'schema': {'type': 'array', 'maxItems': MAX_DOCUMENTS, 'items': {
                      'type': 'object', 'additionalProperties': False, 'required': ['text'],
                      'properties': {'name': {'type': 'string'}, 'text': {'type': 'string', 'minLength': 1}}}}}
PRIOR_PORT = {'name': 'prior_plan_outcome', 'required': False, 'schema_ref': 'plan-outcome',
              'description': 'Optional plan-outcome record (outcome must be plan_infeasible) from an earlier infeasible plan.',
              'schema': {'type': 'object'}}
REQUEST_PORT = {'name': 'request', 'required': True, 'schema_ref': 'text',
                'description': 'The user\'s research request, plain text (non-empty).',
                'schema': {'type': 'string', 'minLength': 1}}


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

    def merge(self, other: 'StageStore') -> 'StageStore':
        self.blobs.update(other.blobs)
        return self


class StageCtx:
    """What a compiler carrier touches: model, input_ref, read_blob, read_json, contract."""

    def __init__(self, store, model, contract, input_refs):
        self.store, self.model, self.contract, self._refs = store, model, contract, input_refs
        self.host_records = {}  # in-memory sink for the carrier's record_host proposals (the pipeline's run store holds these)

    def record_host(self, key, ref):
        self.host_records[key] = ref

    def input_ref(self, port):
        if port not in self._refs:
            raise ResearchError('input_binding', 'Missing or duplicate named input')
        return self._refs[port]

    def read_blob(self, ref):
        return self.store.read_blob(ref)

    def read_json(self, ref):
        return self.store.read_record(ref)


class StageBase:
    """Shared build, pin and intake logic for the compiler stages (Intent, Requirements)."""

    NOT_APPLICABLE = NOT_APPLICABLE
    stage_key = ''            # key in prepare_compiler_assets' result
    capability_id = ''
    module = ''               # carrier module name under jiuwenswarm.research.capsules
    pinned_bodies: dict = {}  # imported module (dotted) -> its path in the declaration body
    # imported check module (dotted) -> its path inside the pinned check closure (runner blob)
    runner_modules = {'jiuwenswarm.research.checks.compiler': 'research/checks/compiler.py',
                      'jiuwenswarm.research.target_comparisons': 'research/target_comparisons.py'}

    def __init__(self, version: str):
        self.version = version
        self.prepare_kwargs: dict = {}

    # --- build and pins --------------------------------------------------
    def _prepare(self):
        store = StageStore()
        return store, self._assets(store)

    def _assets(self, store):
        """The product's own prepare function for this stage's release, against an in-memory store."""
        from jiuwenswarm.capsule_runtime.engine import run_sync
        from jiuwenswarm.research.compiler import prepare_compiler_assets
        return run_sync(prepare_compiler_assets(store, **self.prepare_kwargs))[self.stage_key]

    def _module_bytes_match(self, store, asset) -> None:
        """The imported carrier, helper and check code must be the pinned bytes (the catalog hashes these files)."""
        for name, path in self.pinned_bodies.items():
            wanted = asset['body_refs'][path]['sha256']
            if sha256(Path(importlib.import_module(name).__file__).read_bytes()) != wanted:
                raise ResearchError('asset_integrity', 'Imported module differs from its pinned release: ' + path)
        pinned = json.loads(store.read_blob(asset['runner_ref']).decode('utf-8'))['files']
        for name, path in self.runner_modules.items():
            if sha256(Path(importlib.import_module(name).__file__).read_bytes()) != pinned[path]['sha256']:
                raise ResearchError('asset_integrity', 'Imported check code differs from its pinned release: ' + path)

    @staticmethod
    def release_hash(asset) -> str:
        return sha256(json_bytes(asset))

    def verify_pins(self) -> str:
        """Rebuild the release with the product's own catalog checks; return its hash."""
        store, asset = self._prepare()
        self._module_bytes_match(store, asset)
        return self.release_hash(asset)

    def load(self) -> Capsule:
        capsule = Capsule(key=self.capability_id, capability_id=self.capability_id, version=self.version, root=Path(__file__).parent,
                          module=self.module, package='jiuwenswarm.research')
        try:
            store, asset = self._prepare()
            self._module_bytes_match(store, asset)
        except ResearchError as error:
            capsule.status, capsule.reason, capsule.refusal_code = 'refused', error.message, error.code
            return capsule
        execute = self.carrier(asset)
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

    def carrier(self, asset):
        """The carrier's execute function (a plain module function unless a stage binds more)."""
        return importlib.import_module('jiuwenswarm.research.capsules.' + self.module).execute

    # --- inputs -----------------------------------------------------------
    @staticmethod
    def _validate_common(name: str, value) -> bool:
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
        else:
            return False
        return True

    def validate_port(self, name: str, value) -> None:
        self._validate_common(name, value)

    def validate_inputs(self, inputs: dict) -> None:
        """Cross-port checks, run after every port passed its own validation."""

    @staticmethod
    def _intake(source: dict):
        """Plain request/documents/prior outcome -> blobs and a qualified-intake record, as ``intake.qualify_intake`` makes them."""
        store = StageStore()
        request_ref = store.put_blob(source['request'].encode('utf-8'), media_type='text/plain;charset=utf-8')
        sources = [store.put_blob(d['text'].encode('utf-8'), media_type='text/plain;charset=utf-8') for d in source.get('documents') or []]
        marker = store.put_blob(b'portable runtime: no pipeline profile, workspace or input directory')
        record = {'schema_version': '2.0.0', 'id': 'intake:' + sha256(json_bytes(source))[:32], 'request_ref': request_ref,
                  'source_refs': sources, 'offset_basis': 'Unicode code points', 'resource_refs': [], 'upload_refs': [],
                  'rejected_inputs': [], 'user_id': 'portable', 'profile_ref': marker, 'workspace_ref': marker,
                  'input_directory_ref': marker}
        if source.get('prior_plan_outcome') is not None:
            record['prior_plan_outcome_ref'] = store.put_record('plan-outcome', source['prior_plan_outcome'])
        return store, record

    # --- checks -------------------------------------------------------------
    def check(self, ctx, inputs, outputs):
        """The product's own ``compiler_checks``."""
        from jiuwenswarm.research.checks.compiler import compiler_checks
        return compiler_checks(ctx, inputs, outputs)

    def verify_ctx(self, call, output_refs, raws=None):
        # Outputs are content addressed like the product's, so a carrier-made ref to the same bytes equals the output ref.
        output_refs = {name: {'id': 'blob:' + ref['sha256'], 'sha256': ref['sha256']} for name, ref in output_refs.items()}
        for name, raw in (raws or {}).items():
            call.store.blobs[output_refs[name]['sha256']] = raw
        contract = {'bindings': [{'declaration_ref': self._asset['declaration_ref']}], 'input_refs': call.contract['input_refs']}
        return SimpleNamespace(store=call.store, contract=contract, output_refs=output_refs, observation=None,
                               input_ref=lambda port: call.refs[port], read_blob=call.store.read_blob, read_json=call.store.read_record)


class IntentStage(StageBase):
    """Intent release ``m1-8`` as a portable capability."""

    stage_key, capability_id, module = 'intent', INTENT_ID, 'intent_m1_8'
    pinned_bodies = {'jiuwenswarm.research.capsules.intent_m1_8': 'research/capsules/intent_m1_8.py',
                     'jiuwenswarm.research.capsules._common': 'research/capsules/_common.py'}

    def __init__(self, version: str = INTENT_VERSION):
        super().__init__(version)
        self.prepare_kwargs = {'intent_version': version}
        self.input_ports = [REQUEST_PORT, DOCUMENTS_PORT, PRIOR_PORT]

    def bind(self, inputs: dict, model, base_contract: dict):
        store, record = self._intake(inputs)
        store = StageStore(self._seed).merge(store)
        intake_ref = store.put_record('qualified-intake', record)
        contract = dict(base_contract)
        contract['inputs'] = [{'name': 'request', 'contract_id': 'qualified-intake:field-contract:2', 'version': '2.0.0',
                               'required': True, 'artifact_refs': [intake_ref]}]
        contract['outputs'] = [{'name': 'intent', 'contract_id': 'urn:jiuwenswarm:m1-design:intent-ir:1.0.0',
                                'version': '1.0.0', 'required': True}]
        contract['input_refs'] = [intake_ref]
        refs = {'request': intake_ref}
        return StageCtx(store, model, contract, refs), {'request': store.read_record(intake_ref)}, \
            SimpleNamespace(store=store, refs=refs, contract=contract)

    # --- admission ------------------------------------------------------------
    def admission_cases(self):
        calibration = Path(__file__).parents[1] / 'research' / 'resources' / 'calibration'
        request = (calibration / 'request.txt').read_text('utf-8')
        reply = reply_from_fixture(json.loads((calibration / 'intent_ir.json').read_text('utf-8')), text_ref(request))
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


class RequirementsStage(StageBase):
    """Requirements release ``m1-9`` as a portable capability: Intent in, Research Brief out."""

    stage_key, capability_id, module = 'requirements', REQUIREMENTS_ID, 'requirements_m1_9'
    pinned_bodies = {'jiuwenswarm.research.capsules.requirements_m1_9': 'research/capsules/requirements_m1_9.py',
                     'jiuwenswarm.research.capsules._common': 'research/capsules/_common.py'}
    NOT_APPLICABLE = [
        {'check': 'accepted_intent_input', 'status': 'not_applicable_outside_pipeline',
         'why': 'the pipeline feeds only an Intent that passed its internal acceptance (checks and semantic review); here the supplied '
                'Intent is re-checked mechanically (schema, source spans, identity against the request) but its earlier review cannot be evidenced'},
        *NOT_APPLICABLE[1:]]
    SOURCE_PORTS = ('request', 'documents', 'prior_plan_outcome')

    def __init__(self, version: str = REQUIREMENTS_VERSION):
        super().__init__(version)
        self.prepare_kwargs = {'requirements_version': version}
        self.input_ports = [
            {'name': 'intent', 'required': True, 'schema_ref': 'intent-ir',
             'description': 'The Intent IR for this request, normally the output of research.intent.'},
            {**REQUEST_PORT, 'description': 'The same original request text the Intent was made from (its request_ref must match).'},
            DOCUMENTS_PORT,
            {'name': 'policy', 'required': False, 'schema_ref': 'default-policy',
             'description': 'Optional default-policy record. Omitted: the product default (single_gpu, no automatic retries). '
                            'Only that hardware profile and zero retries are accepted, as in the fixed compiler.'},
            PRIOR_PORT]

    def validate_port(self, name: str, value) -> None:
        if self._validate_common(name, value):
            return
        if name == 'intent':
            validate('intent-ir', value)
        elif name == 'policy':
            validate('default-policy', value)
            if value['automatic_retries'] != 0 or value['hardware_profile'] != 'single_gpu':
                raise ResearchError('default_policy_invalid',
                                    'M1 fixed compiler requires no retries and the protected conservative hardware default')

    def validate_inputs(self, inputs: dict) -> None:
        """The supplied Intent must belong to this request and documents, and pass the product's Intent checks."""
        from jiuwenswarm.research.checks.compiler import check_intent
        store, record = self._intake({k: inputs[k] for k in self.SOURCE_PORTS if k in inputs})
        try:
            check_intent(inputs['intent'], record, store)
        except Exception as error:
            raise ResearchError('intent_input_invalid', 'Supplied Intent does not fit this request and documents: ' + str(error)) from error

    def bind(self, inputs: dict, model, base_contract: dict):
        from jiuwenswarm.research.compiler import input_port
        from jiuwenswarm.research.target_comparisons import BRIEF_CONTRACT, BRIEF_VERSION
        store, record = self._intake({k: inputs[k] for k in self.SOURCE_PORTS if k in inputs})
        store = StageStore(self._seed).merge(store)
        policy = inputs.get('policy') or DEFAULT_POLICY
        refs = {'intake': store.put_record('qualified-intake', record), 'intent': store.put_record('intent-ir', inputs['intent']),
                'defaults': store.put_record('default-policy', policy)}
        contract = dict(base_contract)
        contract['inputs'] = [input_port('intent', 'intent-ir', refs['intent']),
                              input_port('intake', 'qualified-intake:field-contract:2', refs['intake']),
                              input_port('defaults', 'default-policy:field-contract:1', refs['defaults'])]
        contract['outputs'] = [{'name': 'brief', 'contract_id': BRIEF_CONTRACT, 'version': BRIEF_VERSION, 'required': True}]
        contract['input_refs'] = [refs['intent'], refs['intake'], refs['defaults']]
        native = {'intent': inputs['intent'], 'intake': store.read_record(refs['intake']), 'defaults': policy}
        return StageCtx(store, model, contract, refs), native, SimpleNamespace(store=store, refs=refs, contract=contract)

    # --- admission ------------------------------------------------------------
    def reply_for(self, inputs: dict) -> dict:
        """A valid Brief for these inputs: the current fixture with its placeholder refs pointed at the real ones."""
        self._seed = getattr(self, '_seed', None) or StageStore()
        _, _, call = self.bind(inputs, None, {})
        intake = call.store.read_record(call.refs['intake'])
        mapping = {'intent_ir.json': call.refs['intent'], 'qualified_intake.json': call.refs['intake'],
                   'default_policy.json': call.refs['defaults'], 'request.txt': intake['request_ref']}
        return _map_refs(current_brief_fixture(), mapping)

    def admission_cases(self):
        calibration = Path(__file__).parents[1] / 'research' / 'resources' / 'calibration'
        request = (calibration / 'request.txt').read_text('utf-8')
        intent = reply_from_fixture(json.loads((calibration / 'intent_ir.json').read_text('utf-8')), text_ref(request))
        inputs = {'request': request, 'intent': intent}
        return {'positive': [inputs], 'worker_halts': [], 'model_reply': json.dumps(self.reply_for(inputs))}

    @staticmethod
    def mutations():
        def rebind(outputs):
            changed = json.loads(json.dumps(outputs))
            changed['brief']['intent_ref'] = {'id': 'blob:' + '0' * 64, 'sha256': '0' * 64}
            return changed

        def unlink(outputs):
            changed = json.loads(json.dumps(outputs))
            for field in ('acceptance_expectations', 'evidence_obligations'):
                for item in changed['brief'][field]:
                    item['requirement_ids'] = ['requirement:unknown']
            return changed
        return {'identity': rebind, 'coverage': unlink}


class EvaluationStage(StageBase):
    """Evaluation release ``m1-5`` as a portable capability: blueprint + measured payload in, scientific verdict out."""

    stage_key, capability_id, module = 'evaluation', EVALUATION_ID, 'evaluation'
    pinned_bodies = {'jiuwenswarm.research.capsules.evaluation': 'evaluation.py',
                     'jiuwenswarm.research.capsules._common': '_common.py'}
    runner_modules = {'jiuwenswarm.research.checks.' + n: 'checks/' + n + '.py' for n in ('stages', 'research')} | {
        'jiuwenswarm.research.' + n: n + '.py' for n in ('environment', 'science', 'target_comparisons')}
    NOT_APPLICABLE = [
        {'check': 'input_provenance', 'status': 'not_applicable_outside_pipeline',
         'why': 'the pipeline feeds only an accepted blueprint and a payload measured by the protected benchmark; here both are supplied by the '
                'caller and only their schemas, their mutual blueprint reference and the verdict recomputation from their numbers are checked'},
        *NOT_APPLICABLE[1:]]

    def __init__(self, version: str = 'm1-5'):
        super().__init__(version)
        self.input_ports = [
            {'name': 'brief', 'required': True, 'schema_ref': 'research-brief',
             'description': 'The governing Research Brief (schema 3.0.0).'},
            {'name': 'hypothesis_blueprint', 'required': True, 'schema_ref': 'hypothesis-blueprint:field-contract:2',
             'description': 'The frozen Hypothesis blueprint with its registered metrics and outcome rules.'},
            {'name': 'benchmark_payload', 'required': True, 'schema_ref': 'benchmark-payload:field-contract:2',
             'description': 'The measured benchmark payload. Its blueprint_ref.sha256 must be the SHA-256 of the canonical blueprint bytes.'}]

    def _assets(self, store):
        from jiuwenswarm.research.capsules.assets import build_research_assets
        return build_research_assets(store)['evaluation']

    def validate_port(self, name: str, value) -> None:
        validate(next(p['schema_ref'] for p in self.input_ports if p['name'] == name), value)

    def validate_inputs(self, inputs: dict) -> None:
        if sha256(json_bytes(inputs['hypothesis_blueprint'])) != inputs['benchmark_payload']['blueprint_ref']['sha256']:
            raise ResearchError('blueprint_payload_mismatch', 'The payload was not measured against this blueprint (blueprint_ref sha256 differs)')

    def bind(self, inputs: dict, model, base_contract: dict):
        store = StageStore(self._seed)
        payload = inputs['benchmark_payload']
        refs = {'brief': store.put_record('research-brief', inputs['brief']),
                # The payload's own id names the blueprint, so a pipeline-made pair keeps the Ref the product check compares.
                'hypothesis_blueprint': store.put_blob(json_bytes(inputs['hypothesis_blueprint']), record_id=payload['blueprint_ref']['id']),
                'benchmark_payload': store.put_record('benchmark-payload:field-contract:2', payload)}
        contract = dict(base_contract)
        contract['inputs'] = [{'name': p['name'], 'contract_id': p['schema_ref'], 'version': '1.0.0', 'required': True,
                               'artifact_refs': [refs[p['name']]]} for p in self.input_ports]
        contract['outputs'] = [{'name': 'evaluation_verdict', 'contract_id': 'evaluation-verdict:field-contract:2', 'version': '1.0.0', 'required': True}]
        contract['input_refs'] = [refs[p['name']] for p in self.input_ports]
        return StageCtx(store, model, contract, refs), copy.deepcopy(inputs), SimpleNamespace(store=store, refs=refs, contract=contract)

    def check(self, ctx, inputs, outputs):
        """The product's own ``ResearchChecks('evaluation')`` (async), unchanged."""
        from jiuwenswarm.capsule_runtime.engine import run_sync
        from jiuwenswarm.research.checks.stages import ResearchChecks
        return run_sync(ResearchChecks('evaluation')(ctx, inputs, outputs))

    # --- admission ------------------------------------------------------------
    @staticmethod
    def fixture_inputs() -> dict:
        """Packaged calibration records (minus the demonstration-only ``ext``), with the payload pointed at its blueprint."""
        blueprint, payload = _calibration('hypothesis_blueprint'), _calibration('benchmark_payload')
        payload['blueprint_ref'] = {'id': payload['blueprint_ref']['id'], 'sha256': sha256(json_bytes(blueprint))}
        return {'brief': current_brief_fixture(), 'hypothesis_blueprint': blueprint, 'benchmark_payload': payload}

    def reply_for(self, inputs: dict) -> dict:
        _, _, call = self.bind(inputs, None, {})
        verdict = _calibration('evaluation_verdict')
        verdict.update(brief_ref=call.refs['brief'], blueprint_ref=call.refs['hypothesis_blueprint'], benchmark_ref=call.refs['benchmark_payload'])
        return verdict

    def admission_cases(self):
        inputs = self.fixture_inputs()
        return {'positive': [inputs], 'worker_halts': [], 'model_reply': json.dumps(self.reply_for(inputs))}

    @staticmethod
    def mutations():
        def reclassify(outputs):
            changed = json.loads(json.dumps(outputs))
            verdict = changed['evaluation_verdict']
            verdict['classification'] = 'PASS' if verdict['classification'] != 'PASS' else 'FAIL'
            return changed

        def rebind(outputs):
            changed = json.loads(json.dumps(outputs))
            changed['evaluation_verdict']['blueprint_ref'] = {'id': 'blob:' + '0' * 64, 'sha256': '0' * 64}
            return changed
        return {'classification': reclassify, 'identity': rebind}


class ScreeningStage(StageBase):
    """Screening release ``m1-4`` as a portable capability: brief + candidate ideas in, ranked selection and opportunity card out."""

    stage_key, capability_id, module = 'screening', SCREENING_ID, 'screening'
    pinned_bodies = {'jiuwenswarm.research.capsules.screening': 'screening.py',
                     'jiuwenswarm.research.capsules._common': '_common.py',
                     'jiuwenswarm.research.capsules.ranking': 'ranking_parent.txt'}
    runner_modules = EvaluationStage.runner_modules
    NOT_APPLICABLE = [
        {'check': 'input_provenance', 'status': 'not_applicable_outside_pipeline',
         'why': 'the pipeline feeds a candidate set made by the protected Search stage from governed connectors; here the caller supplies the ideas, '
                'so only their schema and the screening arithmetic over them are checked'},
        {'check': 'host_record_custody', 'status': 'not_applicable_outside_pipeline',
         'why': 'the carrier hands the screening result to the run store as a host record; here an in-memory sink holds it and nothing is custodied'},
        *NOT_APPLICABLE[1:]]

    def __init__(self, version: str = 'm1-4'):
        super().__init__(version)
        self.input_ports = [
            {'name': 'brief', 'required': True, 'schema_ref': 'research-brief', 'description': 'The governing Research Brief (schema 3.0.0).'},
            {'name': 'candidate_set', 'required': True, 'schema_ref': 'candidate-set:field-contract:2',
             'description': 'The candidate ideas to screen: ideas with idea_id, title, summary, citation_ids, assumptions and risks.'}]

    def _assets(self, store):
        from jiuwenswarm.research.capsules.assets import build_research_assets
        return build_research_assets(store, screening_version=self.version)['screening']

    def carrier(self, asset):
        from jiuwenswarm.research.capsules.ranking import rank_opportunities
        from jiuwenswarm.research.capsules.screening import ScreeningCarrier
        return ScreeningCarrier(rank_opportunities, asset['body_refs']['ranking_parent.txt'], asset['body_refs']['screening_prompt.txt']).execute

    def validate_port(self, name: str, value) -> None:
        validate(next(p['schema_ref'] for p in self.input_ports if p['name'] == name), value)

    def bind(self, inputs: dict, model, base_contract: dict):
        store = StageStore(self._seed)
        rubric_ref = self._asset['body_refs']['screening_rubric.json']
        rubric = json.loads(store.read_blob(rubric_ref).decode('utf-8'))
        refs = {'brief': store.put_record('research-brief', inputs['brief']),
                'candidate_set': store.put_record('candidate-set:field-contract:2', inputs['candidate_set']),
                'screening_rubric': rubric_ref}  # the pinned rubric is an input, as in the pipeline
        schemas = {'brief': 'research-brief', 'candidate_set': 'candidate-set:field-contract:2',
                   'screening_rubric': 'screening-rubric:field-contract:1'}
        contract = dict(base_contract)
        contract['inputs'] = [{'name': name, 'contract_id': schemas[name], 'version': '1.0.0', 'required': True,
                               'artifact_refs': [ref]} for name, ref in refs.items()]
        contract['outputs'] = [{'name': 'screening_result', 'contract_id': 'screening-result:field-contract:2', 'version': '1.0.0', 'required': True},
                               {'name': 'opportunity_card', 'contract_id': 'opportunity-card:field-contract:2', 'version': '1.0.0', 'required': True}]
        contract['input_refs'] = list(refs.values())
        body = [r for name, r in self._asset['body_refs'].items() if name != '_common.py']
        contract['bindings'] = [{'declaration_ref': self._asset['declaration_ref'], 'implementation_refs': body, 'dependency_refs': []}]
        native = {'brief': inputs['brief'], 'candidate_set': inputs['candidate_set'], 'screening_rubric': rubric}
        return StageCtx(store, model, contract, refs), native, SimpleNamespace(store=store, refs=refs, contract=contract)

    def check(self, ctx, inputs, outputs):
        """The product's own ``ResearchChecks('screening')`` (async), unchanged."""
        from jiuwenswarm.capsule_runtime.engine import run_sync
        from jiuwenswarm.research.checks.stages import ResearchChecks
        return run_sync(ResearchChecks('screening')(ctx, inputs, outputs))

    # --- admission ------------------------------------------------------------
    @staticmethod
    def fixture_inputs() -> dict:
        return {'brief': current_brief_fixture(), 'candidate_set': _calibration('candidate_set')}

    def reply_for(self, inputs: dict) -> dict:
        return {'scores': _calibration('screening_result')['scores'],
                'opportunity_statement': _calibration('opportunity_card')['opportunity_statement']}

    def admission_cases(self):
        inputs = self.fixture_inputs()
        return {'positive': [inputs], 'worker_halts': [], 'model_reply': json.dumps(self.reply_for(inputs))}

    @staticmethod
    def mutations():
        def rebind(outputs):
            changed = json.loads(json.dumps(outputs))
            changed['screening_result']['candidate_ref'] = {'id': 'blob:' + '0' * 64, 'sha256': '0' * 64}
            return changed

        def reselect(outputs):
            changed = json.loads(json.dumps(outputs))
            ids = [row['idea_id'] for row in changed['screening_result']['scores']]
            current = changed['screening_result']['selected_idea_id']
            changed['screening_result']['selected_idea_id'] = next(i for i in ids if i != current)
            return changed
        return {'identity': rebind, 'selection': reselect}


def _calibration(name: str) -> dict:
    value = json.loads((Path(__file__).parents[1] / 'research' / 'resources' / 'calibration' / (name + '.json')).read_text('utf-8'))
    value.pop('ext', None)  # editorial extension of the demonstration fixtures, outside the closed contracts
    return value


def text_ref(text: str) -> dict:
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return {'id': 'blob:' + digest, 'sha256': digest}


def _walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _map_refs(value, mapping):
    if isinstance(value, dict):
        if set(value) == {'id', 'sha256'}:
            return dict(mapping.get(value['id'], value))
        return {k: _map_refs(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_map_refs(v, mapping) for v in value]
    return value


def reply_from_fixture(value, request_ref):
    """Point every placeholder Ref in a fixture Intent at the real request blob."""
    if isinstance(value, dict):
        if set(value) == {'id', 'sha256'}:
            return dict(request_ref)
        return {k: reply_from_fixture(v, request_ref) for k, v in value.items()}
    if isinstance(value, list):
        return [reply_from_fixture(v, request_ref) for v in value]
    return value


def current_brief_fixture() -> dict:
    """The packaged calibration Brief lifted to the current Brief schema (3.0.0); its ids match the packaged Intent."""
    path = Path(__file__).parents[1] / 'research' / 'resources' / 'calibration' / 'research_brief.json'
    brief = json.loads(path.read_text('utf-8'))
    brief['schema_version'] = '3.0.0'
    for metric in brief['target_metrics']:
        metric.setdefault('comparison_status', 'qualitative')
    brief['in_scope'][0]['id'] = 'scope:1'
    validate('research-brief', brief)
    return brief


def load_stage_capsules() -> dict[str, Capsule]:
    capsules = {}
    for stage in (IntentStage(), RequirementsStage(), EvaluationStage(), ScreeningStage()):
        capsule = stage.load()
        capsules[capsule.key] = capsule
    return capsules
