"""Bounded actual FP32 tensor-slice GPU calibration. Run only inside the loop."""
import hashlib
import json
import math
import sys
import time
import torch

path,config=sys.argv[1:]
spec=json.load(open(config))
if spec['format']!='f32_le_row_major': raise ValueError('Unsupported packed format')
rows,columns=spec['shape']; offset=spec['offset']; repeats=spec['repeats']
if any(type(v) is not int or v<=0 for v in (rows,columns,repeats)) or rows*columns>16777216 or repeats>1000 or type(offset) is not int or offset<0:
    raise ValueError('Slice exceeds bounded harness limits')
start=time.perf_counter()
with open(path,'rb') as f:
    f.seek(offset);raw=f.read(rows*columns*4)
read_s=time.perf_counter()-start
if len(raw)!=rows*columns*4 or hashlib.sha256(raw).hexdigest()!=spec['slice_sha256']:
    raise ValueError('Actual tensor slice identity differs')
w=torch.frombuffer(bytearray(raw),dtype=torch.float32).reshape(rows,columns)
x=torch.tensor(spec['input'],dtype=torch.float32)
if len(x)!=columns or not torch.isfinite(w).all() or not torch.isfinite(x).all(): raise ValueError('Invalid input')
reference=w.double()@x.double()
w=w.cuda();x=x.cuda();torch.cuda.synchronize()
# Disable unsupported tensor-core/TF32 substitution; identify the actual path.
torch.backends.cuda.matmul.allow_tf32=False
for _ in range(5): y=w@x
torch.cuda.synchronize()
a,b=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
a.record()
for _ in range(repeats): y=w@x
b.record();b.synchronize();resident_s=a.elapsed_time(b)/1000/repeats
error=float((y.cpu().double()-reference).abs().max())
passed=torch.allclose(y.cpu().double(),reference,rtol=1e-5,atol=1e-5)
copy=torch.empty_like(w);a.record()
for _ in range(repeats): copy.copy_(w)
b.record();b.synchronize();copy_s=a.elapsed_time(b)/1000/repeats
# An event pair measures event overhead, not launch latency. Use a one-element add.
z=torch.zeros(1,device='cuda');a.record()
for _ in range(repeats): z.add_(1)
b.record();b.synchronize();launch_s=a.elapsed_time(b)/1000/repeats
print(json.dumps(dict(kind='measured_resident_slice',slice_sha256=spec['slice_sha256'],shape=[rows,columns],
    numerical_path='fp32_cuda_matvec_tf32_disabled',storage_read_s=read_s,storage_cache_state='unknown',
    resident_matvec_s=resident_s,launch_overhead_s=launch_s,launch_scope='one-element add including kernel work',
    copy_bandwidth_bytes_s=2*len(raw)/copy_s,maximum_absolute_error=error,reference_passed=passed,
    whole_model_tokens_per_second=None,observer_overhead='not_measured',torch_version=torch.__version__,
    device=torch.cuda.get_device_name(),repeats=repeats),allow_nan=False))
if not passed: sys.exit(2)
