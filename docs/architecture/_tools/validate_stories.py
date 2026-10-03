"""Check documented story fixtures; do not execute proposed application code."""
import copy
import json
import re
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

root = Path(__file__).resolve().parents[1]
pack = json.loads((root / 'stories/fixtures/science.json').read_text(encoding='utf-8'))
resources = {}
for path in (root / 'exports/schemas').rglob('*.json'):
    schema = json.loads(path.read_text(encoding='utf-8'))
    resources[schema['$id']] = schema
registry = Registry().with_resources((key, Resource.from_contents(value)) for key, value in resources.items())
checks = 0

def check(condition, label):
    global checks
    assert condition, label
    checks += 1

for case in pack['cases']:
    for name in ['hypothesis_blueprint', 'benchmark_payload', 'evaluation_verdict']:
        schema = json.loads((root / 'exports/schemas/types' / (name.replace('_', '-') + '.schema.json')).read_text())
        v = Draft202012Validator(schema, registry=registry)
        check(v.is_valid(case[name]), (case['name'], name, list(v.iter_errors(case[name]))))
        bad = copy.deepcopy(case[name])
        bad['invented_core_field'] = True
        check(not v.is_valid(bad), (name, 'unknown field'))
        bad = copy.deepcopy(case[name])
        del bad[schema['required'][0]]
        check(not v.is_valid(bad), (name, 'missing required field'))
    bp, raw, verdict = (case[n] for n in ['hypothesis_blueprint', 'benchmark_payload', 'evaluation_verdict'])
    metric = bp['metrics'][0]
    check([r['arm'] for r in raw['runs']] == ['baseline', 'treatment'], 'paired order')
    check(all(r['seed'] == bp['seed'] and r['repeat_index'] == 0 for r in raw['runs']), 'seed/repeat')
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_EVEN
        baseline, treatment = [Decimal(str(r['values']['M1'])) for r in raw['runs']]
        delta = treatment - baseline
        value = 100 * (baseline - treatment) / abs(baseline)
    check(delta == Decimal(str(raw['deltas']['M1'])), 'raw delta')
    c = verdict['comparisons'][0]
    check(value == Decimal(str(c['measured'])), 'relative percent')
    claim = value >= Decimal(str(metric['expected']))
    accepted = value >= Decimal(str(metric['acceptance_target']))
    falsified = value < Decimal(str(metric['falsified_at']))
    check((c['claim_met'], c['acceptance_met'], c['falsified']) == (claim, accepted, falsified), 'three predicates')
    # Deliberately limited to these single-goal complete/plausible fixtures.
    expected = 'FAIL' if falsified else 'PASS' if claim and accepted else bp['middle_zone_classification']
    check(verdict['classification'] == expected, 'preregistered example outcome')

rank = pack['screening']
ordered = sorted(rank['candidates'], key=lambda c: (-sum(c['scores']), tuple(sorted(c['idea_ids']))))
check([c['idea_ids'] for c in ordered] == rank['expected_order'], 'Screening order')
check(next(c['idea_ids'] for c in ordered if c['dependency_status'] == 'compatible') == rank['expected_selected'], 'first eligible')
check(all(1 <= score <= 5 for c in ordered for score in c['scores']), 'score domain')
all_ineligible = [dict(c, dependency_status='conflict') for c in ordered]
check(not any(c['dependency_status'] == 'compatible' for c in all_ineligible), 'no winner')
check(rank['all_ineligible_expected'] == 'NO_ELIGIBLE_OPPORTUNITY', 'no-winner story expectation')

pipeline = (root / 'm1/pipeline.md').read_text(encoding='utf-8')
plan = json.loads(re.search(r'```json\n(.*?)```', pipeline, re.S).group(1))
story = (root / 'stories/01-research-workflow.md').read_text(encoding='utf-8')
for step in plan['steps']:
    check(step['capsule_name'] in story, ('missing work capability', step['step_id']))
    check(step['gate_capsule_name'] == 'research.verifier', 'shared Gate identity')
    check(all(port in story for port in step['inputs']), ('missing input label', step['step_id']))
modules = (root / 'system/modules.md').read_text(encoding='utf-8')
for location in ['cc/runner/pipeline.py', 'cc/adapters/swarmflow.py', 'cc/freeze.py', 'cc/security/measurement_service.py']:
    check(location in modules, ('proposed destination', location))
for path in (root / 'm1').glob('*.md'):
    check(path.read_text(encoding='utf-8').startswith('---\n'), ('M1 front matter', path.name))
screening = (root / 'm1/screening.md').read_text(encoding='utf-8')
decl = json.loads(re.search(r'```json\n(.*?)```', screening, re.S).group(1))
check(decl['identity']['kind'] == 'tool', 'Screening has executable postprocessing handler')
check('Nested call input' not in screening, 'ordinary helper is not a nested capsule API')
entry = decl['ext']['cc']['entry']
check(entry == 'screening.py:run', 'Screening entry')
body = {f['path'] for f in decl['identity']['body']}
check(entry.split(':')[0] in body, 'entry code pinned in body')
check('references/dependency-registry.json' in body, 'registry snapshot pinned')
check('files:screening.py' not in decl['evolution']['may_change'], 'wrapper protected from RSI')
check('files:references/dependency-registry.json' not in decl['evolution']['may_change'], 'registry protected from RSI')
check(any(m['reason_code'] == 'NO_ELIGIBLE_OPPORTUNITY' for m in decl['guarantees']['failure_modes']), 'typed no-winner frame')
runner = (root / 'capsule/runner.md').read_text(encoding='utf-8')
check('cc.ModelUnavailable' in runner and 'broker_request_id' in runner, 'model failure has attributed frame path')
model_frame = next(line for line in runner.splitlines() if '| `model_result` |' in line)
check('broker_request_id' in model_frame, 'model error attribution identity crosses return frame')
check('CREATE_NEW_PROCESS_GROUP' not in runner and 'os.killpg' not in runner, 'no stale group-based launch authority')
gate = (root / 'capsule/gate-host.md').read_text(encoding='utf-8')
check('R1 & R2 & R3 & D1 & D2 & D3 & F2 --> W' in gate, 'all Gate terminal branches persist')
check('NOT_APPLICABLE' not in gate, 'mechanical Gate uses valid tier enum')
profiles = (root / 'schemas/profiles.md').read_text(encoding='utf-8')
check('max_execution_retries=0' in profiles and 'NOT_APPLICABLE' not in profiles, 'profile semantics match schema')
for path in (root / 'm1').glob('*.md'):
    for block in re.findall(r'```json\n(.*?)```', path.read_text(encoding='utf-8'), re.S):
        try:
            declaration = json.loads(block)
        except json.JSONDecodeError:
            continue
        identity = declaration.get('identity', {})
        if identity.get('kind') == 'tool' and 'body' in identity:
            ref = declaration.get('ext', {}).get('cc', {}).get('entry', '')
            check(':' in ref and ref.split(':')[0] in {f['path'] for f in identity['body']}, (path.name, 'tool folder entry'))
print(f'{checks} story structure, numerical expectation, plan connection and metadata checks passed')
print('No record resolution, product execution, model, auth, Docker or sandbox result is claimed')
