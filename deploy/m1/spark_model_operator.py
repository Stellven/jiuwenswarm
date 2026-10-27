"""Three key-free Spark services, managed by the existing AI4R operator.

This module does not run research, alter capsules, or download to Windows.
Only explicit `local-pool weights`/`prepare` download public model weights;
`prepare` also pulls images.
"""
from __future__ import annotations

import json
import fnmatch
import hashlib
import ipaddress
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
from urllib.parse import quote
from urllib.request import Request, urlopen

GIB = 1024 ** 3
LLAMA_IMAGE = 'ghcr.io/ggml-org/llama.cpp:server-cuda13-b11459'
BOLT_IMAGE = 'ghcr.io/ggml-org/llama.cpp:server-cuda13@sha256:7801848d4d37bc0d7a196fce49496e00b0e24bf6f81f36ba629f6be423f11f02'
VLLM_IMAGE = 'nvcr.io/nvidia/vllm:26.09-py3'
MODELS = (
    ('e4b', 'nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB', 'Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf'),
    ('qwen', 'Qwen/Qwen3.8-27B-FP8', None),
    ('bolt', 'nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-GGUF', 'NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB.gguf'),
)


def selection_v2(generation=2):
    if generation not in {2, 3}:
        raise ValueError('Unknown pinned pool generation')
    value = globals().get('SPARK_POOL_SELECTION' if generation == 2 else 'SPARK_POOL_SELECTION_V3')
    if value is None:
        value = json.loads(Path(__file__).with_name('spark-pool-v'+str(generation)+'.json').read_text(encoding='utf-8'))
    if value.get('schema') != 'ai4r-spark-pool-selection:'+str(generation) or len(value.get('models', [])) != 3:
        raise ValueError('Invalid repository Spark pool selection')
    return value


def configure_v2(p, data_root, docker, checked, *, share_address=None, generation=3):
    hardware(p, docker, require_docker=False)
    root = checked(Path(data_root))
    if not root.is_absolute() or str(root) in {'/', '/home', '/tmp', '/var'}:
        raise ValueError('Specify a dedicated absolute model directory')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_uid != os.geteuid() or root.stat().st_mode & 0o022:
        raise ValueError('Model directory must be operator owned and not publicly writable')
    addresses = ['127.0.0.1']
    if share_address:
        address = ipaddress.ip_address(share_address)
        if not isinstance(address, ipaddress.IPv4Address) or address not in ipaddress.ip_network('100.64.0.0/10'):
            raise ValueError('Shared inference requires an explicit Tailscale IPv4')
        addresses.append(str(address))
    models = [dict(row, served_model='ai4r-'+row['id']+'-'+row['revision'][:12]) for row in selection_v2(generation)['models']]
    return {'schema': 'ai4r-spark-pool:2', 'selection_generation':generation, 'data_root': str(root), 'models': models,
        'shared_access': {'bind_addresses': addresses, 'ports': {row['id']: row['port'] for row in models}},
        'images': {'llama': LLAMA_IMAGE}, 'prepared': False,
        'qualification': 'public model selection; actual worker qualification must be measured'}


def hardware(p, docker, *, require_docker=True):
    if platform.system() != 'Linux' or platform.machine() not in {'aarch64', 'arm64'} or p['platform'] != 'linux/arm64':
        raise ValueError('The local pool must be configured on the ARM64 Spark execution host')
    total=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))*1024
    if total<110*GIB:
        raise ValueError('This three-model configuration requires a 128 GB Spark host')
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
        capture_output=True, text=True, timeout=15, check=False)
    if gpu.returncode or 'GB10' not in gpu.stdout:
        raise ValueError('This model configuration requires the Spark GB10 GPU')
    if not require_docker:
        return {'Architecture':'aarch64','MemTotal':total}
    info = json.loads(docker(p, 'info', '--format', '{{json .}}'))
    if info.get('Architecture') not in {'aarch64', 'arm64'} or info.get('MemTotal', 0) < 110 * GIB:
        raise ValueError('This three-model configuration requires a 128 GB Spark Docker host')
    endpoint = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')
    context = json.loads(docker(p, 'context', 'inspect', *([p['docker_context']] if p.get('docker_context') else [])))
    if endpoint != 'unix:///var/run/docker.sock' or context[0]['Endpoints']['docker']['Host'] != endpoint:
        raise ValueError('Spark model storage must belong to the local Unix-socket Docker host')
    if 'nvidia' in info.get('Runtimes', {}):
        info['AI4RGpuAccess'] = 'nvidia-runtime'
    elif info.get('CDISpecDirs') and shutil.which('nvidia-ctk'):
        devices = subprocess.run(['nvidia-ctk', 'cdi', 'list'], capture_output=True, text=True, timeout=15)
        if devices.returncode or 'nvidia.com/gpu=all' not in devices.stdout.splitlines():
            raise ValueError('NVIDIA CDI device is unavailable to Docker')
        info['AI4RGpuAccess'] = 'cdi'
    else:
        raise ValueError('Configure NVIDIA Container Toolkit or its CDI device before preparation')
    return info


