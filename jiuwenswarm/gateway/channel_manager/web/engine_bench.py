"""Read the normalized engine benchmark dataset without following source references."""

import json
import os
from pathlib import Path
import stat

from jiuwenswarm.factory.redact import sanitize

SCHEMA = 'engine-bench/1'
MAX_DATASET_BYTES = 4 * 1024 * 1024
REPORT_FIELDS = frozenset((
    'schema', 'id', 'date', 'run', 'comparison_group', 'arm', 'kind', 'label', 'error',
    'engine', 'pack', 'settings', 'request', 'metrics', 'memory', 'quiet', 'source', 'sources',
    'attempt_id', 'test', 'n', 'acc', 'reference_acc', 'delta', 'interval', 'margin', 'verdict',
))


def _reject_constant(value):
    raise ValueError(f'Invalid JSON constant {value}')


def read_engine_bench(directory: Path):
    """The caller supplies the trusted directory. The request supplies no path."""
    try:
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return {'schema': SCHEMA, 'status': 'unavailable', 'rows': []}
    try:
        try:
            data_fd = os.open('engine-bench.jsonl', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                              dir_fd=directory_fd)
        except FileNotFoundError:
            return {'schema': SCHEMA, 'status': 'unavailable', 'rows': []}
    finally:
        os.close(directory_fd)
    with os.fdopen(data_fd, 'rb') as dataset:
        if not stat.S_ISREG(os.fstat(dataset.fileno()).st_mode):
            raise ValueError('Benchmark dataset must be a regular file')
        data = dataset.read(MAX_DATASET_BYTES + 1)
    if len(data) > MAX_DATASET_BYTES:
        raise ValueError('Benchmark dataset exceeds the size limit')

    rows = []
    ids = set()
    for line in data.decode('utf-8').splitlines():
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
