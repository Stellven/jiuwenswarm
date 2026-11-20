#!/usr/bin/env python3
"""Spark platform metadata adapter around byte-pinned Satay scorer v4.

Acceptance predicates are imported unchanged. See OPS/scorer-portability for the
proven frozen-CLI failure and the explicit platform amendment/override manifest.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

PIN = '9048bad8d6e3a0f9f1726e238e451181c7e02613'
HASHES = {'scorer.py': '2632d6e0da922e54369105266ded5eb903012fc5c5276c615ea7fdf580032cf9',
          'scorer_runtime.py': '67f48d8664513da1920b3697206181fa66e991918f1be693724b11edf8760439'}
FIXTURE_HASH = '087517eafc83e81a7b5ae440be1145fe96ffcd954c93b85d703c80f4f3399de8'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def capped():
    relative = next(line.split('::', 1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    cg = Path('/sys/fs/cgroup') / relative.lstrip('/')
    checks = {'memory.max': str(100 * 1024**3), 'memory.swap.max': '0', 'memory.oom.group': '1'}
    if 'spark-capped-' not in str(cg) or any((cg / key).read_text().strip() != value for key, value in checks.items()):
        raise SystemExit('Runtime/scoring requires bin/capped with the production 100 GiB controls')


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def prepare(base, stage):
    frozen = base / 'inputs/ab'
    for filename, expected in HASHES.items():
        if sha(frozen / filename) != expected:
            raise SystemExit('Frozen scorer digest mismatch: ' + filename)
    stock = base / 'llama.cpp-stock'
    commit = subprocess.check_output(['git', '-C', str(stock), 'rev-parse', 'HEAD'], text=True).strip()
    clean = not subprocess.check_output(['git', '-C', str(stock), 'status', '--porcelain=v1', '--untracked-files=all', '--ignored'])
    if commit != PIN or not clean:
        raise SystemExit('Spark stock source must remain pristine at the frozen pin')
    binary = base / 'build-stock-cuda121/bin/llama-server'
    cache = base / 'build-stock-cuda121/CMakeCache.txt'
    values = {}
    for line in cache.read_text().splitlines():
        if line and not line.startswith(('#', '//')) and ':' in line and '=' in line:
            key, value = line.split('=', 1)
            values[key.split(':', 1)[0]] = value
    if values.get('CMAKE_CUDA_ARCHITECTURES') != '121' or values.get('GGML_CUDA') != 'ON':
        raise SystemExit('Expected the existing sm_121 stock CUDA build')
    flags = ['-S', str(stock), '-B', str(base / 'build-stock-cuda121'), '-G', values['CMAKE_GENERATOR']]
    for key in ('CMAKE_MAKE_PROGRAM', 'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_CUDA_COMPILER',
                'CMAKE_CUDA_HOST_COMPILER', 'GGML_CUDA', 'CMAKE_CUDA_ARCHITECTURES', 'CMAKE_BUILD_TYPE',
                'GGML_NATIVE', 'GGML_CUDA_FA_ALL_QUANTS', 'LLAMA_CURL'):
        if key in values and values[key] and not values[key].endswith('-NOTFOUND'):
            flags.append('-D' + key + '=' + values[key])
    cmake = shutil.which('cmake')
    if not cmake:
        raise SystemExit('cmake is unavailable')
    receipt = dict(status='passed', source_verified=True, source_commit=commit, source_path=str(stock),
                   configure_flags=flags, tools_and_compilers={'cmake': {'path': cmake}},
                   binaries={'llama-server': {'path': str(binary), 'sha256': sha(binary)}},
                   provenance='Existing Spark build cache/binary plus pristine source inspection; not a new build',
                   cache_sha256=sha(cache))
    stage.mkdir(parents=True, exist_ok=True)
    receipt_path = stage / 'spark-stock-receipt.json'
    if receipt_path.exists() and json.loads(receipt_path.read_text()) != receipt:
        raise SystemExit('Existing Spark receipt changed; use a new stage root')
    write(receipt_path, receipt)
    fixture = base / 'models/campaign/gguf/granite-3.1-1b-a400m-instruct-Q8_0.gguf'
    overrides = dict(ROOT=str(stage), STOCK=str(stock), RECEIPT=str(receipt_path),
                     RECEIPT_SHA256=sha(receipt_path), REFERENCE=str(stage / 'reference.json'),
                     MODEL=str(fixture), STOCK_BIN=str(binary))
    manifest = dict(schema='spark.scorer-platform-adapter/1', frozen_files=HASHES, stock_commit=PIN,
                    overrides=overrides, adapter_sha256=sha(__file__), fixture_expected_sha256=FIXTURE_HASH,
                    fixture_satay_identity='unverified: retained historical full model digest unavailable',
                    stage_predicates='Unchanged frozen v4 functions; only platform constants and server ledger instrumentation supplied',
                    build_platform='Existing Spark cache recipe, sm_121; original three-job limit unchanged')
    write(stage / 'platform-overrides.json', manifest)
    command = [sys.executable, str(Path(__file__).resolve()), '--base', str(base), '--stage-root', str(stage), 'run']
    shim = stage / 'run_checks.sh'
    shim.write_text('#!/bin/sh\nexec ' + shlex.join(command) + ' "$@"\n')
    shim.chmod(0o755)
    return frozen, receipt_path, fixture, overrides


def install_ledger(runtime, base):
    original = runtime.server
    @contextmanager
    def recorded(binary, directory, port, args, gate=None, cache=False):
        row = dict(utc=utc(), arm='fixture-scorer-v4', command=[str(binary), '-m', str(runtime.MODEL),
                   '--host', '127.0.0.1', '--port', str(port), *runtime.BASE_ARGS,
                   '--cache-prompt' if cache else '--no-cache-prompt', *args],
                   binary_sha256=sha(binary), result_path=str(directory), gate=dict([gate]) if gate else {},
                   model_sha256=FIXTURE_HASH)
        def append(value):
            with (base / 'OPS/LEDGER.jsonl').open('a') as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                stream.write(json.dumps(dict(row, **value)) + '\n')
        append(dict(event='start'))
        started = time.monotonic()
        error = None
        try:
            with original(binary, directory, port, args, gate=gate, cache=cache) as result:
                yield result
        except BaseException as exc:
            error = type(exc).__name__ + ': ' + str(exc)
            raise
        finally:
            append(dict(event='stop', utc_stop=utc(), wall_seconds=time.monotonic() - started,
                        outcome='failed' if error else 'completed', error=error))
    runtime.server = recorded


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    p.add_argument('--stage-root', type=Path)
    p.add_argument('action', choices=['prepare', 'score', 'run', 'reference'])
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    args = p.parse_args()
    base = args.base.resolve()
    stage = (args.stage_root or base / 'scorer-spark-v4').resolve()
    if not stage.is_relative_to(base) or stage.is_relative_to((base / 'inputs').resolve()):
        raise SystemExit('Stage root must be inside predemo-spark and outside frozen inputs')
    if args.action != 'prepare' and not (args.action == 'score' and '--scope-only' in args.arguments):
        capped()
    frozen, receipt_path, fixture, overrides = prepare(base, stage)
    if args.action == 'prepare':
        print(json.dumps(overrides, indent=2))
        return 0
    scorer = import_file('scorer', frozen / 'scorer.py')
    for name in ('ROOT', 'STOCK', 'RECEIPT', 'REFERENCE'):
        setattr(scorer, name, Path(overrides[name]))
    scorer.RECEIPT_SHA256 = overrides['RECEIPT_SHA256']
    runtime = import_file('scorer_runtime', frozen / 'scorer_runtime.py')
    runtime.MODEL = fixture
    runtime.STOCK_BIN = Path(overrides['STOCK_BIN'])
    if args.action != 'score' or '--scope-only' not in args.arguments:
        if not fixture.is_file() or fixture.stat().st_size != 1422239456 or sha(fixture) != FIXTURE_HASH:
            raise SystemExit('Published Granite fixture file failed verification')
    install_ledger(runtime, base)
    sys.argv = [str(Path(__file__).resolve()), args.action, *args.arguments]
    return scorer.main()


if __name__ == '__main__':
    raise SystemExit(main())
