from pathlib import Path
import subprocess,json,shutil,hashlib,gzip,re,os
P=Path('/home/muk/backup/20261113 Satay CC Demo and Recovery prepresentation')
J=Path('/home/muk/projects/jiuwenswarm')
def cp(src,dst):
    dst=P/dst; dst.parent.mkdir(parents=True,exist_ok=True)
    if Path(src).is_dir():shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    else:shutil.copy2(src,dst)
cp('/home/muk/tools/TRANSFER/satay-recovery','context/recovery')
for name in ['ONTOLOGY.yaml','STREAMING.md','cc.yaml']:
    cp(J/'jiuwenswarm/factory/ccs/expert_streaming'/name,'context/expert_streaming/'+name)
cp(J/'docs/architecture/factory/NODE-EXAMPLE.md','context/NODE-EXAMPLE.md')
for name in ['p1.txt','p0-short.txt']:
    cp(Path('/home/muk/models/campaign/qwen36-35b-a3b/prompts')/name,'contracts/prompts/'+name)
for name in ['verify.py','restore-sources.py']:
    compile((P/'scripts'/name).read_text(),name,'exec')
subprocess.run(['bash','-n',str(P/'scripts/start-codex.sh')],check=True)
patterns=[re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC) PRIVATE KEY-----'),re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}'),re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'Bearer\s+[A-Za-z0-9_.-]{25,}',re.I)]
hits=[]
for f in P.rglob('*'):
    if not f.is_file() or f.suffix in ['.bundle','.mp4','.png','.jpg']:continue
    data=gzip.decompress(f.read_bytes()) if f.suffix=='.gz' else f.read_bytes()
    if any(p.search(data) for p in patterns):hits.append(str(f.relative_to(P)))
(P/'SECRET-SCAN.json').write_text(json.dumps({'scope':'Selected package text and decompressed gzip evidence. Git history not exhaustively scanned. Authentication directories and live DB excluded.','pattern_hits_files':hits},indent=2))
if hits:raise SystemExit('Potential credential patterns; inspect filenames in SECRET-SCAN.json without echoing contents')
print('Context refresh, syntax checks and selected-evidence secret scan passed',flush=True)
