"""Immutable account model choice for a protected private evaluation runtime.

No account preference or credential is read here. The actual model-settings
owner captures the source selection once before the evaluation is frozen.
"""
from __future__ import annotations

import copy

from .contracts import ResearchError, validate


def require(ok, message):
    if not ok:
        raise ResearchError('evaluation_model_binding', message)


def source_model_selection(store, selection_ref, *, account_id, source_run_id):
    validate('Ref', selection_ref)
    require(store.record_kind(selection_ref) == 'run-model-selection',
            'Evaluation model choice is not an original frozen account selection')
    selection = store.read_record(selection_ref)
    common = {'schema_version', 'id', 'run_id', 'account_id', 'mode', 'preset_id'}
    if selection.get('mode') == 'codex':
        extra = {'chatgpt_model', 'deployment_ref'} if selection.get('chatgpt_model') else set()
        require(selection.get('preset_id') == 'codex', 'Frozen subscription model choice is malformed')
    elif selection.get('platform_id') == 'operator-local':
        extra = {'local_binding_id', 'local_binding_sha256', 'platform_id', 'deployment_ref'}
        require(isinstance(selection.get('preset_id'), str) and selection['preset_id'].startswith('local-'),
                'Frozen local model choice is malformed')
    else:
        extra = {'credential_id', 'platform_id', 'deployment_ref'}
    require(set(selection) == common | extra, 'Frozen model choice has missing or unsupported fields')
    source = store.get_run(source_run_id, account_id=account_id)
    require(selection.get('schema_version') == '1.0.0'
            and selection.get('id') == selection_ref['id']
            and selection.get('run_id') == source['id']
            and selection.get('account_id') == account_id
            and selection.get('mode') in {'codex', 'api'},
            'Evaluation model choice belongs to another source/account')
    originals = list(store.iter_records(run_id=source_run_id, kinds=('run-model-selection',)))
    require(len(originals) == 1 and originals[0]['ref'] == selection_ref,
            'Evaluation source model choice is absent or ambiguous')
    if selection['mode'] == 'api' or selection.get('chatgpt_model'):
        deployment = store.read_record(selection['deployment_ref'])
        require(set(deployment) == {'model_id', 'provider_model_name', 'provider', 'endpoint_ref', 'adapter_id', 'revision'},
                'Frozen model deployment has missing or unsupported fields')
        store.read_record(deployment['endpoint_ref'])
    return copy.deepcopy(selection)


def evaluation_model_selection(store, context):
    """Resolve only exact live-authorized runtime/source/private-child edges."""
    fields = {'evaluation_runtime_ref', 'account_model_selection_ref'}
    present = fields & set(context)
    if not present:
        return None
    require(present == fields, 'Private model context lacks its frozen runtime choice')
    from .evaluation_projection import private_record
    runtime = private_record(store, context['evaluation_runtime_ref'], 'evaluation-runtime')
    require(runtime.get('account_model_selection_ref') == context['account_model_selection_ref'],
            'Private model context changes its original frozen account choice')
    child = private_record(store, context['contract_ref'], 'evaluation-subnode-context')
    request = private_record(store, child['request_ref'], 'evaluation-request')
    require(request['runtime_ref'] == context['evaluation_runtime_ref']
            and child['run_id'] == context['run_id'], 'Private model choice belongs to another runtime/run')
    source = store.read_record(child['source_subject_ref'], contract_id='subnode-execution-contract')
    return source_model_selection(store, runtime['account_model_selection_ref'],
        account_id=runtime['account_id'], source_run_id=source['run_id'])
