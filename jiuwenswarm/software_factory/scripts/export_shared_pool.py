"""Export actual workflow and pinned CC declarations; never execute capabilities."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import subprocess

from jiuwenswarm.software_factory.catalog import stage_catalog
from jiuwenswarm.software_factory.workflow_definitions import WorkflowRegistry
from jiuwenswarm.software_factory.shared_pool import normalize_cc, normalize_workflows, validate_pool


def export_pool(repository, cc_ref):
    import yaml
    from jsonschema import Draft202012Validator
    def git(*args):
        return subprocess.run(['git', '-C', str(repository), *args], check=True,
                              capture_output=True).stdout
    repository_url = 'https://github.com/Stellven/jiuwenswarm'
    own_sha = git('rev-parse', 'HEAD').decode().strip()
    cc_sha = git('rev-parse', cc_ref + '^{commit}').decode().strip()
    stages = stage_catalog()
    library = WorkflowRegistry(stages).export()
    catalog = {'stages': [{**s.serializable(), 'validation_bindings': {
        name: function.__module__ + ':' + function.__name__
        for name, function in s.validators.items()}} for s in stages]}
    entries = normalize_workflows(library, catalog, {
        'system': 'workflow', 'repository': repository_url, 'revision': own_sha,
        'path': 'jiuwenswarm/software_factory/workflow_definitions.py'})
    schema = json.loads(git('show', cc_sha + ':jiuwenswarm/ccv2/schemas/cc.schema.json'))
    validator = Draft202012Validator(schema)
    paths = git('ls-tree', '-r', '--name-only', cc_sha, 'jiuwenswarm/factory/ccs').decode().splitlines()
    count = 0
    for path in paths:
        if not path.endswith('/cc.yaml'):
            continue
        declaration = yaml.safe_load(git('show', cc_sha + ':' + path))
        validator.validate(declaration)
        parent = PurePosixPath(path).parent
        entries.extend(normalize_cc(declaration, {
            'system': 'cc', 'repository': repository_url, 'revision': cc_sha, 'path': path},
            lambda relative: git('show', cc_sha + ':' + str(parent / relative))))
        count += 1
    pool = {'schema_version': '0.1.0', 'entries': entries}
    validate_pool(pool)
    return pool, {'workflow_revision': own_sha, 'cc_revision': cc_sha,
                  'cc_declarations': count, 'entries': len(entries),
                  'kinds': dict(Counter(e['kind'] for e in entries)),
                  'execution_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--cc-ref', default='origin/cc-siminfeng')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pool, summary = export_pool(args.repository, args.cc_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pool, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
