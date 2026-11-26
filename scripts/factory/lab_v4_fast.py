"""Fast lab for the Muse v4 delivery (lab tooling, outside the factory graph; owner 2026-11-26: the lab is not the
contribution area, speed it up and collect time to first token and decode from the same requests).

    python scripts/factory/lab_v4_fast.py CONFIG.json [ARM ...]

CONFIG names, per arm, the engine binary directory (or `image`: an engine image whose /opt/llamacpp is copied
out and run natively, with optional `expect_sha256`), the first pack shard, the MoE cache size, extra server args and
env (the delivered builds, packs and batch plan). Protocol, one capped server load per arm:
per prompt size one cold request (pack pages evicted with POSIX_FADV_DONTNEED first) and, unless the arm lists the
size in skip_warm, one warm request; 32 generated tokens; each streamed request gives client time to first token,
server prefill rate and decode rate together. Rows are written as they finish and a rerun skips rows already done.

For the rev-8 demo supply `factory_run` with `home` and `task_id` and a `baseline_report` path. The completed
Factory run supplies both arms and the device budget. See MUSE-V4-NEXT-PHASE.md for the exact invocation.

Every load uses factory.capped_runner's machine gate and 96 GiB scope. The runner uses -fitt to keep device memory
within total memory less 14 GiB by default, or CONFIG.device_budget_mib. The lab stops below 8 GiB available.
"""
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.ccs.prefill_batch_sizing.run import parse_log
from jiuwenswarm.factory.store import FactoryError
from scripts.factory import lab_v4_inputs

FLOOR_GIB = 8.0


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def evict(model):
    for f in glob.glob(re.sub(r'-00001-of-(\d+)\.gguf$', r'-*-of-\1.gguf', model)):
        fd = os.open(f, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)


def from_image(name, arm, out):
    """Extract once per immutable image ID in this invocation and record the executed binary's digest."""
    image = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', arm['image']], check=True,
                           capture_output=True, text=True).stdout.strip()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise SystemExit(f'{name}: Docker returned an invalid image ID: {image!r}')
    if arm.get('expect_image_id') and image != arm['expect_image_id']:
        raise SystemExit(f'{name}: Docker image does not match the accepted build ID')
    directory = out / image.removeprefix('sha256:')
    server = directory / 'llama-server'
    if not server.is_file():
        container = subprocess.run(['docker', 'create', image], check=True, capture_output=True, text=True).stdout.strip()
        try:
            subprocess.run(['docker', 'cp', f'{container}:/opt/llamacpp/.', str(directory)], check=True)
        finally:
            subprocess.run(['docker', 'rm', container], check=True, capture_output=True)
    with server.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if arm.get('expect_sha256') and digest != arm['expect_sha256']:
        raise SystemExit(f'{name}: llama-server in {arm["image"]} has sha256 {digest}, expected {arm["expect_sha256"]}')
    return str(directory), dict(image=arm['image'], image_id=image, llama_server_sha256=digest)


def start(name, arm, out, device_budget_mib):
    task = dict(resources=dict(memory_cap=capped_run.CAP, device_budget_mib=device_budget_mib, floor_gib=FLOOR_GIB))
    run = capped_run.RunScope(out, out, task, uuid4().hex, f'{name}.progress.log')
    gate = run.gate()
    evict(arm['model'])
    args = ['-lm', 'mmap', '--cpu-moe', '--moe-cache-mib', str(arm['cache_mib']), '-c', '4096', '-np', '1',
            *arm.get('args', []), '-fit', 'on']
    env = {**capped_run.user_bus_env(), **arm.get('env', {})}
    server_path = Path(arm['bin']).resolve() / 'llama-server'
    log_name = f'{name}.server.log'
    (out / log_name).write_bytes(b'')
    server = capped_run.Server(run, str(server_path), arm['model'], args, env, log_name)
    return server, gate


