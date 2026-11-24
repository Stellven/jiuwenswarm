"""Send source, not images: the lab assembles the engine on its own hardware.

The factory may run on a different architecture from the lab (an x86 workstation and an
arm64 DGX Spark, say). Instead of an image, it can ship a **source bundle**
(``factory.lab-source/1``): the base commit of any repository, branch or fork, the diff
from that commit to the tree under test, the name of a build recipe, and the source
dependencies the build needs, each described the same way. The lab rebuilds the exact
tree, checks its git tree hash, compiles natively and packages a runtime image.

Builds are fast after the first one. Each (repository, base commit, recipe, flags)
gets a **warm slot**: a persistent checkout and build directory. A new request resets
the checkout to the base commit (git rewrites only the files that differ, so the
other files keep their timestamps), applies the diff and runs an incremental build,
which recompiles only what the diff touches. Ninja and ccache are used when present.

    # factory side: bundle a checkout against the commit the lab can fetch
    python -m jiuwenswarm.factory.lab_build bundle CHECKOUT --base <commit> --recipe llama-server-cuda-sm121 -o src.tar
    # lab side: assemble a bundle into an image
    python -m jiuwenswarm.factory.lab_build assemble src.tar --cache ~/.jiuwenswarm-factory/lab-build
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

SOURCE = 'factory.lab-source/1'
BUILD = 'factory.lab-build/1'
MEDIA_TYPE = 'application/vnd.factory.lab-source+tar'
FLAG = re.compile(r'^-D[A-Z][A-Z0-9_]*(:[A-Z]+)?=[A-Za-z0-9_.,;:+=/-]*$')
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
COMMIT = re.compile(r'^[0-9a-f]{40}$')
SPARK_RUNTIME = 'ghcr.io/ggml-org/llama.cpp@sha256:695214dcb4d4062014335702caee98836bbf92c5974b78331c70e152176cbf08'

# Recipes a lab knows. A bundle names one; it cannot bring its own build commands.
RECIPES = {
    'llama-server-cuda-sm121': dict(
        does='llama.cpp server for DGX Spark GB10 (CUDA 13, sm_121), packaged on the stock runtime image.',
        machine=('aarch64', 'arm64'), targets=['llama-server'], executable='bin/llama-server',
        flags=['-DCMAKE_BUILD_TYPE=Release', '-DGGML_CUDA=ON', '-DCMAKE_CUDA_ARCHITECTURES=121-real',
               '-DGGML_NATIVE=OFF', '-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16+i8mm', '-DGGML_OPENMP=OFF',
               '-DLLAMA_BUILD_TESTS=OFF', '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_SERVER=ON',
               '-DLLAMA_OPENSSL=OFF', '-DLLAMA_CURL=OFF', '-DLLAMA_BUILD_UI=OFF', '-DLLAMA_USE_PREBUILT_UI=OFF'],
        env={'PATH': '/usr/local/cuda/bin:{PATH}'}, library_roots=['/usr/local/cuda'],
        runtime=dict(base=SPARK_RUNTIME, install='/opt/llamacpp')),
    'llama-server-cpu': dict(
        does='llama.cpp server without CUDA, for any Linux machine.',
        machine=None, targets=['llama-server'], executable='bin/llama-server',
        flags=['-DCMAKE_BUILD_TYPE=Release', '-DGGML_NATIVE=OFF', '-DLLAMA_BUILD_TESTS=OFF',
               '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_SERVER=ON', '-DLLAMA_OPENSSL=OFF', '-DLLAMA_CURL=OFF', '-DLLAMA_BUILD_UI=OFF', '-DLLAMA_USE_PREBUILT_UI=OFF'],
        env={}, library_roots=[], runtime=None),
}


class BuildError(ValueError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _git(repository, *args, env=None, binary=False, check=True):
    done = subprocess.run(['git', '-C', str(repository), *args], capture_output=True, env=env, stdin=subprocess.DEVNULL)
    if check and done.returncode:
        raise BuildError(f'git {" ".join(args[:3])}: {done.stderr.decode(errors="replace").strip()[-300:]}')
    return done.stdout if binary else done.stdout.decode().strip()


def load_recipes(extra=None):
    """Built-in recipes plus a lab's own (a JSON file of the same shape, ``$FACTORY_LAB_RECIPES``)."""
    recipes = dict(RECIPES)
    path = extra or os.environ.get('FACTORY_LAB_RECIPES')
    if path:
        recipes.update(json.loads(Path(path).expanduser().read_text()))
    return recipes


