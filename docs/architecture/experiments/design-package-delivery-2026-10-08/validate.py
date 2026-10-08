"""Matched design delivery checks; not application tests or agent trials."""
from pathlib import Path
import json,hashlib,subprocess,sys
HERE=Path(__file__).resolve().parent
m=json.loads((HERE/'comparison.json').read_text(encoding='utf-8'))
roots={'full':Path(sys.argv[1]).resolve() if len(sys.argv)>1 else (HERE/m['full_root']).resolve(),'compact':Path(sys.argv[2]).resolve() if len(sys.argv)>2 else (HERE/m['compact_root']).resolve()}
for name,root in roots.items():
    actual={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    assert actual==m[name+'_files'], 'delivery byte drift: '+name
    assert sum(len((root/p).read_text(encoding='utf-8').split()) for p in m['explanatory_files'])==m['words'][name]
    assert sum(len((root/p).read_text(encoding='utf-8').split()) for p in ['README.md','m1-design.md','principles.md'])==m['immediate_words'][name]
    subprocess.run([sys.executable,str(root/'reference/validate.py')],check=True)
assert m['shared_files'] and len(m['shared_files'])==len(set(m['shared_files']))
for n in m['shared_files']:assert (roots['full']/n).read_bytes()==(roots['compact']/n).read_bytes(), n
assert round(100*(1-m['words']['compact']/m['words']['full']),2)==m['reduction_percent']
print('PASS matched delivery inventories, shared contracts/sources/decisions, reading counts and both portable validators')
print('LIMIT no paired agent outcomes or runtime acceptance')
