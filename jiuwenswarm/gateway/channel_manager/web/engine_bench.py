"""Read the normalized engine benchmark dataset and its fixed report documents without following source references."""

import json
import os
from pathlib import Path
import stat

from jiuwenswarm.factory import taskgraph
from jiuwenswarm.factory.redact import sanitize

SCHEMA = 'engine-bench/1'
MAX_DATASET_BYTES = 4 * 1024 * 1024
MAX_DOCUMENT_BYTES = 256 * 1024
DOCUMENTS = {'readme': 'README.md', 'method-history': 'strict-history.md'}
R8_TASK = 'muse-2bit-demo-r8'
SOURCE_EXCERPT_FIELDS = frozenset((
    'arm', 'request', 'state', 'repeat', 'n_predict', 'prompt_tokens', 'generated_tokens',
    'client_ttft_ms', 'request_total_ms', 'prompt_ms', 'prompt_tokens_per_second',
    'decode_tokens_per_second', 'output_sha256',
))
REPORT_FIELDS = frozenset((
    'schema', 'id', 'date', 'run', 'comparison_group', 'arm', 'kind', 'label', 'error',
    'engine', 'pack', 'settings', 'request', 'metrics', 'memory', 'quiet', 'source', 'sources',
    'launch_verdict', 'corrected_verdict', 'attempt_id', 'test', 'n', 'acc', 'reference_acc', 'delta', 'interval', 'margin', 'verdict',
))


def _reject_constant(value):
    raise ValueError(f'Invalid JSON constant {value}')


def _read_fixed_file(directory: Path, filename: str, limit: int):
    """Only use server-selected filenames. Refuse symlinks and nonregular files."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    *parents, leaf = filename.split('/')
    try:
        directory_fd = os.open(directory, flags)
    except FileNotFoundError:
        return None
    try:
        for parent in parents:
            child_fd = os.open(parent, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        data_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    except FileNotFoundError:
        return None
    finally:
        os.close(directory_fd)
    with os.fdopen(data_fd, 'rb') as resource:
        if not stat.S_ISREG(os.fstat(resource.fileno()).st_mode):
            raise ValueError('Benchmark resource must be a regular file')
        data = resource.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Benchmark resource exceeds the size limit')
    return data.decode('utf-8')


def read_engine_bench_document(directory: Path, document: str):
    data = _read_fixed_file(directory, DOCUMENTS[document], MAX_DOCUMENT_BYTES)
    return sanitize(data) if data is not None else None


def _delivery_summary(directory, rows):
    records = {}
    for name in ('tasks', 'observations', 'decisions'):
        data = _read_fixed_file(directory, f'graph/records/{name}.json', MAX_DATASET_BYTES)
        if data is None:
            return None
        records[name] = json.loads(data, parse_constant=_reject_constant)
    tasks = records['tasks']
    if len(tasks) != 1 or tasks[0]['task_id'] != R8_TASK:
        raise ValueError('The R8 graph export has the wrong task')
    graph = taskgraph.from_records(records)
    nodes = [node for node in graph['nodes'] if node['state'] not in {'cancelled', 'superseded'}]
    latest = max((row for row in records['decisions'] if row['task_id'] == R8_TASK),
                 key=lambda row: row['rev'], default=None)
    image_data = _read_fixed_file(directory, 'manifests/image-receipt.json', MAX_DOCUMENT_BYTES)
    image = json.loads(image_data, parse_constant=_reject_constant) if image_data is not None else {}
    timed = [row for row in rows if row.get('run') == 'r8-lab' and row.get('arm') in {'B', 'P'}
             and row['kind'] == 'performance']
    image_id = image.get('image_id')
    return {
        'completed': sum(node['state'] == 'done' for node in nodes),
        'total': len(nodes),
        'image_delivered': bool(image_id and any(node['node_id'] == 'deliver_to_lab' and node['state'] == 'done'
                                                for node in nodes)),
        'measured': any(not row.get('error') and (row.get('corrected_verdict') or {}).get('status') == 'accepted'
                        and (row.get('metrics') or {}).get('ttft_ms') is not None for row in timed),
        'decision': {'kind': latest['action']['type'], 'reason': latest.get('uncertainty'),
                     'id': latest['decision_id']} if latest else None,
    }


def read_engine_bench(directory: Path):
    """The caller supplies the trusted directory. The request supplies no path."""
    data = _read_fixed_file(directory, 'engine-bench.jsonl', MAX_DATASET_BYTES)
    if data is None:
        return {'schema': SCHEMA, 'status': 'unavailable', 'rows': []}

    rows = []
    ids = set()
    for line in data.splitlines():
        if not line.strip():
            continue
        row = json.loads(line, parse_constant=_reject_constant)
        if (not isinstance(row, dict) or row.get('schema') != SCHEMA
                or row.get('kind') not in {'performance', 'load', 'accuracy'}
                or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in ids
                or not isinstance(row.get('source'), dict)
                or not isinstance(row['source'].get('path'), str)):
            raise ValueError('Benchmark dataset contains an invalid row')
        ids.add(row['id'])
        report = {key: value for key, value in row.items() if key in REPORT_FIELDS}
        raw = row.get('raw')
        server = raw.get('server') if isinstance(raw, dict) else None
        if row['kind'] == 'performance' and isinstance(raw, dict):
            excerpt = {key: value for key, value in raw.items() if key in SOURCE_EXCERPT_FIELDS
                       and isinstance(value, (str, int, float))}
            if excerpt:
                report['source_excerpt'] = excerpt
        if (isinstance(report.get('pack'), dict) and isinstance(server, dict)
                and isinstance(server.get('census'), dict)):
            report['pack'].setdefault('census', server['census'])
        rows.append(report)
    # Validate JSON compatibility before the response is serialized (e.g. a 1e999 value).
    json.dumps(rows, allow_nan=False)
    result = {'schema': SCHEMA, 'status': 'ready', 'rows': rows}
    delivery = _delivery_summary(directory, rows)
    if delivery is not None:
        result['delivery'] = delivery
    return sanitize(result)
