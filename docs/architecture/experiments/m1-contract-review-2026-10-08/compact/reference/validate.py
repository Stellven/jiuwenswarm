"""Offline design checks, not application acceptance.

Run: python reference/validate.py [copied-package-root]
Requires jsonschema >=4 and referencing. Does not modify the package.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
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


def require(ok, message):
    if not ok:
        errors.append(message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


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
    'capsule-declaration': ROOT / 'capsule/declaration.md',
    'node-execution-contract': REF / 'node-execution.md',
}
for item in catalog['contracts']:
    summary = field_documents[item['name']].read_text(encoding='utf-8')
    require(item['version'] == load(REF / item['schema'])['properties']['schema_version']['const'], 'Catalog version drift')
    for key in item['required_fields']:
        require('`' + key + '`' in summary, 'Missing required field summary: ' + item['name'] + '.' + key)

index = load(EX / 'index.json')['examples']
require(len({item['path'] for item in index}) == len(index), 'Duplicate example index path')
for item in index:
    path = (EX / item['path']).resolve()
    require(path.is_relative_to(EX.resolve()) and path.exists(), 'Example path escape/missing: ' + item['path'])
    value = load(path)
    if item['schema_id']:
        require(item['schema_id'] in validators, 'Unknown example schema ' + item['schema_id'])
        for error in validators[item['schema_id']].iter_errors(value):
            errors.append(f'{item["path"]}:{list(error.path)}: {error.message}')
    for node in walk(value):
        if set(node) == {'id', 'sha256'}:
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
    subject = checks['subject_ref']
    if subject not in gate['output_refs']:
        result.append('wrong deterministic subject')
    plan = resolved(gate['check_plan_ref'])
    if {x['check_id'] for x in checks['results']} != set(plan['mandatory_deterministic']) or len(checks['results']) != len(plan['mandatory_deterministic']):
        result.append('missing or duplicate deterministic obligations')
    contract = resolved(gate['contract_ref'])
    if plan['contract_ref'] != gate['contract_ref'] or plan['input_refs'] != contract['input_refs'] or gate['input_refs'] != contract['input_refs']:
        result.append('wrong concrete contract or bound input inventory')
    for key in ('run_id', 'node_id', 'attempt_id'):
        if contract[key] != gate[key]:
            result.append('wrong contract scope')
    if gate['check_plan_ref'] != checks['check_plan_ref']:
        result.append('wrong check plan')
    for invocation in gate['invocation_refs']:
        if resolved(invocation)['contract_ref'] != gate['contract_ref']:
            result.append('wrong invocation contract')
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
        observations=[resolved(r) for r in gate['invocation_refs']]
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
    known=set(schemas)|{x['id'] for x in catalog['interfaces']}
    for ports in (value['inputs'],value['outputs']):
        if len({p['name'] for p in ports})!=len(ports):result.append('duplicate port')
        if any(p['contract_id'] not in known for p in ports):result.append('unknown contract')
    for b in bindings:
        if any(b['limits'][k]>value['node_limits'][k] for k in b['limits']):result.append('binding exceeds node limit')
        authority=b['effective_authority']
        if authority['network']=='none' and authority['network_allowlist']:result.append('denied network allowlist')
        decl=resolved(b['declaration_ref'])
        for direction,key in [('inputs','inputs'),('outputs','outputs')]:
            advertised={(p['name'],p['schema_ref']) for p in decl['ports'][direction] if p['required']}
            allowed={(p['name'],p['schema_ref']) for p in decl['ports'][direction]}
            actual={(p['name'],p['contract_id']) for p in value[key]}
            if not advertised <= actual or not actual <= allowed:result.append('missing/unknown declared typed port')
    return result

def plan_issues(nodes, allowed_requirements=None):
    result=[];by_id={n['node_id']:n for n in nodes}
    if len(by_id)!=len(nodes):result.append('duplicate planning node')
    pending=set(by_id);done=set()
    while pending:
        ready={n for n in pending if set(by_id[n]['predecessors'])<=done}
        if not ready:result.append('cyclic/unknown plan predecessor');break
        done|=ready;pending-=ready
    known=set(schemas)|{x['id'] for x in catalog['interfaces']}
    for n in nodes:
        if allowed_requirements is not None and (not n['requirement_ids'] or not set(n['requirement_ids'])<=allowed_requirements):result.append('unknown planning obligation')
        if len(n['capsule_refs'])!=1:result.append('M1 plan needs one work declaration')
        for ports in (n['inputs'],n['outputs']):
            if len({p['name'] for p in ports})!=len(ports):result.append('duplicate planning port')
            if any(p['contract_id'] not in known or p['version']!='1.0.0' for p in ports):result.append('unknown planning contract')
        for p in n['inputs']:
            if bool(p['artifact_refs'])==bool(p['future_bindings']):result.append('ambiguous/missing planning source')
            for src in p['future_bindings']:
                owner=by_id.get(src['producer_node']);out=next((o for o in owner['outputs'] if o['name']==src['port']),None) if owner else None
                if src['producer_node'] not in n['predecessors'] or not out or (out['contract_id'],out['version'])!=(src['contract_id'],src['version']) or (src['contract_id'],src['version'])!=(p['contract_id'],p['version']):result.append('incompatible future planning port')
    return result

for name in ('Gate_Decision.json', 'Gate_Topic_Halt.json', 'Gate_Science_Pass.json', 'Gate_Requirements_Pass.json'):
    for issue in gate_issues(load(EX / name)):
        errors.append(name + ': ' + issue)
require(load(EX / 'Topic_Assessment.json')['verdict'] == 'INCONCLUSIVE', 'Topic-only intent must not pass usability')
require(load(EX / 'Gate_Topic_Halt.json')['accepted_refs'] == [], 'Blocked intent must not reach Requirements')
require(load(EX / 'Evaluation_Verdict.json')['classification'] == 'FAIL' and load(EX / 'Gate_Science_Pass.json')['verdict'] == 'PASS', 'Science/gate distinction lost')

brief = load(EX / 'Research_Brief.json')
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
    value = copy.deepcopy(load(EX / 'Intent_IR.json'))
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
value = copy.deepcopy(load(EX / 'Intent_Assessment.json'))
value['action'] = 'halt'
require(not validators[assess_key].is_valid(value), 'Verifier may not author control action')
negative_count += 1
value = copy.deepcopy(load(EX / 'Gate_Decision.json'))
value['verdict'] = 'FAIL'
require(not validators[gate_key].is_valid(value), 'FAIL must not authorize advance')
negative_count += 1
for mode in ('subject', 'scope', 'acceptance', 'missing_assessment'):
    value = copy.deepcopy(load(EX / 'Gate_Decision.json'))
    if mode == 'subject':
        value['output_refs'] = [load(EX / 'Gate_Topic_Halt.json')['output_refs'][0]]
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
require(len(interfaces) == len(field_catalog['interfaces']), 'Duplicate field-contract ID')
require(set(interfaces) == {x['id'] for x in catalog['interfaces']}, 'Catalog/field interface mismatch')
known_contracts = set(schemas) | set(interfaces)

def field_errors(value, fields, prefix=''):
    result = []
    if not isinstance(value, dict):
        return [prefix + ': expected object']
    if 'schema_version' in fields and value.get('schema_version') != '1.0.0':
        result.append(prefix + ': incompatible version')
    for key in set(value) - set(fields) - {'ext'}:
        result.append(prefix + ': unknown core field ' + key)
    for key, info in fields.items():
        if key not in value:
            if info['required']:
                result.append(prefix + ': missing ' + key)
            continue
        result += type_errors(value[key], info['type'], prefix + '.' + key)
    if 'ext' in value:
        ext = value['ext']
        if not isinstance(ext, dict) or any(not re.fullmatch(r'[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+', k) for k in ext):
            result.append(prefix + ': invalid namespaced extension')
    return result

def type_errors(value, kind, prefix):
    if kind.startswith('nullable-'):
        return [] if value is None else type_errors(value, kind[9:], prefix)
    if kind.endswith('[]'):
        return sum((type_errors(x, kind[:-2], prefix + '[]') for x in value), []) if isinstance(value, list) else [prefix + ': expected array']
    if kind in types:
        return field_errors(value, types[kind]['fields'], prefix)
    valid = {'string': isinstance(value, str) and bool(value),
             'sha256': isinstance(value, str) and bool(re.fullmatch(r'[0-9a-f]{64}', value)),
             'integer': isinstance(value, int) and not isinstance(value, bool),
             'number': isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
             'boolean': isinstance(value, bool)}
    return [] if valid.get(kind, False) else [prefix + ': invalid ' + kind]

for item in index:
    if item.get('field_contract_id'):
        require(item['field_contract_id'] in interfaces, 'Unknown example field contract')
        contract = interfaces[item['field_contract_id']]
        errors.extend(field_errors(load(EX / item['path']), contract['fields'], item['path']))
for item in field_catalog['interfaces']:
    for info in item['fields'].values():
        require(info['type'].removeprefix('nullable-').removesuffix('[]') in set(types) | {'string','integer','number','boolean','sha256'}, 'Unknown field type')
    require(bool(item['failure']) and bool(item['producer']) and bool(item['consumers']), 'Incomplete field ownership/behavior')
for item in index:
    value = load(EX / item['path'])
    if item['schema_id'] and ':capsule-declaration:' in item['schema_id']:
        for port in value['ports']['inputs'] + value['ports']['outputs']:
            require(port['schema_ref'] in known_contracts, 'Unresolved CC port contract ' + port['schema_ref'])
    if item['schema_id'] and ':node-execution-contract:' in item['schema_id']:
        require(not node_issues(value), 'Invalid concrete binding: ' + item['path'] + ': ' + str(node_issues(value)))

def research_issues():
    result=[]
    candidates=load(EX/'Candidate_Set.json'); scores=load(EX/'Screening_Result.json'); opportunity=load(EX/'Opportunity_Card.json')
    ids={x['idea_id'] for x in candidates['ideas']}; citations={x['id'] for x in candidates['citations']}
    if not 1 <= len(ids) <= 3 or len(ids)!=len(candidates['ideas']):result.append('candidate cardinality/identity')
    for idea in candidates['ideas']:
        if not idea['citation_ids'] or not set(idea['citation_ids']) <= citations:result.append('ungrounded idea')
    if {x['idea_id'] for x in scores['scores']}!=ids or len(scores['scores'])!=len(ids):result.append('missing/duplicate scores')
    expected=[]
    for score in scores['scores']:
        values=[score[x] for x in ('novelty','feasibility','compute_alignment')]
        if not all(1 <= x <= 5 for x in values):result.append('score bounds')
        if score['eligible']:expected.append({'idea_id':score['idea_id'],'total':sum(values)})
    expected.sort(key=lambda x:(-x['total'],x['idea_id']))
    if scores['ranking']!=expected or not expected or opportunity['idea_id']!=expected[0]['idea_id'] or scores['selected_idea_id']!=opportunity['idea_id']:result.append('inconsistent Top-1')
    blueprint=load(EX/'Hypothesis_Blueprint.json');poc=load(EX/'POC_Manifest.json');benchmark=load(EX/'Benchmark_Payload.json');verdict=load(EX/'Evaluation_Verdict.json');delivery=load(EX/'Delivery_Manifest.json')
    if blueprint['environment_ref']!=poc['environment_ref'] or benchmark['blueprint_ref']!=poc['blueprint_ref']:result.append('different protocol/environment')
    metric_ids={x['metric_id'] for x in blueprint['metrics']}
    if {x['metric_id'] for x in benchmark['metrics']}!=metric_ids or {x['metric_id'] for x in verdict['findings']}!=metric_ids:result.append('incomplete metric coverage')
    for metric in benchmark['metrics']:
        if len(metric['baseline'])!=blueprint['repeat_count'] or len(metric['treatment'])!=blueprint['repeat_count'] or abs(metric['delta']-(metric['treatment_value']-metric['baseline_value']))>1e-9:result.append('measurement relationship')
    if verdict['classification']!='FAIL' or delivery['verdict_ref']!=ref_for('Evaluation_Verdict.json'):result.append('negative delivery changed')
    return result

def ref_for(name):
    return {'id':name,'sha256':hashlib.sha256((EX/name).read_bytes()).hexdigest()}

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

with zipfile.ZipFile(EX/'POC_Artifact_Bundle.zip') as archive:
    poc=load(EX/'POC_Manifest.json')
    require(set(archive.namelist())=={x['path'] for x in poc['files']}, 'POC archive/manifest mismatch')
    for item in poc['files']:
        require(hashlib.sha256(archive.read(item['path'])).hexdigest()==item['artifact_ref']['sha256'], 'POC packaged bytes differ')
for rule in [rule for metric in load(EX/'Hypothesis_Blueprint.json')['metrics'] for rule in (metric['success'],metric['falsification'])]:
    require(rule['operand']=='treatment' and rule['comparator'] in ('lt','le','eq','ge','gt') and rule['reference'] in ('baseline','constant'), 'Unsupported comparison rule')
    require(rule['reference']!='constant' or rule['factor']==0, 'Constant rule has baseline factor')
for item in field_catalog['interfaces']:
    view=(REF/'field-catalog.md').read_text(encoding='utf-8')
    for name,info in item['fields'].items():
        require('| `'+name+'` | `'+info['type']+'` |' in view, 'Field view/type drift '+item['name']+'.'+name)
errors.extend(research_issues())
errors.extend(rsi_issues(load(EX/'RSI_Referee_Evidence.json')))
candidate=load(EX/'RSI_Child_Candidate.json')
require(candidate['implementation_refs']==[load(EX/'RSI_Attempt_01.json')['child_ref']], 'Candidate body/attempt mismatch')
require(load(EX/'RSI_Admission.json')['candidate_ref']==ref_for('RSI_Child_Candidate.json'), 'Admission references wrong package')
parent=load(EX/'Ranking_Declaration.json'); child=load(EX/'Ranking_Child_Declaration.json')
for key in parent:
    if key!='identity':require(parent[key]==child[key], 'RSI changes frozen declaration semantics')
for key in parent['identity']:
    if key not in ('version_label','carrier','body'):require(parent['identity'][key]==child['identity'][key], 'RSI changes frozen identity semantics')
require(child['identity']['body'][0]['sha256']==candidate['implementation_refs'][0]['sha256'], 'Derived body pin mismatch')
require(load(EX/'RSI_Rollback.json')['admission_ref']==ref_for('RSI_Parent_Admission.json'), 'Rollback lacks prior-version admission')

for mode in ('missing_binding','unknown_contract','input_inventory','oversized_limit','port_name'):
    bad=copy.deepcopy(load(EX/'Node_Contract.json'))
    if mode=='missing_binding':bad['bindings']=[]
    elif mode=='unknown_contract':bad['outputs'][0]['contract_id']='invented:contract'
    elif mode=='input_inventory':bad['input_refs']=[]
    elif mode=='oversized_limit':bad['bindings'][0]['limits']['model_calls']=999
    else:bad['inputs'][0]['name']='invented-port'
    require(bool(node_issues(bad)) or not validators['urn:jiuwenswarm:m1-design:node-execution-contract:1.0.0'].is_valid(bad), 'Node negative accepted: '+mode)
    negative_count += 1
for mode in ('missing','type','extension'):
    bad=copy.deepcopy(load(EX/'Opportunity_Card.json'))
    if mode=='missing':del bad['opportunity_statement']
    elif mode=='type':bad['citation_ids']='untyped string'
    else:bad['ext']={'unqualified':True}
    require(bool(field_errors(bad,interfaces['opportunity-card:field-contract:1']['fields'])), 'Field negative accepted: '+mode)
    negative_count += 1
for mode in ('lineage','mandatory','final_reuse'):
    bad=copy.deepcopy(load(EX/'RSI_Referee_Evidence.json'))
    if mode=='lineage':bad['child_ref']=bad['parent_ref']
    elif mode=='mandatory':bad['mandatory_parent_tests_passed']=False
    else:bad['final_evaluations']=2
    require(bool(rsi_issues(bad)), 'RSI negative accepted: '+mode)
    negative_count += 1

# Independent-review regressions: member wiring, optional ports and exact source decoding.
planning=load(EX/'Planning_Nodes.json');nodes=planning['nodes'];governing=resolved(planning['brief_ref']);allowed={r['id'] for r in governing['mandatory_requirements']+governing['optional_preferences']}
errors.extend(type_errors(nodes,'PlanNode[]','Planning_Nodes'))
errors.extend(plan_issues(nodes,allowed))
bad=copy.deepcopy(nodes);bad[0]['requirement_ids']=['invented:obligation']
require('unknown planning obligation' in plan_issues(bad,allowed), 'Foreign planning obligation accepted');negative_count+=1
for mode in ('unknown_port','mixed_source','cycle'):
    bad=copy.deepcopy(nodes)
    if mode=='unknown_port':bad[1]['inputs'][1]['future_bindings'][0]['port']='missing'
    elif mode=='mixed_source':bad[1]['inputs'][1]['artifact_refs']=bad[0]['inputs'][0]['artifact_refs']
    else:bad[0]['predecessors']=['screening']
    require(bool(plan_issues(bad)), 'Planning negative accepted: '+mode);negative_count+=1
# Unmapped optional declaration ports are tested against an in-memory resolver.
old_resolved=resolved
def resolved(r):
    d=old_resolved(r)
    if r['id']=='Capsule_Declaration.json':
        d['ports']['inputs'].append(dict(d['ports']['inputs'][0],name='optional-context',required=False))
        d['ports']['outputs'].append(dict(d['ports']['outputs'][0],name='optional-intent',required=False))
    return d
require(not node_issues(load(EX/'Node_Contract.json')), 'Optional declaration port incorrectly mandatory')
optional=copy.deepcopy(load(EX/'Node_Contract.json'));optional['outputs'].append(dict(optional['outputs'][0],name='optional-intent',required=False))
require(not node_issues(optional) and validators['urn:jiuwenswarm:m1-design:node-execution-contract:1.0.0'].is_valid(optional), 'Optional output incorrectly required')
resolved=old_resolved
bad=copy.deepcopy(load(EX/'Gate_Decision.json'));bad['invocation_refs']=[]
require('incomplete/duplicate work binding observations' in gate_issues(bad), 'Missing binding observation accepted');negative_count+=1
span_fixture=load(EX/'Source_Spans_CRLF.json')
for span,expected_text in zip(span_fixture['source_spans'],span_fixture['expected_text']):
    decoded=(EX/span['source_ref']['id']).read_bytes().decode('utf-8')
    require(decoded[span['start']:span['end']]==expected_text, 'CRLF/non-BMP span regression')
attempt=load(EX/'RSI_Attempt_01.json');genesis=resolved(attempt['chain_root_ref'])
require(genesis['session_id']==attempt['session_id'] and genesis['target_ref']==attempt['target_ref'] and genesis['hash_profile_ref']==attempt['hash_profile_ref'], 'RSI genesis/profile mismatch')
require(attempt['sequence']==1 and attempt['previous_ref'] is None, 'First RSI chain link must start at separate genesis')
for key in ('hash_profile_ref','chain_root_ref'):
    bad=copy.deepcopy(attempt);bad.pop(key)
    require(bool(field_errors(bad,interfaces['rsi-attempt:field-contract:1']['fields'])), 'Missing RSI custody accepted');negative_count+=1
clearance=load(EX/'RSI_Security_Clearance.json')
require(clearance['decision']=='denied' and clearance['effect_scope']=='new_rsi_session_only', 'Synthetic security clearance must not grant eligibility')
bad=copy.deepcopy(clearance);bad.pop('guardrail_evidence_refs')
require(bool(field_errors(bad,interfaces['security-clearance:field-contract:1']['fields'])), 'Missing clearance evidence accepted');negative_count+=1

bad=copy.deepcopy(load(EX/'Node_Contract.json'));bad['bindings'].append(copy.deepcopy(bad['bindings'][0]))
require(bool(node_issues(bad)) and not validators['urn:jiuwenswarm:m1-design:node-execution-contract:1.0.0'].is_valid(bad), 'Unsupported M1 member composition accepted');negative_count+=1

# Source byte preservation is portable: receipt manifest uses package paths.
for source in load(REF / 'provenance.json')['sources']:
    path = (ROOT / source['path']).resolve()
    require(path.is_relative_to(ROOT) and path.is_file(), 'Missing/escaping source path ' + source['path'])
    require(len(path.read_bytes()) == source['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256'], 'Source bytes changed ' + source['path'])


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
# Historical received CC semantic text is immutable bibliography, not required
# navigation. Current product source remains scanned for local Markdown links.
documents = list(ROOT.rglob('*.md')) + list((ROOT / 'sources/product').glob('*.txt'))
for path in documents:
    if 'sources' in path.relative_to(ROOT).parts and 'product' not in path.relative_to(ROOT).parts:
        continue
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

prd = (ROOT / 'sources/product/prd-m1-current-2026-10-07.txt').read_text(encoding='utf-8-sig')
headings = re.findall(r'^#{2,5}\s+(\d+\.\d+(?:\.\d+)?)\s+(.+)$', prd, flags=re.M)
coverage = (ROOT / 'coverage-allocation.md').read_text(encoding='utf-8')
for number, title in headings:
    require(f'| §{number} {title} |' in coverage, 'Missing current source heading ' + number)
audit = (ROOT / 'coverage.md').read_text(encoding='utf-8')
for number in range(1, 21):
    require(f'| US{number:02d} |' in audit, 'Missing user-story mapping')

top = ['README.md', 'principles.md', 'm1-design.md']
words = sum(len((ROOT / name).read_text(encoding='utf-8').split()) for name in top)
require(words <= 3400, 'Three-document orientation exceeds conservative editing target: ' + str(words))
require(not (ROOT / 'handoff.md').exists(), 'Obsolete coding handoff still present')
for path in ROOT.rglob('*.md'):
    if 'sources' not in path.relative_to(ROOT).parts:
        require('handoff.md' not in path.read_text(encoding='utf-8'), 'Stale handoff link: ' + str(path))

for entry in catalog['field_contracts']:
    document, fragment = entry['document'].split('#')
    require(fragment in anchors(REF / document), 'Missing catalog field-contract section')
    require(entry['version'] == catalog['version'] and bool(entry['applicable_phases']), 'Field-contract version/phase mismatch')

manifest = load(ROOT / 'diagrams/manifest.json')['diagrams']
blocks = {}
for path in ROOT.rglob('*.md'):
    if {'sources', 'diagrams'} & set(path.relative_to(ROOT).parts):
        continue
    for number, block in enumerate(re.findall(r'```mermaid\s*\n(.*?)```', path.read_text(encoding='utf-8'), re.S), 1):
        blocks[(path.relative_to(ROOT).as_posix(), number)] = hashlib.sha256(block.encode()).hexdigest()
counts = {}
for item in manifest:
    number = counts.get(item['source'], 0) + 1
    counts[item['source']] = number
    require(blocks.pop((item['source'], number), None) == item['mermaid_sha256'], 'Stale diagram source ' + item['source'])
    for extension in ('svg', 'png'):
        path = (ROOT / item[extension]).resolve()
        require(path.is_relative_to(ROOT) and path.exists(), 'Missing diagram projection')
        if path.exists():
            require(hashlib.sha256(path.read_bytes()).hexdigest() == item[extension + '_sha256'], 'Stale diagram view')
require(not blocks, 'Unrendered maintained Mermaid blocks')

if errors:
    print('\n'.join('FAIL: ' + error for error in errors))
    raise SystemExit(1)
print(f'PASS: 7 critical schemas + common; {len(index)} indexed examples/context records; {negative_count} negative cases; exact references/spans and gate relationships')
print(f'PASS: {len(headings)} PRD headings, US01–US20, source hashes, {link_count} local links/fragments; three-document route {words} words')
print(f'PASS: {len(interfaces)} named field contracts; linked research and RSI identities/selected relationships')
print(f'PASS: {len(manifest)} diagram source/projection hash sets and required field-summary inventories')
print('LIMIT: structural/document checks and selected semantic example checks, not model quality, exhaustive field-proof, transport authentication or runtime acceptance')
