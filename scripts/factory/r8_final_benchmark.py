"""Run the eight approved engine benchmark loads once, from the accepted r8 image."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from uuid import uuid4

from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.ccs.prefill_batch_sizing.run import parse_log
from scripts.factory import lab_v4_fast as lab, lab_v4_inputs as inputs, lab_v4_quiet as quiet
from scripts.spark import r8_empty_watch

ORDER = ('1', '3', '4', '2', '5', '6', '7', '8')
PROPOSAL_SHA = 'bc4ea1dc721599fc7778c480d7743143e1236b4d134f261ccf7a5cd8f1663d8d'
BASE = Path.home() / 'muse-demo'
OUT = BASE / 'lab/r8-final-bench'
BRIDGE = BASE / 'bridge'
PROPOSAL = BASE / 'bench/proposed-engine-benchmark.json'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def record(message):
    subprocess.run([sys.executable, BRIDGE / 'log_step.py', 'run', message], check=True)
    print(now(), message, flush=True)


def digest(path):
    with path.open('rb') as src:
        return hashlib.file_digest(src, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def check_inputs():
    if digest(PROPOSAL) != PROPOSAL_SHA:
        raise ValueError('Ledger bytes differ from the approved proposal')
    p = read(PROPOSAL)
    engine = p['engine']
    identity, plan, _ = inputs.resolve(engine['graph_home'], engine['factory_task_id'])
    for field, expected in [('image_id', 'required_verified_image_id'), ('llama_server_sha256', 'required_image_executable_sha256'),
                            ('source_commit', 'expected_source_commit'), ('batch_plan_sha256', 'accepted_batch_plan_sha256')]:
        if identity[field] != engine[expected]:
            raise ValueError(f'Final graph differs from ledger: {field}')
    for name in ('MIXED_2BIT', 'NVFP4'):
        pin = p['pack_pins'][name]
        manifest = Path(pin['manifest'])
        files = read(manifest)['files']
        if (digest(manifest) != pin['manifest_sha256'] or len(files) != pin['shard_count']
                or files[0]['sha256'] != pin['first_shard_sha256'] or files[0]['name'] != Path(pin['first_shard']).name
                or sum(f['bytes'] for f in files) != pin['bytes']
                or any((manifest.parent / f['name']).stat().st_size != f['bytes'] for f in files)):
            raise ValueError(f'{name} shard manifest mismatch')
    for key, prompt in p['speed_prompt_pins'].items():
        if digest(Path(prompt['file'])) != prompt['sha256']:
            raise ValueError(f'{key} prompt hash mismatch')
    return p, identity, plan


def settings(leg, out):
    effective = deepcopy(leg)
    for field, source in effective.get('settings_from', {}).items():
        calibration, key = source.split(':plan.')
        effective[field] = read(out / f'{calibration}.plan.json')[key]
    return effective


def validate_ready(server, leg):
    parsed = parse_log(server.log.read_text(errors='replace'))
    for key, actual in [('ctx', 'n_ctx'), ('batch', 'n_batch'), ('ubatch', 'n_ubatch')]:
        if leg[key] != parsed[actual]:
            raise ValueError(f"{leg['role']} wanted {key} {leg[key]}, observed {parsed[actual]}")
    device = parsed['device_mib']
    total = sum(device[key] for key in ('model', 'kv', 'compute', 'moe_cache'))
    if total > 110000 or not 0 <= leg['moe_cache_mib'] - device['moe_cache'] <= 1024:
        raise ValueError(f"Device allocations differ from ledger budget or requested cache: {device}")
    return parsed


def run_load(out, p, leg, image_dir, identity, plan, prepared):
    lid, role = leg['id'], leg['role']
    receipt = out / f'{lid}.load.json'
    if receipt.exists():
        if read(receipt)['status'] == 'complete':
            return
        raise RuntimeError(f'Load {lid} already reserved or consumed; refusing another launch')
    from scripts.factory import r8_bench_cells, r8_bench_score
    pin = p['pack_pins'][leg['pack']]
    arm = dict(model=pin['first_shard'], cache_mib=leg['moe_cache_mib'],
               image_id=identity['image_id'], llama_server_sha256=identity['llama_server_sha256'],
               pack_manifest_sha256=pin['manifest_sha256'], device_budget_mib=110000)
    scope = capped_run.RunScope(out, out, dict(resources=dict(memory_cap=capped_run.CAP, device_budget_mib=110000,
        floor_gib=8, gate_wait_s=0)), uuid4().hex, f'{lid}.progress.log')
    rec = dict(load=leg, factory_provenance=identity, pack=pin, settings=arm, status='admitting', utc=now(),
               memory_cap=scope.cap, swap_cap_bytes=0, device_budget_mib=110000)
    args = [*p['base_args'], '-c', str(leg['ctx']), '-np', str(leg['np']), '-b', str(leg['batch']),
            '-ub', str(leg['ubatch']), '--moe-cache-mib', str(leg['moe_cache_mib']), *leg.get('extra_args', [])]
    server = None
    record(f"Final benchmark load {lid}/8 ({role}): fresh quiet and machine admission, {leg['pack']}, "
           f"context {leg['ctx']}, batch/microbatch {leg['batch']}/{leg['ubatch']}, cache {leg['moe_cache_mib']} MiB.")
    with quiet.Monitor(quiet.policy(quiet.EMPTY), slots=leg['np'], stop_on_gate=True) as mon:
        try:
            mon.wait('arm_start', 'loading', lab.log)
            rec['gate'] = scope.gate()
            lab.evict(arm['model'])
            mon.wait('pre_launch', 'loading', lab.log)
            rec['gate_before_load'] = scope.gate()
            rec['status'] = 'launch_reserved'
            lab.save(receipt, rec)
            server = capped_run.Server(scope, str(image_dir/'llama-server'), arm['model'], args,
                                       capped_run.user_bus_env(), f'{lid}.server.log')
            mon.server = server
            mon.mark('ready', 'between_rows')
            rec.update(status='loaded', ready_s=server.ready_s, pid=server.proc.pid, argv=server.argv,
                       placement=server.placement, observed=validate_ready(server, leg))
            lab.save(receipt, rec)
            if leg['recipe'] == 'speed':
                r8_bench_cells.speed(server, mon, p, out, leg, arm)
            elif leg['recipe'] == 'readiness_buffer_calibration':
                r8_bench_cells.calibration(server, p, out, dict(leg, target_plan=plan) if lid == '1' else leg)
            else:
                r8_bench_score.score(server, mon, prepared, out, leg)
            rec['status'] = 'complete'
        except BaseException as exc:
            rec.update(status='stopped', error=str(exc), code=getattr(exc, 'code', type(exc).__name__))
            record(f"Final benchmark STOP at {role}, load {lid}: {rec['code']} {exc}. No retry.")
            raise
        finally:
            if server:
                rec.update(peak_process_rss_bytes=lab.server_peak_rss(server.proc.pid),
                           peak_memory_bytes=scope.peak, min_available_bytes=scope.low)
                server.close()
                mon.server = None
            mon.mark('arm_end')
            rec['ended_utc'] = now()
            lab.save(receipt, rec)
            lab.save(out/f'{lid}.admission.json', [s for s in mon.samples if s['phase'] not in ('during', 'end')])
    record(f'Final benchmark {role} (load {lid}) completed. Receipt {receipt.name}.')


def main(execute, diagnostic):
    from scripts.factory import r8_bench_score
    p, identity, plan = check_inputs()
    prepared = r8_bench_score.prepare(p)
    if not diagnostic:
        for name in ('speed_full', 'speed_A'):
            p['request_plans'][name] = [c for c in p['request_plans'][name] if c.get('role') != 'decode']
    if not execute:
        print('Validated proposal, manifests, image and graph records, prompt hashes, scoring cases.')
        return
    OUT.mkdir(exist_ok=True)
    with (OUT/'campaign.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = dict(proposal_sha256=PROPOSAL_SHA, order=ORDER, diagnostic_128=diagnostic,
                      approval='Owner approved the single eight-load final benchmark.',
                      calibration_mapping='PC coordinator clarification within the owner-approved benchmark.',
                      identity=identity, policy=quiet.policy(quiet.EMPTY))
        config = json.loads(json.dumps(config))
        path = OUT/'campaign.json'
        if path.exists() and read(path) != config:
            raise ValueError('Resume configuration differs from campaign')
        lab.save(path, config)
        if any(read(f)['status'] != 'complete' for f in OUT.glob('*.load.json')):
            raise RuntimeError('Incomplete load receipt; no automatic repeat')
        evidence = OUT/f'empty-watch-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.jsonl'
        record('Final eight-load benchmark: starting uninterrupted ten-minute empty-machine admission. Watch state logged every five minutes.')
        r8_empty_watch.watch(BRIDGE, evidence)
        with TemporaryDirectory(dir=OUT, prefix='image-bins-') as scratch:
            image_args = dict(image=identity['image_id'], expect_image_id=identity['image_id'],
                              expect_sha256=identity['llama_server_sha256'])
            directory, image = lab.from_image('r8-final-bench', image_args, Path(scratch))
            lab.save(OUT/'image.json', image)
            loads = {leg['id']:leg for leg in p['required_loads']}
            for lid in ORDER:
                run_load(OUT, p, settings(loads[lid], OUT), Path(directory), identity, plan, prepared)
        record('Final eight-load benchmark completed. All eight load receipts are durable; starting evidence integration.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--diagnostic-128', action='store_true')
    opts = ap.parse_args()
    main(opts.execute, opts.diagnostic_128)
