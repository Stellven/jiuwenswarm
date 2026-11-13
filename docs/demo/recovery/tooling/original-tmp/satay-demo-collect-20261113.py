from pathlib import Path
import subprocess, json, shutil, hashlib, re

ROOT=Path('/home/muk/backup/20261113 Satay CC Demo and Recovery prepresentation')
ROOT.mkdir(parents=True,exist_ok=True)
J=Path('/home/muk/projects/jiuwenswarm'); S=Path('/home/muk/projects/siminfeng')
def cp(src,dest):
    src=Path(src); dst=ROOT/dest; dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir(): shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    else: shutil.copy2(src,dst)
cp(J/'artifacts/factory/demo-incremental','evidence/incremental')
cp(S/'experiments/jetson/OM/J-OM13','evidence/J-OM13')
cp(J/'artifacts/factory/evidence/factory-bd173c082bf34ae3b8471938c19b8068','evidence/factory-run4')
for name in ['qwen36-quick-v1.json','qwen36-bare-greedy-v1.json']:
    cp(J/'jiuwenswarm/factory/contracts'/name,'contracts/'+name)
for name in ['engine-diagram.svg','SESSION-HANDOFF-20261113.md','WORKLOG.md']:
    cp(J/'docs/demo'/name,'context/historical/'+name)
for name in ['STREAMING.md','SOURCE-MAP.md','ONTOLOGY.yaml','EVIDENCE.md']:
    cp(J/'jiuwenswarm/factory/ccs/expert_streaming'/name,'context/expert_streaming/'+name)
for name in ['builder','lab_client','methodology_ab','expert_streaming']:
    cp(J/'jiuwenswarm/factory/ccs'/name/'cc.yaml','context/capsules/'+name+'.yaml')
for ident in ['232a349573c8400c92efb7b39b8e1793','c5c456f087344f539ec524ee29813912','29901f7e34c2487cb9c64f512635696e']:
    cp(Path('/home/muk/.jiuwenswarm-factory/lab-spool')/ident,'evidence/incremental-lab/'+ident)
prompt=Path('/home/muk/projects/siminfeng/cc/om_run/prompts')
for name in ['p1.txt','p0-short.txt']:
    if (prompt/name).exists(): cp(prompt/name,'contracts/prompts/'+name)
print(json.dumps({'package':str(ROOT),'files':sum(1 for p in ROOT.rglob('*') if p.is_file())}))
