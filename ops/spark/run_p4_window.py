#!/usr/bin/env python3
"""Measure one ready, capped Spark server in the mirrored P4 protocol."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

from source_residency import snapshot

HERE = Path(__file__).resolve().parent
PROMPTS = (512, 2048)
GIB = 1024**3


def json_read(path):
    return json.loads(path.read_bytes())


def json_write(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_scope(scope, receipt, start, arm, port):
    fields = {'memory.max': str(100 * GIB), 'memory.swap.max': '0', 'memory.oom.group': '1',
              'cpu.max': '800000 100000', 'sched_affinity': list(range(8))}
    if not (scope / 'monitor.ready').is_file() or (scope / 'result.json').exists():
        raise ValueError('Server scope is not active with its watchdog handshake')
    if any(receipt['actual'].get(name) != value for name, value in fields.items()):
        raise ValueError('Kernel control receipt does not match the production scope')
    cgroup = Path(receipt['cgroup']).resolve(strict=True)
    if not cgroup.is_relative_to('/sys/fs/cgroup') or not cgroup.name.startswith('spark-capped-'):
        raise ValueError('Invalid capped scope cgroup')
    command = start['command']
    if start['arm'] != arm or '--port' not in command or command[command.index('--port') + 1] != str(port):
        raise ValueError('Arm or loopback port differs from the capped start receipt')
    return cgroup


def boundary_resources(out, cgroup, scope_pid):
    pids = (cgroup / 'cgroup.procs').read_text().split()
    if str(scope_pid) not in pids:
        raise ValueError('The capped server process has exited')
    checks = [str(HERE / 'bin/quiet')]
    for pid in pids:
        checks.extend(('--allow-model-pid', pid))
    probe = subprocess.run(checks, capture_output=True, text=True)
    quiet = json.loads(probe.stdout)
    events = dict(line.split() for line in (cgroup / 'memory.events').read_text().splitlines())
    values = dict(quiet, observed_utc=datetime.now(timezone.utc).isoformat(), scope_pids=pids,
                  cgroup_memory_current_bytes=int((cgroup / 'memory.current').read_text()), memory_events=events)
    json_write(out, values)
    blocked = ('build_processes', 'model_processes', 'factory_controllers', 'test_processes')
    if probe.returncode not in (0, 1) or any(quiet[key] for key in blocked):
        raise ValueError(f'Competing process detected. See {out}')
    if any(int(events.get(key, 0)) for key in ('oom', 'oom_kill')) or quiet['mem_available_gib'] < 8:
        raise ValueError(f'Unexpected memory event. See {out}')


def accepted_result(path, size, repeat, arm, approved, hash_pairs):
    result = json_read(path)
    ttft = result.get('ttft_s')
    usage = result.get('usage', {})
    if (result['arm'] != arm or result['prompt_tokens'] != size or result['repeat'] != repeat
            or result['discard'] != (repeat == 0) or not result['ok']
            or type(ttft) not in (int, float) or not math.isfinite(ttft) or ttft <= 0
            or result.get('prompt_sha256') != approved or usage.get('prompt_tokens') != size
            or usage.get('completion_tokens') != 32 or usage.get('prompt_tokens_details', {}).get('cached_tokens') != 0
            or result.get('timings', {}).get('cache_n') != 0):
        raise ValueError(f'Invalid TTFT, response token count, cache reuse or prompt digest. See {path}')
    pair = [result['output_sha256'], result['reasoning_sha256']]
    if not all(re.fullmatch(r'[0-9a-f]{64}', digest) for digest in pair):
        raise ValueError(f'Missing greedy output hashes. See {path}')
    expected = hash_pairs.setdefault(str(size), pair)
    if pair != expected:
        raise ValueError(f'Greedy output changed for the fixed {size}-token prompt. See {path}')


def run_window(args):
    scope = args.scope.resolve(strict=True)
    start = json_read(scope / 'start.json')
    receipt = json_read(scope / 'scope.json')
    cgroup = check_scope(scope, receipt, start, args.arm, args.port)
    quiet_bytes = args.quiet_preflight.read_bytes()
    if json.loads(quiet_bytes)['quiet'] is not True or (
            args.quiet_preflight.stat().st_mtime > datetime.fromisoformat(start['start']).timestamp()):
        raise ValueError('Quiet preflight must pass before launch')
    prompts = HERE / 'prompts'
    manifest_bytes = (prompts / 'MANIFEST.json').read_bytes()
    approved = {p['target_tokens_including_template']: p['prompt_sha256'] for p in json.loads(manifest_bytes)['prompts']}
    for size in PROMPTS:
        if sha((prompts / f'{size}.txt').read_bytes()) != approved[size]:
            raise ValueError(f'Fixed {size}-token prompt content changed')
    region_bytes = args.regions.read_bytes()
    regions = json.loads(region_bytes)
    record = dict(schema='spark-p4-window/2', status='running', arm=args.arm, view=args.view, launch_pass=args.launch_pass,
                  scope=str(scope), binary_sha256=start['binary_sha256'], regions_sha256=sha(region_bytes),
                  prompts_sha256=sha(manifest_bytes), quiet_preflight_sha256=sha(quiet_bytes),
                  pages_per_sample=args.pages_per_sample, seed=args.seed, requests=[], greedy_hashes={})
    if args.launch_pass == 2:
        if not args.first_window:
            raise ValueError('Second-pass launches need that arm’s completed --first-window receipt')
        previous = json_read(args.first_window)
        matching = ('schema', 'arm', 'view', 'binary_sha256', 'regions_sha256', 'prompts_sha256', 'pages_per_sample', 'seed')
        if (previous['status'] != 'complete' or previous['launch_pass'] != 1
                or previous['scope'] == str(scope) or any(previous[k] != record[k] for k in matching)):
            raise ValueError('First-pass receipt does not match this fresh launch and fixed workload')
        record['greedy_hashes'] = previous['greedy_hashes']
        record['first_window_sha256'] = sha(args.first_window.read_bytes())
    elif args.first_window:
        raise ValueError('--first-window is only accepted for pass 2')

    out = scope / 'p4-window'
    out.mkdir(exist_ok=False)
    status = out / 'window.json'
    (out / 'quiet-prelaunch.json').write_bytes(quiet_bytes)
    if os.getenv('SPARK_EXPERT_SAMPLE_DETAIL') == '1':
        # Capture file-backed expert state after load and before the first prompt changes it.
        postload = snapshot(regions, args.view, args.pages_per_sample, args.seed, scope / 'scope.json')
        postload['regions_sha256'] = record['regions_sha256']
        json_write(out / 'load-ready-residency.json', postload)
        record['load_ready_residency'] = 'load-ready-residency.json'
    json_write(status, record)
    plan = [(f'warmup-{round_number}-{size}', 0, size) for round_number in (1, 2, 3)
            for size in (PROMPTS[::-1] if round_number == 3 else PROMPTS)]
    repeats = range(1, 6) if args.launch_pass == 1 else range(6, 11)
    for repeat in repeats:
        plan.extend((f'repeat-{repeat}-{size}', repeat, size) for size in (PROMPTS if (repeat - 1) % 5 in (0, 2, 4) else PROMPTS[::-1]))
    try:
        for name, repeat, size in plan:
            directory = out / name
            item = dict(repeat=repeat, prompt_tokens=size, discarded=repeat == 0, status='running')
            record['requests'].append(item)
            json_write(status, record)
            before = out / f'{name}-before-resources.json'
            boundary_resources(before, cgroup, receipt['pid'])
            if repeat:
                residency = snapshot(regions, args.view, args.pages_per_sample, args.seed, scope / 'scope.json')
                residency['regions_sha256'] = record['regions_sha256']
                residency_path = out / f'{name}-before-residency.json'
                json_write(residency_path, residency)
                item['residency'] = residency_path.name
            command = [sys.executable, str(HERE / 'bench_http.py'), '--url', f'http://127.0.0.1:{args.port}',
                       '--arm', args.arm, '--prompt', str(prompts / f'{size}.txt'), '--prompt-tokens', str(size),
                       '--repeat', str(repeat), '--out', str(directory)]
            if repeat == 0:
                command.append('--discard')
            with (out / f'{name}-client.log').open('wb') as log:
                finished = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
            after = out / f'{name}-after-resources.json'
            boundary_resources(after, cgroup, receipt['pid'])
            if finished.returncode:
                raise ValueError(f'Client failed with exit {finished.returncode}. See {name}-client.log')
            path = directory / 'result.json'
            accepted_result(path, size, repeat, args.arm, approved[size], record['greedy_hashes'])
            item.update(status='complete', result=str(path.relative_to(out)), sha256=sha(path.read_bytes()),
                        before_resources=before.name, after_resources=after.name)
            if repeat == 0 and name in ('warmup-1-2048', 'warmup-2-2048', 'warmup-3-512'):
                residency = snapshot(regions, args.view, args.pages_per_sample, args.seed, scope / 'scope.json')
                residency['regions_sha256'] = record['regions_sha256']
                residency_path = out / f'{name}-after-residency.json'
                json_write(residency_path, residency)
                item['residency'] = residency_path.name
            json_write(status, record)
    except (Exception, KeyboardInterrupt) as exc:
        item.update(status='failed', error=str(exc))
        record.update(status='failed', error=str(exc))
        json_write(status, record)
        raise
    record['status'] = 'complete'
    json_write(status, record)
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', required=True, type=Path, help='Existing ready bin/capped result directory')
    parser.add_argument('--arm', required=True, help='Arm as named in the capped start receipt')
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--launch-pass', required=True, type=int, choices=(1, 2))
    parser.add_argument('--view', required=True, choices=('llama', 'strata'))
    parser.add_argument('--regions', required=True, type=Path)
    parser.add_argument('--quiet-preflight', required=True, type=Path)
    parser.add_argument('--pages-per-sample', type=int, default=4096)
    parser.add_argument('--seed', type=int, default=20261120)
    parser.add_argument('--first-window', type=Path, help='The arm’s completed pass-1 p4-window/window.json')
    print(run_window(parser.parse_args()))
