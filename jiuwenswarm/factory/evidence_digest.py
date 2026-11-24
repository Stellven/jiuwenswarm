"""Exact bounded JSON projections over current-task verified artifact bytes."""
from __future__ import annotations
import hashlib
import json
import math
import re
from .store import ScopeDenied

MAX_ARTIFACTS = 8
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 65536
MAX_POINTERS = 32
MAX_KEYS = 128
MAX_NODES = 100000
MAX_DEPTH = 64

def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'), sort_keys=True).encode('utf-8')

def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON object key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Nonfinite JSON value')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError('Malformed UTF-8 JSON or excessive depth') from error
    stack, nodes = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('JSON node/depth bound exceeded')
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError('Nonfinite JSON number')
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return value

def pointer_tokens(pointer):
    if not isinstance(pointer, str) or len(pointer.encode('utf-8')) > 1024:
        raise ValueError('JSON pointer must be a string of at most 1024 bytes')
    if pointer == '':
        return []
    if not pointer.startswith('/') or re.search(r'~(?![01])', pointer):
        raise ValueError('Malformed RFC6901 JSON pointer')
    return [part.replace('~1', '/').replace('~0', '~') for part in pointer[1:].split('/')]

def select(value, pointer):
    tokens = pointer_tokens(pointer)
    for token in tokens:
        if isinstance(value, dict):
            if token not in value:
                raise ValueError('Missing JSON pointer: ' + pointer)
            value = value[token]
        elif isinstance(value, list):
            if not re.fullmatch(r'0|[1-9][0-9]*', token) or len(token) > 10 or int(token) >= len(value):
                raise ValueError('Missing or invalid array pointer: ' + pointer)
            value = value[int(token)]
        else:
            raise ValueError('JSON pointer traverses a scalar: ' + pointer)
    return value

def shape(value):
    if value is None:
        return {'type': 'null'}
    if isinstance(value, dict):
        return {'type': 'object', 'length': len(value)}
    if isinstance(value, list):
        return {'type': 'array', 'length': len(value)}
    if isinstance(value, str):
        return {'type': 'string', 'utf8_bytes': len(value.encode('utf-8'))}
    return {'type': 'boolean' if isinstance(value, bool) else 'number'}

def project_document(raw, artifact_id, pointers=None):
    if not isinstance(raw, bytes) or len(raw) > MAX_SOURCE_BYTES:
        raise ValueError('Artifact source byte bound exceeded')
    value = strict_json(raw)
    keys = sorted(value) if isinstance(value, dict) else []
    if len(keys) > MAX_KEYS:
        raise ValueError('Top-level key cardinality bound exceeded')
    common = {'artifact_id': artifact_id, 'source_sha256': hashlib.sha256(raw).hexdigest(),
              'source_bytes': len(raw), 'root': shape(value)}
    if pointers is None:
        return {**common, 'top_level_fields': {key: shape(value[key]) for key in keys},
                'omitted_top_level_keys': keys, 'values_included': False}
    if not isinstance(pointers, list) or not 1 <= len(pointers) <= MAX_POINTERS:
        raise ValueError('pointers must contain 1..32 exact JSON pointers')
    if any(not isinstance(p, str) for p in pointers) or len(set(pointers)) != len(pointers):
        raise ValueError('JSON pointers must be unique strings')
    selections, touched = [], set()
    for pointer in pointers:
        tokens = pointer_tokens(pointer)
        selected = select(value, pointer)
        touched.update(keys if not tokens else tokens[:1])
        selections.append({'pointer': pointer, 'value': selected,
                           'value_json_sha256': hashlib.sha256(encoded(selected)).hexdigest()})
    return {**common, 'selections': selections,
            'omitted_top_level_keys': [key for key in keys if key not in touched],
            'unselected_nested_fields_may_remain': any(pointer_tokens(p) for p in pointers),
            'parsed_values_exact': True, 'original_json_lexemes_preserved': False,
            'scientific_summary_generated': False}

def dispatch(store, task_id, operation, inputs):
    if operation not in {'index', 'project'}:
        raise ValueError('Unknown evidence digest operation')
    if not isinstance(inputs, dict):
        raise ValueError('Inputs must be an object')
    if len(encoded(inputs)) > 65536:
        raise ValueError('Digest serialized input byte bound exceeded')
    allowed = {'artifact_ids', 'max_output_bytes'} if operation == 'index' else {'sources', 'max_output_bytes'}
    if set(inputs) - allowed or not (allowed - {'max_output_bytes'}) <= set(inputs):
        raise ValueError('Unknown or missing digest input fields')
    if hasattr(store, 'task_id') and store.task_id != task_id:
        raise ScopeDenied('Digest requires the current task, even with cross-task read grants')
    budget = inputs.get('max_output_bytes', MAX_OUTPUT_BYTES)
    if type(budget) is not int or not 1 <= budget <= MAX_OUTPUT_BYTES:
        raise ValueError('max_output_bytes must be 1..65536')
    sources = [{'artifact_id': identity} for identity in inputs['artifact_ids']] if operation == 'index' and isinstance(inputs['artifact_ids'], list) else inputs.get('sources')
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_ARTIFACTS:
        raise ValueError('Supply 1..8 artifact sources')
    identities, metadata = set(), []
    total = 0
    for source in sources:
        expected = {'artifact_id'} if operation == 'index' else {'artifact_id', 'pointers'}
        if not isinstance(source, dict) or set(source) != expected:
            raise ValueError('Invalid source fields')
        if operation == 'project':
            pointers = source['pointers']
            if not isinstance(pointers, list) or not 1 <= len(pointers) <= MAX_POINTERS:
                raise ValueError('pointers must contain 1..32 exact JSON pointers')
        identity = source['artifact_id']
        if not isinstance(identity, str) or not 1 <= len(identity) <= 256 or identity in identities:
            raise ValueError('Unique bounded artifact IDs required')
        identities.add(identity)
        # Fetch scoped metadata before reading/verifying any blob, so an
        # oversized artifact fails before artifact_bytes loads it.
        if hasattr(store, '_check'):
            store._check(task_id)
            host = store._store
        else:
            host = store
        record = host._get('artifacts', task_id, identity)
        if record['media_type'] != 'application/json' and not record['media_type'].endswith('+json'):
            raise ValueError('Artifact media type must identify JSON')
        total += record['size']
        if record['size'] > MAX_SOURCE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError('Artifact source byte bound exceeded')
        metadata.append((source, record))
    results = []
    for source, record in metadata:
        raw = store.artifact_bytes(task_id, source['artifact_id'])
        if len(raw) != record['size'] or hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('Verified artifact identity changed')
        results.append(project_document(raw, source['artifact_id'], source.get('pointers')))
    result = {'operation': operation, 'task_id': task_id, 'sources': results,
              'source_input_bytes': total, 'bounds': {'max_artifacts': MAX_ARTIFACTS,
              'max_source_bytes': MAX_SOURCE_BYTES, 'max_total_bytes': MAX_TOTAL_BYTES,
              'max_output_bytes': budget, 'max_pointers_per_source': MAX_POINTERS,
              'max_top_level_keys': MAX_KEYS, 'max_nodes_per_source': MAX_NODES, 'max_depth': MAX_DEPTH},
              'partial_context': True, 'truncated': False, 'inferences_generated': False}
    outputs = {'result': result}
    # Bound the complete success envelope, not merely the selected source values.
    if len(json.dumps({'outcome': 'ok', 'outputs': outputs}, ensure_ascii=False, allow_nan=False).encode('utf-8')) + 1 > budget:
        raise ValueError('Serialized output byte bound exceeded; request fewer explicit fields')
    return outputs
