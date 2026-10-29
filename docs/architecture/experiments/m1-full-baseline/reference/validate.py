"""Offline design checks, not application acceptance.

Run: python reference/validate.py [copied-package-root]
Requires jsonschema >=4 and referencing. Does not modify the package.
"""
from pathlib import Path
import copy
import hashlib
import json
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
require(len(schemas) == len(schema_files) == 7, 'Expected six critical schemas and common definitions')
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
            text = target.read_text(encoding='utf-8')
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
        if any(x['outcome'] != 'PASS' for x in checks['results']):
            result.append('nonpassing deterministic checks')
        if not gate['accepted_refs'] or any(x not in gate['output_refs'] for x in gate['accepted_refs']):
            result.append('unreviewed accepted output')
    elif gate['accepted_refs']:
        result.append('halt published acceptance')
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

top = ['README.md', 'principles.md', 'm1-design.md', 'delivery-phases.md', 'immediate-plan.md']
words = sum(len((ROOT / name).read_text(encoding='utf-8').split()) for name in top)
require(words <= 4400, 'Immediate route exceeds approximate 4,000-word editing target: ' + str(words))
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
print(f'PASS: 6 critical schemas + common; {len(index)} indexed examples/context records; {negative_count} negative cases; exact references/spans and gate relationships')
print(f'PASS: {len(headings)} PRD headings, US01–US20, source hashes, {link_count} local links/fragments; five-document route {words} words')
print(f'PASS: {len(manifest)} diagram source/projection hash sets and required field-summary inventories')
print('LIMIT: structural/document checks and selected semantic example checks, not model quality, exhaustive field-proof, transport authentication or runtime acceptance')
