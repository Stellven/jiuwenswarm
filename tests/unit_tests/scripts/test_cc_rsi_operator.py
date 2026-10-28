"""Native-auth/Root-proof contract tests with synthetic terminal callbacks only."""
import asyncio
import ast
import base64
import copy
import hashlib
import importlib.util
import json
import sqlite3
import threading
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
spec = importlib.util.spec_from_file_location('unit_cc_operator_publisher', ROOT / 'deploy/m1/rsi_ui_publish.py')
publisher = importlib.util.module_from_spec(spec); spec.loader.exec_module(publisher)
from _ai4r_cc_ui_publish.cc_rsi_operator import NativeCcOperatorAdapter, RootOperatorEngine, RootOperatorJournal
from _ai4r_cc_ui_publish.cc_rsi_projection import ProjectionError
from _ai4r_cc_ui_publish.cc_rsi_broker import PROTOCOL


@pytest.fixture
def native_operator(tmp_path):
    from jiuwenswarm.research.shell_auth import SessionAuthority
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research_rsi.signing import Signer
    authority = SessionAuthority(tmp_path / 'synthetic-native-auth', 'http://127.0.0.1:5175')
    bootstrap = authority.initialize(Principal('unit:human', frozenset({'local'}), frozenset({'status'})))
    grant = authority.bootstrap(bootstrap.split('research_bootstrap=')[1], origin=authority.origin, host=authority.host)
    headers = {'origin': authority.origin, 'host': authority.host, 'cookie': grant['set_cookie'].split(';')[0]}
    signer = Signer.generate('unit:gateway')
    ref = {'id': 'unit-request', 'sha256': 'b' * 64}; digest = 'a' * 64
    policy = {'schema': 'ai4r-cc-rsi-root-operator-policy:1', 'revision': 'synthetic-unit-only', 'origin': authority.origin,
        'gateway_key_id': 'unit:gateway', 'operators': {'unit:human': ['admit']},
        'candidates': {digest: {'node_id': 'unit-node', 'admit_request_ref': ref, 'activate_request_ref': None}}}
    class SyntheticJournal:
        def __init__(self): self.values = {}
        def lookup(self, key): return self.values.get(key)
        def claim(self, key, record):
            assert key not in self.values
            self.values[key] = {'claim': record}
        def complete(self, key, record): return {'id': 'synthetic-human-receipt', 'sha256': hashlib.sha256(json.dumps(record).encode()).hexdigest()}
        def acknowledge(self, key, receipt): self.values[key]['receipt'] = receipt
    journal = SyntheticJournal(); effects = []; assertions = []
    def terminal(command, request_ref):
        effects.append((command, request_ref))
        return {'request_ref': ref, 'candidate_hash': digest, 'status': 'admitted_inactive', 'operator_receipt_ref': ref}
    engine = RootOperatorEngine(policy, signer.public_bytes(), journal, lambda *args: True, terminal, clock=lambda: 1000)
    class SyntheticClient:
        def execute(self, action, node, candidate_hash, authorization):
            request = {'protocol': PROTOCOL, 'action': action, 'node_id': node, 'candidate_hash': candidate_hash,
                'authorization': {'actor': authorization.actor, 'action_id': authorization.action_id, 'proof': authorization.proof}}
            assertions.append(request)
            return engine.handle(request)
    adapter = NativeCcOperatorAdapter(authority, signer, SyntheticClient(), policy['operators'], clock=lambda: 1000)
    try: yield authority, adapter, headers, engine, journal, effects, assertions
    finally: authority.close()


def test_native_session_identity_proof_and_root_exact_grant_execute_once(native_operator):
    authority, adapter, headers, engine, journal, effects, assertions = native_operator
    params = {'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': 'a' * 64}
    receipt = asyncio.run(adapter.execute(headers, params))
    assert receipt['actor'] == 'unit:human'
    assert asyncio.run(adapter.execute(headers, params)) == receipt
    assert len(effects) == 1
    # The native principal still has status only. No Library role is granted.
    assert authority.authenticate_ws(headers, 'status').operations == frozenset({'status'})


def test_forged_actor_revoked_session_and_ungranted_activation_fail(native_operator):
    from jiuwenswarm.research.contracts import ResearchError
    authority, adapter, headers, engine, journal, effects, assertions = native_operator
    params = {'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': 'a' * 64}
    with pytest.raises(ResearchError): asyncio.run(adapter.execute(headers, dict(params, actor='os:0:root')))
    with pytest.raises(ResearchError): asyncio.run(adapter.execute(headers, dict(params, action='activate')))
    authority.revoke(authority.token_path.read_text())
    with pytest.raises(ResearchError): asyncio.run(adapter.execute(headers, params))
    assert effects == []


