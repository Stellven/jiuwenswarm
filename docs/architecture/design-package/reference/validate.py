"""Offline design checks, not application acceptance.

Research artifacts are checked by one function per named check ID of the CC pages (see RCHECKS).
Every index example with expect invalid must be rejected by its rejected_by check.

Run: python reference/validate.py [copied-package-root]
Requires jsonschema >=4 and referencing. Does not modify the package.
"""
from pathlib import Path
import ast
import copy
import hashlib
import json
import math
import statistics
import zipfile
import re
import sys
from urllib.parse import unquote, urlsplit
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
REF = ROOT / 'reference'
EX = REF / 'examples'
errors = []

# Page roles. Change these lists, not the checks, when pages move.
PAGES = {
    'tier1': ['README.md', '1-system.md', '2-capability-capsules.md', '3-build-plan.md'],
    'tier1_word_cap': 4800,
    'synonyms_enforced': True,
    'clause_coverage': 'method/clause-coverage.md',
    'user_story_map': 'method/clause-coverage.md',
    'brief_boundary': ['README.md', '1-system.md', 'pipeline/intention-compiler.md'],
}


def require(ok, message):
    if not ok:
        errors.append(message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_example(path):
    """A JSON example, or the logical parts of a zip example (the poc-artifact-bundle contract)."""
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            value = {'archive_format': 'zip', 'entry_names': names}
            for entry, key in (('requirements.txt', 'requirements_txt'), ('poc_patch.py', 'poc_patch_py'), ('run_benchmark.py', 'run_benchmark_py')):
                if entry in names:
                    value[key] = archive.read(entry).decode('utf-8')
        return value
    return load(path)


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


catalog = load(REF / 'catalog.json')
schema_files = list((REF / 'schemas').glob('*.schema.json'))
schemas = {load(p)['$id']: load(p) for p in schema_files}
require(len(schemas) == len(schema_files) == 8, 'Expected seven critical schemas and common definitions')
registry = Registry().with_resources((key, Resource.from_contents(value)) for key, value in schemas.items())
validators = {}
for key, value in schemas.items():
    Draft202012Validator.check_schema(value)
    validators[key] = Draft202012Validator(value, registry=registry, format_checker=FormatChecker())
    for node in walk(value):
        if '$ref' in node:
            require(node['$ref'].split('#')[0] in schemas, 'Unresolved/nonlocal schema reference: ' + node['$ref'])

seen = set()
for item in catalog['contracts']:
    require(item['name'] not in seen, 'Duplicate contract ' + item['name'])
    seen.add(item['name'])
    schema = load(REF / item['schema'])
    require(schema['$id'] == item['schema_id'], 'Catalog schema identity mismatch ' + item['name'])
    require(schema['required'] == item['required_fields'], 'Catalog required-field drift ' + item['name'])
    require(bool(item['producer']) and bool(item['consumers']) and bool(item['examples']), 'Incomplete contract mapping ' + item['name'])

field_documents = {
    'intent-ir': ROOT / 'reference/intent-and-requirements.md',
    'research-brief': ROOT / 'reference/intent-and-requirements.md',
    'deterministic-check-result': ROOT / 'reference/checking.md',
    'verifier-assessment': ROOT / 'reference/checking.md',
    'gate-decision': ROOT / 'reference/checking.md',
    'capsule-declaration': ROOT / 'reference/declaration.md',
    'subnode-execution-contract': REF / 'node-execution.md',
}
for item in catalog['contracts']:
    summary = field_documents[item['name']].read_text(encoding='utf-8')
    require(item['version'] == load(REF / item['schema'])['properties']['schema_version']['const'], 'Catalog version drift')
    for key in item['required_fields']:
        require('`' + key + '`' in summary, 'Missing required field summary: ' + item['name'] + '.' + key)

index = load(EX / 'index.json')['examples']
negative_examples = []
require(len({item['path'] for item in index}) == len(index), 'Duplicate example index path')
for item in index:
    path = (EX / item['path']).resolve()
    require(path.is_relative_to(EX.resolve()) and path.exists(), 'Example path escape/missing: ' + item['path'])
    value = load_example(path)
    if item['schema_id'] and item.get('expect') != 'invalid':
        require(item['schema_id'] in validators, 'Unknown example schema ' + item['schema_id'])
        for error in validators[item['schema_id']].iter_errors(value):
            errors.append(f'{item["path"]}:{list(error.path)}: {error.message}')
    for node in walk(value):
        if set(node) == {'id', 'sha256'} and item.get('rejected_by') not in ('ref_hash_match', 'package_refs_resolve'):
            target = (EX / node['id']).resolve()
            require(target.is_relative_to(EX.resolve()) and target.is_file(), 'Example reference escape/missing: ' + node['id'])
            if target.is_file():
                require(hashlib.sha256(target.read_bytes()).hexdigest() == node['sha256'], 'Stale reference hash ' + node['id'])
        if set(node) == {'source_ref', 'start', 'end'}:
            target = EX / node['source_ref']['id']
            text = target.read_bytes().decode('utf-8')
            require(0 <= node['start'] < node['end'] <= len(text), 'Source-span bounds: ' + item['path'])


def resolved(reference):
    return load(EX / reference['id'])


def gate_issues(gate):
    result = []
    checks = resolved(gate['deterministic_result_ref'])
    # One check result covers every output of the work subnode (subject_refs, in port order).
    # A per-output decision reviews exactly one of them.
    checked = checks.get('subject_refs') or [checks['subject_ref']]
    subject = gate['output_refs'][0] if gate['output_refs'] else checks['subject_ref']
    if checks['subject_ref'] != checked[0]:
        result.append('subject_ref is not the first of subject_refs')
    if gate['action']=='advance' and (len(gate['output_refs']) != 1 or subject not in checked):
        result.append('wrong deterministic subject')
    plan = resolved(gate['check_plan_ref'])
    if {x['check_id'] for x in checks['results']} != set(plan['mandatory_deterministic']) or len(checks['results']) != len(plan['mandatory_deterministic']):
        result.append('missing or duplicate deterministic obligations')
    contract = resolved(gate['contract_ref'])
    if gate['scope_kind']!='subnode' or contract['node_contract_ref']!=gate['node_contract_ref']:result.append('wrong parent/child scope')
    if plan['contract_ref'] != gate['contract_ref'] or plan['input_refs'] != contract['input_refs'] or gate['input_refs'] != contract['input_refs']:
        result.append('wrong concrete contract or bound input inventory')
    for key in ('run_id', 'node_id', 'subnode_id', 'attempt_id'):
        if contract[key] != gate[key]:
            result.append('wrong contract scope')
    if gate['check_plan_ref'] != checks['check_plan_ref']:
        result.append('wrong check plan')
    for invocation in gate['invocation_refs']:
        observed=resolved(invocation); executed=resolved(observed['contract_ref'])
        if executed['node_contract_ref']!=gate['node_contract_ref'] or executed['run_id']!=gate['run_id']:
            result.append('wrong invocation parent scope')
    if gate['assessment_ref']:
        assessment = resolved(gate['assessment_ref'])
        context = resolved(assessment['review_context_ref'])
        if assessment['subject_ref'] != subject or context['subject_ref'] != subject:
            result.append('wrong semantic subject')
        if context['contract_ref'] != gate['contract_ref'] or context['check_plan_ref'] != gate['check_plan_ref'] or context['deterministic_result_ref'] != gate['deterministic_result_ref']:
            result.append('wrong protected review context')
        if set(context['criteria']) != set(plan['mandatory_semantic']):
            result.append('wrong assigned semantic obligations')
        findings = assessment['findings']
        if {x['criterion_id'] for x in findings} != set(context['criteria']) or len(findings) != len(context['criteria']):
            result.append('missing or duplicate criteria')
        if gate['action'] == 'advance':
            if any(x['outcome'] != 'PASS' for x in findings) or assessment['uncertainties']:
                result.append('nonpassing semantic obligations')
            if assessment['verdict'] not in ('PASS', 'PASS_WITH_KNOWN_LIMITATIONS'):
                result.append('nonadvancing assessment')
    elif gate['action'] == 'advance':
        result.append('missing required assessment')
    if gate['action'] == 'advance':
        observations=[resolved(r) for r in gate['invocation_refs'] if resolved(r)['contract_ref']==gate['contract_ref']]
        reviewer_observations=[resolved(r) for r in gate['invocation_refs'] if resolved(r)['contract_ref']!=gate['contract_ref']]
        decl_ref = contract['bindings'][0]['declaration_ref']
        if not gate['assessment_ref'] or not reviewer_observations or any(o['input_refs']!=[decl_ref, subject] or resolved(o['contract_ref'])['input_refs']!=[decl_ref, subject] for o in reviewer_observations):result.append('missing/mismatched verifier execution (the verifier sees only the declaration and the exact output)')
        expected={b['id'] for b in contract['bindings']}
        if {o['binding_id'] for o in observations}!=expected or len(observations)!=len(expected):result.append('incomplete/duplicate work binding observations')
        if any(o['outcome']!='success' and o.get('observed_runtime',True) for o in observations):result.append('failed/pending work invocation')
        # Synthetic single-output examples do not assert observed runtime execution.
        if any(r not in [x for o in observations for x in o['output_refs']] for r in gate['accepted_refs']):result.append('unobserved accepted output')
        if any(x['outcome'] != 'PASS' for x in checks['results']):
            result.append('nonpassing deterministic checks')
        if not gate['accepted_refs'] or any(x not in gate['output_refs'] for x in gate['accepted_refs']):
            result.append('unreviewed accepted output')
    elif gate['accepted_refs']:
        result.append('halt published acceptance')
    return result



def node_issues(value):
    result=[]
    bindings=value['bindings']
    if len(bindings)!=1:result.append('M1 requires one work binding')
    if value['input_refs']!=[r for p in value['inputs'] for r in p['artifact_refs']]:result.append('wrong input inventory')
    ids=[p['contract_id'] for p in value['outputs'] if p['required']]
    names=[next((x['name'] for x in catalog['contracts'] if x['schema_id']==p),None) or next((x['name'] for x in catalog['interfaces'] if x['id']==p),None) for p in ids]
    if value['required_outputs']!=names:result.append('wrong output inventory')
    known=set(schemas)|{x['id'] for x in catalog['interfaces']}|{'opaque-bytes'}
    for ports in (value['inputs'],value['outputs']):
        if len({p['name'] for p in ports})!=len(ports):result.append('duplicate port')
        if any(p['contract_id'] not in known for p in ports):result.append('unknown contract')
    for b in bindings:
        if any(b['limits'][k]>value['subnode_limits'][k] for k in b['limits']):result.append('binding exceeds subnode limit')
        parent=resolved(value['node_contract_ref'])
        if value['node_id']!=parent['node_id'] or value['run_id']!=parent['run_id'] or any(value['subnode_limits'][k]>parent['node_limits'][k] for k in value['subnode_limits']):result.append('wrong/exceeded parent scope or limit')
        authority=b['effective_authority']
        if authority['network']=='none' and authority['network_allowlist']:result.append('denied network allowlist')
        decl=resolved(b['declaration_ref'])
        if decl['identity']['kind']=='composite':result.append('composite dispatch unsupported in M1')
        for direction,key in [('inputs','inputs'),('outputs','outputs')]:
            advertised={(p['name'],p['schema_ref']) for p in decl['ports'][direction] if p['required']}
            allowed={(p['name'],p['schema_ref']) for p in decl['ports'][direction]}
            actual={(p['name'],p['contract_id']) for p in value[key]}
            if not advertised <= actual or not actual <= allowed:result.append('missing/unknown declared typed port')
    return result

for name in ('gate_decision.json',):
    for issue in gate_issues(load(EX / name)):
        errors.append(name + ': ' + issue)

brief = load(EX / 'research_brief.json')
req_ids = {x['id'] for x in brief['mandatory_requirements'] + brief['optional_preferences']}
for expectation in brief['acceptance_expectations'] + brief['evidence_obligations']:
    require(set(expectation['requirement_ids']) <= req_ids, 'Unknown Brief requirement ID')
require(not any(x['blocking'] for x in brief['unresolved_items']), 'Illustrative accepted Brief has blocking uncertainty')

# Deliberate malformed/stale/control-boundary checks do not write fixtures.
negative_count = 0
intent_key = next(k for k in schemas if ':intent-ir:' in k)
assess_key = next(k for k in schemas if ':verifier-assessment:' in k)
gate_key = next(k for k in schemas if ':gate-decision:' in k)
for mode in ('missing', 'unknown_field', 'bad_version', 'bad_extension', 'bad_enum', 'bad_reference'):
    value = copy.deepcopy(load(EX / 'intent_ir.json'))
    if mode == 'missing':
        del value['interpretation']
    elif mode == 'unknown_field':
        value['workflow_action'] = 'advance'
    elif mode == 'bad_version':
        value['schema_version'] = 'incompatible'
    elif mode == 'bad_extension':
        value['ext'] = {'unqualified': True}
    elif mode == 'bad_enum':
        value['readiness']['status'] = 'auto_advance'
    else:
        value['request_ref']['sha256'] = 'not-a-content-hash'
    require(not validators[intent_key].is_valid(value), 'Negative schema case incorrectly accepted: ' + mode)
    negative_count += 1
value = copy.deepcopy(load(EX / 'intent_assessment.json'))
value['action'] = 'halt'
require(not validators[assess_key].is_valid(value), 'Verifier may not author control action')
negative_count += 1
value = copy.deepcopy(load(EX / 'gate_decision.json'))
value['verdict'] = 'FAIL'
require(not validators[gate_key].is_valid(value), 'FAIL must not authorize advance')
negative_count += 1
for mode in ('subject', 'scope', 'acceptance', 'missing_assessment'):
    value = copy.deepcopy(load(EX / 'gate_decision.json'))
    if mode == 'subject':
        value['output_refs'] = [{'id': 'research_brief.json', 'sha256': hashlib.sha256((EX / 'research_brief.json').read_bytes()).hexdigest()}]
    elif mode == 'scope':
        value['run_id'] = 'wrong-run'
    elif mode == 'acceptance':
        value['accepted_refs'] = [value['input_refs'][0]]
    else:
        value['assessment_ref'] = None
    require(bool(gate_issues(value)), 'Negative semantic case incorrectly accepted: ' + mode)
    negative_count += 1


# Selected field contracts use a small explicit type inventory, not an unbounded
# second schema DSL. Their relational behavior is checked separately below.
field_catalog = load(REF / 'field-contracts.json')
interfaces = {item['id']: item for item in field_catalog['interfaces']}
types = field_catalog['types']
interface_types = {item['type_name']: item for item in field_catalog['interfaces'] if item.get('type_name')}
primitive_types = {'string','integer','number','boolean','sha256','object','markdown'}
def contract_view(item):
    mapping = next(x for x in catalog['interfaces'] if x['id'] == item['id'])
    target = (REF / mapping['document'].split('#')[0]).resolve()
    if not target.is_relative_to(REF.resolve()) or not target.is_file():
        require(False, 'Missing/escaping authoritative contract view')
        return ''
    return target.read_text(encoding='utf-8')
require(len(interfaces) == len(field_catalog['interfaces']), 'Duplicate field-contract ID')
require(set(interfaces) == {x['id'] for x in catalog['interfaces']}, 'Catalog/field interface mismatch')
known_contracts = set(schemas) | set(interfaces) | {'opaque-bytes'}

def field_errors(value, fields, prefix=''):
    result = []
    if not isinstance(value, dict):
        return [prefix + ': expected object']
    if 'schema_version' in fields and value.get('schema_version') != re.search(r'\d+\.\d+\.\d+', fields['schema_version']['meaning']).group():
        result.append(prefix + ': incompatible version')
    for key in set(value) - set(fields) - {'ext'}:
        result.append(prefix + ': unknown core field ' + key)
    for key, info in fields.items():
        if key not in value:
            if info['required']:
                result.append(prefix + ': missing ' + key)
            continue
        result += type_errors(value[key], info['type'], prefix + '.' + key)
        result += constraint_errors(value[key], info, prefix + '.' + key)
    if 'ext' in value:
        ext = value['ext']
        if not isinstance(ext, dict) or any(not re.fullmatch(r'[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+', k) for k in ext):
            result.append(prefix + ': invalid namespaced extension')
    return result

def constraint_errors(value, info, prefix):
    # Optional constraint keys from field tables: enum, min, max, min_items, max_items, pattern.
    result = []
    items = value if isinstance(value, list) else [value]
    if isinstance(value, list):
        if 'min_items' in info and len(value) < info['min_items']:
            result.append(prefix + ': fewer than %s items' % info['min_items'])
        if 'max_items' in info and len(value) > info['max_items']:
            result.append(prefix + ': more than %s items' % info['max_items'])
    for item in items:
        if item is None:
            continue
        if 'enum' in info and item not in info['enum']:
            result.append(prefix + ': value not in enum')
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            if 'min' in info and item < info['min']:
                result.append(prefix + ': below minimum')
            if 'max' in info and item > info['max']:
                result.append(prefix + ': above maximum')
        if 'pattern' in info and isinstance(item, str) and not re.fullmatch(info['pattern'], item):
            result.append(prefix + ': pattern mismatch')
    return result

def type_errors(value, kind, prefix):
    if kind.startswith('nullable-'):
        return [] if value is None else type_errors(value, kind[9:], prefix)
    if kind.endswith('[]'):
        return sum((type_errors(x, kind[:-2], prefix + '[]') for x in value), []) if isinstance(value, list) else [prefix + ': expected array']
    if kind in interface_types:
        return field_errors(value, interface_types[kind]['fields'], prefix)
    if kind in types:
        return field_errors(value, types[kind]['fields'], prefix)
    valid = {'string': isinstance(value, str) and bool(value),
             'sha256': isinstance(value, str) and bool(re.fullmatch(r'[0-9a-f]{64}', value)),
             'integer': isinstance(value, int) and not isinstance(value, bool),
             'number': isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
             'boolean': isinstance(value, bool),
             'object': isinstance(value, dict)}
    return [] if valid.get(kind, False) else [prefix + ': invalid ' + kind]

for item in index:
    if item.get('field_contract_id'):
        require(item['field_contract_id'] in interfaces, 'Unknown example field contract')
        if item['field_contract_id'] not in interfaces:
            continue
        contract = interfaces[item['field_contract_id']]
        found = field_errors(load_example(EX / item['path']), contract['fields'], item['path'])
        if item.get('expect') == 'invalid':
            require(bool(item.get('rejected_by')), 'Invalid example names no rejecting check: ' + item['path'])
            negative_examples.append(item['path'])
        else:
            errors.extend(found)
for item in field_catalog['interfaces']:
    for info in item['fields'].values():
        require(info['type'].removeprefix('nullable-').removesuffix('[]') in set(types) | set(interface_types) | primitive_types, 'Unknown field type')
    require(bool(item['failure']) and bool(item['producer']) and bool(item['consumers']), 'Incomplete field ownership/behavior')
for item in index:
    value = load_example(EX / item['path'])
    if item['schema_id'] and ':capsule-declaration:' in item['schema_id']:
        for port in value['ports']['inputs'] + value['ports']['outputs']:
            require(port['schema_ref'] in known_contracts, 'Unresolved CC port contract ' + port['schema_ref'])
    if item['schema_id'] and ':subnode-execution-contract:' in item['schema_id']:
        require(not node_issues(value), 'Invalid concrete binding: ' + item['path'] + ': ' + str(node_issues(value)))

# ---------------------------------------------------------------------------
# Research chain checks. One function per named check ID of the CC pages.
# A check returns a list of failure messages. An empty list means PASS.
# Each check applies to one artifact kind (the field contract name).
# ---------------------------------------------------------------------------
RCHECKS = {}


def rcheck(kind, check_id):
    def decorate(function):
        RCHECKS.setdefault(kind, {})[check_id] = function
        return function
    return decorate


def rref_file(ref):
    return EX / ref['id']


def rref_ok(ref):
    path = rref_file(ref)
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256']


def rload(ref):
    return load(rref_file(ref))


def rrefs(value):
    """Every {id, sha256} reference in a value."""
    return [node for node in walk(value) if set(node) == {'id', 'sha256'}]


def rfield_errors(contract_id, doc):
    return field_errors(doc, interfaces[contract_id]['fields'], contract_id)


def rlines(path):
    return [x for x in path.read_text(encoding='utf-8').splitlines() if x.strip() and not x.startswith('#')]


def rbundle(manifest_ref=None):
    return zipfile.ZipFile(EX / 'poc_artifact_bundle.zip')


def rbundle_text(name):
    with zipfile.ZipFile(EX / 'poc_artifact_bundle.zip') as archive:
        return archive.read(name)


# ---- candidate set (Search)
CS = 'candidate-set'


@rcheck(CS, 'candidate_set_schema')
def _(d, path):
    return rfield_errors('candidate-set:field-contract:2', d)


@rcheck(CS, 'idea_count')
def _(d, path):
    return [] if 1 <= len(d['ideas']) <= 3 else ['idea count %d is outside 1 to 3' % len(d['ideas'])]


@rcheck(CS, 'idea_ids_unique')
def _(d, path):
    ideas = [x['idea_id'] for x in d['ideas']]
    cites = [x['id'] for x in d['citations']]
    return [] if len(set(ideas)) == len(ideas) and len(set(cites)) == len(cites) else ['duplicate idea or citation ID']


@rcheck(CS, 'idea_citations_resolve')
def _(d, path):
    ids = {x['id'] for x in d['citations']}
    return ['idea %s has no resolvable citation' % x['idea_id'] for x in d['ideas'] if not x['citation_ids'] or not set(x['citation_ids']) <= ids]


@rcheck(CS, 'scope_binding')
def _(d, path):
    if not rref_ok(d['scope_ref']):
        return ['scope_ref does not resolve']
    scope = rload(d['scope_ref'])
    return [] if scope['brief_ref'] == d['brief_ref'] else ['brief_ref differs from the scope brief_ref']


@rcheck(CS, 'brief_binding')
def _(d, path):
    return [] if rref_ok(d['brief_ref']) else ['brief_ref does not resolve']


@rcheck(CS, 'queries_within_bounds')
def _(d, path):
    scope = rload(d['scope_ref'])
    q = d['queries']
    bad = []
    if not 1 <= len(q) <= scope['max_queries']:
        bad.append('query count outside 1 to max_queries')
    if len(set(q)) != len(q):
        bad.append('duplicate query')
    bad += ['query length outside 3 to 200: ' + x for x in q if not 3 <= len(x) <= 200]
    return bad


@rcheck(CS, 'connector_outcomes')
def _(d, path):
    scope = rload(d['scope_ref'])
    rows = d['connector_outcomes']
    bad = []
    if sorted(x['connector'] for x in rows) != sorted(scope['connectors']):
        bad.append('connector rows differ from the scope connectors')
    for row in rows:
        count = sum(1 for c in d['citations'] if c['connector'] == row['connector'])
        if row['citations_captured'] != count or (row['status'] == 'unavailable' and count):
            bad.append('citations_captured mismatch for ' + row['connector'])
    return bad


@rcheck(CS, 'citation_source_resolves')
def _(d, path):
    return ['source does not resolve: ' + c['id'] for c in d['citations'] if not rref_ok(c['source_ref'])]


@rcheck(CS, 'excerpt_matches_source')
def _(d, path):
    bad = []
    for c in d['citations']:
        if not rref_file(c['source_ref']).is_file():
            bad.append('missing source ' + c['id'])
            continue
        text = rref_file(c['source_ref']).read_bytes().decode('utf-8')
        if text[c['char_start']:c['char_end']] != c['excerpt']:
            bad.append('excerpt differs from source text: ' + c['id'])
    return bad


@rcheck(CS, 'excerpt_hash')
def _(d, path):
    return ['excerpt hash mismatch: ' + c['id'] for c in d['citations'] if hashlib.sha256(c['excerpt'].encode('utf-8')).hexdigest() != c['excerpt_sha256']]


@rcheck(CS, 'citation_query_ran')
def _(d, path):
    used = {x['connector'] for x in d['connector_outcomes'] if x['status'] == 'used'}
    return ['citation %s query or connector not valid' % c['id'] for c in d['citations'] if c['query'] not in d['queries'] or c['connector'] not in used]


@rcheck(CS, 'hit_limit')
def _(d, path):
    scope = rload(d['scope_ref'])
    seen = {}
    for c in d['citations']:
        if c['connector'] != 'local_documents':
            seen.setdefault((c['connector'], c['query']), set()).add(c['source_ref']['id'])
    return ['too many sources for %s' % (k,) for k, v in seen.items() if len(v) > scope['max_hits_per_query']]


# ---- screening result and opportunity card (Screening)
SR = 'screening-result'
OC = 'opportunity-card'
DIMS = ('novelty', 'feasibility', 'compute_alignment')


def rcandidate(d):
    return rload(d['candidate_ref'])


@rcheck(SR, 'screening_result_schema')
def _(d, path):
    return rfield_errors('screening-result:field-contract:2', d)


@rcheck(SR, 'candidate_binding')
def _(d, path):
    if not rref_ok(d['candidate_ref']) or not rref_ok(d['brief_ref']):
        return ['candidate_ref or brief_ref does not resolve']
    return [] if rcandidate(d)['brief_ref'] == d['brief_ref'] else ['candidate set serves another Brief']


@rcheck(SR, 'rubric_pinned')
def _(d, path):
    return [] if rref_ok(d['rubric_ref']) else ['rubric_ref hash differs from the pinned rubric']


@rcheck(SR, 'scores_cover_candidates')
def _(d, path):
    ids = [x['idea_id'] for x in d['scores']]
    want = sorted(x['idea_id'] for x in rcandidate(d)['ideas'])
    return [] if sorted(ids) == want else ['scores do not cover the candidate ideas exactly once']


@rcheck(SR, 'score_range')
def _(d, path):
    return ['score out of range for %s.%s' % (s['idea_id'], k) for s in d['scores'] for k in DIMS if not (isinstance(s[k], int) and 1 <= s[k] <= 5)]


@rcheck(SR, 'score_total_sum')
def _(d, path):
    bad = ['total is not the sum for ' + s['idea_id'] for s in d['scores'] if s['total'] != sum(s[k] for k in DIMS)]
    totals = {s['idea_id']: s['total'] for s in d['scores']}
    bad += ['ranking total differs for ' + r['idea_id'] for r in d['ranking'] if totals.get(r['idea_id']) != r['total']]
    return bad


@rcheck(SR, 'score_citations_in_idea')
def _(d, path):
    ideas = {x['idea_id']: set(x['citation_ids']) for x in rcandidate(d)['ideas']}
    return ['score cites a citation its idea does not: ' + s['idea_id'] for s in d['scores'] if not set(s['citation_ids']) <= ideas.get(s['idea_id'], set())]


@rcheck(SR, 'dependency_filter')
def _(d, path):
    rubric = rload(d['rubric_ref'])
    ideas = {x['idea_id']: x for x in rcandidate(d)['ideas']}
    bad = []
    for s in d['scores']:
        idea = ideas.get(s['idea_id'])
        if not idea:
            continue
        text = ' '.join([idea['title'], idea['summary']] + idea['assumptions'] + idea['risks']).lower()
        hits = {dep['id'] for dep in rubric['forbidden_dependencies'] if any(t in text for t in dep['match_terms'])}
        if not hits <= set(s['dependency_flags']):
            bad.append('term match flag missing for ' + s['idea_id'])
        if s['eligible'] != (not s['dependency_flags']):
            bad.append('eligible flag disagrees with flags for ' + s['idea_id'])
    return bad


@rcheck(SR, 'disposition_consistency')
def _(d, path):
    bad = []
    if sum(1 for s in d['scores'] if s['disposition'] == 'selected') != 1:
        bad.append('not exactly one selected idea')
    for s in d['scores']:
        if (s['disposition'] == 'rejected') == s['eligible']:
            bad.append('rejected does not match eligible for ' + s['idea_id'])
    if sorted(r['idea_id'] for r in d['ranking']) != sorted(s['idea_id'] for s in d['scores'] if s['disposition'] in ('selected', 'eligible')):
        bad.append('ranking rows are not the selected and eligible ideas')
    return bad


@rcheck(SR, 'ranking_deterministic')
def _(d, path):
    rows = sorted((s for s in d['scores'] if s['eligible']), key=lambda s: (-s['total'], s['idea_id']))
    want = [{'rank': i + 1, 'idea_id': s['idea_id'], 'total': s['total']} for i, s in enumerate(rows)]
    return [] if d['ranking'] == want else ['ranking differs from the recomputed order']


@rcheck(SR, 'selected_is_top1')
def _(d, path):
    return [] if d['ranking'] and d['selected_idea_id'] == d['ranking'][0]['idea_id'] else ['selected idea is not rank 1']


@rcheck(OC, 'opportunity_card_schema')
def _(d, path):
    return rfield_errors('opportunity-card:field-contract:2', d)


@rcheck(OC, 'selected_in_candidates')
def _(d, path):
    ids = {x['idea_id'] for x in rcandidate(d)['ideas']}
    screening = rload(d['screening_ref'])
    bad = []
    if d['idea_id'] not in ids:
        bad.append('card idea is not a candidate idea')
    if screening['selected_idea_id'] not in ids:
        bad.append('selected idea is not a candidate idea')
    return bad


@rcheck(OC, 'card_matches_selection')
def _(d, path):
    screening = rload(d['screening_ref'])
    ideas = {x['idea_id']: x for x in rcandidate(d)['ideas']}
    score = next((s for s in screening['scores'] if s['idea_id'] == d['idea_id']), None)
    idea = ideas.get(d['idea_id'])
    if score is None or idea is None:
        return ['card idea has no score row or candidate idea']
    bad = []
    if d['idea_id'] != screening['selected_idea_id']:
        bad.append('card idea is not the selected idea')
    if d['title'] != idea['title'] or d['citation_ids'] != idea['citation_ids'] or d['assumptions'] != idea['assumptions'] or d['risks'] != idea['risks']:
        bad.append('card text differs from the selected idea')
    if d['scores'] != {k: score[k] for k in DIMS + ('total',)} or d['rank'] != 1:
        bad.append('card scores or rank differ from the screening result')
    if rcandidate(d) != rload(screening['candidate_ref']) or screening['candidate_ref'] != d['candidate_ref']:
        bad.append('card and screening result use different candidate sets')
    return bad


@rcheck(OC, 'card_constraints_carried')
def _(d, path):
    brief = rload(d['brief_ref'])
    need = [x['text'] for x in brief['constraints'] + brief['mandatory_requirements']]
    return ['constraint not carried: ' + t for t in need if t not in d['constraints']]


@rcheck(OC, 'card_dispositions_complete')
def _(d, path):
    screening = rload(d['screening_ref'])
    want = sorted((s['idea_id'], s['disposition'], s['disposition_reason']) for s in screening['scores'] if s['idea_id'] != d['idea_id'])
    got = sorted((x['idea_id'], x['disposition'], x['reason']) for x in d['other_dispositions'])
    return [] if want == got else ['other_dispositions differ from the screening dispositions']


# ---- hypothesis blueprint
HB = 'hypothesis-blueprint'
LOWER = {'lt', 'le'}
HIGHER = {'gt', 'ge'}


def rregion(rule, baseline):
    """Region of treatment values for which a rule holds, as (lo, lo_closed, hi, hi_closed)."""
    t = rule['factor'] * baseline + rule['offset'] if rule['reference'] == 'baseline' else rule['offset']
    c = rule['comparator']
    inf = math.inf
    return {'lt': (-inf, False, t, False), 'le': (-inf, False, t, True), 'eq': (t, True, t, True),
            'ge': (t, True, inf, False), 'gt': (t, False, inf, False)}[c]


def roverlap(a, b):
    if a[0] > b[0]:
        lo, loc = a[0], a[1]
    elif b[0] > a[0]:
        lo, loc = b[0], b[1]
    else:
        lo, loc = a[0], a[1] and b[1]
    if a[2] < b[2]:
        hi, hic = a[2], a[3]
    elif b[2] < a[2]:
        hi, hic = b[2], b[3]
    else:
        hi, hic = a[2], a[3] and b[3]
    return lo < hi or (lo == hi and loc and hic)


def rprobes(*rules):
    return (0.001, 1.0, 1000.0) if any(r['reference'] == 'baseline' for r in rules if r) else (1.0,)


@rcheck(HB, 'blueprint_schema')
def _(d, path):
    return rfield_errors('hypothesis-blueprint:field-contract:2', d)


@rcheck(HB, 'rules_reference_declared_metrics')
def _(d, path):
    ids = [m['metric_id'] for m in d['metrics']]
    rules = [r['metric_id'] for r in d['outcome_rules']]
    return [] if sorted(ids) == sorted(rules) and len(set(ids)) == len(ids) else ['outcome rules do not map one to one onto declared metrics']


@rcheck(HB, 'dependent_variables_match_metrics')
def _(d, path):
    return [] if set(d['dependent_variables']) == {m['metric_id'] for m in d['metrics']} else ['dependent_variables differ from the metric IDs']


@rcheck(HB, 'rule_direction_consistent')
def _(d, path):
    bad = []
    direction = {m['metric_id']: m['direction'] for m in d['metrics']}
    for r in d['outcome_rules']:
        better = LOWER if direction.get(r['metric_id']) == 'lower_better' else HIGHER
        worse = HIGHER if better is LOWER else LOWER
        if r['success']['comparator'] not in better or r['falsification']['comparator'] not in worse:
            bad.append('rule direction disagrees with metric direction: ' + r['metric_id'])
    return bad


@rcheck(HB, 'boundaries_disjoint')
def _(d, path):
    bad = []
    for r in d['outcome_rules']:
        for b in rprobes(r['success'], r['falsification']):
            if roverlap(rregion(r['success'], b), rregion(r['falsification'], b)):
                bad.append('success and falsification overlap for %s at baseline %s' % (r['metric_id'], b))
                break
    return bad


@rcheck(HB, 'conditional_rule_in_middle')
def _(d, path):
    bad = []
    for r in d['outcome_rules']:
        cond = r['conditional_rule']
        if (cond is None) != (r['middle'] != 'CONDITIONALLY_ACCEPTABLE'):
            bad.append('conditional_rule and middle disagree for ' + r['metric_id'])
        if cond is not None:
            for b in rprobes(r['success'], r['falsification'], cond):
                if roverlap(rregion(cond, b), rregion(r['success'], b)) or roverlap(rregion(cond, b), rregion(r['falsification'], b)):
                    bad.append('conditional region overlaps a boundary for ' + r['metric_id'])
                    break
    return bad


@rcheck(HB, 'brief_targets_covered')
def _(d, path):
    brief = rload(d['brief_ref'])
    got = {m['target_id'] for m in d['metrics'] if m['target_id']}
    return ['Brief target not measured: ' + t['id'] for t in brief['target_metrics'] if t['id'] not in got]


@rcheck(HB, 'brief_comparison_consistent')
def _(d, path):
    brief = rload(d['brief_ref'])
    rules = {r['metric_id']: r for r in d['outcome_rules']}
    metrics = {m['target_id']: m for m in d['metrics'] if m['target_id']}
    bad = []
    for t in brief['target_metrics']:
        c = t.get('comparison')
        if not c or t['id'] not in metrics:
            continue
        s = rules[metrics[t['id']]['metric_id']]['success']
        want = {'comparator': c['comparator'], 'reference': c['reference'], 'factor': 0 if c['reference'] == 'constant' else c['value'], 'offset': c['value'] if c['reference'] == 'constant' else 0}
        if any(s[k] != want[k] for k in want):
            bad.append('success rule differs from the Brief comparison for ' + t['id'])
    return bad


@rcheck(HB, 'resource_refs_resolve')
def _(d, path):
    bad = ['ref does not resolve: ' + r['id'] for r in [d['brief_ref'], d['opportunity_ref']] + d['resource_refs'] if not rref_ok(r)]
    for r in d['resource_refs']:
        if rref_ok(r) and rload(r).get('availability') != 'available':
            bad.append('resource not available: ' + r['id'])
    return bad


@rcheck(HB, 'baseline_identity_resolves')
def _(d, path):
    b = d['baseline_identity']
    if b['resource_ref'] not in d['resource_refs'] or not rref_ok(b['resource_ref']):
        return ['baseline resource is not one of resource_refs or does not resolve']
    snap = rload(b['resource_ref'])
    bad = [] if snap['revision'] == b['revision'] else ['baseline revision differs from the snapshot']
    if b['entry_point'] not in [f['path'] for f in snap['files']]:
        bad.append('entry_point is not a snapshot file')
    return bad


@rcheck(HB, 'environment_from_resources')
def _(d, path):
    envs = [rload(r).get('environment_ref') for r in d['resource_refs'] if rref_ok(r)]
    return [] if envs and all(e and e == d['environment_ref'] for e in envs) else ['environment_ref differs from the resources']


@rcheck(HB, 'constraints_carried')
def _(d, path):
    brief = rload(d['brief_ref'])
    return ['constraint not carried: ' + c['text'] for c in brief['constraints'] if c['text'] not in d['constraints']]


# ---- POC manifest and build receipt (Builder)
PM = 'poc-manifest'
REQUIRED_FILES = ['requirements.txt', 'poc_patch.py', 'run_benchmark.py']
PIN = re.compile(r'^([a-z0-9][a-z0-9._-]*)==([0-9]+(?:\.[0-9]+)*)$')


def rzip_names():
    with zipfile.ZipFile(EX / 'poc_artifact_bundle.zip') as archive:
        return archive.namelist()


def rrequirements():
    return [x.strip() for x in rbundle_text('requirements.txt').decode('utf-8').splitlines() if x.strip() and not x.startswith('#')]


@rcheck(PM, 'manifest_schema')
def _(d, path):
    return rfield_errors('poc-manifest:field-contract:2', d)


@rcheck(PM, 'required_files_present')
def _(d, path):
    names = rzip_names()
    paths = [f['path'] for f in d['files']]
    bad = []
    if sorted(names) != sorted(REQUIRED_FILES) or any(x != x.lower() or '/' in x or '..' in x for x in names):
        bad.append('bundle entries are not exactly the three required files')
    if sorted(paths) != sorted(REQUIRED_FILES) or len(set(paths)) != len(paths):
        bad.append('manifest files are not exactly the three required files')
    return bad


@rcheck(PM, 'bundle_hash_matches')
def _(d, path):
    bad = [] if hashlib.sha256((EX / 'poc_artifact_bundle.zip').read_bytes()).hexdigest() == d['archive_ref']['sha256'] else ['archive hash differs']
    for f in d['files']:
        if f['path'] in rzip_names() and hashlib.sha256(rbundle_text(f['path'])).hexdigest() != f['artifact_ref']['sha256']:
            bad.append('entry hash differs: ' + f['path'])
    return bad


@rcheck(PM, 'dependencies_pinned')
def _(d, path):
    bad = []
    lines = rrequirements()
    parsed = []
    for x in lines:
        m = PIN.match(x)
        if not m:
            bad.append('requirements line is not name==version: ' + x)
        else:
            parsed.append({'name': m.group(1), 'version': m.group(2)})
    for dep in d['dependencies']:
        if not re.fullmatch(r'[0-9]+(\.[0-9]+)*', dep['version']):
            bad.append('dependency %s has no exact version: %s' % (dep['name'], dep['version']))
    if d['dependencies'] != parsed:
        bad.append('dependencies differ from requirements.txt')
    return bad


@rcheck(PM, 'requirements_within_lock')
def _(d, path):
    lock = rload(d['environment_ref'])
    allowed = set(rlines(rref_file(lock['requirements_ref'])))
    return ['pin not in the environment lock: ' + x for x in rrequirements() if x not in allowed]


@rcheck(PM, 'environment_unchanged')
def _(d, path):
    bp = rload(d['blueprint_ref'])
    return [] if bp['environment_ref'] == d['environment_ref'] else ['manifest and blueprint name different environments']


@rcheck(PM, 'blueprint_unchanged')
def _(d, path):
    return [] if rref_ok(d['blueprint_ref']) else ['blueprint hash differs from the frozen blueprint']


BR = 'build-receipt'
FORBIDDEN = lambda: [x.strip() for x in (EX / 'build_receipt_forbidden_modules.txt').read_text(encoding='utf-8').splitlines() if x.strip() and not x.startswith('#')]


def rimports(source):
    tree = ast.parse(source)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split('.')[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split('.')[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('__import__', 'exec', 'eval'):
            found.add(node.func.id)
        elif isinstance(node, ast.Name) and node.id == 'importlib':
            found.add('importlib')
    return found


def rformat_scan(source, metric_ids):
    tree = ast.parse(source)
    prints = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'print']
    json_prints = [n for n in prints if len(n.args) == 1 and isinstance(n.args[0], ast.Call) and isinstance(n.args[0].func, ast.Attribute)
                   and n.args[0].func.attr == 'dumps' and isinstance(n.args[0].func.value, ast.Name) and n.args[0].func.value.id == 'json']
    metrics_key = False
    for call in json_prints:
        for node in ast.walk(call):
            if isinstance(node, ast.Dict) and any(isinstance(k, ast.Constant) and k.value == 'metrics' for k in node.keys):
                metrics_key = True
    consts = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    missing = [m for m in metric_ids if m not in consts]
    other_prints = len(prints) - len(json_prints)
    ok = len(json_prints) == 1 and metrics_key and not missing and other_prints == 0
    return {'result': 'pass' if ok else 'fail', 'json_print_calls': len(json_prints), 'metrics_key_found': metrics_key, 'missing_metric_ids': missing}


@rcheck(BR, 'build_receipt_schema')
def _(d, path):
    return rfield_errors('build-receipt:field-contract:1', d)


@rcheck(BR, 'bundle_hash_matches')
def _(d, path):
    m = rload(d['manifest_ref'])
    bad = [] if d['archive_ref'] == m['archive_ref'] and d['blueprint_ref'] == m['blueprint_ref'] and d['environment_ref'] == m['environment_ref'] else ['receipt refs differ from the manifest']
    for f in d['file_checks']:
        if f['path'] in rzip_names() and hashlib.sha256(rbundle_text(f['path'])).hexdigest() != f['sha256']:
            bad.append('receipt hash differs: ' + f['path'])
    if sorted(f['path'] for f in d['file_checks']) != sorted(f['path'] for f in m['files']):
        bad.append('receipt files differ from the manifest files')
    return bad


@rcheck(BR, 'syntax_check')
def _(d, path):
    bad = []
    for f in d['file_checks']:
        if not f['path'].endswith('.py'):
            continue
        try:
            compile(rbundle_text(f['path']), f['path'], 'exec')
            actual = 'pass'
        except SyntaxError:
            actual = 'fail'
        if actual != f['syntax_result']:
            bad.append('syntax result differs for ' + f['path'])
    return bad


@rcheck(BR, 'forbidden_modules_absent')
def _(d, path):
    bad = []
    forbidden = set(FORBIDDEN())
    anyhit = False
    for f in d['file_checks']:
        if not f['path'].endswith('.py'):
            continue
        hits = sorted((rimports(rbundle_text(f['path']).decode('utf-8')) & forbidden) | (rimports(rbundle_text(f['path']).decode('utf-8')) & {'__import__', 'importlib', 'exec', 'eval'}))
        anyhit = anyhit or bool(hits)
        if sorted(f['forbidden_imports']) != hits:
            bad.append('forbidden import list differs for ' + f['path'])
    if d['forbidden_scan_result'] != ('fail' if anyhit else 'pass'):
        bad.append('forbidden_scan_result differs from the scan')
    return bad


@rcheck(BR, 'output_log_format')
def _(d, path):
    bp = rload(d['blueprint_ref'])
    want = rformat_scan(rbundle_text('run_benchmark.py').decode('utf-8'), [m['metric_id'] for m in bp['metrics']])
    return [] if d['output_format_check'] == want else ['output_format_check differs from the static scan: %s' % (want,)]


@rcheck(BR, 'dependencies_pinned')
def _(d, path):
    m = rload(d['manifest_ref'])
    pinned = all(re.fullmatch(r'[0-9]+(\.[0-9]+)*', x['version']) for x in d['dependencies'])
    bad = [] if d['dependencies'] == m['dependencies'] else ['receipt dependencies differ from the manifest']
    if d['dependencies_all_pinned'] != pinned:
        bad.append('dependencies_all_pinned differs from the dependencies')
    return bad


@rcheck(BR, 'build_receipt_ready')
def _(d, path):
    ok = (all(f['syntax_result'] in ('pass', 'not_applicable') for f in d['file_checks']) and d['forbidden_scan_result'] == 'pass'
          and d['output_format_check']['result'] == 'pass' and d['dependencies_all_pinned'])
    bad = []
    if d['trial_executed'] or d['packages_installed']:
        bad.append('a trial or install is recorded')
    if (d['readiness'] == 'READY') != ok or (d['readiness'] == 'READY') != (not d['readiness_reasons']):
        bad.append('readiness disagrees with the evidence')
    return bad


# ---- benchmark payload and receipts (Research Benchmark)
BP = 'benchmark-payload'
EPS = 1e-9


def raggregate(rule, values):
    if rule == 'min':
        return min(values)
    if rule == 'max':
        return max(values)
    if rule == 'mean':
        return sum(values) / len(values)
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def rclose(a, b):
    return abs(a - b) <= EPS * max(1.0, abs(a), abs(b))


def rbench(d):
    return {'blueprint': rload(d['blueprint_ref']), 'receipt': rload(d['execution_receipt_ref']), 'prov': rload(d['provisioning_receipt_ref']),
            'manifest': rload(d['poc_ref']), 'empirical': rload(next(r for r in d['raw_evidence_refs'] if r['id'] == rload(d['execution_receipt_ref'])['empirical_results_ref']['id']))}


@rcheck(BP, 'benchmark_payload_schema')
def _(d, path):
    x = rbench(d)
    return (rfield_errors('benchmark-payload:field-contract:2', d) + rfield_errors('execution-receipt:field-contract:1', x['receipt']) + rfield_errors('provisioning-receipt:field-contract:1', x['prov']))


@rcheck(BP, 'refs_resolve')
def _(d, path):
    return ['ref does not resolve: ' + r['id'] for r in rrefs(d) + rrefs(rload(d['execution_receipt_ref'])) if not rref_ok(r)]


@rcheck(BP, 'protocol_matches_blueprint')
def _(d, path):
    x = rbench(d)
    bp = x['blueprint']
    bad = []
    if not rref_ok(d['blueprint_ref']) or d['blueprint_ref'] != x['manifest']['blueprint_ref'] or x['receipt']['blueprint_ref'] != d['blueprint_ref']:
        bad.append('blueprint_ref differs between payload, receipt and manifest')
    if d['repeat_count'] != bp['repeat_count'] or d['seed'] != bp['seed']:
        bad.append('repeat_count or seed differs from the blueprint')
    if any(r['seed'] != bp['seed'] for r in x['receipt']['runs']):
        bad.append('a run seed differs from the registered seed')
    if sorted(r['id'] + r['sha256'] for r in d['resource_refs']) != sorted(r['id'] + r['sha256'] for r in bp['resource_refs']):
        bad.append('resource_refs differ from the blueprint')
    declared = {m['metric_id']: m for m in bp['metrics']}
    for m in d['metrics']:
        b = declared.get(m['metric_id'])
        if not b or b['unit'] != m['unit'] or b['aggregation'] != m['aggregation']:
            bad.append('metric differs from the blueprint: ' + m['metric_id'])
    return bad


@rcheck(BP, 'metric_coverage')
def _(d, path):
    bp = rload(d['blueprint_ref'])
    ids = [m['metric_id'] for m in d['metrics']]
    return [] if sorted(ids) == sorted(m['metric_id'] for m in bp['metrics']) else ['payload metrics are not exactly the blueprint metrics']


@rcheck(BP, 'metric_value_or_reason')
def _(d, path):
    bad = []
    for m in d['metrics']:
        for side in ('baseline', 'treatment'):
            s = m[side]
            if (s['value'] is None) == (s['unmeasured_reason'] is None):
                bad.append('%s %s has both or neither value and reason' % (m['metric_id'], side))
    return bad


@rcheck(BP, 'baseline_before_treatment')
def _(d, path):
    x = rbench(d)
    runs = sorted(x['receipt']['runs'], key=lambda r: r['sequence'])
    order = [r['role'] for r in runs]
    bad = []
    if d['run_order'] != order:
        bad.append('payload run_order differs from the receipt order')
    if len(d['run_order']) != 2 * d['repeat_count'] or d['run_order'] != sorted(d['run_order'], key=lambda r: r != 'baseline'):
        bad.append('a treatment run precedes a baseline run in run_order')
    if order != sorted(order, key=lambda r: r != 'baseline'):
        bad.append('a treatment run precedes a baseline run in the receipt')
    starts = [r['started_at'] for r in runs]
    if starts != sorted(starts):
        bad.append('run start times are not in sequence order')
    return bad


@rcheck(BP, 'baseline_unmodified')
def _(d, path):
    x = rbench(d)
    bp = x['blueprint']
    bad = []
    for r in x['receipt']['runs']:
        want = bp['baseline_identity']['resource_ref'] if r['role'] == 'baseline' else x['manifest']['archive_ref']
        if r['subject_ref'] != want:
            bad.append('run %d subject differs from the registered subject' % r['sequence'])
    return bad


@rcheck(BP, 'environment_lock_match')
def _(d, path):
    x = rbench(d)
    refs = [d['environment_lock_ref'], x['blueprint']['environment_ref'], x['manifest']['environment_ref'], x['prov']['environment_lock_ref']]
    bad = [] if all(r == refs[0] for r in refs) else ['payload, blueprint, manifest and provisioning name different locks']
    lock = rload(d['environment_lock_ref'])
    wanted = sorted(rlines(rref_file(lock['requirements_ref'])))
    got = sorted('%s==%s' % (p['name'], p['installed_version']) for p in x['prov']['packages'])
    if wanted != got or any(p['installed_version'] != p['locked_version'] for p in x['prov']['packages']):
        bad.append('installed packages differ from the lock')
    return bad


@rcheck(BP, 'hardware_inventory_captured')
def _(d, path):
    r = rload(d['execution_receipt_ref'])
    hw = r['hardware_inventory']
    bad = [] if all(run['hardware_ref'] == hw['hardware_id'] for run in r['runs']) else ['a run uses other hardware']
    if hw['gpu_count'] > 0 and (hw['gpu_model'] is None or hw['gpu_memory_mb'] is None):
        bad.append('GPU fields missing')
    if hw['captured_at'] > min(run['started_at'] for run in r['runs']):
        bad.append('hardware captured after the first run')
    return bad


@rcheck(BP, 'raw_repeats_present')
def _(d, path):
    x = rbench(d)
    bad = []
    seqs = {e['sequence'] for e in x['empirical']['runs']}
    for r in x['receipt']['runs']:
        if r['sequence'] not in seqs or not rref_ok(r['stdout_ref']) or not rref_ok(r['stderr_ref']):
            bad.append('run %d lacks stored output or an empirical entry' % r['sequence'])
    for m in d['metrics']:
        for side in ('baseline', 'treatment'):
            if m[side]['value'] is not None and len(m[side]['repeats']) != d['repeat_count']:
                bad.append('%s %s lacks repeats' % (m['metric_id'], side))
    need = {x['receipt']['empirical_results_ref']['id']} | {r[k]['id'] for r in x['receipt']['runs'] for k in ('stdout_ref', 'stderr_ref')}
    if not need <= {r['id'] for r in d['raw_evidence_refs']}:
        bad.append('raw_evidence_refs miss receipt evidence')
    return bad


@rcheck(BP, 'values_match_empirical_results')
def _(d, path):
    x = rbench(d)
    bad = []
    emp = {e['sequence']: e['metrics'] for e in x['empirical']['runs']}
    seq = {}
    for r in x['receipt']['runs']:
        seq[(r['role'], r['repeat_index'])] = r
    for m in d['metrics']:
        for side in ('baseline', 'treatment'):
            for i, value in enumerate(m[side]['repeats']):
                r = seq.get((side, i))
                if r is None or emp.get(r['sequence'], {}).get(m['metric_id']) != value:
                    bad.append('%s %s repeat %d differs from empirical_results' % (m['metric_id'], side, i))
    for r in x['receipt']['runs']:
        lines = rlines(rref_file(r['stdout_ref']))
        try:
            printed = json.loads(lines[r['repeat_index']])['metrics']
        except (IndexError, ValueError, KeyError):
            bad.append('run %d stdout has no output log line' % r['sequence'])
            continue
        if printed != emp.get(r['sequence']):
            bad.append('run %d stdout differs from empirical_results' % r['sequence'])
    return bad


@rcheck(BP, 'arithmetic_consistent')
def _(d, path):
    bad = []
    for m in d['metrics']:
        for side in ('baseline', 'treatment'):
            s = m[side]
            if s['value'] is not None and (not s['repeats'] or not rclose(s['value'], raggregate(m['aggregation'], s['repeats']))):
                bad.append('%s %s value is not the aggregate of the repeats' % (m['metric_id'], side))
        both = m['baseline']['value'] is not None and m['treatment']['value'] is not None
        if both != (m['delta'] is not None) or (both and not rclose(m['delta'], m['treatment']['value'] - m['baseline']['value'])):
            bad.append('%s delta is not treatment minus baseline' % m['metric_id'])
    return bad


@rcheck(BP, 'measurement_within_declared_range')
def _(d, path):
    bounds = {m['metric_id']: (m['valid_min'], m['valid_max']) for m in rload(d['blueprint_ref'])['metrics']}
    bad = []
    for m in d['metrics']:
        lo, hi = bounds[m['metric_id']]
        for side in ('baseline', 'treatment'):
            values = list(m[side]['repeats']) + ([m[side]['value']] if m[side]['value'] is not None else [])
            for x in values:
                if (lo is not None and x < lo) or (hi is not None and x > hi):
                    bad.append('%s %s has %s outside [%s, %s]' % (m['metric_id'], side, x, lo, hi))
                    break
    return bad


@rcheck(BP, 'network_policy_respected')
def _(d, path):
    p = rload(d['provisioning_receipt_ref'])
    ok = p['status'] == 'succeeded' and p['unlisted_network_requests'] == 0 and (p['network_policy_used'] != 'none' or not p['network_allowlist'])
    return [] if ok else ['provisioning did not respect the network policy']


# ---- evaluation verdict (Scientific Evaluation)
EV = 'evaluation-verdict'


def rholds(rule, baseline, treatment):
    t = rule['factor'] * baseline + rule['offset'] if rule['reference'] == 'baseline' else rule['offset']
    c = rule['comparator']
    if c == 'eq':
        return rclose(treatment, t)
    return {'lt': treatment < t, 'le': treatment <= t, 'ge': treatment >= t, 'gt': treatment > t}[c]


def rthreshold(rule, baseline):
    return rule['factor'] * baseline + rule['offset'] if rule['reference'] == 'baseline' else rule['offset']


def rrecompute(d):
    """Recompute findings and the overall classification per aggregation rule m1_conjunctive_v1."""
    bp = rload(d['blueprint_ref'])
    payload = rload(d['benchmark_ref'])
    rules = {r['metric_id']: r for r in bp['outcome_rules']}
    pm = {m['metric_id']: m for m in payload['metrics']}
    findings = []
    for m in bp['metrics']:
        r = rules[m['metric_id']]
        p = pm[m['metric_id']]
        b, t = p['baseline']['value'], p['treatment']['value']
        if b is None or t is None:
            findings.append({'metric_id': m['metric_id'], 'classification': 'INCONCLUSIVE', 'rule_applied': 'unmeasured', 'threshold': None})
            continue
        succ, fals = rholds(r['success'], b, t), rholds(r['falsification'], b, t)
        if succ and fals:
            findings.append({'metric_id': m['metric_id'], 'classification': 'DEFECT', 'rule_applied': 'defect', 'threshold': None})
        elif succ:
            findings.append({'metric_id': m['metric_id'], 'classification': 'PASS', 'rule_applied': 'success', 'threshold': rthreshold(r['success'], b)})
        elif fals:
            findings.append({'metric_id': m['metric_id'], 'classification': 'FAIL', 'rule_applied': 'falsification', 'threshold': rthreshold(r['falsification'], b)})
        elif r['middle'] == 'CONDITIONALLY_ACCEPTABLE' and r['conditional_rule'] and rholds(r['conditional_rule'], b, t):
            findings.append({'metric_id': m['metric_id'], 'classification': 'CONDITIONALLY_ACCEPTABLE', 'rule_applied': 'conditional', 'threshold': rthreshold(r['conditional_rule'], b)})
        else:
            findings.append({'metric_id': m['metric_id'], 'classification': 'INCONCLUSIVE', 'rule_applied': 'middle', 'threshold': None})
    classes = [f['classification'] for f in findings]
    if d['plausibility']['status'] == 'implausible':
        overall = 'INCONCLUSIVE'
    elif 'FAIL' in classes:
        overall = 'FAIL'
    elif 'INCONCLUSIVE' in classes:
        overall = 'INCONCLUSIVE'
    elif 'CONDITIONALLY_ACCEPTABLE' in classes:
        overall = 'CONDITIONALLY_ACCEPTABLE'
    else:
        overall = 'PASS'
    return findings, overall, payload


@rcheck(EV, 'evaluation_verdict_schema')
def _(d, path):
    return rfield_errors('evaluation-verdict:field-contract:2', d)


@rcheck(EV, 'refs_match_inputs')
def _(d, path):
    payload = rload(d['benchmark_ref']) if rref_ok(d['benchmark_ref']) else None
    bad = [] if rref_ok(d['brief_ref']) and rref_ok(d['blueprint_ref']) and payload else ['a verdict ref does not resolve']
    if payload and payload['blueprint_ref'] != d['blueprint_ref']:
        bad.append('payload and verdict name different blueprints')
    return bad


@rcheck(EV, 'blueprint_rules_disjoint')
def _(d, path):
    findings, overall, payload = rrecompute(d)
    return ['success and falsification both hold for ' + f['metric_id'] for f in findings if f['classification'] == 'DEFECT']


@rcheck(EV, 'finding_coverage')
def _(d, path):
    bp = rload(d['blueprint_ref'])
    return [] if [f['metric_id'] for f in d['findings']] == [m['metric_id'] for m in bp['metrics']] else ['findings are not one per blueprint metric in order']


@rcheck(EV, 'rule_recomputation')
def _(d, path):
    findings, overall, payload = rrecompute(d)
    bad = []
    got = {f['metric_id']: f for f in d['findings']}
    for f in findings:
        g = got.get(f['metric_id'])
        if not g or g['classification'] != f['classification'] or g['rule_applied'] != f['rule_applied'] or (g['threshold'] is None) != (f['threshold'] is None) or (f['threshold'] is not None and not rclose(g['threshold'], f['threshold'])):
            bad.append('finding differs from the recomputed one: ' + f['metric_id'])
            continue
        p = {m['metric_id']: m for m in payload['metrics']}[f['metric_id']]
        if g['baseline_value'] != p['baseline']['value'] or g['treatment_value'] != p['treatment']['value']:
            bad.append('finding values differ from the payload: ' + f['metric_id'])
    if d['classification'] != overall:
        bad.append('classification %s differs from the recomputed %s' % (d['classification'], overall))
    unmeasured = any(f['rule_applied'] == 'unmeasured' for f in findings)
    if (d['completeness']['status'] == 'incomplete') != unmeasured:
        bad.append('completeness status differs from the payload')
    if bool(d['blockers']) != (unmeasured or d['plausibility']['status'] == 'implausible'):
        bad.append('blockers differ from the blocker condition')
    return bad


@rcheck(EV, 'registered_rule_only')
def _(d, path):
    bp = rload(d['blueprint_ref'])
    rules = {r['metric_id']: r for r in bp['outcome_rules']}
    bad = []
    for f in d['findings']:
        r = rules.get(f['metric_id'])
        if f['rule_applied'] == 'conditional' and not (r and r['conditional_rule']):
            bad.append('conditional finding without a registered conditional rule: ' + f['metric_id'])
        if (f['classification'] == 'CONDITIONALLY_ACCEPTABLE') != (f['rule_applied'] == 'conditional'):
            bad.append('CONDITIONALLY_ACCEPTABLE appears without the conditional rule: ' + f['metric_id'])
        if f['rule_applied'] in ('success', 'falsification') and r:
            rule = r[f['rule_applied']]
            m = re.fullmatch(r'(success|falsification): treatment (<=|>=|<|>|==) ([0-9.eE+-]+) \* baseline \+ ([0-9.eE+-]+)', f['rule_text'])
            if rule['reference'] == 'baseline' and (not m or m.group(2) != OP_TEXT[rule['comparator']] or not rclose(float(m.group(3)), rule['factor']) or not rclose(float(m.group(4)), rule['offset'])):
                bad.append('rule_text does not restate the registered rule: ' + f['metric_id'])
    return bad


OP_TEXT = {'lt': '<', 'le': '<=', 'eq': '==', 'ge': '>=', 'gt': '>'}


# ---- delivery manifest and report (Delivery)
DM = 'delivery-manifest'
SECTIONS = ['1. Objective', '2. Opportunity and citations', '3. Hypothesis and registered criteria', '4. Method and POC', '5. Results: baseline vs treatment',
            '6. Scientific verdict and reasoning', '7. Limitations and risks', '8. Follow-up recommendations', '9. Reproducibility']
ROLES_ONE = ['report', 'brief', 'candidate_set', 'screening', 'opportunity', 'hypothesis', 'poc_manifest', 'poc_bundle', 'benchmark', 'verdict']


def rreport(d):
    text = rref_file(d['report_ref']).read_text(encoding='utf-8')
    parts = re.split(r'^## (.+)$', text, flags=re.M)
    heads = parts[1::2]
    bodies = parts[2::2]
    return text, heads, dict(zip(heads, bodies))


def rtable(body):
    rows = [[c.strip() for c in line.strip().strip('|').split('|')] for line in body.splitlines() if line.strip().startswith('|')]
    return rows[2:] if len(rows) >= 2 else []


@rcheck(DM, 'delivery_manifest_schema')
def _(d, path):
    bad = rfield_errors('delivery-manifest:field-contract:2', d)
    roles = [f['role'] for f in d['files']]
    bad += ['role %s is not listed exactly once' % r for r in ROLES_ONE if roles.count(r) != 1]
    if roles.count('gate_decision') < 1 or roles.count('raw_evidence') < 2 or roles.count('environment') < 2:
        bad.append('role coverage is incomplete')
    return bad


@rcheck(DM, 'required_sections')
def _(d, path):
    text, heads, bodies = rreport(d)
    bad = [] if heads == SECTIONS else ['report headings are not the nine required sections in order: %s' % heads]
    bad += ['empty section ' + h for h, b in bodies.items() if not b.strip()]
    return bad


@rcheck(DM, 'recommendation_labeling')
def _(d, path):
    text, heads, bodies = rreport(d)
    bad = []
    for h, b in bodies.items():
        if h != '8. Follow-up recommendations' and 'Recommendation:' in b:
            bad.append('Recommendation label outside section 8')
    sec = bodies.get('8. Follow-up recommendations', '')
    bad += ['section 8 bullet without the label' for x in sec.splitlines() if x.startswith('- ') and not x.startswith('- Recommendation:')]
    return bad


@rcheck(DM, 'ref_resolves')
def _(d, path):
    return ['ref does not resolve: ' + r['id'] for r in rrefs(d) if not rref_file(r).is_file()]


@rcheck(DM, 'ref_hash_match')
def _(d, path):
    bad = ['hash mismatch for ' + r['id'] for r in rrefs(d) if rref_file(r).is_file() and not rref_ok(r)]
    rep = [f for f in d['files'] if f['role'] == 'report']
    if rep and rep[0]['artifact_ref'] != d['report_ref']:
        bad.append('report_ref differs from the report file entry')
    return bad


@rcheck(DM, 'manifest_completeness')
def _(d, path):
    bad = []
    need = ['candidate_set', 'screening_result', 'opportunity_card', 'hypothesis_blueprint', 'poc_manifest', 'benchmark_payload', 'evaluation_verdict']
    names = [r['id'] for r in d['artifact_refs']]
    bad += ['artifact_refs miss ' + n for n in need if n + '.json' not in names]
    if len(set(names)) != len(names):
        bad.append('duplicate artifact ref')
    v = rload(d['verdict_ref'])
    if v['brief_ref'] != d['brief_ref']:
        bad.append('brief_ref differs from the verdict brief_ref')
    if d['verdict_ref'] not in d['artifact_refs']:
        bad.append('verdict_ref is not in artifact_refs')
    index = load(EX / 'gate_decision_index.json')
    if d['gate_decision_refs'] != [e['gate_decision_ref'] for e in index['entries']]:
        bad.append('gate_decision_refs differ from the gate_decision_index')
    return bad


@rcheck(DM, 'results_table_matches_payload')
def _(d, path):
    text, heads, bodies = rreport(d)
    payload = None
    for r in d['artifact_refs']:
        if r['id'] == 'benchmark_payload.json':
            payload = rload(r)
    rows = {row[0]: row for row in rtable(bodies.get('5. Results: baseline vs treatment', ''))}
    bad = []
    if payload is None:
        return ['no benchmark payload in the manifest']
    if set(rows) != {m['metric_id'] for m in payload['metrics']}:
        bad.append('results rows differ from the payload metrics')
    for m in payload['metrics']:
        row = rows.get(m['metric_id'])
        if not row:
            continue
        try:
            got = [float(row[2]), float(row[3]), float(row[4])]
        except (ValueError, IndexError):
            bad.append('results row is not numeric: ' + m['metric_id'])
            continue
        want = [m['baseline']['value'], m['treatment']['value'], m['delta']]
        if any(w is None or not rclose(g, w) for g, w in zip(got, want)):
            bad.append('results row differs from the payload: ' + m['metric_id'])
    return bad


@rcheck(DM, 'criteria_match_blueprint')
def _(d, path):
    text, heads, bodies = rreport(d)
    bp = next(rload(r) for r in d['artifact_refs'] if r['id'] == 'hypothesis_blueprint.json')
    rows = {row[0]: row for row in rtable(bodies.get('3. Hypothesis and registered criteria', ''))}
    want = {m['metric_id']: (m['unit'], m['aggregation']) for m in bp['metrics']}
    got = {k: (v[1], v[2]) for k, v in rows.items()}
    return [] if want == got else ['criteria table differs from the blueprint metrics']


def rverdict_lines(v):
    return ['Classification: ' + v['classification'], 'Completeness: ' + v['completeness']['status'], 'Plausibility: ' + v['plausibility']['status']]


@rcheck(DM, 'verdict_matches_evaluation')
def _(d, path):
    text, heads, bodies = rreport(d)
    v = rload(d['verdict_ref'])
    sec = [x for x in bodies.get('6. Scientific verdict and reasoning', '').splitlines() if x.strip()]
    bad = [] if sec[:3] == rverdict_lines(v) else ['verdict, completeness or plausibility lines differ from the saved verdict']
    lines = {x.split(':')[0][2:] for x in sec if x.startswith('- ')}
    for f in v['findings']:
        if '- %s: %s. %s' % (f['metric_id'], f['classification'], f['rationale']) not in sec:
            bad.append('finding line differs from the verdict: ' + f['metric_id'])
    return bad


@rcheck(DM, 'carried_content')
def _(d, path):
    text, heads, bodies = rreport(d)
    v = rload(d['verdict_ref'])
    card = next(rload(r) for r in d['artifact_refs'] if r['id'] == 'opportunity_card.json')
    s7 = bodies.get('7. Limitations and risks', '')
    s8 = bodies.get('8. Follow-up recommendations', '')
    s2 = bodies.get('2. Opportunity and citations', '')
    bad = ['not carried in section 7: ' + x for x in v['blockers'] + v['residual_risks'] + v['completeness']['notes'] + v['plausibility']['notes'] if '- ' + x not in s7]
    bad += ['follow-up not carried: ' + x for x in v['followups'] if '- Recommendation: ' + x not in s8]
    bad += ['risk not carried: ' + x for x in card['risks'] if x not in s7]
    bad += ['citation not carried: ' + x for x in card['citation_ids'] if x not in s2]
    return bad


@rcheck(DM, 'reproducibility_pins')
def _(d, path):
    text, heads, bodies = rreport(d)
    rows = {row[1]: row[2] for row in rtable(bodies.get('9. Reproducibility', ''))}
    need = ['lifecycle_research_brief.json', 'hypothesis_blueprint.json', 'poc_manifest.json', 'poc_artifact_bundle.zip', 'environment_lock.json', 'run_configuration.json', 'benchmark_payload.json', 'evaluation_verdict.json']
    manifest = {f['artifact_ref']['id']: f['artifact_ref']['sha256'] for f in d['files']}
    bad = ['pin row missing: ' + n for n in need if n not in rows]
    bad += ['pin row differs from the manifest: ' + n for n in need if n in rows and manifest.get(n) != rows[n]]
    return bad


@rcheck(DM, 'negative_result_delivered')
def _(d, path):
    v = rload(d['verdict_ref'])
    if v['classification'] in ('FAIL', 'INCONCLUSIVE'):
        hidden = [x for x in d['missing_evidence'] if x.get('blocking')]
        return ['blocking missing evidence hides a negative result'] if hidden else []
    return []


# ---- plan proposal, static template and run plan (Planner and binder)
def rplan_env(d):
    lib = rload(d['library_snapshot_ref']) if 'library_snapshot_ref' in d else load(EX / 'library_snapshot.json')
    inv = rload(d['resource_inventory_ref']) if 'resource_inventory_ref' in d else load(EX / 'resource_inventory.json')
    pol = rload(d['policy_ref']) if 'policy_ref' in d else load(EX / 'plan_policy.json')
    brief = rload(d['brief_ref']) if 'brief_ref' in d else load(EX / 'lifecycle_research_brief.json')
    return lib, inv, pol, brief


SELECTORS = {'all_mandatory_requirements': ('mandatory_requirements', 'requirement', 'requirement_ids'),
             'all_deliverables': ('deliverables', 'deliverable', 'deliverable_ids'),
             'all_evidence_obligations': ('evidence_obligations', 'evidence_obligation', None)}


def rexpand(d, brief, allow_selectors):
    """The binder step that expands the selectors of a static template against the accepted Brief.
    Returns (tags, coverage, problems). tags maps node_id to (requirement_ids, deliverable_ids), expanded.
    Planner proposals and run plans may not hold a selector."""
    problems, tags, coverage = [], {}, []
    for n in d['nodes']:
        out = {'requirement_ids': [], 'deliverable_ids': []}
        for field in out:
            for tag in n[field]:
                sel = SELECTORS.get(tag)
                if sel is None or sel[2] != field:
                    out[field].append(tag)
                elif not allow_selectors:
                    problems.append('selector %s outside a static template (node %s)' % (tag, n['node_id']))
                else:
                    out[field] += [x['id'] for x in brief[sel[0]] if x['id'] not in out[field]]
        tags[n['node_id']] = (out['requirement_ids'], out['deliverable_ids'])
    seen = set()
    for c in d['coverage']:
        if ('selector' in c) == ('item_id' in c) or ('item_id' in c) != ('item_kind' in c):
            problems.append('a coverage entry sets exactly one of item_id with item_kind, or selector')
            continue
        if 'selector' in c:
            if not allow_selectors:
                problems.append('selector %s outside a static template' % c['selector'])
                continue
            key, kind, _ = SELECTORS[c['selector']]
            entries = [{'item_id': x['id'], 'item_kind': kind, 'node_ids': list(c['node_ids'])} for x in brief[key]]
        else:
            entries = [c]
        for e in entries:
            if (e['item_id'], e['item_kind']) in seen:
                problems.append('coverage of %s appears twice' % e['item_id'])
            seen.add((e['item_id'], e['item_kind']))
            coverage.append(e)
    return tags, coverage, problems


def rlib_entry(lib, cc):
    return next((e for e in lib['entries'] if e['cc_name'] == cc['cc_name'] and e['cc_version'] == cc['cc_version'] and e['declaration_sha256'] == cc['declaration_sha256']), None)


HOST_RECORDS = {'screening_rubric', 'build_receipt', 'gate_decision_index', 'screening_result', 'execution_receipt', 'provisioning_receipt', 'environment_lock', 'run_configuration'}


def rplan_checks(kind, contract_id, structure_id):
    @rcheck(kind, structure_id)
    def _(d, path):
        return rfield_errors(contract_id, d)

    @rcheck(kind, 'acyclicity')
    def _(d, path):
        by = {n['node_id']: n for n in d['nodes']}
        pending, done = set(by), set()
        while pending:
            ready = {n for n in pending if set(by[n]['predecessors']) <= done}
            if not ready:
                return ['predecessors graph has a cycle or an unknown predecessor']
            done |= ready
            pending -= ready
        return []

    @rcheck(kind, 'delivery_leaf_coverage')
    def _(d, path):
        # A leaf is a node that no other node lists in predecessors. M1 allows exactly one leaf.
        # It must run research.delivery, carry every Brief deliverable, and have exactly one
        # research.evaluation ancestor.
        by = {n['node_id']: n for n in d['nodes']}
        named = {p for n in d['nodes'] for p in n['predecessors']}
        leaves = [n for n in by if n not in named]
        out = []
        for stage in rplan_env(d)[2].get('required_stages', []):
            count = sum(1 for n in d['nodes'] if n['cc']['cc_name'] == stage)
            if count != 1:
                out.append('required stage %s runs in %d nodes, not 1' % (stage, count))
        if len(leaves) != 1:
            return out + ['M1 needs exactly one leaf, found %d' % len(leaves)]
        leaf = by[leaves[0]]
        if leaf['cc']['cc_name'] != 'research.delivery':
            out.append('leaf %s is not a Delivery node' % leaf['node_id'])
        brief = rplan_env(d)[3]
        tags = rexpand(d, brief, kind == 'static-template')[0]
        missing = {x['id'] for x in brief['deliverables']} - set(tags[leaf['node_id']][1])
        if missing:
            out.append('deliverables not on the leaf: %s' % sorted(missing))
        seen, stack = set(), list(leaf['predecessors'])
        while stack:
            n = stack.pop()
            if n in seen or n not in by:
                continue
            seen.add(n)
            stack.extend(by[n]['predecessors'])
        if sum(by[n]['cc']['cc_name'] == 'research.evaluation' for n in seen) != 1:
            out.append('leaf needs exactly one Scientific Evaluation ancestor')
        return out

    @rcheck(kind, 'library_membership')
    def _(d, path):
        lib = rplan_env(d)[0]
        bad = []
        for n in d['nodes']:
            e = rlib_entry(lib, n['cc'])
            if e is None or not e['selectable_by_planner']:
                bad.append('node %s names a CC that is not selectable in the library' % n['node_id'])
        return bad

    @rcheck(kind, 'port_type_compatibility')
    def _(d, path):
        lib = rplan_env(d)[0]
        by = {n['node_id']: n for n in d['nodes']}
        bad = []
        for n in d['nodes']:
            e = rlib_entry(lib, n['cc'])
            if e is None:
                continue
            ports_in = {p['name']: p for p in e['input_ports']}
            ports_out = {p['name']: p for p in e['output_ports']}
            names_in = [i['name'] for i in n['inputs']]
            if len(set(names_in)) != len(names_in) or any(p['required'] and p['name'] not in names_in for p in e['input_ports']):
                bad.append('node %s misses a required input or repeats one' % n['node_id'])
            if any(p['required'] and p['name'] not in [o['name'] for o in n['outputs']] for p in e['output_ports']):
                bad.append('node %s misses a required output' % n['node_id'])
            for o in n['outputs']:
                if o['name'] not in ports_out or ports_out[o['name']]['artifact_type'] != o['artifact_type']:
                    bad.append('node %s output %s is not a library port' % (n['node_id'], o['name']))
            for i in n['inputs']:
                port = ports_in.get(i['name'])
                if port is None or port['artifact_type'] != i['artifact_type'] or (port['required'] and not i['required']):
                    bad.append('node %s input %s is not a library port' % (n['node_id'], i['name']))
                    continue
                if i['source_kind'] == 'host_record' and i['run_input_key'] != i['artifact_type']:
                    bad.append('host record key differs from the port type: ' + i['name'])
                if i['source_kind'] == 'future_output' and i['future']:
                    f = i['future']
                    prod = by.get(f['producer_node'])
                    pe = rlib_entry(lib, prod['cc']) if prod else None
                    out = next((p for p in pe['output_ports'] if p['name'] == f['port']), None) if pe else None
                    if out is None or not (f['artifact_type'] == i['artifact_type'] == out['artifact_type'] and out['schema_ref'] == port['schema_ref']):
                        bad.append('incompatible binding %s.%s from %s' % (n['node_id'], i['name'], f['producer_node']))
        return bad

    @rcheck(kind, 'dependency_closure')
    def _(d, path):
        lib, inv, pol, brief = rplan_env(d)
        by = {n['node_id']: n for n in d['nodes']}
        keys = {r['resource_key'] for r in inv['resources']}
        bad = []
        for n in d['nodes']:
            for i in n['inputs']:
                if (i['source_kind'] == 'future_output') != (i['future'] is not None) or (i['source_kind'] in ('accepted_ref', 'host_record')) != (i['run_input_key'] is not None):
                    bad.append('source fields disagree for %s.%s' % (n['node_id'], i['name']))
                if i['source_kind'] == 'accepted_ref' and i['run_input_key'] not in ({'brief', 'search_scope'} | keys):
                    bad.append('unknown run input key ' + str(i['run_input_key']))
                if i['source_kind'] == 'host_record' and i['run_input_key'] not in HOST_RECORDS:
                    bad.append('unknown host record key ' + str(i['run_input_key']))
                if i['source_kind'] == 'future_output':
                    f = i['future']
                    prod = by.get(f['producer_node'])
                    if prod is None or f['producer_node'] == n['node_id'] or f['producer_node'] not in n['predecessors'] or f['port'] not in [o['name'] for o in prod['outputs']]:
                        bad.append('future input of %s.%s is not closed' % (n['node_id'], i['name']))
            if n['node_id'] in n['predecessors'] or any(p not in by for p in n['predecessors']):
                bad.append('predecessors of %s are not nodes of the plan' % n['node_id'])
        return bad

    @rcheck(kind, 'brief_coverage')
    def _(d, path):
        lib, inv, pol, brief = rplan_env(d)
        reqs = {r['id'] for r in brief['mandatory_requirements']}
        dels = {x['id'] for x in brief['deliverables']}
        bad = []
        tags, coverage, problems = rexpand(d, brief, kind == 'static-template')
        bad += problems
        cov = {(c['item_id'], c['item_kind']): set(c['node_ids']) for c in coverage}
        for n in d['nodes']:
            if not tags[n['node_id']][0] and not tags[n['node_id']][1]:
                bad.append('node %s has no coverage tag' % n['node_id'])
            if not set(tags[n['node_id']][0]) <= reqs or not set(tags[n['node_id']][1]) <= dels:
                bad.append('node %s tags an item that is not in the Brief' % n['node_id'])
        for kind_name, ids, pos in (('requirement', reqs, 0), ('deliverable', dels, 1)):
            for item in ids:
                nodes = {nid for nid, t in tags.items() if item in t[pos]}
                if not nodes or cov.get((item, kind_name)) != nodes:
                    bad.append('coverage of %s is missing or not the inverse of the node tags' % item)
        evid = {x['id'] for x in brief['evidence_obligations']}
        for (item, kind_name), nodes in cov.items():
            if kind_name == 'evidence_obligation' and (item not in evid or not nodes <= set(tags)):
                bad.append('evidence coverage of %s names an unknown obligation or node' % item)
        return bad

    @rcheck(kind, 'effects_within_policy')
    def _(d, path):
        lib, inv, pol, brief = rplan_env(d)
        bad = []
        for n in d['nodes']:
            e = rlib_entry(lib, n['cc'])
            if e and (e['effect_class'] not in pol['allowed_effect_classes'] or (e['network_mode'] != 'none' and not pol['allow_network'])):
                bad.append('node %s is outside the effect or network policy' % n['node_id'])
        return bad

    @rcheck(kind, 'resource_feasibility')
    def _(d, path):
        lib, inv, pol, brief = rplan_env(d)
        res = {r['resource_key']: r for r in inv['resources']}
        bad = []
        for n in d['nodes']:
            e = rlib_entry(lib, n['cc'])
            for need in (e['resource_needs'] if e else []):
                r = res.get(need['resource_key'])
                if r is None or not r['available'] or (need['min_quantity'] and (r['quantity'] or 0) < need['min_quantity']):
                    bad.append('node %s lacks resource %s' % (n['node_id'], need['resource_key']))
        return bad

    @rcheck(kind, 'budget_ceilings')
    def _(d, path):
        lib, inv, pol, brief = rplan_env(d)
        bad = []
        for n in d['nodes']:
            e = rlib_entry(lib, n['cc'])
            if e and any(n['limits'][k] > e['max_limits'][k] for k in n['limits']):
                bad.append('node %s asks for more than the library ceiling' % n['node_id'])
        lim = d['limits']
        if lim['time_s'] < sum(n['limits']['time_s'] for n in d['nodes']) or lim['model_calls'] < sum(n['limits']['model_calls'] for n in d['nodes']) or lim['memory_mb'] < max(n['limits']['memory_mb'] for n in d['nodes']):
            bad.append('plan limits are below the node limits')
        if any(lim[k] > pol['aggregate_limits'][k] for k in lim) or len(d['nodes']) > pol['max_nodes']:
            bad.append('plan limits or node count exceed the policy')
        return bad

    @rcheck(kind, 'mandatory_check_bundle_present')
    def _(d, path):
        lib = rplan_env(d)[0]
        bad = []
        for n in d['nodes']:
            e = rlib_entry(lib, n['cc'])
            if e is not None and e['check_pins'] is None:
                bad.append('node %s uses a CC version with no admitted check bundle and profile' % n['node_id'])
        return bad


rplan_checks('plan-proposal', 'plan-proposal:field-contract:3', 'plan_proposal_schema')
rplan_checks('static-template', 'static-template:field-contract:1', 'template_structure')
rplan_checks('run-plan', 'run-plan:field-contract:1', 'run_plan_structure')


def kahn_order(nodes):
    order, taken = [], set()
    while len(order) < len(nodes):
        ready = [n['node_id'] for n in nodes if n['node_id'] not in taken and set(n['predecessors']) <= taken]
        if not ready:
            return None
        order.append(ready[0])
        taken.add(ready[0])
    return order


for name in ('run_plan.json',):
    rp = load(EX / name)
    require(rp['topological_order'] == kahn_order(rload(rp['source_ref'])['nodes']), 'Run plan order is not the Kahn order with the source-list tie rule: ' + name)


@rcheck('plan-proposal', 'proposal_references')
def _(d, path):
    return ['proposal ref does not resolve: ' + r['id'] for r in rrefs(d) if not rref_ok(r)]


@rcheck('run-plan', 'run_plan_binding')
def _(d, path):
    lib = rload(d['library_snapshot_ref'])
    bad = []
    if not d['frozen']:
        bad.append('run plan is not frozen')
    order = d['topological_order']
    pos = {n: i for i, n in enumerate(order)}
    if sorted(order) != sorted(n['node_id'] for n in d['nodes']) or any(pos[p] >= pos[n['node_id']] for n in d['nodes'] for p in n['predecessors']):
        bad.append('topological_order is not a valid order')
    for n in d['nodes']:
        e = rlib_entry(lib, n['cc'])
        if e is None or n['check_pins'] != e['check_pins'] or n['effect_class'] != e['effect_class']:
            bad.append('node %s pins or effect class differ from the library' % n['node_id'])
        for i in n['inputs']:
            if (i['source_kind'] == 'accepted_ref') != (i['accepted_ref'] is not None):
                bad.append('accepted_ref is not bound exactly for accepted_ref inputs: %s.%s' % (n['node_id'], i['name']))
    src = rload(d['source_ref'])
    if d['plan_source'] != src['plan_source'] or [n['node_id'] for n in d['nodes']] != [n['node_id'] for n in src['nodes']]:
        bad.append('run plan differs from its source')
    return bad


@rcheck('run-plan', 'acceptance_advances')
def _(d, path):
    acc = rload(d['acceptance_ref'])
    if d['plan_source'] == 'static':
        # plan_source static: the template is pre-admitted, so acceptance is a deterministic check result with no verifier
        plan = rload(acc['check_plan_ref'])
        ok = acc['subject_ref'] == d['source_ref'] and 'template_structure' in plan['mandatory_deterministic'] and not plan['mandatory_semantic']
        ok = ok and {r['check_id'] for r in acc['results']} == set(plan['mandatory_deterministic']) and all(r['outcome'] == 'PASS' for r in acc['results'])
        return [] if ok else ['static plan acceptance is not a passing deterministic result for the template']
    return [] if acc.get('action') == 'advance' else ['plan acceptance is not an advance decision']


@rcheck('run-plan', 'selectors_expanded')
def _(d, path):
    # The binder expanded every selector of the source template against the accepted Brief and recorded the result.
    src, brief = rload(d['source_ref']), rload(d['brief_ref'])
    tags, coverage, problems = rexpand(src, brief, True)
    bad = list(problems)
    if any('selector' in c for c in d['coverage']):
        bad.append('the run plan coverage still holds a selector')
    key = lambda cs: sorted((c['item_id'], c['item_kind'], tuple(c['node_ids'])) for c in cs if 'item_id' in c)
    if key(d['coverage']) != key(coverage):
        bad.append('the run plan coverage is not the expansion of the template coverage')
    for n in d['nodes']:
        if n['node_id'] in tags and (n['requirement_ids'], n['deliverable_ids']) != tags[n['node_id']]:
            bad.append('node %s tags are not the expansion of the template tags' % n['node_id'])
    return bad


# ---- library snapshot, dispatch record, plan outcome, gate decision index, search scope
DECL_FILES = {'intent.compiler': 'capsule_declaration.json', 'requirements.compiler': 'requirements_capsule.json', 'research.search': 'search_capsule.json',
              'research.screening': 'screening_capsule.json', 'research.hypothesis': 'hypothesis_capsule.json', 'research.builder': 'builder_capsule.json',
              'research.benchmark': 'research_benchmark_capsule.json', 'research.evaluation': 'scientific_evaluation_capsule.json',
              'research.delivery': 'delivery_capsule.json', 'research.verifier': 'verifier_capsule.json', 'research.planner': 'planner_capsule.json'}
DOTTED = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$')


@rcheck('library-snapshot', 'output_structure')
def _(d, path):
    return rfield_errors('library-snapshot:field-contract:1', d)


@rcheck('library-snapshot', 'library_matches_declarations')
def _(d, path):
    bad = []
    for e in d['entries']:
        f = DECL_FILES.get(e['cc_name'])
        if not f:
            bad.append('no declaration example for ' + e['cc_name'])
            continue
        decl = load(EX / f)
        if decl['identity']['version_label'] != e['cc_version'] or hashlib.sha256((EX / f).read_bytes()).hexdigest() != e['declaration_sha256']:
            bad.append('version or digest differs from the declaration: ' + e['cc_name'])
        ports = lambda L: [(p['name'], p['artifact_type'], p['schema_ref'], p['required']) for p in L]
        if ports(e['input_ports']) != ports(decl['ports']['inputs']) or ports(e['output_ports']) != ports(decl['ports']['outputs']):
            bad.append('ports differ from the declaration: ' + e['cc_name'])
        if e['effect_class'] != decl['changes']['effect_class'] or e['network_mode'] != decl['needs']['network']['mode']:
            bad.append('effect or network differs from the declaration: ' + e['cc_name'])
        if [(r['resource_key'], r['mode']) for r in e['resource_needs']] != [(r['resource_key'], r['mode']) for r in decl['needs']['resources']]:
            bad.append('resources differ from the declaration: ' + e['cc_name'])
        b = decl['budget']['per_call']
        if e['max_limits']['time_s'] != b['wall_s'] or e['max_limits']['model_calls'] not in (0, b['invocations']):
            bad.append('limits differ from the declaration budget: ' + e['cc_name'])
        pins = e['check_pins']
        if pins:
            if not DOTTED.match(pins['check_bundle_id']) or not DOTTED.match(pins['checking_profile_id']):
                bad.append('check pin identifiers are not dotted snake_case: ' + e['cc_name'])
            if pins['check_bundle_id'] != e['cc_name'] + '.checks' or pins['checking_profile_id'] != e['cc_name'] + '.profile':
                bad.append('check pin identifiers differ from the bundle_id and profile_id pattern: ' + e['cc_name'])
    return bad


@rcheck('library-snapshot', 'check_pins_match_records')
def _(d, path):
    bad = []
    for e in d['entries']:
        p = e['check_pins']
        if p is None:
            continue
        for fname, key, idkey, vkey in (('check_bundle.json', 'check_bundle_sha256', 'check_bundle_id', 'check_bundle_version'), ('checking_profile.json', 'checking_profile_sha256', 'checking_profile_id', 'checking_profile_version'), ('intent_checking_profile.json', 'checking_profile_sha256', 'checking_profile_id', 'checking_profile_version'), ('requirements_checking_profile.json', 'checking_profile_sha256', 'checking_profile_id', 'checking_profile_version'), ('science_checking_profile.json', 'checking_profile_sha256', 'checking_profile_id', 'checking_profile_version'), ('planner_checking_profile.json', 'checking_profile_sha256', 'checking_profile_id', 'checking_profile_version')):
            if not (EX / fname).exists():
                continue
            rec = load(EX / fname)
            if rec['target_cc_name'] == e['cc_name']:
                ident = rec['bundle_id'] if 'bundle_id' in rec else rec['profile_id']
                if hashlib.sha256((EX / fname).read_bytes()).hexdigest() != p[key] or ident != p[idkey] or rec['version'] != p[vkey]:
                    bad.append('pin differs from the %s record for %s' % (fname, e['cc_name']))
    return bad


@rcheck('dispatch-record', 'output_structure')
def _(d, path):
    bad = rfield_errors('dispatch-record:field-contract:2', d)
    if d['phase'] == 'pre_plan':
        if d['run_plan_ref'] is not None or d['node_id'] not in ('intention_compiler', 'planner'):
            bad.append('a pre-plan record names no run plan and a pre-plan node')
    else:
        if d['run_plan_ref'] is None:
            bad.append('a planned record needs a run plan')
        else:
            plan = rload(d['run_plan_ref'])
            node = next((n for n in plan['nodes'] if n['node_id'] == d['node_id']), None)
            if node is None or node['cc'] != d['cc'] or node['check_pins'] != d['check_pins']:
                bad.append('cc or check pins differ from the run plan node')
            elif sorted(x['name'] for x in d['bound_input_refs']) != sorted(i['name'] for i in node['inputs']):
                bad.append('bound inputs differ from the run plan node')
    if d['attempt_id'] != '%s-a%d' % (d['node_id'], d['attempt']):
        bad.append('attempt_id is not <node_id>-a<attempt>')
    node_gate = rload(d['gate_decision_ref']) if d['gate_decision_ref'] else None
    if node_gate is not None:
        if node_gate['scope_kind'] != 'node' or any(node_gate[k] != d[k] for k in ('run_id', 'node_id', 'attempt_id')) or node_gate['node_contract_ref'] != d['node_contract_ref']:
            bad.append('gate_decision_ref is not the node-scope decision of this attempt')
        elif d['outcome'] == 'accepted' and (node_gate['action'] != 'advance' or node_gate['internal_decision_refs'] != d['output_gate_decision_refs'] or node_gate['accepted_refs'] != d['output_refs']):
            bad.append('accepted record differs from its node-scope decision')
    return bad


@rcheck('plan-outcome', 'output_structure')
def _(d, path):
    bad = rfield_errors('plan-outcome:field-contract:1', d)
    if d['trigger'] != 'planner_reported_infeasible' and d['source_ref'] is None:
        bad.append('source_ref is null without a Planner report')
    if (d['trigger'] != 'planner_reported_infeasible') != (d['check_result_ref'] is not None):
        bad.append('check_result_ref must be set exactly when a check ran')
    elif d['check_result_ref'] is not None:
        res = rload(d['check_result_ref'])
        failing = {r['check_id'] for r in res['results'] if r['outcome'] != 'PASS'}
        if d['trigger'] == 'proposal_rejected' and not {x['check_id'] for x in d['reasons'] if x['check_id']} <= failing:
            bad.append('a reason names a check that did not fail in the check result')
    if d['attempt_depth'] < 2 and d['linked_attempt_id'] is None:
        bad.append('a linked Intention Compiler attempt is required before the depth limit')
    if d['attempt_depth'] > 2 or (d['attempt_depth'] == 2 and d['linked_attempt_id'] is not None):
        bad.append('a request gets at most two plan attempts, so no third attempt is linked (PLT-8)')
    return bad


@rcheck('plan-outcome', 'ref_hash_match')
def _(d, path):
    return ['ref does not resolve: ' + r['id'] for r in rrefs(d) if not rref_ok(r)]


@rcheck('gate-decision-index', 'output_structure')
def _(d, path):
    bad = rfield_errors('gate-decision-index:field-contract:1', d)
    plan = rload(d['run_plan_ref'])
    nodes = {n['node_id'] for n in plan['nodes']}
    ids = [e['node_id'] for e in d['entries']]
    if len(set(ids)) != len(ids) or not set(ids) <= nodes:
        bad.append('entries repeat a node or name a node outside the run plan')
    for e in d['entries']:
        g = rload(e['gate_decision_ref'])
        if g['action'] != 'advance' or g['scope_kind'] != 'node' or g['node_id'] != e['node_id']:
            bad.append('entry is not an advancing node-scope gate decision of its node')
    return bad


@rcheck('search-scope', 'output_structure')
def _(d, path):
    bad = rfield_errors('search-scope:field-contract:1', d)
    if 'local_documents' in d['connectors'] and not d['local_document_refs']:
        bad.append('local_documents permitted without local document refs')
    if len(set(d['topic_hints'])) != len(d['topic_hints']) or any(not 3 <= len(x) <= 100 for x in d['topic_hints']):
        bad.append('topic_hints violate their constraints')
    if 'queries' in d:
        bad.append('a search scope must hold no queries')
    return bad


# ---- check bundle and checking profile (Verifier)
def rdecl_outputs(name):
    return [p['name'] for p in load(EX / DECL_FILES[name])['ports']['outputs']]


@rcheck('check-bundle', 'output_structure')
def _(d, path):
    return rfield_errors('check-bundle:field-contract:1', d)


@rcheck('check-bundle', 'bundle_has_blocking_schema_check')
def _(d, path):
    bad = []
    for port in rdecl_outputs(d['target_cc_name']):
        ok = any(c['check_id'] == port + '_schema' and c['target_port'] == port and c['reads'] == ['output'] and c['blocking'] for c in d['checks'])
        if not ok:
            bad.append('no blocking %s_schema check for output port %s' % (port, port))
    if len({c['check_id'] for c in d['checks']}) != len(d['checks']):
        bad.append('duplicate check_id')
    outs = rdecl_outputs(d['target_cc_name'])
    bad += ['target_port is not an output port: ' + c['target_port'] for c in d['checks'] if c['target_port'] not in outs]
    return bad


@rcheck('checking-profile', 'output_structure')
def _(d, path):
    return rfield_errors('checking-profile:field-contract:1', d)


FIDELITY_WORDS = ('fidelity', 'preservation', 'faithful', 'source_support')


@rcheck('checking-profile', 'criterion_answerable_from_declaration_and_output')
def _(d, path):
    bad = ['criterion %s is not answerable from the declaration and output' % c['criterion_id'] for c in d['criteria'] if c['answerable_from'] != 'declaration_and_output']
    bad += ['criterion %s means fidelity or source support' % c['criterion_id'] for c in d['criteria'] if any(w in c['criterion_id'] for w in FIDELITY_WORDS)]
    ids = {c['criterion_id']: c for c in d['criteria']}
    for g in ('declared_output_conformance', 'internal_consistency', 'limitations_consistency'):
        if g not in ids or not ids[g]['blocking'] or ids[g]['target_port'] is not None:
            bad.append('generic criterion %s is missing, not blocking or not asked for every output' % g)
    outs = rdecl_outputs(d['target_cc_name'])
    bad += ['target_port is not an output port: ' + str(c['target_port']) for c in d['criteria'] if c['target_port'] is not None and c['target_port'] not in outs]
    if len(ids) != len(d['criteria']):
        bad.append('duplicate criterion_id')
    return bad


# ---- platform records: intake, lock, check plan, node contract, observation, run bundle, clients, profile, admission, results
# Check IDs are defined on field-catalog.md, checking.md and the Research Benchmark page.
MODEL_BRIDGE = 'audited_model_bridge'


@rcheck('qualified-intake', 'request_text_decodable')
def _(d, path):
    bad = []
    for ref in [d['request_ref']] + d['source_refs']:
        try:
            rref_file(ref).read_bytes().decode('utf-8')
        except (UnicodeDecodeError, OSError):
            bad.append('%s does not decode as UTF-8' % ref['id'])
    return bad


@rcheck('qualified-intake', 'intake_refs_unique')
def _(d, path):
    ids = [r['id'] for r in d['source_refs']] + [r['id'] for r in d['resource_refs']]
    return ['duplicate or shared source/resource ref'] if len(ids) != len(set(ids)) else []


@rcheck('qualified-intake', 'prior_outcome_is_plan_infeasible')
def _(d, path):
    if d.get('prior_plan_outcome_ref') is None:
        return []
    outcome = rload(d['prior_plan_outcome_ref'])
    if outcome.get('outcome') != 'plan_infeasible' or outcome.get('next_stage') != 'intention_compiler':
        return ['prior_plan_outcome_ref is not a plan_infeasible outcome']
    return []


@rcheck('qualified-intake', 'intake_files_are_uploads')
def _(d, path):
    uploads = [rload(r) for r in d['upload_refs']]
    bad = ['upload %s is not uploaded' % u['id'] for u in uploads if u['status'] != 'uploaded']
    texts = {u['text_sha256'] for u in uploads}
    contents = {u['content_sha256'] for u in uploads}
    bad += ['source ref %s is not the text of an upload' % r['id'] for r in d['source_refs'] if r['sha256'] not in texts]
    bad += ['resource ref %s is not an upload' % r['id'] for r in d['resource_refs'] if r['sha256'] not in contents]
    return bad


UPLOAD_TYPES = {'docs': 'reference_document', 'repo': 'project_asset', 'datasets': 'validation_data'}


@rcheck('client-upload', 'upload_kind_matches_type')
def _(d, path):
    bad = []
    if UPLOAD_TYPES.get(d['kind']) != d['resource_type']:
        bad.append('resource_type does not follow kind')
    if d['stored_path'] != 'workspace/input/%s/%s/%s' % (d['kind'], d['scope_id'], d['filename']):
        bad.append('stored_path does not follow kind, scope_id and filename')
    if (d['text_sha256'] is not None) != (d['kind'] == 'docs'):
        bad.append('text_sha256 is non-null exactly for docs')
    return bad


@rcheck('client-upload', 'upload_deleted_consistent')
def _(d, path):
    return [] if (d['deleted_at'] is not None) == (d['status'] == 'deleted') else ['deleted_at and status disagree']


@rcheck('environment-lock', 'requirements_pinned')
def _(d, path):
    lines = [x.strip() for x in rref_file(d['requirements_ref']).read_text(encoding='utf-8').splitlines()]
    return ['unpinned requirement: ' + x for x in lines if x and not x.startswith('#') and not PIN.match(x)]


@rcheck('environment-lock', 'package_refs_unique')
def _(d, path):
    ids = [r['id'] for r in d['package_refs']]
    return ['duplicate package ref'] if len(ids) != len(set(ids)) else []


@rcheck('bound-check-plan', 'check_ids_unique')
def _(d, path):
    return ['duplicate ID in ' + k for k in ('mandatory_deterministic', 'mandatory_semantic') if len(d[k]) != len(set(d[k]))]


@rcheck('bound-check-plan', 'check_plan_scope')
def _(d, path):
    if d['contract_ref'] == d['node_contract_ref']:
        return [] if d['subnode_id'] is None else ['node-scope plan names a subnode']
    if d['subnode_id'] is None:
        return ['subnode-scope plan has a null subnode_id']
    contract = rload(d['contract_ref'])
    bad = []
    if contract.get('subnode_id') != d['subnode_id'] or contract.get('node_contract_ref') != d['node_contract_ref']:
        bad.append('plan scope differs from its subnode contract')
    if contract.get('input_refs') != d['input_refs']:
        bad.append('plan inputs differ from its subnode contract')
    return bad


@rcheck('node-execution-contract', 'internal_dependencies_acyclic')
def _(d, path):
    ids = [s['subnode_id'] for s in d['subnodes']]
    if len(ids) != len(set(ids)):
        return ['duplicate subnode_id']
    if any(x not in ids for s in d['subnodes'] for x in s['depends_on']):
        return ['depends_on names an unknown subnode']
    done, pending = set(), set(ids)
    while pending:
        ready = {s['subnode_id'] for s in d['subnodes'] if s['subnode_id'] in pending and set(s['depends_on']) <= done}
        if not ready:
            return ['cyclic internal dependency among ' + ', '.join(sorted(pending))]
        done |= ready
        pending -= ready
    return []


@rcheck('node-execution-contract', 'input_inventory_matches_ports')
def _(d, path):
    return [] if d['input_refs'] == [r for p in d['inputs'] for r in p['artifact_refs']] else ['input_refs differ from the input ports']


@rcheck('node-execution-contract', 'gate_subjects_bound')
def _(d, path):
    work = {s['subnode_id'] for s in d['subnodes'] if s['role'] == 'work'}
    return ['gate subject is not a work subnode: ' + g['subject_subnode_id'] for g in d['gate_assignments'] if g['subject_subnode_id'] not in work]


@rcheck('node-execution-contract', 'verifier_follows_work')
def _(d, path):
    work = {s['subnode_id'] for s in d['subnodes'] if s['role'] == 'work'}
    return ['verifier without a work dependency: ' + s['subnode_id'] for s in d['subnodes'] if s['role'] == 'verifier' and not set(s['depends_on']) & work]


def robs_binding(d):
    contract = rload(d['contract_ref'])
    binding = contract['bindings'][0]
    return contract, binding, rload(binding['declaration_ref'])


@rcheck('invocation-observation', 'observation_identity_matches_contract')
def _(d, path):
    contract, binding, decl = robs_binding(d)
    bad = ['%s differs from the contract' % k for k in ('run_id', 'attempt_id', 'node_id', 'subnode_id', 'node_contract_ref') if d[k] != contract[k]]
    if d['binding_id'] != binding['id']:
        bad.append('binding_id differs from the contract binding')
    if (d['cc_name'], d['cc_version'], d['declaration_sha256']) != (decl['identity']['name'], decl['identity']['version_label'], binding['declaration_ref']['sha256']):
        bad.append('cc_name, cc_version or declaration_sha256 differs from the bound declaration')
    return bad


@rcheck('invocation-observation', 'measurement_status_consistent')
def _(d, path):
    if d['measurement_status'] == 'observed':
        bad = ['observed status with null ' + k for k in ('started_at', 'duration_s', 'model_calls') if d[k] is None]
        return bad + ([] if d['observed_runtime'] else ['observed status without observed runtime'])
    return [] if d['unavailable_reasons'] else ['unavailable status without a reason']


@rcheck('invocation-observation', 'route_id_matches_model_use')
def _(d, path):
    decl = robs_binding(d)[2]
    if not any(x['service_key'] == MODEL_BRIDGE for x in decl['needs']['injects']) and d['route_id'] is not None:
        return ['route_id set for a CC without the model bridge']
    if (d['model_calls'] or 0) > 0 and d['route_id'] is None:
        return ['model calls without a route_id']
    return []


def rbundle_set_sha(snapshot):
    values = sorted({e['check_pins']['check_bundle_sha256'] for e in snapshot['entries'] if e['check_pins'] is not None})
    return hashlib.sha256(''.join(v + '\n' for v in values).encode('utf-8')).hexdigest()


def rrouter_pin(value):
    return [] if (value['router_version'] is None) == (not value['router_enabled']) else ['router_version must be null exactly when router_enabled is false']


@rcheck('run-bundle', 'bundle_pins_match_run_plan')
def _(d, path):
    if d['run_plan_ref'] is None:
        return []
    plan, pins, bad = rload(d['run_plan_ref']), d['pins'], []
    if pins['library_snapshot_sha256'] != plan['library_snapshot_ref']['sha256']:
        bad.append('library snapshot pin differs from the run plan')
    if pins['plan_policy_ref'] != plan['policy_ref']:
        bad.append('plan policy pin differs from the run plan')
    if pins['check_bundle_set_sha256'] != rbundle_set_sha(rload(plan['library_snapshot_ref'])):
        bad.append('check bundle set digest does not recompute')
    if d['plan_source'] != plan['plan_source']:
        bad.append('plan_source differs from the run plan')
    return bad


@rcheck('run-bundle', 'bundle_router_pin_consistent')
def _(d, path):
    return rrouter_pin(d['pins'])


@rcheck('run-bundle', 'faults_only_in_evaluation')
def _(d, path):
    return ['fault ids outside an evaluation profile'] if d['fault_ids'] and d['evaluation_profile_id'] is None else []


@rcheck('run-bundle', 'bundle_gate_entries_match')
def _(d, path):
    bad = []
    if sorted(r['id'] + r['sha256'] for r in d['decision_refs']) != sorted(e['decision_ref']['id'] + e['decision_ref']['sha256'] for e in d['gate_decisions']):
        bad.append('decision_refs differ from the gate entries')
    for e in d['gate_decisions']:
        g = rload(e['decision_ref'])
        bad += ['gate entry %s differs from %s' % (k, e['decision_ref']['id']) for k in ('node_id', 'subnode_id', 'scope_kind', 'verdict', 'action', 'recorded_at') if e[k] != g[k]]
        if e['output_port'] != g.get('output_port'):
            bad.append('gate entry output_port differs from ' + e['decision_ref']['id'])
        if g['run_id'] != d['run_id']:
            bad.append('decision of another run: ' + e['decision_ref']['id'])
    if d['status'] == 'completed':
        advanced = {e['node_id'] for e in d['gate_decisions'] if e['scope_kind'] == 'node' and e['action'] == 'advance'}
        bad += ['completed bundle without an advancing node decision for ' + n['node_id'] for n in d['node_dispatches'] if n['node_id'] not in advanced]
    return bad


@rcheck('run-bundle', 'bundle_dispatch_times_match')
def _(d, path):
    bad = []
    for e in d['node_dispatches']:
        record = rload(e['dispatch_record_ref'])
        bad += ['dispatch entry %s differs from its record' % k for k in ('node_id', 'attempt_id', 'started_at', 'ended_at', 'outcome') if e[k] != record[k]]
        if record['run_id'] != d['run_id']:
            bad.append('dispatch record of another run')
    for ref in d['observation_refs'] + d['route_record_refs']:
        if rload(ref).get('run_id') != d['run_id']:
            bad.append('record of another run: ' + ref['id'])
    return bad


@rcheck('client-readiness', 'readiness_pins_match_identity')
def _(d, path):
    bad = rrouter_pin(d['pins'])
    if d['pins']['app_build'] != d['build_id'] or d['pins']['client_contract_version'] != d['client_contract_version']:
        bad.append('pins differ from build_id or client_contract_version')
    return bad


@rcheck('client-readiness', 'fault_injection_needs_profile')
def _(d, path):
    return ['fault injection without an evaluation profile'] if d['fault_injection'] and d['evaluation_profile'] is None else []


@rcheck('client-submission', 'fault_requires_profile')
def _(d, path):
    bad = []
    if d.get('fault_id') is not None and (d.get('profile_id') is None or d.get('evaluation') is None):
        bad.append('fault_id without profile_id and evaluation')
    if d.get('profile_id') is not None and d.get('evaluation') is None:
        bad.append('profile_id without evaluation')
    return bad


@rcheck('evaluation-profile', 'profile_router_pin_consistent')
def _(d, path):
    return rrouter_pin(d)


@rcheck('evaluation-profile', 'evaluation_only_marked_invalid_for_product')
def _(d, path):
    evaluation_only = bool(set(d['allowed_entry_points']) & {'E2', 'E3', 'E4', 'E5'}) or bool(d['candidate_pins'])
    return ['evaluation-only profile not marked invalid_for_product'] if evaluation_only and not d['invalid_for_product'] else []


@rcheck('evaluation-profile', 'entry_points_unique')
def _(d, path):
    return ['duplicate entry point'] if len(d['allowed_entry_points']) != len(set(d['allowed_entry_points'])) else []


@rcheck('library-admission', 'admission_cc_matches_candidate')
def _(d, path):
    candidate = rload(d['candidate_ref'])
    decl_ref = candidate.get('child_declaration_ref') or candidate.get('declaration_ref') or d['candidate_ref']
    decl = rload(decl_ref)
    expected = {'cc_name': decl['identity']['name'], 'cc_version': decl['identity']['version_label'], 'declaration_sha256': decl_ref['sha256']}
    return [] if d['cc'] == expected else ['cc differs from the candidate declaration']


@rcheck('library-admission', 'standing_follows_status')
def _(d, path):
    return ['standing %s without admission' % d['standing']] if d['standing'] != 'inactive' and d['status'] != 'admitted' else []


@rcheck('library-admission', 'memory_with_check_pins')
def _(d, path):
    return ['check pins without a memory ceiling'] if d['check_pins'] is not None and d['memory_mb'] is None else []


@rcheck('library-admission', 'child_inherits_parent_check_pins')
def _(d, path):
    # A child (parent_ref set) names its parent admission, the same CC name, and copies the parent's check pins.
    if (d['parent_ref'] is None) != (d['parent_admission_ref'] is None):
        return ['parent_ref and parent_admission_ref must be set together']
    if d['parent_admission_ref'] is None:
        return []
    parent = rload(d['parent_admission_ref'])
    bad = []
    if parent['cc']['cc_name'] != d['cc']['cc_name']:
        bad.append('the parent admission names a different CC')
    if d['check_pins'] != parent['check_pins']:
        bad.append('check_pins differ from the parent admission')
    return bad


ALLOWED_MOVES = {'inactive': {'active', 'revoked'}, 'active': {'suspended', 'revoked'}, 'suspended': {'active', 'revoked'}, 'revoked': set()}


@rcheck('activation-record', 'activation_target_admitted')
def _(d, path):
    adm = rload(d['admission_ref'])
    bad = []
    if adm['status'] != 'admitted':
        bad.append('the admission status is %s, not admitted' % adm['status'])
    if adm['cc'] != d['cc']:
        bad.append('cc differs from the admission record')
    return bad


@rcheck('activation-record', 'activation_target_has_check_pins')
def _(d, path):
    return [] if rload(d['admission_ref'])['check_pins'] is not None else ['the admission record pins no check bundle']


@rcheck('activation-record', 'activation_transition_allowed')
def _(d, path):
    if d['from_standing'] == d['to_standing'] == 'active':
        return []  # promotion; activation_scope_matches_lineage limits it to RSI children
    return [] if d['to_standing'] in ALLOWED_MOVES[d['from_standing']] else ['%s to %s is not an allowed move' % (d['from_standing'], d['to_standing'])]


@rcheck('activation-record', 'activation_scope_matches_lineage')
def _(d, path):
    adm = rload(d['admission_ref'])
    bad = []
    if adm['parent_ref'] is not None and d['to_standing'] == 'active' and d['effect_scope'] == 'live_plans' and d['from_standing'] != 'active':
        bad.append('an RSI child reaches live_plans only by promotion from an active sandbox activation')
    if adm['parent_ref'] is None and d['from_standing'] == 'active' and d['to_standing'] == 'active':
        bad.append('active to active is only for promoting an RSI child')
    return bad


@rcheck('client-submission', 'submission_structure')
def _(d, path):
    return rfield_errors('client-submission:field-contract:1', d)


@rcheck('empirical-results', 'empirical_sequence_contiguous')
def _(d, path):
    seq = [r['sequence'] for r in d['runs']]
    return [] if seq == list(range(1, len(seq) + 1)) else ['sequences are not 1..N in order']


@rcheck('empirical-results', 'empirical_values_finite')
def _(d, path):
    keys = set(d['runs'][0]['metrics']) if d['runs'] else set()
    bad = []
    for r in d['runs']:
        if set(r['metrics']) != keys:
            bad.append('run %s has different metric keys' % r['sequence'])
        bad += ['run %s %s is not a finite number' % (r['sequence'], k) for k, v in r['metrics'].items()
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)]
    return bad


PLATFORM_KINDS = ('qualified-intake', 'environment-lock', 'bound-check-plan', 'node-execution-contract', 'invocation-observation', 'run-bundle',
                  'client-readiness', 'client-submission', 'evaluation-profile', 'library-admission', 'empirical-results', 'activation-record')


# ---- exact-schema records with relational checks. Same rule as RCHECKS: invalid examples name the rejecting check.
def _results_cover_plan(d, path):
    plan = rload(d['check_plan_ref'])
    ids = [r['check_id'] for r in d['results']]
    return [] if len(ids) == len(set(ids)) and set(ids) == set(plan['mandatory_deterministic']) else ['results do not cover the bound check plan exactly once']


SCHEMA_CHECKS = {'deterministic-check-result': {'results_cover_plan': _results_cover_plan}}


# ---- deterministic admission checks of the CC declaration (declaration.md). They run on every declaration example.
ROLE = {i['path']: i.get('role') for i in index}
M1_KINDS = ('agent', 'tool')
ALWAYS_PROTECTED = ('/ports', '/needs', '/changes', '/guarantees', '/budget', '/identity/name', '/identity/lineage', '/evolution')
RSI_MAY_DIFFER = ('/identity/version_label', '/identity/carrier', '/identity/body', '/identity/lineage')
M1_POINTER_ENTRIES = ('/identity/body', '/identity/carrier')
GATE_EVIDENCE_CCS = ('research.verifier', 'research.benchmark', 'research.evaluation')
SECRET_ALLOWLIST = ('DEMO_API_TOKEN',)  # fixture allowlist; the operator sets the real one and M1 ships it empty
EFFECT_ORDER = ('pure', 'read_only', 'idempotent', 'compensable', 'irreversible')
REASON_CODE = re.compile(r'^[a-z][a-z0-9_]{0,63}$')


def glob_regex(glob):
    out, i = '', 0
    while i < len(glob):
        if glob.startswith('**', i):
            out, i = out + '.*', i + 2
        elif glob[i] == '*':
            out, i = out + '[^/]*', i + 1
        elif glob[i] == '?':
            out, i = out + '[^/]', i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out)


