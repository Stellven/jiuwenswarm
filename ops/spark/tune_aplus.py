#!/usr/bin/env python3
"""Run the stock MoE tuner with capped shard warming and a first-run review stop."""
import argparse
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path.home() / 'predemo-spark'
MAX_MIB = 61440
TUNER_SHA256 = 'c3baf2d21ba7119cdd78a941f4f587caee2b376bad1c83bb44d194231ae6998b'
WARM_SHARDS = '''
import sys

for name in sys.argv[1:]:
    print(name, flush=True)
    with open(name, 'rb') as shard:
        while shard.read(64 * 1024 * 1024):
            pass
'''


class FirstCalibrationComplete(Exception):
    pass


def load_tuner(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != TUNER_SHA256:
        raise SystemExit('REFUSED: stock tuner digest changed')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('stock_moe_cache_tune', path)
    tuner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tuner)
    return tuner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['first', 'continue'])
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    model, out = args.model.absolute(), args.out.resolve()
    command = [str(ROOT / 'bin/tune-server'), '-m', str(model), '-lm', 'mmap', '--cpu-moe']
    approval_boundary = out / 'first-calibration.json'
    if args.phase == 'first':
        out.mkdir(parents=True, exist_ok=False)
    elif not approval_boundary.is_file() or (out / 'command.txt').read_text() != shlex.join(command):
        raise SystemExit('REFUSED: continuation needs completed first calibration with the identical command')

    native = load_tuner(ROOT / 'llama.cpp-stock/scripts/moe-cache-tune.py')
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    native.FMT['markdown'] = True
    native_run_server = native.run_server

    def run_server(cmd, destination, mib, share, n_predict, seed, label, _native_warm):
        if not 0 < mib <= MAX_MIB:
            raise SystemExit(f'REFUSED: native calibration {mib} MiB exceeds the permitted 1–{MAX_MIB} MiB')
        if args.phase == 'continue' and label == '1/6':
            base = Path(destination) / f'run-{mib}-{share:g}'
            if not all(base.with_suffix(ext).is_file() for ext in ('.json', '.trace')):
                raise SystemExit('REFUSED: retain the first calibration result and routing trace before continuing')
        if args.phase == 'first':
            warm_dir = ROOT / 'OPS/runs' / f'aplus-tune-warm-{time.time_ns()}'
            subprocess.run([str(ROOT / 'bin/capped'), '--arm', 'A+-tune-warm', '--result-dir', str(warm_dir), '--',
                            sys.executable, '-c', WARM_SHARDS, *native.model_files(str(model))], check=True)
            (out / 'warm-scope.txt').write_text(str(warm_dir) + '\n')

        scope_index = out / f'run-{mib}-{share:g}.scopes'
        os.environ['SPARK_TUNE_SCOPE_INDEX'] = str(scope_index)
        result = native_run_server(cmd, destination, mib, share, n_predict, seed, label, lambda: None)
        scopes = scope_index.read_text().splitlines()
        for scope in scopes:
            receipt = json.loads((Path(scope) / 'result.json').read_text())
            if receipt['returncode'] != 0 or receipt['reason'] or not receipt['scope_verified']:
                raise SystemExit(f'REFUSED: calibration scope did not complete safely: {scope}')
        if result['hits'] + result['misses'] == 0:
            raise SystemExit(f'REFUSED: native tuner reported no cache activity for {scope_index.stem}')
        if args.phase == 'first':
            native.device_room((out / f'run-{mib}-{share:g}.log').read_text(errors='replace'))
            approval_boundary.write_text(json.dumps({'native_tuner_sha256': TUNER_SHA256, 'max_mib': MAX_MIB,
                                                     'calibration': result, 'scopes': scopes}, indent=2) + '\n')
            raise FirstCalibrationComplete
        return result

    native.run_server = run_server
    try:
        native.tune(command, str(out), MAX_MIB)
    except FirstCalibrationComplete:
        print(f'First calibration complete. Review {approval_boundary} before continuing.', flush=True)


if __name__ == '__main__':
    main()