def request(server, prompt, n_predict):
    body = dict(prompt=prompt, n_predict=n_predict, temperature=0, seed=1, cache_prompt=False, stream=True)
    t0 = time.monotonic()

    def consume(response):
        first, text, final = None, [], None
        for raw in response:
            line = raw.decode().strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            d = json.loads(data)
            if d.get('error'):
                raise ValueError(d['error'])
            if first is None and d.get('content'):
                first = time.monotonic()
            text.append(d.get('content', ''))
            if d.get('stop'):
                final = d
        if final is None:
            raise ValueError('completion stream ended before the terminal event')
        t1, tm, output = time.monotonic(), final['timings'], ''.join(text)
        return dict(client_ttft_ms=round(((first or t1) - t0) * 1000, 1), request_total_ms=round((t1 - t0) * 1000, 1),
                    prompt_tokens=tm['prompt_n'], prompt_ms=tm['prompt_ms'], prompt_tokens_per_second=tm['prompt_per_second'],
                    generated_tokens=tm['predicted_n'], decode_tokens_per_second=tm['predicted_per_second'],
                    output_sha256=hashlib.sha256(output.encode()).hexdigest(), text_head=output[:160])

    return server.post(body, consume=consume)


def summary(rows):
    out = {}
    for r in rows:
        key = f"{r['arm']} {r['request']} {r['state']}"
        out.setdefault(key, []).append(r)
    return {k: dict(client_ttft_s=round(statistics.median(x['client_ttft_ms'] for x in v) / 1000, 1),
                    request_total_s=round(statistics.median(x['request_total_ms'] for x in v) / 1000, 1),
                    decode_tok_s=round(statistics.median(x['decode_tokens_per_second'] or 0 for x in v), 3),
                    prefill_tok_s=round(statistics.median(x['prompt_tokens_per_second'] or 0 for x in v), 1), n=len(v))
            for k, v in sorted(out.items())}


COMPARISON_METRICS = ('client_ttft_ms', 'decode_tokens_per_second', 'request_total_ms')
COMPARISON_PROVENANCE = ('image_id', 'llama_server_sha256', 'pack_manifest_sha256', 'batch_plan', 'n_batch',
                         'n_ubatch', 'moe_cache_mib', 'requested_moe_cache_mib', 'batch_mode', 'prompt_sha256')


def baseline(path):
    path = Path(path).expanduser().resolve()
    raw = path.read_bytes()
    rows = [row for row in json.loads(raw)['rows'] if row['arm'] == 'A']
    for size, tokens in lab_v4_inputs.PROMPT_TOKENS.items():
        for state in ('cold', 'warm'):
            cell = [row for row in rows if (row['request'], row['state']) == (size, state)]
            if not cell or any(row['prompt_tokens'] != tokens for row in cell):
                raise ValueError(f'Historical A needs {size} {state} at {tokens} rendered tokens')
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), rows=rows)


def comparison(rows, reference):
    def groups(data):
        cells = {}
        for row in data:
            cells.setdefault((row['arm'], row['request'], row['state']), []).append(row)
        return cells

    def cell_summary(cell):
        metrics = {key: round(statistics.median(row[key] for row in cell), 6) for key in COMPARISON_METRICS}
        provenance = {key: cell[0].get(key) if all(row.get(key) == cell[0].get(key) for row in cell) else None
                      for key in COMPARISON_PROVENANCE}
        return dict(n=len(cell), prompt_tokens=sorted({row['prompt_tokens'] for row in cell}),
                    generated_tokens=sorted({row['generated_tokens'] for row in cell}), **metrics, **provenance)

    historical = groups(reference['rows'])
    output = []
    for (arm, size, state), cell in sorted(groups(rows).items()):
        key = ('A', size, state)
        if arm not in {'B', 'P'} or key not in historical:
            continue
        current, baseline_a = cell_summary(cell), cell_summary(historical[key])
        same_prompt_tokens = current['prompt_tokens'] == baseline_a['prompt_tokens']
        same_generated_tokens = (len(current['generated_tokens']) == 1
                                 and current['generated_tokens'] == baseline_a['generated_tokens'])
        deltas = {key: round(current[key] - baseline_a[key], 6) for key in COMPARISON_METRICS
                  if same_prompt_tokens and (key != 'request_total_ms' or same_generated_tokens)}
        output.append(dict(arm=arm, request=size, state=state, measured=current, baseline_a=baseline_a,
                           same_prompt_tokens=same_prompt_tokens, same_generated_tokens=same_generated_tokens,
                           delta_vs_a=deltas))
    return dict(baseline_sha256=reference['sha256'], aggregation='median per arm, request and state', cells=output)