def may_files(decl):
    return [e[6:] for e in decl['evolution'].get('may_change', []) if e.startswith('files:')]


def covered(globs, path):
    return any(glob_regex(g).fullmatch(path) for g in globs)


def pointer_get(doc, pointer):
    value = doc
    for token in pointer.split('/')[1:]:
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def pointer_ok(doc, pointer):
    try:
        pointer_get(doc, pointer)
        return True
    except (KeyError, IndexError, ValueError, TypeError):
        return False


def _decl_kind(d, path):
    bad = []
    if d['identity']['kind'] not in M1_KINDS:
        bad.append('kind %s is not admitted in M1' % d['identity']['kind'])
    if any(k in d for k in ('members', 'structure', 'wiring')) or 'remote' in d['identity']:
        bad.append('composite or remote form is not admitted in M1')
    if d['identity'].get('load_mode', 'invoked') != 'invoked':
        bad.append('load_mode other than invoked is not admitted in M1')
    return bad


def _decl_network(d, path):
    n = d['needs']['network']
    if n['mode'] == 'none':
        return [] if n['direction'] == 'none' and not n['allowlist'] else ['mode none needs direction none and an empty allowlist']
    if n['mode'] == 'allowlist':
        return [] if n['direction'] == 'egress' and n['allowlist'] else ['mode allowlist needs direction egress and a non-empty allowlist']
    return ['network mode open is rejected in M1']


