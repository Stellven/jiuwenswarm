import json,sys
from components import implementation
CAPABILITIES = ['plan', 'verify', 'native_experiment']
def dispatch(capability,data):
    if capability not in CAPABILITIES: raise ValueError('unknown capability')
    if not isinstance(data,dict): raise ValueError('request must be object')
    return getattr(implementation,capability)(data)
if __name__=='__main__':
    try:
        raw=sys.stdin.read(2000001)
        if len(raw)>2000000: raise ValueError('packet too large')
        p=json.loads(raw);result=dispatch(p['capability'],p['inputs']['request'])
        reply={'outcome':'ok','outputs':{'result':result}}
    except Exception as e: reply={'outcome':'error','outputs':{},'error':{'code':'INVALID_REQUEST','message':str(e)}}
    print(json.dumps(reply,allow_nan=False))
