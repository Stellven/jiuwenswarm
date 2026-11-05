"""Bounded, read-only workspace inventory; optional YAML support."""
import csv
import heapq
import json
import os
from pathlib import Path
import sys
from collections import Counter

SKIP = {'.git', '.venv', 'node_modules', '__pycache__'}
STRUCTURED = {'.json', '.jsonl', '.csv', '.yaml', '.yml'}


def value_type(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, dict):
        return 'object'
    if isinstance(value, list):
        return 'array'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, (int, float)):
        return 'number'
    return type(value).__name__


def shape(value):
    return {'type': value_type(value), 'keys': {
        str(k): value_type(v) for k, v in value.items()
    } if isinstance(value, dict) else {}}


def describe(path):
    text = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.csv':
        rows = list(csv.reader(text.splitlines()))
        return {'line_count': len(text.splitlines()), 'row_count': max(0, len(rows) - 1),
                'columns': rows[0] if rows else []}
    if path.suffix.lower() == '.jsonl':
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        columns = sorted({str(k) for row in rows if isinstance(row, dict) for k in row})
        return {'line_count': len(text.splitlines()), 'row_count': len(rows), 'columns': columns}
    if path.suffix.lower() == '.json':
        return shape(json.loads(text))
    try:
        import yaml
    except ImportError:
        return {'reason': 'yaml parser unavailable'}
    return shape(yaml.safe_load(text))


def inspect(packet):
    inputs = packet.get('inputs', {})
    handle = inputs.get('workspace')
    resource = packet.get('resources', {}).get(handle) if isinstance(handle, str) else None
    if not resource or not resource.get('path'):
        raise ValueError('Unknown or missing workspace handle')
    root = Path(resource['path']).resolve()
    if not root.is_dir():
        raise ValueError('Workspace path is not a directory')
    output = Path(packet['output_dir']).resolve()
    if output == root or root in output.parents:
        raise ValueError('output_dir must be outside the workspace')
    limit = inputs.get('max_files', 2000)
    if type(limit) is not int or limit < 0:
        raise ValueError('max_files must be a nonnegative integer')
    report = {'file_count': 0, 'total_bytes': 0, 'counts_by_extension': {},
              'largest_files': [], 'structured_files': [], 'errors': [],
              'max_files': limit, 'truncated': False}
    extensions, largest = Counter(), []

    def walk_error(error):
        report['errors'].append({'reason': str(error)})

    for folder, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not (Path(folder) / d).is_symlink())
        for name in sorted(files):
            path = Path(folder) / name
            if path.is_symlink() or not path.is_file():
                continue
            if report['file_count'] >= limit:
                report['truncated'] = True
                break
            relative = path.relative_to(root).as_posix()
            try:
                size = path.stat().st_size
                report['file_count'] += 1
                report['total_bytes'] += size
                suffix = path.suffix.lower()
                extensions[suffix or '(none)'] += 1
                heapq.heappush(largest, (size, relative))
                if len(largest) > 10:
                    heapq.heappop(largest)
                if suffix in STRUCTURED and size <= 1024 * 1024 and len(report['structured_files']) < 50:
                    detail = {'path': relative}
                    try:
                        detail.update(describe(path))
                    except Exception as error:
                        detail['reason'] = str(error)
                    report['structured_files'].append(detail)
            except OSError as error:
                report['errors'].append({'path': relative, 'reason': str(error)})
        if report['truncated']:
            break
    report['counts_by_extension'] = dict(sorted(extensions.items()))
    report['largest_files'] = [{'path': name, 'bytes': size} for size, name in sorted(largest, reverse=True)]
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return {'outcome': 'ok', 'outputs': {'report': report, 'summary': {'path': 'summary.json'}}}


if __name__ == '__main__':
    try:
        result = inspect(json.load(sys.stdin))
    except Exception as error:
        result = {'outcome': 'error', 'outputs': {}, 'reason': str(error),
                  'error': {'code': 'WORKSPACE_INSPECTION_FAILED', 'message': str(error)}}
    print(json.dumps(result))
