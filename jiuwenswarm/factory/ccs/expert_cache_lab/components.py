"""Original CPU reference algorithms; no framework, host or GPU dependencies."""
from collections import Counter, defaultdict


def integer(value, name, low=0, high=2**53):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name + ' must be a bounded integer')
    return value


def validate(inputs):
    rows = inputs['trace']
    if not isinstance(rows, list) or len(rows) > 100000:
        raise ValueError('trace must have at most 100000 events')
    layers = integer(inputs.get('layers', 40), 'layers', 1, 10000)
    experts = integer(inputs.get('experts', 384), 'experts', 1, 100000)
    sizes, last, previous = {}, {}, -1
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('event must be an object')
        seq = integer(row['seq'], 'seq')
        if seq <= previous:
            raise ValueError('seq must be globally strictly increasing')
        previous = seq
        request = row['request']
        if not isinstance(request, str) or not request or len(request) > 128:
            raise ValueError('request must be a bounded nonempty string')
        token = integer(row['token'], 'token')
        layer = integer(row['layer'], 'layer', 0, layers - 1)
        expert = integer(row['expert'], 'expert', 0, experts - 1)
        size = integer(row['bytes'], 'bytes', 1)
        key = (layer, expert)
        if key in sizes and sizes[key] != size:
            raise ValueError('expert byte size changed')
        sizes[key] = size
        if token < last.get(request, -1):
            raise ValueError('request tokens must not go backwards')
        last[request] = token
        normalized.append(dict(seq=seq, request=request, token=token, layer=layer, expert=expert, bytes=size))
    return normalized


class NextExpertPredictor:
    """Request/layer scoped first-order transitions, updated only after prediction."""
    def __init__(self):
        self.transitions = defaultdict(Counter)
        self.previous = {}
        self.frequency = defaultdict(Counter)

    def predict(self, request, layer, count=1):
        previous = self.previous.get((request, layer))
        scores = self.transitions.get((layer, previous), {}) or self.frequency.get(layer, {})
        return [e for e, _ in sorted(scores.items(), key=lambda p: (-p[1], p[0]))[:count]]

    def observe(self, row):
        scope = (row['request'], row['layer'])
        previous = self.previous.get(scope)
        if previous is not None:
            self.transitions[(row['layer'], previous)][row['expert']] += 1
        self.frequency[row['layer']][row['expert']] += 1
        self.previous[scope] = row['expert']


def predict(inputs):
    rows = validate(inputs)
    split = integer(inputs.get('train_events', 0), 'train_events', 0, len(rows))
    count = integer(inputs.get('top_k', 6), 'top_k', 1, inputs.get('experts', 384))
    groups, seen = [], set()
    for row in rows:
        key = (row['request'], row['token'], row['layer'])
        if not groups or groups[-1][0] != key:
            if key in seen:
                raise ValueError('prediction requires contiguous atomic request/token/layer groups')
            seen.add(key)
            groups.append((key, []))
        groups[-1][1].append(row)
    boundary = 0
    boundaries = {0}
    for key, group in groups:
        ids = [row['expert'] for row in group]
        if len(set(ids)) != len(ids):
            raise ValueError('duplicate selected expert in atomic group')
        boundary += len(group)
        boundaries.add(boundary)
    if split not in boundaries:
        raise ValueError('train_events must fall on an atomic group boundary')
    heldout = inputs.get('evaluation_requests')
    if heldout is not None:
        if not isinstance(heldout, list) or not heldout or any(not isinstance(r, str) for r in heldout):
            raise ValueError('evaluation_requests must be a nonempty request ID list')
        if split:
            raise ValueError('use request holdout or train_events, not both')
        unknown = set(heldout) - {r['request'] for r in rows}
        if unknown:
            raise ValueError('unknown evaluation request')
        # Strict request separation; all reference requests are a training corpus.
        training = [g for g in groups if g[0][0] not in heldout]
        evaluation = [g for g in groups if g[0][0] in heldout]
        if not training:
            raise ValueError('request holdout needs distinct training requests')
        ordered = [(g, False) for g in training] + [(g, True) for g in evaluation]
    else:
        ordered, consumed = [], 0
        for g in groups:
            ordered.append((g, consumed >= split))
            consumed += len(g[1])
    previous, transitions, frequency = {}, defaultdict(Counter), defaultdict(Counter)
    results = []
    for (key, group), evaluate_group in ordered:
        request, token, layer = key
        scope = (request, layer)
        before = previous.get(scope)
        scores = transitions.get((layer, before), {}) or frequency.get(layer, {})
        guesses = [e for e, _ in sorted(scores.items(), key=lambda p: (-p[1], p[0]))[:count]]
        actual = sorted(row['expert'] for row in group)
        if evaluate_group:
            results.append(dict(seq=group[0]['seq'], request=request, token=token,
                                layer=layer, predicted=guesses, actual=actual,
                                hits=len(set(guesses) & set(actual)), selected_count=len(actual)))
        # Frozen request holdout never trains on evaluation request labels.
        if heldout is None or not evaluate_group:
            if before is not None:
                transitions[(layer, before)].update(actual)
            frequency[layer].update(actual)
        previous[scope] = tuple(actual)
    return dict(mode='request_separated_frozen_holdout' if heldout is not None else 'causal_online_group_holdout',
                prediction_unit='atomic request/token/layer expert set; prediction precedes all selected experts',
                train_events=split if heldout is None else sum(len(g[1]) for g in training),
                evaluation_groups=len(results), evaluation_events=sum(r['selected_count'] for r in results),
                hits=sum(r['hits'] for r in results), predictions=results,
                leakage_rule='forecast entire current group before observing any of its expert IDs; no performance claim')


def replay(inputs):
    rows = validate(inputs)
    capacity = integer(inputs.get('capacity_bytes', 0), 'capacity_bytes')
    policy = inputs.get('policy', 'lru')
    if policy not in ('lru', 'lfu', 'hybrid'):
        raise ValueError('policy must be lru, lfu or hybrid')
    cache, frequency = {}, Counter()
    hits = misses = loaded = used = peak = 0
    events = []
    for clock, row in enumerate(rows):
        key, size = (row['layer'], row['expert']), row['bytes']
        hit = key in cache
        hits += hit
        misses += not hit
        frequency[key] += 1
        evicted = []
        if hit:
            cache[key] = (size, clock)
        elif size <= capacity:
            loaded += size
            while used + size > capacity:
                def score(k):
                    b, recent = cache[k]
                    if policy == 'lru': return (recent, k)
                    if policy == 'lfu': return (frequency[k], recent, k)
                    return ((frequency[k] + 1) / b, recent, k)
                victim = min(cache, key=score)
                used -= cache.pop(victim)[0]
                evicted.append(list(victim))
            cache[key] = (size, clock)
            used += size
        else:
            loaded += size  # demand streamed, never admitted
        peak = max(peak, used)
        events.append(dict(seq=row['seq'], hit=hit, resident_bytes=used, evicted=evicted))
    return dict(scope='CPU reference trace replay; no measured inference speedup', policy=policy,
                hits=hits, misses=misses, loaded_bytes=loaded, capacity_bytes=capacity,
                peak_resident_bytes=peak, events=events)


def dispatch(capability, inputs):
    if capability == 'validate':
        rows = validate(inputs)
        return dict(valid=True, events=len(rows), requests=len({r['request'] for r in rows}))
    if capability == 'replay': return replay(inputs)
    if capability == 'predict': return predict(inputs)
    raise ValueError('unknown capability')
