"""Portable factory-stage checker for one CPU SWA model in two configurations."""

from itertools import takewhile
import re

from jiuwenswarm.factory.llama_request_log import first_cached_tasks


def _checkpoint_limit(startup_log):
    found = re.search(r'context checkpoints enabled, max = (\d+)\b', startup_log)
    return int(found[1]) if found else None


def verify_mode(startup_log, window_tokens, *, configured):
    """Check actual mode and buffers from a caller-supplied server's startup log."""
    if (type(window_tokens) is not int or window_tokens <= 0
            or not re.search(rf'\bn_swa\s*=\s*{window_tokens}\b', startup_log)
            or not re.search(r'\bCPU(?:_Mapped)?\s+model buffer size', startup_log)
            or re.search(r'offloaded [1-9]\d*/|(?:CUDA|ROCm|Vulkan|Metal|SYCL)\d*\s+'
                         r'(?:model|KV|compute) buffer size', startup_log, re.IGNORECASE)):
        raise ValueError('Server did not confirm the stated sliding window and CPU-only buffers')
    full_swa = 'using full-size SWA cache' in startup_log
    if full_swa != configured:
        raise ValueError('Server log shows the other configuration’s SWA mode')
    if configured and _checkpoint_limit(startup_log) != 32:
        raise ValueError('Server log did not confirm 32 context checkpoints')
    return full_swa


def read_request_cache(raw, expected_tokens):
    """Read the first cached-token count for one completed request."""
    tasks = first_cached_tasks(raw)
    if len(tasks) != 1:
        raise ValueError('The raw log slice does not contain exactly one inference request')
    task = tasks[0]
    count = task.get('cached_tokens')
    if (task['slot_id'] != 0 or task.get('prompt_tokens') != expected_tokens or 'end' not in task
            or type(count) is not int or not 0 <= count < expected_tokens):
        raise ValueError('The task lacks a valid initial cached-token observation')
    return task


def verify(evidence):
    """Check both CPU runs from their inputs and logs, without requiring a live server."""
    model = evidence['model']
    size, window = model['bytes'], model['window_tokens']
    if type(size) is not int or not 0 < size < 1_000_000_000 or type(window) is not int or window <= 0:
        raise ValueError('The fixture requires a sub-1 GB model with sliding-window attention')
    model_sha = model['sha256']
    executable_sha = evidence['executable_sha256']
    if not all(isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{64}', sha)
               for sha in (model_sha, executable_sha)):
        raise ValueError('The fixture requires the model and executable SHA-256 values')
    configurations = evidence['configurations']
    if set(configurations) != {'stock', 'configured'}:
        raise ValueError('Expected stock and configured CPU runs')
    first, follow = evidence['request_tokens']
    if not first or not follow or any(type(t) is not int for t in [*first, *follow]):
        raise ValueError('Expected two real token ID sequences')
    shared = sum(1 for _ in takewhile(lambda pair: pair[0] == pair[1], zip(first, follow)))
    if not window < shared < min(len(first), len(follow)) or abs(shared / window - 1.5) > 0.1:
        raise ValueError('Expected two distinct questions sharing approximately 1.5 attention windows')
    results = {}
    for name, record in configurations.items():
        logs = record['request_logs']
        if len(logs) != 2:
            raise ValueError('Expected exactly two CPU fixture requests')
        if record['model_sha256'] != model_sha or record['executable_sha256'] != executable_sha:
            raise ValueError('Expected both configurations to use the same pinned model and executable')
        expected_flags = ['--swa-full', '--ctx-checkpoints', '32'] if name == 'configured' else []
        if record['extra_args'] != expected_flags or record['cache_prompt'] is not True:
            raise ValueError('Expected the prescribed cache and configuration flags')
        startup = record['startup_log']
        full_swa = verify_mode(startup, window, configured=name == 'configured')
        seed = read_request_cache(logs[0].encode(), len(first))
        reuse = read_request_cache(logs[1].encode(), len(follow))
        if seed['cached_tokens'] != 0 or seed['task_id'] == reuse['task_id'] or reuse['cached_tokens'] > shared:
            raise ValueError('The cache observations do not describe the supplied two-request prefix')
        results[name] = dict(cached_tokens=reuse['cached_tokens'], prompt_tokens=len(follow),
                             full_swa=full_swa, checkpoints_max=_checkpoint_limit(startup),
                             first_cache_line=reuse['cache_line'])
    return dict(stage='factory', shared_prefix_tokens=shared, configurations=results,
                cached_tokens_delta=results['configured']['cached_tokens'] - results['stock']['cached_tokens'])
