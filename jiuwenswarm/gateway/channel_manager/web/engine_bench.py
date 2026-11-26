"""Read the normalized engine benchmark dataset and its fixed report documents without following source references."""

import json
import os
from pathlib import Path
import stat

from jiuwenswarm.factory.redact import sanitize

SCHEMA = 'engine-bench/1'
MAX_DATASET_BYTES = 4 * 1024 * 1024
MAX_DOCUMENT_BYTES = 256 * 1024
DOCUMENTS = {'readme': 'README.md', 'method-history': 'strict-history.md'}
REPORT_FIELDS = frozenset((
    'schema', 'id', 'date', 'run', 'comparison_group', 'arm', 'kind', 'label', 'error',
    'engine', 'pack', 'settings', 'request', 'metrics', 'memory', 'quiet', 'source', 'sources',
    'launch_verdict', 'corrected_verdict', 'attempt_id', 'test', 'n', 'acc', 'reference_acc', 'delta', 'interval', 'margin', 'verdict',
))


def _reject_constant(value):
    raise ValueError(f'Invalid JSON constant {value}')


def _read_fixed_file(directory: Path, filename: str, limit: int):
    """Only use server-selected filenames. Refuse symlinks and nonregular files."""
    try:
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    try:
        try:
            data_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
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
        if (isinstance(report.get('pack'), dict) and isinstance(server, dict)
                and isinstance(server.get('census'), dict)):
            report['pack'].setdefault('census', server['census'])
        rows.append(report)
    # Validate JSON compatibility before the response is serialized (e.g. a 1e999 value).
    json.dumps(rows, allow_nan=False)
    return {'schema': SCHEMA, 'status': 'ready', 'rows': sanitize(rows)}
