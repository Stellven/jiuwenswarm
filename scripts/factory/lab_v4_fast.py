"""Fast lab for the Muse v4 delivery (lab tooling, outside the factory graph; owner 2026-11-26: the lab is not the
contribution area, speed it up and collect time to first token and decode from the same requests).

    python scripts/factory/lab_v4_fast.py CONFIG.json [A B C D]

CONFIG names, per arm, the engine binary directory, the first pack shard, the MoE cache size, extra server args and
env (the delivered E0/E1 builds, packs, profile and batch plan). Protocol, one capped server load per arm:
per prompt size one cold request (pack pages evicted with POSIX_FADV_DONTNEED first) and, unless the arm lists the
size in skip_warm, one warm request; 32 generated tokens; each streamed request gives client time to first token,
server prefill rate and decode rate together. Rows are written as they finish and a rerun skips rows already done.

Memory: every load runs under systemd-run MemoryMax=96G; device memory (not charged to the cgroup on the GB10) is
kept inside total memory less 14 GiB with -fitt, and the run stops below 8 GiB available.
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
import time
import urllib.request

PORT, HOST_RESERVE_MIB, FLOOR_GIB = 8097, 14336, 8.0


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def meminfo():
    return {l.split(':')[0]: int(l.split()[1]) * 1024 for l in open('/proc/meminfo')}


def evict(model):
    for f in glob.glob(re.sub(r'-00001-of-(\d+)\.gguf$', r'-*-of-\1.gguf', model)):
        fd = os.open(f, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)


def stop(proc):
    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(90)
    except Exception:  # noqa: BLE001
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    time.sleep(5)


def start(name, arm, out):
    mem = meminfo()
    avail, total = mem['MemAvailable'] // 2**20, mem['MemTotal'] // 2**20
    margin = max(1024, avail - (total - HOST_RESERVE_MIB))
    argv = ['systemd-run', '--user', '--scope', '--quiet', '-p', 'MemoryMax=96G', '-p', 'MemorySwapMax=0',
            '--unit', f'muse-lab-v4-{name}-{int(time.time())}', str(Path(arm['bin']) / 'llama-server'), '-m', arm['model'],
            '-lm', 'mmap', '--cpu-moe', '--moe-cache-mib', str(arm['cache_mib']), '-c', '4096', '-np', '1',
            '--host', '127.0.0.1', '--port', str(PORT), '-lv', '4', '-fitt', str(margin), *arm.get('args', [])]
    env = dict(os.environ, LD_LIBRARY_PATH=str(arm['bin']), **arm.get('env', {}))
    evict(arm['model'])
    t0 = time.time()
    proc = subprocess.Popen(argv, env=env, stdout=subprocess.DEVNULL, stderr=open(out / f'{name}.server.log', 'wb'),
                            start_new_session=True)
    while True:
        time.sleep(3)
        if proc.poll() is not None:
            raise SystemExit(f'{name}: server exited {proc.returncode}')
        if meminfo()['MemAvailable'] / 2**30 < FLOOR_GIB:
            stop(proc)
            raise SystemExit(f'{name}: available memory below {FLOOR_GIB} GiB, stopped')
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2).status == 200:
                return proc, time.time() - t0, argv, margin
        except Exception:  # noqa: BLE001
            pass


def request(prompt, n_predict):
    body = json.dumps(dict(prompt=prompt, n_predict=n_predict, temperature=0, seed=1, cache_prompt=False, stream=True)).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/completion', data=body, headers={'Content-Type': 'application/json'})
    t0, first, text, final = time.time(), None, [], {}
    with urllib.request.urlopen(req, timeout=7200) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith('data:'):
                continue
            d = json.loads(line[5:])
            if first is None and d.get('content'):
                first = time.time()
            text.append(d.get('content', ''))
            if d.get('stop'):
                final = d
    t1, tm = time.time(), final.get('timings', {})
    return dict(client_ttft_ms=round(((first or t1) - t0) * 1000, 1), request_total_ms=round((t1 - t0) * 1000, 1),
                prompt_tokens=tm.get('prompt_n'), prompt_ms=tm.get('prompt_ms'), prompt_tokens_per_second=tm.get('prompt_per_second'),
                generated_tokens=tm.get('predicted_n'), decode_tokens_per_second=tm.get('predicted_per_second'),
                output_sha256=hashlib.sha256(''.join(text).encode()).hexdigest(), text_head=''.join(text)[:160])


def summary(rows):
    out = {}
    for r in rows:
        key = f"{r['arm']} {r['request']} {r['state']}"
        out.setdefault(key, []).append(r)
    return {k: dict(client_ttft_s=round(statistics.median(x['client_ttft_ms'] for x in v) / 1000, 1),
                    decode_tok_s=round(statistics.median(x['decode_tokens_per_second'] or 0 for x in v), 3),
                    prefill_tok_s=round(statistics.median(x['prompt_tokens_per_second'] or 0 for x in v), 1), n=len(v))
            for k, v in sorted(out.items())}


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
    for name in names or list(config['arms']):
        arm = config['arms'][name]
        plan = [(size, state) for size in prompts for state in ('cold', 'warm')
                if not (state == 'warm' and size in arm.get('skip_warm', [])) and (name, size, state) not in done]
        if not plan:
            continue
        log(f'{name}: start', arm['model'])
        proc, ready_s, argv, margin = start(name, arm, out)
        markers = [l.strip()[:240] for l in open(out / f'{name}.server.log', errors='replace')
                   if re.search(r'expert_weight_cache.*(active|inactive)|MoE cache size|compute buffer size', l)][:6]
        report['arms'][name] = dict(argv=argv, env=arm.get('env', {}), load_seconds=round(ready_s, 1), fit_margin_mib=margin,
                                    markers=markers, started=time.strftime('%Y-%m-%dT%H:%M:%S'))
        log(f'{name}: ready {ready_s:.0f}s')
        try:
            for size, state in plan:
                if state == 'cold':
                    evict(arm['model'])
                row = dict(arm=name, request=size, state=state, **request(prompts[size], config.get('n_predict', 32)))
                report['rows'].append(row)
                report['summary'] = summary(report['rows'])
                report_path.write_text(json.dumps(report, indent=1))
                log(json.dumps({k: v for k, v in row.items() if k != 'text_head'}))
        finally:
            stop(proc)
            report_path.write_text(json.dumps(report, indent=1))
    log('lab done', json.dumps(report.get('summary', {}), indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