def _decl_rsi_mode(d, path):
    mode = d['evolution']['rsi']
    bad = []
    if mode == 'submit':
        bad.append('rsi submit is rejected in M1')
    if mode != 'none' and d['identity']['name'] in GATE_EVIDENCE_CCS:
        bad.append('a verifier or gate-evidence CC must have rsi none')
    return bad


def _decl_cannot_grant(d, path):
    return ['may_change lists ' + e for e in d['evolution'].get('may_change', []) if e == '/evolution' or e.startswith('/evolution/')]


def _decl_may_change_entries(d, path):
    bad = []
    for e in d['evolution'].get('may_change', []):
        if e.startswith('files:'):
            glob = e[6:]
            if not glob or glob.startswith('/') or '..' in glob.split('/'):
                bad.append('files entry is not a relative glob: ' + e)
        elif e not in M1_POINTER_ENTRIES:
            bad.append('M1 may_change does not accept ' + e)
    if len(set(d['evolution'].get('may_change', []))) != len(d['evolution'].get('may_change', [])):
        bad.append('may_change repeats an entry')
    return bad


def _decl_dependencies(d, path):
    bad = []
    for e in d['needs']['external']:
        if e['kind'] == 'package':
            if 'pin' not in e or 'lockfile' not in e:
                bad.append('package %s needs a pin and a lockfile' % e['identifier'])
        elif 'lockfile' in e:
            bad.append('lockfile on a dependency that is not a package: ' + e['identifier'])
    return bad


