"""Prepare public demo inputs and separate, unmounted reviewer material.

This file contains reviewer answers. Never copy it into the runner input mount.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import pathlib
import platform
import secrets
import shutil
import subprocess
import sys
import textwrap
import time

import numpy as np
import requests
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = pathlib.Path(__file__).resolve().parent
BENCH = ROOT.parent
REPO = next(p for p in ROOT.parents if (p / 'AGENTS.md').is_file())
STAMP = 'demos-20261023'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        value = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    raw = value if isinstance(value, bytes) else value.encode('utf8')
    if path.exists():
        if path.read_bytes() != raw:
            raise RuntimeError('Refusing to replace existing demo input: ' + str(path))
        return
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def csv_file(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', newline='', encoding='utf8') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(headers)
        writer.writerows(rows)


def command(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    return {'command': argv, 'exit_code': result.returncode,
            'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()[:1000]}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


DOCKER = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--exec', 'env',
          '-u', 'DOCKER_CONTEXT', '-u', 'DOCKER_TLS_VERIFY', '-u', 'DOCKER_CERT_PATH',
          'DOCKER_HOST=unix:///var/run/docker.sock', 'docker']

PROVENANCE = '''import importlib.metadata,json,os,pathlib,platform,socket
meta=json.loads(pathlib.Path('inputs/runtime-meta.json').read_text())
versions={}
for name in ('httpx','jsonschema','psutil','numpy','scikit-learn','torch'):
 try: versions[name]=importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError: versions[name]=None
record=dict(meta,runner_hostname=socket.gethostname(),runner_os=platform.platform(),
 runner_architecture=platform.machine(),runner_python=platform.python_version(),
 runner_uid=os.getuid(),runner_package_versions=versions)
pathlib.Path('runtime-environment.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'runtime_environment':'runtime-environment.json','host':meta['physical_host'],
 'checkout_commit':meta['checkout_commit'],'app_build_id':meta['app_build_id']}))
'''

GPU_PREFLIGHT = '''import importlib.util,json,pathlib,sys
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
'''

GPU_MEASUREMENT = '''"""Run manually on an approved CUDA host; never use CPU fallback."""
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
'''


def common_notes(expected, stages):
    return f'''# Reviewer only — never upload this file

This is a small demonstration, not M1 acceptance. Expected outcome: {expected}

Manual checklist (leave unchecked until a human reviews the saved evidence):
- [ ] The actual host, checkout commit, installed build and observed model are recorded.
- [ ] Expected stages: {stages}. Record missing stages and the earliest stop reason.
- [ ] Capsule verifiers and deterministic gates advanced or blocked for a documented reason.
- [ ] Claims cite only the supplied public inputs. Reviewer files were not uploaded.
- [ ] Every reported measurement traces to original raw outputs and an actual execution.
- [ ] No missing number, prediction or timing is fabricated.
- [ ] Execution/collection outcomes are distinguished from research quality.

Assessment:

Evidence references:

Review notes:

'''


def prepare_case(name, task, public, notes, gpu=False):
    folder = ROOT / name
    write(folder / 'reviewer' / 'notes.md', notes)
    for path, raw in public.items():
        write(folder / 'public' / path, raw)
    upload_rows = []
    for name_in, raw in public.items():
        destination = BENCH / 'inputs' / STAMP / name / name_in
        write(destination, raw)
        upload_rows.append({'path': f'{STAMP}/{name}/{name_in}', 'destination': name_in,
                            'kind': 'datasets' if name_in.endswith('.csv') else 'docs'})
    for filename, raw in [('provenance.py', PROVENANCE), ('runtime-meta.json', META)]:
        write(BENCH / 'inputs' / STAMP / name / filename, raw)
        upload_rows.append({'path': f'{STAMP}/{name}/{filename}', 'destination': filename, 'upload': False})
    setup = [{'id': 'capture-runtime', 'trusted': True, 'command': ['python', 'inputs/provenance.py'],
              'outputs': ['runtime-environment.json'], 'timeout_s': 20}]
    if gpu:
        write(BENCH / 'inputs' / STAMP / name / 'gpu-preflight.py', GPU_PREFLIGHT)
        upload_rows.append({'path': f'{STAMP}/{name}/gpu-preflight.py', 'destination': 'gpu-preflight.py', 'upload': False})
        setup.append({'id': 'require-gpu', 'trusted': True, 'command': ['python', 'inputs/gpu-preflight.py'],
                      'outputs': ['gpu-environment.json'], 'timeout_s': 20})
    case = {'schema_version': 'sequential-cases:1', 'policy': 'stop',
            'limits': {'deadline_s': 600, 'poll_s': 2, 'command_timeout_s': 30,
                       'command_cpu_s': 30, 'command_memory_mb': 512,
                       'max_total_bytes': 134217728, 'max_artifact_bytes': 67108864},
            'cases': [{'id': name, 'task': task, 'inputs': upload_rows, 'setup': setup, 'repeats': 1}]}
    write(folder / 'case.json', case)
    write(BENCH / 'cases' / STAMP / (name + '.json'), case)
    write(folder / 'README.md', f'''# {name}

Public task and inputs: `case.json`, `public/`.
Reviewer-only material: `reviewer/` (not mounted into the app or runner).
The runner-ready public copies are `../../cases/{STAMP}/{name}.json` and
`../../inputs/{STAMP}/{name}/`. Input rows with `upload:false` are provenance/preflight only.
Run outputs remain under `../../results/`; see `run-manifest.json` after execution.
No app code, baseline or approved environment is changed to make this case pass.
''')
    return folder


if __name__ == '__main__':
    if (ROOT / 'case1-cpu').exists():
        raise SystemExit('Demos already exist; preserve original frozen inputs and attempts.')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    active = json.loads((pathlib.Path(os.environ['LOCALAPPDATA']) / 'AI4Research/runtime/poc-clean-active.json').read_bytes())
    gpu = command(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.free', '--format=csv,noheader'])
    device = command(DOCKER + ['inspect', '--format', '{{json .HostConfig.DeviceRequests}}', 'ai4r-poc-clean-ai4r-1'])
    torch_probe = command(DOCKER + ['exec', 'ai4r-poc-clean-ai4r-1', '/opt/venv/bin/python', '-c',
        'import importlib.util,json;print(json.dumps(importlib.util.find_spec(\'torch\') is not None))'])
    import psutil
    META = {'schema': 'demo-runtime-provenance:1', 'captured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'physical_host': platform.node(), 'host_os': platform.platform(), 'host_architecture': platform.machine(),
            'physical_memory': dict(psutil.virtual_memory()._asdict()), 'cpu_logical': psutil.cpu_count(),
            'cpu_physical': psutil.cpu_count(logical=False), 'checkout_commit': commit,
            'app_build_id': active['build_id'], 'app_image': active['image_id'],
            'runner_image': active['runner_image_id'], 'declared_model': 'gpt-6.1-sol',
            'observed_model': None, 'gpu_inventory': gpu, 'app_gpu_device_requests': json.loads(device['stdout']),
            'app_torch_installed': json.loads(torch_probe['stdout']), 'source_note': 'Host and commit supplied by reviewer-side provenance capture; actual model must come from app run evidence.'}
    write(ROOT / 'host-preflight.json', META)

    seed = secrets.randbits(64)
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(2000, 10))
    y = (1.8*x[:, 0] - .9*x[:, 1] + .6*x[:, 2] + rng.normal(scale=.08, size=2000) > 0).astype(int)
    order = rng.permutation(2000)
    train_i, test_i = order[:1400], order[1400:]
    features = [f'x{i}' for i in range(10)]
    data_root = ROOT / 'case1-cpu'
    csv_file(data_root/'public/train.csv', ['id', *features, 'label'],
             [[f'tr-{i:04}', *[f'{v:.10f}' for v in x[j]], int(y[j])] for i, j in enumerate(train_i)])
    csv_file(data_root/'public/test.csv', ['id', *features],
             [[f'te-{i:04}', *[f'{v:.10f}' for v in x[j]]] for i, j in enumerate(test_i)])
    csv_file(data_root/'reviewer/test_labels.csv', ['id', 'label'],
             [[f'te-{i:04}', int(y[j])] for i, j in enumerate(test_i)])
    reference = {}
    for label, estimator in [('logistic_regression', LogisticRegression(max_iter=500, random_state=42)),
                              ('one_nearest_neighbour', KNeighborsClassifier(n_neighbors=1))]:
        model = make_pipeline(StandardScaler(), estimator).fit(x[train_i], y[train_i])
        pred = model.predict(x[test_i])
        reference[label] = {'accuracy': float((pred == y[test_i]).mean()), 'correct': int((pred == y[test_i]).sum()), 'n': len(test_i)}
        csv_file(data_root/f'reviewer/{label}-reference-predictions.csv', ['id', 'label'],
                 [[f'te-{i:04}', int(v)] for i, v in enumerate(pred)])
    reference['gap_points'] = 100*(reference['logistic_regression']['accuracy']-reference['one_nearest_neighbour']['accuracy'])
    reference['seed_reviewer_only'] = seed
    reference['numpy'] = np.__version__
    reference['scikit_learn'] = importlib.metadata.version('scikit-learn')
    reference['scope'] = 'Reviewer fixture calibration only, not AI4R output or an automatic quality judge.'
    write(data_root/'reviewer/reference-measurements.json', reference)
    write(data_root/'reviewer/generation-notes.md', 'Gaussian ten-feature data; binary noisy linear decision boundary; random split 1400 train / 600 blind test. Seed and reference measurements are reviewer-only. No seed selection loop or app solution was supplied.\n')
    public_cpu = {p.name: p.read_bytes() for p in (data_root/'public').iterdir()}
    public_cpu['data-description.md'] = '''# Classification demo inputs
train.csv has 1400 labelled rows; test.csv has 600 unlabelled rows. There are ten numeric features x0 through x9. id is an opaque row identifier, not a feature. Labels are 0 or 1. Output predictions.csv must contain exactly id,label for all test IDs, in test order, without duplicates. Learn preprocessing only from training data. A seeded stratified train/validation split is permitted for the comparison because test labels are unavailable. Distinguish validation measurements from blind test predictions; never invent test accuracy. Use no external data or downloads. Document the exact preprocessing, parameters and split.
'''
    prepare_case('case1-cpu', 'Using only the attached data, test whether logistic regression beats a 1-nearest-neighbour baseline by at least 5 points accuracy. Train on train.csv, write predictions for test.csv to predictions.csv, and report your conclusion and limitations.',
        public_cpu, common_notes('full CPU workflow, predictions.csv, supported claim if the measured gap is at least 5 percentage points.', 'Intent → Requirements → Planner → Search → Screening → Hypothesis → Builder → Benchmark → Evaluation → Delivery') +
        '\nPrivate calibration is in reference-measurements.json. Score actual AI4R predictions against test_labels.csv by ID only after collection. The installed runtime currently pins a majority-class baseline and a different root-scored data.json; do not relabel that baseline as 1-NN or use its scores for these CSVs. If the app cannot bind the requested data/baseline, record BLOCKED and preserve its output.\n')

    gpu_spec = '''# Small local CUDA inference comparison
Use PyTorch on an NVIDIA CUDA GPU. Do not download weights or data. Do not run a CPU substitute.
Model: TransformerEncoder, 2 layers, d_model 256, 8 heads, FFN 1024, ReLU activation for both modes, dropout 0, batch_first=True, enable_nested_tensor=False, eval() and inference_mode(). Seed 20261023. Synthetic normal inputs [32,128,256]. Identical initial state and inputs cast to FP32/FP16; random weights only. No torch.compile. Disable TF32 and the MHA inference fast path for both modes; record the actual PyTorch/backend versions and attention kernels if exposed.
Protocol: batch size 32, ten unmeasured warm-up iterations per dtype, then thirty measured iterations per dtype. Alternate FP32-first and FP16-first order across paired iterations. Use CUDA events and synchronize each measured iteration. Allocate/cast weights and inputs before timing, exclude host/device transfer and initialization. Save every per-batch timing in milliseconds, medians, FP16/FP32 median ratio and 1-ratio. The claim requires ratio <=0.70. Save a runnable measurement script and gpu-timings.json. Check outputs are finite; inference quality of random weights is not evaluated. Record host, GPU, driver, CUDA, PyTorch, memory and background contention. Tensor cores do not guarantee the proposed speedup; report an honest negative/inconclusive result if observed. If CUDA, PyTorch or approved GPU execution is unavailable, return ENVIRONMENT_BLOCKED with a reason and do not fabricate measurements.
'''
    gpu_notes = common_notes('supported if an actual qualified tensor-core GPU measurement shows FP16/FP32 <=0.70; otherwise report the measured negative or ENVIRONMENT_BLOCKED.', 'Compiler and Planner, then the complete scientific DAG only on an approved CUDA executor')
    gpu_notes += '\nUser subsequently deferred execution: build Case 2 only, do not run it now. Physical host has an RTX 4060 Laptop GPU, but the current AI4R container has no GPU device request/PyTorch and its approved benchmark capsule measures accuracy only. No GPU timing has been taken. Reviewer repeat: run measure_gpu.py on the same approved GPU with the same environment, then compare raw arrays/ratio; do not use a different host as if it were the app experiment.\n'
    gpu_folder = prepare_case('case2-gpu', 'Using the attached spec, test whether FP16 inference reduces per-batch latency by at least 30% versus FP32 on the local GPU. Report raw timings, the ratio, your conclusion and limitations.', {'transformer-spec.md': gpu_spec}, gpu_notes, gpu=True)
    write(gpu_folder/'public/measure_gpu.py', GPU_MEASUREMENT)
    write(gpu_folder/'reviewer/run-status.json', {'status': 'NOT_RUN', 'reason': 'User explicitly deferred Case 2 execution.', 'host_inventory_only': META['physical_host'], 'measurement_executed': False})

    response = requests.get('https://arxiv.org/pdf/2610.31019', timeout=60)
    response.raise_for_status()
    if not response.content.startswith(b'%PDF-'):
        raise RuntimeError('Paper response is not a PDF; do not replace it with invented text.')
    import fitz
    pdf = fitz.open(stream=response.content, filetype='pdf')
    if len(pdf) != 6:
        raise RuntimeError('Unexpected paper page count; inspect before running.')
    extracted = '\n\n'.join(f'--- PAGE {i+1} ---\n'+page.get_text() for i, page in enumerate(pdf))
    title = 'Chunk Recomputation under Real Document Revisions: Measuring Update Cost and Retrieval Quality of Fixed, Recursive, and Content-Defined Chunking'
    paper_notes = common_notes('paper summary completes; all three factual answers agree with the original paper and citations point to the right sections/tables.', 'Intent → Requirements → Planner → Summary → Delivery (not the experimental DAG)')
    paper_notes += '''\nReviewer-only oracle supplied by the user:
1. CDC failed on 4 of 62 Chinese articles — Abstract and Section V.
2. Fixed-size recomputed 68.4% Chinese and 57.4% English embedding workload — Section V/Table I.
3. Primary benchmark: 120 revision pairs (149 total); common-success pool: 116 articles — Section IV.
Spare check: 2000 paired-bootstrap resamples, Section IV.
Also inspect fixed-size 304 tokens, recursive target 400, CDC 176–352, frozen BGE-M3, and recall@2048 differences below two points within each language. Do not put this oracle into task text, setup scripts, public descriptions or uploaded artifacts.
New publication alone does not prove the model lacked prior knowledge. Verify the uploaded PDF hash, captured extraction and output citations; this is evidence of document use, not proof about model training.
'''
    paper_task = 'Using only the attached paper (chunk-recomputation-2610.31019.pdf), summarize its main claims, the evidence for each with section or table references, and the limitations the authors state. Then answer: (1) On how many of the Chinese articles did content-defined chunking fail? (2) What fraction of the embedding workload did fixed-size chunking recompute for Chinese and for English articles? (3) How many revision pairs are in the primary benchmark, and how many articles are in the common-success pool processed by all three chunkers?'
    paper_folder = prepare_case('case3-paper', paper_task, {'chunk-recomputation-2610.31019.pdf': response.content}, paper_notes)
    write(paper_folder/'reviewer/paper-extraction.txt', extracted)
    write(paper_folder/'reviewer/download.json', {'url': response.url, 'title': title, 'pages': len(pdf), 'bytes': len(response.content), 'sha256': hashlib.sha256(response.content).hexdigest(), 'downloaded_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    write(ROOT/'README.md', '''# Three small AI4Research demonstrations

These are demonstrations, not M1 acceptance. Only Case 1 and Case 3 are to be run now; Case 2 was deferred by the user. Each case folder has public inputs, its case JSON and a reviewer-only folder. Reviewer folders and this builder are outside all runner/app mounts. Public copies only are published into the existing Benchmark/cases and Benchmark/inputs mounts. Explicit input rows with upload:false capture infrastructure provenance; they contain no labels, expected answers or reference scores.

Do not modify the app, fixed baseline, approved environment or protected scoring fixture to force an outcome. The CPU request may be blocked by the installed majority-baseline classification contract; the GPU case additionally needs a real approved CUDA/PyTorch executor. Preserve blocked outputs. Runner records installed build and observed model events; an additional linked run-manifest.json records checkout commit, physical host, app image, missing fields and reviewer observations without claiming the runner natively records every field.
''')
    print(json.dumps({'demo_root': str(ROOT), 'cpu_reference_gap_points_reviewer_only': reference['gap_points'],
                      'paper_pages': len(pdf), 'case2_status': 'NOT_RUN', 'published_cases': str(BENCH/'cases'/STAMP)}))
