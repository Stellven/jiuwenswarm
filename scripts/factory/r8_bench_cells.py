"""Run ledger cells on an already-running capped server."""

import hashlib
import json
import math
from pathlib import Path

from jiuwenswarm.factory.capped_run import RunError
from jiuwenswarm.factory.ccs.prefill_batch_sizing import run as prefill_batch_sizing
from scripts.factory import lab_v4_fast

PROMPTS = ('p128', 'p512', 'p1024', 'p2048', 'p4096')
DEVICE_BUFFERS = ('model', 'moe_cache', 'kv', 'compute')


def read_prompts(proposal):
    """Check the rendered files byte for byte before using their text."""
    prompts = {}
    for name in proposal.get('speed_lengths', PROMPTS):
        pin = proposal['speed_prompt_pins'][name]
        data = Path(pin['file']).expanduser().read_bytes()
        if hashlib.sha256(data).hexdigest() != pin['sha256']:
            raise ValueError(f'{name}: rendered prompt SHA-256 differs from the proposal')
        prompts[name] = data.decode('utf-8')
    return prompts


def tokenize(server, proposal, prompts):
    counts = {}
    for name, text in prompts.items():
        # The accepted server's /completion string path uses both special-token flags.
        response = server.post(dict(content=text, add_special=True, parse_special=True),
                               timeout=60, path='/tokenize')
        tokens = response.get('tokens') if isinstance(response, dict) else None
        if not isinstance(tokens, list) or not tokens or any(type(token) is not int for token in tokens):
            raise ValueError(f'{name}: missing or invalid token IDs from /tokenize')
        count = len(tokens)
        pinned = proposal['speed_prompt_pins'][name]['verified_server_tokens']
        if pinned is not None and count != pinned:
            raise ValueError(f'{name}: /tokenize returned {count} tokens, expected {pinned}')
        counts[name] = count
    return counts


def speed_schedule(proposal, leg):
    cells = proposal['request_plans'][leg['request_plan']]
    lengths = tuple(proposal.get('speed_lengths', PROMPTS))
    if lengths not in (PROMPTS, ('p512', 'p2048')):
        raise ValueError('Unexpected benchmark prompt lengths')
    expected = [
        (prompt, 'cold' if repeat == 0 else 'warm', repeat)
        for prompt in lengths
        for repeat in range(2 if leg['role'] == 'A' and prompt == 'p4096' else 3)
    ]
    regular = []
    decode = False
    for cell in cells:
        key = (cell['prompt'], cell['state'], cell['repeat'])
        if cell['n_predict'] == 32 and cell.get('role', 'speed') == 'speed':
            if cell['evict_pages'] is not (cell['state'] == 'cold'):
                raise ValueError(f'{leg["role"]} {key}: invalid page eviction setting')
            regular.append(key)
        elif (not decode and key == ('p512', 'warm', 0) and cell['n_predict'] == 128
              and cell.get('role') == 'decode' and cell['evict_pages'] is False
              and regular == expected[:6]):
            decode = True
        else:
            raise ValueError(f'{leg["role"]} {key}: unexpected speed request')
    if regular != expected:
        raise ValueError(f'{leg["role"]}: incomplete, duplicated or out-of-order speed schedule')
    return cells


def _server_evidence(server, leg):
    raw = server.log.read_bytes()
    observed = prefill_batch_sizing.parse_log(raw.decode('utf-8', errors='replace'))
    expected = (leg['ctx'], leg['batch'], leg['ubatch'])
    actual = (observed['n_ctx'], observed['n_batch'], observed['n_ubatch'])
    if actual != expected:
        raise ValueError(f'{leg["role"]}: observed context/batch/ubatch {actual}, expected {expected}')
    buffers = observed['device_mib']
    if not all(buffers.get(key, 0) > 0 for key in DEVICE_BUFFERS):
        raise ValueError(f'{leg["role"]}: server log lacks required device buffers')
    cache_mib = leg['moe_cache_mib']
    if not cache_mib - 1024 <= buffers['moe_cache'] <= cache_mib:
        raise ValueError(f'{leg["role"]}: observed cache {buffers["moe_cache"]} MiB differs from request {cache_mib} MiB')
    return observed, hashlib.sha256(raw).hexdigest()


def _device_mib(settings):
    return sum(settings['device_mib'][key] for key in DEVICE_BUFFERS)


def _memory(server):
    return dict(peak_process_rss_bytes=lab_v4_fast.server_peak_rss(server.proc.pid),
                sampled_peak_memory_bytes=server.run.peak or None,
                min_available_bytes=server.run.low)


