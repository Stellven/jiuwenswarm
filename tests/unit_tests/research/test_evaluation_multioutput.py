"""Actual two-port frozen replay: one selected review, all-port host checks."""
import io
import json
import zipfile

import pytest

from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.evaluation_provider import EvaluationProvider, InstalledEvaluationResources
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_authority import source_fixture, product_state
from tests.unit_tests.research.test_evaluation_private_replay import replay_runtime


@pytest.mark.asyncio
@pytest.mark.parametrize('bad_unselected', [False, True])
async def test_two_original_ports_are_checked_before_one_selected_private_review_and_export(tmp_path, bad_unselected):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, producer, actor, single, prompts = await source_fixture(tmp_path, allowed_entry_points=['E2', 'E3'],
        opportunity_statement='The frozen mechanism avoids repeated lookup work.')
    try:
        admitted = producer.resources.admitted
        contract_ref = producer.assets['cases'][0]['binding_ref']
        contract = store.read_record(contract_ref)
        plan_ref = next(x['ref'] for x in store.iter_records(kinds=('bound-check-plan',)) if x['record']['contract_ref'] == contract_ref)
        original = await admitted.execute(admitted.prepare(contract_ref, plan_ref, semantic_review=False))
        assert len(prompts) == 1 and len(original.output_refs) == 2
        store.require_product_material(list(original.output_refs.values()))
        frozen_outputs=dict(original.output_refs);frozen_observation=original.observation_ref
        if bad_unselected:
            # An explicit negative IMPORTED fixture, never a claimed new live
            # producer: retain the valid selected output, alter the other port's
            # internally linked score and capture the submitted observation.
            # Imported observation provenance cannot prove producing execution.
            card=store.read_record(frozen_outputs['opportunity_card'])
            card['scores']['total']+=1
            frozen_outputs['opportunity_card']=store.put_blob(json_bytes(card),media_type='application/json')
            observed=store.read_record(original.observation_ref)
            observed.update(id=observed['id']+':negative-import',output_refs=list(frozen_outputs.values()))
            frozen_observation=store.put_record('invocation-observation',observed,record_id='negative-import-observation')
        selected = 'screening_result'
        verifier = admitted.resources.composition.installed['verifier']['pin']
        verifier_id = verifier['cc_name'] + '@' + verifier['cc_version']
        declaration = contract['bindings'][0]['declaration_ref']
        binding = store.append_record('evaluation-case-binding', {'schema': 'ai4r-node-replay-binding:2', 'id': 'binding:two-original',
            'contract_ref': contract_ref, 'check_plan_ref': plan_ref, 'output_refs': frozen_outputs,
            'original_observation_ref': frozen_observation, 'verifier_cc_id': verifier_id,
            'host_records': [], 'selected_output_port': selected})
        assets = store.append_record('evaluation-assets', {'schema': 'ai4r-evaluation-assets:1', 'id': 'assets:two-original',
            **{k: producer.assets[k] for k in ('profile_ref', 'configuration_ref', 'account_id', 'workspace_id', 'campaign_id')},
            'entries': [{'path': path, 'sha256': ref['sha256'], 'artifact_ref': ref, 'role': role}
                for path, ref, role in [('declaration.json', declaration, 'declaration'),
                    ('selected.json', original.output_refs[selected], 'output')]],
            'cases': [{'case_id': 'two-original', 'entry_point': 'E2', 'binding_ref': binding, 'record_gate': False}]})
        resources = InstalledEvaluationResources(admitted, profile_ref=producer.profile_ref, assets_ref=assets,
            library_snapshot_ref=producer.resources.snapshot_ref)
        replay = EvaluationProvider(store, admitted.resources.operator, assets_ref=assets, resources=resources, library=admitted.library)
        request = {'request_id': 'two-original:request', 'campaign_id': producer.assets['campaign_id'], 'case_id': 'two-original',
            'evaluation_profile_id': producer.profile['profile_id'], 'verifier_cc_id': verifier_id, 'node_id': contract['node_id'],
            'declaration': {'path': 'declaration.json', 'sha256': declaration['sha256']},
            'output': {'path': 'selected.json', 'sha256': original.output_refs[selected]['sha256']}}
        runtime = replay_runtime(store, replay, [request])
        owner = resources.bind_runtime(runtime)
        before = product_state(store)
        result = await replay.node_replay(actor, request)
        assert result['tier1_verdict'] == ('FAIL' if bad_unselected else 'PASS'), result['reason']
        assert result['tier2_verdict'] == ('NOT_RUN' if bad_unselected else 'PASS'), result['reason']
        assert len(prompts) == (1 if bad_unselected else 2)
        assert len(result['model_calls']) == (0 if bad_unselected else 1)
        assert product_state(store) == before
        store.require_product_material(list(original.output_refs.values()))
        actor = Principal(actor.account_id, actor.workspace_ids, actor.operations, frozenset({'reviewer'}))
        data = EvaluationReader(store, runtime_ref=runtime).export_bytes(actor, request['request_id'], audience='reviewer')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read('evaluation_export.json'))
            delivered = {json_bytes(f['artifact_ref']) for f in manifest['files']}
            assert all(json_bytes(ref) in delivered for ref in [frozen_observation, plan_ref, *frozen_outputs.values()])
    finally:
        store.close()
