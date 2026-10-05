"""Documentation-only public schema checks; no runtime behavior claim."""
import copy
import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
source = root / 'docs/architecture/contracts/services-v1.schema.json'
schema = json.loads(source.read_text(encoding='utf-8'))
resources = {schema['$id']: schema}
for p in (root / 'docs/architecture/exports/schemas').rglob('*.json'):
    s = json.loads(p.read_text(encoding='utf-8'))
    resources[s['$id']] = s
registry = Registry().with_resources((key, Resource.from_contents(value)) for key, value in resources.items())
Draft202012Validator.check_schema(schema)

def sample(s, owner=schema):
    if '$ref' in s:
        ref = s['$ref']
        if ref.startswith('#/$defs/'):
            return sample(owner['$defs'][ref.rsplit('/', 1)[1]], owner)
        return sample(resources[ref], resources[ref])
    if 'const' in s:
        return s['const']
    if 'enum' in s:
        return s['enum'][0]
    if 'anyOf' in s:
        return sample(s['anyOf'][0], owner)
    if 'oneOf' in s:
        return sample(s['oneOf'][0], owner)
    t = s.get('type')
    if isinstance(t, list):
        t = t[0]
    if t == 'object':
        result = {k: sample(s['properties'][k], owner) for k in s.get('required', [])}
        if result.get('status') == 'VALID':
            result['validated_plan_ref'] = {'id': 'valid-plan', 'sha256': 'a' * 64}
        if set(result) == {'value', 'unit', 'evidence_ref', 'unavailable_reason'}:
            result['unavailable_reason'] = None
        if set(result) == {'verdict_ref', 'unavailable_reason'}:
            result['unavailable_reason'] = None
        if set(result) == {'requested', 'effective', 'unavailable_reason'}:
            result['unavailable_reason'] = None
        if 'allowed_features' in result:
            result['ablation_study_ref'] = None
        if 'replacement_sha256' in result and result.get('action') == 'disable':
            result['replacement_sha256'] = None
        if 'profile_id' in result and 'operation' in result:
            result['login_id'] = None
        if 'profile_id' in result and 'state' in result:
            for key in ['login_id', 'verification_url', 'user_code', 'expires_at']:
                result[key] = None
        if result.get('state') == 'NOT_RUN' and 'skipped_check_ids' in result:
            result['verification_ref'] = None
        if result.get('operation') == 'turn':
            result['target_request_id'] = None
        if 'content_sha256' in result and 'role' in result:
            result['scope'] = {'kind': 'rsi_controller', 'session_id': 'session', 'attempt_id': 'attempt'}
        if result.get('state') in ['queued', 'running'] and 'reply_content_sha256' in result:
            result['reply_content_ref'] = None
            result['reply_content_sha256'] = None
        return result
    if t == 'array':
        return [sample(s['items'], owner) for _ in range(s.get('minItems', 0))]
    if t == 'integer':
        return s.get('minimum', 0)
    if t == 'number':
        return 0
    if t == 'boolean':
        return False
    if t == 'null':
        return None
    if t == 'string':
        if s.get('format') == 'date-time':
            return '2026-10-02T12:00:00Z'
        if '{64}' in s.get('pattern', ''):
            return 'a' * 64
        return 'fixture'
    return {}

names = ['planner_request', 'planner_proposal', 'validation_request', 'plan_validation',
         'experiment_request', 'experiment_profile', 'benchmark_request', 'run_handle',
         'export_request', 'benchmark_export', 'error', 'step', 'model_call', 'artifact',
         'measurement', 'deviation', 'seed', 'routing_request', 'routing_decision',
         'readiness', 'benchmark_profiles', 'export_handle', 'abort_request',
         'ablation_study', 'ablation_action', 'experimental_advance', 'experimental_gate_evidence',
         'auth_request', 'auth_result', 'model_bridge_request', 'model_bridge_result',
         'private_model_capture', 'scoped_capture_ref', 'retry_profile']
checks = 0
for name in names:
    validator = Draft202012Validator({'$schema': schema['$schema'], '$ref': schema['$id'] + '#/$defs/' + name}, registry=registry, format_checker=FormatChecker())
    fixture = sample(schema['$defs'][name])
    validator.validate(fixture)
    checks += 1
    for key in schema['$defs'][name].get('required', []):
        bad = copy.deepcopy(fixture)
        del bad[key]
        assert not validator.is_valid(bad), (name, key)
        checks += 1
    bad = copy.deepcopy(fixture)
    bad['unknown_core_field'] = True
    assert not validator.is_valid(bad), name
    checks += 1
    if 'version' in fixture:
        bad = copy.deepcopy(fixture)
        bad['version'] = 2
        assert not validator.is_valid(bad), name
        checks += 1
    for key, value in fixture.items():
        if isinstance(value, dict) and set(value) == {'id', 'sha256'}:
            bad = copy.deepcopy(fixture)
            bad[key]['sha256'] = 'not-a-hash'
            assert not validator.is_valid(bad), (name, key)
            checks += 1
    # Examples are constructed in memory; this check does not write runtime evidence.

