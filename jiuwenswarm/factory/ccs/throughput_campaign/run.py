import json
import os
import sys

from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.throughput_campaign import Campaign

packet = json.load(sys.stdin)
try:
    with Store(os.environ['FACTORY_HOME']) as store:
        campaign = Campaign(store, os.environ['FACTORY_TASK_ID'])
        operation = packet['capability']
        if operation not in {'submit', 'status', 'result', 'cancel'}:
            raise ValueError('Unknown campaign operation')
        result = getattr(campaign, operation)(**packet['inputs'])
    print(json.dumps({'outcome': 'ok', 'outputs': {'result': result}}))
except Exception as error:
    print(json.dumps({'outcome': 'error', 'error': {'code': 'CAMPAIGN_REJECTED', 'message': str(error)}}))
