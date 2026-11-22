"""Standalone native CC packet entrypoint."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from components import dispatch
if __name__ == '__main__':
    try:
        packet = json.load(sys.stdin)
        result = dispatch(packet['capability'], packet['inputs']['inputs'])
        output = {'outcome': 'ok', 'outputs': {'result': result}}
    except Exception as error:
        output = {'outcome': 'error', 'outputs': {}, 'reason': str(error),
                  'error': {'code': 'INVALID_INPUT', 'message': str(error)}}
    print(json.dumps(output))
