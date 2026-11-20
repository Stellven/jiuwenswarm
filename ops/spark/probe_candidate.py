#!/usr/bin/env python3
"""Run one capped DeepSeek functional probe or one quiet early comparison window."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from p4_launch import (REGIONS, add_window_arguments, condition_source_and_check_quiet, request_window,
                       validate_window_arguments, verify_prior_profile)
from run_p4_window import accepted_result, boundary_resources
from source_residency import snapshot
from steady_requests import run as steady_requests

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


def combined_profile(first, product, scope, on):
    controls_path = ROOT / 'OPS/p3/combined-d-matched-controls.json'
    controls = read(controls_path)
    if controls['parent_head'] != product['source_commit']:
        raise RuntimeError('Combined controls belong to a different source revision')
    matched = read(ROOT / 'OPS/p3/placement-v1-matched-controls.json')['cpu_identity_smoke']
    field = 'all_gates_enabled_flags' if on else 'stock_and_all_gates_unset_flags'
    flags = controls[field]
    if flags != matched['gate_on_argv' if on else 'stock_and_gate_unset_argv']:
        raise RuntimeError('Combined controls differ from the matched CPU identity policy')
    settings = {}
    if on:
        plan = Path(flags[flags.index('--placement-plan') + 1])
        if hashlib.sha256(plan.read_bytes()).hexdigest() != matched['plan_sha256']:
            raise RuntimeError('Combined CPU identity plan digest mismatch')
        settings = dict(controls['all_gates_on_env'], LLAMA_EVENT_REC=str(scope / 'events.jsonl'))
        if set(settings) != set(GATES) - {'LLAMA_EXPERT_CACHE_NATIVE_PROFILE', 'LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH'}:
            raise RuntimeError('Combined gate set differs from the five verified components')
    return (['-m', first['command'][2], '--host', '127.0.0.1', '--port', str(PORT),
             *controls['common_flags'], *flags], settings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cc', choices=(*ARMS, 'D'))
    parser.add_argument('mode', choices=('stock', 'strict-stock', 'equivalent-stock', 'off', 'on'))
    parser.add_argument('window', choices=('functional', 'early', 'speed', 'p4'))
    parser.add_argument('scope', type=Path)
    parser.add_argument('--products', type=Path, default=ROOT / 'OPS/p3/native-star-build-products.json',
                        help='Frozen native product/receipt index for this iteration')
    parser.add_argument('--placement-policy', choices=('cpu_identity_smoke', 'heldout_layer27_policy'),
                        default='cpu_identity_smoke')
    parser.add_argument('--native-mib', type=int, choices=(15360, 30720, 46080, 61440),
                        help='Fixed matched cache budget in MiB for the candidate experiment')
    add_window_arguments(parser)
    args = parser.parse_args()
    p4 = args.window == 'p4'
    validate_window_arguments(parser, args, p4, 'llama')
    combined = args.cc == 'D'
    if combined and (args.window != 'functional' or args.mode not in ('stock', 'off', 'on')):
        parser.error('Combined D supports matched stock, off and on functional smoke probes')
    speed = args.window == 'speed'
    native_cache = bool(args.native_mib)
    if ((speed and not native_cache) or (native_cache and
           (args.window not in ('speed', 'p4') or args.cc != 'C3' or args.mode == 'strict-stock'))):
        parser.error('Native-cache speed cells require C3, a matched stock/off/on mode and a fixed cache budget')
    if args.mode == 'equivalent-stock' and not native_cache and (args.cc != 'C2' or args.placement_policy != 'heldout_layer27_policy'):
        parser.error('The equivalent-placement stock control requires the layer 27 policy')
    scope = args.scope.resolve()
    if scope.exists() or scope.parent != ROOT / 'OPS/runs':
        parser.error('Choose a fresh directory immediately under OPS/runs')
    first = read(ROOT / 'OPS/runs/a-first-load-retry/start.json')
    product_inventory = read(args.products)
    if product_inventory['schema'] != 'spark-native-star-build-products/1':
        raise RuntimeError('Expected a frozen native build product manifest')
    capsule = 'combined_d' if combined else ARMS[args.cc]
    product = next(p for p in product_inventory['products'] if p['capsule'] == capsule)
    stock = args.mode in ('stock', 'strict-stock', 'equivalent-stock')
    binary = Path(first['command'][0] if stock else product['executable']['path'])
    sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    if sha != (first['binary_sha256'] if stock else product['executable']['sha256']):
        raise RuntimeError('Engine executable digest differs from the build receipt')
    if not stock and 'retained_elf_sha256_by_filename' in product:
        if str(binary.parent) != product['retain_library_dir']:
            raise RuntimeError('Engine library directory differs from the build receipt')
        for name, expected in product['retained_elf_sha256_by_filename'].items():
            with (binary.parent / name).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise RuntimeError(f'Retained engine library digest differs for {name}')
    flags = list(first['command'][1:]) + ['-lv', '4']
    env = {k: v for k, v in os.environ.items() if k not in GATES and not k.startswith('LLAMA_ARG_')}
    env['LD_LIBRARY_PATH'] = str(binary.parent)
    on = args.mode == 'on'
    if combined:
        flags, settings = combined_profile(first, product, scope, on)
        env.update(settings)
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
    if native_cache:
        if args.mode != 'stock':
            flags += ['--moe-cache-mib', str(args.native_mib), '--moe-cache-cpu-share', '0']
        if on:
            profile = ROOT / 'OPS/p3/frozen-strata-top192-ranked-pool.json'
            profile_hash = hashlib.sha256(profile.read_bytes()).hexdigest()
            if profile_hash != 'dd4861349970a46e9e23ebe58c39b5afb91bd1d9e4c28e960026fc375b1034da':
                raise RuntimeError('Frozen nomination profile digest mismatch')
            env.update(LLAMA_EXPERT_CACHE_NATIVE_PROFILE='1', LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH=str(profile))
    elif args.cc == 'C3' and on:
        env.update(LLAMA_EXPERT_CACHE='1', LLAMA_EXPERT_CACHE_MIB='64')
    if args.cc in ('C4', 'C5'):
        flags += ['-np', '1', '-c', '4096']
    if args.cc == 'C4' and on:
        env['LLAMA_EXPERT_PREDICT'] = '1'
    if args.cc == 'C5':
        flags += ['--ctx-checkpoints', '0', '-b', '2047', '-ub', '512']
        if on:
            env['LLAMA_BATCH_LAYOUT'] = '1'
    if args.mode == 'strict-stock':
        flags = list(first['command'][1:])
    elif (args.window == 'early' or (p4 and not native_cache)) and '-lv' in flags:
        # All timed cells use documented default verbosity. Diagnostic markers live in gate-on probes.
        index = flags.index('-lv')
        del flags[index:index + 2]
    products_sha = hashlib.sha256(args.products.read_bytes()).hexdigest()
    if p4:
        settings = {key: env[key] for key in (*GATES, 'LD_LIBRARY_PATH', 'GGML_CUDA_REGISTER_HOST', 'LLAMA_MOE_CACHE_TRACE',
                                               'GGML_OP_OFFLOAD_MIN_BATCH') if key in env}
        if 'LLAMA_EVENT_REC' in settings:
            settings['LLAMA_EVENT_REC'] = Path(settings['LLAMA_EVENT_REC']).name
        launch_profile = dict(command=[str(binary), *flags], binary_sha256=sha,
                              build_receipt=None if stock else product['receipt_artifact_id'],
                              environment=settings, products_manifest_sha256=products_sha)
        verify_prior_profile(args, launch_profile)
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', PORT))
    early = args.window == 'early'
    if early:
        regions = read(REGIONS)
    if early or speed or p4:
        quiet_preflight = condition_source_and_check_quiet(scope)
    label = f'{args.cc}-{args.mode}-{args.window}'
    if args.mode == 'strict-stock':
        label = f'A-{args.cc}-strict-{args.window}'
    elif args.mode == 'stock':
        label = f'A-matched-{args.cc}-{args.window}'
    if speed:
        arm = {'stock': 'A-matched', 'equivalent-stock': 'Aplus', 'off': 'C3-native-off', 'on': 'C3-profile-on'}[args.mode]
        label = f'{arm}-speed-{args.native_mib}MiB'
    if p4:
        label = args.arm
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
                                         'products_manifest': str(args.products.resolve()),
                                         'products_manifest_sha256': products_sha,
                                         'native_build_receipt': None if stock else product['receipt_artifact_id']})
        if native_cache and on:
            log = (scope / 'stderr.log').read_text(errors='replace')
            active = re.search(r'expert_weight_cache_native_profile: active seeds=(\d+) initial_h2d_bytes=(\d+) init_us=(\d+) charged_bound=(\d+)', log)
            if not active or min(map(int, active.groups()[:2])) <= 0 or int(active[4]) > args.native_mib * 1024**2:
                raise RuntimeError('Profile did not engage within its byte budget; see the retained engine log')
            save(scope / 'profile-activation.json', {'sha256': profile_hash, 'marker': active[0]})
        receipt = read(scope / 'scope.json')
        hashes = {}
        prompts = HERE / 'prompts'
        manifest = read(prompts / 'MANIFEST.json')
        approved = {p['target_tokens_including_template']: p['prompt_sha256'] for p in manifest['prompts']}
        if speed:
            hashes = steady_requests(scope, label, PORT, 'llama')
        if p4:
            save(scope / 'p4-launch-profile.json', launch_profile)
            hashes = request_window(args, scope, PORT, 'llama', quiet_preflight)
        repeats = [] if speed or p4 else ([0, 1] if early else [0])
        sizes = (512,) if combined else (512, 2048)
        for repeat in repeats:
            for size in sizes:
                target = scope / f'rep-{repeat}-{size}'
                if early:
                    boundary_resources(scope / f'{target.name}-before.json', Path(receipt['cgroup']), receipt['pid'])
                if early and repeat:
                    save(scope / f'{target.name}-residency.json',
                         snapshot(regions, 'llama', 4096, 20261120, scope / 'scope.json'))
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