def configure(p, data_root, docker, checked, *, share_address=None):
    hardware(p, docker, require_docker=False)
    addresses = ['127.0.0.1']
    if share_address is not None:
        address = ipaddress.ip_address(share_address)
        if not isinstance(address, ipaddress.IPv4Address) or address not in ipaddress.ip_network('100.64.0.0/10'):
            raise ValueError('Shared remote inference must bind an explicit Tailscale IPv4 address')
        addresses.append(str(address))
    raw = Path(data_root)
    if not raw.is_absolute() or str(raw) in {'/', '/tmp', '/var', '/home'}:
        raise ValueError('Specify a dedicated absolute Spark data directory')
    root = checked(raw)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o022 or root.stat().st_uid not in {0, os.geteuid()}:
        raise ValueError('Spark data directory must be operator owned and not writable by other users')
    pins = []
    for ident, repo, filename in MODELS:
        with urlopen('https://huggingface.co/api/models/' + repo, timeout=30) as response:
            metadata = json.loads(response.read(2 * 1024 * 1024))
        revision = metadata.get('sha', '')
        if not re.fullmatch('[a-f0-9]{40}', revision):
            raise ValueError('Cannot pin public model revision: ' + ident)
        if filename and filename not in {row['rfilename'] for row in metadata.get('siblings', [])}:
            raise ValueError('Official model file is unavailable: ' + ident)
        pins.append({'id': ident, 'repository': repo, 'revision': revision, 'file': filename,
                     'served_model': 'ai4r-' + ident + '-' + revision[:12]})
    return {'schema': 'ai4r-spark-pool:1', 'data_root': str(root), 'models': pins,
            'shared_access': {'bind_addresses': addresses, 'ports': {'e4b': 8011, 'qwen': 8012, 'bolt': 8013}},
            'images': {'llama': LLAMA_IMAGE, 'bolt': BOLT_IMAGE, 'vllm': VLLM_IMAGE}, 'prepared': False}


def _file_matches(path, item):
    if not path.is_file() or path.stat().st_size!=item['size']:
        return False
    digest=hashlib.sha256() if item['algorithm']=='sha256' else hashlib.sha1()
    if item['algorithm']=='git-sha1':
        digest.update(('blob '+str(item['size'])+'\0').encode())
    with path.open('rb') as stream:
        while block:=stream.read(4*1024*1024):
            digest.update(block)
        if hasattr(os, 'posix_fadvise'):
            # Spark shares CPU/GPU memory. Retaining tens of GB of freshly
            # hashed download pages makes cudaMemGetInfo underreport usable
            # startup space. Discard only clean cache for this owned file;
            # file bytes and running model allocations are never removed.
            os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    return digest.hexdigest()==item['digest']


