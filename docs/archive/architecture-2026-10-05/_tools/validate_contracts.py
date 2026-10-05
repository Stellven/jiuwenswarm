"""Check every contract schema in contracts/ and its fixtures. Documentation check only: no runtime claim.

Layout:
  contracts/<name>.schema.json          JSON Schema 2020-12 with $defs, one def per message or record
  contracts/fixtures/<name>.json        {"schema": "<name>.schema.json",
                                         "cases": [{"def": "runner_request", "valid": [..], "invalid": [..]}]}
Rules checked:
  * every schema is valid JSON Schema and every $ref resolves (other contracts and exports/schemas are importable)
  * every def listed in the communication index (contracts/README.md and contracts/index-*.md tables), in every schema file,
    has a fixture case with at least one valid and one invalid example
  * valid examples validate; invalid examples are rejected
  * every def in a schema is either named in the communication index or marked `"x-internal": true`
  * principles.md rules, per def and per family (the Family column of the index):
      - strings have maxLength, lists have maxItems, date-time strings end in Z (RFC 3339 UTC)
      - enum values are lower_snake or UPPER_SNAKE by field name, never mixed
      - `ext` only on Record and Report defs and only as the services-v1 ext helper
      - top-level messages carry version / schema_version / protocol_version; nested objects do not carry a const version
      - every _request def requires request_id; every object _result def requires request_id
      - `_at` fields are date-time, `dispatch_id` is an id, `*sha256` fields are hashes, policy_ref and vocabulary_ref are refs
Usage: python validate_contracts.py
"""
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

V = Path(__file__).resolve().parents[1]
C = V / 'contracts'
errors = []

schemas = {}
for p in sorted(C.glob('*.schema.json')):
    s = json.loads(p.read_text(encoding='utf-8'))
    schemas[p.name] = s
resources = {s['$id']: s for s in schemas.values()}
for p in (V / 'exports/schemas').rglob('*.json'):
    s = json.loads(p.read_text(encoding='utf-8'))
    if '$id' in s:
        resources[s['$id']] = s
registry = Registry().with_resources((k, Resource.from_contents(v)) for k, v in resources.items())
for name, s in schemas.items():
    try:
        Draft202012Validator.check_schema(s)
    except Exception as e:  # noqa: BLE001
        errors.append(f'{name}: invalid schema: {e}')

readme = ''.join(x.read_text(encoding='utf-8') for x in [C / 'README.md', *sorted(C.glob('index-*.md'))])
indexed = set(re.findall(r'`([a-z0-9_.-]+\.schema\.json)#([a-z_0-9]+)`', readme))

FAMILIES = {'Call', 'Record', 'Event', 'Frame', 'Profile', 'Report', 'Helper'}
ROW = re.compile(r'^\| `([a-z0-9_.-]+\.schema\.json)#([a-z_0-9]+)` \| (\w+) \|')
family = {}
for ix in sorted(C.glob('index-*.md')):
    for line in ix.read_text(encoding='utf-8').split(chr(10)):
        if line.startswith('| `') and '.schema.json#' in line:
            m = ROW.match(line)
            if not (m and m.group(3) in FAMILIES):
                errors.append(f'{ix.name}: row without a valid Family (Call, Record, Event, Frame, Profile, Report, Helper): {line[:70]}')
            else:
                family[(m.group(1), m.group(2))] = m.group(3)

covered = set()
for p in sorted((C / 'fixtures').glob('*.json')) if (C / 'fixtures').exists() else []:
    f = json.loads(p.read_text(encoding='utf-8'))
    sname = f['schema']
    if sname not in schemas:
        errors.append(f'{p.name}: unknown schema {sname}')
        continue
    schema = schemas[sname]
    for case in f['cases']:
        d = case['def']
        if d not in schema.get('$defs', {}):
            errors.append(f'{p.name}: def {d} not in {sname}')
            continue
        covered.add((sname, d))
        wrapper = {'$ref': f"{schema['$id']}#/$defs/{d}"}
        v = Draft202012Validator(wrapper, registry=registry, format_checker=FormatChecker())
        if not case.get('valid'):
            errors.append(f'{p.name}: {d} has no valid example')
        if not case.get('invalid'):
            errors.append(f'{p.name}: {d} has no invalid example')
        for i, ex in enumerate(case.get('valid', [])):
            errs = list(v.iter_errors(ex))
            if errs:
                errors.append(f'{p.name}: {d} valid[{i}] rejected: {errs[0].message[:140]}')
        for i, ex in enumerate(case.get('invalid', [])):
            if not v.is_valid(ex):
                continue
            errors.append(f'{p.name}: {d} invalid[{i}] was accepted')

for sname, d in sorted(indexed):
    if sname not in schemas:
        errors.append(f'communication index names missing schema {sname}')
    elif d not in schemas[sname].get('$defs', {}):
        errors.append(f'communication index names {sname}#{d}, which does not exist')
    elif (sname, d) not in covered:
        errors.append(f'communication index entry {sname}#{d} has no fixture case')

for sname, s in schemas.items():
    for d, body in s.get('$defs', {}).items():
        if (sname, d) not in indexed and not body.get('x-internal'):
            errors.append(f'{sname}#{d} is not in the communication index (add it or mark x-internal)')

# ---------------- principles lint ----------------
UPPER = re.compile(r'^[A-Z][A-Z0-9_]*$')
LOWER = re.compile(r'^[a-z][a-z0-9_]*$')
UPPER_NAMES = {'verdict', 'gate_verdict', 'normalized_verdict', 'status', 'code', 'reason_code', 'reason', 'unavailable_reason', 'routing_action', 'observed'}
LOWER_NAMES = {'state', 'kind', 'action', 'decision', 'outcome', 'phase', 'operation', 'purpose', 'result'}
VERSION_KEYS = ('version', 'schema_version', 'protocol_version')
VERSION_EXEMPT = {'call_descriptor'}  # carries the constant cc: 1 (descriptor version), a canonical-JSON cache key


