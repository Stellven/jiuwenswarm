"""Task contracts, format 2 (``factory.contract/2``).

A format-2 contract says what is tested, on which engine and model, how it is measured and
when a result counts. It names every file by logical name, size and digest; where the
files lie on a machine is decided by the lab that runs it (see ``resolve``). Anything a
contract needs that the format does not hold goes under ``extensions.<namespace>``, so the
format itself rarely has to change. Adding an optional field keeps the format; changing
the meaning of a field needs ``factory.contract/3``.

Format-1 contracts (the JSON files that carry ``tolerance`` or ``adapter``) are still
loaded by ``contract.load`` exactly as before.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA_ID = 'factory.contract/2'
SCHEMAS = Path(__file__).parent / 'schemas'
PLACEHOLDER = re.compile(r'\{(model|model_dir|output_dir|input:([A-Za-z0-9][A-Za-z0-9._-]*))\}')
# Absolute host paths belong in a lab's binding, never in a contract.
HOST_PATH = re.compile(r'(^|[\s=:"\'])(/home/|/Users/|/root/|/mnt/|/opt/|/tmp/|~/|[A-Za-z]:\\)')


def schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding='utf-8'))


def schema_errors(document, name):
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(schema(name))
    errors = sorted(validator.iter_errors(document), key=lambda e: [str(p) for p in e.absolute_path])
    return [('/'.join(str(p) for p in error.absolute_path) or '(top)') + ': ' + error.message for error in errors]


def _strings(value, path=''):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f'{path}/{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f'{path}/{index}')


def host_paths(document):
    """Paths of fields (outside extensions) whose text holds an absolute host path."""
    body = {k: v for k, v in document.items() if k != 'extensions'}
    return [path for path, text in _strings(body) if HOST_PATH.search(text)]


def arm_ids(contract):
    return [arm['id'] for arm in contract['arms']]


def check_ids(contract):
    return [check['id'] for check in contract['correctness']['checks']]


def request_ids(contract):
    return [request['id'] for request in contract['workload']['requests']]


def metric_ids(contract):
    return list(contract['measurement']['metrics'])


def arms_for(contract, selectors):
    """Arm ids named by a list of arm ids or arm roles."""
    roles = {}
    for arm in contract['arms']:
        roles.setdefault(arm['role'], []).append(arm['id'])
    result = []
    for selector in selectors:
        for arm in ([selector] if selector in arm_ids(contract) else roles.get(selector, [])):
            if arm not in result:
                result.append(arm)
    return result


def _duplicates(values):
    seen, repeated = set(), []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return repeated


def problems(contract):
    """Every reason the document is not a valid format-2 contract, in a stable order."""
    found = schema_errors(contract, 'contract-2.schema.json')
    if found:
        return found
    arms, roles = arm_ids(contract), {arm['role'] for arm in contract['arms']}
    inputs = contract.get('inputs', {})
    for label, values in (('arm', arms), ('check', check_ids(contract)), ('request', request_ids(contract))):
        for value in _duplicates(values):
            found.append(f'{label} id {value!r} is declared twice')
    for arm in contract['arms']:
        if 'from' in arm and arm['from'] not in arms:
            found.append(f'arms/{arm["id"]}/from: unknown arm {arm["from"]!r}')
        if arm.get('from') == arm['id']:
            found.append(f'arms/{arm["id"]}/from: an arm cannot derive from itself')
    measurement = contract['measurement']
    metrics = set(measurement['metrics'])
    if measurement['primary'] not in metrics:
        found.append(f'measurement/primary: {measurement["primary"]!r} is not a declared metric')
    for name, derived in measurement.get('derived', {}).items():
        if name in metrics:
            found.append(f'measurement/derived/{name}: name is already a metric')
        for used in derived['uses']:
            if used not in metrics and used not in arms:
                found.append(f'measurement/derived/{name}/uses: {used!r} is neither a metric nor an arm')
    correctness = contract['correctness']
    reference = correctness.get('reference')
    if reference:
        if reference['arm'] not in arms:
            found.append(f'correctness/reference/arm: unknown arm {reference["arm"]!r}')
        frozen = reference.get('output_sha256')
        if frozen and not (reference.get('frozen_at') and reference.get('run_ref')):
            found.append('correctness/reference: a frozen reference needs frozen_at and run_ref')
        if not frozen and (reference.get('frozen_at') or reference.get('run_ref')):
            found.append('correctness/reference: frozen_at and run_ref need output_sha256')
    elif correctness['equivalence'] not in {'not_required', 'approximate'}:
        found.append('correctness/reference: equivalence ' + correctness['equivalence'] + ' needs a reference arm')
    for check in correctness['checks']:
        for selector in check['applies_to']:
            if selector not in arms and selector not in roles:
                found.append(f'correctness/checks/{check["id"]}/applies_to: {selector!r} is neither an arm nor a role in use')
    workload = contract['workload']
    texts = [*workload['argv'], *workload.get('env', {}).values()]
    for request in workload['requests']:
        if 'input' in request and request['input'] not in inputs:
            found.append(f'workload/requests/{request["id"]}/input: unknown input {request["input"]!r}')
        texts.extend(text for _, text in _strings(request.get('params', {})))
    for text in texts:
        for match in PLACEHOLDER.finditer(text):
            if match.group(2) and match.group(2) not in inputs:
                found.append(f'workload: placeholder {match.group(0)} names no declared input')
            if match.group(1) in {'model', 'model_dir'} and 'model' not in contract['subject']:
                found.append(f'workload: placeholder {match.group(0)} needs subject.model')
    for path in host_paths(contract):
        found.append(f'{path.lstrip("/")}: absolute host path; name the file in inputs or subject and let the lab resolve it')
    return found


def validate(contract):
    found = problems(contract)
    if found:
        raise ValueError('Invalid factory.contract/2: ' + '; '.join(found[:20])
                         + (f' (and {len(found) - 20} more)' if len(found) > 20 else ''))
    return contract


def is_frozen(contract):
    return bool((contract['correctness'].get('reference') or {}).get('output_sha256'))


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def resolve(contract, binding):
    """Argv, env and requests with placeholders replaced from a lab binding.

    ``binding`` is the lab's own record of where things lie:
    ``{"model": path, "model_dir": path, "output_dir": path, "inputs": {name: path}}``.
    A missing location raises; the lab must say where every named file is.
    """
    inputs = binding.get('inputs', {})

    def fill(text):
        def replace(match):
            key, name = match.group(1), match.group(2)
            value = inputs.get(name) if name else binding.get(key)
            if not value:
                raise ValueError(f'Lab binding gives no location for {match.group(0)}')
            return str(value)
        return PLACEHOLDER.sub(replace, text)

    def walk(value):
        if isinstance(value, str):
            return fill(value)
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        return value

    workload = contract['workload']
    requests = []
    for request in workload['requests']:
        resolved = dict(request, params=walk(request.get('params', {})))
        if 'input' in request:
            location = inputs.get(request['input'])
            if not location:
                raise ValueError(f'Lab binding gives no location for input {request["input"]!r}')
            resolved['input_path'] = str(location)
        requests.append(resolved)
    return dict(argv=walk(workload['argv']), env=walk(workload.get('env', {})), requests=requests)


def verify_inputs(contract, binding):
    """Check that every bound input file has the contract's size and digest."""
    found = []
    for name, spec in contract.get('inputs', {}).items():
        location = binding.get('inputs', {}).get(name)
        if not location:
            found.append(f'{name}: no location')
            continue
        path = Path(location)
        if not path.is_file():
            found.append(f'{name}: {path} is not a file')
        elif path.stat().st_size != spec['size'] or file_sha256(path) != spec['sha256']:
            found.append(f'{name}: size or sha256 differs from the contract')
    return found


def _atomic_write(path, document):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(document, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def freeze(path, output_sha256, run_ref, frozen_at=None):
    """Record the reference output once. A frozen contract changes only as version+1."""
    path = Path(path)
    if not re.fullmatch(r'[a-f0-9]{64}', output_sha256 or ''):
        raise ValueError('Reference output SHA256 is required')
    if not isinstance(run_ref, str) or not run_ref:
        raise ValueError('run_ref is required')
    lock = path.with_name(path.name + '.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Contract is being frozen by another process') from None
    try:
        os.close(fd)
        contract = validate(json.loads(path.read_text(encoding='utf-8')))
        if is_frozen(contract):
            raise ValueError('Contract is frozen; create a version+1 contract file')
        reference = contract['correctness'].get('reference')
        if not reference:
            raise ValueError('Contract has no reference arm to freeze')
        reference.update(output_sha256=output_sha256, run_ref=run_ref,
                         frozen_at=frozen_at or datetime.now(timezone.utc).isoformat())
        validate(contract)
        _atomic_write(path, contract)
        return contract
    finally:
        lock.unlink(missing_ok=True)
