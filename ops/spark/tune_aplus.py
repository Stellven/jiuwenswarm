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
    parser.add_argument('phase', choices=['first', 'point-30', 'point-60'])
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

    if args.phase != 'first':
        first = json.loads(approval_boundary.read_text())
        previous = first['calibration']
        first_base = out / f"run-{previous['mib']}-{previous['share']:g}"
        for ext in ('.json', '.trace'):
            if not first_base.with_suffix(ext).is_file():
                raise SystemExit('Missing original first calibration evidence')
        host, device, free, used = native.device_room(first_base.with_suffix('.log').read_text(errors='replace'))
        mib = 30720 if args.phase == 'point-30' else MAX_MIB
        if mib > free - used - 512 or mib >= host:
            raise SystemExit(f'Requested {mib} MiB exceeds first-load room on {device}')
        if args.phase == 'point-60' and not (out / 'point-30.json').is_file():
            raise SystemExit('Complete the 30 GiB point before the 60 GiB point')
        # Preserve upstream calibration generations and its shutdown-counter parser.
        # Match the sampling seeds across the two additional zero-CPU-share points.
        measured = run_server(command, out, mib, 0.0, native.N_CALIB, 3, args.phase, None)
        selected = {'calibration': measured, 'native_tuner_sha256': TUNER_SHA256,
                    'protocol': 'Owner-capped three-size survey, native run_server, fixed CPU share 0',
                    'generations': 2, 'tokens_per_generation': native.N_CALIB,
                    'seeds': [3, 4], 'result_file': f'run-{mib}-0.json'}
        (out / f'{args.phase}.json').write_text(json.dumps(selected, indent=2) + '\n')
        if args.phase == 'point-60':
            points = [previous, json.loads((out / 'point-30.json').read_text())['calibration'], measured]
            rates = [{'mib': r['mib'], 'tokens': r['tokens'], 'decode_tps': 1000 * r['tokens'] / r['ms']}
                     for r in points]
            recommendation = {'source': 'measured native calibration results, owner-limited three-point survey',
                              'native_six_point_recommendation': None, 'cpu_share': 0.0, 'points': rates,
                              'empirical_fastest_mib': max(rates, key=lambda row: row['decode_tps'])['mib'],
                              'limitations': 'First point generates 2048 tokens per request, later points 512. '
                                             'Three zero-share points do not fit the upstream six-run CPU-share model.'}
            (out / 'selection.json').write_text(json.dumps(recommendation, indent=2) + '\n')
        return

    native.run_server = run_server
    try:
        native.tune(command, str(out), MAX_MIB)
    except FirstCalibrationComplete:
        print(f'First calibration complete. Review {approval_boundary} before continuing.', flush=True)


if __name__ == '__main__':
    main()