# ---- factory side ----------------------------------------------------------------------
def _public_repository(url):
    # A local path names a directory on this machine; it means nothing to the lab.
    return url if url and re.match(r'^(https?://|ssh://|git@|git://)', url) else None


def _source_spec(checkout, base, staging, prefix, repository=None, include_base=False, worktree=True):
    checkout = Path(checkout)
    base = _git(checkout, 'rev-parse', '--verify', f'{base}^{{commit}}')
    if worktree:
        with tempfile.TemporaryDirectory() as scratch:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(scratch) / 'index'))
            _git(checkout, 'read-tree', 'HEAD', env=env)
            _git(checkout, 'add', '-A', env=env)
            head_tree = _git(checkout, 'write-tree', env=env)
    else:
        head_tree = _git(checkout, 'rev-parse', 'HEAD^{tree}')
    patch = _git(checkout, 'diff', '--binary', '--full-index', '--no-renames', f'{base}^{{tree}}', head_tree, binary=True)
    (staging / f'{prefix}patch.diff').write_bytes(patch)
    repository = _public_repository(repository or _git(checkout, 'remote', 'get-url', 'origin', check=False))
    spec = dict(repository=repository, base_commit=base, head_tree=head_tree,
                patch=dict(name=f'{prefix}patch.diff', sha256=hashlib.sha256(patch).hexdigest(), size=len(patch)))
    if include_base or repository is None:
        ref = f'refs/factory-lab/base-{base[:12]}'
        _git(checkout, 'update-ref', ref, base)
        try:
            _git(checkout, 'bundle', 'create', str(staging / f'{prefix}base.bundle'), ref)
        finally:
            _git(checkout, 'update-ref', '-d', ref)
        path = staging / f'{prefix}base.bundle'
        spec['base_bundle'] = dict(name=path.name, sha256=sha256_file(path), size=path.stat().st_size, ref=ref)
    return spec


def make_bundle(checkout, base, output, recipe, repository=None, include_base=False, worktree=True,
                deps=(), extra_flags=()):
    """Write a source bundle for ``checkout`` against ``base``; return its description.

    ``deps`` lists source dependencies: dicts with ``name``, ``checkout``, ``base``,
    ``cmake_var`` and optionally ``repository`` and ``include_base``. The lab assembles
    each one and passes its directory to CMake as ``-D<cmake_var>=<dir>``.
    """
    if recipe not in load_recipes():
        raise BuildError(f'Unknown recipe {recipe!r}; known: {", ".join(load_recipes())}')
    for flag in extra_flags:
        if not FLAG.fullmatch(flag):
            raise BuildError(f'Extra flag {flag!r} must look like -DNAME=value')
    with tempfile.TemporaryDirectory() as scratch:
        staging = Path(scratch)
        source = _source_spec(checkout, base, staging, '', repository, include_base, worktree)
        dependencies = []
        for dep in deps:
            if not NAME.fullmatch(dep.get('name', '')) or not re.fullmatch(r'[A-Z][A-Z0-9_]*', dep.get('cmake_var', '')):
                raise BuildError('A dependency needs a name and a CMake variable')
            spec = _source_spec(dep['checkout'], dep['base'], staging, f'deps-{dep["name"]}-',
                                dep.get('repository'), dep.get('include_base', False), dep.get('worktree', True))
            dependencies.append(dict(spec, name=dep['name'], cmake_var=dep['cmake_var']))
        document = dict(schema=SOURCE, recipe=recipe, extra_flags=list(extra_flags), source=source, deps=dependencies)
        (staging / 'source.json').write_text(json.dumps(document, indent=1, sort_keys=True))
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output, 'w') as archive:
            for path in sorted(staging.iterdir()):
                info = archive.gettarinfo(str(path), path.name)
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mtime = 0
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
    return dict(path=str(output), sha256=sha256_file(output), size=output.stat().st_size, recipe=recipe,
                repository=source['repository'], base_commit=source['base_commit'], head_tree=source['head_tree'],
                deps=[dict(name=d['name'], head_tree=d['head_tree']) for d in dependencies])


