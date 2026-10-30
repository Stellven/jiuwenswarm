"""Ordinary (non-replay) evidence-aware review path, end to end with a fake model.

The evidence-aware verifier path had only ever run on the private replay
branch. This drives the real CapsuleRunner: a work subnode (Intent, evidence
aware release) succeeds, the runner builds review evidence, binds the evidence
aware verifier through VerifierBindings and runs the verifier's host checks.

Each assertion pins one fix:
* binding.validate_child_authority raised input_authority when review_evidence
  was bound required=True against the verifier's optional port. Reverting
  compiler.VerifierBindings.bind (commit 680c56b3a) fails the run before the
  verifier starts, so the review_evidence required-False assertion, the
  verifier-observation lookup and the accepted result all fail.
* runner._host_checks did not put the verifier's review_evidence refs in its
  read ceiling, so the verifier's host_authority check was FAIL. Reverting that
  (commit 8fae99885) fails only the host_authority PASS assertions.
"""
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.checks.assets import prepare_evidence_aware_release
from jiuwenswarm.research.checks.compiler import compiler_checks
from jiuwenswarm.research.compiler import VerifierBindings, input_port
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.evidence_review import prepare_evidence_aware_verifier_release
from jiuwenswarm.research.intake import qualify_intake
from jiuwenswarm.research.runner import CapsuleRunner
from tests.unit_tests.research.test_budget_ceiling import installed_library

GENERIC = {'declared_output_conformance', 'internal_consistency', 'limitations_consistency'}


async def admit(library, store, asset, actor):
    library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor)
    admission = store.read_record(await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=256))
    assert admission['status'] == 'admitted', admission['reasons']
    pin = admission['cc']
    library.set_standing(pin['cc_name'], pin['cc_version'], 'active', actor, reason='Controlled evidence-path fixture')
    return pin