def test_tampered_and_expired_proofs_and_unresolved_delivery_never_replay(native_operator):
    authority, adapter, headers, engine, journal, effects, assertions = native_operator
    params = {'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': 'a' * 64}
    asyncio.run(adapter.execute(headers, params))
    request = copy.deepcopy(assertions[0]); request['candidate_hash'] = 'c' * 64
    with pytest.raises(ProjectionError): engine.handle(request)
    engine.clock = lambda: 1031
    with pytest.raises(ProjectionError): engine.handle(assertions[0])
    engine.clock = lambda: 1000
    next(iter(journal.values.values())).pop('receipt')
    with pytest.raises(ProjectionError): engine.handle(assertions[0])
    assert len(effects) == 1


@pytest.mark.parametrize('unknown', [True, False])
def test_policy_revision_preserves_prior_claim_and_terminal_identity(native_operator, unknown):
    authority, adapter, headers, engine, journal, effects, assertions = native_operator
    params = {'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': 'a' * 64}
    original = asyncio.run(adapter.execute(headers, params))
    if unknown:
        next(iter(journal.values.values())).pop('receipt')
    updated_policy = copy.deepcopy(engine.policy)
    updated_policy['revision'] = 'synthetic-unit-only-next-revision'
    def forbidden(*args):
        pytest.fail('A retained prior claim must resolve before preflight or another Library dispatch')
    revised = RootOperatorEngine(updated_policy, engine.public_key, journal, forbidden, forbidden, clock=lambda: 1000)
    if unknown:
        with pytest.raises(ProjectionError, match='unresolved'):
            revised.handle(assertions[0])
    else:
        assert revised.handle(assertions[0]) == original
    assert len(effects) == 1
    assert len(journal.values) == 1


@pytest.mark.parametrize('unknown', [True, False])
def test_other_authorized_actor_cannot_repeat_issued_candidate_action(native_operator, unknown):
    authority, adapter, headers, engine, journal, effects, assertions = native_operator
    params = {'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': 'a' * 64}
    original = asyncio.run(adapter.execute(headers, params))
    if unknown:
        next(iter(journal.values.values())).pop('receipt')
    changed_policy = copy.deepcopy(engine.policy)
    changed_policy['revision'] = 'synthetic-new-operator-enrollment'
    changed_policy['operators']['unit:second-human'] = ['admit']
    def forbidden(*args): pytest.fail('Another operator cannot preflight or dispatch an issued candidate action')
    second = RootOperatorEngine(changed_policy, engine.public_key, journal, forbidden, forbidden, clock=lambda: 1000)
    request = copy.deepcopy(assertions[0])
    assertion = json.loads(base64.urlsafe_b64decode(request['authorization']['proof']))
    assertion.update(actor='unit:second-human', action_id='synthetic-second-human-action')
    assertion = adapter.signer.sign(assertion)
    request['authorization'] = {'actor': assertion['actor'], 'action_id': assertion['action_id'],
        'proof': base64.urlsafe_b64encode(json.dumps(assertion).encode()).decode()}
    with pytest.raises(ProjectionError, match='unresolved' if unknown else 'already handled'):
        second.handle(request)
    stored = next(iter(journal.values.values()))
    assert stored['claim']['actor'] == original['actor'] == 'unit:human'
    if not unknown: assert stored['receipt'] == original
    assert len(effects) == len(journal.values) == 1


@pytest.mark.parametrize('unknown', [True, False])
def test_changed_root_request_mapping_blocks_even_known_terminal(native_operator, unknown):
    authority, adapter, headers, engine, journal, effects, assertions = native_operator
    params = {'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': 'a' * 64}
    original = asyncio.run(adapter.execute(headers, params))
    if unknown: next(iter(journal.values.values())).pop('receipt')
    changed_policy = copy.deepcopy(engine.policy)
    changed_policy['revision'] = 'synthetic-changed-request'
    changed_policy['candidates']['a' * 64]['admit_request_ref'] = {'id': 'different-immutable-request', 'sha256': 'c' * 64}
    def forbidden(*args): pytest.fail('A changed request cannot preflight, dispatch or acknowledge the original action')
    revised = RootOperatorEngine(changed_policy, engine.public_key, journal, forbidden, forbidden, clock=lambda: 1000)
    with pytest.raises(ProjectionError, match='request mapping changed'):
        revised.handle(assertions[0])
    stored = next(iter(journal.values.values()))
    assert stored['claim']['request_ref']['id'] == 'unit-request'
    if not unknown: assert stored['receipt'] == original
    assert len(effects) == len(journal.values) == 1


