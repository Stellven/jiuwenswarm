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

from p4_launch import (REGIONS, add_window_arguments, condition_source_and_check_quiet, profile_bytes, request_window,
                       validate_window_arguments, verify_prior_profile)
from run_p4_window import accepted_result, boundary_resources
from source_residency import snapshot
from steady_requests import run as steady_requests

ROOT = Path.home() / 'predemo-spark'
HERE = Path(__file__).resolve().parent
PORT = 8082
GATES = ('LLAMA_EVENT_REC', 'LLAMA_EVENT_REC_MIB', 'LLAMA_EXPERT_CACHE', 'LLAMA_EXPERT_CACHE_MIB',
         'LLAMA_EXPERT_PREDICT', 'LLAMA_BATCH_LAYOUT', 'LLAMA_PLACEMENT_PLAN',
         'LLAMA_EXPERT_CACHE_NATIVE_PROFILE', 'LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH', 'LLAMA_EXPERT_CACHE_DIRECT_SEED')
C3_PROFILE_GATES = {'LLAMA_EXPERT_CACHE_NATIVE_PROFILE', 'LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH',
                    'LLAMA_EXPERT_CACHE_DIRECT_SEED'}
ARMS = {'C1': 'observability_event_recorder', 'C2': 'weight_placement_planner', 'C3': 'expert_weight_cache',
        'C4': 'expert_demand_predictor', 'C5': 'batch_layout_mapper'}
C2_POOLED_SOURCE = '24dbb8309e604de8d8c97e623b78d49d0f14a736'
PLACEMENT_ROW = re.compile(r'weight_placement_planner: assignment name="(blk\.\d+\.ffn_(?:gate|up|down)_exps\.weight)" '
                           r'planned=(\w+) actual=(\w+) bytes=(\d+)')
def read(path):
    return json.loads(path.read_bytes())

def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def pooled_placement_profile(first, product):
    if product['source_commit'] != C2_POOLED_SOURCE:
        raise RuntimeError('Pooled placement requires the verified tier03 source with its compatible manual path')
    control = read(ROOT / 'OPS/p3/placement-v1-matched-controls.json')['heldout_layer27_policy']
    placement = control['gate_on_argv']
    plan = Path(placement[placement.index('--placement-plan') + 1])
    if hashlib.sha256(plan.read_bytes()).hexdigest() != control['plan_sha256'] or read(plan)['version'] != 1:
        raise RuntimeError('Pooled C2 requires the pinned version-1 layer-27 placement plan')
    common = list(first['command'][1:])
    common.remove('--cpu-moe')
    return [*common, '-lv', '4', *placement], control


def pooled_placement_readback(log, control):
    rows = PLACEMENT_ROW.findall(log)
    actual = {name: (planned, buffer, int(size)) for name, planned, buffer, size in rows}
    expected = {f'blk.{layer}.ffn_{kind}_exps.weight' for layer in range(40) for kind in ('gate', 'up', 'down')}
    requested = {item['name']: item['bytes'] for item in control['selected']}
    stock = expected - requested.keys()
    match = re.findall(r'CUDA0 MoE cache size = ([\d.]+) MiB for ([\d.]+) MiB of host experts, ([\d.]+)% of the misses on the CPU', log)
    active = re.findall(r'weight_placement_planner: active cap_bytes=\d+ peak_bytes=\d+', log)
    if (len(active) != 1 or len(rows) != len(actual) or set(actual) != expected or
            any(actual[name] != ('CUDA0', 'CUDA0', size) for name, size in requested.items()) or
            any(actual[name][:2] != ('stock', 'CPU_Mapped') for name in stock) or len(match) != 1):
        raise RuntimeError('C2 activation, exact layer-27 CUDA weight or CPU fallback readback is missing')
    allocated, host, share = map(float, match[0])
    if not 0 < allocated <= 30720 or host <= 0 or share != 0:
        raise RuntimeError('C2 placement did not preserve the bounded native cache request')
    return dict(policy='manual-v1-layer27', source_commit=C2_POOLED_SOURCE, plan_sha256=control['plan_sha256'],
                active_marker=active[0], selected=[dict(name=name, planned=actual[name][0], buffer=actual[name][1],
                bytes=actual[name][2]) for name in sorted(requested)], cpu_mapped_expert_tensors=len(stock),
                native_bank=dict(requested_mib=30720, allocated_mib=allocated, host_experts_mib=host, cpu_share_pct=share))