def observed_settings(server_log, arm):
    parsed = parse_log(server_log)
    return dict(n_batch=parsed['n_batch'], n_ubatch=parsed['n_ubatch'],
                moe_cache_mib=parsed['device_mib'].get('moe_cache'), requested_moe_cache_mib=arm['cache_mib'])


def validate_settings(name, observed, plan):
    if name == 'P':
        wanted = (plan['batch'], plan['ubatch'])
    else:
        wanted = (plan['reference']['n_batch'], plan['reference']['n_ubatch'])
    if (observed['n_batch'], observed['n_ubatch']) != wanted:
        raise ValueError(f'{name}: server batch settings {observed} differ from the verified plan ({wanted})')
    cache = observed['moe_cache_mib']
    if cache is None or not plan['moe_cache_mib'] - 1024 <= cache <= plan['moe_cache_mib']:
        raise ValueError(f'{name}: server MoE cache {cache} MiB differs from plan {plan["moe_cache_mib"]} MiB')


def save(report_path, report):
    temporary = report_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=1))
    temporary.replace(report_path)


def run_arm(name, arm, out, plan, prompts, report_path, report, config, reference=None):
    progress = out / f'{name}.progress.log'
    log(f'{name}: waiting for the machine; progress in {progress}')
    server, gate = start(name, arm, out, config.get('device_budget_mib'))
    try:
        server_log = server.log.read_text(errors='replace')
        markers = [line.strip()[:240] for line in server_log.splitlines() if re.search(
            r'expert_weight_cache.*(active|inactive)|MoE cache size|n_(?:u)?batch|compute buffer size', line)][:20]
        settings = observed_settings(server_log, arm)
        factory = report.get('factory_provenance')
        batch_plan = report.get('batch_plan')
        if factory:
            validate_settings(name, settings, batch_plan)
        arm_record = dict(argv=server.argv, env=arm.get('env', {}), load_seconds=round(server.ready_s, 1),
                          **server.placement, machine_gate=gate, memory_cap=server.run.cap, markers=markers,
                          started=time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(server.started)))
        report['arms'][name] = arm_record
        log(f'{name}: ready {server.ready_s:.0f}s')
        n_predict = config.get('n_predict', 32)
        for size, state in plan:
            if state == 'cold':
                evict(arm['model'])
            elif (size, 'cold') not in plan:
                # A resumed warm cell needs a preceding request on this load.
                evict(arm['model'])
                request(server, prompts[size], n_predict)
            row = dict(arm=name, request=size, state=state, **request(server, prompts[size], n_predict))
            if factory and row['prompt_tokens'] != lab_v4_inputs.PROMPT_TOKENS[size]:
                raise ValueError(f'{name} {size}: server reported unexpected prompt token count {row["prompt_tokens"]}')
            row.update(report.get('images', {}).get(name, {}), **settings, n_predict=n_predict, cache_prompt=False,
                       prompt_sha256=hashlib.sha256(prompts[size].encode()).hexdigest())
            if factory:
                row.update(factory, batch_plan={key: batch_plan[key] for key in ('batch', 'ubatch', 'moe_cache_mib')},
                           batch_mode='planned' if name == 'P' else 'default', pack_first_shard=arm['model'],
                           device_budget_mib=server.placement['device_budget_mib'])
            report['rows'].append(row)
            report['summary'] = summary(report['rows'])
            if reference:
                report['comparison'] = comparison(report['rows'], reference)
            arm_record.update(sampled_peak_memory_bytes=server.run.peak or None,
                              min_available_bytes=server.run.low)
            save(report_path, report)
            log(json.dumps({key: value for key, value in row.items() if key != 'text_head'}))
    finally:
        server.close()
        save(report_path, report)


