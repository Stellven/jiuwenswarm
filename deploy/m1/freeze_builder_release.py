"""Explicit Builder-upgrade authoring; never run by product startup."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Author Builder m1-18 and its schema-routed Benchmark receipt consumer')
    args = parser.parse_args()
    from jiuwenswarm.research.capsules.assets import build_research_assets, build_pi_benchmark_asset
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
    path = ROOT / 'jiuwenswarm/research/resources/capsules/capsule_catalog.json'
    prior = json.loads(path.read_text('utf-8'))
    with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(directory)) as store:
        stages = json.loads(json_bytes(build_research_assets(store, verify_catalog=False)))
        pi = json.loads(json_bytes(build_pi_benchmark_asset(store, base=stages['benchmark'], verify_catalog=False)))
    for stage in stages:
        if stage not in {'builder', 'benchmark'} and stages[stage] != prior['stages'][stage]:
            raise SystemExit('Refusing unrelated scientific release change: ' + stage)
    if args.write:
        prior['stages'] = stages
        prior['protocols'] = {'pi': {'benchmark': pi}}
        path.write_bytes(json_bytes(prior))
    elif stages != prior['stages'] or prior.get('protocols') != {'pi': {'benchmark': pi}}:
        raise SystemExit('Builder/Benchmark release bytes differ from committed pins')
    print('Builder and Benchmark release pins ' + ('authored; no admission/activation performed' if args.write else 'verified'))
    core_path = ROOT / 'jiuwenswarm/research_assets/catalog.json'
    core = json.loads(core_path.read_text('utf-8'))
    template_path = ROOT / 'jiuwenswarm/research_assets' / core['static_template']['path']
    template = json.loads(template_path.read_text('utf-8'))
    template.update(id='static_template_m1_builder_development_v1', template_name='m1_blind_builder_development_v1')
    for node in template['nodes']:
        stage = node['node_id']
        if stage in {'builder', 'benchmark'}:
            node['cc'].update(cc_version='m1-18' if stage == 'builder' else 'm1-10-agent-pi',
                              declaration_sha256=stages[stage]['declaration_ref']['sha256'])
            if stage == 'builder':
                node['objective'] = 'Build and test the frozen intervention through bounded native development actions'
                node['limits']['model_calls'] = 22  # bounded Builder actions plus both independent output reviews
    validate('static-template', template)
    raw = json_bytes(template)
    if args.write:
        template_path.write_bytes(raw)
        core['static_template'].update(sha256=hashlib.sha256(raw).hexdigest(),
            meaning='Bounded native Builder actions and protected compile/unit/smoke checks; independent reviews, gates and schema-routed Benchmark retained.')
        core_path.write_text(json.dumps(core, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    elif template_path.read_bytes() != raw or core['static_template']['sha256'] != hashlib.sha256(raw).hexdigest():
        raise SystemExit('Static Builder/Benchmark pins or development allowance differ')


if __name__ == '__main__':
    main()
