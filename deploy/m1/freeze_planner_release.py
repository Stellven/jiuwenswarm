"""Explicit authoring tool for the core Planner and its affected PDF checker.

Never called by startup. Other compiler/scientific/PDF work releases stay pinned.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from contextlib import closing

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def derived(version):
    package = ROOT / 'jiuwenswarm'
    catalog_path = package / 'research_assets/catalog.json'
    catalog = json.loads(catalog_path.read_text('utf-8'))
    declaration_path = package / 'research_assets' / catalog['capsules']['planner']['declaration_path']
    declaration = json.loads(declaration_path.read_text('utf-8'))
    paths = ['research/capsules/planner.py', 'research_assets/planner/planner.txt',
             'research/capsules/_common.py', 'research/unified_planning.py',
             'research/capability_planning.py', 'research/summary_planning.py', 'research/planner_catalog.py']
    bodies = [{'path': name, 'sha256': hashlib.sha256((package / name).read_bytes()).hexdigest()} for name in paths]
    identity = declaration['identity']
    identity.update(version_label=version,
        summary='Bounded native typed DAG synthesis with one validation-guided correction from accepted Brief, admitted library, resources and protected policy',
        carrier={'ref': paths[0], 'sha256': bodies[0]['sha256']},
        body=[row for row in bodies if row['path'] != 'research/capsules/_common.py'])
    declaration['needs']['external'][0]['pin'] = {'ref': bodies[2]['path'], 'sha256': bodies[2]['sha256']}
    declaration['budget']['per_call'].update(invocations=2, wall_s=240)
    if not any(port['name'] == 'capsule_contracts' for port in declaration['ports']['inputs']):
        declaration['ports']['inputs'].append({'name': 'capsule_contracts', 'artifact_type': 'capsule_contracts', 'required': True, 'check_ids': [],
            'description': 'Complete pinned declarations of the exact selectable frozen catalog; descriptive data only', 'schema_ref': 'urn:ai4r:planner-catalog:1.0.0'})
    runner_digest = hashlib.sha256(encoded(planner_check_closure(package))).hexdigest()
    for check in declaration['guarantees']['checks']:
        check['runner'] = {'ref': 'protected_planner_checks', 'sha256': runner_digest}
    catalog['capsules']['planner'].update(declaration_sha256=hashlib.sha256(encoded(declaration)).hexdigest(), body=bodies)
    return catalog_path, catalog, declaration_path, declaration


def planner_check_closure(package):
    names = ['research/planning.py', 'research/binding.py', 'research/unified_planning.py',
             'research/summary_planning.py', 'research/capability_planning.py', 'research/planner_catalog.py']
    return {'implementation': 'research.planning.planner_checks', 'files': {
        name: {'id': 'blob:' + (digest := hashlib.sha256((package / name).read_bytes()).hexdigest()), 'sha256': digest}
        for name in names}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', help='Explicit new core Planner release version')
    parser.add_argument('--check', action='store_true', help='Verify only; do not rewrite catalogs')
    args = parser.parse_args()
    current = json.loads((ROOT / 'jiuwenswarm/research_assets/planner/planner.declaration.json').read_text('utf-8'))
    if not args.check and (not args.version or args.version == current['identity']['version_label']):
        parser.error('writing requires an explicit new --version')
    version = args.version or current['identity']['version_label']
    catalog_path, catalog, declaration_path, declaration = derived(version)
    if args.check:
        if catalog != json.loads(catalog_path.read_text('utf-8')) or declaration != current:
            raise SystemExit('Core Planner release closure differs from committed pins')
    else:
        declaration_path.write_bytes(encoded(declaration))
        # put_record hashes canonical JSON without the optional file newline.
        # Existing declaration catalog entries pin their complete file bytes.
        catalog['capsules']['planner']['declaration_sha256'] = hashlib.sha256(declaration_path.read_bytes()).hexdigest()
        catalog_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.capsules.paper_assets import build_paper_assets
    path = ROOT / 'jiuwenswarm/research/resources/capsules/paper_catalog.json'
    with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(directory)) as store:
        paper = json.loads(encoded(build_paper_assets(store, verify_catalog=False)))
        prior = json.loads(path.read_text('utf-8'))
        for stage in ('paper_summary', 'paper_delivery'):
            if paper[stage] != prior[stage]:
                raise SystemExit('Refusing to change unrelated PDF work release: ' + stage)
        if args.check:
            if paper != prior:
                raise SystemExit('PDF Planner checker closure differs from committed pins')
        else:
            path.write_text(json.dumps(paper, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print('Core Planner and affected PDF checker release pins verified' if args.check else 'Authored new Planner release; no admission or activation performed')


if __name__ == '__main__':
    main()
