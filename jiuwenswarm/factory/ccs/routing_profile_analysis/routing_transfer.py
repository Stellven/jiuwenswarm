"""Compare historical ranks with the retained llama.cpp recorder trace."""
from collections import Counter
import json

from routing_profile import read_pinned


ROUTE_PHASES = ('prefill', 'decode', 'unknown')
DISPATCH_PHASES = (*ROUTE_PHASES, 'mixed')
LIMITATION = (
    'Coverage uses recorded route IDs and the supplied layer/expert mapping. '
    'A mixed dispatch contributes per-phase unions but its copy bytes cannot be '
    'divided by phase. Known submitted bytes describe this capture; they do not '
    'estimate bandwidth, avoided copies or a cache hit rate. The recorder summary '
    'is self-reported and supplies no independent dispatch coverage proof.'
)


def uint(value):
    return type(value) is int and value >= 0


def rank_tiers(report):
    layers = report['layers']
    experts = report['experts_per_layer']
    ks = sorted(row['k_per_layer'] for row in report['rows'])
    rankings = report['top_expert_ids_by_layer']
    if report['schema'] != 'routing-profile-analysis/1' or not uint(layers) or not uint(experts):
        raise ValueError('Unsupported rank report')
    if not ks or ks[0] < 1 or ks[-1] > experts or len(set(ks)) != len(ks) or len(rankings) != layers:
        raise ValueError('Rank report dimensions differ')
    for ranking in rankings:
        if len(ranking) != ks[-1] or len(set(ranking)) != len(ranking) or any(
                not uint(expert) or expert >= experts for expert in ranking):
            raise ValueError('Invalid expert IDs in ranking')
    rank_by_layer = [{expert: rank for rank, expert in enumerate(ranking, start=1)} for ranking in rankings]
    return ks, rank_by_layer, experts


def tagged_routes(event):
    phase = event['phase']
    routes = event['expert_ids']
    if phase not in DISPATCH_PHASES or not isinstance(routes, list) or not routes:
        raise ValueError('Invalid dispatch phase or empty route rows')
    tags = event.get('rows')
    if tags is None:
        if phase == 'mixed':
            raise ValueError('Mixed dispatch is missing row phases')
        row_phases = [phase] * len(routes)
    else:
        if len(tags) != len(routes):
            raise ValueError('Row tags and routes differ in length')
        row_phases = [tag['phase'] for tag in tags]
        if any(tag not in ROUTE_PHASES or phase not in (tag, 'mixed') for tag in row_phases):
            raise ValueError('Invalid row phase or disagreement with dispatch phase')
    by_phase = {name: Counter() for name in ROUTE_PHASES}
    for tag, experts in zip(row_phases, routes, strict=True):
        if not isinstance(experts, list) or not experts or not all(map(uint, experts)):
            raise ValueError('Invalid or empty expert selection')
        by_phase[tag].update(experts)
    return by_phase


def compare(trace, ranks, hashes):
    ks, ranking, width = rank_tiers(ranks)
    tally = {phase: {'route_rank': Counter(), 'union_rank': Counter()} for phase in ROUTE_PHASES}
    transfers = {phase: {'known_events': 0, 'unknown_events': 0, 'known_submitted_copy_bytes': 0}
                 for phase in DISPATCH_PHASES}
    seen = set()
    excluded_events = 0
    summary = None
    for line in trace.splitlines():
        event = json.loads(line)
        if summary is not None:
            raise ValueError('Recorder summary must be final')
        if event['type'] == 'summary':
            summary = event
            continue
        if event['type'] != 'event':
            raise ValueError('Unknown recorder record')
        microbatch, layer = event['microbatch'], event['layer']
        key = layer, microbatch
        if not uint(layer) or not uint(microbatch) or key in seen:
            raise ValueError('Invalid or duplicate layer/microbatch key')
        seen.add(key)
        by_phase = tagged_routes(event)
        transfer = transfers[event['phase']]
        submitted = event['bytes_transferred']
        if submitted is None:
            transfer['unknown_events'] += 1
        elif uint(submitted):
            transfer['known_events'] += 1
            transfer['known_submitted_copy_bytes'] += submitted
        else:
            raise ValueError('Invalid submitted copy byte count')
        if layer >= len(ranking):
            excluded_events += 1
            continue
        for phase, counts in by_phase.items():
            phase_tally = tally[phase]
            for expert, count in counts.items():
                if expert >= width:
                    raise ValueError('Recorded expert lies outside stated rank dimensions')
                rank = ranking[layer].get(expert, width + 1)
                phase_tally['route_rank'][rank] += count
                phase_tally['union_rank'][rank] += 1

    bytes_known = sum(item['known_submitted_copy_bytes'] for item in transfers.values())
    transfers_unknown = sum(item['unknown_events'] for item in transfers.values())
    capture_state = 'empty' if not seen else 'missing_summary'
    if summary is not None:
        required = ('expected', 'written', 'lost', 'bytes_transferred', 'transfer_incomplete')
        if not all(uint(summary.get(field)) for field in required) or (
                summary['written'] != len(seen) or summary['expected'] != len(seen) + summary['lost']
                or summary['bytes_transferred'] != bytes_known or summary['transfer_incomplete'] != transfers_unknown):
            raise ValueError('Recorder summary does not reconcile with retained events')
        capture_state = 'accounted_loss' if summary['lost'] else 'complete_as_reported' if seen else 'empty'

    rows = []
    for phase, phase_tally in tally.items():
        selections = phase_tally['route_rank']
        unions = phase_tally['union_rank']
        total_selections, total_unions = sum(selections.values()), sum(unions.values())
        for k in ks:
            covered_selections = sum(count for rank, count in selections.items() if rank <= k)
            covered_unions = sum(count for rank, count in unions.items() if rank <= k)
            rows.append({
                'phase': phase, 'k_per_layer': k,
                'route_selections': total_selections, 'covered_route_selections': covered_selections,
                'route_fraction': covered_selections / total_selections if total_selections else None,
                'dispatch_expert_unions': total_unions, 'covered_dispatch_expert_unions': covered_unions,
                'dispatch_expert_union_fraction': covered_unions / total_unions if total_unions else None,
            })
    return {
        'schema': 'routing-profile-transfer/1',
        'kind': 'analysis',
        'title': 'Strata rank coverage on recorded llama.cpp routes',
        'sha256': hashes,
        'capture_state': capture_state,
        'events': len(seen),
        'excluded_unranked_layer_events': excluded_events,
        'recorder_summary': summary,
        'known_submitted_copy_bytes': bytes_known if any(item['known_events'] for item in transfers.values()) else None,
        'unknown_copy_events': transfers_unknown,
        'submitted_copy_by_dispatch_phase': transfers,
        'rows': rows,
        'limitations': LIMITATION,
    }


def compare_artifacts(artifacts):
    hashes = {name: item['sha256'] for name, item in artifacts.items()}
    trace = read_pinned(artifacts['trace']['path'], hashes['trace'], 64 * 1024**2)
    ranks = json.loads(read_pinned(artifacts['ranks']['path'], hashes['ranks'], 8 * 1024**2))
    return compare(trace, ranks, hashes)
