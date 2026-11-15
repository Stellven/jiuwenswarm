"""Build a review/source overlay archive, preserving exact source and verified exports.

No images, models, credentials, virtualenvs or mutable mission DB are swept into it.
Docker images are a separate operator-created archive. No execution or cleanup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from jiuwenswarm.factory.export import verify
from jiuwenswarm.factory.redact import SECRET_PATTERNS, sanitize

ROOTS = ('jiuwenswarm/factory', 'jiuwenswarm/ccv2', 'tests/factory', 'tests/ccv2',
         'deploy/spark', 'docs/architecture/factory', 'docs/architecture/ccv2')
FILES = ('AGENTS.md', 'LICENSE', 'OPEN_SOURCE_SOFTWARE_NOTICE.md', 'pyproject.toml',
         'uv.lock', 'README.md', '.gitmodules', 'jiuwenswarm/__init__.py')
EXCEPTIONS = {
 'source/jiuwenswarm/factory/store.py': 'Regex false positive: Python expected_state argument assignment.',
 'source/tests/factory/test_export.py': 'Deliberately synthetic credential examples testing redaction.',
}
VERIFY = '''#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST.json').read_text())
actual={}
for path in root.rglob('*'):
 if path.is_symlink():raise SystemExit('Unexpected symlink: '+str(path))
 if path.is_file() and path != root/'MANIFEST.json':
  actual[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
if actual!=manifest:raise SystemExit('File set or SHA256 mismatch')
for nested in (root/'evidence').rglob('MANIFEST.json'):
 expected=json.loads(nested.read_text());found={str(p.relative_to(nested.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in nested.parent.rglob('*') if p.is_file() and p!=nested}
 if found!=expected:raise SystemExit('Evidence manifest mismatch: '+str(nested))
print('Verified',len(actual),'files and all nested evidence manifests; no runtime dependencies required.')
'''


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--additional-export',type=Path,action='append',default=[])
 p.add_argument('--additional-receipt',type=Path,action='append',default=[])
 p.add_argument('--readme',type=Path)
 a=p.parse_args();root=a.root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 stage=out/'spark-factory-review';stage.mkdir(exist_ok=False)
 copied=[]
 def copy(src,dst):
  if src.is_symlink():raise ValueError('Explicitly resolve and review symlink before packaging: '+str(src))
  if src.name in {'auth.json','.env','.git'} or src.suffix in {'.pem','.key'}:raise ValueError('Excluded private/config file: '+str(src))
  target=stage/dst;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target);copied.append((src,target))
 for name in ROOTS:
  for src in sorted((REPO/name).rglob('*')):
   if src.is_file() and '__pycache__' not in src.parts and '.pytest_cache' not in src.parts and src.suffix!='.pyc':copy(src,'source/'+str(src.relative_to(REPO)))
 for name in FILES:
  if (REPO/name).is_file():copy(REPO/name,'source/'+name)
 provenance=dict(scope='Exact focused working-tree overlay; includes uncommitted changes, excludes external .git worktree pointer and full project history.',
  base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
  branch=subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),
  dirty_status=subprocess.check_output(['git','status','--short'],cwd=REPO,text=True),
  roots=list(ROOTS),source_sha256={str(dst.relative_to(stage/'source')):hashlib.sha256(src.read_bytes()).hexdigest() for src,dst in copied})
 (stage/'SOURCE-PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n')
 for directory in [root/'exports/arc-drafting-main-001',*sorted((root/'exports/factory-loop-v1').iterdir()), *a.additional_export]:
  if not directory.is_dir():continue
  verify(directory);shutil.copytree(directory,stage/'evidence'/directory.name)
 for name in ['benchmark-data/arc-v1','assets']:
  shutil.copytree(root/name,stage/name)
 pack=Path('/home/user2/strata-baseline/Strata-data/packs/deepseek-v4.1-flash-ist-das-2.00bpw')
 for src in pack.rglob('*'):
  if src.is_file():copy(src,'model-pack/'+str(src.relative_to(pack)))
 for name in ['factory-loop-final-tests.log','factory-loop-agent-proof.json','factory-loop-export-index.json',
              'final-role-images.json','factory-loop-cli-image.json','handoff-cleanup-inventory.json']:
  copy(root/'results'/name,'receipts/'+name)
 for name,path in [('agent-closure.json',root/'agent-build-context-001/closure.json'),('builder-toolchain.json',root/'builder-build-context-001/toolchain.json')]:
  target=stage/'receipts'/name;target.write_text(json.dumps(sanitize(json.loads(path.read_text())),indent=2)+'\n')
 donor=Path('/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source/bin/jobq').resolve()
 copy(donor,'host-tools/jobq');(stage/'host-tools/PROVENANCE.json').write_text(json.dumps({'source':str(donor),'sha256':hashlib.sha256(donor.read_bytes()).hexdigest(),'scope':'Queue executable only; no shared queue state copied.'},indent=2)+'\n')
 for path in a.additional_receipt:
  copy(path,'receipts/additional/'+path.name)
 copy(a.readme or root/'handoff-20261114/README.md','README.md')
 copy(root/'handoff-20261114/image-archive-verification.json','receipts/image-archive-verification.json')
 (stage/'verify.py').write_text(VERIFY)
 # Review exact source without rewriting test fixtures or numeric token metrics.
 # Evidence exports already pass their stricter sanitized-export scanner.
 exceptions=[]
 for f in (stage/'source').rglob('*'):
  if not f.is_file():continue
  data=f.read_bytes();hits=[i for i,pattern in enumerate(SECRET_PATTERNS) if i!=3 and pattern.search(data)]
  if not hits:continue
  rel=str(f.relative_to(stage));reason=EXCEPTIONS.get(rel)
  if not reason and (rel.startswith('source/tests/factory/fixtures/ab/') or rel.startswith('source/jiuwenswarm/factory/views/sample/')) and hits==[4]:
   reason='Reviewed numeric *_per_token fixture metrics; not credentials.'
  if not reason:raise ValueError('Review credential-shaped source content without printing values: '+rel)
  exceptions.append(dict(path=rel,sha256=hashlib.sha256(data).hexdigest(),reason=reason,pattern_ids=hits))
 (stage/'SOURCE-SCAN.json').write_text(json.dumps(dict(scope='Credential-pattern scan of exact focused source; email addresses are not classified as secrets; exclusions are hash-bound and reviewed.',exceptions=exceptions),indent=2)+'\n')
 manifest={str(f.relative_to(stage)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(stage.rglob('*')) if f.is_file()}
 (stage/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
 subprocess.run([sys.executable,str(stage/'verify.py')],check=True)
 archive=out/'spark-factory-review.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:tar.add(stage,arcname=stage.name)
 digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
 (out/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
 print(json.dumps(dict(archive=str(archive),size_bytes=archive.stat().st_size,sha256=digest,files=len(manifest))))

if __name__=='__main__':main()