def _identity(proposal, leg):
    engine = proposal['engine']
    pack = proposal['pack_pins'][leg['pack']]
    return dict(image_id=engine['required_verified_image_id'],
                llama_server_sha256=engine['required_image_executable_sha256'],
                engine_source_commit=engine.get('expected_source_commit'),
                pack=leg['pack'], pack_first_shard=pack['first_shard'],
                pack_manifest_sha256=pack['manifest_sha256'])


def _quiet_failure(error, samples):
    reasons = [reason for sample in samples for reason in sample['reasons']]
    reasons.append(f'{getattr(error, "code", type(error).__name__)}: {error}')
    return dict(status='excluded', reasons=list(dict.fromkeys(reasons)), samples=samples)


def _prefill_segments(progress, expected):
    positions = [0]
    for event in progress:
        position = event.get('processed')
        if (type(position) is not int or event.get('cache') != 0 or event.get('total') != expected
                or not positions[-1] <= position <= expected):
            return None
        if position > positions[-1]:
            positions.append(position)
    if positions[-1] != expected:
        return None
    return [end - start for start, end in zip(positions, positions[1:])]


def speed(server, monitor, proposal, out, leg, arm):
    """Measure an authorized speed ledger leg, persisting each attempted cell."""
    path = Path(out) / f'{leg["id"]}.speed.json'
    cells = speed_schedule(proposal, leg)
    prompts = read_prompts(proposal)
    identity = _identity(proposal, leg)
    prompt_sha = {name: proposal['speed_prompt_pins'][name]['sha256'] for name in prompts}
    if path.exists():
        previous = json.loads(path.read_text())
        if (previous['status'] == 'completed' and previous['leg'] == leg and previous['identity'] == identity
                and previous['request_schedule'] == cells and previous['prompt_sha256'] == prompt_sha):
            return previous
        raise ValueError(f'{path} already records this load; preserve it before considering another load')
    settings, log_sha = _server_evidence(server, leg)
    budget = proposal['memory']['device_budget_mib']
    if _device_mib(settings) > budget:
        raise ValueError(f'{leg["role"]}: observed server buffers exceed {budget} MiB')
    model = str(arm.get('model', identity['pack_first_shard']))
    if Path(model).resolve() != Path(identity['pack_first_shard']).resolve():
        raise ValueError(f'{leg["role"]}: model for cold page eviction differs from the pinned pack')
    report = dict(format='muse-r8-bench-speed/1', status='running', leg=leg, identity=identity,
                  quiet_policy=monitor.limits, rows=[], observed_settings=settings,
                  request_schedule=cells, prompt_sha256=prompt_sha,
                  load_seconds=server.ready_s, server_log=str(server.log), readiness_log_sha256=log_sha)
    lab_v4_fast.save(path, report)
    try:
        counts = tokenize(server, proposal, prompts)
        report['tokenized_prompt_tokens'] = counts
        lab_v4_fast.save(path, report)
        for cell in cells:
            name = cell['prompt']
            row = dict(identity, arm=leg['role'], request=name, state=cell['state'], repeat=cell['repeat'],
                       role=cell.get('role', 'speed'), n_predict=cell['n_predict'], cache_prompt=False,
                       ignore_eos=True, evict_pages=cell['evict_pages'], tokenized_prompt_tokens=counts[name],
                       prompt_sha256=prompt_sha[name],
                       n_batch=settings['n_batch'], n_ubatch=settings['n_ubatch'], n_ctx=settings['n_ctx'],
                       device_budget_mib=budget, moe_cache_mib=settings['device_mib']['moe_cache'],
                       requested_moe_cache_mib=leg['moe_cache_mib'])
            start = len(monitor.samples)
            try:
                if cell['evict_pages']:
                    lab_v4_fast.evict(model)
                metrics, evidence, error = lab_v4_fast.measure(
                    server, prompts[name], cell['n_predict'], counts[name], monitor, benchmark=True)
            except BaseException as error:
                row['quiet'] = _quiet_failure(error, monitor.samples[start:])
                report['rows'].append(row)
                raise
            row.update(metrics, quiet=evidence,
                       prefill_segment_tokens=_prefill_segments(metrics.get('prompt_progress', []), counts[name]))
            if error is not None:
                row['error'] = str(error)
            report['rows'].append(row)
            report.update(_memory(server), quiet_samples=list(monitor.samples))
            lab_v4_fast.save(path, report)
            lab_v4_fast.log(f'{leg["role"]} {name} {cell["state"]} repeat {cell["repeat"]}: {evidence["status"]}')
            # The next admission verifies the server is idle even after a failed HTTP request.
            request_error = isinstance(error, RunError) and error.code == 'REQUEST'
            if error is not None and not (request_error or metrics and isinstance(error, ValueError)):
                raise error
            if any('probe unavailable' in reason or 'missing' in reason or 'incomplete' in reason
                   for reason in evidence['reasons']):
                raise RunError('LAB_NOT_QUIET', f'{leg["role"]} {name}: quiet evidence lost')
        report['status'] = 'completed'
    except BaseException as error:
        report.update(status='stopped', error=dict(code=getattr(error, 'code', type(error).__name__), message=str(error)))
        raise
    finally:
        report.update(_memory(server), quiet_samples=list(monitor.samples))
        lab_v4_fast.save(path, report)
    return report


