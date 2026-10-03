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
print(f'{checks} story structure, numerical expectation, plan connection and metadata checks passed')
print('No record resolution, product execution, model, auth, Docker or sandbox result is claimed')