def _decl_secrets(d, path):
    names = [s['name'] for s in d['needs'].get('secrets', [])]
    bad = ['secret %s is not on the admission allowlist' % n for n in names if n not in SECRET_ALLOWLIST]
    if len(set(names)) != len(names):
        bad.append('secret names repeat')
    return bad


def _decl_failure_modes(d, path):
    modes = d['guarantees'].get('failure_modes', [])
    codes = [m['reason_code'] for m in modes]
    bad = ['reason_code %s is not lowercase snake case' % c for c in codes if not REASON_CODE.fullmatch(c)]
    if len(set(codes)) != len(codes):
        bad.append('reason_code repeats')
    bad += ['failure mode %s is retriable, which M1 rejects' % m['reason_code'] for m in modes if m['retriable'] is not False]
    bad += ['failure mode %s has no when text' % m['reason_code'] for m in modes if not m['when'].strip()]
    return bad


def _decl_self_tests(d, path):
    g = d['guarantees']
    tests = g.get('self_tests', [])
    codes = {m['reason_code'] for m in g.get('failure_modes', [])}
    ids = [t['id'] for t in tests]
    bad = []
    if len(set(ids)) != len(ids):
        bad.append('self-test IDs repeat')
    if 'pass' in codes:
        bad.append('pass is reserved and cannot be a failure mode code')
    bad += ['failure mode %s has no self-test that expects it' % c for c in sorted(codes) if not any(t['expects'] == c for t in tests)]
    bad += ['self-test %s expects %s, which is not a declared failure mode' % (t['id'], t['expects']) for t in tests if t['expects'] != 'pass' and t['expects'] not in codes]
    for t in tests:
        p = EX / t['ref']['ref']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != t['ref']['sha256']:
            bad.append('self-test %s ref does not resolve to its digest' % t['id'])
    return bad


