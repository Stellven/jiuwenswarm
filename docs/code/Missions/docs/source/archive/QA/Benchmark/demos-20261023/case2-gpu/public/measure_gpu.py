"""Run manually on an approved CUDA host; never use CPU fallback."""
import importlib.util,json,pathlib,platform,socket,statistics,sys,time
def blocked(reason):
 print(json.dumps({'status':'ENVIRONMENT_BLOCKED','reason':reason,'host':socket.gethostname(),
                   'cpu_fallback_permitted':False,'measurement_executed':False}));sys.exit(2)
if importlib.util.find_spec('torch') is None: blocked('PyTorch is not installed')
import torch
if not torch.cuda.is_available(): blocked('CUDA GPU is unavailable')
torch.manual_seed(20261023);torch.cuda.manual_seed_all(20261023)
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
torch.backends.mha.set_fastpath_enabled(False)
device=torch.device('cuda:0');batch=32;seq=128;dim=256;warmup=10;iterations=30
layer=torch.nn.TransformerEncoderLayer(d_model=dim,nhead=8,dim_feedforward=1024,
                                      dropout=0.0,batch_first=True)
base=torch.nn.TransformerEncoder(layer,num_layers=2,enable_nested_tensor=False).eval()
state={k:v.detach().clone() for k,v in base.state_dict().items()}
inputs=torch.randn(batch,seq,dim)
models={};data={}
for name,dtype in [('fp32',torch.float32),('fp16',torch.float16)]:
 model=torch.nn.TransformerEncoder(torch.nn.TransformerEncoderLayer(d_model=dim,nhead=8,
         dim_feedforward=1024,dropout=0.0,batch_first=True),num_layers=2,enable_nested_tensor=False)
 model.load_state_dict(state);models[name]=model.to(device=device,dtype=dtype).eval()
 data[name]=inputs.to(device=device,dtype=dtype)
raw={'fp32':[],'fp16':[]}
with torch.inference_mode():
 for name in raw:
  for _ in range(warmup): models[name](data[name])
 torch.cuda.synchronize()
 for i in range(iterations):
  for name in (('fp32','fp16') if i%2==0 else ('fp16','fp32')):
   start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
   start.record();result=models[name](data[name]);end.record();end.synchronize()
   raw[name].append(float(start.elapsed_time(end)))
   if not bool(torch.isfinite(result).all()): raise RuntimeError('Nonfinite output')
medians={name:statistics.median(values) for name,values in raw.items()}
result={'status':'MEASURED','host':socket.gethostname(),'os':platform.platform(),
 'python':platform.python_version(),'torch':torch.__version__,'cuda_runtime':torch.version.cuda,
 'gpu':torch.cuda.get_device_name(0),'compute_capability':list(torch.cuda.get_device_capability(0)),
 'protocol':{'batch':batch,'sequence_length':seq,'d_model':dim,'heads':8,'layers':2,
 'ffn':1024,'warmup_per_dtype':warmup,'timed_per_dtype':iterations,'tf32':False,
 'downloads':False,'timing':'CUDA events, per iteration synchronization; transfers excluded'},
 'raw_ms':raw,'median_ms':medians,'fp16_over_fp32':medians['fp16']/medians['fp32'],
 'latency_reduction':1-medians['fp16']/medians['fp32'],
 'quality_assessment':None,'limitations':['Random weights, synthetic fixed-shape activations.',
 'No claim about trained-model accuracy or universal speedups.','Background GPU contention is not controlled.']}
path=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'gpu-timings.json')
path.write_text(json.dumps(result,indent=2));print(json.dumps(result))
