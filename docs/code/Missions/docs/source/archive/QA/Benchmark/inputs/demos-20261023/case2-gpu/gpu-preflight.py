import importlib.util,json,pathlib,sys
meta=json.loads(pathlib.Path('inputs/runtime-meta.json').read_text())
record={'status':'ENVIRONMENT_BLOCKED','host':meta['physical_host'],
 'reason':'Required GPU execution readiness has not been confirmed for this exact AI4R app.',
 'cpu_fallback_permitted':False,'measurement_executed':False}
if not meta.get('app_gpu_device_requests'):
 record['reason']='The AI4R container has no configured NVIDIA GPU device request.'
elif not meta.get('app_torch_installed'):
 record['reason']='PyTorch is not installed in the AI4R execution environment.'
else:
 record.update(status='READY',reason='GPU device request and PyTorch installation are recorded; the app must independently admit and execute the GPU protocol.')
pathlib.Path('gpu-environment.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record));sys.exit(0 if record['status']=='READY' else 2)
