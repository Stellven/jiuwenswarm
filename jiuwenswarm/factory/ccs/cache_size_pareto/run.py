"""Native cache-size analysis and exact recomputation."""
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

from cache_size_pareto import summarize


def dispatch(packet):
    inputs = packet['inputs']
    uri = urlparse(inputs['evidence']['uri'])
    if uri.scheme != 'file' or uri.netloc:
        raise ValueError('Expected a host-materialized evidence artifact')
    data = Path(unquote(uri.path)).read_bytes()
    if len(data) > 4 * 1024**2:
        raise ValueError('Evidence is larger than 4 MiB')
    report = summarize(json.loads(data))
    if packet['capability'] == 'analyze':
        return {'report': report}
    if packet['capability'] == 'verify':
        return {'verification': {'done': report == inputs['report'], 'method': 'exact deterministic recomputation'}}
    raise ValueError('Unknown cache Pareto capability')


if __name__ == '__main__':
    try:
        result = {'outcome': 'ok', 'outputs': dispatch(json.load(sys.stdin))}
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        result = {'outcome': 'error', 'error': {'code': 'INVALID_EVIDENCE', 'message': str(exc)}}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