@pytest.mark.asyncio
async def test_ordinary_evidence_aware_review_binds_optional_port_and_passes_host_authority(tmp_path):
    store, registry, checks, library, installed, actor = await installed_library(tmp_path)
    work_base = installed['intent']
    profile = store.read_record(work_base['profile_ref'], contract_id='checking-profile')
    selected = next(row['criterion_id'] for row in profile['criteria'] if row['criterion_id'] not in GENERIC)
    work_asset = prepare_evidence_aware_release(store, work_base, version_label='evidence-test',
        evidence_criterion_ids=[selected], evidence_input_names=['request'],
        reviewer_instructions='Use the selected original request and Tier 1 scores only for the named criterion.')
    verifier_asset = prepare_evidence_aware_verifier_release(store, installed['verifier'], version_label='m1-3')
    work_pin = await admit(library, store, work_asset, actor)
    # The new release reuses the installed Intent carrier and check runners under its own pins.
    handler, implementation_refs = registry.resolve(work_base['pin']['cc_name'], work_base['pin']['cc_version'], work_base['pin']['declaration_sha256'])
    registry.register(work_pin['cc_name'], work_pin['cc_version'], handler, declaration_sha256=work_pin['declaration_sha256'],
        implementation_refs=implementation_refs)
    work_bundle = store.read_record(work_asset['bundle_ref'], contract_id='check-bundle')
    checks.register_bundle(work_bundle['bundle_id'], [row['check_id'] for row in work_bundle['checks']], compiler_checks,
        implementation_ref=work_bundle['checks'][0]['runner_ref'], profile_ref=work_asset['profile_ref'])
    verifier_pin = await admit(library, store, verifier_asset, actor)

    opaque = store.put_blob(b'controlled approved binding')
    user = Principal('alice', frozenset({'project'}), frozenset({'ingest'}))
    request = Path('tests/fixtures/research/compiler/request.txt').read_text('utf-8')
    intake_ref = qualify_intake(store, user, request, [], workspace_id='project', profile_ref=opaque,
        workspace_ref=opaque, input_directory_ref=opaque)
    intake = store.read_record(intake_ref)
    store.create_run('run:evidence-path', account_id='alice', workspace_id='project', submission={})
    intent_ir = json.loads(Path('tests/fixtures/research/compiler/intent_ir.json').read_bytes())

    def rewrite(value):
        if isinstance(value, dict):
            return intake['request_ref'] if set(value) == {'id', 'sha256'} else {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        return value

    verifier_profile = store.read_record(work_asset['profile_ref'], contract_id='checking-profile')
    reply = {'findings': [{'criterion_id': row['criterion_id'], 'outcome': 'PASS', 'reason': 'Controlled evidence-path fixture.'}
                          for row in verifier_profile['criteria'] if row['target_port'] in (None, 'intent')],
             'uncertainties': [], 'limitations': [], 'required_correction': None}
    calls = []

    class Transport:
        async def call(self, context, prompt):
            protected = runner.authorize_model_context(context)
            calls.append(protected['call_function'])
            store.append_record('model-call-start', dict(protected, id=protected['call_id'] + ':start'))
            text = json.dumps(rewrite(intent_ir)) if protected['call_function'] == 'worker' else json.dumps(reply)
            return {'text': text, 'observed_runtime': True}

    runner = CapsuleRunner(store, registry, checks, model=Transport(), check_assets=library.check_assets)
    final = store.put_record('node-finalization-profile', {'schema_version': '2.0.0', 'id': 'final',
        'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
        'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0})
    factory = ContractFactory(store, library, verifier_pin=verifier_pin, finalization_profile_ref=final)
    inputs = [input_port('request', 'qualified-intake:field-contract:2', intake_ref)]
    parent = factory.prepare_parent('run:evidence-path', 'intent', [{'subnode_id': 'intent', 'cc': work_pin, 'depends_on': []}],
        inputs=inputs, outputs=[{'name': 'intent', 'contract_id': 'intent-ir', 'version': '1.0.0', 'required': True}],
        objective='Controlled ordinary evidence-aware review', requirement_ids=['intent'],
        limits={'time_s': 120, 'model_calls': 2, 'memory_mb': 256}, policy_ref=opaque, configuration_ref=opaque, template_ref=opaque,
        authority_ceiling={'network': 'none', 'network_allowlist': [], 'resource_reads': [intake_ref, intake['request_ref']],
                           'write_roots': [], 'tools': []})
    contract, checkplan, bundle = factory.bind_subnode(parent, 'intent', inputs)
    selection = store.put_record('model-selection-profile', {'schema_version': '1.0.0', 'id': 'fixed', 'policy_mode': 'fixed_baseline',
        'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {},
        'selection_allowance': {'enabled': False, 'deployment_ref': None, 'model_calls': 0, 'time_s': 0, 'output_tokens': 0, 'disclosure_scope': []},
        'alternate_model_id': None, 'policy_ref': opaque})
    runner.configure_run('run:evidence-path', model_selection_profile_ref=selection, deployment_ref=opaque,
        router={'enabled': False, 'deadline_s': 30, 'profile_ref': None}, configuration_ref=opaque,
        run_limits={'time_s': 120, 'model_calls': 2, 'memory_mb': 256})
    runner.prepare_node_check_plan(parent)

    result = await runner.run(contract, checkplan, bundle_id=bundle,
        verifier_contract_refs=VerifierBindings(factory, parent, contract, {'intent': 'intent.verifier'}))

    # Work succeeded, then the evidence-aware verifier ran; nothing was refused at binding.
    assert calls == ['worker', 'verifier']
    assert result.accepted and len(result.assessment_refs) == 1
    verifier_contracts = [row for row in store.iter_records(run_id='run:evidence-path', kinds=('subnode-execution-contract',))
                          if row['record']['bindings'][0]['role'] == 'verifier']
    assert len(verifier_contracts) == 1
    vref, vcontract = verifier_contracts[0]['ref'], verifier_contracts[0]['record']
    ports = {port['name']: port for port in vcontract['inputs']}
    # Fix 680c56b3a: the host binds review_evidence as the declared optional port.
    assert set(ports) == {'subject_declaration', 'subject_output', 'review_evidence'}
    assert ports['review_evidence']['required'] is False and len(ports['review_evidence']['artifact_refs']) == 1
    declared = store.read_record(vcontract['bindings'][0]['declaration_ref'], contract_id='capsule-declaration')
    assert next(p for p in declared['ports']['inputs'] if p['name'] == 'review_evidence')['required'] is False

    # Fix 8fae99885: the verifier's own host_authority check passes with that projection in its read ceiling.
    observations = [row for row in store.iter_records(run_id='run:evidence-path', kinds=('invocation-observation',))
                    if row['record']['subnode_id'] == 'intent.verifier']
    assert len(observations) == 1
    rows = runner._host_checks(vref, vcontract, observations[0]['record'], observations[0]['ref'])
    assert {row['check_id']: row['outcome'] for row in rows}['host_authority'] == 'PASS'
    persisted = [row['record'] for row in store.iter_records(run_id='run:evidence-path', kinds=('deterministic-check-result',))
                 if row['record']['subject_ref'] == observations[0]['ref'] or row['record']['subject_ref'] == result.assessment_refs[0]]
    assert persisted and all(r['outcome'] == 'PASS' for p in persisted for r in p['results'] if r['check_id'] == 'host_authority')
    store.close()
