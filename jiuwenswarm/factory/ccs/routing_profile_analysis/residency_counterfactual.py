"""Model captured upload payloads with fixed expert residency."""
import itertools
import json

from copy_timing import positive_number
from routing_profile import indexed_expert_roles, read_pinned
from routing_transfer import ROUTE_PHASES, rank_tiers, tagged_routes, uint


LIMITATION = (
    'The modeled resident experts are assumed to hit in every eligible group. '
    'The model omits placement setup, eviction, cache admission, induced copies, altered kernel work and any change '
    'in copy rate as call sizes change. Avoided bytes divided by replay rate describe the serial-copy '
    'opportunity within this assumption, without observed latency gains. Actual C1 zero-byte events are excluded.'
)


def upload_cost(experts, strides, width):
    """Reconstruct contiguous ID group count and bytes, including tail padding."""
    calls, bytes_ = 0, 0
    for _, group in itertools.groupby(enumerate(sorted(experts)), key=lambda pair: pair[1] - pair[0]):
        consecutive = [expert for _, expert in group]
        padding = sum(min(512, stride) for stride in strides) if consecutive[-1] + 1 < width else 0
        calls += len(strides)
        bytes_ += len(consecutive) * sum(strides) + padding
    return calls, bytes_


def compare(trace, ranks, transfer, tensor_index, timing, hashes):
    ks, ranking, width = rank_tiers(ranks)
    if (timing['schema'] != 'routing-copy-timing/1' or timing['sha256']['transfer'] != hashes['transfer']
            or timing['prefill_submitted_bytes'] <= 0):
        raise ValueError('Expected exact copy timing report for the compared trace')
    if (transfer['schema'] != 'routing-profile-transfer/1' or transfer['capture_state'] != 'complete_as_reported'
            or transfer['sha256'] != {'trace': hashes['trace'], 'ranks': hashes['ranks']}):
        raise ValueError('Trace and ranks must match the verified transfer report')
    if ranks['sha256']['tensor_index'] != hashes['tensor_index']:
        raise ValueError('Rank and tensor index inputs differ')
    weight_roles = indexed_expert_roles(tensor_index, len(ranking), width)
    strides_by_layer = []
    for layer in range(len(ranking)):
        strides = [weight_roles[layer, 0, role] for role in (1, 2, 3)]
        if any(weight_roles[layer, expert, role] != strides[role - 1]
               for expert in range(width) for role in (1, 2, 3)):
            raise ValueError('Selected pack lacks uniform expert role strides for a layer')
        strides_by_layer.append(strides)
    groups = 0
    events = 0
    baseline_calls = 0
    baseline_bytes = 0
    counterfactual = {k: {'calls': 0, 'bytes': 0} for k in ks}
    seen = set()
    summary = None
    for line in trace.splitlines():
        event = json.loads(line)
        if summary is not None:
            raise ValueError('Recorder summary must be final')
        if event['type'] == 'summary':
            summary = event
            continue
        if event['type'] != 'event':
            raise ValueError('Unexpected recorder event type')
        layer = event['layer']
        key = layer, event['microbatch']
        if not uint(layer) or not uint(event['microbatch']) or key in seen:
            raise ValueError('Invalid or repeated recorder group')
        seen.add(key)
        events += 1
        bytes_ = event['bytes_transferred']
        if not uint(bytes_):
            raise ValueError('Counterfactual requires known copy bytes for every event')
        if bytes_ == 0:
            continue
        if event['phase'] != 'prefill' or layer >= len(ranking):
            raise ValueError('Copy timing report is scoped to nonzero known prefill uploads')
        phase_counts = tagged_routes(event)
        selected = set(phase_counts['prefill'])
        if any(expert >= width for expert in selected) or any(phase_counts[phase] for phase in ROUTE_PHASES[1:]):
            raise ValueError('Nonzero group does not map to the prefill rank domain')
        strides = strides_by_layer[layer]
        calls, baseline = upload_cost(selected, strides, width)
        if baseline != bytes_:
            raise ValueError(f'Indexed role strides do not reproduce recorded bytes at {key}')
        groups += 1
        baseline_calls += calls
        baseline_bytes += baseline
        for k, result in counterfactual.items():
            remaining = {expert for expert in selected if ranking[layer].get(expert, width + 1) > k}
            calls, remaining_bytes = upload_cost(remaining, strides, width)
            result['calls'] += calls
            result['bytes'] += remaining_bytes
    if (summary is None or summary['lost'] != 0 or summary['transfer_incomplete'] != 0
            or summary['written'] != events or summary['expected'] != events or summary['bytes_transferred'] != baseline_bytes):
        raise ValueError('Recorder summary does not reconcile with the original copy path')
    if (groups != timing['replay_groups'] or baseline_calls != timing['replay_copy_calls']
            or baseline_bytes != timing['prefill_submitted_bytes']):
        raise ValueError('Reconstructed nonzero groups, bytes or copy count differs from measured replay')
    bandwidth = timing['qualifying_bandwidth_bytes_per_second']
    ttft = timing['matched_c1']['ttft_s']
    if not positive_number(bandwidth) or not positive_number(ttft):
        raise ValueError('Missing qualified measured copy bandwidth or matched TTFT')
    rows = []
    for k, result in counterfactual.items():
        avoided = baseline_bytes - result['bytes']
        rows.append({
            'k_per_layer': k,
            'indexed_resident_payload_bytes': next(row['indexed_payload_bytes'] for row in ranks['rows'] if row['k_per_layer'] == k),
            'modeled_remaining_upload_bytes': result['bytes'],
            'modeled_remaining_upload_calls': result['calls'],
            'modeled_avoided_upload_bytes': avoided,
            'modeled_avoided_upload_fraction': avoided / baseline_bytes,
            'modeled_upload_call_reduction': baseline_calls - result['calls'],
            'serial_copy_equivalent_reduction_seconds_at_later_median': avoided / bandwidth,
            'serial_copy_equivalent_reduction_fraction_of_c1_ttft': avoided / (bandwidth * ttft),
        })
    return {
        'schema': 'routing-residency-counterfactual/1',
        'kind': 'analysis',
        'title': 'Modeled expert upload opportunity from a fixed resident set',
        'sha256': hashes,
        'nonzero_prefill_groups': groups,
        'zero_copy_events_excluded': events - groups,
        'recorded_upload_bytes': baseline_bytes,
        'reconstructed_upload_calls': baseline_calls,
        'measured_later_median_bandwidth_bytes_per_second': bandwidth,
        'matched_c1_ttft_s': ttft,
        'rows': rows,
        'limitations': LIMITATION,
    }


def compare_artifacts(artifacts):
    hashes = {name: item['sha256'] for name, item in artifacts.items()}
    def read(name):
        item = artifacts[name]
        return read_pinned(item['path'], item['sha256'], 64 * 1024**2)

    return compare(read('trace'), json.loads(read('ranks')), json.loads(read('transfer')),
                   read('tensor_index').decode(), json.loads(read('timing')), hashes)
