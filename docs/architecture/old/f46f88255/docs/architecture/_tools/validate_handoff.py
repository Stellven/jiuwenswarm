"""Architecture fixtures and source bytes only; no product runtime is invoked."""
import hashlib
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator
from canary import seam

root = Path(__file__).resolve().parents[3]
vault = root / 'docs/architecture'
manifest = json.loads((root / 'docs/product/source-freeze-2026-10-02.json').read_text())
for item in manifest['files']:
    assert hashlib.sha256((root / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
print(f"{len(manifest['files'])} frozen source hashes match")

fixture_root = vault / 'reviews/fixtures/2026-10-02'
order = [('compile_brief', 'requirement'), ('search_ideas', 'search'),
         ('select_opportunity', 'screening'), ('form_hypothesis', 'hypothesis'),
         ('build_poc', 'poc'), ('run_benchmark', 'benchmark'),
         ('evaluate_results', 'evaluation'), ('write_report', 'report')]
available = {}
joins = 0
for producer_name, consumer_name in order:
    # Producer and consumer packets were derived independently by two reviewers.
    producer = json.loads((fixture_root / 'producers' / (producer_name + '.json')).read_text())
    consumer = json.loads((fixture_root / 'consumers' / (consumer_name + '.json')).read_text())
    for port in consumer['ports']['inputs']:
        if port['name'] in available:
            prior = available[port['name']]
            external = [p['name'] for p in consumer['ports']['inputs'] if p['name'] != port['name']]
            errors = seam(prior, consumer, [port['name'] + '=' + port['name']], external)
            assert not errors, (producer_name, errors)
            joins += 1
    assert {p['name']: (p['type'], p.get('required', True)) for p in producer['ports']['inputs']} == {
        p['name']: (p['type'], p.get('required', True)) for p in consumer['ports']['inputs']}, producer_name
    for port in producer['ports']['outputs']:
        available[port['name']] = producer
print(f'8 independent module input contracts agree; {joins} producer/consumer joins agree')

rsi = json.loads((fixture_root / 'rsi-producer.json').read_text())
admission = json.loads((fixture_root / 'admission-consumer.json').read_text())
assert not seam(rsi, admission, ['candidate_ref=candidate_ref'],
                ['policy_ref', 'admission_profile_ref', 'request_id'])
print('RSI accepted Candidate/admission seam agrees; private TrialRefs are not admission inputs')

checks = 0
for schema_path in sorted((vault / 'exports/schemas').rglob('*.json')):
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)
    if schema_path.parent.name != 'types':
        continue
    owner = vault / 'types' / (schema_path.name.replace('.schema.json', '.md'))
    match = re.search(r'```json\s*\n(.*?)```', owner.read_text(encoding='utf-8'), re.S)
    if not match:
        continue
    value = json.loads(match.group(1))
    validator = Draft202012Validator(schema)
    validator.validate(value)
    checks += 1
    for field in schema.get('required', []):
        bad = dict(value)
        del bad[field]
        assert not validator.is_valid(bad), (owner.name, field)
        checks += 1
    bad = dict(value, unknown_core_field=True)
    assert not validator.is_valid(bad), owner.name
    checks += 1
print(f'{checks} generated payload positive/missing/unknown-field checks pass; all generated schemas compile')
print('Reference resolution, process isolation and runtime acceptance remain downstream checks.')
