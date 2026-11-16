"""Compile explicit engineering requirements into artifact and capability demands.

Free prose is retained as intent. Decisions use the submitted acceptance contract
and inspected source features; this does not pretend to understand arbitrary
natural language with keyword-to-DAG templates.
"""
from __future__ import annotations
from .contracts import StageFailure

ACCEPTANCE_GOALS = {
    'source_project': 'construction.package', 'cpu_validation': 'construction.portability',
    'full_model_inference': 'inference.result', 'compare_original': 'verification.comparison',
    'native_execution': 'inference.result',
}


def normalize_task(task):
    if not isinstance(task, dict) or not isinstance(task.get('description'), str) or not task['description'].strip():
        raise StageFailure('invalid_engineering_task', 'Engineering task requires a nonempty description')
    unknown = set(task) - {'description', 'source_scope', 'capabilities', 'acceptance', 'oracle'}
    if unknown:
        raise StageFailure('invalid_engineering_task', f'Unknown task fields: {sorted(unknown)}')
    scope = task.get('source_scope') or ['src/kernels/cuda/*.cu']
    capabilities = task.get('capabilities') or []
    for name, values in (('source_scope', scope), ('capabilities', capabilities)):
        if not isinstance(values, list) or len(values) > 32 or any(not isinstance(v, str) or not v.strip() for v in values):
            raise StageFailure('invalid_engineering_task', f'{name} requires nonempty string entries')
    if any(path.startswith('/') or '..' in path.split('/') for path in scope):
        raise StageFailure('invalid_engineering_task', 'Source scope must remain inside the acquired repository')
    acceptance = task.get('acceptance') if task.get('acceptance') is not None else {'source_project': True, 'cpu_validation': True}
    if not isinstance(acceptance, dict) or not acceptance or set(acceptance) - set(ACCEPTANCE_GOALS) or any(type(v) is not bool for v in acceptance.values()):
        raise StageFailure('invalid_engineering_task', 'Acceptance requires the declared Boolean engineering criteria')
    normalized = {'description': task['description'].strip(), 'source_scope': list(scope),
                  'capabilities': list(dict.fromkeys(capabilities)), 'acceptance': acceptance}
    if task.get('oracle') is not None:
        from .oracle_validation import OracleError, normalize_oracle
        try:
            normalized['oracle'] = normalize_oracle(task['oracle'])
        except OracleError as error:
            raise StageFailure(error.code,str(error),error.details) from error
    return normalized


def compile_goals(request):
    goals = list(dict.fromkeys(request.get('goals') or []))
    if request.get('workflow_path') and 'workflow.execution' not in goals:
        goals.append('workflow.execution')
    if request.get('task') is not None:
        task = normalize_task(request['task'])
        request['task'] = task
        for name, enabled in task['acceptance'].items():
            if enabled and ACCEPTANCE_GOALS[name] not in goals:
                goals.append(ACCEPTANCE_GOALS[name])
        if task['acceptance'].get('native_execution') and request.get('target_backend', 'ascend') != 'ascend':
            raise StageFailure('target_contract_conflict', 'Native Ascend acceptance requires target_backend=ascend')
    if not goals:
        raise StageFailure('invalid_engineering_task', 'Specify an engineering acceptance criterion or artifact goal')
    request['goals'] = goals
    return request
