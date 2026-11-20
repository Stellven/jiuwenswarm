#!/usr/bin/env python3
"""Score next-layer expert overlap on complete, ordered JSONL observations."""
import argparse
from collections import Counter, deque
import json
from pathlib import Path


def rank(observations):
    frequency = Counter(expert for ids in observations for expert in ids)
    return set(sorted(frequency, key=lambda expert: (-frequency[expert], expert))[:4])


def replay(lines, layers, bytes_per_expert):
    stats = dict.fromkeys(("requests", "targets", "forecasts", "hits", "misses", "simulated_wasted_bytes"), 0)
    previous = deque(maxlen=2)
    current = []
    seen = set()
    request_id = None
    microbatch = 0
    forecast = set()
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            request, batch, layer, raw_ids = (row[key] for key in ("request", "microbatch", "layer", "experts"))
            if (
                type(request) is not str or not request or type(batch) is not int
                or type(layer) is not int or not isinstance(raw_ids, list) or not raw_ids
                or any(type(expert) is not int or expert < 0 for expert in raw_ids)
            ):
                raise ValueError("invalid observation")
            if request_id != request:
                if current or request in seen:
                    raise ValueError("expected contiguous requests and complete microbatches")
                seen.add(request)
                request_id, microbatch = request, 0
                previous.clear()
                stats["requests"] += 1
            if (batch, layer) != (microbatch, len(current)):
                raise ValueError("expected zero-based microbatches and layers in order")
        except (ValueError, TypeError, KeyError) as error:
            raise ValueError(f"line {number}: {error}") from error

        actual = set(raw_ids)
        if layer:
            stats["targets"] += 1
            stats["hits"] += len(actual & forecast)
            stats["misses"] += len(actual - forecast)
            stats["simulated_wasted_bytes"] += len(forecast - actual) * bytes_per_expert

        current.append(actual)
        if len(current) == layers:
            previous.append(current)
            current = []
            microbatch += 1
        else:
            forecast = rank([actual, *(batch[layer + 1] for batch in previous)])
            stats["forecasts"] += 1

    if current or not seen:
        raise ValueError("expected at least one complete request and no partial microbatch")
    total = stats["hits"] + stats["misses"]
    return {**stats, "coverage": stats["hits"] / total if total else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--layers", type=int, required=True, help="observations per microbatch")
    parser.add_argument("--bytes-per-expert", type=int, required=True, help="uniform simulated byte cost")
    args = parser.parse_args()
    if args.layers < 2 or args.bytes_per_expert <= 0:
        parser.error("require at least two layers and a positive simulated byte cost")
    try:
        with args.trace.open(encoding="utf-8") as trace:
            result = replay(trace, args.layers, args.bytes_per_expert)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