def configuration(config_path):
    config = json.loads(Path(config_path).read_text())
    reference = baseline(config['baseline_report']) if 'baseline_report' in config else None
    prompts = {size: Path(path).expanduser().read_text() for size, path in config['prompts'].items()}
    identity, batch_plan = None, None
    if 'factory_run' in config:
        if set(config) & {'arms', 'device_budget_mib'}:
            raise ValueError('Factory mode derives arms and device budget from the accepted run')
        if reference is None or set(prompts) != set(lab_v4_inputs.PROMPT_TOKENS):
            raise ValueError('Factory mode needs the historical A report and p512/p2048 rendered prompts')
        identity, batch_plan, config['arms'] = lab_v4_inputs.resolve(**config['factory_run'])
        config['device_budget_mib'] = int(batch_plan['device_budget_mib'])
    return config, prompts, reference, identity, batch_plan


def main(config_path, names):
    config, prompts, reference, identity, batch_plan = configuration(config_path)
    out = Path(config['out_dir']).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / 'report.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else dict(
        format='muse-v4-fast-lab/1', note='Lab tooling outside the factory graph; engines and packs as delivered.',
        config=config, rows=[], arms={})
    if identity:
        protocol = dict(factory_provenance=identity, batch_plan=batch_plan,
                        baseline={key: reference[key] for key in ('path', 'sha256')},
                        prompt_sha256={size: hashlib.sha256(prompt.encode()).hexdigest() for size, prompt in prompts.items()})
        if report_path.exists() and (report['config'] != config or any(report.get(key) != value for key, value in protocol.items())):
            raise ValueError('Factory inputs differ from the existing report. Use a new out_dir.')
        report.update(protocol)
    elif report.get('factory_provenance'):
        raise ValueError('Factory report requires its original Factory configuration')
    done = {(r['arm'], r['request'], r['state']) for r in report['rows']}
    with TemporaryDirectory(prefix='image-bins-', dir=out) as extracted:
        pending = []
        for name in dict.fromkeys(names or config['arms']):
            arm = dict(config['arms'][name])
            plan = [(size, state) for size in prompts for state in ('cold', 'warm')
                    if not (state == 'warm' and size in arm.get('skip_warm', [])) and (name, size, state) not in done]
            if not plan:
                continue
            if arm.get('image'):
                arm['bin'], image_record = from_image(name, arm, Path(extracted))
                images = report.setdefault('images', {})
                if any(key[0] == name for key in done):
                    previous = images.get(name, {})
                    if any(previous.get(field) != image_record[field] for field in ('image_id', 'llama_server_sha256')):
                        raise SystemExit(f'{name}: image identity differs from the partial report; use a new out_dir')
                images[name] = image_record
            pending.append((name, arm, plan))
        for name, arm, plan in pending:
            run_arm(name, arm, out, plan, prompts, report_path, report, config, reference)
    log('lab done', json.dumps(report.get('summary', {}), indent=1))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    args = sys.argv[1:]
    try:
        if len(args) == 3 and args[0] == '--compare':
            measured = json.loads(Path(args[1]).read_text())
            reference = baseline(args[2])
            recorded = measured.get('baseline', {}).get('sha256')
            if recorded and recorded != reference['sha256']:
                raise ValueError('Historical A report digest differs from the recorded baseline')
            print(json.dumps(comparison(measured['rows'], reference), indent=1))
        elif len(args) == 2 and args[0] == '--resolve':
            config, _, _, identity, plan = configuration(args[1])
            print(json.dumps(dict(config=config, factory_provenance=identity, batch_plan=plan), indent=1))
        elif args and not args[0].startswith('--'):
            main(args[0], args[1:])
        else:
            raise SystemExit('usage: lab_v4_fast.py CONFIG.json [ARM ...] | --resolve CONFIG.json | '
                             '--compare REPORT.json BASELINE.json')
    except capped_run.RunError as exc:
        raise SystemExit(f'{exc.code}: {exc}') from exc
    except (FactoryError, ValueError, OSError, KeyError) as exc:
        raise SystemExit(f'Lab evidence or configuration: {exc}') from exc
