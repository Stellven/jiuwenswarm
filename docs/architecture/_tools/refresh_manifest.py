"""Refresh package identities/projections from a specified checkout; never runtime evidence."""
from pathlib import Path
import argparse,hashlib,json,re,os

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,t):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8',newline='\n')
def record(p,root):return {'path':p.relative_to(root).as_posix(),'sha256':digest(p),'bytes':p.stat().st_size}
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',required=True,type=Path);args=parser.parse_args()
 root=Path(__file__).resolve().parents[1];repo=args.repo.resolve();inputs=json.loads((root/'_tools/snapshot-inputs.json').read_text(encoding='utf-8'))
 docs=sorted(p for p in root.rglob('*.md') if not set(p.relative_to(root).parts)&{'sources','old','.obsidian','__pycache__'})
 architecture=[{'path':p.relative_to(root).as_posix(),'sha256':digest(p)} for p in docs]
 aggregate=hashlib.sha256(json.dumps(architecture,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 baseline={'revision':'r2026-10-06.5','purpose':'Current high-level design identity; snapshots and native evidence remain separately labelled.','aggregate_method':'SHA256 of UTF-8 canonical JSON architecture [{path,sha256}] sorted by path, keys sorted, separators comma/colon; exact bytes per file.','architecture_aggregate_sha256':aggregate,'architecture':architecture,'runtime_validation':'NOT_RUN'}
 write(root/'source-baseline.json',json.dumps(baseline,indent=2)+'\n')
 origins={'docs/code/Missions/M1/TASKS.md':root/'sources/live-program/TASKS.md','docs/code/Missions/M1/TRIAL-1/TASK.md':root/'sources/live-program/TRIAL-1/TASK.md'}
 for origin in origins:
  p=repo/origin;t=p.read_text(encoding='utf-8')
  t=re.sub(r'aggregate SHA256 `[^`]+`','aggregate SHA256 `'+aggregate+'`',t,flags=re.I)
  t=t.replace('r2026-10-06.4','r2026-10-06.5')
  write(p,t)
 projections=[]
 for origin,dest in origins.items():
  source=repo/origin;t=source.read_text(encoding='utf-8')
  def rebase(match):
   target=match.group(2);path,separator,fragment=target.partition('#')
   if '://' in target or not path:return match.group(0)
   from urllib.parse import unquote
   live=(source.parent/unquote(path)).resolve()
   key=live.relative_to(repo).as_posix() if live.is_relative_to(repo) else None
   projected=origins.get(key)
   if projected is None:
    if live.is_relative_to(root):projected=live
    else:projected=root/'sources/main-baseline'/key if key else None
   if projected is None or (not projected.exists() and projected not in origins.values()):raise ValueError('Unpackaged live target: '+target+' in '+origin)
   link=Path(os.path.relpath(projected,dest.parent)).as_posix().replace(' ','%20')+(separator+fragment if separator else '')
   return match.group(1)+link+')'
  t=re.sub(r'(\[[^\]]*\]\()([^\n]+?)\)',rebase,t)
  write(dest,'<!-- Read-only live projection. Edit the canonical checkout record, then refresh. -->\n'+t)
  projections.append({**record(dest,root),'origin':origin,'source_sha256':digest(source)})
 files=[record(p,root) for p in sorted(root.rglob('*')) if p.is_file() and not set(p.relative_to(root).parts)&{'old','.obsidian','__pycache__','.git','.cache','cache'} and p.resolve()!=(root/'package-manifest.json').resolve()]
 snapshots=inputs['snapshots']
 authorities=[{'path':p} for p in origins]+[{'path':p} for p in ['docs/code/Code_SOP.md','docs/code/SPEC_KIT_WORKFLOW.md','docs/code/VERIFICATION.md','.specify/memory/constitution.md','plugins/spec-kit/README.md']]
 manifest={'revision':'r2026-10-06.5','scope':'Complete active design reading set and locally navigable read-only context; old/ is historical, unchanged and excluded.','current_prd':{**record(root/'sources/product/prd-m1-current-2026-10-06.txt',root),'origin':'User-supplied attachment 7ee1c393-9903-425b-92e8-a22eae56c50e, received 2026-10-06; author date not inferred'},'target_main':inputs['target_main'],'snapshots':snapshots,'live_projections':projections,'live_authorities':authorities,'source_baseline':{**record(root/'source-baseline.json',root),'architecture_aggregate_sha256':aggregate},'validation':{'standalone':'_tools/check_package.py','checkout':'_tools/check_package.py --repo CHECKOUT','runtime_validation':'NOT_RUN'},'files':files}
 write(root/'package-manifest.json',json.dumps(manifest,indent=2)+'\n')
 print(json.dumps({'files':len(files),'snapshots':len(snapshots),'projections':len(projections),'architecture_aggregate_sha256':aggregate}))
if __name__=='__main__':main()
