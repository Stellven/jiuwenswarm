"""Native file copies never substitute for private request-owned captures."""
import copy
import json

import pytest

from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.evaluation_history import EvaluationReader
from jiuwenswarm.research.run_evidence import RunEvidence
from jiuwenswarm.research_sidecar.evaluation_records import EvaluationRecords
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime


@pytest.mark.asyncio
@pytest.mark.parametrize('auth_failed', [False, True])
async def test_e3_with_native_run_evidence_exports_only_owned_trace_refs(tmp_path, auth_failed):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        runner = provider.resources.admitted.runner
        runner.evidence = RunEvidence(store, provider.resources.admitted.library)
        if auth_failed:
            from jiuwenswarm.research.providers import ProviderError
            class Refused:
                async def invoke_governed(self, *args, **kwargs):
                    raise ProviderError('auth_failed')
            runner.model.subscription = Refused()
        runtime = capture_runtime(store, provider, [request])
        owner = provider.resources.bind_runtime(runtime)
        response = await provider.single_cc(actor, request)
        assert response['status'] == ('failed' if auth_failed else 'completed')
        audience = Principal(actor.account_id, actor.workspace_ids, actor.operations, frozenset({'reviewer'}))
        raw = EvaluationReader(store, runtime_ref=runtime).export_bytes(audience, request['request_id'], audience='reviewer')
        records = EvaluationRecords.from_archive(raw, request_id=request['request_id'], campaign_id=request['campaign_id'],
            audience='reviewer', expected_request=request).require_complete()
        observed = records.json_ref(records.rows('observation')[0]['artifact_ref'], 'observation')
        assert observed['trace_refs']
        captured = {json.dumps(e['capture_ref'], sort_keys=True) for _, e in records.events if e['kind'] == 'captured'
            and e['capture_kind'] in {'trace', 'model_call', 'route', 'model_start', 'model_refusal'}}
        assert all(json.dumps(ref, sort_keys=True) in captured for ref in observed['trace_refs'])
        files = list(store.iter_records(run_id=observed['run_id'], kinds=('run-evidence-file',)))
        copied_prompts = [row['record']['artifact_ref'] for row in files if row['record']['role'] == 'prompt']
        assert copied_prompts and all(ref not in observed['trace_refs'] for ref in copied_prompts)
        # The optional ordinary evidence path still retains its original copies.
        execution = copy.copy(next(e for e in runner._executions.values() if e['invocation_id'] in
            {records.json_ref(r['artifact_ref'],'assignment_grant')['invocation_id'] for r in records.rows('assignment_grant')}))
        execution.pop('evaluation_owner')
        ordinary = runner._observation(execution, observed['contract_ref'], observed['started_at'], {}, 'failed', 'unit-only')
        assert all(ref in ordinary['trace_refs'] for ref in copied_prompts)
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('explicit', [False, True])
async def test_optional_frozen_model_choice_has_exact_finite_original_export(tmp_path, explicit):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        source = store.read_record(provider.assets['cases'][0]['binding_ref'])
        selection = dict(schema_version='1.0.0', id='model-selection:unit-closed', run_id=source['run_id'],
                         account_id=actor.account_id, mode='codex', preset_id='codex')
        if explicit:
            from jiuwenswarm.research.model_settings import ModelSettingsOwner
            endpoint_ref = store.put_blob(json.dumps({'provider_id':'chatgpt',
                'transport':'packaged-app-server-subscription'}).encode())
            deployment_ref = store.put_blob(json.dumps({'model_id':'unit-manual-model',
                'provider_model_name':'unit-manual-model', 'provider':'chatgpt', 'endpoint_ref':endpoint_ref,
                'adapter_id':'native-chatgpt-subscription-v1', 'revision':'manual-chatgpt:1'}).encode())
            selection.update(chatgpt_model='unit-manual-model', deployment_ref=deployment_ref)
            provider.resources.admitted.runner.model.manual_models = ModelSettingsOwner(store, tmp_path/'private-unit-models.json')
        selection_ref = store.append_record('run-model-selection', selection)
        runtime = store.read_record(capture_runtime(store, provider, [request]))
        runtime.update(id='evaluation-runtime:unit-model-closed', account_model_selection_ref=selection_ref)
        runtime_ref = store.append_record('evaluation-runtime', runtime)
        provider.resources.bind_runtime(runtime_ref)
        assert (await provider.single_cc(actor, request))['status'] == 'completed'
        audience = Principal(actor.account_id, actor.workspace_ids, actor.operations, frozenset({'reviewer'}))
        raw = EvaluationReader(store, runtime_ref=runtime_ref).export_bytes(audience, request['request_id'], audience='reviewer')
        records = EvaluationRecords.from_archive(raw, request_id=request['request_id'], campaign_id=request['campaign_id'],
            audience='reviewer', expected_request=request).require_complete()
        assert records.json_ref(selection_ref, 'source_model_selection') == selection
        assert len(records.rows('source_model_deployment')) == int(explicit)
        assert len(records.rows('source_model_endpoint')) == int(explicit)
        if explicit:
            assert records.account_model_deployment['model_id'] == 'unit-manual-model'
            records.account_model_deployment['model_id'] = 'other-unselected-model'
            with pytest.raises(ValueError, match='frozen account model choice'):
                records._native_closure()
            records._model_selection_closure()
        records.runtime.pop('account_model_selection_ref')
        with pytest.raises(ValueError, match='unbound original account model selection'):
            records._model_selection_closure()
        records.runtime['account_model_selection_ref'] = selection_ref
        records.source['run_id'] = 'another-source'
        with pytest.raises(ValueError, match='another source/account'):
            records._model_selection_closure()
    finally:
        store.close()