def read_bundle(path):
    """The ``source.json`` of a bundle, without unpacking the rest."""
    with tarfile.open(path) as archive:
        member = archive.extractfile('source.json')
        if member is None:
            raise BuildError('Not a source bundle: no source.json')
        document = json.load(member)
    if document.get('schema') != SOURCE:
        raise BuildError('Not a factory.lab-source/1 bundle')
    return document


# ---- lab side --------------------------------------------------------------------------
@contextmanager
def _locked(path):
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _unpack(bundle, destination):
    with tarfile.open(bundle) as archive:
        archive.extractall(destination, filter='data')
    document = read_bundle(bundle)
    for spec in [document['source'], *document['deps']]:
        for key in ('patch', 'base_bundle'):
            item = spec.get(key)
            if item and (not NAME.fullmatch(item['name']) or sha256_file(destination / item['name']) != item['sha256']):
                raise BuildError(f'{item["name"]}: differs from its digest in source.json')
        if not COMMIT.fullmatch(spec['base_commit']) or not COMMIT.fullmatch(spec['head_tree']):
            raise BuildError('Base commit and head tree must be full git object ids')
    return document


def _mirror(cache, spec, files, seconds):
    """A bare repository holding the base commit: fetched from a shipped bundle or the network."""
    key = hashlib.sha256((spec.get('repository') or spec['base_commit']).encode()).hexdigest()[:16]
    mirror = cache / 'git' / f'{key}.git'
    if not (mirror / 'HEAD').is_file():
        mirror.parent.mkdir(parents=True, exist_ok=True)
        _git(mirror.parent, 'init', '-q', '--bare', mirror.name)
    started = time.monotonic()
    present = subprocess.run(['git', '-C', str(mirror), 'cat-file', '-e', f'{spec["base_commit"]}^{{commit}}'],
                             capture_output=True).returncode == 0
    if present:
        pass
    elif spec.get('base_bundle'):
        _git(mirror, 'fetch', '-q', str(files / spec['base_bundle']['name']), f'+{spec["base_bundle"]["ref"]}:refs/bases/{spec["base_commit"]}')
    elif spec.get('repository'):
        _git(mirror, 'fetch', '-q', '--depth=1', spec['repository'], spec['base_commit'])
        _git(mirror, 'update-ref', f'refs/bases/{spec["base_commit"]}', spec['base_commit'])
    else:
        raise BuildError('The base commit is neither shipped nor fetchable')
    seconds['fetch'] = seconds.get('fetch', 0) + round(time.monotonic() - started, 3)
    return mirror


def _checkout(mirror, spec, files, directory, seconds):
    """Reset ``directory`` to the base commit and apply the diff; check the resulting tree."""
    started = time.monotonic()
    if not (directory / '.git').exists():
        # Read objects straight from the mirror; a local clone of a shallow mirror would not.
        directory.mkdir(parents=True, exist_ok=True)
        _git(directory, 'init', '-q')
        (directory / '.git' / 'objects' / 'info' / 'alternates').write_text(str((mirror / 'objects').resolve()) + '\n')
    if (mirror / 'shallow').is_file():
        shutil.copyfile(mirror / 'shallow', directory / '.git' / 'shallow')
    _git(directory, 'checkout', '-q', '-f', '--detach', spec['base_commit'])
    _git(directory, 'clean', '-fdxq')
    patch = files / spec['patch']['name']
    if patch.stat().st_size:
        _git(directory, 'apply', '--index', '--whitespace=nowarn', str(patch))
    tree = _git(directory, 'write-tree')
    if tree != spec['head_tree']:
        raise BuildError(f'Assembled tree {tree[:12]} is not the tree under test {spec["head_tree"][:12]}')
    seconds['checkout'] = seconds.get('checkout', 0) + round(time.monotonic() - started, 3)


