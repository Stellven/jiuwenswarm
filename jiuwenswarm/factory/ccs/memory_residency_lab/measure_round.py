"""Manual actual allocation/touch/check, synthetic explicit lifetimes."""
import hashlib,json,platform,time
from pathlib import Path
from components.implementation import native_experiment
if __name__=='__main__':
    base=Path(__file__).resolve().parent;request=json.loads((base/'EXAMPLES.json').read_text())['native_experiment']['request'];result=native_experiment(request)
    artifact=dict(format='native-component-round/1',utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),machine=platform.machine(),source_sha256=hashlib.sha256((base/'native_arena.cpp').read_bytes()).hexdigest(),binary_sha256=hashlib.sha256((base/'native_arena').read_bytes()).hexdigest(),request=request,result=result,scope='native CPU payload allocations; explicit synthetic lifetimes; not whole engine memory')
    (base/'ROUND1.json').write_text(json.dumps(artifact,indent=2)+'\n');print(json.dumps(artifact,indent=2))