def test_sqlite_journal_preserves_claim_metadata_and_receipt_across_reopen(tmp_path):
    # Exercise actual journal SQL/storage methods on an isolated synthetic DB.
    # The OS Root custody constructor and real runtime paths are never entered.
    path = tmp_path / 'synthetic-operator-journal.sqlite'
    def open_storage():
        journal = RootOperatorJournal.__new__(RootOperatorJournal)
        journal.db = sqlite3.connect(path, isolation_level=None)
        journal.lock = threading.RLock()
        journal.db.execute('CREATE TABLE IF NOT EXISTS actions (identity TEXT PRIMARY KEY, claim TEXT NOT NULL, receipt TEXT)')
        return journal
    journal = open_storage()
    claim = {'actor': 'unit:human', 'action': 'admit', 'candidate_hash': 'a' * 64,
        'action_id': 'synthetic-action', 'request_ref': {'id': 'unit-request', 'sha256': 'b' * 64}}
    receipt = {'actor': claim['actor'], 'action': 'admit', 'candidate_hash': claim['candidate_hash'],
        'node_id': 'unit-node', 'receipt_ref': {'id': 'unit-receipt', 'sha256': 'c' * 64}}
    try:
        assert journal.lookup('synthetic-global-identity') is None
        journal.claim('synthetic-global-identity', claim)
        assert journal.lookup('synthetic-global-identity') == {'claim': claim, 'receipt': None}
        with pytest.raises(ProjectionError): journal.claim('synthetic-global-identity', dict(claim, actor='unit:second-human'))
        journal.close(); journal = open_storage()
        assert journal.lookup('synthetic-global-identity')['claim'] == claim
        journal.acknowledge('synthetic-global-identity', receipt)
        journal.close(); journal = open_storage()
        assert journal.lookup('synthetic-global-identity') == {'claim': claim, 'receipt': receipt}
    finally: journal.close()


def test_native_gateway_forwards_read_only_cc_and_requires_installed_proof_adapter(native_operator):
    from jiuwenswarm.research.contracts import ResearchError
    # Execute the actual WS routing functions without importing unrelated HTTP
    # framework/WebChannel initialization; this dependency-light environment
    # does not install FastAPI or the legacy WebSocket channel dependencies.
    source = ast.parse((ROOT / 'jiuwenswarm/gateway/channel_manager/web/research_http.py').read_text(encoding='utf8'))
    functions = [node for node in source.body if isinstance(node, ast.AsyncFunctionDef) and node.name in {'_result', 'native_research_message'}]
    namespace = {'asyncio': asyncio, 'ResearchError': ResearchError, 'inspect': __import__('inspect'), 'os': __import__('os')}
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'native-research-message-boundary', 'exec'), namespace)
    native_research_message = namespace['native_research_message']
    authority, adapter, headers, engine, journal, effects, assertions = native_operator
    channel = SimpleNamespace(research_authority=authority, research_service=object(), research_refusal_reason='blocked calibration')
    ws = SimpleNamespace(request_headers=headers)
    for method in ('rsi.cc.snapshot', 'rsi.cc.candidate.get'):
        assert asyncio.run(native_research_message(channel, ws, method, {})) == (False, None)
    assert ws.authenticated_user_id == 'unit:human'
    params = {'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': 'a' * 64}
    with pytest.raises(ResearchError): asyncio.run(native_research_message(channel, ws, 'rsi.cc.operator.action', params))
    channel.research_cc_operator = adapter
    handled, receipt = asyncio.run(native_research_message(channel, ws, 'rsi.cc.operator.action', params))
    assert handled and receipt['actor'] == 'unit:human'
    with pytest.raises(ResearchError): asyncio.run(native_research_message(channel, ws, 'rsi.cc.run.start', {}))
    authority.revoke(authority.token_path.read_text())
    with pytest.raises(ResearchError): asyncio.run(native_research_message(channel, ws, 'rsi.cc.snapshot', {}))