def _tool_versions(env):
    versions = {}
    for tool in ('cmake', 'ninja', 'ccache', 'nvcc', 'gcc'):
        found = shutil.which(tool, path=env.get('PATH'))
        if found:
            out = subprocess.run([found, '--version'], capture_output=True, text=True, env=env).stdout.strip().splitlines()
            versions[tool] = out[-1] if tool == 'nvcc' and out else (out[0] if out else '')
    return versions


def assemble(bundle, cache, recipes=None, jobs=None, tag=None, image=True, log=None):
    """Build a source bundle on this machine; return a ``factory.lab-build/1`` record."""
    cache = Path(cache).expanduser()
    recipes = load_recipes() if recipes is None else recipes
    record = dict(schema=BUILD, status='failed', machine=platform.machine(), seconds={})
    seconds = record['seconds']
    started = time.monotonic()
    with tempfile.TemporaryDirectory(dir=_mkdir(cache / 'tmp')) as scratch:
        files = Path(scratch)
        document = _unpack(bundle, files)
        recipe = recipes.get(document['recipe'])
        if recipe is None:
            raise BuildError(f'This lab has no recipe {document["recipe"]!r}')
        if recipe.get('machine') and platform.machine() not in recipe['machine']:
            raise BuildError(f'Recipe {document["recipe"]} builds on {"/".join(recipe["machine"])}, not {platform.machine()}')
        for flag in document.get('extra_flags', []):
            if not FLAG.fullmatch(flag):
                raise BuildError(f'Refused extra flag {flag!r}')
        source = document['source']
        flags = [*recipe['flags'], *document.get('extra_flags', [])]
        env = dict(os.environ)
        for key, value in recipe.get('env', {}).items():
            env[key] = value.replace('{PATH}', os.environ.get('PATH', ''))
        generator = 'Ninja' if shutil.which('ninja', path=env.get('PATH')) else 'Unix Makefiles'
        launcher = []
        if shutil.which('ccache', path=env.get('PATH')):
            launcher = [f'-DCMAKE_{lang}_COMPILER_LAUNCHER=ccache' for lang in ('C', 'CXX', 'CUDA')]
        dep_specs = [dict(name=d['name'], repository=d.get('repository'), base=d['base_commit'], var=d['cmake_var'])
                     for d in document['deps']]
        slot_key = hashlib.sha256(json.dumps([source.get('repository') or source['base_commit'], source['base_commit'],
                                              document['recipe'], flags, generator, dep_specs], sort_keys=True).encode()).hexdigest()[:20]
        slot = cache / 'slots' / slot_key
        if launcher:
            # One compiler cache for every slot; paths relative to the slot so slots share hits.
            env.setdefault('CCACHE_DIR', str(cache / 'ccache'))
            env['CCACHE_BASEDIR'] = str(slot)
        record.update(recipe=document['recipe'], repository=source.get('repository'), base_commit=source['base_commit'],
                      head_tree=source['head_tree'], flags=flags, generator=generator, ccache=bool(launcher), slot=slot_key,
                      deps=[dict(name=d['name'], head_tree=d['head_tree']) for d in document['deps']])
        with _locked(slot / 'lock'):
            mirror = _mirror(cache, source, files, seconds)
            _checkout(mirror, source, files, slot / 'src', seconds)
            for dep in document['deps']:
                dep_mirror = _mirror(cache, dep, files, seconds)
                _checkout(dep_mirror, dep, files, slot / 'deps' / dep['name'], seconds)
                flags = [*flags, f'-D{dep["cmake_var"]}={slot / "deps" / dep["name"]}']
            build = slot / 'build'
            record['warm'] = (build / 'CMakeCache.txt').is_file()
            jobs = int(jobs or os.environ.get('FACTORY_LAB_BUILD_JOBS') or min(os.cpu_count() or 4, 12))
            record['jobs'] = jobs
            nice = ['nice', '-n', '10'] if shutil.which('nice') else []

            def run(phase, argv):
                began = time.monotonic()
                done = subprocess.run([*nice, *map(str, argv)], capture_output=True, text=True, env=env)
                seconds[phase] = round(seconds.get(phase, 0) + time.monotonic() - began, 3)
                (slot / f'{phase}.log').write_text(done.stdout[-200000:] + done.stderr[-200000:])
                if done.returncode:
                    raise BuildError(f'{phase} failed ({done.returncode}): {done.stderr.strip()[-600:]}')
                return done.stdout

            if not record['warm']:
                run('configure', ['cmake', '-G', generator, '-S', slot / 'src', '-B', build, *launcher, *flags])
            out = run('compile', ['cmake', '--build', build, '--parallel', jobs, '--target', *recipe['targets']])
            record['compiled_units'] = len(re.findall(r'^\[\s*\d+/\d+\]|Building (C|CXX|CUDA) object', out, re.M))
            record['toolchain'] = _tool_versions(env)
            # Package what the executable needs from the build and the named toolkits.
            began = time.monotonic()
            # The image context stays in the slot: toolkit libraries (large, unchanged between
            # builds) and the engine's own files are separate layers, so Docker reuses the first.
            context = slot / 'image'
            app, toolkit = context / 'app', context / 'toolkit'
            shutil.rmtree(app, ignore_errors=True)
            app.mkdir(parents=True)
            toolkit.mkdir(parents=True, exist_ok=True)
            executable = build / recipe['executable']
            shutil.copy2(executable, app / executable.name)
            ldd = subprocess.run(['ldd', str(executable)], capture_output=True, text=True,
                                 env=dict(env, LD_LIBRARY_PATH=str(build / 'bin'))).stdout
            wanted = set()
            for line in ldd.splitlines():
                if '=>' not in line:
                    continue
                path = Path(line.split('=>', 1)[1].strip().split()[0])
                if not path.is_file():
                    continue
                if path.resolve().is_relative_to(build.resolve()):
                    shutil.copy2(path.resolve(), app / path.name)
                elif any(str(path).startswith(root) for root in recipe.get('library_roots', [])):
                    wanted.add(path.name)
                    target, origin = toolkit / path.name, path.resolve()
                    if (not target.is_file() or target.stat().st_size != origin.stat().st_size
                            or target.stat().st_mtime_ns != origin.stat().st_mtime_ns):
                        shutil.copy2(origin, target)  # copy2 keeps the mtime, so an unchanged library is skipped next time
            for stale in toolkit.iterdir():
                if stale.name not in wanted:
                    stale.unlink()
            for library in (build / 'bin').glob('*.so*'):
                if not (app / library.name).exists():
                    shutil.copy2(library, app / library.name)
            record['executable_sha256'] = sha256_file(app / executable.name)
            record['files'] = sorted(p.name for p in [*app.iterdir(), *toolkit.iterdir()])
            seconds['package'] = round(time.monotonic() - began, 3)
            runtime = recipe.get('runtime')
            if image and runtime:
                began = time.monotonic()
                install = runtime['install']
                (context / 'Dockerfile').write_text(
                    f'FROM {runtime["base"]}\nUSER root\nCOPY toolkit/ {install}/\nCOPY app/ {install}/\n'
                    f'ENV LD_LIBRARY_PATH={install}:/usr/local/nvidia/lib:/usr/local/nvidia/lib64\n'
                    f'WORKDIR {install}\nENTRYPOINT ["{install}/{executable.name}"]\n')
                tag = tag or f'factory/lab-build:{source["head_tree"][:16]}'
                from .lab_payload import _docker
                done = _docker(['docker', 'build', '--network=none', '--pull=false', '-t', tag,
                                '--label', f'factory.head_tree={source["head_tree"]}',
                                '--label', f'factory.base_commit={source["base_commit"]}',
                                '--label', f'factory.recipe={document["recipe"]}', str(context)], 1800)
                if done.returncode:
                    raise BuildError(f'docker build failed: {(done.stderr or done.stdout).strip()[-600:]}')
                inspected = _docker(['docker', 'image', 'inspect', '--format', '{{.Id}}', tag], 60)
                record.update(image_id=inspected.stdout.strip(), tag=tag)
                seconds['image'] = round(time.monotonic() - began, 3)
            else:
                kept = slot / 'last-app'
                shutil.rmtree(kept, ignore_errors=True)
                shutil.copytree(app, kept)
                record['app'] = str(kept)
    record['status'] = 'succeeded'
    record['seconds']['total'] = round(time.monotonic() - started, 3)
    if log:
        log(json.dumps(dict(head_tree=record['head_tree'][:12], warm=record['warm'], seconds=record['seconds'])))
    return record


