"""Offline temporal holdout evaluation, not an inference speed experiment."""
from collections import Counter, defaultdict
import hashlib
import json

MAX_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 10000


def _int(value, name, maximum=2**63-1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(name + ' must be a bounded nonnegative integer')
    return value


def _fields(value, required):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError('Trace fields differ from schema: ' + ', '.join(required))


def validate(trace):
    """Require complete request separation and causal timestamp ordering."""
    _fields(trace, ('schema_version', 'origin', 'requests'))
    if trace['schema_version'] != 1 or type(trace['schema_version']) is not int:
        raise ValueError('Unsupported prediction trace schema version')
    if trace['origin'] not in ('synthetic', 'recorded'):
        raise ValueError('Trace origin must explicitly be synthetic or recorded')
    requests = trace['requests']
    if not isinstance(requests, list) or not 2 <= len(requests) <= 128:
        raise ValueError('Supply 2..128 disjoint train/test requests')
    ids = set()
    count = 0
    train_end, test_start = [], []
    test_seen = False
    for request in requests:
        _fields(request, ('request_id', 'split', 'events'))
        rid = request['request_id']
        if not isinstance(rid, str) or not 1 <= len(rid) <= 128 or rid in ids:
            raise ValueError('Request IDs must be bounded and unique')
        ids.add(rid)
        split = request['split']
        if split not in ('train', 'test') or split == 'train' and test_seen:
            raise ValueError('All complete training requests must precede test requests')
        test_seen |= split == 'test'
        events = request['events']
        if not isinstance(events, list) or not events:
            raise ValueError('Each request requires events')
        previous = {}
        previous_demand = -1
        for event in events:
            count += 1
            if count > MAX_EVENTS:
                raise ValueError('Trace exceeds 10000 events')
            _fields(event, ('phase', 'token', 'layer', 'issued_ns', 'demand_ns', 'selected', 'predicted'))
            phase = event['phase']
            if phase not in ('prefill', 'decode'):
                raise ValueError('Explicit prefill/decode phase required')
            token = _int(event['token'], 'token', 1000000)
            layer = _int(event['layer'], 'layer', 4095)
            issued = _int(event['issued_ns'], 'issued_ns')
            demand = _int(event['demand_ns'], 'demand_ns')
            if issued > demand or demand < previous_demand:
                raise ValueError('Noncausal issue/demand timestamps or unsorted events')
            key = (phase, layer)
            if token <= previous.get(key, -1):
                raise ValueError('Tokens must increase within each phase/layer')
            previous[key] = token
            previous_demand = demand
            selected, predicted = event['selected'], event['predicted']
            if (not isinstance(selected, list) or not 1 <= len(selected) <= 64 or
                not isinstance(predicted, list) or len(predicted) > 64):
                raise ValueError('Selected/predicted expert lists exceed bounds')
            selected_bytes = {}
            for rows, prediction in ((selected, False), (predicted, True)):
                seen = set()
                for row in rows:
                    _fields(row, ('expert', 'bytes', 'ready_ns') if prediction else ('expert', 'bytes'))
                    expert = _int(row['expert'], 'expert', 1000000)
                    size = _int(row['bytes'], 'bytes', 2**40)
                    if not size or expert in seen:
                        raise ValueError('Duplicate expert or empty expert byte count')
                    seen.add(expert)
                    if prediction:
                        ready = row['ready_ns']
                        if ready is not None and _int(ready, 'ready_ns') < issued:
                            raise ValueError('Read readiness precedes prediction issue')
                        if expert in selected_bytes and selected_bytes[expert] != size:
                            raise ValueError('Selected/predicted expert byte counts differ')
                    else:
                        selected_bytes[expert] = size
            (train_end if split == 'train' else test_start).append(demand if split == 'train' else issued)
    if not train_end or not test_start or max(train_end) >= min(test_start):
        raise ValueError('Training evidence must finish before every holdout prediction issue')
    return requests


def evaluate(trace, k=6):
    _int(k, 'k', 64)
    if k == 0:
        raise ValueError('k must be 1..64')
    if len(json.dumps(trace, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError('Prediction trace exceeds 8 MiB')
    requests = validate(trace)
    frequency = defaultdict(Counter)
    for request in requests:
        if request['split'] == 'train':
            for event in request['events']:
                frequency[(event['phase'], event['layer'])].update(row['expert'] for row in event['selected'])
    policies = {name: dict(selected=0, hits=0, events=0, empty_predictions=0)
                for name in ('observed', 'last_token', 'frequency')}
    timely_hits = waste_bytes = requested_unused_bytes = prediction_bytes = 0
    test_requests = 0
    for request in requests:
        if request['split'] != 'test':
            continue
        test_requests += 1
        history = {}
        for event in request['events']:
            key = (event['phase'], event['layer'])
            chosen = {row['expert'] for row in event['selected']}
            previous = history.get(key)
            last = previous['selected'] if previous and previous['demand_ns'] <= event['issued_ns'] else []
            ids = {
                'observed': [row['expert'] for row in event['predicted'][:k]],
                'last_token': [row['expert'] for row in last[:k]],
                'frequency': [expert for expert, _ in sorted(frequency[key].items(), key=lambda pair: (-pair[1], pair[0]))[:k]],
            }
            for name, predicted in ids.items():
                metric = policies[name]
                metric['selected'] += len(chosen)
                metric['hits'] += len(chosen.intersection(predicted))
                metric['events'] += 1
                metric['empty_predictions'] += not predicted
            for row in event['predicted'][:k]:
                prediction_bytes += row['bytes']
                timely = row['ready_ns'] is not None and row['ready_ns'] <= event['demand_ns']
                if row['expert'] in chosen:
                    timely_hits += timely
                else:
                    requested_unused_bytes += row['bytes']
                    if timely:
                        waste_bytes += row['bytes']
            # Update only after scoring. A future token's choices never train
            # the last-token policy; frozen frequency never learns test data.
            history[key] = event
    for name, metric in policies.items():
        metric['coverage_at_k'] = metric['hits'] / metric['selected']
        metric['timely_coverage_at_k'] = timely_hits / metric['selected'] if name == 'observed' else None
        metric['waste_bytes_at_demand'] = waste_bytes if name == 'observed' else None
    return dict(schema_version=1, origin=trace['origin'], k=k, scoring_eligible=False,
                performance_gain='not_established', test_requests=test_requests, policies=policies,
                observed_bytes=dict(prediction_requested=prediction_bytes,
                    requested_but_unselected=requested_unused_bytes,
                    completed_by_demand_but_unselected=waste_bytes),
                split='Complete request temporal holdout; frequency frozen on training requests.',
                limitations=[
                    'Recorded origin is caller metadata; authenticity and capture completeness require independent host provenance.',
                    'Coverage counts selected expert IDs, not execution time or model quality.',
                    'Counterfactual baselines have no measured read schedule; their timely coverage and byte waste remain unknown.',
                    'Waste is completed bytes unused by this demand, not proven lifetime waste; later reuse is unknown.',
                    'Null readiness means no completion observed by demand; event capture must retain complete coverage.',
                ])


def dispatch(store, task_id, capability, inputs):
    from .api import fields
    if capability != 'evaluate':
        raise ValueError('Unknown expert_prediction capability')
    fields(inputs, {'artifact_id', 'k'}, {'artifact_id'})
    ref = inputs['artifact_id']
    if not isinstance(ref, str) or not ref:
        raise ValueError('artifact_id must be a nonempty scoped artifact reference')
    raw = store.artifact_bytes(task_id, ref)
    if len(raw) > MAX_BYTES:
        raise ValueError('Prediction trace exceeds 8 MiB')
    result = evaluate(json.loads(raw), inputs.get('k', 6))
    result['source_sha256'] = hashlib.sha256(raw).hexdigest()
    evidence = store.append_observation(task_id, dict(kind='expert_prediction_offline', values=result,
        source_artifacts=[ref], limitations='Offline predictor evidence only; no inference speed claim.'))
    return dict(analysis=result, evidence=evidence)