def fetch_weights(p, docker, checked, publish, canonical):
    """Resumable public downloads on Spark, independent of Docker/GPU loading."""
    hardware(p,docker,require_docker=False)
    pool=p.get('local_pool')
    if not pool or pool.get('schema') not in {'ai4r-spark-pool:1', 'ai4r-spark-pool:2'}:
        raise ValueError('Configure the local pool first')
    root=checked(pool['data_root'])
    selected=[]
    for model in pool['models']:
        accepted = MODELS if pool['schema'] == 'ai4r-spark-pool:1' else tuple(
            (row['id'], row['repository'], row['file']) for row in selection_v2(pool.get('selection_generation',2))['models'])
        if ((model['id'],model['repository'],model['file']) not in accepted
                or not re.fullmatch('[a-f0-9]{40}',model['revision'])):
            raise ValueError('Unknown pinned model download')
        if pool['schema'] == 'ai4r-spark-pool:2':
            expected = next(row for row in selection_v2(pool.get('selection_generation',2))['models'] if row['id'] == model['id'])
            if any(model.get(key) != expected[key] for key in ('repository', 'revision', 'file', 'sha256', 'bytes')):
                raise ValueError('Repository model selection differs from operator pin')
        repo=model['repository']; revision=model['revision']
        with urlopen('https://huggingface.co/api/models/'+repo+'/revision/'+revision+'?blobs=true',timeout=30) as response:
            metadata=json.loads(response.read(8*1024*1024))
        if metadata.get('sha')!=revision:
            raise ValueError('Model repository revision changed')
        for row in metadata.get('siblings',[]):
            name=row['rfilename']
            wanted=(name==model['file'] if model['file'] else any(fnmatch.fnmatch(name,pattern)
                for pattern in ('*.json','*.safetensors','*.model','*.txt','*.jinja','*.tiktoken')))
            if not wanted:
                continue
            relative=PurePosixPath(name)
            lfs=row.get('lfs') or {}
            digest=lfs.get('sha256') or row.get('blobId','')
            algorithm='sha256' if lfs else 'git-sha1'
            size=row.get('size')
            if (relative.is_absolute() or '..' in relative.parts or '\\' in name
                    or type(size) is not int or size<0 or not re.fullmatch('[a-f0-9]{'+('64' if lfs else '40')+'}',digest)):
                raise ValueError('Invalid pinned file metadata')
            target=checked(root/'models'/model['id']/name)
            selected.append({'path':target,'size':size,'digest':digest,'algorithm':algorithm,
                'url':'https://huggingface.co/'+repo+'/resolve/'+revision+'/'+quote(name,safe='/')})
        if not any(item['path'].is_relative_to(root/'models'/model['id']) for item in selected):
            raise ValueError('Pinned model files are unavailable: '+model['id'])
    pending=[item for item in selected if not _file_matches(item['path'],item)]
    missing=sum(item['size'] for item in pending)
    usage=shutil.disk_usage(root)
    if usage.free-missing<max(20*GIB,int(usage.total*.20)):
        raise ValueError('Insufficient Spark download storage; preserve 20% disk headroom')
    for item in pending:
        target=item['path']; target.parent.mkdir(parents=True,exist_ok=True)
        partial=checked(target.with_name('.'+target.name+'.'+item['digest'][:12]+'.partial'))
        offset=partial.stat().st_size if partial.exists() else 0
        if offset>item['size']:
            raise ValueError('Partial download exceeds pinned file size')
        if item['size'] == 0 and not partial.exists():
            # Empty upstream files still need an actual verified file. With
            # size==offset==0 there is no HTTP body to create the partial.
            with partial.open('xb'):
                pass
        if offset!=item['size']:
            headers={'Range':'bytes='+str(offset)+'-'} if offset else {}
            with urlopen(Request(item['url'],headers=headers),timeout=60) as response:
                resumed=offset and response.status==206
                if response.status not in (200,206) or (resumed and not response.headers.get('Content-Range','').startswith('bytes '+str(offset)+'-')):
                    raise ValueError('Invalid ranged download response')
                received=offset if resumed else 0
                with partial.open('ab' if resumed else 'wb') as stream:
                    while block:=response.read(4*1024*1024):
                        received+=len(block)
                        if received>item['size']:
                            raise ValueError('Download exceeds pinned file size')
                        stream.write(block)
                    stream.flush();os.fsync(stream.fileno())
        if not _file_matches(partial,item):
            if partial.exists() and partial.stat().st_size==item['size']:
                # A complete corrupt temporary file cannot be resumed. Reset
                # only this downloader-owned partial, preserving final files.
                with partial.open('wb'):
                    pass
            raise ValueError('Downloaded model file failed its pinned hash: '+target.name)
        os.replace(partial,target)
        publish(root/'weights-progress.json',canonical({'completed':str(target.relative_to(root)),
            'bytes':item['size'],'digest':item['digest']}),replace=True)
    pool['weights_ready']=True
    publish(root/'weights.json',canonical({'schema':'ai4r-local-weights:1','files':[
        {key:(str(value.relative_to(root)) if key=='path' else value) for key,value in item.items() if key!='url'}
        for item in selected]}),replace=True)
    return pool


