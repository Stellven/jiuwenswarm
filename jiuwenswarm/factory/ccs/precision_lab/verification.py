"""Standalone numerical checks, separate exact/approximation gates."""
import json
from components.precision import quantize, unpack, evaluate, calibrate, memory_plan


def verify():
    zeros=quantize({'values':[0]*7,'block_size':3})
    assert zeros['decoded']==[0]*7 and len(zeros['codec']['packed'])==4
    exact=quantize({'values':[-7,0,7],'block_size':3})
    assert exact['decoded']==[-7,0,7] and exact['codec']['packed']==[9,7]
    for source in ([1e300,-1e300,0],[1e-300,-1e-300,0]):
        result=quantize({'values':source,'block_size':3})
        assert evaluate({'reference':source,'candidate':result['decoded'],'max_abs_budget':1e300})['within_budget']
    metrics=evaluate({'reference':[1,2],'candidate':[1,2.1],'max_abs_budget':0.2})
    assert metrics['approximation_gate'] and not metrics['exact_gate']
    assert calibrate({'values':[0,1,2,7],'block_sizes':[2,4],'max_abs_budget':0})['selected'] is not None
    for source in ([float('nan')],[float('inf')]):
        try:quantize({'values':source})
        except ValueError:pass
        else:raise AssertionError('nonfinite accepted')
    bad=dict(exact['codec'],packed=[8,7])
    try:unpack(bad)
    except ValueError:pass
    else:raise AssertionError('reserved nibble accepted')
    sizes=memory_plan({'weight_elements':3,'block_size':2,'tokens':1,'layers':1,'kv_heads':1,'head_dim':2})
    assert sizes['weight_reference_int4_bytes']==18 and sizes['kv_fp16_bytes']==8
    return {'passed':True,'scope':'cpu_reference_only','checks':9}

if __name__=='__main__':print(json.dumps(verify()))