def _calibrated_plan(server, leg, settings, counts, budget):
    target = leg.get('target_plan')
    prompts = sorted(set(counts.values()))
    baseline_cache = leg['moe_cache_mib']
    measured_cache = settings['device_mib']['moe_cache']
    # Charge each candidate for the entire requested cache even if the server rounded down the allocation.
    sizing_prompts = [min(count, target['ubatch']) for count in prompts] if target else prompts
    # Retain the complete source log in the receipt. The capsule's budget input is for device buffers.
    device_log = '\n'.join(line for line in server.log.read_text(errors='replace').splitlines()
                           if 'CUDA_Host compute buffer size =' not in line)
    native = prefill_batch_sizing.plan(dict(
        baseline_log=device_log, prompt_tokens=sizing_prompts, n_ctx=leg['ctx'],
        device_budget_mib=budget - baseline_cache + measured_cache))
    if not native['done']:
        return native, None
    plan = native['plan']
    without_cache = plan['estimate_mib'] - measured_cache
    cache = baseline_cache
    if target:
        wanted = target['moe_cache_mib']
        if without_cache + wanted <= budget:
            cache = wanted
        else:
            remaining = budget - without_cache - target.get('headroom_mib', 0)
            cache = max(baseline_cache, min(wanted, int(remaining // 1024) * 1024))
    estimate = round(without_cache + cache, 1)
    tried = [dict(option, estimate_mib=round(option['estimate_mib'] - measured_cache + cache, 1),
                  fits=option['estimate_mib'] - measured_cache + cache <= budget) for option in plan['tried']]
    ubatch = plan['ubatch']
    passes = {str(count): dict(before=math.ceil(count / settings['n_ubatch']), after=math.ceil(count / ubatch))
              for count in prompts}
    return native, dict(
        plan, device_budget_mib=budget, estimate_mib=estimate, fits=estimate <= budget,
        prompt_tokens=prompts, tried=tried, micro_batches=passes, moe_cache_mib=cache,
        args=[*plan['args'], '--moe-cache-mib', str(cache)],
        rationale=f'Calibrated uBatch {ubatch} at context {leg["ctx"]} using the capsule buffer estimate. '
                  f'Request {cache} MiB for the MoE cache, for an estimated {estimate:g} MiB of {budget:g} MiB.')


def calibration(server, proposal, out, leg):
    """Size a plan from readiness logs and the loaded pack's tokenizer."""
    out = Path(out)
    path = out / f'{leg["id"]}.calibration.json'
    plan_path = out / f'{leg["id"]}.plan.json'
    if path.exists() or plan_path.exists():
        raise ValueError(f'{path} or {plan_path} already records this calibration')
    budget = proposal['memory']['device_budget_mib']
    report = dict(format='muse-r8-bench-calibration/1', status='running', leg=leg,
                  identity=_identity(proposal, leg), server_log=str(server.log), load_seconds=server.ready_s,
                  device_budget_mib=budget)
    lab_v4_fast.save(path, report)
    try:
        settings, log_sha = _server_evidence(server, leg)
        report.update(observed_settings=settings, server_log_sha256=log_sha)
        if _device_mib(settings) > budget:
            raise ValueError(f'{leg["role"]}: calibration server buffers exceed {budget} MiB')
        counts = tokenize(server, proposal, read_prompts(proposal))
        report['tokenized_prompt_tokens'] = counts
        native, plan = _calibrated_plan(server, leg, settings, counts, budget)
        report['capsule_result'] = native
        if plan is None or not plan['fits']:
            raise ValueError(f'{leg["role"]}: capsule found no feasible batch plan under {budget} MiB')
        lab_v4_fast.save(plan_path, plan)
        report.update(status='completed', plan_path=str(plan_path), plan=plan)
        return plan
    except BaseException as error:
        report.update(status='stopped', error=dict(code=getattr(error, 'code', type(error).__name__), message=str(error)))
        raise
    finally:
        report.update(_memory(server))
        lab_v4_fast.save(path, report)