def _decl_human_interaction(d, path):
    value = d['needs'].get('human_interaction', 'none')
    return [] if value == 'none' else ['human_interaction %s is reserved and rejected in M1' % value]


def _decl_effect_class(d, path):
    need = 0
    for e in d['changes']['effects']:
        if e['op'] == 'model_invoke':
            continue
        if e['idempotent']:
            level = 'pure' if e['reversibility'] == 'scoped' else 'read_only'
        else:
            level = 'compensable' if e['reversibility'] in ('scoped', 'inverse', 'compensate') else 'irreversible'
        need = max(need, EFFECT_ORDER.index(level))
    declared = d['changes']['effect_class']
    return [] if EFFECT_ORDER.index(declared) >= need else ['effect_class %s is weaker than the effects imply (%s)' % (declared, EFFECT_ORDER[need])]


def _decl_lineage(d, path):
    lineage = d['identity'].get('lineage')
    bad = []
    if lineage is not None and lineage['relation'] in ('composes', 'fuses', 'rollback_of'):
        bad.append('relation %s is rejected in M1' % lineage['relation'])
    if ROLE.get(path) == 'rsi_child':
        if lineage is None:
            bad.append('an RSI child has no lineage')
        elif lineage['parent'] is None or lineage['relation'] != 'supersedes' or lineage['builder'] != 'rsi_workbench':
            bad.append('an RSI child lineage needs a parent, relation supersedes and builder rsi_workbench')
    return bad


def _decl_body(d, path):
    bad = []
    for item in d['identity'].get('body', []):
        target = EX / item['path']
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != item['sha256']:
            bad.append('body file hash differs: ' + item['path'])
    carrier = d['identity'].get('carrier')
    if carrier and (not (EX / carrier['ref']).is_file() or hashlib.sha256((EX / carrier['ref']).read_bytes()).hexdigest() != carrier['sha256']):
        bad.append('carrier hash differs: ' + carrier['ref'])
    return bad


# ---- gate decision and verifier assessment relational checks (checking.md, capsules/verifier.md)
def _gate_verdict_action(d, path):
    bad = []
    advancing = d['verdict'] in ('PASS', 'PASS_WITH_KNOWN_LIMITATIONS')
    if (d['action'] == 'advance') != advancing:
        bad.append('action %s does not follow verdict %s' % (d['action'], d['verdict']))
    if d['action'] == 'advance':
        if d['assessment_ref'] is None or not d['accepted_refs'] or not d['invocation_refs']:
            bad.append('advance needs an assessment, invocations and accepted refs')
        if any(r not in d['output_refs'] for r in d['accepted_refs']):
            bad.append('an accepted ref is not a reviewed output')
        if d['scope_kind'] == 'subnode' and (d.get('output_port') is None or len(d['output_refs']) != 1):
            bad.append('an advancing subnode-scope decision names one output_port and one output')
    elif d['accepted_refs']:
        bad.append('a halt publishes accepted refs')
    if d['scope_kind'] == 'node' and (d.get('output_port') is not None or d['subnode_id'] is not None):
        bad.append('a node-scope decision has a null output_port and subnode_id')
    return bad


def _assessment_verdict(d, path):
    outcomes = [f['outcome'] for f in d['findings']]
    v = d['verdict']
    bad = []
    if v == 'PASS' and (any(o != 'PASS' for o in outcomes) or d['uncertainties']):
        bad.append('PASS needs every finding PASS and no uncertainty')
    if v == 'FAIL' and 'FAIL' not in outcomes:
        bad.append('FAIL needs a failing finding')
    if v == 'ENVIRONMENT_BLOCKED' and 'ENVIRONMENT_BLOCKED' not in outcomes:
        bad.append('ENVIRONMENT_BLOCKED needs a blocked finding')
    if v == 'INCONCLUSIVE' and 'INCONCLUSIVE' not in outcomes and not d['uncertainties']:
        bad.append('INCONCLUSIVE needs an inconclusive finding or an uncertainty')
    if v in ('PASS', 'PASS_WITH_KNOWN_LIMITATIONS') and d['required_correction'] is not None:
        bad.append('an advancing verdict carries no required correction')
    if len({f['criterion_id'] for f in d['findings']}) != len(d['findings']):
        bad.append('duplicate criterion finding')
    return bad


SCHEMA_CHECKS['capsule-declaration'] = {'m1_kind_admitted': _decl_kind, 'network_consistent': _decl_network,
                                        'rsi_mode_allowed': _decl_rsi_mode, 'rsi_cannot_grant': _decl_cannot_grant, 'may_change_entries_valid': _decl_may_change_entries,
                                        'rsi_child_has_lineage': _decl_lineage, 'body_hashes_match': _decl_body, 'dependencies_pinned': _decl_dependencies,
                                        'secrets_allowed': _decl_secrets, 'failure_modes_valid': _decl_failure_modes, 'failure_modes_have_self_tests': _decl_self_tests, 'human_interaction_none': _decl_human_interaction,
                                        'effect_class_matches_effects': _decl_effect_class}
SCHEMA_CHECKS['gate-decision'] = {'verdict_action_consistent': _gate_verdict_action}
SCHEMA_CHECKS['verifier-assessment'] = {'verdict_follows_findings': _assessment_verdict}


# ---- dispatch record, gate decision index, rubric, bundle and receipts
@rcheck('dispatch-record', 'dispatch_outcome_consistent')
def _(d, path):
    bad = []
    no_gate = d['outcome'] in ('failed', 'budget_exhausted', 'interrupted')
    if (d['gate_decision_ref'] is None) != no_gate:
        bad.append('gate_decision_ref is null exactly for failed, budget_exhausted and interrupted')
    if (not d['output_gate_decision_refs']) != (d['gate_decision_ref'] is None):
        bad.append('output_gate_decision_refs is empty exactly when gate_decision_ref is null')
    if bool(d['output_refs']) and d['outcome'] != 'accepted':
        bad.append('output_refs are set only for an accepted attempt')
    if (d['ended_at'] is None) != (d['outcome'] == 'interrupted'):
        bad.append('ended_at is null exactly for an interrupted attempt')
    if (d['cc'] is None) != (d['check_pins'] is None):
        bad.append('check_pins is null exactly when cc is null')
    return bad


@rcheck('gate-decision-index', 'entries_are_advancing_node_decisions')
def _(d, path):
    bad = []
    for e in d['entries']:
        g = rload(e['gate_decision_ref'])
        if g['action'] != 'advance' or g['scope_kind'] != 'node' or g['node_id'] != e['node_id']:
            bad.append('entry %s is not an advancing node-scope decision of its node' % e['node_id'])
    return bad


@rcheck('screening-rubric', 'rubric_structure')
def _(d, path):
    return rfield_errors('screening-rubric:field-contract:1', d)


@rcheck('screening-rubric', 'rubric_dimensions_complete')
def _(d, path):
    bad = []
    if sorted(x['name'] for x in d['dimensions']) != sorted(DIMS):
        bad.append('dimensions are not novelty, feasibility and compute_alignment once each')
    for x in d['dimensions']:
        if sorted(a['score'] for a in x['anchors']) != list(range(x['scale_min'], x['scale_max'] + 1)):
            bad.append('anchors of %s do not cover the scale once each' % x['name'])
    if len({f['id'] for f in d['forbidden_dependencies']}) != len(d['forbidden_dependencies']):
        bad.append('duplicate forbidden dependency id')
    return bad


BUNDLE_FILES = ['poc_patch.py', 'requirements.txt', 'run_benchmark.py']


