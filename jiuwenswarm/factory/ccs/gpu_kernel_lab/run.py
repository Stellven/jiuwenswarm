import json,sys
from pathlib import Path
from components import implementation
CAPABILITIES = ['evaluate', 'benchmark']
def dispatch(capability,data):
    if capability not in CAPABILITIES: raise ValueError('unknown capability')
    if not isinstance(data,dict): raise ValueError('request must be object')
    return getattr(implementation,capability)(data)
if __name__=='__main__':
    try:
        raw=sys.stdin.read(2000001)
        if len(raw)>2000000: raise ValueError('packet too large')
        p=json.loads(raw)
        if p['capability']=='benchmark':
            handle=p.get('inputs',{}).get('gpu')
            if not isinstance(handle,str) or p.get('resources',{}).get(handle,{}).get('kind')!='gpu':
                raise ValueError('benchmark requires host-bound GPU handle, gpu.use grant and an exclusive operator-scheduled measurement slot; forbidden in CPU-only missions')
        if p['capability'] == 'trace_dispatch':
            from components.muse_dispatch import load, result
            fixtures = Path(__file__).parent / 'fixtures'
            outputs = result(p['inputs']['request'], load(fixtures / 'muse_dispatch_pins.json'),
                             fixtures / 'muse_dispatch.cpp')
        elif p['capability'] == 'verify_candidate':
            from components.candidate import verify_candidate

            outputs = verify_candidate(**p['inputs'])
        else:
            outputs = {'result': dispatch(p['capability'], p['inputs']['request'])}
        reply={'outcome':'ok','outputs':outputs}
    except Exception as e: reply={'outcome':'error','outputs':{},'error':{'code':'INVALID_REQUEST','message':str(e)}}
    print(json.dumps(reply,allow_nan=False))
