"""Synthetic client timings, not inference performance evidence."""
import json
import math
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen


def percentile(values, quantile):
    # Nearest-rank percentile; no observations => no estimate.
    return sorted(values)[math.ceil(quantile * len(values)) - 1] if values else None


def benchmark(packet):
    target = packet['resources'][packet['inputs']['engine']]
    rows, failure, runtime = [], None, None
    for point in packet['inputs']['workload']['points']:
        started = time.perf_counter()
        try:
            url = target['url'].rstrip('/') + '/compute?' + urlencode({'x': point})
            with urlopen(url, timeout=2) as response:
                result = json.load(response)
            value = result['value']
            if not rows:
                runtime = result.get('runtime')
            rows.append({'point': point, 'value': value,
                         'client_ms': (time.perf_counter() - started) * 1000})
        except Exception as error:
            failure = 'Incomplete workload at point ' + str(point) + ': ' + type(error).__name__ + ': ' + str(error)
            break
    durations = [row['client_ms'] for row in rows]
    metrics = {'count': len(rows), 'values': [row['value'] for row in rows],
               'request_ms': durations, 'p50_client_ms': percentile(durations, .50),
               'p95_client_ms': percentile(durations, .95), 'runtime': runtime,
               'scope': 'Synthetic loopback client timings including client overhead, NOT inference-engine TTFT or token-rate evidence.'}
    output = Path(packet['output_dir'])
    output.mkdir(parents=True, exist_ok=True)
    (output / 'series.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    result = {'outcome': 'partial' if failure else 'ok',
              'outputs': {'metrics': metrics, 'series': {'path': 'series.json'}}}
    if failure:
        result['reason'] = failure
    return result


if __name__ == '__main__':
    try:
        result = benchmark(json.load(sys.stdin))
    except Exception as error:
        result = {'outcome': 'error', 'outputs': {}, 'reason': str(error),
                  'error': {'code': 'BENCHMARK_FAILED', 'message': str(error)}}
    print(json.dumps(result))