@rcheck('poc-artifact-bundle', 'bundle_schema')
def _(d, path):
    bad = rfield_errors('poc-artifact-bundle:field-contract:1', d)
    raw = EX / path
    if raw.stat().st_size > 1024 * 1024:
        bad.append('bundle is larger than 1 MiB')
    with zipfile.ZipFile(raw) as archive:
        bad += ['encrypted or directory entry: ' + i.filename for i in archive.infolist() if i.flag_bits & 1 or i.is_dir()]
    return bad


@rcheck('poc-artifact-bundle', 'required_files_present')
def _(d, path):
    names = d['entry_names']
    bad = [] if sorted(names) == BUNDLE_FILES else ['entries are not exactly %s' % BUNDLE_FILES]
    bad += ['unsafe entry name: ' + n for n in names if '/' in n or '\\' in n or '..' in n or n != n.lower()]
    return bad


@rcheck('execution-receipt', 'execution_receipt_schema')
def _(d, path):
    return rfield_errors('execution-receipt:field-contract:1', d)


@rcheck('execution-receipt', 'baseline_before_treatment')
def _(d, path):
    runs, bad = d['runs'], []
    if [r['sequence'] for r in runs] != list(range(1, len(runs) + 1)):
        bad.append('sequences are not 1..N in order')
    base = [r['sequence'] for r in runs if r['role'] == 'baseline']
    treat = [r['sequence'] for r in runs if r['role'] == 'treatment']
    if not base or not treat or max(base) > min(treat):
        bad.append('a treatment run precedes a baseline run')
    if [r['started_at'] for r in runs] != sorted(r['started_at'] for r in runs):
        bad.append('started_at is not in sequence order')
    repeats = rload(d['blueprint_ref'])['repeat_count']
    if len(base) != repeats or len(treat) != repeats:
        bad.append('run counts differ from repeat_count')
    return bad


@rcheck('provisioning-receipt', 'provisioning_receipt_schema')
def _(d, path):
    return rfield_errors('provisioning-receipt:field-contract:1', d)


@rcheck('provisioning-receipt', 'network_policy_respected')
def _(d, path):
    bad = []
    if d['network_policy_used'] == 'none' and d['network_allowlist']:
        bad.append('policy none with a non-empty allowlist')
    if d['status'] == 'succeeded' and d['unlisted_network_requests'] != 0:
        bad.append('a succeeded receipt has unlisted network requests')
    if d['runner_user'] == 'root' or not d['venv_path'].startswith('/workspace/poc/'):
        bad.append('environment is not an unprivileged venv under /workspace/poc/')
    return bad


# ---- RSI records (rsi-contracts.md)
SESSION_DEFAULTS = {'max_attempts': 20, 'max_no_progress': 5, 'wall_s': 3600, 'per_call_s': 300, 'session_query_limit': 30, 'lifetime_query_limit': 90}


@rcheck('rsi-session', 'session_structure')
def _(d, path):
    return rfield_errors('rsi-session:field-contract:1', d)


@rcheck('rsi-session', 'session_limits_within_defaults')
def _(d, path):
    lim, q, bad = d['limits'], d['qualification'], []
    bad += ['limit %s is above the default %s' % (k, v) for k, v in SESSION_DEFAULTS.items() if lim[k] > v]
    if lim['per_call_s'] > lim['wall_s'] or lim['session_query_limit'] > lim['lifetime_query_limit']:
        bad.append('per-call time above wall time, or session queries above lifetime queries')
    target = rload(d['target_profile_ref'])
    if lim['session_query_limit'] > target['session_query_limit'] or lim['lifetime_query_limit'] > target['lifetime_query_limit']:
        bad.append('query limits exceed the target profile')
    if (q['min_pass_rate_gain'] < 0.05 or q['alpha'] > 0.05 or q['min_timing_gain'] < 0.1 or q['noise_multiplier'] < 3
            or q['warmup_batches'] != 5 or q['paired_rounds'] != target['scoring']['paired_rounds']):
        bad.append('qualification policy is weaker than the frozen rule')
    return bad


@rcheck('rsi-session', 'session_pins_consistent')
def _(d, path):
    bad = []
    genesis = rload(d['chain_root_ref'])
    if genesis['session_id'] != d['session_id'] or genesis['target_ref'] != d['target_profile_ref'] or genesis['hash_profile_ref'] != d['hash_profile_ref']:
        bad.append('genesis does not pin this session, target and hash profile')
    if d['parent']['declaration_sha256'] != d['parent_declaration_ref']['sha256']:
        bad.append('parent pin differs from the parent declaration')
    target = rload(d['target_profile_ref'])
    if d['configuration_ref'] != target['configuration_ref'] or d['improver_ref'] != target['improver_ref'] or d['scoring_adapter_ref'] != target['scoring_adapter_ref']:
        bad.append('session pins differ from the target profile')
    if d['parent_declaration_ref'] != target['parent_declaration_ref']:
        bad.append('parent declaration differs from the target profile')
    return bad


def binom_tail(g, l):
    n = g + l
    return sum(math.comb(n, k) for k in range(g, n + 1)) / 2 ** n


@rcheck('rsi-session-result', 'result_structure')
def _(d, path):
    return rfield_errors('rsi-session-result:field-contract:1', d)


@rcheck('rsi-session-result', 'qualification_rule_holds')
def _(d, path):
    bad, s, how = [], d['statistics'], d['qualified_by']
    q = rload(d['session_ref'])['qualification']
    if (d['outcome'] == 'QUALIFIED') != (how != 'none'):
        bad.append('qualified_by is none exactly when the outcome is not QUALIFIED')
    if d['outcome'] == 'QUALIFIED' and (d['child'] is None or d['child_declaration_ref'] is None or d['referee_evidence_ref'] is None or s is None):
        bad.append('QUALIFIED needs a child, its declaration, referee evidence and statistics')
    if s is not None:
        if s['parent_passed'] > s['fixture_units'] or s['child_passed'] > s['fixture_units'] or s['child_passed'] - s['parent_passed'] != s['gain_units'] - s['loss_units']:
            bad.append('pass counts and discordant units do not reconcile')
        if not rclose(s['pass_rate_gain'], (s['child_passed'] - s['parent_passed']) / s['fixture_units']):
            bad.append('pass_rate_gain does not recompute')
        no_discordant = s['gain_units'] + s['loss_units'] == 0
        if (s['p_value'] is None) != no_discordant or (s['p_value'] is not None and not rclose(s['p_value'], binom_tail(s['gain_units'], s['loss_units']))):
            bad.append('p_value does not recompute from the discordant units')
        if s['child_passed'] < s['parent_passed'] and d['outcome'] == 'QUALIFIED':
            bad.append('a child with fewer passes never qualifies')
    if how == 'pass_gain' and s is not None:
        if s['child_passed'] <= s['parent_passed'] or s['loss_units'] != 0 or s['pass_rate_gain'] < q['min_pass_rate_gain'] or s['p_value'] is None or s['p_value'] > q['alpha']:
            bad.append('pass_gain needs more passes, zero protected regressions, the minimum gain and p_value at most alpha')
    if how == 'timing_tiebreak' and s is not None:
        t = s['timing']
        if s['child_passed'] != s['parent_passed'] or s['loss_units'] != 0 or t is None:
            bad.append('timing_tiebreak needs equal passes, zero protected regressions and a timing comparison')
        elif (not rclose(t['relative_gain'], 1 - t['child_median_s'] / t['parent_median_s']) or t['relative_gain'] < t['min_relative_gain']
              or t['relative_gain'] <= t['noise_multiplier'] * t['calibrated_relative_noise'] or t['min_relative_gain'] < q['min_timing_gain']
              or t['paired_rounds'] != q['paired_rounds'] or t['warmup_batches'] != q['warmup_batches']):
            bad.append('timing gain does not meet the calibrated rule')
    return bad


@rcheck('rsi-session-result', 'result_matches_referee_evidence')
def _(d, path):
    if d['referee_evidence_ref'] is None:
        return []
    ev, bad, s = rload(d['referee_evidence_ref']), [], d['statistics']
    target = rload(rload(d['session_ref'])['target_profile_ref'])
    final = [p for p in ev['pairs'] if p['split'] == target['splits']['hidden_final']]
    if ev['final_evaluations'] != 1 or len(final) != 1:
        bad.append('referee evidence has not exactly one final evaluation')
    elif s is not None:
        p = final[0]
        if (p['total'], p['parent_passed'], p['child_passed']) != (s['fixture_units'], s['parent_passed'], s['child_passed']):
            bad.append('statistics differ from the final referee pair')
        if s['timing'] is not None and not (rclose(statistics.median(p['parent_time_s']), s['timing']['parent_median_s']) and rclose(statistics.median(p['child_time_s']), s['timing']['child_median_s'])):
            bad.append('timing medians differ from the final referee pair')
    if d['child_declaration_ref'] is not None and [b['sha256'] for b in rload(d['child_declaration_ref'])['identity']['body']] != [ev['child_ref']['sha256']]:
        bad.append('child body differs from the assessed child')
    return bad


@rcheck('candidate-package', 'package_structure')
def _(d, path):
    return rfield_errors('candidate-package:field-contract:1', d)


@rcheck('candidate-package', 'package_refs_resolve')
def _(d, path):
    return ['ref does not resolve: ' + r['id'] for r in rrefs(d) if not rref_ok(r)]


@rcheck('candidate-package', 'declaration_digests_match')
def _(d, path):
    bad = []
    for side in ('parent', 'child'):
        decl, pin = rload(d[side + '_declaration_ref']), d[side]
        if pin['declaration_sha256'] != d[side + '_declaration_ref']['sha256'] or pin['cc_name'] != decl['identity']['name'] or pin['cc_version'] != decl['identity']['version_label']:
            bad.append('%s pin differs from its declaration' % side)
    if d['parent']['cc_name'] != d['child']['cc_name'] or d['parent']['cc_version'] == d['child']['cc_version']:
        bad.append('child must keep the name and change the version label')
    if rload(d['provenance_ref'])['declaration_ref'] != d['child_declaration_ref']:
        bad.append('provenance names another declaration')
    return bad


@rcheck('candidate-package', 'child_lineage_matches_parent')
def _(d, path):
    lineage = rload(d['child_declaration_ref'])['identity'].get('lineage')
    if lineage is None:
        return ['child declaration has no lineage']
    if lineage['parent'] != d['parent_declaration_ref'] or lineage['relation'] != 'supersedes' or lineage['builder'] != 'rsi_workbench':
        return ['child lineage does not name the parent with relation supersedes and builder rsi_workbench']
    return []


@rcheck('candidate-package', 'changes_allowed')
def _(d, path):
    parent, child, bad = rload(d['parent_declaration_ref']), rload(d['child_declaration_ref']), []
    if parent['evolution']['rsi'] == 'none':
        bad.append('the parent has rsi none, so RSI may not build a child')
    bad += ['child changes /' + k for k in set(parent) | set(child) if k != 'identity' and parent.get(k) != child.get(k)]
    bad += ['child changes /identity/' + k for k in set(parent['identity']) | set(child['identity'])
            if '/identity/' + k not in RSI_MAY_DIFFER and parent['identity'].get(k) != child['identity'].get(k)]
    pb = {b['path']: b['sha256'] for b in parent['identity'].get('body', [])}
    cb = {b['path']: b['sha256'] for b in child['identity'].get('body', [])}
    globs = may_files(parent)
    bad += ['body file outside may_change: ' + p for p in sorted(set(pb) | set(cb)) if pb.get(p) != cb.get(p) and not covered(globs, p)]
    for pointer in ALWAYS_PROTECTED:
        if pointer in RSI_MAY_DIFFER or not pointer_ok(parent, pointer):
            continue
        if not pointer_ok(child, pointer) or pointer_get(parent, pointer) != pointer_get(child, pointer):
            bad.append('child changes protected ' + pointer)
    return bad


@rcheck('candidate-package', 'rsi_no_copy')
def _(d, path):
    child = rload(d['child_declaration_ref'])
    shas = {b['sha256'] for b in child['identity'].get('body', [])}
    bad = []
    for item in index:
        if not item['schema_id'] or ':capsule-declaration:' not in item['schema_id'] or item.get('expect') == 'invalid':
            continue
        other = load(EX / item['path'])
        if other['identity']['name'] == child['identity']['name'] or other['evolution']['rsi'] != 'none':
            continue
        same = shas & {b['sha256'] for b in other['identity'].get('body', [])}
        if same:
            bad.append('body files copy the CC %s, which has rsi none' % other['identity']['name'])
    return bad


@rcheck('candidate-package', 'mutable_paths_within_profile')
def _(d, path):
    allowed = set(rload(d['target_profile_ref'])['mutable_paths'])
    touched = d['mutable_paths_touched']
    bad = ['path outside the profile mutable paths: ' + p for p in touched if p not in allowed]
    if not touched or len(set(touched)) != len(touched):
        bad.append('mutable_paths_touched is empty or repeats a path')
    return bad


@rcheck('candidate-package', 'session_result_qualified')
def _(d, path):
    r, bad = rload(d['session_result_ref']), []
    if r['outcome'] != 'QUALIFIED' or r['qualified_by'] == 'none':
        bad.append('session result is not QUALIFIED')
    if r['parent'] != d['parent'] or r['child'] != d['child'] or r['referee_evidence_ref'] != d['referee_evidence_ref'] or r['session_ref'] != d['session_ref']:
        bad.append('session result names another parent, child, session or referee evidence')
    return bad


@rcheck('candidate-package', 'attempt_chain_verifies')
def _(d, path):
    r, session = rload(d['session_result_ref']), rload(d['session_ref'])
    bad, previous = [], None
    for n, ref in enumerate(r['attempt_refs'], 1):
        a = rload(ref)
        if a['sequence'] != n or a['previous_ref'] != previous or a['session_id'] != session['session_id']:
            bad.append('attempt %s breaks the chain' % ref['id'])
        if a['chain_root_ref'] != session['chain_root_ref'] or a['hash_profile_ref'] != session['hash_profile_ref'] or a['target_ref'] != d['target_profile_ref']:
            bad.append('attempt %s has another root, hash profile or target' % ref['id'])
        previous = ref
    if r['final_attempt_ref'] not in r['attempt_refs']:
        bad.append('final attempt is not in the chain')
    return bad


@rcheck('candidate-package', 'diff_matches_final_attempt')
def _(d, path):
    final = rload(rload(d['session_result_ref'])['final_attempt_ref'])
    child = rload(d['child_declaration_ref'])
    bad = [] if final['diff_ref'] == d['diff_ref'] else ['diff differs from the final attempt']
    if [b['sha256'] for b in child['identity']['body']] != [final['child_ref']['sha256']]:
        bad.append('child body differs from the final attempt child')
    return bad


def rsi_issues(evidence):
    result=[];attempt=resolved(evidence['attempt_ref']);target=resolved(evidence['target_ref'])
    if evidence['parent_ref']!=attempt['parent_ref'] or evidence['child_ref']!=attempt['child_ref'] or evidence['target_ref']!=attempt['target_ref'] or target['parent_ref']!=attempt['parent_ref']:result.append('wrong lineage')
    if not evidence['mandatory_parent_tests_passed'] or not evidence['integrity_passed'] or evidence['violations']:result.append('failed mandatory integrity')
    if evidence['configuration_ref']!=target['configuration_ref'] or attempt['configuration_ref']!=target['configuration_ref']:result.append('changed RSI comparison context')
    if evidence['final_evaluations']!=1:result.append('final query misuse')
    if len(set(target['splits'].values()))!=4:result.append('split identity overlap')
    if target['scoring']['primary']!='passed_test_count' or target['scoring']['secondary']!='paired_time_at_equal_counts':result.append('wrong scoring order')
    if attempt['queries_used']>target['session_query_limit'] or target['session_query_limit']!=30 or target['lifetime_query_limit']!=90:result.append('query limit')
    for pair in evidence['pairs']:
        if pair['split'] not in [target['splits']['hidden_loop'],target['splits']['hidden_final']] or pair['total']<20 or not 0<=pair['parent_passed']<=pair['child_passed']<=pair['total']:result.append('invalid comparable counts')
        if len(pair['parent_time_s'])!=target['scoring']['paired_rounds'] or len(pair['child_time_s'])!=target['scoring']['paired_rounds']:result.append('missing paired timing')
    return result

# ---- target profile, attempt, feedback, referee evidence, export, provenance, clearance, opportunity, completion report
@rcheck('rsi-target-profile', 'profile_structure')
def _(d, path):
    return rfield_errors('rsi-target-profile:field-contract:1', d)


@rcheck('rsi-target-profile', 'profile_parent_matches_declaration')
def _(d, path):
    decl = rload(d['parent_declaration_ref'])
    return [] if d['parent_ref']['sha256'] in {b['sha256'] for b in decl['identity'].get('body', [])} else ['parent_ref is not a body file of the parent declaration']


@rcheck('rsi-target-profile', 'profile_within_may_change')
def _(d, path):
    decl = rload(d['parent_declaration_ref'])
    globs, bad = may_files(decl), []
    if decl['evolution']['rsi'] != 'propose':
        bad.append('the parent declaration does not have rsi propose')
    bad += ['mutable path is outside the parent may_change: ' + p for p in d['mutable_paths'] if not covered(globs, p)]
    if len(set(d['mutable_paths'])) != len(d['mutable_paths']):
        bad.append('mutable_paths repeats a path')
    bad += ['a protected ref is also a mutable path: ' + r['id'] for r in d['protected_refs'] if r['id'] in d['mutable_paths']]
    return bad


@rcheck('rsi-target-profile', 'profile_scoring_fixed')
def _(d, path):
    s, bad = d['scoring'], []
    if len(set(d['splits'].values())) != 4:
        bad.append('split identities overlap')
    if s['primary'] != 'passed_test_count' or s['secondary'] != 'paired_time_at_equal_counts' or s['warmup_batches'] != 5 or s['paired_rounds'] != 7:
        bad.append('scoring is not the frozen passed-tests-first rule')
    if d['session_query_limit'] != 30 or d['lifetime_query_limit'] != 90:
        bad.append('query limits are not 30 and 90')
    return bad


@rcheck('rsi-attempt', 'attempt_structure')
def _(d, path):
    return rfield_errors('rsi-attempt:field-contract:1', d)


@rcheck('rsi-attempt', 'attempt_chain_link')
def _(d, path):
    if (d['sequence'] == 1) != (d['previous_ref'] is None):
        return ['previous_ref is null exactly for sequence 1']
    return []


@rcheck('rsi-attempt', 'attempt_matches_genesis')
def _(d, path):
    g = rload(d['chain_root_ref'])
    ok = g['session_id'] == d['session_id'] and g['target_ref'] == d['target_ref'] and g['hash_profile_ref'] == d['hash_profile_ref']
    return [] if ok else ['genesis does not pin this session, target and hash profile']


@rcheck('rsi-attempt', 'attempt_unavailable_explained')
def _(d, path):
    return ['time or model calls are null without an unavailable reason'] if (d['time_s'] is None or d['model_calls'] is None) and not d['unavailable_reasons'] else []


@rcheck('rsi-attempt', 'attempt_violation_halts')
def _(d, path):
    return ['violations without a stop_reason'] if d['violations'] and d['stop_reason'] is None else []


@rcheck('rsi-loop-feedback', 'feedback_structure')
def _(d, path):
    return rfield_errors('rsi-loop-feedback:field-contract:1', d)


@rcheck('rsi-loop-feedback', 'feedback_counts_consistent')
def _(d, path):
    return [] if 0 <= d['passed'] <= d['total'] else ['passed is above total']


@rcheck('rsi-referee-evidence', 'referee_structure')
def _(d, path):
    return rfield_errors('rsi-referee-evidence:field-contract:1', d)


@rcheck('rsi-referee-evidence', 'referee_lineage_matches')
def _(d, path):
    return [m for m in rsi_issues(d) if m in ('wrong lineage', 'changed RSI comparison context')]


@rcheck('rsi-referee-evidence', 'referee_integrity_holds')
def _(d, path):
    return [m for m in rsi_issues(d) if m in ('failed mandatory integrity', 'final query misuse')]


def rsign(d, key_id):
    # Stand-in for the Ed25519 signature of production: the SHA-256 of the key ID and the canonical bytes without `signature`.
    body = {k: v for k, v in d.items() if k != 'signature'}
    return hashlib.sha256((key_id + '\n' + json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False)).encode('utf-8')).hexdigest()


def rsignature_errors(d):
    pinned = load(EX / 'operator_config.json')['rsi']['custodian_key_id']
    bad = []
    if d['signer_key_id'] != pinned:
        bad.append('signer_key_id %s is not the pinned custodian key %s' % (d['signer_key_id'], pinned))
    if d['signature'] != rsign(d, d['signer_key_id']):
        bad.append('the signature does not verify over the record bytes')
    return bad


@rcheck('rsi-referee-evidence', 'referee_signature_valid')
def _(d, path):
    return rsignature_errors(d)


@rcheck('rsi-session-result', 'referee_signature_valid')
def _(d, path):
    return rsignature_errors(d)


@rcheck('rsi-referee-evidence', 'referee_pairs_comparable')
def _(d, path):
    return [m for m in rsi_issues(d) if m in ('invalid comparable counts', 'missing paired timing', 'split identity overlap', 'wrong scoring order', 'query limit')]


@rcheck('rsi-evidence-export', 'export_structure')
def _(d, path):
    return rfield_errors('rsi-evidence-export:field-contract:1', d)


@rcheck('rsi-evidence-export', 'export_matches_referee')
def _(d, path):
    ev, bad = rload(d['referee_ref']), []
    if ev['attempt_ref'] != d['attempt_ref'] or ev['parent_ref'] != d['parent_ref'] or ev['child_ref'] != d['child_ref']:
        bad.append('export names another attempt, parent or child than the referee evidence')
    if ev['violations'] != d['violations']:
        bad.append('violations differ from the referee evidence')
    return bad


@rcheck('rsi-evidence-export', 'export_redacts_hidden')
def _(d, path):
    bad = [] if d['redactions'] else ['an export lists no redaction']
    target = rload(rload(d['referee_ref'])['target_ref'])
    bad += ['summary names the hidden split ' + v for k, v in target['splits'].items() if k.startswith('hidden') and v in d['summary']]
    return bad


@rcheck('candidate-provenance', 'provenance_structure')
def _(d, path):
    return rfield_errors('candidate-provenance:field-contract:1', d)


@rcheck('candidate-provenance', 'provenance_matches_declaration')
def _(d, path):
    decl = rload(d['declaration_ref'])
    return [] if [r['sha256'] for r in d['implementation_refs']] == [b['sha256'] for b in decl['identity']['body']] else ['implementation refs differ from the declaration body']


@rcheck('candidate-provenance', 'provenance_lineage_consistent')
def _(d, path):
    lineage = rload(d['declaration_ref'])['identity'].get('lineage')
    if lineage is None or lineage['parent'] is None:
        return [] if d['parent_ref'] is None else ['parent_ref is set but the declaration has no parent']
    if d['parent_ref'] is None:
        return ['an RSI child names no parent body file']
    parent = rload(lineage['parent'])
    return [] if d['parent_ref']['sha256'] in {b['sha256'] for b in parent['identity']['body']} else ['parent_ref is not a body file of the lineage parent']


@rcheck('security-clearance', 'clearance_structure')
def _(d, path):
    return rfield_errors('security-clearance:field-contract:1', d)


@rcheck('security-clearance', 'clearance_evidence_complete')
def _(d, path):
    if d['decision'] == 'cleared' and (not d['guardrail_evidence_refs'] or not d['violation_refs']):
        return ['a clearance needs incident and guardrail evidence']
    return []


@rcheck('rsi-opportunity', 'opportunity_structure')
def _(d, path):
    return rfield_errors('rsi-opportunity:field-contract:1', d)


@rcheck('rsi-opportunity', 'opportunity_pins_consistent')
def _(d, path):
    profile = rload(d['target_profile_ref'])
    bad = [] if d['parent']['declaration_sha256'] == profile['parent_declaration_ref']['sha256'] else ['parent differs from the target profile declaration']
    return bad


@rcheck('rsi-opportunity', 'opportunity_start_conditions')
def _(d, path):
    bad = []
    if d['attribution'] == 'uncertain' and d['decision'] != 'NEEDS_REVIEW':
        bad.append('an uncertain attribution needs NEEDS_REVIEW')
    if d['decision'] == 'NEEDS_REVIEW' and d['attribution'] != 'uncertain':
        bad.append('NEEDS_REVIEW is only for an uncertain attribution')
    if d['decision'] == 'START':
        if d['attribution'] != 'implementation' or not d['symptom_reproduced'] or not d['parent_mandatory_passed']:
            bad.append('START needs an implementation cause, a reproduced symptom and passing parent behavior')
        if d['headroom'] is None or d['headroom'] < d['headroom_minimum']:
            bad.append('START needs headroom at least the profile minimum')
        if d['diagnosis_ref'] is None:
            bad.append('START needs a retained diagnosis')
    return bad


@rcheck('rsi-completion-report', 'completion_report_structure')
def _(d, path):
    return rfield_errors('rsi-completion-report:field-contract:1', d)


