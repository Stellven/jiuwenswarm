"""Harder core Requirements artifact-production fixtures; no model dispatch.

Upstream Intent is authored fixture data validated against production schema and
source checks. It is NOT an accepted commit/admission or executable E3 binding.
Actual whole-compiler comparisons must begin with the original request/uploads
and capture real candidate/accepted Intent, Brief, checks, review and gate records.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

from jsonschema import Draft202012Validator

REPO = Path(__file__).parents[2]
IDS = ('core-complex-01', 'core-complex-02', 'core-complex-03', 'core-complex-04')
ORACLE_VERSION = 'hard-core-requirements-finite-predicates:2'


def grader_source_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def data(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def write(path, value):
    with Path(path).open('xb') as stream:
        stream.write(data(value))


def schema(name):
    from jiuwenswarm.research.contracts import contract_schema
    value = contract_schema(name)
    common = json.loads((REPO / 'jiuwenswarm/research_contracts/schemas/common.schema.json').read_text('utf-8'))
    value['$defs'] = {**common['$defs'], **value.get('$defs', {})}
    def local(item):
        if isinstance(item, dict):
            return {key: child.replace('urn:jiuwenswarm:m1-design:common:1.0.0#/$defs/', '#/$defs/') if key == '$ref' and isinstance(child, str) else local(child) for key, child in item.items()}
        return [local(child) for child in item] if isinstance(item, list) else item
    return local(value)


def _fixture(store, case_id):
    clauses = [
        'Study whether the supplied binary sensor classifier can improve fault detection without changing its trained weights or data split.',
        'Change only its intervention decision cutoff from 0.60 to 0.55; this is not permission to change a scientific success threshold.',
        'Keep the scientific accuracy success rule fixed: treatment accuracy must be at least 5 percentage points above baseline accuracy.',
        'Require latency at least 5 percent lower than baseline latency, and require treatment latency strictly below 120 milliseconds.',
        'Use only the uploaded local dataset as validation_data and weights as project_asset; reference notes are context, never evaluation labels.',
        'Do not use network access, download data, retrain weights, invent measurements, add experiments, or retry failed scientific runs.',
        'Create research_report.md and comparisons.csv with explicit baseline/treatment values, units, target decisions, limitations and source references.',
        'Keep total scientific wall time at most 20 minutes and CPU memory at most 512 MiB. If a mandatory obligation cannot fit, preserve it and record the unresolved feasibility instead of relaxing acceptance.',
        'Prefer a compact report; compactness is optional and cannot remove mandatory evidence. Do not choose an unrequested algorithm or measurement procedure.',
        'No observed baseline accuracy or latency is provided: retain symbolic baseline comparisons rather than invent numerical baseline measurements.'
    ]
    if case_id == 'core-complex-02':
        clauses += ['The current Unicode note is authoritative; the near-duplicate archived note is superseded and cannot change the requested cutoff or success rule.']
    if case_id == 'core-complex-03':
        clauses += ['At the same time replace that scientific accuracy success rule with at least 7 percentage points above baseline. These two current instructions have equal authority and neither overrides the other; record their conflict rather than selecting a winner.']
    if case_id == 'core-complex-04':
        clauses += ['A GPU is optional only if the resource inventory confirms availability; it reports GPU unavailable. Use the explicit CPU-only allocation, retain the 20-minute wall limit and do not present the single_gpu default policy as observed hardware.']
    else:
        clauses += ['Use the explicitly supplied CPU-only allocation; do not apply an omitted-hardware GPU default.']
    request = '\n\n'.join(clauses)
    current = '当前版本 Café 🧪：分类器 cutoff 从 0.60 调到 0.55；accuracy 成功门槛保持 baseline 以上 5 percentage points。'
    archived = '归档版本 Cafe\u0301 🧪：分类器 cutoff 从 0.60 调到 0.50；accuracy 成功门槛改为 baseline 以上 5 percent relative。'
    documents = {'current-note.txt': current, 'archived-note.txt': archived,
        'resource-inventory.json': json.dumps({'dataset': 'uploaded and available', 'weights': 'uploaded and available',
             'execution': 'CPU-only', 'gpu_available': False, 'wall_minutes': 20, 'memory_mib': 512}, ensure_ascii=False)}
    if case_id != 'core-complex-02':
        documents = {'resource-inventory.json': documents['resource-inventory.json']}
    request_ref = store.put_blob(request.encode(), media_type='text/plain')
    source_refs = {name: store.put_blob(text.encode(), media_type='text/plain') for name, text in documents.items()}
    resource_values = {'dataset.json': {'rows': [[0, 0], [1, 1]], 'role': 'validation_data'},
                       'weights.json': {'fixed_weights': [0.1, 0.9], 'role': 'project_asset'}}
    resources = {name: store.put_blob(data(value), media_type='application/json') for name, value in resource_values.items()}
    defaults = {'schema_version': '1.0.0', 'id': 'policy:fixture', 'hardware_profile': 'single_gpu', 'automatic_retries': 0}
    defaults_ref = store.put_blob(data(defaults)); metadata_ref = store.put_blob(data({'fixture_only': True}))
    intake = {'schema_version': '2.0.0', 'id': 'intake:' + case_id, 'request_ref': request_ref,
        'source_refs': list(source_refs.values()), 'offset_basis': 'Unicode code points', 'resource_refs': list(resources.values()),
        'upload_refs': [], 'rejected_inputs': [], 'user_id': 'fixture', 'profile_ref': metadata_ref,
        'workspace_ref': metadata_ref, 'input_directory_ref': metadata_ref}
    def span(text, value=None, reference=None):
        source = request if value is None else value; found = source.index(text)
        return [{'source_ref': reference or request_ref, 'start': found, 'end': found + len(text)}]
    def statement(identifier, text, spans=None):
        return {'id': identifier, 'text': text, 'source_spans': spans or span(text)}
    constraints = [
        ('c-cutoff', clauses[1], 'intervention'), ('c-success', clauses[2], 'scientific_success'),
        ('c-resources', clauses[4], 'input_roles'), ('c-no-effects', clauses[5], 'effects'),
        ('c-budget', clauses[7], 'budget'), ('c-no-baseline', clauses[9], 'evidence'),
        ('c-hardware', clauses[-1], 'hardware')]
    if case_id == 'core-complex-02':
        cutoff_span = span('cutoff 从 0.60 调到 0.55', current, source_refs['current-note.txt'])
    else:
        cutoff_span = None
    intent = {'schema_version': '1.0.0', 'request_ref': request_ref,
        'interpretation': {'problem': statement('problem-main', clauses[0]),
            'desired_change': statement('change-main', clauses[1]), 'requested_result': statement('result-main', clauses[6])},
        'context': [{'id': 'context-resources', 'name': 'Uploaded resource inventory', 'role': 'resource availability',
                     'source_spans': span(documents['resource-inventory.json'], documents['resource-inventory.json'], source_refs['resource-inventory.json'])}],
        'in_scope': [statement('scope-main', clauses[0])], 'out_of_scope': [statement('excluded-effects', clauses[5])],
        'constraints': [{'id': identifier, 'text': text, 'category': category,
             'source_spans': cutoff_span if identifier == 'c-cutoff' and cutoff_span else span(text)} for identifier, text, category in constraints],
        'preferences': [statement('pref-compact', clauses[8])],
        'user_targets': [{'id': 't-accuracy', 'metric': 'accuracy', 'target_text': 'at least 5 percentage points above baseline accuracy',
                         'source_spans': span('at least 5 percentage points above baseline accuracy')},
            {'id': 't-latency', 'metric': 'latency', 'target_text': 'latency at least 5 percent lower than baseline latency',
             'source_spans': span('latency at least 5 percent lower than baseline latency')},
            {'id': 't-cap', 'metric': 'latency', 'target_text': 'treatment latency strictly below 120 milliseconds',
             'source_spans': span('treatment latency strictly below 120 milliseconds')}],
        'context_refs': list(source_refs.values()), 'uncertainties': [],
        'readiness': {'status': 'ready', 'reason': 'Purpose, comparison equations, resources and requested deliverables are explicit.'}}
    if case_id == 'core-complex-03':
        intent['user_targets'].append({'id': 't-conflict', 'metric': 'accuracy', 'target_text': 'at least 7 percentage points above baseline',
            'source_spans': span('at least 7 percentage points above baseline')})
        intent['uncertainties'] = [{'id': 'u-conflict', 'kind': 'conflicting', 'description': 'The fixed 5-percentage-point scientific accuracy rule conflicts with the equal-authority replacement 7-percentage-point rule.',
            'affected_fields': ['/user_targets'], 'blocking': True, 'clarification': 'Which scientific accuracy rule should apply?'}]
        intent['readiness'] = {'status': 'needs_clarification', 'reason': 'Equal-authority scientific accuracy success rules conflict.'}
    intake_ref = store.put_blob(data(intake)); intent_ref = store.put_blob(data(intent))
    from jiuwenswarm.research.checks.compiler import check_intent
    from jiuwenswarm.research.contracts import validate
    validate('qualified-intake', intake); validate('default-policy', defaults); check_intent(intent, intake, store)
    inputs = {'intent': intent, 'intake': intake, 'defaults': defaults}
    refs = {'intent': intent_ref, 'intake': intake_ref, 'defaults': defaults_ref}
    expected = {'blocker_expected': case_id == 'core-complex-03',
        'equations': {'t-accuracy': ['ge', 'baseline', '1', '5', 'accuracy_pp'],
            't-latency': ['le', 'baseline', '0.95', '0', 'time_ms'], 't-cap': ['lt', 'constant', '0', '120', 'time_ms']},
        'constraint_ids': [row[0] for row in constraints], 'scope_ids': ['scope-main'],
        'resource_roles': {'dataset.json': 'validation_data', 'weights.json': 'project_asset'},
        'cutoff_source_ref': source_refs.get('current-note.txt', request_ref),
        'forbidden_cutoff_source_ref': source_refs.get('archived-note.txt'),
        'production_check_limit': 'check_intent validates structure/source identities/span bounds, not semantic completeness; check_brief checks stable IDs/links, not original-request entailment.'}
    if case_id == 'core-complex-03': expected['equations']['t-conflict'] = ['ge', 'baseline', '1', '7', 'accuracy_pp']
    return {'id': case_id, 'request': request, 'documents': documents, 'resource_values': resource_values,
            'resources': resources, 'inputs': inputs, 'refs': refs, 'oracle': expected}


def freeze(destination):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.compiler import prepare_compiler_assets
    root = Path(destination); root.mkdir(parents=True, exist_ok=False)
    (root / 'public').mkdir(); (root / 'private').mkdir()
    store = SQLiteRunStore(root / 'fixture-store')
    try:
        asset = asyncio.run(prepare_compiler_assets(store))['requirements']
        rows = []
        for case_id in IDS:
            case = _fixture(store, case_id); folder = root / 'public' / case_id; folder.mkdir()
            (folder / 'original-request.txt').write_text(case['request'], encoding='utf-8', newline='')
            for name, text in case['documents'].items(): (folder / name).write_text(text, encoding='utf-8', newline='')
            for name, value in case['resource_values'].items(): write(folder / name, value)
            public = {'schema': 'hard-core-requirements-task:1', 'id': case_id,
                'input_status': 'Authored upstream Intent fixture validated by production schema/check_intent; NOT a committed accepted output or E3 admission.',
                'task': 'Produce a complete Research Brief JSON matching the actual production schema from the exact public inputs. Preserve constraints, scopes, IDs, source attribution, units and symbolic comparisons. Represent every mandatory constraint/target as an appropriate mandatory requirement with mandatory acceptance/evidence links (logical grouping is allowed); optional compactness cannot make evidence optional. Provide resource roles; retain real conflicts without choosing an unsupported winner. No execution or invented observations.',
                'inputs': case['inputs'], 'input_refs': case['refs'],
                'source_texts': [{'ref': reference, 'text': store.read_blob(reference).decode()} for reference in [case['inputs']['intake']['request_ref'], *case['inputs']['intake']['source_refs']]],
                'resource_files': [{'path': name, 'ref': reference} for name, reference in case['resources'].items()],
                'output_schema': schema('research-brief'),
                'instructions': (REPO / 'jiuwenswarm/research_assets/compiler/requirements.txt').read_text('utf-8'),
                'declaration': store.read_record(asset['declaration_ref'])}
            write(folder / 'task.json', public); write(folder / 'output-schema.json', public['output_schema'])
            (folder / 'task.txt').write_text(public['task'] + '\n\n' + public['instructions'], encoding='utf-8')
            private = {'oracle': case['oracle'], 'resources': case['resources']}
            write(root / 'private' / (case_id + '.json'), private)
            rows.append({'id': case_id, 'public_sha256': hashlib.sha256(data(public)).hexdigest(),
                'oracle_version': ORACLE_VERSION, 'grader_source_sha256': grader_source_sha256(),
                'private_oracle_sha256': hashlib.sha256(data(private)).hexdigest(),
                'declaration_ref': asset['declaration_ref'], 'profile_ref': asset['profile_ref'], 'bundle_ref': asset['bundle_ref'],
                'measurement_status': 'not_run', 'full_node_execution_ready': False,
                'reason': 'No authentic committed upstream Intent, canonical node contracts or approved E3 binding exists for this new fixture.'})
        skill = ('---\nname: rigorous-research-brief\ndescription: Compile supplied attributed research intent into a complete faithful Research Brief using ordinary tools.\n---\n\n'
            'Read all original request/source/resource files, task.json and output-schema.json. The upstream Intent is shared public input, not the target answer. '
            'Use ordinary Python/tools for schema checks, exact Unicode source inspection, affine comparisons and link coverage. '
            'Preserve scopes, IDs, mandatory/preference distinctions, resources and quantitative units. Unknown baseline observations do not prevent symbolic comparisons. '
            'Do not conflate intervention cutoffs with scientific success thresholds or percentages with percentage points. '
            'Carry real conflicts as blocking unresolved items; do not invent conflicts where roles differ. '
            'Write research_brief.json with the full production schema. Do not import production checks or read private oracle/fixture-store. '
            'You may author generic helpers/self-checks; no gold answer or tailored output helper is supplied.\n')
        skill_dir = root / 'public' / 'native-skill'; skill_dir.mkdir(); (skill_dir / 'SKILL.md').write_text(skill, encoding='utf-8')
        (root / 'private' / 'grader-source.py').write_bytes(Path(__file__).read_bytes())
        write(root / 'manifest.json', {'schema': 'hard-core-requirements-bank:1', 'cases': rows,
            'oracle_version': ORACLE_VERSION, 'grader_source_sha256': grader_source_sha256(),
            'primary_review_case': IDS[0], 'deferred_ladder_cases': list(IDS[1:]),
            'model_calls': 0, 'dispatch_performed': False, 'new_measured_trials': 0,
            'feasibility': {'worker': 'jiuwenswarm.research.capsules.requirements.execute(ctx, inputs)',
                'deterministic': 'jiuwenswarm.research.checks.compiler.check_brief',
                'shared_semantic': 'jiuwenswarm.research.gate.SemanticVerifier.review with actual prepared requirements profile',
                'authentic_whole_compiler': 'IntentionCompiler.run(run_id, protected) on original request/uploads through ordinary E1; capture candidateIntent, acceptedIntent, candidateBrief, checks/review/gate and committedBrief.',
                'single_full_node': 'Unavailable until actual admitted runtime/accepted upstream bindings exist; do not synthesize admission or call this E3.',
                'warning': 'Worker+check+review components with fixture input are not a protected full CC node.'}})
        return rows
    finally: store.close()


def load(directory):
    root = Path(directory); manifest = json.loads((root / 'manifest.json').read_text('utf-8')); cases = []
    for row in manifest['cases']:
        public = json.loads((root / 'public' / row['id'] / 'task.json').read_text('utf-8'))
        if hashlib.sha256(data(public)).hexdigest() != row['public_sha256']: raise ValueError('Frozen input changed')
        private = json.loads((root / 'private' / (row['id'] + '.json')).read_text('utf-8'))
        if row.get('private_oracle_sha256') and hashlib.sha256(data(private)).hexdigest() != row['private_oracle_sha256']:
            raise ValueError('Frozen private oracle changed')
        cases.append({**row, 'public': public, **private})
    return cases


def _equation_matches(target, wanted):
    if target.get('comparison_status') != 'quantitative' or not isinstance(target.get('comparison'), dict): return False
    comparison = target['comparison']; comparator, reference, factor, offset, dimension = wanted
    unit = str(target.get('unit', '')).lower().strip().replace('_', ' ')
    multiplier = {'fraction': Decimal(100), 'percentage points': Decimal(1), 'percentage point': Decimal(1), 'pp': Decimal(1)} if dimension == 'accuracy_pp' else {'ms': Decimal(1), 'milliseconds': Decimal(1), 'millisecond': Decimal(1), 's': Decimal(1000), 'seconds': Decimal(1000)}
    try:
        return (comparison['comparator'] == comparator and comparison['reference'] == reference
            and Decimal(str(comparison['factor'])) == Decimal(factor)
            and unit in multiplier and Decimal(str(comparison['offset'])) * multiplier[unit] == Decimal(offset))
    except (KeyError, ValueError, TypeError): return False


def _numbers(text):
    normalized = text.lower()
    for word, number in [('five', '5'), ('twenty', '20')]:
        normalized = re.sub(r'\b' + word + r'\b', number, normalized)
    return {Decimal(value) for value in re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?![\d.])', normalized)}


def _constraint_state(identifier, text, source):
    """Finite recognized entailment patterns; unfamiliar paraphrases stay UNKNOWN.

    This is neither substring presence nor a general semantic truth judge. Only
    clear recognized mutations are FAIL; unrecognized prose requires review.
    """
    if not isinstance(text, str): return False
    value = text.lower()
    for word, number in [('five', '5'), ('twenty', '20')]: value = re.sub(r'\b' + word + r'\b', number, value)
    def found(pattern): return re.search(pattern, value, re.I | re.S) is not None
    if found(r'\b(?:but|however|except|unless|actually|reverse|optionally)\b'):
        return None  # Scope exceptions/overrides need human review, not keyword acceptance.
    if _numbers(text) != _numbers(source):
        return False if _numbers(text) else None
    if identifier == 'c-cutoff':
        if found(r'0\.55\s*(?:to|->|→|调到|改为)\s*0\.60?\b'): return False
        return True if found(r'(?:cutoff|decision|intervention|分类器)') and found(r'0\.60?\s*(?:to|->|→|调到|降至)\s*0\.55\b') else None
    if identifier == 'c-success':
        if found(r'(?:change|replace|raise|lower|relax)\s+(?:the\s+)?scientific.*?(?:threshold|rule)') and not found(r'(?:not|never|unchanged|fixed|keep|retain|preserve)'): return False
        return True if found(r'(?:fixed|unchanged|keep|retain|preserv|保持)') and found(r'(?:scientific|accuracy|准确)') and found(r'\b5\s*(?:percentage[ _-]points?|pp|个百分点)\s*(?:above|over|higher than|以上)\s*(?:the\s+)?baseline') else None
    if identifier == 'c-no-effects':
        if found(r'^\s*(?:use|enable|allow|perform|retrain|download|retry)\b'): return False
        prohibited = found(r'^\s*(?:do not|never|must not|no)\b')
        body = re.sub(r'^\s*(?:do not|never|must not|no)\s+', '', value).rstrip('. ')
        if re.search(r'[.;:]', body) or re.search(r'\b(?:and|also)\s+(?:do|must|will|may|can|allow|enable)\b', body): return None
        groups = [r'network|网络', r'download|下载', r'retrain|重新训练', r'invent|fabricat|编造', r'add experiments|extra experiments|additional experiments|增加实验', r'retry|retries|重试']
        return True if prohibited and all(found(pattern) for pattern in groups) and not found(r'\b(?:but|however)\b.*\b(?:allow|may|can|will)\b') else None
    if identifier == 'c-budget':
        if found(r'\b(?:may|will|can|should|must)\s+(?:relax|drop|waive)\b'): return False
        wall = found(r'wall.{0,55}(?:at most|<=|≤|no more than)\s*20\s*(?:minutes|min\b)')
        memory = found(r'memory.{0,35}(?:at most|<=|≤|no more than)\s*512\s*mib\b')
        preserve = found(r'preserv|retain|never relax|do not relax|instead of relaxing')
        return True if wall and memory and preserve else None
    if identifier == 'c-resources':
        if found(r'dataset.{0,25}(?:as|is|role).{0,8}project.asset|weights.{0,25}(?:as|is|role).{0,8}validation.data'): return False
        return True if found(r'dataset.{0,35}validation.data') and found(r'weights.{0,35}project.asset') and found(r'context.{0,25}(?:never|not).{0,30}(?:evaluation|validation|labels)') else None
    if identifier == 'c-no-baseline':
        absence = found(r'(?:no|unknown|unobserved).{0,35}baseline|baseline.{0,35}(?:unknown|not provided|unobserved)')
        return True if absence and found(r'symbolic|符号') and found(r'(?:rather than invent|do not invent|never invent|no invented|not invent)') else None
    if identifier == 'c-hardware':
        cpu = found(r'cpu[ -]only')
        no_default = found(r'(?:do not|never|no)\s+(?:apply|present|claim).{0,100}(?:gpu|single_gpu|default)')
        unavailable = not re.search(r'gpu unavailable', source, re.I) or found(r'gpu.{0,30}(?:unavailable|not available|false)')
        return True if cpu and no_default and unavailable else None
    return None


def grade(case, brief, *, protected_accepted=None):
    """Independent propositions/links oracle; never calls production checker/worker."""
    if case.get('oracle_version') != ORACLE_VERSION or case.get('grader_source_sha256') != grader_source_sha256():
        raise ValueError('Grader version/source differs from this frozen bank; preserve prior grading and freeze a new revision')
    checks = []
    def check(key, value): checks.append({'id': key, 'passed': None if value is None else bool(value),
        'status': 'INCONCLUSIVE' if value is None else 'PASS' if value else 'FAIL'})
    check('actual_full_output_schema', Draft202012Validator(case['public']['output_schema']).is_valid(brief))
    if not checks[-1]['passed']:
        return {'content_correct': False, 'correct_usable_completion': False, 'checks': checks,
                'invalid_output_promoted': protected_accepted is True, 'protected_accepted': protected_accepted}
    intent = case['public']['inputs']['intent']; oracle = case['oracle']; refs = case['public']['input_refs']
    unresolved = brief['unresolved_items']; blockers = [item for item in unresolved if item['blocking']]
    check('input_identity', brief['intent_ref'] == refs['intent'] and brief['intake_ref'] == refs['intake'])
    constraints = {item['id']: item for item in brief['constraints']}
    scope_ids = {item['id'] for item in brief['in_scope']}
    check('scope_stable_ids', set(oracle['scope_ids']) <= scope_ids)
    check('constraint_stable_ids', set(oracle['constraint_ids']) <= set(constraints))
    for identifier in oracle['constraint_ids']:
        item = constraints.get(identifier, {}); text = item.get('text', '')
        source_text = next(row['text'] for row in intent['constraints'] if row['id'] == identifier)
        check('finite_constraint_entailment:' + identifier, _constraint_state(identifier, text, source_text))
    cutoff = constraints.get('c-cutoff', {})
    allowed_cutoff_refs = [refs['intent'], oracle['cutoff_source_ref'], intent['request_ref']]
    check('current_cutoff_source_attribution', bool(cutoff.get('source_refs')) and all(reference in allowed_cutoff_refs for reference in cutoff.get('source_refs', [])))
    if oracle['forbidden_cutoff_source_ref']:
        check('superseded_source_not_authority', oracle['forbidden_cutoff_source_ref'] not in cutoff.get('source_refs', []))
    targets = {item['id']: item for item in brief['target_metrics']}
    for identifier, equation in oracle['equations'].items():
        check('symbolic_equation:' + identifier, _equation_matches(targets.get(identifier, {}), equation))
    mandatory = {item['id']: item for item in brief['mandatory_requirements']}
    for source_constraint in intent['constraints']:
        identifier, source_text = source_constraint['id'], source_constraint['text']
        required = any(_constraint_state(identifier, row['text'], source_text) is True for row in mandatory.values())
        optional = any(_constraint_state(identifier, row['text'], source_text) is True for row in brief['optional_preferences'])
        check('mandatory_strength:' + identifier, True if required else False if optional else None)
    for field in ('acceptance_expectations', 'evidence_obligations'):
        linked = {identifier for item in brief[field] for identifier in item['requirement_ids']}
        check('typed_links:' + field, all(set(item['requirement_ids']) <= set(mandatory) for item in brief[field]))
        check('complete_links:' + field, set(mandatory) <= linked)
        optional_evidence = r'(?:evidence|acceptance|verification|proof)\s+(?:(?:is|are|may be|can be)\s+)?(?:optional|not required)\b|\boptional\s+(?:evidence|acceptance|verification|proof)\b|\bmay omit\s+(?:the\s+)?(?:evidence|acceptance|verification|proof)\b'
        check('evidence_not_optional:' + field, not any(re.search(optional_evidence, item['description'], re.I) for item in brief[field]))
    for target in brief['target_metrics']:
        check('target_links:' + target['id'], set(target['requirement_ids']) <= set(mandatory))
        linked_text = ' '.join(mandatory.get(identifier, {}).get('text', '') for identifier in target['requirement_ids'])
        expected_word = r'accuracy|准确' if target['id'] in ('t-accuracy', 't-conflict') else r'latency|延迟|response'
        check('meaningful_target_link:' + target['id'], re.search(expected_word, linked_text, re.I) is not None)
    expected_resources = list(case['resources'].values())
    check('exact_resources', sorted(data(ref) for ref in brief['resource_refs']) == sorted(data(ref) for ref in expected_resources))
    for filename, role in oracle['resource_roles'].items():
        check('resource_role:' + filename, any(item['resource_ref'] == case['resources'][filename] and item['role'] == role for item in brief['input_bindings']))
    names = {item['name'] for item in brief['deliverables']}
    check('requested_deliverables', {'research_report.md', 'comparisons.csv'} <= names)
    check('optional_preference_preserved', any(re.search(r'compact|简', item['text'], re.I) for item in brief['optional_preferences']))
    check('no_hardware_default_as_observation', not any(item['origin'] == 'system_default' for item in brief['constraints']))
    if oracle['blocker_expected']:
        check('honest_conflict_disposition', any(item['kind'] == 'conflicting' and re.search(r'5|five', item['description']) and re.search(r'7|seven', item['description']) for item in blockers))
    else: check('no_invented_blocking_conflict', not blockers)
    failed = any(item['passed'] is False for item in checks)
    uncertain = any(item['passed'] is None for item in checks)
    correct = False if failed else None if uncertain else True
    return {'content_correct': correct, 'correct_usable_completion': correct is True and not blockers,
        'honest_qualified_output': correct is True and bool(blockers), 'checks': checks,
        'manual_review_required': uncertain,
        'protected_accepted': protected_accepted,
        'invalid_output_promoted': None if protected_accepted is None or correct is None else protected_accepted and correct is False,
        'false_rejection': None if protected_accepted is None or correct is None else not protected_accepted and correct and not blockers,
        'scope': 'independent_finite_proposition_and_link_oracle_not_scientific_truth',
        'semantic_limit': 'Recognized finite propositions only. Unfamiliar paraphrases/scope exceptions are INCONCLUSIVE; this is not unrestricted source-entailment or whole-node validation.',
        'trial_accounting': 'Regrading the same artifact does not create a new measured trial.'}


def production_check(case, brief, store):
    """Actual check_brief diagnostic, separate from the independent content oracle."""
    from jiuwenswarm.research.checks.compiler import check_brief
    inputs = case['public']['inputs']; refs = case['public']['input_refs']
    try:
        check_brief(brief, inputs['intent'], inputs['intake'], store, intent_ref=refs['intent'],
            intake_ref=refs['intake'], policy=inputs['defaults'], policy_ref=refs['defaults'])
        return {'passed': True, 'scope': 'actual_check_brief_component_not_gate'}
    except Exception as error:
        return {'passed': False, 'error': type(error).__name__ + ': ' + str(error), 'scope': 'actual_check_brief_component_not_gate'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(freeze(parser.parse_args().output), indent=2))
