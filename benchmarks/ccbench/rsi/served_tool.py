"""Portable T1 interface bridge; computes no answers and preserves the selected worker.

This executes inside the benchmark sandbox, not the protected RSI evaluator.
The frozen bootstrap verifies every runtime file and the exact Python build.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from decimal import Decimal


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def pinned(path, expected):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('RSI bundle file is missing or linked: ' + str(path))
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise RuntimeError('RSI bundle digest differs: ' + str(path))
    return raw


def packet(payload, family, declaration):
    """Translate ports and impose the historical benchmark's narrower boundary."""
    files = []
    if family == 'calculate':
        values, mode, operation = payload['values'], payload['mode'], payload['operation']
        ports, ranges = declaration['ports']['inputs'], declaration['ranges']
        if (type(values) is not list or len(values) > ranges['max_rows']
                or mode not in ports['mode'] or operation not in ports['operation']):
            raise ValueError('benchmark input domain')
        for value in values:
            if mode == 'json_numbers' and type(value) not in (int, float):
                raise ValueError('benchmark number type')
            if mode == 'decimal_strings' and (type(value) is not str or len(value) > 100
                    or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', value)):
                raise ValueError('benchmark numeric grammar')
            number = Decimal(str(value))
            if (not number.is_finite() or len(number.as_tuple().digits) > ranges['max_digits']
                    or abs(number.adjusted()) > ranges['max_adjusted_exponent']):
                raise ValueError('benchmark numeric range')
        data = {'table': {'columns': ['value'], 'rows': [[value] for value in values]},
                'calculation': {'columns': ['value'], 'operations': [operation], 'numeric_mode': mode}}
    elif family == 'table_normalize':
        text = payload['text']
        if type(text) is not str:
            raise ValueError('benchmark text type')
        name = 'input.' + ('json' if payload['format'] == 'json' else 'csv')
        files = [{'path': name, 'text': text, 'sha256': sha(text.encode())}]
        data = {'table_request': {'file': name, 'format': payload['format'],
                                 'columns': payload['columns'], 'delimiter': payload['delimiter']}}
    else:
        raise RuntimeError('unsupported benchmark port adapter: ' + family)
    return {'schema_version': '1.0.0', 'data': data, 'files': files, 'trust': 'low',
            'provenance': [], 'limitations': ['Historical T1 benchmark port adapter.']}


def invoke(payload, *, directory, specification, specification_sha256):
    root = Path(directory)
    spec = json.loads(pinned(root / specification, specification_sha256))
    family = spec['family']
    declaration = json.loads(pinned(root / 'declarations.json', spec['declarations_sha256']))[family]
    try:
        request = packet(payload, family, declaration)
        input_raw = encoded({'packet': request})
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return {'status': 'error'}
    manifest_raw = pinned(root / spec['manifest'], spec['manifest_sha256'])
    body = pinned(root / spec['body'], spec['selection']['body_ref']['sha256'])
    bootstrap = pinned(root / 'bootstrap.py', spec['bootstrap_sha256']).decode()
    with tempfile.TemporaryDirectory(prefix='ai4r-t1-rsi-') as temporary:
        work = Path(temporary).resolve()
        (work / 'body.py').write_bytes(body)
        (work / 'input.json').write_bytes(input_raw)
        (work / 'capsule-runtime-manifest.json').write_bytes(manifest_raw)
        config = {'bootstrap_schema': 'ai4r-rsi-capsule-bootstrap:2', 'capsule_name': spec['capsule_name'],
                  'manifest_sha256': spec['manifest_sha256'], 'candidate_sha256': sha(body),
                  'input_sha256': sha(input_raw), 'iterations': 1, 'output_limit_bytes': 2 * 1024 * 1024,
                  'execution_profile': 'local_unprotected', 'resource_root': str(work),
                  'runtime_root': str((root / spec['runtime']).resolve())}
        # Only typed domain errors become the legacy error port. Broken pins,
        # ABI mismatches and unexpected candidate exceptions stay visible errors.
        trailer = '\ntry:\n    _child_main(' + repr(config) + ')\nexcept Exception as error:\n'
        trailer += "    import sys, json\n    module = sys.modules.get('jiuwenswarm.research.contracts')\n"
        trailer += "    if module is not None and isinstance(error, module.ResearchError) and error.code in ('calculation_input', 'table_input', 'packet_limit'):\n"
        trailer += "        print('AI4R_T1_DOMAIN_ERROR', file=sys.stderr)\n        raise SystemExit(42)\n    raise\n"
        (work / 'worker.py').write_text(bootstrap + trailer, encoding='utf-8')
        completed = subprocess.run([sys.executable, '-I', '-S', '-B', str(work / 'worker.py')],
                                   capture_output=True, timeout=60)
    if completed.returncode == 42 and completed.stderr.strip() == b'AI4R_T1_DOMAIN_ERROR':
        return {'status': 'error'}
    if completed.returncode or len(completed.stdout) > 2 * 1024 * 1024:
        raise RuntimeError('Selected RSI worker failed: ' + completed.stderr.decode(errors='replace')[-2000:])
    output = json.loads(completed.stdout)['data']
    if family == 'calculate':
        return {'status': 'ok', 'value': output['calculation_result']['columns']['value'][payload['operation']]}
    return {'status': 'ok', **output['table']}


def main(argv, run, family):
    # The partner CLI interfaces are retained, including filtering and output.
    if family == 'calculate':
        if len(argv) < 3:
            print('usage: calc_tool.py FILE.csv COLUMN OPERATION [--where COLUMN=VALUE]')
            print('operations: count sum mean min max')
            return 2
        path, column, operation = argv[:3]
        with open(path, newline='', encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        if '--where' in argv:
            key, value = argv[argv.index('--where') + 1].split('=', 1)
            rows = [row for row in rows if row[key] == value]
        result = run({'values': [row[column] for row in rows], 'mode': 'decimal_strings', 'operation': operation})
        if result['status'] != 'ok':
            print('error: could not compute')
            return 1
        print(result['value'])
        return 0
    if not argv:
        print('usage: table_tool.py FILE.csv|FILE.json')
        return 2
    path = argv[0]
    is_json = path.lower().endswith('.json')
    with open(path, encoding='utf-8', newline='') as stream:
        text = stream.read()
    columns = list(json.loads(text)[0].keys()) if is_json else next(csv.reader(io.StringIO(text, newline='')))
    result = run({'text': text, 'format': 'json' if is_json else 'csv', 'columns': columns,
                  'delimiter': None if is_json else ','})
    print(json.dumps(result))
    return 0 if result['status'] == 'ok' else 1
