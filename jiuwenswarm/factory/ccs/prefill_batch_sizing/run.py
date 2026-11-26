"""CC v2 native entry of engine.size_prefill_batch: one JSON packet on stdin, one JSON result on stdout.

plan    pick the server's logical/physical batch (-b/-ub) so each expected prompt is prefilled in as few
        micro-batches as the device memory budget allows. With CPU-resident (mmap, --cpu-moe) experts every
        micro-batch streams the routed expert weights again, so prefill time grows with the micro-batch
        count, not with the token count.
verify  check one capped server load (its log) and lab rows of the same requests at the default and the
        planned batch: the batch was applied, every planned prompt fits one micro-batch, the measured device
        buffers fit the budget, and the greedy outputs agree (byte-identical, or a long common prefix when a
        different batch split changes the float summation order).
fill    (plan input fill_moe_cache_headroom_mib) after the batch is chosen, give the rest of the device budget to
        the MoE expert cache: --moe-cache-mib = budget - headroom - (model + KV + compute at the planned batch),
        in whole GiB. Unified memory left idle under the budget is expert bytes streamed from disk again; verify
        then checks the server sized its cache to the plan.
Reads files only; starts nothing.
"""
import json
import math
import re
import sys
from pathlib import Path

STATIC, NATIVE, RUNTIME = 'fixture', 'native CC execution', 'runtime acceptance'
ORDER = (STATIC, NATIVE, 'compile', RUNTIME)
MIN_UBATCH = 512


def check(name, status, detail, stage):
    return dict(name=name, status=status, detail=detail, stage=stage)


def result(checks, need=None, **extra):
    failed = [c for c in checks if c['status'] == 'fail']
    reached = None
    for stage in ORDER:
        mine = [c for c in checks if c['stage'] == stage]
        if any(c['status'] in ('fail', 'skipped') for c in mine):
            break
        if any(c['status'] == 'pass' for c in mine):
            reached = stage
    why = [f"{c['name']}: {c['detail']}" for c in failed]
    if need and (reached is None or ORDER.index(reached) < ORDER.index(need)):
        why.append(f'stage {need} not reached (reached {reached})')
    return dict(done=bool(checks) and not why, checks=checks, stage_reached=reached, not_done_because=why, **extra)


# ---- the server log ------------------------------------------------------------------------
MIB = r'\s*([0-9.]+) MiB'


def parse_log(text):
    """The numbers a llama-server load prints at -lv 4 (stock 9048bad8 wording)."""
    def first(pattern, cast=int):
        m = re.search(pattern, text)
        return cast(m.group(1)) if m else None
    device = {}
    for name, pattern in (('model', r'CUDA0 model buffer size =' + MIB), ('kv', r'CUDA0 KV buffer size =' + MIB),
                          ('moe_cache', r'CUDA0 MoE cache size =' + MIB), ('compute', r'CUDA0 compute buffer size =' + MIB),
                          ('host_compute', r'CUDA_Host compute buffer size =' + MIB)):
        values = [float(v) for v in re.findall(pattern, text)]
        if values:
            device[name] = round(sum(values), 2)
    return dict(n_ctx=first(r'llama_context: n_ctx\s+= (\d+)'), n_batch=first(r'llama_context: n_batch\s+= (\d+)'),
                n_ubatch=first(r'llama_context: n_ubatch\s+= (\d+)'), device_mib=device,
                mapped_mib=round(sum(float(v) for v in re.findall(r'CPU_Mapped model buffer size =' + MIB, text)), 2))


def _text(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} is a path or the log text')
    path = Path(value)
    return path.read_text(errors='replace') if '\n' not in value and path.is_file() else value


def _prompts(inputs):
    sizes = inputs['prompt_tokens']
    if not isinstance(sizes, list) or not sizes or not all(type(s) is int and s > 0 for s in sizes):
        raise ValueError('prompt_tokens is a nonempty list of positive token counts')
    return sorted(set(sizes))


def _budget(inputs):
    budget = inputs['device_budget_mib']
    if not isinstance(budget, (int, float)) or budget <= 0:
        raise ValueError('device_budget_mib is a positive number')
    return float(budget)


# ---- plan ------------------------------------------------------------------------------------
def estimate(base, ubatch):
    """Device MiB at ``ubatch`` scaled from a load at the reference ubatch and the same context. Model, MoE cache
    and KV buffers do not depend on the ubatch (KV is sized by n_ctx) and are taken as measured; the compute
    buffers (CUDA0 and host) are scaled linearly, which overestimates them: measured on Muse, the CUDA0 compute
    buffer was 1538.5 MiB at 512 and 2128.1 MiB at 2048."""
    d, scale = base['device_mib'], ubatch / base['n_ubatch']
    fixed = d.get('model', 0) + d.get('moe_cache', 0) + d.get('kv', 0)
    scaled = sum(d.get(k, 0) for k in ('compute', 'host_compute')) * max(1.0, scale)
    return round(fixed + scaled, 1)


def _headroom(inputs, key='fill_moe_cache_headroom_mib'):
    value = inputs.get(key)
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f'{key} is a non-negative integer (MiB)')
    return value


