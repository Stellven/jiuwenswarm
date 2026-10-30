"""Stopgap: one bounded re-ask of a carrier reply that fails its own reply schema.

Carriers built on capsules/_common.ask end their fixed instructions with the
public contract, including call_reply_schema. The runner validates a completed
reply against that schema and, within the invocation's single retry allowance,
asks once more with the validator's findings. Carrier bytes and pins do not
change; the carrier and every check still judge whatever comes back.
"""
from __future__ import annotations

import json

from .capsules._common import strict_json
from .contracts.types import ResearchError

# Written by the frozen capsules/_common.ask immediately before the contract JSON.
CONTRACT_MARKER = '\nProtected public contract and exact bound input identities:\n'
NOT_JSON = '(root): reply is not one finite JSON object without duplicate members'


def carrier_reply_schema(system):
    """(True, schema-or-None) for an ask-built system text, else (False, None)."""
    if not isinstance(system, str) or CONTRACT_MARKER not in system:
        return False, None
    try:
        contract = json.loads(system.rsplit(CONTRACT_MARKER, 1)[1])
    except ValueError:
        return False, None
    schema = contract.get('call_reply_schema') if isinstance(contract, dict) else None
    return True, schema if isinstance(schema, dict) else None


def reply_problems(text, schema, limit=8):
    """Short reply-schema violations: path, rule and bound, never the offending text."""
    try:
        value = strict_json(text)
    except ResearchError:
        return [NOT_JSON]
    if schema is None:
        return []
    from jsonschema import Draft202012Validator
    from .contracts.validators import _contracts
    problems = []
    errors = Draft202012Validator(schema, registry=_contracts()[1]).iter_errors(value)
    for error in sorted(errors, key=lambda e: [str(p) for p in e.absolute_path]):
        where = '/'.join(str(p) for p in error.absolute_path) or '(root)'
        if error.validator in ('maxLength', 'minLength') and isinstance(error.instance, str):
            detail = '%s %s, got %d characters' % (error.validator, error.validator_value, len(error.instance))
        elif error.validator in ('maxItems', 'minItems') and isinstance(error.instance, list):
            detail = '%s %s, got %d items' % (error.validator, error.validator_value, len(error.instance))
        elif error.validator in ('required', 'additionalProperties'):
            detail = error.message[:200]
        else:
            detail = '%s %s' % (error.validator, json.dumps(error.validator_value, ensure_ascii=False)[:200])
        problems.append(where + ': ' + detail)
        if len(problems) >= limit:
            break
    return problems


def span_problems(text, prompt, read_text, limit=8):
    """Source spans outside their source, as the compiler checks judge them.

    Only sources whose Ref the model was shown in this prompt are read, and a
    finding names the bound and the source length, never the source text.
    """
    try:
        value = strict_json(text)
    except ResearchError:
        return []
    problems, lengths = [], {}

    def walk(item, path):
        if len(problems) >= limit:
            return
        if isinstance(item, dict):
            ref = item.get('source_ref')
            if (isinstance(ref, dict) and isinstance(ref.get('sha256'), str) and ref['sha256'] in prompt
                    and type(item.get('start')) is int and type(item.get('end')) is int):
                if ref['sha256'] not in lengths:
                    try:
                        lengths[ref['sha256']] = len(read_text(ref))
                    except Exception:
                        lengths[ref['sha256']] = None
                size = lengths[ref['sha256']]
                if size is not None and not 0 <= item['start'] < item['end'] <= size:
                    problems.append('%s: span start %d end %d must satisfy 0 <= start < end <= %d, the length of '
                                    'source %s in Unicode code points' % (path or '(root)', item['start'], item['end'],
                                                                           size, ref['sha256'][:12]))
            for key, child in item.items():
                walk(child, path + '/' + key if path else key)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, path + '/' + str(index) if path else str(index))

    walk(value, '')
    return problems


def repair_prompt(prompt, text, problems):
    """The original payload plus the previous reply and the validator findings."""
    try:
        inputs = json.loads(prompt)
    except ValueError:
        inputs = prompt
    return json.dumps({'inputs': inputs, 'repair': {
        'previous_reply': text[:65536], 'validation_errors': problems,
        'instruction': 'Your previous reply did not satisfy call_reply_schema. Return the complete corrected '
                       'JSON object. Change only what the validation errors require.'}}, ensure_ascii=False)
