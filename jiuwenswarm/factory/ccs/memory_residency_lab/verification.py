import json,random
from pathlib import Path
from components.implementation import plan,verify,native_experiment

def checks():
    r=random.Random(472)
    for trial in range(25):
        a=[]
        for i in range(12):
            start=r.randrange(12);a.append(dict(name=str(i),bytes=r.randrange(1,512),start=start,end=start+r.randrange(1,6)))
        out=verify(dict(tensors=a,alignment=64))
        assert out['correct'] and out['arena_bytes']>=out['peak_live_payload_lower_bound']
        assert all(t['offset']%64==0 for t in out['allocations'])
    disjoint=dict(tensors=[dict(name='a',bytes=1024,start=0,end=1),dict(name='b',bytes=1024,start=1,end=2)])
    assert plan(disjoint)['arena_bytes']==1024
    overlap=dict(tensors=[dict(name='a',bytes=1024,start=0,end=2),dict(name='b',bytes=1024,start=1,end=3)])
    assert plan(overlap)['arena_bytes']==2048
    for bad in [dict(tensors=[]),dict(disjoint,alignment=3),dict(tensors=[dict(name='a',bytes=10,start=1,end=1)]),dict(tensors=[dict(name='a',bytes=True,start=0,end=1)])]:
        try:plan(bad)
        except ValueError:pass
        else:raise AssertionError('invalid request accepted')
    print(json.dumps(dict(passed=True,random_liveness_cases=25,scope='CPU reference only; native experiment separate')))
if __name__=='__main__':checks()
