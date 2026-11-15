"""Portable source/evidence supplement; no models, credentials or live DB swept in."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

REPO=Path(__file__).resolve().parents[2]
VERIFY='''import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
expected=json.loads((root/'MANIFEST.json').read_text())
actual={}
for p in root.rglob('*'):
 if p.is_symlink():raise SystemExit('Unexpected symlink')
 if p.is_file() and p!=root/'MANIFEST.json':actual[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
if actual!=expected:raise SystemExit('Digest or file set mismatch')
print('Verified',len(actual),'files')
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    root=a.root.resolve();out=a.output.resolve();stage=out/'night-branches';stage.mkdir(parents=True,exist_ok=False)
    def copy(source,target):
        if source.is_symlink():raise ValueError('Unexpected symlink: '+str(source))
        target=stage/target;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    def tree(source,relative):
        for p in sorted(source.rglob('*')):
            if any(x in {'__pycache__','.pytest_cache','.git','node_modules','build','.codex'} for x in p.relative_to(source).parts) or p.suffix in {'.pyc','.lock','.sqlite','.db'} or p.name.endswith(('-wal','-shm')):continue
            if p.is_file():copy(p,Path(relative)/p.relative_to(source))
    for name in ['jiuwenswarm','tests/factory','docs/architecture/factory','docs/architecture/ccv2','deploy/spark']:
        tree(REPO/name,Path('source')/name)
    for name in ['AGENTS.md','LICENSE','pyproject.toml','scripts/factory_branch_mission.py','tools/benchmark_cc_workflow_lab.py','tools/profile_cc_workflow_lab.py','tools/qualify_evidence_digest.py']:
        if (REPO/name).is_file():copy(REPO/name,Path('source')/name)
    for name in ['night-branch-engine-v1','night-branch-engine-v2','runtime-native-artifacts-20261115','night-cc-qualification-001','cc-workflow-efficiency-002','cc-native-inventory-once-001','cc-native-inventory-once-002','night-long-prefill-v1','night-branch-analysis-v1','night-fewshot-quality-v1','night-prefill-qualification-001','night-gpu-cc-smoke-001','night-evidence-digest-qualification-001','night-evidence-digest-qualification-002','night-evidence-digest-qualification-003']:
        if (root/name).is_dir():tree(root/name,Path('evidence')/name)
    for name in ['benchmark-data/arc-v1/dataset.json','workload-shape-comparison-v1/dataset.json','assets/deepseek-full-identity-v1.json']:
        copy(root/name,Path('evidence/input-identities')/name)
    mission=root/'night-branch-jiuwen-v1'
    for name in ['manifest.json','task.json','launch.py','controller-result.json','evidence-snapshot.json','branches.json','pareto.json','console.log','native-receipts.json','native-call-summary.json','AGENT-REPORT.md','NEXT-INPUT-PROPOSAL.json']:
        if (mission/name).is_file():copy(mission/name,Path('evidence/jiuwen')/name)
    if (mission/'controller-attempts').is_dir():tree(mission/'controller-attempts','evidence/jiuwen/controller-attempts')
    for folder in ['runtime','factory/ccstore/releases','factory/ccstore/attempts','factory/sessions']:
        if (mission/folder).is_dir():tree(mission/folder,Path('evidence/jiuwen')/folder)
    workspace=mission/'factory/agent-workspace'
    if workspace.is_dir():
        for p in sorted(workspace.rglob('*')):
            relative=p.relative_to(workspace)
            if any(part.startswith('.') or part=='inputs' for part in relative.parts):continue
            if p.is_file() and p.suffix in {'.json','.md','.txt'} and p.stat().st_size<=4*1024**2:
                copy(p,Path('evidence/jiuwen/agent-reports')/relative)
    for p in sorted((root/'results').glob('night-*')):
        if p.is_file():copy(p,Path('evidence/verification')/p.name)
    for name in ['final-role-images.json','agent-final-standalone-smoke.log']:
        if (root/'results'/name).is_file():copy(root/'results'/name,Path('evidence/runtime')/name)
    (stage/'README.md').write_text('''# Night branching and methodologies supplement

Read source/docs/architecture/factory/NIGHT-BRANCH-METHODOLOGIES.md and NIGHT-BRANCH-RESULTS.md for exact evidence and limits. This is a compatible-checkout source overlay plus raw experimental evidence, not a new dependency environment. A separately exported immutable agent image supplies the exercised ARM64 environment. No model weights, credentials or live mission database are included. Native artifacts in evidence are explicitly ARM64; portable CCs contain source and require an explicit local build for native experiments. Never run the GPU tool without its gpu.use grant, bound device and exclusive lab slot.

Verify with `python3 verify.py`. Preserve earlier handoffs for full source/build ancestry and model identity. Requalify changed CC releases before admission; CPU checks, synthetic GPU timings, actual engine tests and agent exploration are different scopes. The factory metadata optimization is an optional source-pinned material component; core Host remains unchanged.

Cleanup is optional only after copying and verifying: remove owned exported archives or copied staging trees, then stop/remove only owned stopped lab resources. Retain raw results until RSI imports and checks them. Do not prune shared images/build caches, unrelated containers, source trees, user environments or model weights. No global dependency installation was made in this round.
''')
    (stage/'SOURCE-STATE.json').write_text(json.dumps(dict(git_head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),git_dirty_status=subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'],text=True),scope='Source overlay includes authored uncommitted files; MANIFEST pins actual exported bytes, git HEAD alone is insufficient'),indent=2)+'\n')
    (stage/'DATA-LICENSES.md').write_text('ARC-derived datasets: CC-BY-SA-4.0; AI2 Reasoning Challenge, Peter Clark et al., 2018; allenai/ai2_arc revision210d026faf9955653af8916fad021475a3f00453. Adaptations and exact source references are recorded in each dataset provenance. Long speed text is derived from the source-pinned Strata HOW_IT_WORKS.md under its recorded MIT license. No model weights are included.\n')
    (stage/'verify.py').write_text(VERIFY)
    manifest={str(p.relative_to(stage)):sha(p) for p in sorted(stage.rglob('*')) if p.is_file() and p!=stage/'MANIFEST.json'}
    (stage/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');subprocess.run([sys.executable,str(stage/'verify.py')],check=True)
    archive=out/'night-branches.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:tar.add(stage,arcname=stage.name)
    (out/(archive.name+'.sha256')).write_text(sha(archive)+'  '+archive.name+'\n')
    print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(manifest))))
if __name__=='__main__':main()
