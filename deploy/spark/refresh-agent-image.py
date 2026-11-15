"""Refresh only factory source in the retained dependency context, then qualify.

Run only after final source tests and after GPU measurements have finished.
The existing mission role receipt is read, never overwritten.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

REPO = Path(__file__).resolve().parents[2]
SMOKE = r'''
import importlib,importlib.util,json,pathlib,subprocess
from codex_cli_bin import bundled_codex_path
from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm
from jiuwenswarm.ccv2.ccv2 import Host
for name in ('engine_adapters','strata_lab','lab_lifecycle','lab_recorder','methodology','mission_supervisor','benchmark','benchmark_worker','benchmark_data','benchmark_analysis','strata_components','strata_prefill','loop','deep_profile','expert_prediction','hypotheses','prefill_workbench','prefill_worker','cc_qualification','experiment_methods','job_packages','broad_benchmark','throughput_workbench','cc_job_metrics','lab_evidence','fixed_placement_benchmark','branch_workbench','evidence_digest'):
 importlib.import_module('jiuwenswarm.factory.'+name)
if importlib.util.find_spec('jiuwenswarm.factory.fixed_screen_benchmark') is not None:
 importlib.import_module('jiuwenswarm.factory.fixed_screen_benchmark')
host=Host(pathlib.Path('/tmp/sealed-capsules'),session_grants=[])
sealed=[]
for capsule in sorted(pathlib.Path('/factory/jiuwenswarm/factory/ccs').iterdir()):
 if (capsule/'cc.yaml').is_file():
  sealed.append(dict(directory=capsule.name,release=host.prepare(capsule)))
assert {'standard_benchmark','strata_verified_drafting','lab_client','evidence','engine_factory_loop','deep_profile','expert_prediction','strata_prefill_chunk','methodology_hypothesis','strata_prefill_workbench','cc_qualification','inference_lab','strata_throughput_workbench','strata_fixed_placement','expert_cache_lab','ssd_streaming_lab','heterogeneous_placement_lab','precision_lab','kv_reuse_lab','serving_scheduler_lab','methodology_transfer_lab','branch_workbench','cc_workflow_lab','native_inventory_once','strata_budget_workbench','memory_residency_lab','gpu_kernel_lab','evidence_digest_lab'} <= {v['directory'] for v in sealed}
print(json.dumps(dict(actual_facade_import=True,standalone_source=True,source_bind=False,
 codex_version=subprocess.check_output([str(bundled_codex_path()),'--version'],text=True).strip(),
 sealed_capsules=sealed)))
'''


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=REPO.parents[1] if len(REPO.parents)>1 else Path.cwd())
    p.add_argument('--context', type=Path)
    p.add_argument('--tag', default='factory/agent:cc-dgx-spark-final')
    a = p.parse_args()
    root = a.root.resolve()
    context = (a.context or root/'agent-build-context-001').resolve()
    manifest_path = context/'closure.json'
    if not manifest_path.is_file() or not (context/'site').is_dir() or not (context/'system').is_dir():
        raise ValueError('Existing admitted agent dependency context is required')
    if context == REPO or not context.is_relative_to(root):
        raise ValueError('Use the owned build context outside the source checkout')
    with (context/'.refresh.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        results = root/'results'
        results.mkdir(parents=True, exist_ok=True)
        # Preserve prior evidence by content hash before any fixed-name log or
        # receipt is overwritten. Archives are append-only; old tags remain.
        for name in ('agent-final-image-build.log', 'agent-final-standalone-smoke.log',
                     'final-role-images.json', 'mission-role-images.json'):
            prior = results/name
            if prior.is_file():
                archive = results/'prior-agent-refresh'/(sha(prior)+'-'+name)
                archive.parent.mkdir(parents=True, exist_ok=True)
                if archive.exists() and sha(archive) != sha(prior):
                    raise ValueError('Archived prior image evidence differs')
                if not archive.exists():
                    shutil.copy2(prior, archive)
        manifest = json.loads(manifest_path.read_text())
        previous_manifest_sha256 = sha(manifest_path)
        archived_manifest = root/'results'/('agent-closure-'+previous_manifest_sha256+'.json')
        if archived_manifest.exists():
            if sha(archived_manifest) != previous_manifest_sha256:
                raise ValueError('Archived original closure identity differs')
        else:
            shutil.copy2(manifest_path, archived_manifest)
        for relative in ('jiuwenswarm', 'deploy/spark'):
            destination = context/relative
            stage = destination.with_name(destination.name+'-refresh-'+uuid.uuid4().hex)
            shutil.copytree(REPO/relative, stage, ignore=shutil.ignore_patterns(
                '__pycache__', '*.pyc', '.git', '.env', 'auth.json'))
            if destination.exists():
                shutil.rmtree(destination)
            stage.rename(destination)
        retained = {k:v for k,v in manifest['files'].items()
                    if not k.startswith(('jiuwenswarm/', 'deploy/spark/'))}
        for relative in ('jiuwenswarm', 'deploy/spark'):
            for path in sorted((context/relative).rglob('*')):
                if path.is_file():
                    retained[str(path.relative_to(context))] = sha(path)
        manifest.update(files=retained, source_refresh=dict(previous_manifest_sha256=previous_manifest_sha256,
            previous_manifest_path=str(archived_manifest),
            dependency_files_reused=True, source_path=str(REPO),
            git_head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),
            git_dirty=bool(subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'],text=True).strip())))
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        shutil.copy2(REPO/'deploy/spark/Agent.Dockerfile', context/'Dockerfile')
        results = root/'results'
        with (results/'agent-final-image-build.log').open('w') as log:
            subprocess.run(['docker','build','--network=none','--pull=false','-t',a.tag,str(context)],
                           stdout=log,stderr=subprocess.STDOUT,check=True)
        info=json.loads(subprocess.check_output(['docker','image','inspect',a.tag]))[0]
        with (results/'agent-final-standalone-smoke.log').open('w') as log:
            subprocess.run(['docker','run','--rm','--pull=never','--network=none','--read-only',
                '--user',f'{os.getuid()}:{os.getgid()}','--cap-drop=ALL','--security-opt=no-new-privileges',
                '--workdir','/tmp','--env','HOME=/tmp','--memory=2g','--memory-swap=2g','--cpus=2',
                '--tmpfs','/tmp:rw,nosuid,nodev,size=128m','--entrypoint','/usr/bin/python3',
                info['Id'],'-c',SMOKE],stdout=log,stderr=subprocess.STDOUT,check=True)
        smoke = json.loads((results/'agent-final-standalone-smoke.log').read_text().splitlines()[-1])
        roles=json.loads((results/'mission-role-images.json').read_text())
        original_closure = results/('agent-closure-'+roles['agent']['manifest_sha256']+'.json')
        if not original_closure.is_file() or sha(original_closure) != roles['agent']['manifest_sha256']:
            raise ValueError('Original mission closure must remain available by its recorded hash')
        roles['mission_source_bind_agent']=dict(roles['agent'],manifest_path=str(original_closure),
                                               original_manifest_path=roles['agent']['manifest_path'])
        roles['agent']=dict(tag=a.tag,image_id=info['Id'],architecture=info['Architecture'],
            docker_size_bytes=info['Size'],manifest_path=str(manifest_path),manifest_sha256=sha(manifest_path),
            rootfs_layers=info['RootFS']['Layers'],standalone_smoke=smoke)
        (results/'final-role-images.json').write_text(json.dumps(roles,indent=2)+'\n')
        print(json.dumps(dict(image_id=info['Id'],sealed_capsules=len(smoke['sealed_capsules']),
            actual_facade_import=smoke['actual_facade_import'],roles=str(results/'final-role-images.json'))))


if __name__=='__main__':
    main()
