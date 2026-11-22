"""Provision only the reviewed CPU capsule-inspection task; no source/build/model jobs."""
from pathlib import Path

from jiuwenswarm.factory.store import Store
from scripts.spark.prepare_star_home import copy_auth_for_home

ROOT = Path(__file__).resolve().parents[2]
NAMES = ('observability_event_recorder', 'weight_placement_planner', 'expert_weight_cache',
         'expert_demand_predictor', 'batch_layout_mapper')


def prepare_inspection_home(home, task):
    if set(task.get('allowed_effects', [])) != {'process.exec', 'workspace.read'}:
        raise ValueError('Inspection template must have exactly the reviewed read grants')
    if task.get('operator_labels', {}).get('inspection_only') is not True:
        raise ValueError('Inspection template must be labelled inspection_only')
    if task.get('constraints', {}).get('local_commits'):
        raise ValueError('Inspection cannot provision a product checkout')
    if not copy_auth_for_home(home):
        raise ValueError('Existing Codex login unavailable; operator login required')
    references = list((ROOT / 'jiuwenswarm/factory/contracts').glob('star-deepseek-v1.*'))
    for name in NAMES:
        capsule = ROOT / 'jiuwenswarm/factory/ccs' / name
        references.extend(path for path in capsule.iterdir() if path.is_file() and path.suffix in {'.md', '.yaml', '.json'})
    references.extend((Path.home() / 'predemo-spark/inputs/ontology').glob('*'))
    with Store(home) as store:
        refs = []
        names = []
        for path in sorted(set(references)):
            if not path.is_file() or path.is_symlink():
                continue
            label = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else 'ontology/' + path.name
            artifact = store.put_artifact(task['task_id'], 'source:' + label, path, 'text/plain', None)
            refs.append(artifact['artifact_id'])
            names.append(label)
        store.append_observation(task['task_id'], dict(kind='inspection_inputs', source_artifacts=refs,
            values={'message': 'Operator prepared read-only all-five capsule inspection; no model/build job', 'files': names},
            limitations='This session inspects methodology only; it does not implement capsules or measure performance.'))
    return {'auth_prepared': True, 'input_artifacts': len(refs), 'inspection_only': True}