def plan(inputs):
    base = parse_log(_text(inputs['baseline_log'], 'baseline_log'))
    if not base['n_ubatch'] or not base['device_mib'].get('compute'):
        raise ValueError('baseline_log lacks n_ubatch or the CUDA0 compute buffer line (run the server at -lv 4)')
    prompts, budget = _prompts(inputs), _budget(inputs)
    n_ctx = inputs.get('n_ctx') or base['n_ctx']
    # KV and the attention part of the compute buffer grow with the context; a log at a smaller context cannot
    # bound them. The estimate is only trusted from a baseline at (at least) the target context.
    ctx_ok = not base['n_ctx'] or n_ctx <= base['n_ctx']
    want = min(n_ctx, 2 ** math.ceil(math.log2(max(prompts))))
    ubatch, tried = max(want, MIN_UBATCH), []
    while True:
        need = estimate(base, ubatch)
        tried.append(dict(ubatch=ubatch, estimate_mib=need, fits=need <= budget))
        if need <= budget or ubatch <= MIN_UBATCH:
            break
        ubatch //= 2
    fits = tried[-1]['fits']
    headroom, cache = _headroom(inputs), None
    if headroom is not None and fits:
        others = tried[-1]['estimate_mib'] - base['device_mib'].get('moe_cache', 0)
        cache = int((budget - headroom - others) // 1024) * 1024
        cache = max(cache, int(base['device_mib'].get('moe_cache', 0) // 1024) * 1024)
        tried[-1]['estimate_mib'] = round(others + cache, 1)
    batch = max(ubatch, base['n_batch'] or 0)
    passes = {str(p): dict(before=math.ceil(p / base['n_ubatch']), after=math.ceil(p / ubatch)) for p in prompts}
    args = ['-b', str(batch), '-ub', str(ubatch)] + (['--moe-cache-mib', str(cache)] if cache else [])
    doc = dict(format='factory.prefill-batch-plan/1', batch=batch, ubatch=ubatch, args=args,
               reference=dict(n_ubatch=base['n_ubatch'], n_batch=base['n_batch'], n_ctx=n_ctx, device_mib=base['device_mib']),
               device_budget_mib=budget, estimate_mib=tried[-1]['estimate_mib'], tried=tried, prompt_tokens=prompts,
               micro_batches=passes, fits=fits,
               **(dict(moe_cache_mib=cache, headroom_mib=headroom,
                       moe_cache_from_mib=base['device_mib'].get('moe_cache', 0)) if cache else {}),
               rationale=(f'Each prefill micro-batch streams the CPU-resident experts again; ubatch {ubatch} prefills '
                          + ', '.join(f'{p} tokens in {v["after"]} (was {v["before"]})' for p, v in passes.items())
                          + f' micro-batch(es); estimated device {tried[-1]["estimate_mib"]:.0f} MiB of {budget:.0f}.'
                          + (f' The rest of the budget less {headroom} MiB headroom goes to the MoE cache: {cache} MiB '
                             f'(was {base["device_mib"].get("moe_cache", 0):.0f}).' if cache else '')))
    checks = [check('baseline_log', 'pass', f"ubatch {base['n_ubatch']}, device {sum(base['device_mib'].values()):.0f} MiB", NATIVE),
              check('baseline_context', 'pass' if ctx_ok else 'fail',
                    f"baseline n_ctx {base['n_ctx']}, target {n_ctx}" + ('' if ctx_ok else ': load the baseline at the target context'), NATIVE),
              check('fits_budget', 'pass' if fits else 'fail',
                    f"{tried[-1]['estimate_mib']:.0f} MiB estimated vs {budget:.0f} MiB budget at ubatch {ubatch}", NATIVE),
              *([check('moe_cache_filled', 'pass' if cache else 'fail',
                       f"--moe-cache-mib {cache}, estimate {tried[-1]['estimate_mib']:.0f} MiB with {headroom} MiB headroom"
                       if cache else 'no room: the batch does not fit the budget', NATIVE)] if headroom is not None else []),
              check('fewer_micro_batches', 'pass' if any(v['after'] < v['before'] for v in passes.values()) else 'info',
                    json.dumps(passes), NATIVE)]
    if inputs.get('plan_out'):
        Path(inputs['plan_out']).write_text(json.dumps(doc, indent=1))
    return result(checks, plan=doc)


# ---- verify ----------------------------------------------------------------------------------
def _rows(value, name):
    rows = value if isinstance(value, list) else json.loads(_text(value, name))
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) and 'request' in r for r in rows):
        raise ValueError(f'{name} is a list of lab rows with request, output_sha256 and text_head')
    return rows


def _prefix(a, b):
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def verify(inputs):
    doc = inputs['plan'] if isinstance(inputs['plan'], dict) else json.loads(_text(inputs['plan'], 'plan'))
    budget = _budget(inputs)
    checks = []
    ok_format = doc.get('format') == 'factory.prefill-batch-plan/1' and type(doc.get('ubatch')) is int and type(doc.get('batch')) is int
    checks.append(check('plan_format', 'pass' if ok_format else 'fail', 'factory.prefill-batch-plan/1' if ok_format else 'not a plan', NATIVE))
    if not ok_format:
        return result(checks, RUNTIME)
    prompts = _prompts(dict(prompt_tokens=inputs.get('prompt_tokens') or doc.get('prompt_tokens')))
    over = [p for p in prompts if p > doc['ubatch']]
    checks.append(check('one_micro_batch', 'pass' if not over else 'fail',
                        f"ubatch {doc['ubatch']} covers {prompts}" if not over else f'prompts {over} still need several micro-batches', NATIVE))
    checks.append(check('batch_covers_ubatch', 'pass' if doc['batch'] >= doc['ubatch'] else 'fail',
                        f"-b {doc['batch']} -ub {doc['ubatch']}", NATIVE))
    log = parse_log(_text(inputs['server_log'], 'server_log'))
    applied = log['n_ubatch'] == doc['ubatch'] and log['n_batch'] == doc['batch']
    checks.append(check('batch_applied', 'pass' if applied else 'fail',
                        f"server n_batch {log['n_batch']} n_ubatch {log['n_ubatch']} vs plan {doc['batch']}/{doc['ubatch']}", RUNTIME))
    device = sum(log['device_mib'].values())
    if not log['device_mib'].get('compute'):
        checks.append(check('device_budget', 'fail', 'server_log has no CUDA0 compute buffer line (-lv 4)', RUNTIME))
    else:
        checks.append(check('device_budget', 'pass' if device <= budget else 'fail',
                            f"{device:.0f} MiB measured ({', '.join(f'{k} {v:.0f}' for k, v in log['device_mib'].items())}) vs {budget:.0f} MiB", RUNTIME))
        planned = doc.get('moe_cache_mib')
        if planned:
            got = log['device_mib'].get('moe_cache', 0)
            # The server rounds the cache down to whole expert slots (61440 MiB asked printed 61425 on Muse).
            checks.append(check('moe_cache_applied', 'pass' if planned - 1024 <= got <= planned else 'fail',
                                f'server MoE cache {got:.0f} MiB vs planned --moe-cache-mib {planned}', RUNTIME))
        headroom = _headroom(inputs)
        if headroom is not None:
            filled = bool(planned) and device + headroom + 2048 >= budget
            checks.append(check('budget_filled', 'pass' if filled else 'fail',
                                f'{device:.0f} MiB used + {headroom} MiB headroom vs {budget:.0f} MiB budget'
                                + ('' if planned else ': the plan does not size the MoE cache')
                                + ('' if filled or not planned else ': the compute estimate was high; plan again with '
                                   "this load's log as baseline_log (compute measured at the planned batch)"), RUNTIME))
        estimate_mib = doc.get('estimate_mib')
        if isinstance(estimate_mib, (int, float)):
            checks.append(check('estimate_safe', 'pass' if device <= estimate_mib * 1.02 else 'fail',
                                f'measured {device:.0f} MiB vs planned estimate {estimate_mib:.0f} MiB', RUNTIME))
    base, cand = _rows(inputs['baseline_rows'], 'baseline_rows'), _rows(inputs['candidate_rows'], 'candidate_rows')
    min_agree = int(inputs.get('min_agree_chars', 64))
    requests = sorted({r['request'] for r in cand})
    if not requests:
        checks.append(check('output_agreement', 'fail', 'no candidate rows', RUNTIME))
    for request in requests:
        b = next((r for r in base if r['request'] == request), None)
        c = next(r for r in cand if r['request'] == request)
        name = f'output_agreement:{request}'
        if b is None:
            checks.append(check(name, 'fail', 'no baseline row for this request', RUNTIME))
        elif b.get('output_sha256') and b.get('output_sha256') == c.get('output_sha256'):
            checks.append(check(name, 'pass', 'greedy output byte-identical to the default batch', RUNTIME))
        else:
            n = _prefix(b.get('text_head', ''), c.get('text_head', ''))
            status = 'pass' if n >= min_agree else 'fail'
            checks.append(check(name, status, f'outputs agree for the first {n} characters, then differ (a different '
                                'micro-batch split changes the float summation order of prefill); '
                                f'required {min_agree}', RUNTIME))
    return result(checks, RUNTIME, measured=dict(device_mib=log['device_mib'], n_batch=log['n_batch'], n_ubatch=log['n_ubatch']))


def main():
    packet = json.load(sys.stdin)
    capability = packet.get('capability')
    if capability not in ('plan', 'verify'):
        print(json.dumps({'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': 'Expected plan or verify'}}))
        return
    try:
        outputs = (plan if capability == 'plan' else verify)(packet.get('inputs', {}))
    except (KeyError, OSError, TypeError, ValueError) as exc:
        outputs = result([check('input', 'fail', f'{type(exc).__name__}: {exc}', NATIVE)], RUNTIME if capability == 'verify' else None)
    print(json.dumps({'outcome': 'ok', 'outputs': outputs}))


if __name__ == '__main__':
    main()
