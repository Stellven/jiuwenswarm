"""Stage/verify broad campaign evidence after all labs stop. Dry plan by default.

No image build/save, model copy, shared pruning or deletion. Run --execute only
when the operator has declared all measurements complete. Fails on active jobs.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from contextlib import closing

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from jiuwenswarm.factory.export import export_task, snapshot, verify
from jiuwenswarm.factory.redact import SECRET_PATTERNS, sanitize, scrub_bytes

PARENTS=('spark-broad-throughput-004','spark-broad-throughput-006',
         'spark-fixed-placement-aa-001','spark-fixed-placement-build-001')
TERMINAL={'succeeded','failed','cancelled'}
RECEIPT_GLOBS=('broad-*','fixed-placement-*','fixed-screen-*','throughput-workbench-tests.log',
               'final-role-images.json','mission-role-images.json','agent-final-*')


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def plan(root,extra):
    home=root/'mission-store'
    with closing(sqlite3.connect((home/'factory.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        names={r[0] for r in db.execute('SELECT task_id FROM tasks')}
        active=[dict(zip(('task_id','attempt_id','kind','state'),r)) for r in db.execute(
            "SELECT task_id,attempt_id,kind,state FROM attempts WHERE state NOT IN ('succeeded','failed','cancelled')")]
    selected=set(PARENTS)|set(extra)|{n for n in names if n.startswith('spark-fixed-placement-screens-')}
    missing=selected-names
    if missing:raise ValueError('Required task missing: '+','.join(sorted(missing)))
    pending=list(selected)
    while pending:
        task=pending.pop()
        records=snapshot(home,task)
        for row in records.get('factory_loop_cycles',[]):
            child=row['record'].get('child_task_id')
            if child and child not in selected:
                selected.add(child);pending.append(child)
    return dict(tasks=sorted(selected),active_attempts=active,
        future_task_prefix='spark-fixed-placement-screens-',bulk_work_performed=False,
        next_action='Refresh standalone agent in a quiet interval, then --execute only after all labs complete.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--task',action='append',default=[])
    parser.add_argument('--receipt',type=Path,action='append',default=[])
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();root=args.root.resolve();p=plan(root,args.task)
    if not args.execute:
        print(json.dumps(p,indent=2));return
    if p['active_attempts']:raise ValueError('All lab/build attempts must be terminal before packaging')
    if args.output is None:raise ValueError('--output requires a new owned directory')
    out=args.output.resolve()
    if not out.is_relative_to(root) or out==root:raise ValueError('Use a new task-owned output beneath root')
    out.mkdir(parents=True,exist_ok=False)
    stage=out/'spark-broad-campaign';stage.mkdir()
    # Reuse the portable verification format and reviewed source-scan exceptions.
    spec=importlib.util.spec_from_file_location('handoff_support',REPO/'deploy/spark/package-handoff.py')
    support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
    exports=[]
    for task in p['tasks']:
        destination=stage/'evidence'/task
        export_task(task,destination,home=root/'mission-store');count=verify(destination)
        exports.append(dict(task_id=task,path=str(destination.relative_to(stage)),files=count))
    for relative in support.ROOTS:
        for src in sorted((REPO/relative).rglob('*')):
            if src.is_symlink():raise ValueError('Unexpected source symlink')
            if src.is_file() and not {'__pycache__','.pytest_cache'}.intersection(src.parts) and src.suffix!='.pyc':
                dst=stage/'source'/src.relative_to(REPO);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    for relative in support.FILES:
        src=REPO/relative
        if src.is_file():
            dst=stage/'source'/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    receipts=[];omitted=[]
    candidates=set(args.receipt)
    for pattern in RECEIPT_GLOBS:candidates.update((root/'results').glob(pattern))
    prior=root/'results/prior-agent-refresh'
    if prior.is_dir():candidates.update(prior.iterdir())
    for src in sorted(candidates):
        if not src.is_file() or src.is_symlink():continue
        if src.stat().st_size>50*2**20:
            omitted.append(dict(path=str(src),size=src.stat().st_size,reason='receipt over50MiB'));continue
        dst=stage/'receipts'/src.name;dst.parent.mkdir(exist_ok=True)
        raw=src.read_bytes()
        try:data=(json.dumps(sanitize(json.loads(raw)),indent=2)+'\n').encode()
        except (ValueError,UnicodeDecodeError):data=scrub_bytes(raw)
        dst.write_bytes(data);receipts.append(dict(name=src.name,original_sha256=digest(src),exported_sha256=digest(dst)))
    exceptions=[]
    for f in (stage/'source').rglob('*'):
        if not f.is_file():continue
        hits=[i for i,pattern in enumerate(SECRET_PATTERNS) if i!=3 and pattern.search(f.read_bytes())]
        if not hits:continue
        rel=str(f.relative_to(stage));reason=support.EXCEPTIONS.get(rel)
        if not reason and (rel.startswith('source/tests/factory/fixtures/ab/') or rel.startswith('source/jiuwenswarm/factory/views/sample/')) and hits==[4]:
            reason='Reviewed numeric fixture metrics; not credentials.'
        if not reason:raise ValueError('Review credential-shaped source content without printing values: '+rel)
        exceptions.append(dict(path=rel,sha256=digest(f),reason=reason,pattern_ids=hits))
    for f in (stage/'receipts').iterdir():
        if any(pattern.search(f.read_bytes()) for pattern in SECRET_PATTERNS):raise ValueError('Receipt secrets scan failed: '+f.name)
    shutil.copy2(REPO/'deploy/spark/BROAD-CAMPAIGN-HANDOFF.md',stage/'README.md')
    (stage/'verify.py').write_text(support.VERIFY)
    (stage/'SOURCE-SCAN.json').write_text(json.dumps(dict(exceptions=exceptions),indent=2)+'\n')
    (stage/'EXPORT-INDEX.json').write_text(json.dumps(dict(exports=exports,receipts=receipts,omissions=omitted),indent=2)+'\n')
    inventory=dict(scope='Inventory only; no deletions, image pruning or shared queue cleanup.',
        owned_candidates=['projects/fixed-placement','fixed-placement-preparation-ccstore',
            'broad-campaign-v1','broad-diagnostic-v1','fixed-placement-campaign-v1','fixed-screen-campaign-v1','fixed-screen-final-v1'],
        retained_images='See immutable final-role-images and fixed-placement-build-result receipts; no docker save or prune performed.',
        exclusions=['model weights','private environments','credentials','mutable mission database','shared queue/runtime caches'])
    (stage/'CLEANUP-INVENTORY.json').write_text(json.dumps(inventory,indent=2)+'\n')
    manifest={str(f.relative_to(stage)):digest(f) for f in sorted(stage.rglob('*')) if f.is_file()}
    (stage/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    subprocess.run([sys.executable,str(stage/'verify.py')],check=True)
    archive=out/'spark-broad-campaign.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:tar.add(stage,arcname=stage.name)
    (out/(archive.name+'.sha256')).write_text(digest(archive)+'  '+archive.name+'\n')
    print(json.dumps(dict(archive=str(archive),sha256=digest(archive),exported_tasks=p['tasks'],files=len(manifest))))


if __name__=='__main__':main()
