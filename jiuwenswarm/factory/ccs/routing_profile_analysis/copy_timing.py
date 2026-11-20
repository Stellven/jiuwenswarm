"""Relate a shape-matched copy replay to its recorder probe."""
import json
import math
from pathlib import Path
from statistics import median

from routing_profile import read_pinned


GB = 10**9
LIMITATION = (
    'The copy replay uses a reusable CUDA buffer, one stream and a synchronization at each group. '
    'It includes replay dispatch overhead and page residency effects without concurrent graph execution. '
    'The C1 trace counts submitted H2D expert bytes, including padding, but has no copy completion spans. '
    'Each consuming CUDA graph split depends on its weight uploads. Overlap of other work in the probe '
    'is unmeasured. The replay time and its ratio to TTFT provide an isolated serial-copy equivalent, '
    'with no measured latency attribution or speedup. Later-pass residency and stability are unproven.'
)


def positive_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def timing(transfer, replay, request, activation, baseline, hashes):
    if transfer['schema'] != 'routing-profile-transfer/1' or transfer['capture_state'] != 'complete_as_reported':
        raise ValueError('Expected a complete transfer report')
    bytes_ = transfer['known_submitted_copy_bytes']
    phases = transfer['submitted_copy_by_dispatch_phase']
    if (not positive_number(bytes_) or transfer['unknown_copy_events'] != 0
            or phases['prefill']['known_submitted_copy_bytes'] != bytes_
            or replay['schema'] != 'spark-mmap-expert-copy-replay/1'
            or replay['event_sha256'] != transfer['sha256']['trace']
            or replay['submitted_bytes'] != bytes_):
        raise ValueError('Replay must match the complete prefill copy trace and its byte total')
    if not all(type(replay[field]) is int and replay[field] > 0 for field in ('groups', 'copy_calls')):
        raise ValueError('Replay must record positive measured copy and group counts')
    command = activation['command']
    if (activation['arm'] != request['arm'] or Path(activation['result_path']).name != Path(request['request_path']).parent.parent.name
            or '--cpu-moe' not in command or '-lm' not in command or command[command.index('-lm') + 1:][:1] != ['mmap']
            or any(arg.startswith(('--moe-cache', '-moe-cache')) for arg in command)):
        raise ValueError('Request must match the C1 activation run using strict stock mmap placement')
    ttft = request['ttft_s']
    prompt_ms = request['timings']['prompt_ms']
    tokens = request['prompt_tokens']
    if (request['ok'] is not True or not positive_number(ttft) or not positive_number(prompt_ms)
            or request['timings']['prompt_n'] != tokens or request['timings']['cache_n'] != 0):
        raise ValueError('Expected a successful prompt of the exact token count without prompt-cache reuse')
    samples = []
    if len(replay['samples']) < 2:
        raise ValueError('Expected an initial residency-uncontrolled and later warm copy sample')
    for i, sample in enumerate(replay['samples']):
        seconds = sample['wall_s']
        rate = sample['measured_GB_s']
        if (sample['pass_index'] != i or not positive_number(seconds) or not positive_number(rate)
                or not math.isclose(rate, bytes_ / seconds / GB, rel_tol=1e-9)):
            raise ValueError('Replay rate or sample index does not reconcile')
        samples.append({
            'pass_index': i,
            'residency': 'initial_uncontrolled' if i == 0 else 'later_replay',
            'measured_bandwidth_bytes_per_second': rate * GB,
            'serial_copy_equivalent_seconds': bytes_ / (rate * GB),
            'serial_copy_equivalent_fraction_of_c1_ttft': bytes_ / (rate * GB * ttft),
        })
    warm_rate = median(row['measured_bandwidth_bytes_per_second'] for row in samples[1:])
    if not math.isclose(warm_rate, replay['warm_median_GB_s'] * GB, rel_tol=1e-9):
        raise ValueError('Reported warm median does not match replay samples')
    warm_equivalent = bytes_ / warm_rate

    baseline_rows = [row for row in baseline['summary'] if row['arm'] == 'A' and row['prompt_tokens'] == tokens]
    if len(baseline_rows) != 1 or not positive_number(baseline_rows[0]['ttft_s']):
        raise ValueError('Expected the corresponding historical A warm summary')
    return {
        'schema': 'routing-copy-timing/1',
        'kind': 'analysis',
        'title': 'Shape-matched expert upload replay and C1 first-token latency',
        'sha256': hashes,
        'path': {
            'id': 'cuda-h2d-host-weight-to-device',
            'source': 'Original converted GGUF mapped as pageable host memory',
            'destination': 'Reusable CUDA device buffer on the Spark GB10',
            'api': 'cudaMemcpyAsync(cudaMemcpyHostToDevice), synchronized per replay layer/microbatch group',
            'replay_scope': replay['scope'],
        },
        'prefill_submitted_bytes': bytes_,
        'replay_groups': replay['groups'],
        'replay_copy_calls': replay['copy_calls'],
        'rows': samples,
        'qualifying_bandwidth_bytes_per_second': warm_rate,
        'serial_copy_equivalent_seconds': warm_equivalent,
        'serial_copy_equivalent_fraction_of_c1_ttft': warm_equivalent / ttft,
        'matched_c1': {
            'arm': request['arm'],
            'prompt_tokens': tokens,
            'binary_sha256': activation['binary_sha256'],
            'ttft_s': ttft,
            'engine_prompt_seconds': prompt_ms / 1000,
            'submitted_bytes_per_ttft_second': bytes_ / ttft,
        },
        'historical_a_warm_context': {
            'prompt_tokens': tokens,
            'ttft_median_s': baseline_rows[0]['ttft_s'],
            'n': baseline_rows[0]['n'],
            'basis': 'P1 warm reconnaissance; excluded from the replay equivalence ratios.',
        },
        'limitations': LIMITATION,
    }


def timing_artifacts(artifacts):
    hashes = {name: item['sha256'] for name, item in artifacts.items()}
    inputs = {
        name: json.loads(read_pinned(item['path'], hashes[name], 8 * 1024**2))
        for name, item in artifacts.items()
    }
    return timing(**inputs, hashes=hashes)
