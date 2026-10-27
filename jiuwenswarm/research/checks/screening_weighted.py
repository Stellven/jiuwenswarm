"""Independent mandatory checks for weighted screening.

These recompute every exclusion, exact total, the ranking and the Top-1 from the
bound inputs alone. They share no code with the pure ranker the carrier calls.
"""
from __future__ import annotations

from fractions import Fraction

from ..contracts import validate
from .research import CheckError

CHECK_IDS = ('screening_result_schema', 'candidate_binding', 'ids_accounted', 'values_match_inputs',
             'exclusions_recomputed', 'totals_recomputed', 'ranking_recomputable', 'dispositions_consistent')
RESULT_SCHEMA = 'urn:ai4r:screening-weighted-result:1.0.0'


def _num(text):
    return Fraction(text)


def _expected_codes(facts, constraints):
    codes = []
    if constraints['cpu_only'] and facts['requires_gpu']:
        codes.append('requires_gpu')
    if constraints['allowed_licenses'] is not None and facts['license'] not in constraints['allowed_licenses']:
        codes.append('license_not_allowed')
    if constraints['max_runtime_minutes'] is not None and _num(facts['runtime_minutes']) > _num(constraints['max_runtime_minutes']):
        codes.append('runtime_exceeds_budget')
    codes += ['forbidden_dependency'] * sum(d in constraints['forbidden_dependencies'] for d in facts['dependencies'])
    return codes


class WeightedScreeningChecks:
    def __init__(self, stage='screening', *, executor=None):
        self.stage, self.executor = stage, executor
        self.check_ids = list(CHECK_IDS)

    async def __call__(self, ctx, inputs, outputs):
        results = []
        evidence = list(ctx.output_refs.values())
        for check_id in CHECK_IDS:
            try:
                getattr(self, '_' + check_id)(ctx, inputs, outputs)
                outcome, reason = 'PASS', 'Recomputed from the bound inputs without error.'
            except CheckError as exc:
                outcome, reason = 'FAIL', str(exc)
            except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
                outcome, reason = 'FAIL', check_id + ': ' + type(exc).__name__
            results.append({'check_id': check_id, 'outcome': outcome, 'reason': reason, 'evidence_refs': evidence})
        return results

    def _screening_result_schema(self, ctx, inputs, outputs):
        validate(RESULT_SCHEMA, outputs['screening_result'])
        validate('urn:ai4r:screening-weighted-candidates:1.0.0', inputs['candidate_set'])
        validate('urn:ai4r:screening-weighted-rubric:1.0.0', inputs['screening_rubric'])

    def _candidate_binding(self, ctx, inputs, outputs):
        result = outputs['screening_result']
        if result['candidate_ref'] != ctx.input_ref('candidate_set') or result['rubric_ref'] != ctx.input_ref('screening_rubric'):
            raise CheckError('candidate_binding', 'result refs differ from the bound inputs')

    def _ids_accounted(self, ctx, inputs, outputs):
        result = outputs['screening_result']
        ids = [idea['idea_id'] for idea in inputs['candidate_set']['ideas']]
        scored = [row['idea_id'] for row in result['scores']]
        if len(set(ids)) != len(ids) or sorted(scored) != sorted(ids):
            raise CheckError('ids_accounted', 'scores must hold each input idea exactly once')
        ranked = [row['idea_id'] for row in result['ranking']]
        for row in result['scores']:
            if row['eligible'] and row['idea_id'] not in ranked:
                raise CheckError('ids_accounted', 'eligible idea is not ranked: ' + row['idea_id'])
            if not row['eligible'] and (not row['violations'] or not row['disposition_reason'].strip() or row['idea_id'] in ranked):
                raise CheckError('ids_accounted', 'excluded idea lacks a reason or is ranked: ' + row['idea_id'])

    def _values_match_inputs(self, ctx, inputs, outputs):
        rubric = inputs['screening_rubric']
        by_id = {idea['idea_id']: idea for idea in inputs['candidate_set']['ideas']}
        for row in outputs['screening_result']['scores']:
            idea = by_id[row['idea_id']]
            if row['values'] != {name: idea['assessments'][name] for name in rubric['weights']}:
                raise CheckError('values_match_inputs', 'values differ from the supplied assessments: ' + row['idea_id'])
            if row['citation_ids'] != idea['citation_ids']:
                raise CheckError('values_match_inputs', 'citations differ from the idea: ' + row['idea_id'])

    def _exclusions_recomputed(self, ctx, inputs, outputs):
        constraints = inputs['screening_rubric']['constraints']
        by_id = {idea['idea_id']: idea for idea in inputs['candidate_set']['ideas']}
        for row in outputs['screening_result']['scores']:
            expected = _expected_codes(by_id[row['idea_id']]['facts'], constraints)
            if [v['code'] for v in row['violations']] != expected or row['eligible'] is not (not expected):
                raise CheckError('exclusions_recomputed', 'exclusion differs from the hard constraints: ' + row['idea_id'])

    def _totals_recomputed(self, ctx, inputs, outputs):
        weights = {name: _num(value) for name, value in inputs['screening_rubric']['weights'].items()}
        for row in outputs['screening_result']['scores']:
            total = Fraction(0)
            for name, weight in weights.items():
                total += weight * _num(row['values'][name])
            if _num(row['weighted_total']) != total:
                raise CheckError('totals_recomputed', 'exact total differs: ' + row['idea_id'])

    def _ranking_recomputable(self, ctx, inputs, outputs):
        result = outputs['screening_result']
        order = sorted((row for row in result['scores'] if row['eligible']), key=lambda r: (-_num(r['weighted_total']), r['idea_id']))
        expected = [{'rank': i + 1, 'idea_id': r['idea_id'], 'weighted_total': r['weighted_total']} for i, r in enumerate(order)]
        if result['ranking'] != expected or not expected or result['selected_idea_id'] != expected[0]['idea_id']:
            raise CheckError('ranking_recomputable', 'ranking or Top-1 differs from the exact recomputation')

    def _dispositions_consistent(self, ctx, inputs, outputs):
        result = outputs['screening_result']
        selected = result['selected_idea_id']
        for row in result['scores']:
            want = 'rejected' if not row['eligible'] else 'selected' if row['idea_id'] == selected else 'eligible'
            if row['disposition'] != want:
                raise CheckError('dispositions_consistent', 'disposition differs: ' + row['idea_id'])
