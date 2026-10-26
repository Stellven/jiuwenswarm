"""Offline installed-wheel rebuild from an explicitly pinned complete runtime.

Used only by Dockerfile.pipeline02-fast. Reuses the base's built UI assets and
installed dependency closure. It never downloads, resolves, or rebuilds the SDK.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from email.parser import BytesParser

BASE = 'sha256:f31901c0b25c0856399b17c56bc50f9971d6bc86a7e07e00d57418cd0d7ab9ba'
PYTHON = '/opt/venv/bin/python'


def run(*args):
    subprocess.run(args, check=True, cwd='/tmp')


def inventory():
    return {d.metadata['Name'].lower():d.version for d in metadata.distributions()}


def copy_source(source, target):
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','node_modules','dist','.git','.venv','*.egg-info','auth.json','credentials.json','secrets.json','.env','.env.local'),symlinks=True)


def build(project, output):
    run('uv','build','--wheel','--python',PYTHON,'--offline','--no-cache','--no-build-isolation','--out-dir',str(output),str(project))


def install(wheel):
    run('uv','pip','install','--python',PYTHON,'--offline','--no-deps','--reinstall',str(wheel))


def identity(root):
    run(PYTHON,'/context/deploy/m1/build_identity.py','--lock',str(root/'uv.lock'),
        '--project',str(root/'pyproject.toml'),'--source',str(root/'jiuwenswarm'),
        '--tui-source',str(root/'packages/jiuwenswarm-tui/jiuwenswarm_tui'),
        '--output','/usr/local/share/ai4r-build-identity.json')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['app','runner'],required=True)
    parser.add_argument('--dependency-image-id',required=True);args=parser.parse_args()
    if args.dependency_image_id != BASE:
        raise ValueError('EXACT_BASE_IMAGE_PIN_REQUIRED')
    context=Path('/context');root=Path('/build/project');root.mkdir(parents=True)
    output=Path('/usr/local/share/ai4r-fast-wheels');output.mkdir(exist_ok=True)
    before=inventory();product=metadata.distribution('workswarm');installed=Path(product.locate_file('jiuwenswarm'))
    previous=json.loads(Path('/usr/local/share/ai4r-build-identity.json').read_bytes())
    lock=(context/'uv.lock').read_bytes()
    if hashlib.sha256(lock).hexdigest()!=previous['uv_lock_sha256']:
        raise ValueError('LOCK_CHANGED_REQUIRES_NEW_DEPENDENCY_BUILD')
    if args.mode=='app':
        for name in ('pyproject.toml','uv.lock','LICENSE','OPEN_SOURCE_SOFTWARE_NOTICE.md'):
            shutil.copy2(context/name,root/name)
        for name in ('jiuwenswarm','jiuwenbox','packages/jiuwenswarm-tui'):
            copy_source(context/name,root/name)
        assets=['channels/web/frontend/dist','channels/tui/frontend/dist','channels/tui/frontend/node_modules','channels/tui/frontend/package.json']
        for name in assets:
            source=installed/name;target=root/'jiuwenswarm'/name
            if not source.exists():raise ValueError('BASE_UI_ASSET_MISSING:'+name)
            if target.exists():shutil.rmtree(target) if target.is_dir() else target.unlink()
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copytree(source,target,symlinks=True) if source.is_dir() else shutil.copy2(source,target)
        old_requirements=sorted(product.metadata.get_all('Requires-Dist') or [])
        build(root/'packages/jiuwenswarm-tui',output);build(root,output)
        native=list(output.glob('workswarm-*.whl'))
        if len(native)!=1:raise ValueError('EXACT_NATIVE_WHEEL_REQUIRED')
        with zipfile.ZipFile(native[0]) as archive:
            names=[n for n in archive.namelist() if n.count('/')==1 and n.endswith('.dist-info/METADATA')]
            new_requirements=sorted(BytesParser().parsebytes(archive.read(names[0])).get_all('Requires-Dist') or [])
        if new_requirements!=old_requirements:raise ValueError('DEPENDENCY_DECLARATIONS_CHANGED')
        for wheel in sorted(output.glob('*.whl')):install(wheel)
        # Source egg-info cannot shadow the installed wheel's metadata.
        for path in root.rglob('*.egg-info'):
            if path.is_dir():shutil.rmtree(path)
        after=inventory()
        if {k:v for k,v in before.items() if k not in {'workswarm','workswarm-tui'}} != {k:v for k,v in after.items() if k not in {'workswarm','workswarm-tui'}}:
            raise ValueError('DEPENDENCY_INVENTORY_CHANGED')
        identity(root)
        run(PYTHON,'/context/scripts/research_compat_wheel.py','--output',str(output),'--license',str(root/'LICENSE'))
        # Audit the three newly delivered wheels; retain original base wheelhouse.
        Path('/usr/local/share/ai4r-wheel-assets.json').unlink(missing_ok=True)
        run(PYTHON,'/context/scripts/research_offline_assets.py','--wheelhouse',str(output),
            '--project',str(root/'pyproject.toml'),'--lock',str(root/'uv.lock'),
            '--generated-root',str(root/'jiuwenswarm/channels/tui/frontend'),
            '--output','/usr/local/share/ai4r-wheel-assets.json')
        manifest={'schema':'ai4r-fast-rebuild:1','dependency_image_id':BASE,'mode':'app',
            'asset_origin':'exact installed base image; no frontend build',
            'uv_lock_sha256':hashlib.sha256(lock).hexdigest(),
            'dependency_inventory_unchanged':True,
            'wheels':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.whl')}}
        Path('/usr/local/share/ai4r-fast-rebuild.json').write_text(json.dumps(manifest,indent=2)+'\n')
    else:
        # A separate genuine wheel owns runner-only code, not the app wheel.
        source=root/'runner';source.mkdir()
        packages={'benchmarks':'benchmarks','benchmarks.harbor_pilot':'benchmarks/harbor_pilot','benchmarks.harbor_suite':'benchmarks/harbor_suite','jiuwenswarm.research_sidecar':'jiuwenswarm/research_sidecar'}
        for package,relative in packages.items():
            destination=source/relative;destination.mkdir(parents=True,exist_ok=True)
            for file in (context/relative).glob('*.py'):shutil.copy2(file,destination/file.name)
        (source/'pyproject.toml').write_text('[build-system]\nrequires=["setuptools>=61.0"]\nbuild-backend="setuptools.build_meta"\n[project]\nname="ai4r-root-runner-tools"\nversion="1.0.0"\n[tool.setuptools]\npackages='+json.dumps(list(packages))+'\ninclude-package-data=false\n')
        build(source,output)
        wheel=next(output.glob('ai4r_root_runner_tools-*.whl'));install(wheel)
        # Original benchmark inputs and protected referee assets are mounted by
        # the operator, never copied into this tool wheel or exposed to the app.
        module=metadata.distribution('ai4r-root-runner-tools')
        files={str(p):hashlib.sha256(Path(module.locate_file(p)).read_bytes()).hexdigest() for p in module.files or [] if str(p).endswith('.py')}
        Path('/usr/local/share/ai4r-root-runner-tools.json').write_text(json.dumps({'schema':'ai4r-root-runner-tools:1','wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'files':files},indent=2)+'\n')
        if {k:v for k,v in inventory().items() if k!='ai4r-root-runner-tools'}!=before:raise ValueError('RUNNER_DEPENDENCY_INVENTORY_CHANGED')
        identity(context)


if __name__=='__main__':main()
