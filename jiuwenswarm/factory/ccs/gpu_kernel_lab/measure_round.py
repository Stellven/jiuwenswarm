"""Manual one-round component sweep. Run only in an exclusive GPU slot."""
import hashlib,json,platform,subprocess,sys,time
from pathlib import Path
from components.implementation import benchmark

def case(E,M,K,T,R):
    return dict(experts=E,rows=M,cols=K,tokens=T,top_k=R,weights=[((i*17)%101-50)/128 for i in range(E*M*K)],inputs=[((i*7)%53-26)/64 for i in range(T*K)],routes=[(t+r)%E for t in range(T) for r in range(R)],gates=[(R-r)/(R*(R+1)/2) for t in range(T)for r in range(R)],repeats=100)
if __name__=='__main__':
    if sys.argv[1:]!=['--exclusive-gpu-slot']:raise SystemExit('Run explicitly: python3 measure_round.py --exclusive-gpu-slot')
    base=Path(__file__).resolve().parent;out=[]
    for label,shape in [('small',(4,16,64,4,2)),('decode',(8,64,512,1,4)),('prefill',(8,64,256,16,4)),('tail',(3,19,127,3,2))]:
        request=case(*shape);result=benchmark(request);result.pop('output')
        out.append(dict(case=label,shape=shape,input_generation='case() in measure_round.py',input_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),result=result))
    artifact=dict(format='native-component-round/1',utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),machine=platform.machine(),source_sha256=hashlib.sha256((base/'native_experts.cu').read_bytes()).hexdigest(),binary_sha256=hashlib.sha256((base/'native_experts').read_bytes()).hexdigest(),scope='single fixed-order CUDA component sweep; synthetic inputs; not model throughput',cases=out)
    (base/'ROUND1.json').write_text(json.dumps(artifact,indent=2)+'\n');print(json.dumps(artifact,indent=2))
