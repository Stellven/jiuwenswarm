"""Operator metadata/disclosure controls; no live admission or model claims."""
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

REQUEST = 'Inspect the authorized helper and propose one bounded improvement.'

SCRIPTS = Path(__file__).parents[3] / 'deploy/m1'
sys.path.insert(0, str(SCRIPTS))
try:
    spec = importlib.util.spec_from_file_location('controller_setup_test', SCRIPTS / 'rsi_controller_setup.py')
    setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
finally:
    sys.path.pop(0)


def public_fixture(tmp_path):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    from jiuwenswarm.research_rsi.process_policy import POLICY
    import jiuwenswarm.research_rsi as package
    fixture = make_unit_package(tmp_path)
    core = fixture['store']; put = lambda value: core.put_blob(setup.encoded(value))
    target = copy.deepcopy(core.read_record(fixture['session']['target_profile_ref']))
    asset = __import__('jiuwenswarm.research.capsules.assets', fromlist=['build_research_assets']).build_research_assets(core)['screening']
    parent = core.read_record(asset['declaration_ref'])
    public_refs = [asset['declaration_ref'], *asset['body_refs'].values()]
    cases = [{'id': 'development-' + str(index), 'inputs': {'scores': [{'idea_id': 'idea-' + str(index),
        'novelty': 1, 'feasibility': 2, 'compute_alignment': 3, 'eligible': True}]},
        'expected': {'selected_idea_id': 'idea-' + str(index), 'ranking': []}} for index in range(12)]
    export = {'schema': 'ai4r-rsi-visible-ranking-cases:1', 'parent_ref': target['parent_ref'], 'cases': cases}
    export_ref = put(export); public_refs.append(export_ref)
    sources = {name: core.put_blob((Path(package.__file__).parent / name).read_bytes()) for name in setup.SOURCE_PATHS}
    public_refs.extend(sources.values())
    tests = []; mandatory = []
    for row in cases:
        inputs = put(row['inputs']); expected = put(row['expected'])
        test = put({'schema': 'ai4r-rsi-frozen-helper-test:1', 'target_kind': 'ranking-v1',
            'parent_ref': target['parent_ref'], 'input_ref': inputs, 'expected_ref': expected,
            'development_export_ref': export_ref, 'source_refs': sources, 'execution_performed': False, 'case_id': row['id']})
        public_refs.extend([inputs, expected, test]); tests.append(test); mandatory.append({'input_ref': inputs, 'test_ref': test})
    target['required_test_refs'] = tests
    target_ref = put(target); public_refs.append(target_ref)
    session = copy.deepcopy(fixture['session'])
    session.update(target_profile_ref=target_ref, started_by='unit:owner', pass_count_repeats=1)
    session['limits'].update(max_attempts=1, per_call_s=120)
    session_ref = put(session); public_refs.append(session_ref)
    unit = session['configuration_ref']
    worker_ref = put({'schema': 'ai4r-rsi-worker-profile:3', 'target_kind': 'ranking-v1',
        'session_ref': session_ref, 'target_ref': target_ref, 'parent_ref': target['parent_ref'],
        'contract_ref': unit, 'environment_ref': unit, 'hardware_ref': unit,
        'memory_mb': 256, 'pids_max': 32, 'timeout_s': 1, 'process_policy': POLICY})
    public_refs.append(worker_ref)
    visible_ref = put({'context': export, 'mandatory_fixtures': mandatory, 'required_test_refs': tests}); public_refs.append(visible_ref)
    source_ref = put({'schema': 'ai4r-rsi-parent-source-export:1', 'status': 'NOT_ADMISSION', 'stage': 'screening',
        'configuration_ref': unit, 'installed_source_sha256': 'a' * 64, 'parent_declaration_ref': asset['declaration_ref'],
        'parent_body_refs': {row['path']: asset['body_refs'][row['path']] for row in parent['identity']['body']},
        'external_refs': {'_common.py': asset['body_refs']['_common.py']}})
    value = {'account_id': 'unit:owner', 'configuration_ref': unit, 'model_selection_profile_ref': unit,
             'deployment_ref': unit, 'installed_source_sha256': 'a' * 64}
    grant = {'schema': 'ai4r-rsi-controller-assembly-approval:1', 'action_id': 'unit-source-assembly',
        'operations': ['ingest', 'upload', 'prepare_controller'], 'request_text': REQUEST,
        'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        **{key: value[key] for key in ('account_id', 'configuration_ref', 'model_selection_profile_ref', 'deployment_ref')},
        'source_export_ref': source_ref, 'session_ref': session_ref, 'target_profile_ref': target_ref,
        'worker_profile_ref': worker_ref, 'visible_context_ref': visible_ref,
        'public_original_refs': list({setup.encoded(pin): pin for pin in public_refs}.values())}
    class Public:
        def __init__(self): self.reads = []
        def read(self, pin): self.reads.append(pin); return core.read_blob(pin)
        def get(self, pin): return json.loads(self.read(pin))
    return core, value, grant, Public()


