import json,math
from components.implementation import evaluate,normalize

def checks():
    d=dict(experts=2,rows=2,cols=3,tokens=2,top_k=2,weights=[1,2,3,4,5,6,-1,2,-3,4,-5,6],inputs=[1,2,3,-1,-2,-3],routes=[0,1,1,1],gates=[0.75,0.25,0.25,0.75])
    # Independently hand-computed two-expert weighted rows; duplicate second token routes retained.
    assert evaluate(d)['output']==[9.0,27.0,6.0,-12.0]
    z=dict(d,gates=[0,0,0,0]);assert evaluate(z)['output']==[0.0]*4
    for bad in [dict(d,routes=[0,2,1,1]),dict(d,weights=[0]),dict(d,gates=[math.nan]*4),dict(d,top_k=True),dict(d,cols=2049)]:
        try:normalize(bad)
        except ValueError:pass
        else:raise AssertionError('invalid request accepted')
    print(json.dumps(dict(passed=True,checks=7,scope='CPU oracle and input validation; CUDA separate')))
if __name__=='__main__':checks()
