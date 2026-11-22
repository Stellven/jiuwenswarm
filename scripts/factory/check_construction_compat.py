import importlib.util,json,sys
from pathlib import Path
import yaml,jsonschema
from jiuwenswarm.ccv2.ccv2 import Host
import argparse
parser=argparse.ArgumentParser(description='Validate canonical factory CCs using the pinned upstream source checkout')
parser.add_argument('upstream_protocol_root',type=Path)
root=parser.parse_args().upstream_protocol_root
sys.path.insert(0,str(root/'reference'))
spec=importlib.util.spec_from_file_location('upstream_ccv2',root/'reference/ccv2.py');up=importlib.util.module_from_spec(spec);sys.modules[spec.name]=up;spec.loader.exec_module(up)
ccs=Path('jiuwenswarm/factory/ccs');schema=json.loads((root/'schemas/cc.schema.json').read_text())
paths=list(ccs.rglob('cc.yaml'))
for p in paths:jsonschema.validate(yaml.safe_load(p.read_text()),schema)
results=[]
for name,cls in [('factory',Host),('upstream',up.Host)]:
    host=cls(Path('artifacts/construction-verification')/name,session_grants=['process.exec'])
    release=host.prepare(ccs/'performance_baseline')
    if isinstance(release,dict):release=release['release']
    receipt=host.call(release,'replay',dict(trace=[[0],[1],[0]],page_bytes=4,capacity_bytes=4,storage_bytes_per_s=4,compute_seconds=[0,0,0]))
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['result']['page_reads']==3
    results.append(dict(runner=name,release=release,receipt=receipt))
result=dict(upstream_commit='b74121c712ee5378b70ad54c4997cd81563685e7',declarations_validated=len(paths),cross_runner=results)
Path('artifacts/construction-verification/compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
print('Schema:',len(paths),'Mixed-package cross-runner results:',[(r['runner'],r['receipt']['state']) for r in results])
