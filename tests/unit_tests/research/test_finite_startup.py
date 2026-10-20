"""Actual finite composition/attachment with explicitly controlled probes.

These tests do not qualify live model, checking, isolation or trajectory.
"""
import copy
import json
import os
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.native_ports import NativePorts
from jiuwenswarm.research.operator_config import OperatorConfiguration
from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture
from tests.unit_tests.research.test_native_readiness import installed_manifest


async def finite_target(tmp_path, monkeypatch):
    from jiuwenswarm.research import bootstrap_core, trajectory
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path / 'source', 'valid')
    operator = OperatorConfiguration.from_mapping(owner._operator, resolve_profile=store.read_record)
    actor = Principal('owner', frozenset({'work'}), frozenset({'readiness', 'submit', 'status'}))
    options = {key: copy.deepcopy(protected[key]) for key in (
        'finite_e1_binding_ref', 'profile_ref', 'workspace_ref', 'input_directory_ref',
        'resource_inventory_ref', 'authority_ceiling', 'host_records', 'candidate_pins')}
    options['finalization_profile_ref'] = scheduler.factory.finalization_profile_ref
    options['document_extraction_timeout_s'] = 10  # Explicit bounded fixture only; no product default.
    bindings = {key: copy.deepcopy(protected[key]) for key in (
        'configuration_ref', 'model_selection_profile_ref', 'deployment_ref')}
    bindings.update(workspace_id='work', host_id='controlled-finite-startup', protected_options=options)
    monkeypatch.setattr(bootstrap_core, 'LibraryService', lambda *args, **kwargs: owner.library)
    manifest, package, build = installed_manifest(tmp_path)
    ipc = tmp_path / 'ipc'; ipc.mkdir(mode=0o700)
    (ipc / 'session.json').write_text(json.dumps({'session_id': 'finite-startup-test', 'capability': 'controlled-test-only'}))
    (ipc / 'session.json').chmod(0o600)
    ports = NativePorts(executor=SimpleNamespace(prerequisites=lambda: {'ready': True}),
        ipc_root=ipc, app_uid=os.geteuid(), build_manifest=manifest,
        installed_package_root=package, installed_component_roots={'jiuwenswarm_tui': tmp_path / 'installed_tui'})
    status = {'enabled': True, 'state': 'ready', 'capture_healthy': True, 'builder_qualified': False}
    async def observe_status(*args, **kwargs):
        return copy.deepcopy(status)
    ports.status_client = SimpleNamespace(call=observe_status)
    ports.model_bridge = scheduler.runner.model
    monkeypatch.setattr(trajectory, 'capture_healthy', lambda: True)
    composition = await bootstrap_core.compose_core(store=store, operator=operator,
        model=ports.model_bridge, executor=ports.executor, readiness=None, upload_manager=None,
        principal=actor, workspace_id='work', protected_options=options, initialize=False,
        **{key: bindings[key] for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')})
    assert not composition.diagnostics, composition.diagnostics
    assert composition.compiler is None and composition.planner is None
    assert composition.service.finite_e1.binding_ref == owner.binding_ref
    bindings['build_id'] = build
    bindings['instance_id'] = ports.session['session_id']
    await ports.bind_composition(composition, bindings, operator)
    return store, owner, protected, composition, ports, actor, status, prompts, bindings, operator


def effect_counts(store):
    return {kind: len(list(store.iter_records(kinds=(kind,)))) for kind in
        ('model-call-start', 'dispatch-start', 'gate-decision', 'acceptance-commit')}


@pytest.mark.asyncio
async def test_exact_native_finite_scope_can_be_ready_without_compiler_or_builder(tmp_path, monkeypatch):
    store, owner, protected, composition, ports, actor, status, prompts, bindings, operator = await finite_target(tmp_path, monkeypatch)
    try:
        before = effect_counts(store)
        report = await ports.readiness(actor)
        assert report['ready'] is True, report['prerequisites']
        assert report['evaluation_profile'] == owner._profile['profile_id']
        assert 'submit' in report['operations']
        assert report['pins']['plan_policy_ref'] == owner._binding['policy_ref']
        assert not any(row['name'] == 'builder' and row['status'] == 'ready' for row in report['prerequisites'])
        assert status['builder_qualified'] is False and prompts == [] and effect_counts(store) == before
    finally:
        await ports.close(); store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('lost', ['model', 'trajectory', 'isolation'])
async def test_finite_scope_keeps_every_actual_mandatory_probe(tmp_path, monkeypatch, lost):
    store, owner, protected, composition, ports, actor, status, prompts, bindings, operator = await finite_target(tmp_path, monkeypatch)
    try:
        if lost == 'model': status['state'] = 'unavailable'
        elif lost == 'trajectory': status['capture_healthy'] = False
        else: ports.executor = SimpleNamespace(prerequisites=lambda: {'ready': False})
        before = effect_counts(store)
        report = await ports.readiness(actor)
        assert report['ready'] is False and 'submit' not in report['operations']
        assert next(row for row in report['prerequisites'] if row['name'] == lost)['status'] == 'unavailable'
        assert prompts == [] and effect_counts(store) == before
    finally:
        await ports.close(); store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['missing_owner', 'marker', 'binding', 'model_port', 'model_swap', 'checking', 'factory', 'workspace'])
async def test_finite_readiness_requires_original_owner_binding_and_eligibility(tmp_path, monkeypatch, fault):
    store, owner, protected, composition, ports, actor, status, prompts, bindings, operator = await finite_target(tmp_path, monkeypatch)
    try:
        status['builder_qualified'] = True
        if fault == 'missing_owner': composition.service.finite_e1 = None
        elif fault == 'marker':
            composition.service.finite_e1 = SimpleNamespace(binding_ref=owner.binding_ref, invalid_for_product=True)
        elif fault == 'binding':
            ports.bindings['protected_options']['finite_e1_binding_ref'] = store.put_blob(b'foreign protected binding')
        elif fault == 'model_port': composition.runner.model = None
        elif fault == 'model_swap':
            replacement = object()
            composition.runner.model = replacement
            composition.service.model = replacement
        elif fault == 'factory': composition.scheduler.factory = SimpleNamespace()
        elif fault == 'workspace':
            composition.service._workspaces[('owner', 'work')]['resource_inventory_ref'] = store.put_blob(b'foreign protected inventory')
        else:
            def blocked(*args, **kwargs):
                raise ResearchError('check_assets_unqualified', 'Controlled loss of independent checking qualification')
            monkeypatch.setattr(owner.library, 'eligible_association', blocked)
        before = effect_counts(store)
        try:
            report = await ports.readiness(actor)
        except ResearchError:
            report = None
        assert report is None or report['ready'] is False and 'submit' not in report['operations']
        assert prompts == [] and effect_counts(store) == before
    finally:
        await ports.close(); store.close()


@pytest.mark.asyncio
async def test_actual_gateway_attachment_preserves_exact_finite_readiness(tmp_path, monkeypatch):
    from jiuwenswarm.research import bootstrap_gateway as gateway
    store, owner, protected, composition, ports, actor, status, prompts, bindings, operator = await finite_target(tmp_path, monkeypatch)
    attachment = None
    try:
        binding_ref = store.append_record('bootstrap-binding', bindings)
        configuration = tmp_path / 'operator.yaml'
        configuration.write_text('controlled-loader-fixture: true\n'); configuration.chmod(0o600)
        locator = tmp_path / 'binding.json'
        locator.write_text(json.dumps({'binding_ref': binding_ref})); locator.chmod(0o600)
        accounts_root = tmp_path / 'accounts'
        accounts = gateway.AccountStore(accounts_root); accounts.primary()
        accounts.db.execute('UPDATE accounts SET account_id=? WHERE slot=?', ('owner', 'primary'))
        accounts.db.commit(); accounts.close()
        handoff = tmp_path / 'handoff'; handoff.mkdir(mode=0o700)
        for name, value in {'JIUWENSWARM_M1_STATE': str(tmp_path / 'state'),
            'JIUWENSWARM_M1_ACCOUNTS': str(accounts_root), 'JIUWENSWARM_M1_CONFIG': str(configuration),
            'JIUWENSWARM_M1_ORIGIN': 'http://testserver',
            'JIUWENSWARM_M1_BOOTSTRAP_BINDINGS': str(locator)}.items(): monkeypatch.setenv(name, value)
        monkeypatch.delenv('JIUWENSWARM_M1_RSI_INBOX', raising=False)
        monkeypatch.setattr(gateway, 'M1_REFUSAL_REASON', None)
        monkeypatch.setattr(gateway, 'BOOTSTRAP_HANDOFF', handoff / 'browser-bootstrap.json')
        monkeypatch.setattr(gateway, 'SQLiteRunStore', lambda *args, **kwargs: store)
        monkeypatch.setattr(gateway.OperatorConfiguration, 'load', lambda *args, **kwargs: operator)
        # The real compose_core runs again inside attach; only Library eligibility
        # and remote process/probe responses are controlled by finite_target.
        before = effect_counts(store)
        channel = SimpleNamespace()
        attachment = await gateway.attach_native_research(channel, runtime_ports=ports)
        assert not attachment.diagnostics, attachment.diagnostics
        token = attachment.authority.token_path.read_text(encoding='ascii')
        authenticated = attachment.authority.authenticate('Bearer ' + token, 'readiness')
        report = await attachment.service.readiness(authenticated)
        assert report['ready'] is True, report['prerequisites']
        assert attachment.composition.compiler is None and attachment.composition.scheduler is not None
        assert attachment.service.finite_e1.binding_ref == owner.binding_ref
        assert report['evaluation_profile'] == owner._profile['profile_id']
        assert not prompts and effect_counts(store) == before
    finally:
        await ports.close()
        if attachment is not None: attachment.close()
        else: store.close()
