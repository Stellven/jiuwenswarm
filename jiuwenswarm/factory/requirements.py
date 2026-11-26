"""TaskInput (``factory.task-input/1`` / ``factory.requirements/1``): the planner's single input.

A TaskInput carries everything the planner needs without requiring a separate multi-arm
measurement contract: objective, pinned subject (engine revision + exact model version),
target hardware, structured acceptance_criteria, and constraints (allowed_effects + budget).
"""
from __future__ import annotations

import json
from pathlib import Path

FORMAT = 'factory.task-input/1'
FORMATS = frozenset({'factory.task-input/1', 'factory.requirements/1'})
SCHEMA = Path(__file__).with_name('schemas') / 'requirements-1.schema.json'
SHIPPED = Path(__file__).with_name('requirements')
TASKS = Path(__file__).with_name('tasks')
EFFECTS = frozenset({'workspace.read', 'workspace.write', 'process.exec', 'gpu.use'})
_validator = None


def input_id(task_input):
    return task_input.get('task_id') or task_input.get('requirements_id') or ''


def schema_problems(document):
    global _validator
    if _validator is None:
        import jsonschema
        _validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding='utf-8')))
    return [f"{'/'.join(map(str, e.absolute_path)) or '(document)'}: {e.message}"
            for e in sorted(_validator.iter_errors(document), key=lambda e: list(e.absolute_path))]


def contract_of(task_input):
    """Load an optional legacy contract if named, or synthesize a single-solution contract from TaskInput."""
    if task_input.get('contract_id'):
        from .contract import load
        contract = load(task_input['contract_id'])
        if contract.get('schema') != 'factory.contract/2':
            raise ValueError(f"Contract {task_input['contract_id']} is not a format-2 contract")
        return contract
    return to_contract(task_input)


def to_contract(task_input):
    """Synthesize a single-solution factory.contract/2 document from a standalone TaskInput.

    Downstream init, scheduler, node_check and lab_manager expect a contract_id JSON with
    target, subject, arms, correctness.checks, measurement.metrics and extensions["factory.node-contracts"].
    """
    tid = input_id(task_input)
    target = task_input['target']
    subject = task_input['subject']
    criteria = task_input['acceptance_criteria']
    checks = [dict(id=c['id'], does=c['description'], applies_to=['candidate'])
              for c in criteria if c['kind'] in {'correctness', 'constraint'}]
    if not checks:
        checks = [dict(id='acceptance_passed', does=criteria[0]['description'], applies_to=['candidate'])]
    metrics = {c['id']: dict(unit='unit', better='lower', how=c['description'])
               for c in criteria if c['kind'] == 'metric'}
    if not metrics:
        metrics = {'primary_objective': dict(unit='score', better='higher', how=task_input['objective'][:200])}
    primary = next(iter(metrics))
    requires = {k: target[k] for k in ('machine', 'cuda', 'sm', 'arch', 'memory_gb') if k in target}
    return dict(
        schema='factory.contract/2',
        contract_id=tid,
        version=1,
        title=task_input['objective'][:120],
        purpose=task_input['objective'],
        scope=dict(covers=[c['description'] for c in criteria], excludes=[]),
        target=dict(profile=target['profile'], requires=requires),
        subject=dict(
            engine=dict(name=subject['engine']['name'],
                        source=subject['engine'].get('source', 'https://github.com/ggml-org/llama.cpp'),
                        revision=subject['engine']['revision']),
            model=dict(name=subject['model']['name'],
                       files=[dict(name=subject['model'].get('manifest') or subject['model']['name'],
                                   size=0, sha256=None)])),
        inputs=dict(default_prompt=dict(media_type='text/plain', sha256='0' * 64, size=0,
                                        description=task_input['objective'][:200])),
        workload=dict(tool='llama-server', argv=['-m', '{model}'], env={},
                      requests=[dict(id='default_req', input='default_prompt',
                                     params=dict(n_predict=32, temperature=0, seed=1))]),
        arms=[
            dict(id='baseline', role='baseline', summary='Pinned stock reference.'),
            dict(id='candidate', role='candidate', summary=task_input['objective'], **{'from': 'baseline'}),
        ],
        measurement=dict(primary=primary, metrics=metrics,
                         protocol=dict(repeats=1, order='sequential', discard_first_request=False,
                                       cold_load='separate', quiet=dict(max_load=1.0, no_builds=True))),
        correctness=dict(equivalence='approximate', checks=checks),
        acceptance=dict(rules=[c['description'] for c in criteria]),
        limits=dict(memory_bytes=int(target.get('memory_gb', 128) * (1024 ** 3))),
        execution=dict(by='factory_lab', lab_profile=target['profile']),
        revisions=[],
    )


def ids(task_input):
    """Structured acceptance criterion ids by kind, from TaskInput."""
    criteria = task_input.get('acceptance_criteria') or []
    return dict(
        arms={'candidate': 'candidate'},
        checks={c['id']: list(c.get('applies_to') or ['candidate'])
                for c in criteria if c['kind'] in {'correctness', 'constraint'}},
        metrics=[c['id'] for c in criteria if c['kind'] == 'metric'],
        all_criteria=[c['id'] for c in criteria],
        built_arms=['candidate'],
        realizable_arms=['candidate'],
    )


def contract_ids(contract):
    """Requirement ids by kind, from a legacy factory.contract/2 (for verify-plan compatibility)."""
    from .contract_v2 import metric_ids
    arms = {arm['id']: arm.get('role', '') for arm in contract['arms']}
    checks = {check['id']: list(check.get('applies_to') or []) for check in contract['correctness']['checks']}
    built = [a for a, role in arms.items() if role in {'candidate', 'combined'}]
    return dict(arms=arms, checks=checks, metrics=list(metric_ids(contract)),
                built_arms=built, realizable_arms=built)


def problems(task_input):
    """Everything wrong with a TaskInput document; empty when the planner can use it."""
    found = schema_problems(task_input)
    if found:
        return found
    unknown = set(task_input['constraints']['allowed_effects']) - EFFECTS
    if unknown:
        found.append(f'constraints/allowed_effects: unknown effects {sorted(unknown)}')
    if task_input.get('task_template') and not (TASKS / (task_input['task_template'] + '.json')).is_file():
        found.append(f'task_template: no task file {task_input["task_template"]} in jiuwenswarm/factory/tasks')
    seen_ids = set()
    for item in task_input.get('acceptance_criteria') or []:
        cid = item['id']
        if cid in seen_ids:
            found.append(f'acceptance_criteria/{cid}: duplicate id')
        seen_ids.add(cid)
    from .plan_catalog import load as catalog
    capsules = catalog()['capsules']
    hints = task_input.get('hints') or {}
    for field in ('must_include', 'excludes'):
        for capsule in hints.get(field) or []:
            if capsule not in capsules or not capsules[capsule]['realizable']:
                found.append(f'hints/{field}: {capsule} is not a realizable capsule in the catalog')
    overlap = sorted(set(hints.get('must_include') or []) & set(hints.get('excludes') or []))
    if overlap:
        found.append(f'hints: capsules {overlap} cannot be in both must_include and excludes')
    return found


def load(path):
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    found = problems(document)
    if found:
        raise ValueError('Invalid TaskInput: ' + '; '.join(found[:8]))
    return document


def shipped():
    """Reviewed TaskInput documents shipped with the factory, by id."""
    result = {}
    for path in sorted(SHIPPED.glob('*.json')):
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            continue
        rid = input_id(document) if isinstance(document, dict) else ''
        if rid:
            result[rid] = document
    return result
