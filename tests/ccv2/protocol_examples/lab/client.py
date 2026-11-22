"""Synthetic Lab client; does not claim inference, SOL or internal tracing."""
import json
import sys
import time
import urllib.parse
import urllib.request

packet = json.load(sys.stdin)
target = packet['resources'][packet['inputs']['engine']]
if packet['capability'] == 'observe':
    print(json.dumps({'outcome': 'partial', 'outputs': {'report': {
        'instance': target['instance'], 'coverage': 'unavailable', 'scope': 'internal traces',
        'reason': 'No internal instrumentation is supplied by this fixture'}},
        'reason': 'Internal telemetry unavailable; independent benchmark can proceed'}))
else:
    values = []
    started = time.perf_counter()
    try:
        for point in packet['inputs']['workload']['points']:
            with urllib.request.urlopen(target['url']+'compute?'+urllib.parse.urlencode({'x': point}), timeout=2) as response:
                values.append(json.load(response)['value'])
        print(json.dumps({'outcome': 'ok', 'outputs': {'metrics': {
            'instance': target['instance'], 'count': len(values), 'values': values,
            'client_ms': (time.perf_counter()-started)*1000,
            'scope': 'Synthetic loopback requests including client overhead'}}}))
    except Exception as error:
        print(json.dumps({'outcome': 'partial', 'outputs': {'metrics': {
            'instance': target['instance'], 'count': len(values), 'values': values}},
            'reason': 'Incomplete workload: '+type(error).__name__}))
