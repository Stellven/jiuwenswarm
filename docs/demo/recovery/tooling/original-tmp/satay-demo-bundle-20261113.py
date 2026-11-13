from pathlib import Path
import subprocess,json,shutil,tempfile,os
P=Path('/home/muk/backup/20261113 Satay CC Demo and Recovery prepresentation')
(P/'sources').mkdir(exist_ok=True)
repos={'jiuwenswarm':Path('/home/muk/projects/jiuwenswarm'),'siminfeng':Path('/home/muk/projects/siminfeng'),'tools':Path('/home/muk/tools'),'llama-engine':Path('/home/muk/.jiuwenswarm-factory/agent-workspace/llama.cpp')}
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
engine=repos['llama-engine']
for name,rev in [('plain','cf34d311332e362198f0a410c466d1e940287d02'),('fill','00c6038f15e5'),('headline','0b514fba8')]:
    git(engine,'update-ref','refs/heads/recovery/'+name+'-20261113',git(engine,'rev-parse',rev))
pins=json.loads((P/'SOURCE-PINS.json').read_text()) if (P/'SOURCE-PINS.json').exists() else {}
for name,repo in repos.items():
    head=git(repo,'rev-parse','HEAD'); branch=git(repo,'symbolic-ref','--short','HEAD')
    if name in pins and pins[name]['commit']==head:
        print('Unchanged snapshot',name,flush=True);continue
    refs=['refs/heads/'+branch]
    if name=='jiuwenswarm':refs+=['refs/tags/cc-rsi-v1','refs/tags/cc-demo-incremental-v1']
    if name=='llama-engine':refs+=['refs/heads/recovery/'+n+'-20261113' for n in ['plain','fill','headline']]
    dest=P/'sources'/f'{name}.bundle'
    print('Bundling',name,head,flush=True)
    snap=Path(tempfile.mkdtemp(prefix='satay-source-snapshot-'))
    git(snap,'init')
    for ref in refs:
        git(snap,'fetch','--depth=1','--no-tags','file://'+str(repo),ref+':'+ref)
    git(snap,'-c','pack.threads=1','bundle','create',str(dest),'--all')
    boundary=dest.with_suffix('.shallow'); shutil.copy2(snap/'.git/shallow',boundary)
    git(snap,'bundle','verify',str(dest))
    pins[name]={'commit':head,'branch':branch,'remote':git(repo,'remote','get-url','origin'),'bundle':str(dest.relative_to(P)),'shallow':str(boundary.relative_to(P)),'history':'Exact pinned source snapshots; parents outside pins are intentionally omitted. Restore boundary before unbundling.','refs':{r:git(repo,'rev-parse',r) for r in refs},'working_tree_status':git(repo,'status','--short')}
    print('Bytes',dest.stat().st_size,flush=True)
(P/'SOURCE-PINS.json').write_text(json.dumps(pins,indent=2)+'\n')
print('DONE',flush=True)
