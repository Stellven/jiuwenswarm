#!/usr/bin/env python3
"""Prepare one isolated factory home and copy existing auth; never starts an agent/model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from jiuwenswarm.factory.controller import Controller
from jiuwenswarm.factory.contract import load

NAMES = ['observability_event_recorder', 'weight_placement_planner', 'expert_weight_cache',
         'expert_demand_predictor', 'batch_layout_mapper']
ROOT = Path.home() / 'predemo-spark'


def prepare(name, *, copy_auth=True):
    home = ROOT / 'factory-runs' / ('star-' + name)
    if home.exists():
        raise ValueError('Factory home already exists; use retained task instead of overwriting')
    task_path = REPO / 'jiuwenswarm/factory/tasks' / ('star-spark-' + name + '.json')
    task = json.loads(task_path.read_text())
    workspace = home / 'agent-workspace'
    workspace.mkdir(parents=True)
    checkout = workspace / task['source']['subpath']
    source = ROOT / 'llama.cpp-stock'
    subprocess.run(['git', '-C', str(source), 'worktree', 'add', '-b', task['source']['branch'],
                    str(checkout), task['source']['pre_integration_commit']], check=True)
    # The factory initializes only the already-provisioned, clean owned checkout.
    # No agent, model, build or network call occurs here.
    controller = Controller(home=home, grants=task['allowed_effects'])
    task_id = controller.init_task(task_path)
    references = [REPO / 'jiuwenswarm/factory/contracts/star-deepseek-v1.json',
                  REPO / 'jiuwenswarm/factory/contracts/star-deepseek-v1.md',
                  REPO / 'jiuwenswarm/factory/ccs/star-transport-migration.json',
                  ROOT / 'inputs/ontology/SHA256SUMS']
    references += sorted((ROOT / 'inputs/ontology').glob('*'))
    bundle = REPO / 'jiuwenswarm/factory/ccs' / name
    references += [p for p in sorted(bundle.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    refs = []
    for index, path in enumerate(dict.fromkeys(references)):
        artifact = controller.store.put_artifact(task_id, f'input-{index}:{path.name}', path,
                                                'application/json' if path.suffix == '.json' else 'text/plain', None)
        refs.append(artifact['artifact_id'])
    controller.store.append_observation(task_id, dict(kind='spark_preparation',
        values=dict(source_commit=task['source']['pre_integration_commit'], target='spark-gb10',
                    agent_started=False, models_loaded=False, capsule_source_version='1.1.1',
                    capsule_transport_version='1.1.2'), source_artifacts=refs,
        limitations='Preparation only; no verifier, native build or runtime acceptance yet.'))
    auth_present = False
    if copy_auth:
        auth = Path.home() / '.codex/auth.json'
        if auth.is_file():
            destination = home / 'agent-data/subscription/codex-home'
            destination.mkdir(parents=True, mode=0o700)
            shutil.copyfile(auth, destination / 'auth.json')
            (destination / 'auth.json').chmod(0o600)
            auth_present = True
    result = dict(home=str(home), task_id=task_id, checkout=str(checkout), auth_copied=auth_present,
                  agent_started=False, models_loaded=False)
    (home / 'preparation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capsule', choices=NAMES)
    parser.add_argument('--no-auth', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.capsule, copy_auth=not args.no_auth), indent=2))