def _mkdir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---- command line ----------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(prog='lab-build', description='Bundle source for a lab, or assemble a bundle in the lab.')
    sub = parser.add_subparsers(dest='command', required=True)
    bundle = sub.add_parser('bundle', help='factory side: write a source bundle')
    bundle.add_argument('checkout')
    bundle.add_argument('--base', required=True, help='commit the lab can fetch (upstream or fork); the diff starts here')
    bundle.add_argument('--recipe', required=True)
    bundle.add_argument('--repository', help='URL of the repository or fork holding --base (default: origin)')
    bundle.add_argument('--include-base', action='store_true', help='ship the base history too (no network needed in the lab)')
    bundle.add_argument('--committed', action='store_true', help='bundle HEAD only, not uncommitted changes')
    bundle.add_argument('--dep', action='append', default=[], help='NAME=CHECKOUT@BASE:CMAKE_VAR, a source dependency')
    bundle.add_argument('--flag', action='append', default=[], help='extra -DNAME=value for CMake')
    bundle.add_argument('-o', '--output', required=True)
    build = sub.add_parser('assemble', help='lab side: build a bundle here')
    build.add_argument('bundle')
    build.add_argument('--cache', default=os.environ.get('FACTORY_LAB_BUILD_CACHE', '~/.jiuwenswarm-factory/lab-build'))
    build.add_argument('--jobs', type=int)
    build.add_argument('--tag')
    build.add_argument('--no-image', action='store_true')
    sub.add_parser('recipes', help='list the recipes this lab knows')
    args = parser.parse_args(argv)
    try:
        if args.command == 'recipes':
            result = {name: recipe['does'] for name, recipe in load_recipes().items()}
        elif args.command == 'bundle':
            deps = []
            for value in args.dep:
                match = re.fullmatch(r'([^=]+)=(.+)@([^:]+):([A-Z][A-Z0-9_]*)', value)
                if not match:
                    raise BuildError('--dep takes NAME=CHECKOUT@BASE:CMAKE_VAR')
                deps.append(dict(name=match[1], checkout=match[2], base=match[3], cmake_var=match[4]))
            result = make_bundle(args.checkout, args.base, args.output, args.recipe, args.repository,
                                 args.include_base, not args.committed, deps, args.flag)
        else:
            result = assemble(args.bundle, args.cache, jobs=args.jobs, tag=args.tag, image=not args.no_image,
                              log=lambda line: print(line, file=sys.stderr))
    except (BuildError, OSError) as exc:
        print(json.dumps(dict(error=str(exc))), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