@rcheck('rsi-completion-report', 'completion_report_claims_backed')
def _(d, path):
    bad, results = [], {r['id']: rload(r) for r in d['session_result_refs']}
    ids = [r['requirement_id'] for r in d['requirement_coverage']]
    if len(set(ids)) != len(ids):
        bad.append('requirement_id repeats')
    for r in d['requirement_coverage']:
        if r['status'] in ('PASS', 'FAIL') and not r['evidence_refs']:
            bad.append('%s is %s without evidence' % (r['requirement_id'], r['status']))
    if any(r['status'] == 'BLOCKED' for r in d['requirement_coverage']) and not d['blockers']:
        bad.append('a BLOCKED requirement needs a blocker')
    for q in d['qualified_result_refs']:
        if q not in d['session_result_refs'] or results[q['id']]['outcome'] != 'QUALIFIED':
            bad.append('qualified result %s is not a QUALIFIED session in scope' % q['id'])
    if d['transfer_claim'] == 'supported' and not d['transfer_evidence_refs']:
        bad.append('a transfer claim needs held-out evidence')
    tests = [x['test_id'] for x in d['executed_tests']]
    if len(set(tests)) != len(tests):
        bad.append('test_id repeats')
    if any(x['outcome'] != 'not_run' and x['evidence_ref'] is None for x in d['executed_tests']):
        bad.append('a test that ran has no evidence')
    if any(x['kind'] == 'security' and x['outcome'] == 'failed' for x in d['executed_tests']) and all(r['status'] == 'PASS' for r in d['requirement_coverage']):
        bad.append('every requirement passes although a security test failed')
    return bad


# ---- Capsule Run Record fields (field-catalog.md#invocation-observation) and derived records (derived-records.md)
def rbody_sha(decl):
    body = sorted(decl['identity']['body'], key=lambda b: b['path'].encode('utf-8'))
    return hashlib.sha256(''.join('%s\t%s\n' % (b['path'], b['sha256']) for b in body).encode('utf-8')).hexdigest()


def rjsonl(ref):
    return [json.loads(x) for x in rref_file(ref).read_text(encoding='utf-8').splitlines() if x.strip()]


@rcheck('invocation-observation', 'observation_body_matches_declaration')
def _(d, path):
    return [] if d['body_files_sha256'] == rbody_sha(robs_binding(d)[2]) else ['body_files_sha256 does not recompute from the bound declaration identity.body']


@rcheck('invocation-observation', 'observation_decision_source_consistent')
def _(d, path):
    return [] if (d['decision_source'] is None) == (d['route_id'] is None) else ['decision_source is null exactly when route_id is null']


@rcheck('invocation-observation', 'failure_class_consistent')
def _(d, path):
    fc, bad = d['failure_class'], []
    if fc is None:
        if d['check_result_refs'] or d['verifier_assessment_ref'] is not None or d['human_answer_ref'] is not None:
            bad.append('gate-side refs are set while failure_class is null')
        return bad
    if fc == 'none':
        if d['outcome'] in ('failed', 'budget_exhausted', 'interrupted'):
            bad.append('failure_class none with outcome ' + d['outcome'])
        if d['error_fingerprint'] is not None or d['failure_reason_code'] is not None:
            bad.append('failure_class none with an error fingerprint or reason code')
    return bad


def rcl_required(decl):
    ids = {'needs.network'}
    for side in ('inputs', 'outputs'):
        ids |= {'ports.%s.%s' % (side, p['name']) for p in decl['ports'][side]}
    ids |= {'needs.resources.' + r['resource_key'] for r in decl['needs']['resources']}
    ids |= {'changes.effects.' + e['id'] for e in decl['changes']['effects']}
    ids |= {'guarantees.checks.' + c['id'] for c in decl['guarantees']['checks']}
    ids |= {'guarantees.failure_modes.' + m['reason_code'] for m in decl['guarantees'].get('failure_modes', [])}
    return ids


@rcheck('contract-conformance', 'conformance_counts_match_items')
def _(d, path):
    items, bad = d['items'], []
    count = lambda s: sum(1 for i in items if i['status'] == s)
    if d['undeclared_count'] != count('undeclared'):
        bad.append('undeclared_count differs from the items')
    if d['unused_count'] != count('unused'):
        bad.append('unused_count differs from the items')
    accounted, observed = count('matched') + count('mismatched'), count('matched') + count('mismatched') + count('undeclared')
    want = round(accounted / observed, 6) if observed else None
    if (d['coverage'] is None) != (want is None) or (want is not None and not rclose(d['coverage'], want)):
        bad.append('coverage does not recompute: %s' % want)
    keys = [(i['clause_kind'], i['clause_id']) for i in items]
    if len(keys) != len(set(keys)):
        bad.append('a clause appears twice')
    for i in items:
        if (i['declared'] is None) != (i['status'] == 'undeclared'):
            bad.append('declared is null exactly for undeclared: ' + i['clause_id'])
        if i['observed'] is None and i['status'] not in ('unused', 'unavailable'):
            bad.append('observed is null for status ' + i['status'])
    if any(i['status'] == 'unavailable' for i in items) and not d['unavailable_reasons']:
        bad.append('unavailable item without a reason')
    return bad


@rcheck('contract-conformance', 'conformance_clauses_complete')
def _(d, path):
    decl = rload(d['declaration_ref'])
    bad = [] if d['declaration_sha256'] == d['declaration_ref']['sha256'] else ['declaration_sha256 differs from declaration_ref']
    have = {i['clause_id'] for i in d['items'] if i['status'] != 'undeclared'}
    return bad + ['no item for declared clause ' + x for x in sorted(rcl_required(decl) - have)]


@rcheck('contract-conformance', 'conformance_matches_record')
def _(d, path):
    rec = next((r for r in rjsonl(d['records_ref']) if r['id'] == d['observation_id']), None)
    if rec is None:
        return ['observation_id is not in the records file']
    keys = ('run_id', 'node_id', 'attempt_id', 'subnode_id', 'cc_name', 'cc_version', 'declaration_sha256')
    return ['%s differs from the record' % k for k in keys if d[k] != rec[k]]


@rcheck('capsule-scorecard', 'scorecard_counts_recompute')
def _(d, path):
    recs = {r['id']: r for r in rjsonl(d['records_ref'])}
    ids, bad = d['record_ids'], []
    if len(ids) != len(set(ids)) or d['execution_count'] != len(ids):
        bad.append('execution_count differs from record_ids')
    sel = [recs[i] for i in ids if i in recs]
    if len(sel) != len(ids):
        return bad + ['record_ids names a line that is not in the records file']
    triple = (d['cc_name'], d['cc_version'], d['declaration_sha256'])
    bad += ['record %s has another CC triple' % r['id'] for r in sel if (r['cc_name'], r['cc_version'], r['declaration_sha256']) != triple]
    if any(r['failure_class'] is None for r in sel):
        return bad + ['a scored record is not classified']
    counts = {k: sum(1 for r in sel if r['failure_class'] == k) for k in ('none', 'capsule', 'input', 'infrastructure', 'scientific')}
    if d['class_counts'] != counts:
        bad.append('class_counts differ from the records: %s' % counts)
    counted = len(sel) - counts['infrastructure'] - counts['scientific']
    if d['counted_count'] != counted:
        bad.append('counted_count must exclude infrastructure and scientific failures: %s' % counted)
    want = round(counts['none'] / counted, 6) if counted else None
    if (d['gate_pass_rate'] is None) != (want is None) or (want is not None and not rclose(d['gate_pass_rate'], want)):
        bad.append('gate_pass_rate does not recompute: %s' % want)
    if sorted(set(r['run_id'] for r in sel)) != sorted(d['run_ids']):
        bad.append('run_ids differ from the records')
    if sum(d['verdict_counts'].values()) > len(sel):
        bad.append('verdict_counts exceed the executions')
    tally = lambda key: {k: sum(1 for r in sel if r[key] == k) for k in {r[key] for r in sel if r[key] is not None}}
    if {x['reason']: x['count'] for x in d['failure_reasons']} != tally('failure_reason_code'):
        bad.append('failure_reasons differ from the records')
    if {x['error_fingerprint']: x['count'] for x in d['error_fingerprints']} != tally('error_fingerprint'):
        bad.append('error_fingerprints differ from the records')
    durations = [r['duration_s'] for r in sel if r['duration_s'] is not None]
    tokens = [r['usage']['input_tokens'] + r['usage']['output_tokens'] for r in sel if r['usage']['input_tokens'] is not None and r['usage']['output_tokens'] is not None]
    for key, values in (('median_duration_s', durations), ('median_total_tokens', tokens)):
        want = statistics.median(values) if values else None
        if (d[key] is None) != (want is None) or (want is not None and not rclose(d[key], want)):
            bad.append('%s does not recompute: %s' % (key, want))
    confs = [rload(r) for r in d['conformance_refs']]
    if d['undeclared_behavior_count'] != sum(c['undeclared_count'] for c in confs):
        bad.append('undeclared_behavior_count differs from the conformance records')
    coverage = [c['coverage'] for c in confs if c['coverage'] is not None]
    want = round(statistics.mean(coverage), 6) if coverage else None
    if (d['mean_declaration_coverage'] is None) != (want is None) or (want is not None and not rclose(d['mean_declaration_coverage'], want)):
        bad.append('mean_declaration_coverage does not recompute: %s' % want)
    return bad


@rcheck('capsule-scorecard', 'scorecard_grants_no_authority')
def _(d, path):
    bad = [] if d['release_authority'] == 'none' else ['release_authority is not none']
    allowed = {d['records_ref']['id']} | {r['id'] for r in d['conformance_refs']}
    return bad + ['scorecard refers to %s, which is neither its records file nor a conformance record' % r['id'] for r in rrefs(d) if r['id'] not in allowed]


@rcheck('capsule-scorecard', 'scorecard_check_rates_valid')
def _(d, path):
    bad = []
    for c in d['check_rates']:
        want = round(c['passed'] / c['executed'], 6) if c['executed'] else None
        if c['passed'] > c['executed'] or (c['pass_rate'] is None) != (want is None) or (want is not None and not rclose(c['pass_rate'], want)):
            bad.append('check rate of %s is inconsistent' % c['check_id'])
    return bad


def rexport_label(e):
    key = '%s/%s/%s/%s' % (e['run_id'], e['node_id'], e['attempt_id'], e['subnode_id'] if e['subnode_id'] is not None else '-')
    return 'held_out' if int(hashlib.sha256(key.encode('utf-8')).hexdigest()[:8], 16) % 5 == 0 else 'development'


@rcheck('sample-run-export', 'export_content_hash_recomputes')
def _(d, path):
    files = sorted(d['files'], key=lambda f: f['path'].encode('utf-8'))
    want = hashlib.sha256(''.join('%s\t%s\n' % (f['path'], f['sha256']) for f in files).encode('utf-8')).hexdigest()
    bad = [] if d['content_sha256'] == want else ['content_sha256 does not recompute from files: ' + want]
    return bad + (['a files path is repeated'] if len({f['path'] for f in files}) != len(files) else [])


@rcheck('sample-run-export', 'export_labels_match_rule')
def _(d, path):
    return ['label of %s should be %s' % (e['observation_id'], rexport_label(e)) for e in d['entries'] if e['label'] != rexport_label(e)]


@rcheck('sample-run-export', 'export_entries_have_files')
def _(d, path):
    paths = [f['path'] for f in d['files']]
    bad = ['files path escapes the folder: ' + x for x in paths if x.startswith('/') or '..' in x.split('/')]
    recs = {r['id']: r for r in rjsonl(d['records_ref'])}
    for e in d['entries']:
        if not e['call_folder'].endswith('/') or not any(x.startswith(e['call_folder']) for x in paths):
            bad.append('no file under call_folder ' + e['call_folder'])
        r = recs.get(e['observation_id'])
        if r is None or any(r[k] != e[k] for k in ('run_id', 'node_id', 'attempt_id', 'subnode_id', 'failure_class')):
            bad.append('entry %s does not match its record' % e['observation_id'])
    return bad


PLATFORM_KINDS = PLATFORM_KINDS + ('contract-conformance', 'capsule-scorecard', 'sample-run-export')
PLATFORM_KINDS = PLATFORM_KINDS + ('screening-rubric', 'poc-artifact-bundle', 'execution-receipt', 'provisioning-receipt', 'rsi-session', 'rsi-session-result', 'candidate-package', 'rsi-target-profile', 'rsi-attempt', 'rsi-loop-feedback', 'rsi-referee-evidence', 'rsi-evidence-export', 'candidate-provenance', 'security-clearance', 'rsi-opportunity', 'rsi-completion-report')


# ---- additional host checks
@rcheck('run-plan', 'topological_order_is_kahn')
def _(d, path):
    want = kahn_order(d['nodes'])
    return [] if d['topological_order'] == want else ['topological_order %s is not the Kahn order %s with the source-list tie rule' % (d['topological_order'], want)]


@rcheck('run-bundle', 'dispatches_sequential')
def _(d, path):
    spans = sorted((e['started_at'], e['ended_at'] or '9999', e['node_id']) for e in d['node_dispatches'])
    return ['dispatch of %s starts before the previous dispatch ended' % b[2] for a, b in zip(spans, spans[1:]) if b[0] < a[1]]


@rcheck('run-bundle', 'dispatch_attempts_unique')
def _(d, path):
    ids = [e['attempt_id'] for e in d['node_dispatches']]
    return ['attempt %s is dispatched more than once (no replay)' % a for a in sorted(set(ids)) if ids.count(a) > 1]


@rcheck('client-submission', 'profile_matches_readiness')
def _(d, path):
    ready = load(EX / 'client_readiness.json')
    return [] if d['profile_id'] == ready['evaluation_profile'] else ['profile_id %s differs from the readiness evaluation_profile %s' % (d['profile_id'], ready['evaluation_profile'])]


@rcheck(BR, 'no_trial_no_install')
def _(d, path):
    return [k + ' is true' for k in ('trial_executed', 'packages_installed') if d[k]]


PLATFORM_KINDS = PLATFORM_KINDS + ('route-record', 'model-call', 'client-upload')


@rcheck('route-record', 'route_record_structure')
def _(d, path):
    return rfield_errors('route-record:field-contract:1', d)


@rcheck('route-record', 'route_record_consistent')
def _(d, path):
    bad = []
    source = d['decision_source']
    if (source == 'codex_router_disabled') != (not d['router_enabled']):
        bad.append('codex_router_disabled exactly when router_enabled is false')
    if (d['router_failure'] is None) == (source == 'codex_router_failed'):
        bad.append('router_failure is set exactly when decision_source is codex_router_failed')
    if (d['route_decision_ref'] is not None) != (source == 'router'):
        bad.append('route_decision_ref is set exactly when decision_source is router')
    if source != 'router' and d['model_id'] != 'codex-cli-default':
        bad.append('a Codex route record names the Codex route model')
    return bad


@rcheck('model-call', 'model_call_structure')
def _(d, path):
    return rfield_errors('model-call:field-contract:1', d)


@rcheck('model-call', 'model_call_outcome_consistent')
def _(d, path):
    bad = []
    if (d['ended_at'] is None) != (d['outcome'] == 'outcome_unknown'):
        bad.append('ended_at is null exactly for outcome_unknown')
    if d['ended_at'] is not None and d['ended_at'] < d['started_at']:
        bad.append('ended_at is before started_at')
    if d['purpose'] == 'routing_selection' and d['route_decision_ref'] is not None:
        bad.append('a routing_selection call has no route decision yet')
    return bad


@rcheck('model-call', 'provider_error_code_consistent')
def _(d, path):
    return [] if (d['provider_error_code'] is not None) == (d['outcome'] == 'failed') else ['provider_error_code is non-null exactly when outcome is failed']


@rcheck('rsi-session-result', 'no_evidence_no_hidden_query')
def _(d, path):
    if d['referee_evidence_ref'] is not None:
        return []
    bad = []
    if d['queries_used'] != 0:
        bad.append('a child with no referee evidence was rejected before any hidden query, so queries_used is 0')
    if d['statistics'] is not None or d['outcome'] == 'QUALIFIED':
        bad.append('without referee evidence there are no statistics and no QUALIFIED outcome')
    return bad


def rblueprint_frozen(d, path):
    frozen = {'id': 'hypothesis_blueprint.json', 'sha256': hashlib.sha256((EX / 'hypothesis_blueprint.json').read_bytes()).hexdigest()}
    return [] if d['blueprint_ref'] == frozen else ['blueprint_ref is not the frozen blueprint recorded at acceptance']


for _kind in (PM, BP, EV):
    rcheck(_kind, 'blueprint_frozen_hash_recorded')(rblueprint_frozen)


def _gate_decision_schema(d, path):
    return [e.message for e in validators['urn:jiuwenswarm:m1-design:gate-decision:2.0.0'].iter_errors(d)]


SCHEMA_CHECKS['gate-decision']['gate_decision_schema'] = _gate_decision_schema


# ---- checking profiles that bound check plans point to: each is checked against its contract by the registered checks;
# here each bound check plan must list the semantic criteria of the profile it points to
profiles = {x['path']: load(EX / x['path']) for x in index if x.get('field_contract_id') == 'checking-profile:field-contract:1' and x.get('expect') != 'invalid'}
for _item in index:
    if _item.get('field_contract_id') == 'bound-check-plan:field-contract:2' and _item.get('expect') != 'invalid':
        _plan = load(EX / _item['path'])
        _profile = profiles.get(_plan['profile_ref']['id'])
        if _profile is None:
            continue
        require([c['criterion_id'] for c in _profile['criteria']] == _plan['mandatory_semantic'], 'Check plan %s semantic checks differ from checking profile %s' % (_item['path'], _plan['profile_ref']['id']))


# ---- run the registered checks over the index
RKIND = {'candidate-set': CS, 'screening-result': SR, 'opportunity-card': OC, 'hypothesis-blueprint': HB, 'poc-manifest': PM, 'build-receipt': BR,
         'benchmark-payload': BP, 'evaluation-verdict': EV, 'delivery-manifest': DM, 'plan-proposal': 'plan-proposal', 'static-template': 'static-template',
         'run-plan': 'run-plan', 'library-snapshot': 'library-snapshot', 'dispatch-record': 'dispatch-record', 'plan-outcome': 'plan-outcome',
         'gate-decision-index': 'gate-decision-index', 'search-scope': 'search-scope', 'check-bundle': 'check-bundle', 'checking-profile': 'checking-profile'}
RKIND.update({k: k for k in PLATFORM_KINDS})
rchecked = 0
rrejected = 0
for item in index:
    fc = item.get('field_contract_id')
    if not fc:
        continue
    kind = RKIND.get(interfaces[fc]['name']) if fc in interfaces else None
    if not kind or kind not in RCHECKS:
        continue
    doc = load_example(EX / item['path'])
    failures = {}
    for cid, fn in RCHECKS[kind].items():
        try:
            found = fn(doc, item['path'])
        except Exception as exc:  # a check that cannot run on the example is a failure of that check
            found = ['check could not run: %s: %s' % (type(exc).__name__, exc)]
        if found:
            failures[cid] = found
    rchecked += len(RCHECKS[kind])
    if item.get('expect') == 'invalid':
        want = item['rejected_by']
        if want not in RCHECKS[kind]:
            errors.append('%s: rejected_by %s is not a check of %s' % (item['path'], want, kind))
        elif want not in failures:
            errors.append('%s: expected invalid but check %s passed' % (item['path'], want))
        else:
            rrejected += 1
    else:
        for cid, found in failures.items():
            errors.append('%s: check %s failed: %s' % (item['path'], cid, '; '.join(found[:3])))

for item in index:
    name = next((c['name'] for c in catalog['contracts'] if c['schema_id'] == item.get('schema_id')), None)
    if name not in SCHEMA_CHECKS:
        continue
    doc = load_example(EX / item['path'])
    failures = {}
    for cid, fn in SCHEMA_CHECKS[name].items():
        try:
            found = fn(doc, item['path'])
        except Exception as exc:  # a check that cannot run on the example is a failure of that check
            found = ['check could not run: %s: %s' % (type(exc).__name__, exc)]
        if found:
            failures[cid] = found
    rchecked += len(SCHEMA_CHECKS[name])
    if item.get('expect') == 'invalid':
        want = item.get('rejected_by')
        if want not in SCHEMA_CHECKS[name]:
            errors.append('%s: rejected_by %s is not a check of %s' % (item['path'], want, name))
        elif want not in failures:
            errors.append('%s: expected invalid but check %s passed' % (item['path'], want))
        else:
            rrejected += 1
    else:
        for cid, found in failures.items():
            errors.append('%s: check %s failed: %s' % (item['path'], cid, '; '.join(found[:3])))

# ---- end-to-end chain: candidate_set -> screening_result -> opportunity_card -> hypothesis_blueprint -> poc_manifest/build_receipt
# ---- -> benchmark_payload -> evaluation_verdict -> delivery_manifest. Every ref resolves and the refs agree.
def rchain():
    bad = []
    r = lambda n: {'id': n, 'sha256': hashlib.sha256((EX / n).read_bytes()).hexdigest()}
    cs, sr, oc = load(EX / 'candidate_set.json'), load(EX / 'screening_result.json'), load(EX / 'opportunity_card.json')
    bp, pm, br = load(EX / 'hypothesis_blueprint.json'), load(EX / 'poc_manifest.json'), load(EX / 'build_receipt.json')
    pl, ev, dm = load(EX / 'benchmark_payload.json'), load(EX / 'evaluation_verdict.json'), load(EX / 'delivery_manifest.json')
    scope = load(EX / 'search_scope.json')
    ctx = (('scope.brief_ref', scope['brief_ref']), ('candidate_set.brief_ref', cs['brief_ref']), ('screening_result.brief_ref', sr['brief_ref']), ('opportunity_card.brief_ref', oc['brief_ref']),
           ('hypothesis_blueprint.brief_ref', bp['brief_ref']), ('evaluation_verdict.brief_ref', ev['brief_ref']), ('delivery_manifest.brief_ref', dm['brief_ref']))
    for name, value in ctx:
        if value != ctx[0][1]:
            bad.append('%s names a different Brief' % name)
    links = (('candidate_set.scope_ref', cs['scope_ref'], r('search_scope.json')),
             ('screening_result.candidate_ref', sr['candidate_ref'], r('candidate_set.json')),
             ('opportunity_card.candidate_ref', oc['candidate_ref'], r('candidate_set.json')),
             ('opportunity_card.screening_ref', oc['screening_ref'], r('screening_result.json')),
             ('hypothesis_blueprint.opportunity_ref', bp['opportunity_ref'], r('opportunity_card.json')),
             ('poc_manifest.blueprint_ref', pm['blueprint_ref'], r('hypothesis_blueprint.json')),
             ('build_receipt.manifest_ref', br['manifest_ref'], r('poc_manifest.json')),
             ('benchmark_payload.blueprint_ref', pl['blueprint_ref'], r('hypothesis_blueprint.json')),
             ('benchmark_payload.poc_ref', pl['poc_ref'], r('poc_manifest.json')),
             ('evaluation_verdict.blueprint_ref', ev['blueprint_ref'], r('hypothesis_blueprint.json')),
             ('evaluation_verdict.benchmark_ref', ev['benchmark_ref'], r('benchmark_payload.json')),
             ('delivery_manifest.verdict_ref', dm['verdict_ref'], r('evaluation_verdict.json')))
    for name, got, want in links:
        if got != want:
            bad.append('%s does not point to the current %s' % (name, want['id']))
    listed = {x['id']: x['sha256'] for x in dm['artifact_refs']}
    for n in ('candidate_set', 'screening_result', 'opportunity_card', 'hypothesis_blueprint', 'poc_manifest', 'benchmark_payload', 'evaluation_verdict'):
        if listed.get(n + '.json') != r(n + '.json')['sha256']:
            bad.append('delivery_manifest does not list the current %s' % n)
    if sr['selected_idea_id'] != oc['idea_id']:
        bad.append('selected idea differs from the card idea')
    brief = load(EX / 'lifecycle_research_brief.json')
    if bp['environment_ref'] != pm['environment_ref'] or pl['environment_lock_ref'] != bp['environment_ref']:
        bad.append('environment lock differs along the chain')
    if [m['metric_id'] for m in bp['metrics']] != [m['metric_id'] for m in pl['metrics']] or [f['metric_id'] for f in ev['findings']] != [m['metric_id'] for m in bp['metrics']]:
        bad.append('metric sets differ along the chain')
    if {t['id'] for t in brief['target_metrics']} - {m['target_id'] for m in bp['metrics']}:
        bad.append('a Brief target is not measured')
    return bad


for message in rchain():
    errors.append('chain: ' + message)


# ---- declared output check IDs must be defined on the CC page
PAGE_FOR = {'research.search': 'search.md', 'research.screening': 'screening.md', 'research.hypothesis': 'hypothesis.md', 'research.builder': 'builder.md',
            'research.benchmark': 'research-benchmark.md', 'research.evaluation': 'scientific-evaluation.md', 'research.delivery': 'delivery.md',
            'research.planner': 'planner.md', 'research.verifier': 'verifier.md'}
for cc_name, page_name in PAGE_FOR.items():
    page_text = (REF / 'capsules' / page_name).read_text(encoding='utf-8')
    defined = set(re.findall(r'^\| `([a-z][a-z0-9_]*)` \|', page_text, flags=re.M))
    declaration = load(EX / DECL_FILES[cc_name])
    for port in declaration['ports']['outputs']:
        for check_id in port['check_ids']:
            require(check_id in defined, 'Declared check ID %s of %s is not defined on %s' % (check_id, cc_name, page_name))
    for check in declaration['guarantees']['checks']:
        require(check['id'] in defined, 'Declared guarantee check %s of %s is not defined on %s' % (check['id'], cc_name, page_name))