def prepare(p, docker, checked, publish, canonical):
    info = hardware(p, docker)
    pool = p.get('local_pool')
    if not pool or pool.get('schema') not in {'ai4r-spark-pool:1', 'ai4r-spark-pool:2'}:
        raise ValueError('Configure the local pool before preparing it')
    if pool.get('prepared'):
        return pool
    root = checked(pool['data_root'])
    pool['gpu_access'] = info['AI4RGpuAccess']
    # Includes weights, image layers and compilation headroom. No pruning or
    # cache deletion is performed, even when there is insufficient space.
    if shutil.disk_usage(root).free < 20 * GIB:
        raise ValueError('Spark model data directory needs 20 GiB free for runtime preparation')
    if shutil.disk_usage(info['DockerRootDir']).free < 80 * GIB:
        raise ValueError('Docker image storage needs 80 GiB free before preparation')
    fetch_weights(p,docker,checked,publish,canonical)
    for name in ('models', 'cache', 'cache/huggingface', 'cache/vllm', 'cache/triton', 'cache/flashinfer', 'cache/tmp'):
        checked(root / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    images = (('llama', LLAMA_IMAGE),) if pool['schema'] == 'ai4r-spark-pool:2' else (
        ('llama', LLAMA_IMAGE), ('bolt', BOLT_IMAGE), ('vllm', VLLM_IMAGE))
    for key, tag in images:
        docker(p, 'pull', '--platform', 'linux/arm64', tag, timeout=7200)
        image = json.loads(docker(p, 'image', 'inspect', tag))[0]
        if image['Architecture'] != 'arm64':
            raise ValueError('Model image is not ARM64')
        pool['images'][key] = image['Id']
    pool['prepared'] = True
    publish(root / 'pool.json', canonical(pool), replace=True)
    return pool


def endpoint_configuration(pool):
    return {'schema': 'ai4r-local-model-endpoints:1', 'models': [
        {'id': row['id'], 'base_url': 'http://ai4r-model-' + row['id'] + ':8000/v1',
         'served_model': row['served_model'], 'context_tokens': row.get('context_tokens', 65536),
         'output_tokens': 8192, 'enabled': True} for row in pool['models']]}


def preflight_start(p, docker):
    """Check headroom for new services without stopping or evicting other work."""
    pool=p['local_pool']
    if not pool.get('prepared'):
        raise ValueError('Run local-pool prepare before starting AI4R')
    if pool.get('schema') == 'ai4r-spark-pool:2':
        return preflight_v2(p, docker)
    memory={key:int(value.strip().split()[0])*1024 for key,value in
        (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        if key in {'MemTotal','MemAvailable'}}
    ids=docker(p,'ps','-q','--filter','label=ai4r.deployment='+p['deployment_id']).decode().split()
    running=set()
    for ident in ids:
        observed=json.loads(docker(p,'inspect',ident))[0]
        labels=observed['Config'].get('Labels') or {}
        component=labels.get('ai4r.component','')
        if (component.startswith('model-') and labels.get('ai4r.owner')==p['project']
                and observed['State']['Running']):
            name=component.removeprefix('model-')
            expected=pool['images']['vllm' if name=='qwen' else 'bolt' if name=='bolt' and 'bolt' in pool['images'] else 'llama']
            if observed['Image']==expected:
                running.add(name)
    # File sizes give a minimum for resident weights, not peak runtime usage.
    # Qwen's configured vLLM reservation is larger and must also be accounted
    # for. The container limit sum is never presented as a measured demand.
    needed=8*GIB  # app plus startup headroom
    new=[]
    for row in pool['models']:
        if row['id'] in running:
            continue
        root=Path(pool['data_root'])/'models'/row['id']
        paths=[root/row['file']] if row['file'] else list(root.glob('*.safetensors'))
        if not paths or any(not path.is_file() or path.is_symlink() for path in paths):
            raise ValueError('Pinned model weights are missing: '+row['id'])
        weights=sum(path.stat().st_size for path in paths)
        if hasattr(os, 'posix_fadvise'):
            for path in paths:
                with path.open('rb') as stream:
                    os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        needed+=max(weights,int(memory['MemTotal']*.36)) if row['id']=='qwen' else weights
        new.append(row['id'])
    if memory['MemAvailable']<needed:
        raise ValueError('Insufficient memory for new local services '+','.join(new)
            +': available '+str(round(memory['MemAvailable']/GIB,1))+' GiB, minimum startup estimate '
            +str(round(needed/GIB,1))+' GiB. Coordinate existing workloads; none were stopped.')
    return {'available_bytes':memory['MemAvailable'],'minimum_estimate_bytes':needed,
            'new_models':new,'peak_usage':'not_measured'}


def apply_compose(p, result):
    pool = p['local_pool']
    if not pool.get('prepared'):
        raise ValueError('Run local-pool prepare before starting AI4R')
    if pool.get('schema') == 'ai4r-spark-pool:2':
        return apply_compose_v2(p, result)
    root = Path(pool['data_root'])
    for row in pool['models']:
        ident = row['id']
        command = (['serve', '/models', '--served-model-name', row['served_model'],
            '--host', '0.0.0.0', '--port', '8000', '--tensor-parallel-size', '1',
            '--max-model-len', '65536', '--max-num-seqs', '1', '--max-num-batched-tokens', '2048',
            '--gpu-memory-utilization', '0.36', '--kv-cache-dtype', 'fp8', '--enforce-eager',
            '--language-model-only', '--reasoning-parser', 'qwen3'] if ident == 'qwen' else
            ['--model', '/models/' + row['file'], '--alias', row['served_model'],
             '--host', '0.0.0.0', '--port', '8000', '--ctx-size', '65536', '--parallel', '1',
             '--n-gpu-layers', '999', '--jinja', '--flash-attn', 'on',
             '--cache-type-k', 'q8_0', '--cache-type-v', 'q8_0', '--no-warmup'])
        image_key = 'vllm' if ident == 'qwen' else 'bolt' if ident == 'bolt' and 'bolt' in pool['images'] else 'llama'
        service = {'image': pool['images'][image_key],
            'platform': 'linux/arm64', 'init': True, 'restart': 'unless-stopped',
            'user': f'{os.geteuid()}:{os.getegid()}', 'command': command,
            'mem_limit': {'e4b': '12g', 'qwen': '48g', 'bolt': '36g'}[ident],
            'pids_limit': 512, 'shm_size': '2g', 'cap_drop': ['ALL'],
            'security_opt': ['no-new-privileges:true'], 'networks': ['private'],
            'environment': {'HOME': '/cache', 'HF_HOME': '/cache/huggingface', 'HF_HUB_OFFLINE': '1',
                'TRANSFORMERS_OFFLINE': '1', 'TMPDIR': '/cache/tmp', 'VLLM_CACHE_ROOT': '/cache/vllm',
                'TRITON_CACHE_DIR': '/cache/triton', 'FLASHINFER_WORKSPACE_BASE': '/cache/flashinfer',
                'XDG_CACHE_HOME': '/cache/xdg', 'CUDA_CACHE_PATH': '/cache/cuda',
                'TORCHINDUCTOR_CACHE_DIR': '/cache/torchinductor', 'NUMBA_CACHE_DIR': '/cache/numba',
                'VLLM_WORKER_MULTIPROC_METHOD': 'spawn'},
            'volumes': [{'type': 'bind', 'source': str(root / 'models' / ident), 'target': '/models',
                'read_only': True, 'bind': {'create_host_path': False}},
                {'type': 'bind', 'source': str(root / 'cache'), 'target': '/cache', 'bind': {'create_host_path': False}}],
            'logging': {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '2'}},
            'labels': {'ai4r.owner': p['project'], 'ai4r.deployment': p['deployment_id'], 'ai4r.component': 'model-' + ident}}
        if pool.get('gpu_access') == 'cdi':
            service['devices'] = ['nvidia.com/gpu=all']
        else:
            service['deploy'] = {'resources': {'reservations': {'devices': [
                {'driver': 'nvidia', 'count': 1, 'capabilities': ['gpu']}]}}}
        if ident == 'qwen':
            service['entrypoint'] = ['vllm']
            service['healthcheck'] = {'test': ['CMD', 'python3', '-c',
                "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"],
                'interval': '10s', 'timeout': '5s', 'start_period': '5m', 'retries': 60}
        else:
            service['healthcheck'] = {'test': ['CMD', 'curl', '--fail', '--silent',
                '--max-time', '3', 'http://127.0.0.1:8000/health'],
                'interval': '10s', 'timeout': '5s', 'start_period': '2m', 'retries': 30}
            # Reserve vLLM's configured memory before loading the other
            # models. Otherwise its initial free-memory check races them on
            # unified-memory Spark even when the total pool fits.
            service['depends_on'] = {'ai4r-model-qwen': {'condition': 'service_healthy'}}
        sharing = pool.get('shared_access')
        if sharing:
            service['ports'] = [{'target': 8000, 'published': str(sharing['ports'][ident]),
                'host_ip': address, 'protocol': 'tcp'} for address in sharing['bind_addresses']]
        result['services']['ai4r-model-' + ident] = service
    labels = {'ai4r.owner': p['project'], 'ai4r.deployment': p['deployment_id']}
    result['volumes']['local_pool_config'] = {'name': p['project'] + '_local_pool_config', 'labels': labels}
    app = result['services']['ai4r']
    app['environment']['JIUWENSWARM_M1_LOCAL_MODELS'] = '/run/ai4r-local-pool/models.json'
    app['volumes'].append({'type': 'volume', 'source': 'local_pool_config', 'target': '/run/ai4r-local-pool', 'read_only': True})
    app.setdefault('depends_on', {}).update({'ai4r-model-' + ident: {'condition': 'service_started'} for ident, _, _ in MODELS})


def preflight_v2(p, docker):
    pool = p['local_pool']
    root = Path(pool['data_root'])
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
        if line.startswith('MemAvailable:'))) * 1024
    needed = 12 * GIB
    new = []
    for model in pool['models']:
        name = p['project']+'-ai4r-model-'+model['id']+'-1'
        rows = docker(p, 'ps', '--filter', 'name=^/'+name+'$', '--format', '{{.ID}}').decode().split()
        if rows:
            observed = json.loads(docker(p, 'inspect', rows[0]))[0]
            if (observed['Image'] != pool['images']['llama']
                    or observed['Config']['Labels'].get('ai4r.deployment') != p['deployment_id']):
                raise ValueError('Existing model service differs from the prepared deployment')
            continue
        file = root/'models'/model['id']/model['file']
        if not file.is_file() or file.is_symlink() or file.stat().st_size != model['bytes']:
            raise ValueError('Pinned model file is missing: '+model['id'])
        needed += model['bytes']
        new.append(model['id'])
    if available < needed:
        raise ValueError('Insufficient Spark memory: available '+str(round(available/GIB,1))+
            ' GiB; startup estimate '+str(round(needed/GIB,1))+' GiB. No other workloads stopped.')
    return {'available_bytes': available, 'minimum_estimate_bytes': needed,
        'new_models': new, 'peak_usage': 'not_measured'}