def combined_profile(first, product, scope, on, pooled=False):
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
        if set(settings) != set(GATES) - C3_PROFILE_GATES:
            raise RuntimeError('Combined gate set differs from the five verified components')
    if pooled:
        # Keep the stock A+ scheduler and context. The disjoint override plus the
        # identity placement plan still puts every expert tensor on the CPU.
        base_flags = list(first['command'][1:])
        base_flags.remove('--cpu-moe')
        return [*base_flags, '-lv', '4', *flags], settings
    return (['-m', first['command'][2], '--host', '127.0.0.1', '--port', str(PORT),
             *controls['common_flags'], *flags], settings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cc', choices=(*ARMS, 'D'))
    parser.add_argument('mode', choices=('stock', 'strict-stock', 'equivalent-stock', 'off', 'on'))
    parser.add_argument('window', choices=('functional', 'early', 'speed', 'p4', 'pooled'))
    parser.add_argument('scope', type=Path)
    parser.add_argument('--products', type=Path, default=ROOT / 'OPS/p3/native-star-build-products.json',
                        help='Frozen native product/receipt index for this iteration')
    parser.add_argument('--placement-policy', choices=('cpu_identity_smoke', 'heldout_layer27_policy'),
                        default='cpu_identity_smoke')
    parser.add_argument('--native-mib', type=int, choices=(15360, 30720, 46080, 61440),
                        help='Fixed matched cache budget in MiB for the candidate experiment')
    add_window_arguments(parser)
    args = parser.parse_args()
    pooled = args.window == 'pooled'
    p4 = args.window in ('p4', 'pooled')
    validate_window_arguments(parser, args, p4, 'llama')
    if pooled and (args.mode != 'on' or args.launch_pass != 1 or args.first_window or args.native_mib != 30720):
        parser.error('A pooled screen is one gate-on candidate with a fixed 30720 MiB native bank')
    combined = args.cc == 'D'
    if combined and not pooled and (args.window != 'functional' or args.mode not in ('stock', 'off', 'on')):
        parser.error('Combined D supports matched stock, off and on functional smoke probes')
    speed = args.window == 'speed'
    native_cache = bool(args.native_mib)
    native_window = args.window in ('speed', 'p4', 'pooled') or (args.cc in ('C4', 'C5') and args.window == 'functional')
    pooled_placement = pooled and args.cc == 'C2'
    if native_cache and args.cc == 'C5' and (args.native_mib != 30720 or args.mode == 'stock'):
        parser.error('The mapper native comparison requires the 30 GiB bank on both arms')
    if ((speed and not native_cache) or (native_cache and
           (not native_window or (args.cc not in ('C3', 'C4', 'C5') and not (combined and pooled) and not pooled_placement) or args.mode == 'strict-stock'))):
        parser.error('Native-cache cells require a supported arm, a matched mode and a fixed cache budget')
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
        for name, expected in product.get('retained_library_symlinks', {}).items():
            if os.readlink(binary.parent / name) != expected:
                raise RuntimeError(f'Retained engine library alias differs for {name}')
    flags = list(first['command'][1:]) + ['-lv', '4']
    env = {k: v for k, v in os.environ.items() if k not in GATES and not k.startswith('LLAMA_ARG_')}
    env['LD_LIBRARY_PATH'] = str(binary.parent)
    on = args.mode == 'on'
    if combined:
        flags, settings = combined_profile(first, product, scope, on, pooled=pooled)
        env.update(settings)
    if args.cc == 'C1' and on:
        env['LLAMA_EVENT_REC'] = str(scope / 'events.jsonl')
    if pooled_placement:
        flags, placement_control = pooled_placement_profile(first, product)
        env.update(placement_control['gate_on_env'])
    elif args.cc == 'C2':
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
        if args.cc == 'C3' and not stock:
            default_profile = ROOT / 'OPS/p3/frozen-strata-top192-ranked-pool.json'
            contract = product.get('runtime_contract')
            if contract:
                gates = contract['gate_on_env' if on else 'gate_off_env']
                if not set(gates) <= C3_PROFILE_GATES:
                    raise RuntimeError('Native cache product requests unsupported gate settings')
                env.update(gates)
            elif on:
                env.update(LLAMA_EXPERT_CACHE_NATIVE_PROFILE='1', LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH=str(default_profile))
        if env.get('LLAMA_EXPERT_CACHE_NATIVE_PROFILE') == '1':
            profile = Path(env['LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH'])
            profile_hash = hashlib.sha256(profile.read_bytes()).hexdigest()
            if profile_hash != 'dd4861349970a46e9e23ebe58c39b5afb91bd1d9e4c28e960026fc375b1034da':
                raise RuntimeError('Frozen nomination profile digest mismatch')
    elif args.cc == 'C3' and on:
        env.update(LLAMA_EXPERT_CACHE='1', LLAMA_EXPERT_CACHE_MIB='64')
    if args.cc == 'C5' or (args.cc == 'C4' and not native_cache):
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
        if args.describe_profile:
            sys.stdout.buffer.write(profile_bytes(launch_profile))
            return
        verify_prior_profile(args, launch_profile)
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', PORT))
    early = args.window == 'early'
    if early:
        regions = read(REGIONS)
    if early or speed or p4:
        quiet_preflight = condition_source_and_check_quiet(scope, pooled_screen=pooled)
    label = f'{args.cc}-{args.mode}-{args.window}'
    if args.mode == 'strict-stock':
        label = f'A-{args.cc}-strict-{args.window}'
    elif args.mode == 'stock':
        label = f'A-matched-{args.cc}-{args.window}'
    if speed:
        arm = {'stock': 'A-matched', 'equivalent-stock': 'Aplus', 'off': f'{args.cc}-native-off',
               'on': 'C3-profile-on' if args.cc == 'C3' else f'{args.cc}-native-on'}[args.mode]
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
        if native_cache and env.get('LLAMA_EXPERT_CACHE_NATIVE_PROFILE') == '1':
            log = (scope / 'stderr.log').read_text(errors='replace')
            active = re.search(r'expert_weight_cache_native_profile: active seeds=(\d+) initial_h2d_bytes=(\d+) init_us=(\d+) charged_bound=(\d+)', log)
            if not active or min(map(int, active.groups()[:2])) <= 0 or int(active[4]) > args.native_mib * 1024**2:
                raise RuntimeError('Profile did not engage within its byte budget; see the retained engine log')
            receipt = {'sha256': profile_hash, 'marker': active[0]}
            if contract and 'LLAMA_EXPERT_CACHE_DIRECT_SEED' in contract['gate_on_env']:
                direct = env.get('LLAMA_EXPERT_CACHE_DIRECT_SEED') == '1'
                init = re.findall(r'expert_weight_cache_direct_seed: stats (.+)', log)
                if direct:
                    if len(init) != 1 or not init[0].startswith('state=complete scope=startup_seed_payload ') or 'seed_source=direct' not in log:
                        raise RuntimeError('Direct seed did not complete the witnessed startup transfer')
                    receipt['direct_seed_stats'] = init[0]
                elif init or 'seed_source=mmap' not in log:
                    raise RuntimeError('The buffered control did not preserve the mmap seed path')
                receipt['seed_source'] = 'direct' if direct else 'mmap'
            save(scope / 'profile-activation.json', receipt)
        if pooled_placement:
            log = (scope / 'stderr.log').read_text(errors='replace')
            save(scope / 'placement-activation.json', pooled_placement_readback(log, placement_control))
        receipt = read(scope / 'scope.json')
        hashes = {}
        prompts = HERE / 'prompts'
        manifest = read(prompts / 'MANIFEST.json')
        approved = {p['target_tokens_including_template']: p['prompt_sha256'] for p in manifest['prompts']}
        if speed:
            hashes = steady_requests(scope, label, PORT, 'llama')
        if p4:
            (scope / 'p4-launch-profile.json').write_bytes(profile_bytes(launch_profile))
            hashes = request_window(args, scope, PORT, 'llama', quiet_preflight, pooled_screen=pooled)
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
