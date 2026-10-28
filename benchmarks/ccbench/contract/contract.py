"""Output-contract validator and answer scorer (model-free). The validator reads only the declared contract (ports),
never the gold. The scorer reads the gold and is used only after a run.

Port fields: name, type (number | integer | string | boolean), unit, decimals (number: at most this many digits after
the point), min / max (inclusive), pattern (string: full match), description.
"""
import json
import re
from decimal import Decimal as D, InvalidOperation


def parse_reply(text):
    """Extract one JSON object from a reply. Returns (obj | None, error | None). Literals keep their digits (floats as Decimal)."""
    if text is None or not text.strip():
        return None, 'empty reply'
    body = text.strip()
    fence = re.search(r'```(?:json)?\s*\n(.*?)```', body, flags=re.S)
    if fence:
        body = fence.group(1).strip()
    if not body.startswith('{'):
        a, b = body.find('{'), body.rfind('}')
        if a < 0 or b <= a:
            return None, 'no JSON object found'
        body = body[a:b + 1]
    try:
        obj = json.loads(body, parse_float=D, parse_int=int)
    except ValueError as exc:
        return None, 'not valid JSON: %s' % exc
    if not isinstance(obj, dict):
        return None, 'reply is not a JSON object'
    return obj, None


def check_value(port, value):
    """List of violations for one value against one port."""
    t, name, bad = port['type'], port['name'], []
    if t == 'boolean':
        return [] if isinstance(value, bool) else ['%s must be a boolean (true/false)' % name]
    if t == 'string':
        if not isinstance(value, str):
            return ['%s must be a string' % name]
        if port.get('pattern') and not re.fullmatch(port['pattern'], value):
            bad.append('%s = %r does not match the required pattern %s' % (name, value, port['pattern']))
        return bad
    if isinstance(value, bool) or not isinstance(value, (int, D)):
        return ['%s must be a JSON number, not %s' % (name, type(value).__name__)]
    if t == 'integer':
        if not isinstance(value, int):
            bad.append('%s must be an integer with no decimal point (unit: %s)' % (name, port.get('unit')))
    elif t == 'number':
        exponent = D(value).as_tuple().exponent if isinstance(value, D) else 0
        if isinstance(exponent, int) and -exponent > port.get('decimals', 99):
            bad.append('%s has %d decimals; at most %d are allowed' % (name, -exponent, port['decimals']))
    if port.get('min') is not None and D(value) < D(str(port['min'])):
        bad.append('%s = %s is below the minimum %s %s' % (name, value, port['min'], port.get('unit', '')))
    if port.get('max') is not None and D(value) > D(str(port['max'])):
        bad.append('%s = %s is above the maximum %s %s' % (name, value, port['max'], port.get('unit', '')))
    return bad


def validate(text, ports):
    """Return (violations, obj). Empty violations means the reply honours the declared contract."""
    obj, err = parse_reply(text)
    if err:
        return [err], None
    names = [p['name'] for p in ports]
    bad = ['missing required field %s' % n for n in names if n not in obj]
    bad += ['unexpected field %s' % k for k in obj if k not in names]
    for p in ports:
        if p['name'] in obj:
            bad += check_value(p, obj[p['name']])
    return bad, obj


def value_correct(port, value, gold):
    if port['type'] == 'boolean':
        return isinstance(value, bool) and value == gold
    if port['type'] == 'string':
        return isinstance(value, str) and value == gold
    if isinstance(value, bool) or not isinstance(value, (int, D)):
        return False
    if port['type'] == 'integer':
        return D(value) == D(gold) and (isinstance(value, int) or D(value) == D(value).to_integral_value())
    return D(value) == D(gold)


def score_reply(text, ports, gold):
    """Per-field correctness (compared with the gold value) and contract compliance of one reply."""
    obj, err = parse_reply(text)
    violations, _ = validate(text, ports)
    fields = {}
    for p in ports:
        ok = False
        if obj is not None and p['name'] in obj:
            try:
                ok = value_correct(p, obj[p['name']], gold[p['name']])
            except (InvalidOperation, ValueError, TypeError):
                ok = False
        fields[p['name']] = ok
    correct = all(fields.values())
    compliant = not violations
    return dict(parsed=obj is not None, fields=fields, all_correct=correct, compliant=compliant, correct_and_compliant=correct and compliant,
                violations=violations[:6])
