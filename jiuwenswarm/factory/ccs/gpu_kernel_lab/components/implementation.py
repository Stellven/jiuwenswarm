"""Finite tensors and fixed bundled native CUDA executable only."""
import math,json,subprocess,platform
from pathlib import Path

def integer(x,lo,hi):
    if type(x)is not int or not lo<=x<=hi: raise ValueError('integer out of bounds')
    return x

def finite_json_number(raw):
    value=float(raw)
    if not math.isfinite(value): raise ValueError('native JSON contains a nonfinite number')
    return value

def tensor(x,n):
    if not isinstance(x,list) or len(x)!=n: raise ValueError('incorrect tensor length')
    if any(type(v)not in(int,float) or not math.isfinite(v) or abs(v)>1e6 for v in x): raise ValueError('bounded finite tensor required')
    return [float(v) for v in x]

def normalize(d):
    if not isinstance(d,dict): raise ValueError('request must be object')
    E=integer(d.get('experts'),1,32);M=integer(d.get('rows'),1,2048);K=integer(d.get('cols'),1,2048);T=integer(d.get('tokens'),1,64);R=integer(d.get('top_k'),1,min(E,8))
    if E*M*K>262144 or T*R*M*K>16777216: raise ValueError('bounded experiment too large')
    w=tensor(d.get('weights'),E*M*K);x=tensor(d.get('inputs'),T*K);g=tensor(d.get('gates'),T*R)
    ids=d.get('routes')
    if not isinstance(ids,list)or len(ids)!=T*R: raise ValueError('incorrect routes length')
    ids=[integer(v,0,E-1) for v in ids]
    return E,M,K,T,R,w,x,g,ids

def evaluate(d):
    E,M,K,T,R,w,x,g,ids=normalize(d);out=[]
    for t in range(T):
        for m in range(M):
            out.append(math.fsum(g[t*R+r]*math.fsum(w[(ids[t*R+r]*M+m)*K+k]*x[t*K+k] for k in range(K))for r in range(R)))
    return {'output':out,'oracle':'CPU float64 math.fsum','route_count':T*R,'preserves_gates':True,'weight_bytes_fp32':len(w)*4,'input_bytes_fp32':len(x)*4,'output_bytes_fp32':len(out)*4,'intermediate_bytes_fp32':T*R*M*4,'qualification':'cpu_reference_only'}

def benchmark(d):
    if platform.system()!='Linux' or platform.machine().lower() not in ('aarch64','arm64'):
        raise ValueError('native CUDA benchmark is qualified only on Linux ARM64 GB10 SM121; evaluate is portable, rebuild/requalify explicitly for another target')
    vals=normalize(d);E,M,K,T,R,w,x,g,ids=vals
    repeats=integer(d.get('repeats',30),5,1000)
    binary=Path(__file__).resolve().parents[1]/'native_experts'
    if not binary.is_file(): raise ValueError('native binary is not bundled; explicitly build native_experts.cu in an authorized build slot using METHOD.md')
    header=binary.read_bytes()[:20]
    if len(header)<20 or header[:4]!=b'\x7fELF' or int.from_bytes(header[18:20],'little' if header[5]==1 else 'big')!=183:
        raise ValueError('native_experts binary is incompatible with Linux ARM64; rebuild the bundled CUDA source explicitly')
    lines=[f'{E} {M} {K} {T} {R} {repeats}']+[' '.join(map(str,a))for a in(w,x,g,ids)]
    p=subprocess.run([str(binary)],input='\n'.join(lines)+'\n',capture_output=True,text=True,timeout=120,check=True)
    result=json.loads(p.stdout,parse_float=finite_json_number,parse_constant=finite_json_number)
    if not isinstance(result,dict): raise ValueError('native result must be an object')
    if result.get('all_variants_correct') is not True:
        raise ValueError('native variants did not pass their independent oracle gate')
    actual=result.pop('output',None)
    if not isinstance(actual,list) or len(actual)!=T*M:
        raise ValueError('native output must contain exactly tokens*rows elements')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in actual):
        raise ValueError('native output must contain finite numbers')
    for key in ('serial_route_ms','best_batched_ms','speedup'):
        value=result.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
            raise ValueError('native timing and speedup fields must be finite and positive')
    candidates=result.get('candidate_ms')
    if not isinstance(candidates,list) or len(candidates)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in candidates):
        raise ValueError('native candidate timings must contain four finite positive numbers')
    native_error=result.get('native_max_abs_error')
    if type(native_error) not in (int,float) or not math.isfinite(native_error) or native_error<0:
        raise ValueError('native error metric must be finite and nonnegative')
    oracle=evaluate(d)['output']
    err=max(abs(a-b)for a,b in zip(oracle,actual));scale=max(abs(v)for v in oracle)
    tolerance=2e-5+2e-5*scale
    result.update(max_abs_error_vs_python_fp64=err,tolerance=tolerance,correct=err<=tolerance,qualification='native_cuda_component_microbenchmark_not_model_tps',weight_bytes_fp32=4*len(w),input_bytes_fp32=4*len(x),gate_bytes_fp32=4*len(g),route_bytes_int32=4*len(ids),intermediate_bytes_fp32=4*T*R*M,output_bytes_fp32=4*T*M,device_payload_bytes=4*(len(w)+len(x)+len(g)+len(ids)+T*R*M+T*M),output=actual)
    if not result['correct'] or not result['all_variants_correct']: raise ValueError('native CUDA oracle mismatch')
    return result
