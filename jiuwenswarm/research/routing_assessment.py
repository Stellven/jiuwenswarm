"""Bounded task evidence and conservative quality guards, independent of fixtures.

This is worker-routing metadata, never verifier input. It extracts declared task
rules and data structure, not answer keys, IDs or measured per-case results.
"""
from __future__ import annotations

import json
import re

_INSTRUCTIONS = {'task', 'objective', 'research_objective', 'rule', 'rules', 'policy',
    'constraints', 'requirements', 'deliverables', 'acceptance', 'instructions'}
_METRIC = re.compile(r'accuracy|precision|recall|f1\b|probabilit|percent|p\d\d\b|latency|mean|median|ratio|rate\b|score', re.I)
_DECISION = re.compile(r'threshold|target|greatest|best\b|choose|accept\b|satisf|constraint|\biff\b|at least|at most', re.I)
_OPTIMIZE = re.compile(r'maximi[sz]|minimi[sz]|optimi[sz]|shortest|longest|break ties|argmax|argmin|lexicograph', re.I)
_GUARANTEE = re.compile(r'\bproof\b|\bprove\b|guarantee|safety|security|fail.closed|adversarial', re.I)


def task_evidence(prompt, objective, context=None):
    rules, shapes = [], []
    remaining = 4200

    def add(text):
        nonlocal remaining
        if isinstance(text, str) and text.strip() and remaining > 0:
            value = text[:min(1000, remaining)]
            if value not in rules:
                rules.append(value)
                remaining -= len(value)

    def walk(value, path='input', depth=0):
        if depth > 7 or len(shapes) >= 70:
            return
        if isinstance(value, dict):
            shapes.append({'path': path, 'type': 'object', 'fields': sorted(str(k)[:60] for k in value)[:30]})
            for key, item in list(value.items())[:30]:
                if str(key).lower() in _INSTRUCTIONS:
                    if isinstance(item, list):
                        for text in item[:4]: add(text)
                    else: add(item)
                if isinstance(item, (dict, list)):
                    walk(item, path+'.'+str(key)[:60], depth+1)
        elif isinstance(value, list):
            shapes.append({'path': path, 'type': 'array', 'length': len(value),
                'item_types': sorted({type(item).__name__ for item in value[:100]})})
            # One structural representative; no data rows, labels, IDs or
            # numeric values are placed in the selector view.
            for item in value[:1]:
                if isinstance(item, (dict, list)):
                    walk(item, path+'[]', depth+1)

    add(objective)
    if context:
        walk(context, 'context')
    # Generated CC prompts may embed JSON after prose. Only decoded bounded
    # structures/instruction fields are disclosed; arbitrary document text is
    # not copied into the selector request.
    decoder = json.JSONDecoder()
    for match in list(re.finditer(r'[\[{]', prompt))[:32]:
        try:
            value, _ = decoder.raw_decode(prompt, match.start())
        except ValueError:
            continue
        if isinstance(value, (dict, list)):
            walk(value)
            break
    text = '\n'.join(rules)
    risks = []
    if _OPTIMIZE.search(text): risks.append('optimization_or_tie_sensitive_selection')
    if _METRIC.search(text) and _DECISION.search(text): risks.append('derived_metric_controls_decision')
    if _GUARANTEE.search(text): risks.append('safety_or_correctness_guarantee')
    return {'schema': 'ai4r-task-evidence:1', 'instruction_excerpts': rules,
        'input_structure': shapes, 'protected_risk_flags': risks,
        'source_values_disclosed': False}


def assess_selection(value, eligible, policy):
    allowed_ops = {'extract', 'lookup', 'format', 'count', 'compare', 'arithmetic',
        'aggregate', 'optimize', 'fit', 'invert', 'constraints', 'proof', 'code', 'other'}
    if (not isinstance(value, dict) or set(value) != {'operations', 'difficulty', 'candidate_id', 'reason'}
            or value.get('difficulty') not in {'routine', 'reasoning', 'critical'}
            or not isinstance(value.get('operations'), list) or not 1 <= len(value['operations']) <= len(allowed_ops)
            or any(not isinstance(op, str) or op not in allowed_ops for op in value['operations'])
            or len(set(value['operations'])) != len(value['operations'])
            or not isinstance(value.get('reason'), str) or not 0 < len(value['reason']) <= 600):
        raise ValueError('Invalid task-risk assessment')
    by_id = {candidate['id']: candidate for candidate in eligible}
    if value.get('candidate_id') not in by_id:
        raise ValueError('Assessor named an incompatible candidate')
    ops = set(value['operations'])
    critical = value['difficulty'] == 'critical' or bool(ops & {'optimize', 'proof', 'other'})
    reasoning = value['difficulty'] == 'reasoning' or bool(ops & {'aggregate', 'fit', 'invert', 'constraints', 'code'}
        or {'count', 'arithmetic'} <= ops or {'arithmetic', 'compare'} <= ops)
    if critical:
        target = 'subscription:gpt-6.1-sol'
    elif reasoning:
        permitted = policy['reasoning_executor_ids']
        target = value['candidate_id'] if value['candidate_id'] in permitted else next((k for k in permitted if k in by_id), None)
    else:
        target = value['candidate_id']
    if target not in by_id:
        from .contracts import ResearchError
        raise ResearchError('ENVIRONMENT_BLOCKED', 'Required quality tier is unavailable; do not downgrade')
    return by_id[target], 'Risk '+value['difficulty']+'; operations '+','.join(sorted(ops))+': '+value['reason']
