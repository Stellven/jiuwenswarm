"""Explicit immutable verifier release for protected host dependency gate support."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write',action='store_true')
    args=p.parse_args()
    from jiuwenswarm.research.state import json_bytes
    from jiuwenswarm.research.contracts import validate
    package=ROOT/'jiuwenswarm'
    assets=package/'research_assets'
    catalog_path=assets/'catalog.json'
    catalog=json.loads(catalog_path.read_bytes())
    declaration=json.loads((assets/'compiler/verifier.declaration.json').read_bytes())
    body=[dict(path=name,sha256=hashlib.sha256((package/name).read_bytes()).hexdigest())
          for name in ('research/gate.py','research_assets/compiler/verifier.txt')]
    declaration['identity'].update(version_label='m1-3-host-dependency',body=body,
        carrier={'ref':body[0]['path'],'sha256':body[0]['sha256']})
    paths=('research/checks/verifier.py','research/gate.py')
    closure={'implementation':'research/checks/verifier.py','files':{
        path:{'id':'blob:'+(digest:=hashlib.sha256((package/path).read_bytes()).hexdigest()),'sha256':digest}
        for path in paths}}
    runner_digest=hashlib.sha256(json_bytes(closure)).hexdigest()
    for check in declaration['guarantees']['checks']:
        check['runner']={'ref':'protected_verifier_checks','sha256':runner_digest}
    validate('capsule-declaration',declaration)
    raw=json_bytes(declaration)
    path=assets/'compiler/verifier-host-dependency-v1.declaration.json'
    catalog['capsules']['verifier'].update(declaration_path='compiler/verifier-host-dependency-v1.declaration.json',
        declaration_sha256=hashlib.sha256(raw).hexdigest(),body=body)
    if args.write:
        history=assets/'compiler/history/pre-host-dependency-v1'
        history.mkdir(parents=True,exist_ok=True)
        if not (history/'catalog.json').exists(): (history/'catalog.json').write_bytes(catalog_path.read_bytes())
        if path.exists() and path.read_bytes()!=raw:raise SystemExit('Refusing to rewrite immutable verifier release')
        path.write_bytes(raw)
        catalog_path.write_text(json.dumps(catalog,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    elif not path.exists() or path.read_bytes()!=raw or catalog!=json.loads(catalog_path.read_bytes()):
        raise SystemExit('Verifier host dependency release differs from installed pins')
    print('Verifier m1-3-host-dependency '+hashlib.sha256(raw).hexdigest()+'; checker '+runner_digest)

if __name__=='__main__':main()
