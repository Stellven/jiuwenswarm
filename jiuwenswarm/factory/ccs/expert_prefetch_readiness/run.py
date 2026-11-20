import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

from prefetch import summarize


def dispatch(packet):
    inputs = packet['inputs']
    uri = urlparse(inputs['evidence']['uri'])
    if uri.scheme != 'file' or uri.netloc:
        raise ValueError('Expected a materialized evidence artifact')
    path = Path(unquote(uri.path))
    if path.stat().st_size > 24 * 1024**2:
        raise ValueError('Native predictor evidence exceeds 24 MiB')
    report = summarize(json.loads(path.read_bytes()))
    if packet['capability'] == 'analyze':
        return {'report': report}
    if packet['capability'] == 'verify':
        return {'verification': {'done': report == inputs['report']}}
    raise ValueError('Unknown native predictor analysis capability')


if __name__ == '__main__':
    try:
        reply = {'outcome': 'ok', 'outputs': dispatch(json.load(sys.stdin))}
    except (OSError, TypeError, KeyError, ValueError) as exc:
        reply = {'outcome': 'error', 'error': {'code': 'INVALID_EVIDENCE', 'message': str(exc)}}
    print(json.dumps(reply, allow_nan=False))