@pytest.mark.parametrize('fault', ['owner', 'extra', 'text', 'expired', 'operations'])
def test_authorization_is_bound_to_actual_owner_request_and_finite_operations(tmp_path, monkeypatch, fault):
    core, value, grant, _ = public_fixture(tmp_path)
    try:
        monkeypatch.setattr(setup.bootstrap, 'protected_json', lambda *args, **kwargs: grant)
        assert setup.authorized(value) == grant
        if fault == 'owner': grant['account_id'] = 'foreign-owner'
        elif fault == 'extra': grant['provider_api_key'] = 'forbidden-field'
        elif fault == 'text': grant['request_text'] = '   '
        elif fault == 'expired': grant['expires_at'] = '2000-01-01T00:00:00Z'
        else: grant['operations'] += ['library_admit']
        with pytest.raises(ValueError): setup.authorized(value)
    finally: core.close()


def test_public_metadata_projection_never_walks_private_target_pointers(tmp_path):
    core, value, grant, public = public_fixture(tmp_path)
    try:
        raw, source, session = setup.public_context(public, value, grant)
        document = json.loads(raw)
        assert document['session_ref'] == grant['session_ref']
        assert len(document['originals']) == len(grant['public_original_refs'])
        target = core.read_record(grant['target_profile_ref'])
        assert target['calibration_ref'] not in public.reads
        assert session['chain_root_ref'] not in public.reads
        assert not list(core.iter_records(kinds=('model-call-start', 'library-admission', 'acceptance-commit')))
    finally: core.close()


def test_unapproved_or_private_or_missing_development_context_is_refused(tmp_path):
    core, value, grant, public = public_fixture(tmp_path)
    try:
        missing = copy.deepcopy(grant); missing['public_original_refs'].remove(grant['visible_context_ref'])
        with pytest.raises(ValueError): setup.public_context(public, value, missing)
        assert grant['visible_context_ref'] not in public.reads
        private = core.put_blob(b'{"schema":"ai4r-rsi-fixtures:1","hidden":"unit canary"}')
        widened = copy.deepcopy(grant); widened['public_original_refs'].append(private)
        with pytest.raises(ValueError): setup.public_context(public, value, widened)
        assert private not in public.reads  # Orphans are never followed, even if approved accidentally.
    finally: core.close()


def test_actual_upload_intake_gives_direct_source_capabilities_without_acceptance(tmp_path, monkeypatch):
    from jiuwenswarm.research.contracts import Principal, ResearchError
    from jiuwenswarm.research.runner import CapsuleArtifacts, refs_in
    core, value, grant, public = public_fixture(tmp_path)
    monkeypatch.setattr(setup.bootstrap, 'ROOT', tmp_path)
    try:
        document, source, _ = setup.public_context(public, value, grant)
        actor = Principal(value['account_id'], frozenset({'local'}), frozenset({'upload', 'ingest'}))
        options = {key: value['configuration_ref'] for key in ('profile_ref', 'workspace_ref', 'input_directory_ref')}
        intake_ref, uploaded = asyncio.run(setup.capture_intake(core, actor, options, document, REQUEST))
        intake = core.read_record(intake_ref, contract_id='qualified-intake')
        assert core.read_blob(intake['request_ref']).decode() == REQUEST
        artifacts = CapsuleArtifacts(core, [intake_ref, *refs_in(intake)], scope={})
        # Parent/helper bytes are an actual direct qualified source document,
        # not an unrelated source fetched outside the invocation's capability.
        helper = source['parent_body_refs']['ranking_parent.txt']
        assert artifacts.read_blob(helper) == core.read_blob(helper)
        unrelated = core.put_blob(b'UNAUTHORIZED_HIDDEN_CANARY')
        with pytest.raises(ResearchError, match='artifact_scope'): artifacts.read_blob(unrelated)
        assert all(row['user_id'] == value['account_id'] and row['scope_id'] == 'local' for row in uploaded)
        assert not list(core.iter_records(kinds=('model-call-start', 'library-admission', 'gate-decision', 'acceptance-commit')))
    finally: core.close()
