#!/usr/bin/env python3
"""Run one capped DeepSeek functional probe or one quiet early comparison window."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from run_p4_window import accepted_result, boundary_resources

ROOT = Path.home() / 'predemo-spark'
HERE = Path(__file__).resolve().parent
PORT = 8082
GATES = ('LLAMA_EVENT_REC', 'LLAMA_EVENT_REC_MIB', 'LLAMA_EXPERT_CACHE', 'LLAMA_EXPERT_CACHE_MIB',
         'LLAMA_EXPERT_PREDICT', 'LLAMA_BATCH_LAYOUT', 'LLAMA_PLACEMENT_PLAN',
         'LLAMA_EXPERT_CACHE_NATIVE_PROFILE', 'LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH')
ARMS = {'C1': 'observability_event_recorder', 'C2': 'weight_placement_planner', 'C3': 'expert_weight_cache',
        'C4': 'expert_demand_predictor', 'C5': 'batch_layout_mapper'}
def read(path):
    return json.loads(path.read_bytes())

def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cc', choices=ARMS)
    parser.add_argument('mode', choices=('stock', 'equivalent-stock', 'off', 'on'))
    parser.add_argument('window', choices=('functional', 'early'))
    parser.add_argument('scope', type=Path)
    parser.add_argument('--placement-policy', choices=('cpu_identity_smoke', 'heldout_layer27_policy'),
                        default='cpu_identity_smoke')
    args = parser.parse_args()
    if args.mode == 'equivalent-stock' and (args.cc != 'C2' or args.placement_policy != 'heldout_layer27_policy'):
        parser.error('The equivalent-placement stock control requires the layer 27 policy')
    scope = args.scope.resolve()
    if scope.exists() or scope.parent != ROOT / 'OPS/runs':
        parser.error('Choose a fresh directory immediately under OPS/runs')
    first = read(ROOT / 'OPS/runs/a-first-load-retry/start.json')
    product = next(p for p in read(ROOT / 'OPS/p3/native-star-build-products.json')['products']
                   if p['capsule'] == ARMS[args.cc])
    stock = args.mode in ('stock', 'equivalent-stock')
    binary = Path(first['command'][0] if stock else product['executable']['path'])
    sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    if sha != (first['binary_sha256'] if stock else product['executable']['sha256']):
        raise RuntimeError('Engine executable digest differs from the build receipt')
    flags = list(first['command'][1:]) + ['-lv', '4']
    env = {k: v for k, v in os.environ.items() if k not in GATES and not k.startswith('LLAMA_ARG_')}
    env['LD_LIBRARY_PATH'] = str(binary.parent)
    on = args.mode == 'on'
    if args.cc == 'C1' and on:
        env['LLAMA_EVENT_REC'] = str(scope / 'events.jsonl')
    if args.cc == 'C2':
        controls = read(ROOT / 'OPS/p3/placement-v1-matched-controls.json')
        if controls['source_commit'] != product['source_commit']:
            raise RuntimeError('Placement controls belong to a different build')
        profile = controls[args.placement_policy]
        if on:
            arm_flags = profile['gate_on_argv']
            plan = Path(arm_flags[arm_flags.index('--placement-plan') + 1])
            if hashlib.sha256(plan.read_bytes()).hexdigest() != profile['plan_sha256']:
                raise RuntimeError('Placement plan digest mismatch')
            env.update(profile['gate_on_env'])
        elif args.placement_policy == 'cpu_identity_smoke':
            arm_flags = profile['stock_and_gate_unset_argv']
        elif args.mode == 'stock':
            arm_flags = profile['all_cpu_stock_argv']
        else:
            arm_flags = profile['equivalent_stock_and_candidate_off_argv']
        flags = ['-m', first['command'][2], '--host', '127.0.0.1', '--port', str(PORT),
                 *profile['common_argv'], *arm_flags]
    if args.cc == 'C3' and on:
        env.update(LLAMA_EXPERT_CACHE='1', LLAMA_EXPERT_CACHE_MIB='64')
    if args.cc in ('C4', 'C5'):
        flags += ['-np', '1', '-c', '4096']
    if args.cc == 'C4' and on:
        env['LLAMA_EXPERT_PREDICT'] = '1'
    if args.cc == 'C5':
        flags += ['--ctx-checkpoints', '0', '-b', '2047', '-ub', '512']
        if on:
            env['LLAMA_BATCH_LAYOUT'] = '1'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', PORT))
    early = args.window == 'early'
    if early:
        reset_dir = ROOT / 'OPS/p3/early-preflights'
        reset_dir.mkdir(exist_ok=True)
        subprocess.run([sys.executable, str(HERE / 'source_residency.py'), 'cold-start',
                        '--regions', str(ROOT / 'OPS/p4/source-regions.json'),
                        '--out', str(reset_dir / (scope.name + '-source.json'))], check=True)
        preflight = subprocess.check_output([str(ROOT / 'bin/quiet')])
        (reset_dir / (scope.name + '-quiet.json')).write_bytes(preflight)
    label = f'{args.cc}-{args.mode}-{args.window}'
    launched = time.monotonic()
    server = subprocess.Popen([str(ROOT / 'bin/capped'), '--arm', label, '--graceful-interrupt',
                               '--result-dir', str(scope), '--', str(binary), *flags], env=env)
    try:
        while time.monotonic() - launched < 900:
            if server.poll() is not None:
                raise RuntimeError('Capped server exited during load')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2) as response:
                    if json.load(response).get('status') == 'ok':
                        break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        else:
            raise TimeoutError('Capped server health deadline exceeded')
        save(scope / 'load-ready.json', {'ready_at': datetime.now(timezone.utc).isoformat(),
                                         'health_elapsed_s': time.monotonic() - launched,
                                         'source_commit': '9048bad8d6e3a0f9f1726e238e451181c7e02613' if stock else product['source_commit'],
                                         'native_build_receipt': None if stock else product['receipt_artifact_id']})
        receipt = read(scope / 'scope.json')
        hashes = {}
        prompts = HERE / 'prompts'
        manifest = read(prompts / 'MANIFEST.json')
        approved = {p['target_tokens_including_template']: p['prompt_sha256'] for p in manifest['prompts']}
        for repeat in ([0, 1] if early else [0]):
            for size in (512, 2048):
                target = scope / f'rep-{repeat}-{size}'
                if early:
                    boundary_resources(scope / f'{target.name}-before.json', Path(receipt['cgroup']), receipt['pid'])
                bench = [sys.executable, str(HERE / 'bench_http.py'), '--url', f'http://127.0.0.1:{PORT}',
                         '--arm', label, '--prompt', str(prompts / f'{size}.txt'), '--prompt-tokens', str(size),
                         '--out', str(target), '--repeat', str(repeat)]
                if repeat == 0:
                    bench.append('--discard')
                subprocess.run(bench, check=True)
                accepted_result(target / 'result.json', size, repeat, label, approved[size], hashes)
                if early:
                    boundary_resources(scope / f'{target.name}-after.json', Path(receipt['cgroup']), receipt['pid'])
    finally:
        if server.poll() is None:
            server.send_signal(signal.SIGINT)
        server.wait()
    result = read(scope / 'result.json')
    if result['returncode'] or result['reason'] or not result['scope_verified']:
        raise RuntimeError('Capped server did not exit cleanly')
    save(scope / 'probe.json', {'cc': args.cc, 'mode': args.mode, 'window': args.window,
                                'greedy_hashes': hashes, 'result_dir': str(scope)})

if __name__ == '__main__':
    main()