# ---- checking profiles and review manifests list only criteria a verifier can answer from the declaration and the output
BANNED_CRITERIA = {'fidelity', 'consistency', 'requirements_usability', 'registered_rule_applied'}
for profile in sorted(EX.glob('*_checking_profile.json')) + sorted(EX.glob('*review_context.json')):
    for criterion in (c['criterion_id'] if isinstance(c, dict) else c for c in load(profile).get('criteria', [])):
        require(criterion not in BANNED_CRITERIA and not any(w in criterion for w in FIDELITY_WORDS), 'Verifier criterion %s in %s needs inputs or means fidelity' % (criterion, profile.name))


def ref_for(name):
    return {'id':name,'sha256':hashlib.sha256((EX/name).read_bytes()).hexdigest()}

errors.extend(rsi_issues(load(EX/'rsi_referee_evidence.json')))
candidate=load(EX/'rsi_child_candidate.json')
require(candidate['implementation_refs']==[load(EX/'rsi_attempt_01.json')['child_ref']], 'Candidate body/attempt mismatch')
require(load(EX/'rsi_admission.json')['candidate_ref']==ref_for('candidate_package.json'), 'Admission references wrong package')
parent=load(EX/'ranking_declaration.json'); child=load(EX/'ranking_child_declaration.json')
for key in parent:
    if key!='identity':require(parent[key]==child[key], 'RSI changes frozen declaration semantics')
for key in parent['identity']:
    if key not in ('version_label','carrier','body','lineage'):require(parent['identity'][key]==child['identity'][key], 'RSI changes frozen identity semantics')
require(child['identity']['body'][0]['sha256']==candidate['implementation_refs'][0]['sha256'], 'Derived body pin mismatch')

for mode in ('missing_binding','unknown_contract','input_inventory','oversized_limit','port_name'):
    bad=copy.deepcopy(load(EX/'intention_subnode_contract.json'))
    if mode=='missing_binding':bad['bindings']=[]
    elif mode=='unknown_contract':bad['outputs'][0]['contract_id']='invented:contract'
    elif mode=='input_inventory':bad['input_refs']=[]
    elif mode=='oversized_limit':bad['bindings'][0]['limits']['model_calls']=999
    else:bad['inputs'][0]['name']='invented-port'
    require(bool(node_issues(bad)) or not validators['urn:jiuwenswarm:m1-design:subnode-execution-contract:1.0.0'].is_valid(bad), 'Node negative accepted: '+mode)
    negative_count += 1
for mode in ('lineage','mandatory','final_reuse'):
    bad=copy.deepcopy(load(EX/'rsi_referee_evidence.json'))
    if mode=='lineage':bad['child_ref']=bad['parent_ref']
    elif mode=='mandatory':bad['mandatory_parent_tests_passed']=False
    else:bad['final_evaluations']=2
    require(bool(rsi_issues(bad)), 'RSI negative accepted: '+mode)
    negative_count += 1

# Unmapped optional declaration ports are tested against an in-memory resolver.
old_resolved=resolved
def resolved(r):
    d=old_resolved(r)
    if r['id']=='capsule_declaration.json':
        d['ports']['inputs'].append(dict(d['ports']['inputs'][0],name='optional-context',required=False))
        d['ports']['outputs'].append(dict(d['ports']['outputs'][0],name='optional-intent',required=False))
    return d
require(not node_issues(load(EX/'intention_subnode_contract.json')), 'Optional declaration port incorrectly mandatory')
optional=copy.deepcopy(load(EX/'intention_subnode_contract.json'));optional['outputs'].append(dict(optional['outputs'][0],name='optional-intent',required=False))
require(not node_issues(optional) and validators['urn:jiuwenswarm:m1-design:subnode-execution-contract:1.0.0'].is_valid(optional), 'Optional output incorrectly required')
resolved=old_resolved
bad=copy.deepcopy(load(EX/'gate_decision.json'));bad['invocation_refs']=[]
require('incomplete/duplicate work binding observations' in gate_issues(bad), 'Missing binding observation accepted');negative_count+=1
attempt=load(EX/'rsi_attempt_01.json');genesis=resolved(attempt['chain_root_ref'])
require(genesis['session_id']==attempt['session_id'] and genesis['target_ref']==attempt['target_ref'] and genesis['hash_profile_ref']==attempt['hash_profile_ref'], 'RSI genesis/profile mismatch')
require(attempt['sequence']==1 and attempt['previous_ref'] is None, 'First RSI chain link must start at separate genesis')
for key in ('hash_profile_ref','chain_root_ref'):
    bad=copy.deepcopy(attempt);bad.pop(key)
    require(bool(field_errors(bad,interfaces['rsi-attempt:field-contract:1']['fields'])), 'Missing RSI custody accepted');negative_count+=1

bad=copy.deepcopy(load(EX/'intention_subnode_contract.json'));bad['bindings'].append(copy.deepcopy(bad['bindings'][0]))
require(bool(node_issues(bad)) and not validators['urn:jiuwenswarm:m1-design:subnode-execution-contract:1.0.0'].is_valid(bad), 'Unsupported M1 member composition accepted');negative_count+=1

# Field summary check. Each field of a JSON field contract must appear, with the same type,
# in a table of the page section that the catalog names. Page tables may write the type with or
# without backticks. Types without a `document` entry are found by their heading or bold label.
def heading_slug(text):
    text = re.sub(r'<[^>]*>', '', text).lower().replace('`', '').replace('*', '')
    return re.sub(r'[^\w\- ]', '', text, flags=re.UNICODE).replace(' ', '-')


def page_lines(path):
    return path.read_text(encoding='utf-8-sig').splitlines()


def table_rows(lines):
    rows = {}
    for line in lines:
        match = re.match(r'^\|\s*`([^`]+)`\s*\|\s*`?([^|`]*?)`?\s*\|', line)
        if match:
            rows.setdefault(match.group(1), set()).add(match.group(2).strip())
    return rows


def section_rows(document):
    name, fragment = document.split('#')
    path = (REF / name).resolve()
    if not path.is_relative_to(REF.resolve()) or not path.is_file():
        require(False, 'Missing/escaping authoritative field document: ' + document)
        return {}
    lines = page_lines(path)
    counts = {}
    start = level = None
    for number, line in enumerate(lines):
        match = re.match(r'^(#{1,6})\s+(.+?)(?:\s+#+)?$', line)
        if not match:
            continue
        base = heading_slug(match.group(2))
        index_ = counts.get(base, 0)
        counts[base] = index_ + 1
        if (base + (f'-{index_}' if index_ else '')) == fragment and start is None:
            start, level = number, len(match.group(1))
        elif start is not None and len(match.group(1)) <= level:
            return table_rows(lines[start + 1:number])
    return table_rows(lines[start + 1:]) if start is not None else {}


TYPE_PAGES = sorted((REF / 'capsules').glob('*.md')) + [REF / 'run-plan.md', REF / 'field-catalog.md', REF / 'derived-records.md', REF / 'rsi-contracts.md', REF / 'model-routing-contract.md', REF / 'intent-and-requirements.md', REF / 'checking.md']


def type_rows(name):
    label = re.compile(r'^(?:#{2,6}\s+|\*\*)?`?' + re.escape(name) + r'`?(?:\*\*)?(?:\s.*)?$')
    stop = re.compile(r'^(?:#{1,6}\s|\*\*[^*]+\*\*\s*$)')
    rows = {}
    for page in TYPE_PAGES:
        lines = page_lines(page)
        for number, line in enumerate(lines):
            if label.match(line.strip()):
                end = next((k for k in range(number + 1, len(lines)) if stop.match(lines[k])), len(lines))
                for key, value in table_rows(lines[number + 1:end]).items():
                    rows.setdefault(key, set()).update(value)
    return rows


def view_errors(label, fields, rows):
    if not rows:
        return []
    return [f'Field view/type drift {label}.{key}' for key, info in fields.items() if info['type'] != 'markdown' and info['type'] not in rows.get(key, set())]


for item in field_catalog['interfaces']:
    mapping = next(x for x in catalog['interfaces'] if x['id'] == item['id'])
    errors.extend(view_errors(item['name'], item['fields'], section_rows(mapping['document'])))
TYPE_TEXT = ''.join(page.read_text(encoding='utf-8-sig') for page in TYPE_PAGES)
for type_name, spec in types.items():
    rows = section_rows(spec['document']) if 'document' in spec else type_rows(type_name)
    require(bool(rows) or ('`' + type_name + '`') in TYPE_TEXT or ('**' + type_name + '**') in TYPE_TEXT or ('### ' + type_name) in TYPE_TEXT, 'Undocumented type: ' + type_name)
    errors.extend(view_errors(type_name, spec['fields'], rows))
for label, fields in [(x['name'], x['fields']) for x in field_catalog['interfaces']] + [(n, x['fields']) for n, x in types.items()]:
    for key, info in fields.items():
        require(isinstance(info['required'], bool) and bool(info['meaning'].strip()), 'Incomplete field meaning/requiredness: ' + label + '.' + key)
        require(info['type'].removeprefix('nullable-').removesuffix('[]') in set(types) | set(interface_types) | primitive_types, 'Unknown nested field type: ' + label + '.' + key)

contract_index=(REF/'README.md').read_text(encoding='utf-8')
for x in catalog['contracts']:
    require('('+x['schema']+')' in contract_index, 'Unindexed exact contract: '+x['name'])
for x in catalog['interfaces']:
    require('('+x['document']+')' in contract_index, 'Unindexed field contract: '+x['name'])
cc_key='urn:jiuwenswarm:m1-design:capsule-declaration:1.0.0'
for mode in ('missing_budget_mode','unbound_budget_mode'):
    bad=copy.deepcopy(load(EX/'capsule_declaration.json'))
    if mode=='missing_budget_mode':bad['budget']['enforcement'].pop('wall_s')
    else:bad['budget']['enforcement']['tokens']='hard'
    require(not validators[cc_key].is_valid(bad), 'Budget boundary negative accepted: '+mode);negative_count+=1
old_resolved=resolved
def resolved(r):
    d=old_resolved(r)
    if r['id']=='capsule_declaration.json':d['identity']['kind']='composite'
    return d
require('composite dispatch unsupported in M1' in node_issues(load(EX/'intention_subnode_contract.json')), 'Future composite form dispatched in M1');negative_count+=1
resolved=old_resolved



def brief_issues(b):
    result=[]
    q=resolved(b['intake_ref']); ir=resolved(b['intent_ref'])
    if q['request_ref']!=ir['request_ref']:result.append('wrong intake/intent request')
    ids=[s['id'] for s in b['mandatory_requirements']+b['optional_preferences']]
    if len(ids)!=len(set(ids)):result.append('duplicate requirement ID')
    for row in b['acceptance_expectations']+b['evidence_obligations']+b['target_metrics']:
        if not set(row['requirement_ids'])<=set(ids):result.append('unresolved obligation')
    bindings=[p['resource_ref'] for p in b['input_bindings']]
    if bindings!=b['resource_refs'] or any(r not in q['resource_refs'] for r in bindings):result.append('wrong supplied input inventory')
    for assumption in b['assumptions']:
        policy=resolved(assumption['authority_ref'])
        for pointer in assumption['affected_fields']:
            value=b
            try:
                for token in pointer.strip('/').split('/'):
                    value=value[int(token)] if isinstance(value,list) else value[token.replace('~1','/').replace('~0','~')]
            except (KeyError,ValueError,IndexError,TypeError):result.append('nonexistent assumption field');continue
            if not isinstance(value,dict) or value.get('origin')!='system_default' or value.get('normalized_value')!=policy.get('hardware_profile') or assumption['authority_ref'] not in value['source_refs']:result.append('unsupported default attribution')
    return result

def aggregate_issues(g):
    result=[]; parent=resolved(g['node_contract_ref']); checks=resolved(g['deterministic_result_ref']);plan=resolved(g['check_plan_ref'])
    if g['scope_kind']!='node' or g['subnode_id'] is not None or g['contract_ref']!=g['node_contract_ref']:result.append('wrong aggregate scope')
    if any(g[k]!=parent[k] for k in ('run_id','node_id','attempt_id')):result.append('wrong aggregate identity')
    if plan['contract_ref']!=g['contract_ref'] or plan['input_refs']!=parent['input_refs'] or checks['check_plan_ref']!=g['check_plan_ref']:result.append('wrong aggregate check binding')
    if {r['check_id'] for r in checks['results']}!=set(plan['mandatory_deterministic']) or len(checks['results'])!=len(plan['mandatory_deterministic']) or any(r['outcome']!='PASS' for r in checks['results']):result.append('incomplete aggregate checks')
    decisions=[resolved(r) for r in g['internal_decision_refs']]
    required={s['subnode_id'] for s in parent['subnodes'] if s['role']=='work' and s['required']}
    if {d['subnode_id'] for d in decisions}!=required or len(decisions)!=len(required):result.append('missing internal decisions')
    if any(d['action']!='advance' or d['node_contract_ref']!=g['node_contract_ref'] or gate_issues(d) for d in decisions):result.append('invalid internal acceptance')
    observed=[resolved(r) for r in g['invocation_refs']];expected={s['subnode_id'] for s in parent['subnodes'] if s['required']}
    if {o['subnode_id'] for o in observed}!=expected or len(observed)!=len(expected):result.append('missing aggregate invocation')
    if any(resolved(o['contract_ref'])['node_contract_ref']!=g['node_contract_ref'] for o in observed):result.append('wrong aggregate observation parent')
    finals=[d for d in decisions if g['accepted_refs'] and all(r in d['accepted_refs'] for r in g['accepted_refs'])]
    if len(finals)!=1 or finals[0]['assessment_ref']!=g['assessment_ref'] or g['accepted_refs']!=g['output_refs'] or not set(map(json.dumps, checks.get('subject_refs') or [checks['subject_ref']])) & set(map(json.dumps, g['output_refs'])):result.append('unaccepted aggregate output')
    return result

for n in ('research_brief.json','lifecycle_research_brief.json'):
    errors.extend(n+': '+i for i in brief_issues(load(EX/n)))
errors.extend(aggregate_issues(load(EX/'gate_science_node_pass.json')))
brief_key=next(k for k in schemas if ':research-brief:' in k)
for mode in ('missing_finding','duplicate_finding','wrong_review_subject'):
    saved=resolved
    def resolved(r):
        value=saved(r)
        if r['id']=='intent_assessment.json':
            if mode=='missing_finding':value['findings']=value['findings'][:-1]
            elif mode=='duplicate_finding':value['findings'].append(value['findings'][0])
            else:value['subject_ref']=ref_for('research_brief.json')
        return value
    require(bool(gate_issues(load(EX/'gate_decision.json'))), 'Verification coverage regression accepted: '+mode);negative_count+=1
    resolved=saved


def enclosing_issues(n):
    out=[];assignments=n['subnodes']; ids=[s['subnode_id'] for s in assignments]
    if not ids or len(ids)!=len(set(ids)):out.append('missing/duplicate subnode')
    pending=set(ids);done=set()
    while pending:
        ready={s['subnode_id'] for s in assignments if s['subnode_id'] in pending and set(s['depends_on'])<=done}
        if not ready:out.append('cyclic/unresolved internal dependency');break
        done|=ready;pending-=ready
    if n['input_refs']!=[r for p in n['inputs'] for r in p['artifact_refs']]:out.append('wrong external input inventory')
    if any(s['role'] not in ('work','verifier') for s in assignments):out.append('unsupported subnode role')
    if any(g['subject_subnode_id'] not in ids for g in n['gate_assignments']):out.append('unbound gate subject')
    for s in assignments:
        template=resolved(s['template_ref'])
        if template['capsule_ref']!=s['capsule_ref']:out.append('wrong declaration/template pin')
    return out

for n in ('intention_node_contract.json','science_node_contract.json'):
    errors.extend(n+': '+i for i in enclosing_issues(load(EX/n)))
for mode in ('cycle','missing_subnode','missing_gate_subject'):
    bad=copy.deepcopy(load(EX/'intention_node_contract.json'))
    if mode=='cycle':bad['subnodes'][0]['depends_on']=['requirements']
    elif mode=='missing_subnode':bad['subnodes']=[]
    else:bad['gate_assignments'][0]['subject_subnode_id']='unknown'
    require(bool(enclosing_issues(bad)),'Enclosing-node regression accepted: '+mode);negative_count+=1

# Portable package boundaries replace the removed received-source collection.
exec(compile((REF/'package_checks.py').read_text(encoding='utf-8'), str(REF/'package_checks.py'), 'exec'))
for issue in delivery_issues(ROOT):
    require(False, issue)


def slug(text):
    text = re.sub(r'<[^>]*>', '', text).lower()
    text = text.replace('`', '').replace('*', '')
    return re.sub(r'[^\w\- ]', '', text, flags=re.UNICODE).replace(' ', '-')


def anchors(path):
    text = path.read_text(encoding='utf-8-sig')
    counts = {}
    result = set()
    for line in text.splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)(?:\s+#+)?$', line)
        if match:
            base = slug(match.group(1))
            number = counts.get(base, 0)
            counts[base] = number + 1
            result.add(base + (f'-{number}' if number else ''))
    result.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', text))
    return result


link_count = 0
# Scan all delivered Markdown-bearing text for portable local navigation.
documents = list(ROOT.rglob('*.md')) + list(ROOT.rglob('*.txt'))
for path in documents:
    text = path.read_text(encoding='utf-8-sig')
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    destinations = re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text)
    destinations += re.findall(r'^\[[^\]]+\]:\s+(\S+)', text, flags=re.M)
    for destination in destinations:
        destination = destination.strip().strip('<>')
        parsed = urlsplit(destination)
        if parsed.scheme or destination.startswith('//'):
            continue
        target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
        link_count += 1
        require(target.is_relative_to(ROOT), f'Nonportable required link: {path.relative_to(ROOT)} -> {destination}')
        require(target.exists(), f'Missing link: {path.relative_to(ROOT)} -> {destination}')
        if target.is_file() and parsed.fragment and target.suffix.lower() in ('.md', '.txt'):
            require(unquote(parsed.fragment) in anchors(target), f'Missing anchor: {path.relative_to(ROOT)} -> {destination}')

clause_index = load(REF / 'prd-clause-index.json')
headings = [(c['number'],c['title']) for c in clause_index['clauses']]
require(len(headings)==188 and len(set(n for n,_ in headings))==188, 'Incomplete/duplicate PRD clause index')
if len(sys.argv)>2:
    supplied=Path(sys.argv[2]).resolve()
    require(hashlib.sha256(supplied.read_bytes()).hexdigest()==clause_index['source_sha256'], 'External PRD source differs from audited receipt')
    actual_headings=re.findall(r'^#{2,5}\s+(\d+\.\d+(?:\.\d+)?)\s+(.+)$',supplied.read_text(encoding='utf-8-sig'),re.M)
    require(actual_headings==headings,'External PRD clause crosswalk drift')
coverage = (ROOT / PAGES['clause_coverage']).read_text(encoding='utf-8')
for number, title in headings:
    require(f'| §{number} {title} |' in coverage, 'Missing current source heading ' + number)
audit = (ROOT / PAGES['user_story_map']).read_text(encoding='utf-8')
for number in range(1, 21):
    require(f'| US{number:02d} |' in audit, 'Missing user-story mapping')

def tier1_words(path):
    # Counts prose and Mermaid, since readers read both. Other code fences are excluded.
    # Fences are parsed line by line, and tokens without a letter or digit (table pipes) are not words.
    kept, fence = [], None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.lstrip().startswith('```'):
            fence = None if fence else line.strip()[3:].strip() or 'code'
            continue
        if fence in (None, 'mermaid'):
            kept.append(line)
    return sum(1 for token in ' '.join(kept).split() if re.search(r'[A-Za-z0-9]', token))
words = sum(tier1_words(ROOT / name) for name in PAGES['tier1'])
require(words <= PAGES['tier1_word_cap'], 'Tier 1 exceeds its reading-time cap: ' + str(words))
require(not (ROOT / 'handoff.md').exists(), 'Obsolete coding handoff still present')

# Required current build/navigation must not regress to the historical Intent-only slice.
for name in PAGES['brief_boundary']:
    current=(ROOT/name).read_text(encoding='utf-8')
    require('Research Brief' in current or 'research_brief.json' in current, 'Current build missing Brief boundary: '+name)
    require('ends at accepted Intent or visible halt' not in current, 'Obsolete Intent-only completion: '+name)
require(not (REF/'schemas/node-execution-contract.schema.json').exists(), 'Retired CC-sized node schema remains current')
for entry in catalog['interfaces']:
    require(bool(entry.get('applicable_phases')) and bool(entry.get('producer')) and bool(entry.get('consumers')), 'Contract missing lifecycle/owner: '+entry['name'])

for path in ROOT.rglob('*.md'):
    if 'sources' not in path.relative_to(ROOT).parts:
        require('handoff.md' not in path.read_text(encoding='utf-8'), 'Stale handoff link: ' + str(path))

for entry in catalog['field_contracts']:
    document, fragment = entry['document'].split('#')
    require(fragment in anchors(REF / document), 'Missing catalog field-contract section')
    require(entry['version'] == catalog['version'] and bool(entry['applicable_phases']), 'Field-contract version/phase mismatch')

# Every maintained page names its tier and its hub, so readers and agents can navigate.
for path in ROOT.rglob('*.md'):
    parts = path.relative_to(ROOT).parts
    if parts[0] in ('sources', 'diagrams') or 'examples' in parts:
        continue
    require('`Tier ' in path.read_text(encoding='utf-8-sig')[:600], 'Page lacks a Tier and Part of line: ' + path.relative_to(ROOT).as_posix())
# Canonical terms: forbidden phrases come from the glossary table.
SYNONYM_EXEMPT = {'glossary.md', 'method/decisions.md', 'side-systems/owner-rulings.md'}
forbidden = []
gloss = (ROOT / 'glossary.md').read_text(encoding='utf-8-sig')
section = gloss.split('## Canonical terms', 1)[1].split('\n## ', 1)[0]
for row in section.splitlines():
    cells = [c.strip() for c in row.strip().strip('|').split('|')]
    if len(cells) == 4 and cells[0] not in ('Term', '---'):
        forbidden += re.findall(r'`([^`]+)`', cells[3])
synonym_hits = []
for path in ROOT.rglob('*.md'):
    rel = path.relative_to(ROOT).as_posix()
    if rel.split('/')[0] in ('sources', 'diagrams') or rel in SYNONYM_EXEMPT:
        continue
    text = path.read_text(encoding='utf-8-sig')
    if rel == PAGES['clause_coverage']:
        # The first cell of each row quotes a PRD heading verbatim. Its words are not ours to change.
        text = re.sub(r'^\| §[^|]*\|', '|', text, flags=re.M)
    text = text.lower()
    for phrase in forbidden:
        if phrase.lower() in text:
            synonym_hits.append('%s: %r' % (rel, phrase))
if PAGES['synonyms_enforced']:
    for hit in synonym_hits:
        require(False, 'Forbidden synonym in ' + hit)
elif synonym_hits:
    print('WARN: %d forbidden synonym hits (report-only)' % len(synonym_hits))
    for hit in synonym_hits:
        print('WARN:   ' + hit)
for term in ('Current semantic-review scope', 'immediate-plan.md', 'plan verifier'):
    for path in ROOT.rglob('*.md'):
        parts = path.relative_to(ROOT).parts
        if parts[0] in ('sources', 'diagrams') or path.name in ('history.md', 'glossary.md'):
            continue
        require(term not in path.read_text(encoding='utf-8-sig'), 'Retired term %r in %s' % (term, path.relative_to(ROOT).as_posix()))

# ---- node lifecycle names (field-catalog.md#node-lifecycle): every dispatch outcome maps to a PRD name
_lc = (REF / 'field-catalog.md').read_text(encoding='utf-8-sig').split('### node-lifecycle', 1)[1].split('\n### ', 1)[0]
_lc_rows = {m.group(1): m.group(2) for m in re.finditer(r'^\| `(Pending|Running|Evaluating|Completed|Failed)` \| (.*)$', _lc, re.M)}
require(set(_lc_rows) == {'Pending', 'Running', 'Evaluating', 'Completed', 'Failed'}, 'Node lifecycle table lacks a PRD name')
for _o in interfaces['dispatch-record:field-contract:2']['fields']['outcome']['enum']:
    require(sum(('`%s`' % _o) in v for v in _lc_rows.values()) == 1, 'Dispatch outcome %s is not mapped to exactly one PRD lifecycle name' % _o)
_ns = interfaces['client-status:field-contract:1']['fields']['node_statuses']
require(_ns['type'] == 'NodeStatus[]', 'client-status lacks node_statuses')

exec(compile((REF/'routing_checks.py').read_text(encoding='utf-8'), str(REF/'routing_checks.py'), 'exec'))

if errors:
    print('\n'.join('FAIL: ' + error for error in errors))
    raise SystemExit(1)
print(f'PASS: {len(schemas)-1} critical schemas + common; {len(index)} indexed examples/context records; {negative_count} negative cases; exact references/spans and gate relationships')
print(f'PASS: {len(headings)} PRD headings, US01–US20, delivery boundaries/current external PRD identity, {link_count} local links/fragments; tier 1 {words} words including Mermaid')
print(f'PASS: {len(interfaces)} named field contracts; linked research and RSI identities/selected relationships')
print(f'PASS: {rchecked} research check runs over indexed examples; {rrejected} invalid examples rejected by their named check; end-to-end research chain consistent')
print('LIMIT: structural/document checks and selected semantic example checks, not model quality, exhaustive field-proof, transport authentication or runtime acceptance')
