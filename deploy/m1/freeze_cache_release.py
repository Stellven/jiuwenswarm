"""Author/verify the new cache-capable scientific release; never admits or activates it."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from contextlib import closing
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    from jiuwenswarm.research.capsules.assets import build_research_assets,build_pi_benchmark_asset
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.state import SQLiteRunStore,json_bytes
    path=ROOT/'jiuwenswarm/research/resources/capsules/capsule_catalog.json'
    prior=json.loads(path.read_bytes())
    history=path.parent/'history/pre-cache-v1/capsule_catalog.json'
    with tempfile.TemporaryDirectory() as directory,closing(SQLiteRunStore(directory)) as store:
        stages=json.loads(json_bytes(build_research_assets(store,verify_catalog=False)))
        pi=json.loads(json_bytes(build_pi_benchmark_asset(store,base=stages['benchmark'],verify_catalog=False)))
    old=json.loads(history.read_bytes()) if history.exists() else prior
    for stage in ('search','screening','evaluation'):
        if stages[stage]!=old['stages'][stage]:
            raise SystemExit('Unrelated stage changed: '+stage)
    value=dict(prior,stages=stages,protocols={'pi':{'benchmark':pi}})
    core_path=ROOT/'jiuwenswarm/research_assets/catalog.json'
    core=json.loads(core_path.read_bytes())
    root=core_path.parent
    template=json.loads((root/'planner/static-template.json').read_bytes())
    template.update(id='static_template_m1_cache_study_v6',template_name='m1_cache_study_v6')
    for node in template['nodes']:
        stage=node['node_id']
        if stage in stages:
            from jiuwenswarm.research.capsules.assets import STAGE_VERSIONS
            node['cc'].update(cc_version=STAGE_VERSIONS[stage],declaration_sha256=stages[stage]['declaration_ref']['sha256'])
    validate('static-template',template)
    raw=json_bytes(template)
    template_path=root/'planner/static-template-cache-v6.json'
    core['static_template'].update(path='planner/static-template-cache-v6.json',sha256=hashlib.sha256(raw).hexdigest(),
        meaning='Registered cache study with genuine scoped Builder implementation, original stdout and independent request-count scoring; original typed graph and gates retained.')
    if args.write:
        if not history.exists():
            history.parent.mkdir(parents=True,exist_ok=True)
            history.write_bytes(path.read_bytes())
        core_history=history.parent/'research-assets-catalog.json'
        if not core_history.exists():core_history.write_bytes(core_path.read_bytes())
        if template_path.exists() and template_path.read_bytes()!=raw:
            raise SystemExit('Refusing to rewrite an existing cache static-template release')
        path.write_bytes(json_bytes(value))
        template_path.write_bytes(raw)
        core_path.write_text(json.dumps(core,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    elif value!=prior or not template_path.exists() or template_path.read_bytes()!=raw or core!=json.loads(core_path.read_bytes()):
        raise SystemExit('Cache release pins differ from installed bytes')
    print('Cache capsule/check/static-template pins '+('authored; no admission or activation' if args.write else 'verified'))

if __name__=='__main__':main()