def apply_compose_v2(p, result):
    pool = p['local_pool']; root = Path(pool['data_root'])
    for row in pool['models']:
        ident = row['id']
        command = ['--model', '/models/'+row['file'], '--alias', row['served_model'],
            '--host', '0.0.0.0', '--port', '8000', '--ctx-size', str(row['context_tokens']),
            '--parallel', '1', '--batch-size', '512', '--ubatch-size', '128',
            '--n-gpu-layers', '999', '--jinja', '--flash-attn', 'on', '--fit', 'off',
            '--cache-type-k', 'q8_0', '--cache-type-v', 'q8_0', '--no-warmup',
            '--reasoning-format', 'deepseek', '--reasoning-budget', '0' if ident == 'qwen' else '2048',
            '--temp', '0', '--no-webui']
        service = {'image': pool['images']['llama'], 'platform': 'linux/arm64', 'init': True,
            'restart': 'unless-stopped', 'user': f'{os.geteuid()}:{os.getegid()}', 'command': command,
            'mem_limit': row['memory_limit'], 'pids_limit': 512, 'shm_size': '1g',
            'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'], 'networks': ['private'],
            'environment': {'HOME':'/cache', 'TMPDIR':'/cache/tmp', 'XDG_CACHE_HOME':'/cache/xdg',
                'CUDA_CACHE_PATH':'/cache/cuda'},
            'volumes': [{'type':'bind','source':str(root/'models'/ident),'target':'/models','read_only':True,
                'bind':{'create_host_path':False}}, {'type':'bind','source':str(root/'cache'),
                'target':'/cache','bind':{'create_host_path':False}}],
            'logging': {'driver':'json-file','options':{'max-size':'10m','max-file':'2'}},
            'healthcheck': {'test':['CMD','curl','--fail','--silent','--max-time','3','http://127.0.0.1:8000/health'],
                'interval':'10s','timeout':'5s','start_period':'10m','retries':90},
            'labels': {'ai4r.owner':p['project'],'ai4r.deployment':p['deployment_id'],'ai4r.component':'model-'+ident}}
        if pool.get('gpu_access') == 'cdi':
            service['devices'] = ['nvidia.com/gpu=all']
        else:
            service['deploy']={'resources':{'reservations':{'devices':[{'driver':'nvidia','count':1,'capabilities':['gpu']}]}}}
        sharing = pool.get('shared_access')
        if sharing:
            service['ports']=[{'target':8000,'published':str(sharing['ports'][ident]),'host_ip':address,'protocol':'tcp'}
                for address in sharing['bind_addresses']]
        result['services']['ai4r-model-'+ident]=service
    labels={'ai4r.owner':p['project'],'ai4r.deployment':p['deployment_id']}
    result['volumes']['local_pool_config']={'name':p['project']+'_local_pool_config','labels':labels}
    app=result['services']['ai4r']
    app['environment']['JIUWENSWARM_M1_LOCAL_MODELS']='/run/ai4r-local-pool/models.json'
    app['volumes'].append({'type':'volume','source':'local_pool_config','target':'/run/ai4r-local-pool','read_only':True})
    app.setdefault('depends_on',{}).update({'ai4r-model-'+row['id']:{'condition':'service_healthy'} for row in pool['models']})