def walk(node, fn, name=None, nested=False):
    if not isinstance(node, dict):
        return
    fn(node, name, nested)
    for k in ('properties', 'patternProperties', '$defs', 'dependentSchemas'):
        if isinstance(node.get(k), dict):
            for pn, child in node[k].items():
                walk(child, fn, pn if k == 'properties' else name, nested or k == 'properties')
    for k in ('items', 'additionalProperties', 'not', 'if', 'then', 'else', 'contains', 'propertyNames', 'unevaluatedProperties'):
        if isinstance(node.get(k), dict):
            walk(node[k], fn, name, nested)
    for k in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
        if isinstance(node.get(k), list):
            for child in node[k]:
                walk(child, fn, name, nested)


def variants(body):
    """top-level object variants of a def (oneOf of objects counts each member)"""
    if 'oneOf' in body:
        return [v for v in body['oneOf'] if isinstance(v, dict) and v.get('type') == 'object']
    return [body] if body.get('type') == 'object' and 'properties' in body else []


def isref(node, suffix):
    if not isinstance(node, dict):
        return False
    if '$ref' in node:
        return node['$ref'].endswith(suffix)
    for k in ('anyOf', 'oneOf'):
        if k in node:
            return any(isref(x, suffix) for x in node[k])
    return False


def lint(sname, d, body):
    where = f'{sname}#{d}'
    fam = family.get((sname, d))

    def node_rules(node, name, nested):
        t = node.get('type')
        ts = t if isinstance(t, list) else [t]
        if node.get('format') == 'date-time':
            if not str(node.get('pattern', '')).endswith('Z$'):
                errors.append(f'{where}: date-time field {name} has no pattern ending in Z (RFC 3339 UTC)')
        elif 'string' in ts and '$ref' not in node and not any(k in node for k in ('enum', 'const', 'maxLength')):
            if '{' not in node.get('pattern', ''):
                errors.append(f'{where}: string field {name} has no maxLength')
        if 'array' in ts and 'maxItems' not in node:
            errors.append(f'{where}: list field {name} has no maxItems')
        if isinstance(node.get('enum'), list):
            vals = [x for x in node['enum'] if isinstance(x, str)]
            if vals:
                kinds = {'U' if UPPER.match(x) else 'l' if LOWER.match(x) else 'X' for x in vals}
                if len(kinds) > 1 or 'X' in kinds:
                    errors.append(f'{where}: enum {name} mixes styles or is not snake case: {vals[:4]}')
                elif name in UPPER_NAMES and kinds != {'U'}:
                    errors.append(f'{where}: enum {name} must be UPPER_SNAKE: {vals[:4]}')
                elif name in LOWER_NAMES and kinds != {'l'}:
                    errors.append(f'{where}: enum {name} must be lower_snake: {vals[:4]}')
        props = node.get('properties')
        if isinstance(props, dict):
            if nested and isinstance(props.get('version'), dict) and 'const' in props['version']:
                errors.append(f'{where}: nested object carries a version (only top-level messages do)')
            for pn, pv in props.items():
                if not isinstance(pv, dict) or 'const' in pv or pv.get('type') == 'null':
                    continue
                if pn.endswith('_at') and 'date-time' not in json.dumps(pv) and '/time' not in json.dumps(pv):
                    errors.append(f'{where}: {pn} is not a date-time')
                if pn == 'dispatch_id' and not isref(pv, '/id'):
                    errors.append(f'{where}: dispatch_id must be an id')
                if (pn == 'sha256' or pn.endswith('_sha256')) and not (isref(pv, '/hash') or 'pattern' in json.dumps(pv)):
                    errors.append(f'{where}: {pn} must be a hash')
                if pn in ('policy_ref', 'vocabulary_ref') and not isref(pv, '/ref'):
                    errors.append(f'{where}: {pn} must be a ref {{id, sha256}}')
    walk(body, node_rules, d)

    if body.get('x-internal') or fam is None:
        return
    for v in variants(body):
        props = v['properties']
        if 'ext' in props:
            if fam not in ('Record', 'Report'):
                errors.append(f'{where}: ext is only allowed on Record and Report defs (family {fam})')
            elif not isref(props['ext'], '/ext'):
                errors.append(f'{where}: ext must reference the services-v1 ext helper')
        if fam in ('Helper',) or d in VERSION_EXEMPT:
            continue
        if fam == 'Frame' and 't' in props:
            continue
        if fam == 'Frame' and d == 'skill_turn_frame':
            continue
        if not any(k in props for k in VERSION_KEYS):
            errors.append(f'{where}: top-level {fam} has no version, schema_version or protocol_version')
        if d.endswith('_request') and 'request_id' not in v.get('required', []):
            errors.append(f'{where}: request def must require request_id')
        if d.endswith('_result') and fam == 'Call' and 'request_id' not in v.get('required', []):
            errors.append(f'{where}: result def must require request_id')


for sname, s in schemas.items():
    for d, body in s.get('$defs', {}).items():
        lint(sname, d, body)

if errors:
    print('\n'.join(errors))
    print(f'{len(errors)} contract problem(s)')
    sys.exit(1)
n = sum(len(s.get('$defs', {})) for s in schemas.values())
print(f'{len(schemas)} contract files, {n} definitions, {len(covered)} fixture-covered; schemas valid; examples agree; principles lint clean')
