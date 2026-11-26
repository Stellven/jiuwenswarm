"""Fast lab for the Muse v4 delivery (lab tooling, outside the factory graph; owner 2026-11-26: the lab is not the
contribution area, speed it up and collect time to first token and decode from the same requests).

    python scripts/factory/lab_v4_fast.py CONFIG.json [ARM ...]

CONFIG names, per arm, the engine binary directory (or `image`: an engine image whose /opt/llamacpp is copied
out and run natively, with optional `expect_sha256`), the first pack shard, the MoE cache size, extra server args and
env (the delivered builds, packs and batch plan). Protocol, one capped server load per arm:
per prompt size one cold request (pack pages evicted with POSIX_FADV_DONTNEED first) and, unless the arm lists the
size in skip_warm, one warm request; 32 generated tokens; each streamed request gives client time to first token,
server prefill rate and decode rate together. Rows are written as they finish and a rerun skips rows already done.

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
                    decode_tok_s=round(statistics.median(x['decode_tokens_per_second'] or 0 for x in v), 3),
                    prefill_tok_s=round(statistics.median(x['prompt_tokens_per_second'] or 0 for x in v), 1), n=len(v))
            for k, v in sorted(out.items())}


def save(report_path, report):
    temporary = report_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=1))
    temporary.replace(report_path)


def run_arm(name, arm, out, plan, prompts, report_path, report, config):
    progress = out / f'{name}.progress.log'
    log(f'{name}: waiting for the machine; progress in {progress}')
    server, gate = start(name, arm, out, config.get('device_budget_mib'))
    try:
        with server.log.open(errors='replace') as handle:
            markers = [line.strip()[:240] for line in handle if re.search(
                r'expert_weight_cache.*(active|inactive)|MoE cache size|n_ubatch|compute buffer size', line)][:20]
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
            report['rows'].append(row)
            report['summary'] = summary(report['rows'])
            arm_record.update(sampled_peak_memory_bytes=server.run.peak or None,
                              min_available_bytes=server.run.low)
            save(report_path, report)
            log(json.dumps({key: value for key, value in row.items() if key != 'text_head'}))
    finally:
        server.close()
        save(report_path, report)


def main(config_path, names):
    config = json.loads(Path(config_path).read_text())
    out = Path(config['out_dir'])
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / 'report.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else dict(
        format='muse-v4-fast-lab/1', note='Lab tooling outside the factory graph; engines and packs as delivered.',
        config=config, rows=[], arms={})
    prompts = {size: Path(path).read_text() for size, path in config['prompts'].items()}
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
            run_arm(name, arm, out, plan, prompts, report_path, report, config)
    log('lab done', json.dumps(report.get('summary', {}), indent=1))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    if len(sys.argv) < 2:
        raise SystemExit('usage: python scripts/factory/lab_v4_fast.py CONFIG.json [ARM ...]')
    try:
        main(sys.argv[1], sys.argv[2:])
    except capped_run.RunError as exc:
        raise SystemExit(f'{exc.code}: {exc}') from exc