def provision(p, docker, canonical):
    pool = p['local_pool']
    if not pool.get('prepared'):
        raise ValueError('Run local-pool prepare before starting AI4R')
    volume = p['project'] + '_local_pool_config'
    labels = {'ai4r.owner': p['project'], 'ai4r.deployment': p['deployment_id']}
    existing = docker(p, 'volume', 'ls', '--format', '{{.Name}}').decode().splitlines()
    if volume not in existing:
        docker(p, 'volume', 'create', '--label', 'ai4r.owner=' + p['project'],
               '--label', 'ai4r.deployment=' + p['deployment_id'], volume)
    observed = json.loads(docker(p, 'volume', 'inspect', volume))[0]
    if observed.get('Driver') != 'local' or observed.get('Options') or any(observed.get('Labels', {}).get(k) != v for k, v in labels.items()):
        raise ValueError('Foreign local pool configuration volume')
    active = bool(docker(p, 'ps', '-q', '--filter', 'volume=' + volume).strip())
    script = '''import os,sys
from pathlib import Path
p=Path('/operator/models.json'); data=sys.stdin.buffer.read()
if sys.argv[1]=='check':
 assert p.read_bytes()==data,'Stop the idle app before changing the local pool'
else:
 temporary=p.with_name('models.new'); temporary.write_bytes(data)
 temporary.chmod(0o444); os.chown(temporary,0,0); os.replace(temporary,p)
'''
    docker(p, 'run', '--rm', '-i', '--pull', 'never', '--network', 'none', '--read-only', '--user', '0:0',
        '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--cap-add', 'DAC_OVERRIDE', '--cap-add', 'FOWNER',
        '--security-opt', 'no-new-privileges:true', '--mount', 'type=volume,src=' + volume + ',dst=/operator' + (',readonly' if active else ''),
        '--entrypoint', '/opt/venv/bin/python', p['app_image'], '-c', script, 'check' if active else 'write',
        data=canonical(endpoint_configuration(pool)))
