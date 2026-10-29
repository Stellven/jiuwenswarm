"""Offline packet checks, without execution, provenance admission or semantic review.

Evidence paths are JSON pointers into the supplied packet (or /declaration).
PASS concerns the stated deterministic predicate only, never product acceptance.
Unsupported rule syntax and missing evidence cause abstention, never inference.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from .. import science

PASS, FAIL, NA = 'PASS', 'FAIL', 'NOT_ASSESSABLE'
_NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
_EXPR = rf'treatment\s*(<=|>=|==|<|>)\s*({_NUMBER}\s*\*\s*baseline(?:\s*\+\s*{_NUMBER})?|baseline(?:\s*\+\s*{_NUMBER})?|{_NUMBER})'
_COMPARATORS = {'<': 'lt', '<=': 'le', '==': 'eq', '>=': 'ge', '>': 'gt'}


def comparison(text):
    """Parse a restricted affine ComparisonRule expression; never eval text."""
    m = re.fullmatch(_EXPR, text.strip())
    if not m:
        raise ValueError('unsupported_comparison')
    rhs = m[2]
    if 'baseline' in rhs:
        left, right = rhs.split('baseline')
        factor = float(left.strip().rstrip('*').strip()) if left.strip() else 1
        offset = float(right.strip()[1:].strip()) if right.strip() else 0
        reference = 'baseline'
    else:
        factor, offset, reference = 0, float(rhs), 'constant'
    rule = dict(operand='treatment', comparator=_COMPARATORS[m[1]],
                reference=reference, factor=factor, offset=offset)
    science.threshold(rule, 1)
    return rule


def parse_declaration(declaration):
    """Accept blueprint/outcome-rule JSON or explicit labeled affine prose.

    A per-metric rule list is kept per metric; a single unkeyed rule is global.
    Arbitrary prose, ambiguous duplicate labels and unsupported syntax abstain.
    """
    if isinstance(declaration, str):
        try:
            return parse_declaration(json.loads(declaration))
        except (ValueError, TypeError):
            pass
        found = {}
        for m in re.finditer(_EXPR, declaration):
            suffix = declaration[m.end():].split(';')[0].split('.')[0].strip().lower()
            prefix = declaration[max(0, m.start()-30):m.start()].lower()
            role = next((r for r, words in [('success', ('success',)),
                         ('falsification', ('falsification', 'falsifies'))]
                         if any(suffix.startswith(w) or suffix.startswith('is '+w)
                                or re.search(r'\b'+w+r'\s*:\s*$', prefix) for w in words)), None)
            if role:
                if role in found:
                    raise ValueError('ambiguous_rules')
                found[role] = comparison(m[0])
        if set(found) != {'success', 'falsification'}:
            raise ValueError('unsupported_declaration')
        found.update(middle='INCONCLUSIVE', conditional_rule=None, conditional_meaning=None)
        matched = []
        if re.search(r'\bmatched\b', declaration, re.I):
            matched = [name for name, pattern in [('batch', r'\bbatch'), ('dataset', r'\bdataset'),
                       ('hardware', r'\b(?:hardware|CPU|GPU)\b')] if re.search(pattern, declaration, re.I)]
        aggregation = next((x for x in ('median', 'mean', 'min', 'max')
                            if re.search(r'\b'+x+r's?\b', declaration, re.I)), None)
        return {'rules': {None: found}, 'matched_fields': matched, 'aggregation': aggregation}
    if not isinstance(declaration, Mapping):
        raise ValueError('unsupported_declaration')
    source = declaration.get('outcome_rules', declaration)
    if isinstance(source, Mapping) and 'success' in source:
        rules = {source.get('metric_id'): source}
    elif isinstance(source, list):
        rules = {r['metric_id']: r for r in source}
        if len(rules) != len(source):
            raise ValueError('duplicate_registered_metric')
    else:
        raise ValueError('unsupported_declaration')
    for rule in rules.values():
        for key in ('success', 'falsification'):
            science.threshold(rule[key], 1)
    return {'rules': rules, 'matched_fields': declaration.get('matched_fields', []),
            'aggregation': declaration.get('aggregation')}


def _strings(value, path=''):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for k, v in value.items():
            yield from _strings(v, path+'/'+str(k).replace('~', '~0').replace('/', '~1'))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, path+'/'+str(i))


def prompt_injection_notes(packet):
    """Heuristic advisory only: string content never supplies checker instructions."""
    pattern = r'(?i)\b(?:ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions|system\s*prompt|you\s+must\s+(?:output|return|approve)|override\s+(?:the\s+)?(?:verdict|rules)|mark\s+.*\s+as\s+pass)\b'
    return [dict(status='NOTE', reason='instruction_like_packet_text', evidence_path=p)
            for p, s in _strings(packet) if re.search(pattern, s)]


def check_packet(declaration, packet):
    """Return all ten profile criteria, each with a reason code and evidence path."""
    profile = json.loads((Path(__file__).parents[1]/'resources/calibration/science_checking_profile.json').read_text())
    results = {c['criterion_id']: dict(status=NA, reason='semantic_review_required',
               evidence_path='/', blocking=c['blocking']) for c in profile['criteria']}
    def put(cid, status, reason, path):
        results[cid].update(status=status, reason=reason, evidence_path=path)
    if not isinstance(packet, Mapping):
        put('declared_output_conformance', FAIL, 'packet_not_object', '/')
        return results
    fs = packet.get('findings')
    shape = (isinstance(fs, list) and bool(fs) and all(isinstance(f, Mapping) for f in fs)
             and all(isinstance(packet.get(k), list) for k in ('blockers', 'residual_risks', 'followups'))
             and all(isinstance(packet.get(k), Mapping) for k in ('completeness', 'plausibility'))
             and isinstance(packet.get('ext'), Mapping)
             and isinstance(packet['ext'].get('benchmark.evidence'), Mapping))
    put('declared_output_conformance', PASS if shape else FAIL, 'finite_packet_carrier_shape', '/')
    if not shape:
        return results
    evidence = packet['ext']['benchmark.evidence']
    ep = '/ext/benchmark.evidence'
    try:
        parsed = parse_declaration(declaration)
    except (ValueError, KeyError, TypeError, science.ScienceError):
        parsed = None
    ids = [f.get('metric_id') for f in fs]
    valid_ids = all(isinstance(x, str) and x.strip() for x in ids)
    put('finding_names_metric', PASS if valid_ids and len(set(ids)) == len(ids) else FAIL,
        'distinct_nonempty_metric_ids', '/findings')
    problems, unknown = [], not bool(parsed)
    sources = evidence.get('sources', [])
    sources = list(sources.values()) if isinstance(sources, Mapping) else sources
    provided = {s.get('source_id', s.get('id')) for s in sources
                if isinstance(s, Mapping) and s.get('source_excerpt', s.get('excerpt'))}
    if evidence.get('source_id') and evidence.get('source_excerpt'):
        provided.add(evidence['source_id'])
    citations = evidence.get('citations', [evidence['citation']] if 'citation' in evidence else [])
    if not citations or not provided:
        unknown = True
    for citation in citations:
        if provided and (not isinstance(citation, str) or citation not in provided):
            problems.append(('unresolved_citation', ep+'/citation'))
    if parsed:
        for field in parsed['matched_fields']:
            aliases = ('hardware', 'cpu', 'CPU', 'gpu', 'GPU') if field == 'hardware' else (field,)
            pair = next(((evidence['baseline_'+a], evidence['treatment_'+a]) for a in aliases
                         if 'baseline_'+a in evidence and 'treatment_'+a in evidence), None)
            if pair is None:
                unknown = True
            elif pair[0] != pair[1]:
                problems.append(('unmatched_'+field, ep+'/treatment_'+field))
    value_failures, value_unknown = [], False
    unmeasured = False
    for i, f in enumerate(fs):
        path = '/findings/'+str(i)
        rule = parsed['rules'].get(f.get('metric_id'), parsed['rules'].get(None)) if parsed and isinstance(f.get('metric_id'), str) else None
        b, t = f.get('baseline_value'), f.get('treatment_value')
        unmeasured |= b is None or t is None or f.get('rule_applied') == 'unmeasured'
        inline = evidence if len(fs) == 1 else next((m for m in evidence.get('metrics', [])
                  if m.get('metric_id') == f.get('metric_id')), {})
        for side in ('baseline', 'treatment'):
            repeats = inline.get(side+'_repeats')
            if repeats == [] and f.get(side+'_value') is not None:
                problems.append(('unmeasured_coerced_to_value', path+'/'+side+'_value'))
                unmeasured = True
            elif repeats and parsed and parsed['aggregation']:
                try:
                    actual = science.aggregate(repeats, parsed['aggregation'])
                    if not science.close(actual, f.get(side+'_value')):
                        value_failures.append(('value_disagrees_with_repeats', path+'/'+side+'_value'))
                except (ValueError, TypeError):
                    value_unknown = True
        if not rule:
            value_unknown = unknown = True
            continue
        try:
            expected_class, applied, cutoff = science.classify_metric(b, t, rule)
            if f.get('rule_text') != science.rule_text(rule, f.get('rule_applied')):
                problems.append(('registered_rule_substitution', path+'/rule_text'))
            # Internal stated-rule consistency is distinct from registration agreement.
            stated = re.fullmatch(r'(success|falsification|conditional):\s*(.*)', f.get('rule_text', ''))
            if stated and b is not None and t is not None:
                local = comparison(stated[2])
                cls = {'success': 'PASS', 'falsification': 'FAIL', 'conditional': 'CONDITIONALLY_ACCEPTABLE'}[stated[1]]
                if (f.get('rule_applied') != stated[1] or f.get('classification') != cls
                    or not science.rule_holds(local, b, t)
                    or not science.close(f.get('threshold'), science.threshold(local, b))):
                    value_failures.append(('finding_rule_value_disagreement', path))
            elif (f.get('classification'), f.get('rule_applied'), f.get('threshold')) != (expected_class, applied, cutoff):
                value_failures.append(('finding_registered_outcome_disagreement', path))
        except (ValueError, TypeError, KeyError):
            value_unknown = True
    if problems:
        put('internal_consistency', FAIL, problems[0][0], problems[0][1])
    else:
        put('internal_consistency', NA if unknown else PASS,
            'missing_deterministic_context' if unknown else 'local_evidence_and_registration_agree', ep)
    # Keep every witness, including collateral defects, machine-readable.
    results['internal_consistency']['evidence'] = [dict(reason=r, evidence_path=p) for r, p in problems]
    put('finding_consistent_with_values', FAIL if value_failures else NA if value_unknown else PASS,
        value_failures[0][0] if value_failures else 'unsupported_rule_or_values' if value_unknown else 'values_rules_thresholds_agree',
        value_failures[0][1] if value_failures else '/findings')
    try:
        expected = science.overall_classification([f.get('classification') for f in fs], packet['plausibility'].get('status'))
        status = (PASS if packet.get('classification') == expected else FAIL) if packet.get('aggregation_rule') == 'm1_conjunctive_v1' else NA
        put('classification_consistent_with_findings', status, 'overall_classification_recomputed' if status != NA else 'unsupported_aggregation_rule', '/classification')
    except (ValueError, TypeError):
        put('classification_consistent_with_findings', NA, 'invalid_aggregation_inputs', '/findings')
    need = unmeasured or packet['plausibility'].get('status') == 'implausible'
    status = FAIL if bool(packet['blockers']) != need else NA if need else PASS
    put('blockers_match_findings', status, 'blocker_presence_mismatch' if status == FAIL else 'blocker_explanation_requires_review' if status == NA else 'no_blockers_required', '/blockers')
    if not packet['followups']:
        put('followups_are_recommendations', PASS, 'empty_followups', '/followups')
    return results


def review(packet, declaration):
    criteria = check_packet(declaration, packet)
    failures = [k for k, v in criteria.items() if v['blocking'] and v['status'] == FAIL]
    unknown = [k for k, v in criteria.items() if v['status'] == NA]
    return dict(advance=False if failures else None if any(criteria[k]['blocking'] for k in unknown) else True,
                blocking_failures=failures, not_assessable=unknown, criteria=criteria,
                notes=prompt_injection_notes(packet))
