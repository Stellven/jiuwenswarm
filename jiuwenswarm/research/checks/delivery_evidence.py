"""Independent mandatory checks for evidence-bundle delivery.

They recompute the host-owned tables and derived values from the bound bundle and
trace every number the report states back to the evidence. They share no code with
the carrier that renders the report.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..contracts import validate
from .research import CheckError

CHECK_IDS = ('research_report_schema', 'required_sections', 'evidence_tables_match',
             'derived_values_recomputed', 'numbers_trace_to_evidence')
BUNDLE_SCHEMA = 'urn:ai4r:delivery-evidence-bundle:1.0.0'
REPORT_SCHEMA = 'urn:ai4r:delivery-evidence-report:1.0.0'
HEADINGS = ('Objective', 'Method and scope', 'Results', 'Run log', 'Derived comparisons',
            'What the results show', 'Requests the evidence cannot support', 'Limitations')
NUMBER = re.compile(r'[+\-\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][+\-\u2212]?\d+)?')
DENIAL = re.compile(r"\b(?:not|no|cannot|can't|without|neither|nor|never|unsupported|insufficient|n't)\b", re.I)


def _cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def _row(values):
    return '| ' + ' | '.join(_cell(v) for v in values) + ' |'


def _q(value):
    return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def expected_derived(bundle):
    """Rows for the Derived comparisons table, computed again from the bundle only."""
    rows, log = [], bundle['run_log']
    for config in [None] + sorted({r['configuration'] for r in log}):
        durations = [r['duration_s'] for r in log if config is None or r['configuration'] == config]
        if not durations:
            continue
        total = sum((Decimal(d) for d in durations), Decimal(0))
        who = 'all runs' if config is None else config
        text = ' plus '.join(durations)
        rows.append([who + ' duration', 'sum of durations', text, _q(total), 's'])
        rows.append([who + ' duration', 'mean of durations', text + ' over ' + str(len(durations)) + ' runs',
                     _q(total / len(durations)), 's'])
    ref, trial = bundle['comparison']['reference_configuration'], bundle['comparison']['trial_configuration']
    seen = {}
    for m in bundle['measurements']:
        seen.setdefault((m['workload'], m['metric'], m['unit']), {})[m['configuration']] = m['value']
    for (workload, metric, unit), by_config in seen.items():
        if ref not in by_config or trial not in by_config:
            continue
        a, b = by_config[ref], by_config[trial]
        label = metric + ', ' + workload + ' workload'
        rows.append([label, 'trial minus reference', b + ' minus ' + a, _q(Decimal(b) - Decimal(a)),
                     'percentage points' if unit == '%' else unit])
        if metric in bundle['comparison']['ratio_metrics'] and Decimal(b) != 0:
            rows.append([label, 'reference divided by trial', a + ' divided by ' + b, _q(Decimal(a) / Decimal(b)), 'ratio'])
    return rows


def _decimal(token):
    token = unicodedata.normalize('NFKC', token).replace('\u2212', '-').replace(',', '')
    return Decimal(token)


def numbers_in(text):
    for match in NUMBER.finditer(unicodedata.normalize('NFKC', text)):
        try:
            yield match, _decimal(match.group())
        except InvalidOperation:
            continue


def allowed_numbers(bundle):
    allowed = {Decimal(c['value']) for c in bundle['counts']}
    for m in bundle['measurements']:
        allowed.add(Decimal(m['value']))
    for r in bundle['run_log']:
        allowed.update({Decimal(r['repeat']), Decimal(r['exit_code']), Decimal(r['duration_s'])})
    for row in expected_derived(bundle):
        allowed.add(Decimal(row[3]))
    # Evidence the bundle itself states in prose is evidence too.
    for text in [*bundle['scope_statements'], bundle['arithmetic_policy']]:
        allowed.update(value for _, value in numbers_in(text))
    return allowed


class DeliveryEvidenceChecks:
    def __init__(self, stage='delivery', *, executor=None):
        self.stage, self.executor = stage, executor
        self.check_ids = list(CHECK_IDS)

    async def __call__(self, ctx, inputs, outputs):
        evidence = list(ctx.output_refs.values())
        results = []
        for check_id in CHECK_IDS:
            try:
                getattr(self, '_' + check_id)(ctx, inputs, outputs)
                outcome, reason = 'PASS', 'Recomputed from the bound evidence bundle without error.'
            except CheckError as exc:
                outcome, reason = 'FAIL', str(exc)
            except (ValueError, KeyError, TypeError, InvalidOperation, UnicodeError) as exc:
                outcome, reason = 'FAIL', check_id + ': ' + type(exc).__name__
            results.append({'check_id': check_id, 'outcome': outcome, 'reason': reason, 'evidence_refs': evidence})
        return results

    @staticmethod
    def _text(outputs):
        raw = outputs['research_report']
        return raw.decode('utf-8', errors='strict') if isinstance(raw, bytes) else raw

    @staticmethod
    def _sections(text):
        lines = text.split('\n')
        if not lines or not lines[0].startswith('# ') or not lines[0][2:].strip():
            raise CheckError('research_report_schema', 'the report needs a single # title line first')
        if sum(line.startswith('# ') for line in lines) != 1:
            raise CheckError('required_sections', 'exactly one level-1 title is allowed')
        headings = [line[3:].strip() for line in lines if line.startswith('## ')]
        if headings != list(HEADINGS):
            raise CheckError('required_sections', 'the eight ## headings must appear once each, in order')
        bodies, current = {}, None
        for line in lines[1:]:
            if line.startswith('## '):
                current = line[3:].strip()
                bodies[current] = []
            elif current is not None:
                bodies[current].append(line)
        return {name: '\n'.join(body).strip() for name, body in bodies.items()}

    def _research_report_schema(self, ctx, inputs, outputs):
        validate(BUNDLE_SCHEMA, inputs['evidence_bundle'])
        text = self._text(outputs)
        validate(REPORT_SCHEMA, text)
        self._sections(text)

    def _required_sections(self, ctx, inputs, outputs):
        for name, body in self._sections(self._text(outputs)).items():
            if not body:
                raise CheckError('required_sections', 'empty section: ' + name)

    def _evidence_tables_match(self, ctx, inputs, outputs):
        bundle, sections = inputs['evidence_bundle'], self._sections(self._text(outputs))
        want = [_row([m['workload'], m['configuration'], m['metric'], m['value'], m['unit']]) for m in bundle['measurements']]
        got = [line for line in sections['Results'].split('\n')[2:]]
        if got != want:
            raise CheckError('evidence_tables_match', 'the Results table differs from the measurements')
        want = ([_row([r['configuration'], r['repeat'], r['exit_code'], r['duration_s']]) for r in bundle['run_log']]
                if bundle['run_log'] else ['No run log was supplied.'])
        got = sections['Run log'].split('\n')
        if bundle['run_log']:
            got = got[2:]
        if got != want:
            raise CheckError('evidence_tables_match', 'the Run log differs from the supplied run log')
        method = sections['Method and scope']
        position = 0
        for statement in bundle['scope_statements']:
            found = method.find(statement, position)
            if found < 0:
                raise CheckError('evidence_tables_match', 'a scope statement is missing or altered')
            position = found + len(statement)
        for count in bundle['counts']:
            if _row([count['name'].replace('_', ' '), count['value']]) not in method.split('\n'):
                raise CheckError('evidence_tables_match', 'a count row is missing or altered: ' + count['name'])

    def _derived_values_recomputed(self, ctx, inputs, outputs):
        bundle, sections = inputs['evidence_bundle'], self._sections(self._text(outputs))
        rows = expected_derived(bundle)
        lines = [line for line in sections['Derived comparisons'].split('\n') if line.startswith('|')]
        want = [_row(row) for row in rows]
        got = lines[2:] if lines else []
        if got != want:
            raise CheckError('derived_values_recomputed', 'the derived table differs from the exact recomputation')

    def _numbers_trace_to_evidence(self, ctx, inputs, outputs):
        bundle, text = inputs['evidence_bundle'], self._text(outputs)
        allowed, request_numbers = allowed_numbers(bundle), {v for _, v in numbers_in(bundle['request'])}
        normal = unicodedata.normalize('NFKC', text)
        for match, value in numbers_in(text):
            if value in allowed:
                continue
            start = max(normal.rfind('.', 0, match.start()), normal.rfind('\n', 0, match.start())) + 1
            ends = [i for i in (normal.find('.', match.end()), normal.find('\n', match.end())) if i >= 0]
            sentence = normal[start:min(ends) if ends else len(normal)]
            # A requested figure is not a claim when the same sentence declines it.
            if value in request_numbers and DENIAL.search(sentence):
                continue
            raise CheckError('numbers_trace_to_evidence', 'a number is not an evidence value or a derived value: ' + match.group())
