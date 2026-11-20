"""Native CUDA 13/SM121 Strata builder; no development image or model access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import re
import time
import platform

BASE = 'ghcr.io/ggml-org/llama.cpp@sha256:695214dcb4d4062014335702caee98836bbf92c5974b78331c70e152176cbf08'
FLAGS = ['-DCMAKE_BUILD_TYPE=Release', '-DSTRATA_BUILD_DSV41=ON', '-DSTRATA_ENABLE_CUDA=ON',
         '-DSTRATA_BUILD_TESTS=OFF', '-DSTRATA_PORTABLE=ON',
         '-DSTRATA_ARM64_ARCH=armv8.2-a+dotprod+fp16+i8mm',
         '-DCMAKE_CUDA_ARCHITECTURES=121-real;121-virtual', '-DGGML_NATIVE=OFF',
         '-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16+i8mm', '-DGGML_OPENMP=OFF']

LLAMA_FLAGS = ['-DCMAKE_BUILD_TYPE=Release', '-DGGML_CUDA=ON',
    '-DCMAKE_CUDA_ARCHITECTURES=121-real;121-virtual', '-DGGML_NATIVE=OFF',
    '-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16+i8mm', '-DGGML_OPENMP=OFF',
    '-DLLAMA_BUILD_TESTS=OFF', '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_TOOLS=ON',
    '-DLLAMA_BUILD_SERVER=ON', '-DLLAMA_OPENSSL=OFF']


def build_flags(target, dependency):
    return list(LLAMA_FLAGS) if target == 'llama-server' else [*FLAGS, '-DSTRATA_GGML_DIR='+str(dependency)]


def native_recipe(cache):
    """Use the retained stock generator/toolchain/options, without its source/build paths."""
    values = {}
    for line in Path(cache).read_text().splitlines():
        if not line or line.startswith(('#', '//')) or '=' not in line or ':' not in line.split('=', 1)[0]:
            continue
        key_type, value = line.split('=', 1)
        key, kind = key_type.split(':', 1)
        values[key] = (kind, value)
    generator = values.get('CMAKE_GENERATOR', ('', ''))[1]
    if generator not in {'Unix Makefiles', 'Ninja'}:
        raise ValueError('Unsupported retained stock build generator')
    selected = {'CMAKE_BUILD_TYPE', 'CMAKE_CUDA_ARCHITECTURES', 'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_CUDA_COMPILER',
                'CMAKE_C_FLAGS', 'CMAKE_CXX_FLAGS', 'CMAKE_CUDA_FLAGS', 'CMAKE_C_FLAGS_RELEASE', 'CMAKE_CXX_FLAGS_RELEASE',
                'CMAKE_CUDA_FLAGS_RELEASE', 'CMAKE_EXE_LINKER_FLAGS', 'CMAKE_SHARED_LINKER_FLAGS'}
    flags = [f'-D{key}={value}' for key, (kind, value) in sorted(values.items())
             if kind != 'INTERNAL' and (key in selected or key.startswith(('GGML_', 'LLAMA_')))]
    for key, expected in {'CMAKE_BUILD_TYPE': 'Release', 'GGML_CUDA': 'ON'}.items():
        if values.get(key, ('', ''))[1] != expected:
            raise ValueError('Retained stock cache differs: ' + key)
    if '121' not in values.get('CMAKE_CUDA_ARCHITECTURES', ('', ''))[1]:
        raise ValueError('Retained stock cache must target SM121')
    return generator, flags


def native_ui_archive(cache):
    archive = Path(cache).parent / 'ui/apps/chat/dist.tar.gz'
    return archive if archive.is_file() else None


NATIVE_COMPILE = r'''
import hashlib,json,os,pathlib,shutil,subprocess,sys,time,platform
if platform.machine() not in ("aarch64", "arm64"):raise ValueError("Native ARM64 compilation required")
source,build,app,receipt,flags,target=sys.argv[1:]
flags=json.loads(flags);app=pathlib.Path(app);app.mkdir(parents=True,exist_ok=True)
tools={t:subprocess.check_output([t,'--version'],text=True) for t in ('nvcc','gcc','cmake','ninja')}
if 'release 13.' not in tools['nvcc']:raise ValueError('CUDA13 required')
configure_started=time.monotonic()
subprocess.run(['cmake','-G','Ninja','-S',source,'-B',build,*flags],check=True)
configure_seconds=time.monotonic()-configure_started
compile_started=time.monotonic()
subprocess.run(['cmake','--build',build,'--parallel','8','--target',target],check=True)
compile_seconds=time.monotonic()-compile_started
executable=pathlib.Path(build)/('bin/'+target if target=='llama-server' else target);shutil.copy2(executable,app/executable.name)
linked=subprocess.check_output(['ldd',str(executable)],text=True)
for line in linked.splitlines():
 if '=>' in line:
  path=pathlib.Path(line.split('=>',1)[1].strip().split()[0])
  if path.is_file() and (str(path).startswith('/usr/local/cuda') or path.is_relative_to(build)):
   shutil.copy2(path,app/path.name)
with executable.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
pathlib.Path(receipt).write_text(json.dumps(dict(toolchain=tools,linked_libraries=linked,compile_host_architecture=platform.machine(),
 configure_seconds=configure_seconds,compile_seconds=compile_seconds,
 executable_sha256=digest,toolchain_manifest_sha256=hashlib.sha256(pathlib.Path('/opt/toolchain/toolchain.json').read_bytes()).hexdigest()),indent=2))
'''


def native_compile_argv(image, source, dependency, build, out, flags, *, name=None, labels=None, build_target="strata-dsv41"):
    """No GPU, network, socket or writable source in the native builder."""
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise ValueError('Native builder requires an immutable image ID')
    mounts = [(source, True), (dependency, True), (build, False), (out, False)]
    argv = ['docker', 'run', '--rm', '--pull=never', '--network=none', '--read-only',
            '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--pids-limit=512', '--cpus=8',
            '--memory=16g', '--memory-swap=16g', '--tmpfs', '/tmp:rw,nosuid,nodev,size=4g']
    for path, readonly in mounts:
        if any(c in str(path) for c in (',', '\n', '\0')):
            raise ValueError('Invalid builder mount')
        argv += ['--mount', f'type=bind,src={path},dst={path}' + (',readonly' if readonly else '')]
    if name:
        argv += ['--name', name]
    for key, value in sorted((labels or {}).items()):
        argv += ['--label', key + '=' + value]
    for key in ('CFLAGS', 'CXXFLAGS', 'LDFLAGS'):
        if key in os.environ:
            argv += ['--env', key + '=' + os.environ[key]]
    return [*argv, '--entrypoint', '/usr/bin/python3', image, '-c', NATIVE_COMPILE,
            str(source), str(build), str(out/'image/app'), str(out/'native-compile.json'), json.dumps(flags), build_target]

def owner_native_overlap(a, gpu, available):
    role = os.getenv('SPARK_OWNER_BUILD')
    allowed = {
        'placement-tier': ('spark-owner-c2-cpu.service', 'factory/llamacpp:star-placement-tier-'),
        'combined-d': ('spark-owner-d-cpu.service', 'factory/llamacpp:star-combined-d-'),
    }
    if not role:
        return None
    if role not in allowed or a.delivery != 'native' or a.build_target != 'llama-server':
        raise ValueError('Owner overlap is limited to the two approved native llama-server builds')
    unit, tag = allowed[role]
    group = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    cpus = sorted(os.sched_getaffinity(0))
    nice = os.getpriority(os.PRIO_PROCESS, 0)
    io = subprocess.check_output(['/usr/bin/ionice', '-p', str(os.getpid())], text=True).strip()
    limit = (Path('/sys/fs/cgroup') / group.lstrip('/') / 'memory.max').read_text().strip()
    if (Path(group).name != unit or not a.tag.startswith(tag) or cpus != list(range(12, 20)) or nice != 19 or
            io != 'idle' or not limit.isdigit() or int(limit) > 6 * 1024**3 or available < 21 * 1024**2):
        raise ValueError('Owner overlap requires the exact build unit, CPU and I/O limits, and sufficient host headroom')
    watched = Path.home() / 'predemo-spark/OPS/runs/p4-cache60-aplus-pass-2-01'
    if gpu:
        start = json.loads((watched / 'start.json').read_bytes())
        scope = json.loads((watched / 'scope.json').read_bytes())
        pids = {int(row.split(',', 1)[0]) for row in gpu.splitlines()}
        if (start['arm'] != 'A+' or start['cpus'] != '0-7' or (watched / 'result.json').exists() or
                pids != {scope['pid']}):
            raise ValueError('Owner overlap permits only the capped A+60 control to hold a compute context')
    return dict(role=role, unit=unit, cpu_affinity=cpus, nice=nice, io_priority=io,
                memory_max_bytes=int(limit), compiler_jobs=4, observed_scope=str(watched) if gpu else None)


def main():
    p = argparse.ArgumentParser()
    for name in ('target','source','commit','tag','out','dependency','dependency-commit'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--build-target', default='strata-dsv41')
    p.add_argument('--delivery', choices=['image', 'native'], default='image')
    p.add_argument('--native-cmake-cache')
    p.add_argument('--native-cmake-cache-sha256')
    p.add_argument('--native-ui-archive-sha256')
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,100}',a.build_target):
        raise ValueError('Invalid build target')
    if a.delivery == 'native' and a.build_target != 'llama-server':
        raise ValueError('Native delivery is limited to llama-server')
    if a.target != 'spark-gb10':
        raise ValueError('Spark worker target mismatch')
    source, out = Path(a.source), Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    record = dict(status='failed', target=a.target, source={'commit': a.commit}, flags=FLAGS, build_target=a.build_target,
                  host_architecture=platform.machine(), phase_seconds={})
    start = time.monotonic()
    def run(name, argv):
        phase_started = time.monotonic()
        try:
            from jiuwenswarm.factory.experiment_jobs import bounded_run
            streams=out/(name+'-streams');streams.mkdir()
            result=bounded_run(list(map(str,argv)),streams,5400,16*1024*1024)
            (out/(name+'.log')).write_bytes((streams/'stdout').read_bytes()+(streams/'stderr').read_bytes())
            if result['stop_reason']:
                raise ValueError('Build phase stopped: '+result['stop_reason'])
            if result['returncode']:
                raise subprocess.CalledProcessError(result['returncode'],argv)
        finally:
            record['phase_seconds'][name] = time.monotonic() - phase_started
        return (out/(name+'.log')).read_text().strip()
    try:
        if platform.machine() not in ('aarch64', 'arm64'):
            raise ValueError('Spark builds require a native ARM64 host; emulation is not admitted')
        if run('head',['git','-C',source,'rev-parse','HEAD']) != a.commit or run('clean',['git','-C',source,'status','--porcelain','--untracked-files=all']):
            raise ValueError('Source changed')
        dependency = Path(a.dependency)
        if run('dependency-head',['git','-C',dependency,'rev-parse','HEAD']) != a.dependency_commit or run('dependency-clean',['git','-C',dependency,'status','--porcelain','--untracked-files=all']):
            raise ValueError('Dependency changed')
        generator = 'Ninja'
        flags = build_flags(a.build_target, dependency)
        if a.delivery == 'native':
            cache = Path(a.native_cmake_cache or '')
            if hashlib.sha256(cache.read_bytes()).hexdigest() != a.native_cmake_cache_sha256:
                raise ValueError('Retained stock CMake cache changed')
            generator, flags = native_recipe(cache)
            record['native_cmake_cache'] = dict(path=str(cache), sha256=a.native_cmake_cache_sha256)
            record['generator'] = generator
        record['flags'] = flags
        record['dependency'] = dict(path=str(dependency), commit=a.dependency_commit)
        record['source']['tree'] = run('tree',['git','-C',source,'rev-parse','HEAD^{tree}'])
        # Compile immutable committed trees, never the editable worktrees.
        import tarfile
        def snapshot(repository, revision, name):
            archive = out / (name + '.tar')
            with archive.open('wb') as stream:
                subprocess.run(['git','-C',str(repository),'archive','--format=tar',revision],
                    stdin=subprocess.DEVNULL,stdout=stream,check=True)
            destination = out / name
            destination.mkdir()
            with tarfile.open(archive) as tree:
                tree.extractall(destination, filter='data')
            from jiuwenswarm.factory.execution_binding import inventory, digest
            record[name + '_sha256'] = digest(inventory(destination))
            return destination
        source = snapshot(source,a.commit,'frozen-source')
        dependency = snapshot(dependency,a.dependency_commit,'frozen-dependency')
        if a.delivery == 'native' and a.native_ui_archive_sha256:
            archive = native_ui_archive(cache)
            if archive is None or hashlib.sha256(archive.read_bytes()).hexdigest() != a.native_ui_archive_sha256:
                raise ValueError('Retained stock UI archive changed')
            # git archive omits build-number metadata that selects the stock UI release.
            dist = source / 'ui/apps/chat/dist'
            dist.mkdir()
            with tarfile.open(archive) as assets:
                assets.extractall(dist, filter='data')
            record['native_ui_archive'] = dict(path=str(archive), sha256=a.native_ui_archive_sha256)
        if a.delivery != 'native':
            flags = build_flags(a.build_target, dependency)
        record['flags'] = flags
        builder_image = os.environ.get('FACTORY_NATIVE_BUILDER_IMAGE')
        if a.delivery == 'native' and builder_image:
            raise ValueError('Stock-matched native delivery requires the host toolchain')
        if builder_image:
            builder_info = json.loads(run('builder-image', ['docker','image','inspect',builder_image]))[0]
            if builder_info['Id'] != builder_image or builder_info['Architecture'] != 'arm64':
                raise ValueError('Native ARM64 builder identity mismatch')
            record['toolchain'] = dict(native_builder_image=builder_image)
        else:
            record['toolchain'] = {t:run(t,[t,'--version']) for t in ('nvcc','gcc','cmake', 'make' if generator == 'Unix Makefiles' else 'ninja')}
            if 'release 13.' not in record['toolchain']['nvcc']:
                raise ValueError('CUDA 13 compiler required')
        # Host compute admission supplements shared queue exclusivity.
        gpu = run('gpu-admission',['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'])
        available = int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))
        record['admission'] = dict(gpu_processes=gpu, available_kib=available)
        overlap = owner_native_overlap(a, gpu, available)
        if overlap:
            record['admission']['owner_overlap'] = overlap
        elif gpu or available < 16*1024**2:
            raise ValueError('Unrelated compute or insufficient available memory')
        identity = dict(build_target=a.build_target, source=record['source'], toolchain=record['toolchain'], flags=flags, dependency=record['dependency'],
                        environment={k:os.environ.get(k) for k in ('PATH','CC','CXX','CUDAHOSTCXX','CUDACXX','CFLAGS','CXXFLAGS','LDFLAGS','LD_LIBRARY_PATH')},
                        recipe_sha256=hashlib.sha256((Path(__file__).resolve().parents[2]/'deploy/spark/Runtime.Dockerfile').read_bytes()).hexdigest(),
                        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        if a.native_ui_archive_sha256:
            identity['native_ui_archive_sha256'] = a.native_ui_archive_sha256
        key = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        build = Path(os.environ['FACTORY_HOME']).parent/'cache'/('deepseek-'+key[:24])
        record['cache_path'], record['configuration_sha256'] = str(build), key
        record['build_cache_present'] = (build/'CMakeCache.txt').is_file()
        # Presence is not a hit: Ninja may still rebuild; retain compile timing/logs.
        app = out/'image/app'
        if builder_image:
            build.mkdir(parents=True, exist_ok=True)
            from jiuwenswarm.factory.lab_lifecycle import OwnedContainerGuard
            with OwnedContainerGuard(out/'native-owner', builder_image,
                    lease_root=Path(os.environ['FACTORY_HOME']).parent/'lab-lease',
                    kind='build', timeout_s=5400) as guard:
                run('native-compile', native_compile_argv(builder_image, source, dependency, build, out, flags,
                                                         name=guard.name, labels=guard.labels, build_target=a.build_target))
            record.update(json.loads((out/'native-compile.json').read_text()), native_builder_image=builder_image)
            record['toolchain']['native_builder_image'] = builder_image
        else:
            run('configure',['cmake','-G',generator,'-S',source,'-B',build,*flags])
            jobs = str(overlap['compiler_jobs']) if overlap else '8'
            run('compile',['cmake','--build',build,'--parallel',jobs,'--target',a.build_target])
            app.mkdir(parents=True)
            executable = build/('bin/'+a.build_target if a.build_target=='llama-server' else a.build_target)
            shutil.copy2(executable,app/executable.name)
            # Include non-system shared dependencies resolved by the actual executable.
            ldd = run('ldd',['ldd',executable])
            record['linked_libraries'] = ldd
            for line in ldd.splitlines():
                if '=>' in line:
                    path = Path(line.split('=>',1)[1].strip().split()[0])
                    if path.is_file() and (str(path).startswith('/usr/local/cuda') or path.is_relative_to(build)):
                        shutil.copy2(path,app/path.name)
            record['executable_sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()
        if a.delivery == 'native':
            executable = app / 'llama-server'
            record.update(delivery='native', executable=dict(path=str(executable.resolve()),
                sha256=hashlib.sha256(executable.read_bytes()).hexdigest(), size=executable.stat().st_size),
                status='success')
            return
        recipe = Path(__file__).resolve().parents[2]/'deploy/spark/Runtime.Dockerfile'
        recipe_text = recipe.read_text()
        if a.build_target == 'llama-server':
            recipe_text = recipe_text.replace('/opt/strata','/opt/llamacpp').replace('strata-dsv41','llama-server')
        (out/'image/Dockerfile').write_text(recipe_text)
        argv = ['docker','build','--network=none','--pull=false','-t',a.tag]
        from jiuwenswarm.factory.targets import labels
        for k,v in labels(a.target).items():
            argv += ['--label',k+'='+v]
        argv += ['--label','factory.source='+a.commit,'--label','factory.owner=cc-dgx-spark',out/'image']
        run('package',argv)
        record['image'] = json.loads(run('image',['docker','image','inspect',a.tag]))[0]
        immutable_tag=('factory/llamacpp:artifact-' if a.build_target=='llama-server' else 'factory/strata:artifact-')+record['image']['Id'].split(':',1)[1]
        run('retain-image',['docker','tag',record['image']['Id'],immutable_tag])
        record['retention_tag']=immutable_tag
        record['status'] = 'success'
    finally:
        record['build_wall_seconds'] = time.monotonic()-start
        (out/'build-record.json').write_text(json.dumps(record,indent=2))

if __name__ == '__main__':
    main()
