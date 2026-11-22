"""Agent-authored diagnostics admitted under an immutable operator envelope.

Preparation has no build or lab effects. Diagnostics never promote engines.
"""
from pathlib import Path
import json
import os
import re
from .execution_binding import digest, file_digest
from .store import NotFound, ScopeDenied, encoded

PURPOSES = {'cpu_analysis', 'gpu_probe', 'engine_diagnostic', 'engine_comparison'}
SPEC_FIELDS = {'hypothesis', 'evidence_ids', 'purpose', 'changed_variables', 'artifacts',
               'recipe', 'measurements', 'interpretation', 'budget', 'build'}
LIMITS = {'timeout_s', 'cpus', 'memory_bytes', 'output_bytes', 'pids'}


def positive(value):
    return type(value) is int and value > 0


def validate_contract(contract):
    required = {'adapter', 'version', 'target', 'specification', 'image', 'limits',
                'campaign_timeout_s', 'acceptance_policy_sha256', 'model', 'execution_binding_id', 'build_binding'}
    if not isinstance(contract, dict) or set(contract) != required:
        raise ValueError('Invalid prepared experiment contract')
    if contract['adapter'] != 'factory-experiment-v1' or contract['version'] != 1:
        raise ValueError('Unsupported experiment adapter')
    spec = contract['specification']
    if set(spec) - SPEC_FIELDS or SPEC_FIELDS - {'build'} - set(spec):
        raise ValueError('Unknown or missing experiment fields; acceptance rules are operator-owned')
    if spec['purpose'] not in PURPOSES:
        raise ValueError('Unsupported experiment purpose')
    for key in ('hypothesis', 'interpretation'):
        if not isinstance(spec[key], str) or not spec[key].strip() or len(spec[key]) > 8000:
            raise ValueError('Bounded text required: ' + key)
    for key in ('evidence_ids', 'changed_variables', 'measurements'):
        if not isinstance(spec[key], list) or not spec[key] or len(spec[key]) > 64 or any(not isinstance(x,str) or not x or len(x)>2000 for x in spec[key]):
            raise ValueError('Bounded names required: ' + key)
    if set(contract['limits']) != LIMITS or any(not positive(v) for v in contract['limits'].values()):
        raise ValueError('Explicit positive resource limits required')
    if spec['budget'] != contract['limits'] or contract['campaign_timeout_s'] != contract['limits']['timeout_s']:
        raise ValueError('Experiment budgets differ')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', contract['image']):
        raise ValueError('Immutable image required')
    if not isinstance(spec['artifacts'], dict) or len(spec['artifacts']) > 32:
        raise ValueError('Bounded probe artifacts required')
    for name, text in spec['artifacts'].items():
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,100}', name) or not isinstance(text,str):
            raise ValueError('Probe artifact must be a plain filename and text')
    if len(encoded(spec['artifacts']).encode()) > 262144:
        raise ValueError('Probe artifacts exceed 256 KiB')
    recipe = spec['recipe']
    if not isinstance(recipe, list) or not recipe or len(recipe) > 128 or any(not isinstance(v,str) or not v or '\0' in v or len(v)>4096 for v in recipe):
        raise ValueError('Recipe must be a bounded argv')
    return contract


def prepare(loop, experiment_id, specification, image):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', experiment_id):
        raise ValueError('Invalid experiment ID')
    policy = loop.policy.get('experiment_authority')
    if not isinstance(policy, dict):
        raise ScopeDenied('Operator experiment authority required')
    if image not in policy['images']:
        raise ScopeDenied('Image outside admitted runtime set')
    if specification.get('purpose') not in policy['purposes']:
        raise ScopeDenied('Experiment purpose outside authority')
    if not set(specification.get('changed_variables', [])) <= set(policy['permitted_changes']):
        raise ScopeDenied('Changed variables outside authority')
    budget = specification.get('budget', {})
    if set(budget) != LIMITS or any(not positive(v) or v > policy['limits'][k] for k,v in budget.items()):
        raise ScopeDenied('Experiment exceeds resource envelope')
    model = policy.get('model')
    if model is not None:
        if set(model) != {'path','sha256'} or file_digest(model['path']) != model['sha256']:
            raise ScopeDenied('Pinned model identity differs')
    binding = loop.task['constraints'].get('execution_binding')
    if binding is None:
        raise ScopeDenied('Authored experiments require an execution binding')
    from .execution_binding import verify_task
    verify_task(loop.store, loop.task_id)
    loop.store.validate_evidence(loop.task_id, specification['evidence_ids'], getattr(loop.scoped, 'readable', ()))
    contract = validate_contract(dict(adapter='factory-experiment-v1', version=1, target='spark-gb10',
        specification=specification, image=image, limits=budget, campaign_timeout_s=budget['timeout_s'],
        acceptance_policy_sha256=policy['acceptance_policy_sha256'], model=model,
        execution_binding_id=binding['binding_id'], build_binding=None))
    if specification.get('build'):
        build = specification['build']
        from .builder import Builder
        source = Path(build['source']['path']).resolve()
        roots = [Path(p).resolve() for p in policy.get('owned_worktrees', [])]
        if source not in roots:
            raise ScopeDenied('Build source must be an operator-owned worktree')
        # Existing builder validates clean commit/tree, pinned dependency and recipe.
        if os.environ.get('FACTORY_BRIDGE_DIR'):
            from .bridge import call
            result=call('experiment_build_prepare',task_id=loop.task_id,request=build)
            result.check_returncode()
            contract['build_binding']=json.loads(result.stdout)
        else:
            contract['build_binding'] = Builder(loop.store)._request(build)
    raw = (encoded(contract) + '\n').encode()
    artifact_id = 'prepared-experiment:' + experiment_id
    try:
        artifact = loop.store.read(loop.task_id, artifact_id)
        if artifact['sha256'] != file_bytes_digest(raw):
            raise ValueError('Prepared experiment ID conflicts with frozen specification')
    except NotFound:
        artifact = loop.store.put_artifact(loop.task_id, artifact_id, raw, 'application/json', None)
    return dict(experiment_id=experiment_id, artifact_id=artifact_id, sha256=artifact['sha256'],
                execution_authorized=False, promotion_authorized=False)


def file_bytes_digest(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def resolve(loop, experiment_id):
    artifact = loop.store.read(loop.task_id, 'prepared-experiment:' + experiment_id)
    path = loop.store.home / artifact['location']
    if file_digest(path) != artifact['sha256']:
        raise ValueError('Prepared experiment artifact changed')
    contract = validate_contract(json.loads(path.read_text()))
    return contract, dict(path=str(path), sha256=artifact['sha256'])