v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/plan_validation'}, registry=registry)
invalid = sample(schema['$defs']['plan_validation'])
invalid['status'] = 'INVALID'
invalid['findings'] = [{'code': 'TYPE_MISMATCH', 'explanation': 'Fixture mismatch'}]
del invalid['validated_plan_ref']
v.validate(invalid)
invalid['validated_plan_ref'] = {'id': 'bad', 'sha256': 'a' * 64}
assert not v.is_valid(invalid)
checks += 2
m = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/measurement'}, registry=registry)
missing = {'value': None, 'unit': 'tokens', 'evidence_ref': None, 'unavailable_reason': 'NOT_REPORTED'}
m.validate(missing)
missing['unavailable_reason'] = None
assert not m.is_valid(missing)
checks += 2
for variant in schema['$defs']['model_call_scope']['oneOf']:
    scope = sample(variant)
    namespace = {'run': 'public_artifact', 'admission': 'public_artifact', 'planning': 'public_artifact',
                 'rsi_controller': 'rsi_private', 'oracle': 'oracle_private'}[scope['kind']]
    for name, field in [('model_bridge_request', 'prompt_content_ref'),
                        ('model_bridge_result', 'reply_content_ref')]:
        v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/' + name}, registry=registry)
        example = sample(schema['$defs'][name])
        example['scope'] = scope
        example[field] = {'namespace': namespace, 'ref': {'id': 'capture', 'sha256': 'a' * 64}}
        if name == 'model_bridge_result':
            example.update(state='complete', reply_content_sha256='b' * 64, reason=None)
        v.validate(example)
        checks += 1
        bad = copy.deepcopy(example)
        bad[field]['namespace'] = 'oracle_private' if namespace != 'oracle_private' else 'public_artifact'
        assert not v.is_valid(bad)
        checks += 1
        bad = copy.deepcopy(example)
        bad['scope']['invented_run_id'] = 'wrong'
        assert not v.is_valid(bad)
        checks += 1
    v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/model_bridge_request'}, registry=registry)
    example = sample(schema['$defs']['model_bridge_request'])
    example.update(scope=scope, operation='cancel', target_request_id='target', prompt_content_ref=None)
    v.validate(example)
    checks += 1
    example['target_request_id'] = None
    assert not v.is_valid(example)
    checks += 1
v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/private_model_capture'}, registry=registry)
example = sample(schema['$defs']['private_model_capture'])
example['scope'] = {'kind': 'run', 'run_id': 'wrong'}
assert not v.is_valid(example)
checks += 1
v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/retry_profile'}, registry=registry)
bad = sample(schema['$defs']['retry_profile'])
bad['max_execution_retries'] = 1
assert not v.is_valid(bad)
checks += 1
v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/model_call_limits'}, registry=registry)
for good in [{'a' * 64: 0}, {'b' * 64: 2, 'c' * 64: 1}]:
    v.validate(good)
    checks += 1
for bad in [{}, {'capability_name': 2}, {'a' * 64: -1}, {'a' * 64: 1.5}, {'a' * 64: True}]:
    assert not v.is_valid(bad)
    checks += 1
v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/planner_proposal'}, registry=registry)
proposal = sample(schema['$defs']['planner_proposal'])
proposal['plan']['track'] = 'production'
proposal['objective_bindings'] = []
v.validate(proposal)
checks += 1
proposal['plan']['track'] = 'isolated_experiment'
assert not v.is_valid(proposal)
checks += 1
v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/planning_reservation'}, registry=registry)
reservation = sample(schema['$defs']['planning_reservation'])
v.validate(reservation)
checks += 1
for field in schema['$defs']['planning_reservation']['required']:
    bad = copy.deepcopy(reservation)
    del bad[field]
    assert not v.is_valid(bad)
    checks += 1
v = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/model_call_reservation'}, registry=registry)
reservation = sample(schema['$defs']['model_call_reservation'])
reservation['scope'] = {'kind': 'run', 'run_id': 'r1'}
reservation['decl_hash'] = 'b' * 64
reservation['dispatch_ref'] = {'id': 'dispatch1', 'sha256': 'a' * 64}
reservation.pop('planning_ref', None)
v.validate(reservation)
checks += 1
for field in ['obs_id', 'turn', 'decl_hash', 'dispatch_ref']:
    bad = copy.deepcopy(reservation)
    del bad[field]
    assert not v.is_valid(bad)
    checks += 1
planning = copy.deepcopy(reservation)
planning.update(scope={'kind': 'planning', 'run_id': 'r1', 'planning_request_id': 'p1'}, planning_ref={'id': 'planning1', 'sha256': 'a' * 64})
for field in ['decl_hash', 'dispatch_ref']:
    del planning[field]
v.validate(planning)
checks += 1
for field in ['decl_hash', 'dispatch_ref']:
    bad = copy.deepcopy(planning)
    bad[field] = reservation[field]
    assert not v.is_valid(bad)
    checks += 1
bad = copy.deepcopy(planning)
del bad['planning_ref']
assert not v.is_valid(bad)
checks += 1
print(f'{checks} schema/example checks passed; reference existence and runtime behavior are not tested')
