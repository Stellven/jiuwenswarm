"""Native authentication and signatures across independently consumed slots."""
import asyncio
import copy
import hashlib
import pytest
from jiuwenswarm.research.cc_ui_runtime import module

cap = module('cc_rsi_capsule')
old = module('cc_rsi_development')


@pytest.fixture
def prepared(tmp_path):
    from jiuwenswarm.research.shell_auth import SessionAuthority
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research_rsi.signing import Signer
    authority = SessionAuthority(tmp_path/'native', 'http://127.0.0.1:5175')
    token = authority.initialize(Principal('unit:human', frozenset({'local'}), frozenset({'status'})))
    grant = authority.bootstrap(token.split('research_bootstrap=')[1], origin=authority.origin, host=authority.host)
    headers = {'origin':authority.origin,'host':authority.host,'cookie':grant['set_cookie'].split(';')[0]}
    signer = Signer.generate('unit:key')
    policy = {'schema':cap.POLICY,'workspace_id':'local','origin':authority.origin,
        'actors':['unit:human'],'gateway_key_id':'unit:key','slots':[
            {'target_id':'utility.calculate','revision':'a'*64,'run_id':'unit-calculate'},
            {'target_id':'utility.table_normalize','revision':'b'*64,'run_id':'unit-normalize'}]}
    class Journal:
        value = None
        def lookup(self): return self.value
        def claim(self, identity, assertion): self.value = {'identity':copy.deepcopy(identity),'assertion':assertion}
        def accept(self, record): return {'id':'unit:receipt','sha256':hashlib.sha256(old.encoded(record)).hexdigest()}
        def acknowledge(self, ack): self.value['ack'] = ack
    launches = []; journals = {row['target_id']:Journal() for row in policy['slots']}
    slots = {key:(journal, lambda:None, lambda key=key: launches.append(key) or {'unit':True}) for key,journal in journals.items()}
    engine = cap.RootCapsuleEngine(policy, signer.public_bytes(), slots)
    class Client:
        def status(self): return engine.handle({'protocol':cap.PROTOCOL,'operation':'status'})
        def start(self, params, assertion):
            return engine.handle({'protocol':cap.PROTOCOL,'operation':'start','params':params,'assertion':assertion})
    adapter = cap.NativeCapsuleAdapter(authority, signer, Client(), policy)
    yield locals()
    authority.close()


def test_each_target_exactly_once_and_other_publication_revision_does_not_revoke(prepared):
    v = prepared
    base = {'revision':'c'*64,'targets':[{'id':row['target_id'],'run':{}} for row in v['policy']['slots']]}
    before = asyncio.run(v['adapter'].snapshot(v['headers'], {}, base=base))
    assert [r['run']['revision'] for r in before['targets']] == ['a'*64,'b'*64]
    params = {'target_id':'utility.calculate','revision':'a'*64,'client_request_id':'unit-click-1'}
    ack = asyncio.run(v['adapter'].execute(v['headers'],params))
    assert ack == asyncio.run(v['adapter'].execute(v['headers'],params))
    base['revision'] = 'd'*64
    after = asyncio.run(v['adapter'].snapshot(v['headers'], {}, base=base))
    assert not after['targets'][0]['run']['allowed']
    assert after['targets'][1]['run']['allowed'] and after['targets'][1]['run']['revision'] == 'b'*64
    asyncio.run(v['adapter'].execute(v['headers'],{'target_id':'utility.table_normalize','revision':'b'*64,'client_request_id':'unit-click-2'}))
    assert v['launches'] == ['utility.calculate','utility.table_normalize']


@pytest.mark.parametrize('extra',[{'actor':'root'},{'path':'/tmp/run'},{'budget':99},{'model':'foreign'}])
def test_no_browser_authority_or_executable(prepared,extra):
    v=prepared
    with pytest.raises(ValueError):
        asyncio.run(v['adapter'].execute(v['headers'],{'target_id':'utility.calculate','revision':'a'*64,'client_request_id':'unit-click',**extra}))
    assert v['launches'] == []


def test_foreign_revision_and_unauthenticated_session_blocked(prepared):
    v=prepared
    params={'target_id':'utility.calculate','revision':'b'*64,'client_request_id':'unit-click'}
    with pytest.raises(ValueError): asyncio.run(v['adapter'].execute(v['headers'],params))
    with pytest.raises(Exception): asyncio.run(v['adapter'].execute({},dict(params,revision='a'*64)))
    assert v['launches'] == []


def test_prepared_policy_finite_and_builder_not_falsely_executable(prepared):
    value=copy.deepcopy(prepared['policy']); value['slots'][0]['target_id']='research.builder'
    with pytest.raises(ValueError): cap.policy(value)


def test_unresolved_slot_claim_never_replays_and_does_not_consume_other_slot(prepared):
    v=prepared
    def fail(): raise OSError('Synthetic failure after durable claim')
    v['engine'].engines['utility.calculate'].launch = fail
    params={'target_id':'utility.calculate','revision':'a'*64,'client_request_id':'unit-click'}
    with pytest.raises(OSError): asyncio.run(v['adapter'].execute(v['headers'],params))
    with pytest.raises(ValueError): asyncio.run(v['adapter'].execute(v['headers'],params))
    rows=asyncio.run(v['adapter'].readiness(v['headers']))
    assert not rows['utility.calculate']['run']['allowed']
    assert rows['utility.table_normalize']['run']['allowed']
    assert v['journals']['utility.calculate'].value['identity']['client_request_id']=='unit-click'


def test_native_catalog_exposes_only_broker_prepared_revision(prepared, tmp_path):
    import ast
    import inspect
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from jiuwenswarm.research.contracts import ResearchError
    v=prepared
    source=Path(__file__).parents[3]/'jiuwenswarm/gateway/channel_manager/web/research_http.py'
    functions=[n for n in ast.parse(source.read_text(encoding='utf8')).body
        if isinstance(n,ast.AsyncFunctionDef) and n.name in ('_result','native_research_message')]
    ns={'ResearchError':ResearchError,'inspect':inspect,'os':os}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),ns)
    channel=SimpleNamespace(research_authority=v['authority'],research_service=None,
        research_cc_workspace='local',research_cc_capsules=v['adapter'])
    async def call(method,params):
        return await ns['native_research_message'](channel,SimpleNamespace(request_headers=v['headers']),method,params)
    handled,result=asyncio.run(call('rsi.cc.targets.list',{}))
    assert handled
    rows={row['target_id']:row for row in result['targets']}
    assert rows['utility.calculate']['run']=={'allowed':True,'blocker':None,'revision':'a'*64,'phase':'READY'}
    assert rows['research.builder']['development_grant_status']=='NOT_ESTABLISHED'
    handled,ack=asyncio.run(call('rsi.cc.run.start',{'target_id':'utility.calculate','revision':'a'*64,'client_request_id':'unit-ui-click'}))
    assert handled and ack['run_id']=='unit-calculate'
    value=copy.deepcopy(prepared['policy']); value['slots'][0]['run_id']='../escape'
    with pytest.raises(ValueError): cap.policy(value)


def test_actual_launcher_terminal_status_reports_failure_and_keeps_slot_consumed():
    from deploy.m1.rsi_capsule_broker import terminal_status
    status={'target_id':'utility.calculate','revision':'a'*64,'run_id':'unit-calculate',
        'ready':False,'phase':'LAUNCHED','blocker':'An issued run cannot replay','security_status':'SECURITY_DEFERRED'}
    result=terminal_status(status,lambda name:{'pid':123,'wait_status':256,'recorded_unix':1000})
    assert result['ready'] is False and result['phase']=='LAUNCHED'
    assert 'failed with exit 1' in result['blocker']
    assert terminal_status(status,lambda name:None)==status


# --------------------------------------------------------------------------
# Durable development slots (policy v2, explicit ``mode``).
# --------------------------------------------------------------------------
import threading
from pathlib import Path


class MemoryJournal:
    """Append-only fake of the Root journal: every name is written once."""
    def __init__(self): self.files = {}
    def write(self, name, value):
        assert name not in self.files, 'journal entry rewritten: ' + name
        self.files[name] = copy.deepcopy(value)
        return {'id': 'unit:' + name, 'sha256': hashlib.sha256(old.encoded(value)).hexdigest()}
    def read(self, name): return copy.deepcopy(self.files.get(name))
    def lookup(self):
        claim = self.files.get('claim.json')
        return None if claim is None else {'identity': claim['identity'], 'ack': self.files.get('ack.json')}
    def claim(self, identity, assertion): self.write('claim.json', {'identity': identity, 'assertion': assertion})
    def accept(self, value): return self.write('launch.json', value)
    def acknowledge(self, value): self.write('ack.json', value)


def ledger_files(root):
    return {path.name: path.read_bytes() for path in Path(root).iterdir()}


def durable_policy(origin, slot_id='unit-calculate-dev', strict=True):
    slots = [{'target_id': 'utility.calculate', 'mode': 'durable', 'slot_id': slot_id}]
    if strict:
        slots.append({'target_id': 'utility.table_normalize', 'mode': 'strict', 'revision': 'b'*64, 'run_id': 'unit-normalize'})
    return {'schema': cap.POLICY_V2, 'workspace_id': 'local', 'origin': origin, 'actors': ['unit:human'],
            'gateway_key_id': 'unit:key', 'slots': slots}


@pytest.fixture
def durable(tmp_path, prepared):
    v = prepared
    policy = durable_policy(v['authority'].origin)
    now = [int(__import__("time").time())]; journals = {}; gates = {}; launches = []; observed = []; prepared_runs = []
    preflight_errors = {}

    def journal(run_id): return journals.setdefault(run_id, MemoryJournal())
    def prepare(sequence, run_id):
        if sequence in gates: assert gates[sequence].wait(10)
        prepared_runs.append(run_id)
        return {'configuration': {'path': '/unit/' + run_id + '/run.json', 'sha256': hashlib.sha256(run_id.encode()).hexdigest()},
                'expires_unix_s': now[0] + 7 * 24 * 3600, 'wall_s': 4020, 'max_executions': 19 * 18, 'model_calls': 0}
    def preflight(record):
        if record['run_id'] in preflight_errors: raise ValueError(preflight_errors[record['run_id']])
    holder = {}
    def launch(record, journal_):
        observed.append(holder['slot'].status()['phase'])  # Inside the claimed launch (same Root thread).
        launches.append(record['run_id'])
        return {'pid': 1, 'run_id': record['run_id']}
    ledger = cap.RevisionLedger(tmp_path / 'ledger')
    slot = holder['slot'] = cap.DurableSlot(policy, policy['slots'][0], v['signer'].public_bytes(), ledger, journal=journal,
        preflight=preflight, launch=launch, prepare=prepare, clock=lambda: now[0], launch_margin_s=300)
    strict = MemoryJournal()
    engine = cap.RootCapsuleEngine(policy, v['signer'].public_bytes(), {
        'utility.calculate': slot, 'utility.table_normalize': (strict, lambda: None, lambda: launches.append('strict') or {})})
    class Client:
        def status(self): return engine.handle({'protocol': cap.PROTOCOL, 'operation': 'status'})
        def start(self, params, assertion):
            return engine.handle({'protocol': cap.PROTOCOL, 'operation': 'start', 'params': params, 'assertion': assertion})
    adapter = cap.NativeCapsuleAdapter(v['authority'], v['signer'], Client(), policy)
    def settle():
        if slot.worker is not None: slot.worker[1].join(10)
    def gate(): return asyncio.run(adapter.readiness(v['headers']))['utility.calculate']
    yield dict(locals(), headers=v['headers'])


def test_durable_slot_lifecycle_reprepares_new_revision_without_reusing_claims(durable):
    d = durable; history = []
    def snap():
        files = ledger_files(d['ledger'].root)
        for earlier in history:  # Append-only: nothing rewritten or removed.
            assert all(files.get(name) == raw for name, raw in earlier.items())
        history.append(files)
    first = d['gate']()
    assert first['run']['phase'] in ('PREPARING', 'READY') and first['mode'] == 'durable'
    d['settle'](); ready = d['gate']()
    assert ready['run']['phase'] == 'READY' and ready['run']['allowed'] and ready['run_id'] == 'unit-calculate-dev-r1'
    revision = ready['revision']; assert ready['run']['revision'] == revision; snap()
    params = {'target_id': 'utility.calculate', 'revision': revision, 'client_request_id': 'unit-click-1'}
    ack = asyncio.run(d['adapter'].execute(d['headers'], params))
    assert ack['run_id'] == 'unit-calculate-dev-r1' and d['observed'] == ['CLAIMED']
    launched = d['gate']()
    assert launched['run']['phase'] == 'LAUNCHED' and not launched['run']['allowed'] and launched['revision'] == revision
    assert asyncio.run(d['adapter'].execute(d['headers'], params)) == ack  # Exact retry, never a second launch.
    with pytest.raises(ValueError):
        asyncio.run(d['adapter'].execute(d['headers'], dict(params, client_request_id='unit-click-other')))
    assert d['launches'] == ['unit-calculate-dev-r1']; snap()
    # Terminal run: the slot retires r1 and prepares r2 by itself.
    d['gates'][2] = threading.Event()
    d['journals']['unit-calculate-dev-r1'].write('launcher-exit.json', {'pid': 1, 'wait_status': 0})
    preparing = d['gate']()
    assert preparing['run']['phase'] == 'PREPARING' and preparing['revision'] is None and not preparing['run']['allowed']
    d['gates'][2].set(); d['settle']()
    again = d['gate']()
    assert again['run']['phase'] == 'READY' and again['run_id'] == 'unit-calculate-dev-r2' and again['revision'] != revision
    snap()
    rows = d['ledger'].entries()
    assert rows[1]['retired']['reason'] == 'LAUNCHER_EXITED' and rows[1]['retired']['exit_code'] == 0
    assert rows[2]['prepared']['sequence'] == 2 and rows[2]['prepared']['revision'] == again['revision']
    # The consumed revision stays consumed: a new click on it is refused, its
    # delivery retry returns only the retained acknowledgement.
    with pytest.raises(ValueError):
        asyncio.run(d['adapter'].execute(d['headers'], dict(params, client_request_id='unit-click-2')))
    second = {'target_id': 'utility.calculate', 'revision': again['revision'], 'client_request_id': 'unit-click-2'}
    ack2 = asyncio.run(d['adapter'].execute(d['headers'], second))
    assert ack2['run_id'] == 'unit-calculate-dev-r2' and ack2['receipt_ref'] != ack['receipt_ref']
    assert d['launches'] == ['unit-calculate-dev-r1', 'unit-calculate-dev-r2']
    old_journal = d['journals']['unit-calculate-dev-r1'].files
    assert old_journal['claim.json']['identity']['client_request_id'] == 'unit-click-1'
    assert set(old_journal) == {'claim.json', 'launch.json', 'ack.json', 'launcher-exit.json'}
    assert d['prepared_runs'] == ['unit-calculate-dev-r1', 'unit-calculate-dev-r2']; snap()
    # The strict slot is untouched by the durable slot's revisions.
    assert asyncio.run(d['adapter'].readiness(d['headers']))['utility.table_normalize']['run'] == {
        'allowed': True, 'blocker': None, 'revision': 'b'*64, 'phase': 'READY'}


def test_durable_snapshot_overlays_root_phase_and_blocked_reason(durable):
    d = durable; d['gate'](); d['settle']()
    record = d['slot'].current()
    d['preflight_errors'][record['run_id']] = 'SOURCE_CLOSURE_INCOMPLETE: missing jiuwenswarm/research/x.py'
    base = {'revision': 'c'*64, 'targets': [{'id': 'utility.calculate', 'run': {'allowed': False, 'blocker': None}}]}
    view = asyncio.run(d['adapter'].snapshot(d['headers'], {}, base=base))
    run = view['targets'][0]['run']
    assert run['phase'] == 'BLOCKED' and not run['allowed'] and 'SOURCE_CLOSURE_INCOMPLETE' in run['blocker']
    assert run['revision'] == record['revision']
    with pytest.raises(ValueError):
        asyncio.run(d['adapter'].execute(d['headers'], {'target_id': 'utility.calculate',
            'revision': record['revision'], 'client_request_id': 'unit-blocked'}))
    assert d['launches'] == []


def test_unclaimed_revision_is_refreshed_before_its_horizon_cannot_cover_a_run(durable):
    d = durable; d['gate'](); d['settle']()
    first = d['slot'].current()
    d['now'][0] = first['expires_unix_s'] - first['wall_s'] - 299  # Inside the launch margin.
    d['gate'](); d['settle']()
    rows = d['ledger'].entries()
    assert rows[1]['retired']['reason'] == 'GRANT_HORIZON_REFRESH_UNCLAIMED'
    current = d['slot'].current()
    assert current['sequence'] == 2 and current['expires_unix_s'] > first['expires_unix_s']
    with pytest.raises(ValueError):  # The retired, never-claimed revision can never run.
        asyncio.run(d['adapter'].execute(d['headers'], {'target_id': 'utility.calculate',
            'revision': first['revision'], 'client_request_id': 'unit-stale'}))
    assert d['launches'] == [] and d['journals']['unit-calculate-dev-r1'].files == {}


def test_failed_preparations_stop_at_bound_and_resume_appends_explicitly(tmp_path, prepared):
    v = prepared; policy = durable_policy(v['authority'].origin, 'unit-fail', strict=False)
    attempts = []
    def prepare(sequence, run_id):
        attempts.append(run_id)
        if len(attempts) <= 2: raise ValueError('PREPARATION_STEP_FAILED_NO_REPLAY: prepare')
        return {'expires_unix_s': 10**9, 'wall_s': 100}
    slot = cap.DurableSlot(policy, policy['slots'][0], v['signer'].public_bytes(), cap.RevisionLedger(tmp_path / 'l'),
        journal=lambda run_id: MemoryJournal(), preflight=lambda record: None, launch=None, prepare=prepare,
        clock=lambda: 1000, max_consecutive_failures=2, background=False)
    assert slot.status()['phase'] == 'PREPARING' and attempts == ['unit-fail-r1']  # A successor is still due.
    row = slot.status()
    assert row['phase'] == 'FAILED' and 'PREPARATION_STEP_FAILED' in row['blocker'] and attempts == ['unit-fail-r1', 'unit-fail-r2']
    assert slot.status()['phase'] == 'FAILED' and len(attempts) == 2  # Bounded: no silent retry loop.
    slot.resume()
    with pytest.raises(ValueError): slot.resume()
    row = slot.status()
    assert row['phase'] == 'READY' and row['run_id'] == 'unit-fail-r3' and attempts[-1] == 'unit-fail-r3'
    kinds = {seq: sorted(entry) for seq, entry in slot.ledger.entries().items()}
    assert kinds == {1: ['failed', 'preparing'], 2: ['failed', 'preparing', 'resumed'], 3: ['prepared', 'preparing']}


def test_interrupted_preparation_is_reconciled_never_reentered(tmp_path, prepared):
    v = prepared; policy = durable_policy(v['authority'].origin, 'unit-int', strict=False)
    ledger = cap.RevisionLedger(tmp_path / 'l')
    ledger.append(1, 'preparing', {'run_id': 'unit-int-r1', 'started_unix_s': 1})  # A broker died mid-preparation.
    calls = []
    slot = cap.DurableSlot(policy, policy['slots'][0], v['signer'].public_bytes(), ledger,
        journal=lambda run_id: MemoryJournal(), preflight=lambda record: None, launch=None,
        prepare=lambda sequence, run_id: calls.append(run_id) or {'expires_unix_s': 10**9, 'wall_s': 100},
        clock=lambda: 1000, background=False)
    assert slot.status()['run_id'] == 'unit-int-r2' and calls == ['unit-int-r2']
    assert ledger.entries()[1]['failed']['message'] == 'PREPARATION_INTERRUPTED_RECONCILE_WITHOUT_REPLAY'
    with pytest.raises(ValueError):
        ledger.append(1, 'failed', {})  # Entries are never replaced.


@pytest.mark.parametrize('change', ['missing-mode', 'unknown-mode', 'builder', 'unregistered', 'durable-revision'])
def test_policy_v2_requires_explicit_mode_and_registered_evaluated_capsule(prepared, change):
    value = durable_policy(prepared['authority'].origin, strict=False)
    slot = value['slots'][0]
    if change == 'missing-mode': slot.pop('mode')
    if change == 'unknown-mode': slot['mode'] = 'auto'
    if change == 'builder': slot['target_id'] = 'research.builder'
    if change == 'unregistered': slot['target_id'] = 'utility.unknown'
    if change == 'durable-revision': slot['revision'] = 'a'*64
    with pytest.raises(ValueError): cap.policy(value)
    ok = dict(value, slots=[{'target_id': 'utility.table_normalize', 'mode': 'durable', 'slot_id': 'unit-dev'}])
    assert cap.policy(ok) == ok


def test_status_rows_are_closed_per_mode(prepared):
    policy = durable_policy(prepared['authority'].origin, 'unit-dev', strict=False)
    slot = policy['slots'][0]
    row = {'target_id': 'utility.calculate', 'mode': 'durable', 'revision': 'a'*64, 'run_id': 'unit-dev-r3',
           'sequence': 3, 'ready': True, 'phase': 'READY', 'blocker': None, 'security_status': 'SECURITY_DEFERRED'}
    assert cap.validate_slot_status(row, policy, slot) == row
    for bad in ({'run_id': 'unit-dev-r4'}, {'phase': 'PREPARING'}, {'revision': None}, {'mode': 'strict'},
                {'phase': 'RUNNING', 'ready': False, 'blocker': 'x'}, {'ready': False, 'blocker': None, 'phase': 'BLOCKED'}):
        with pytest.raises(ValueError): cap.validate_slot_status(dict(row, **bad), policy, slot)
    preparing = dict(row, revision=None, run_id=None, sequence=None, ready=False, phase='PREPARING', blocker='Preparing')
    assert cap.validate_slot_status(preparing, policy, slot) == preparing
    with pytest.raises(ValueError): cap.validate_slot_status(dict(preparing, phase='LAUNCHED'), policy, slot)


def test_broker_accepts_package_closure_proof_and_derives_durable_terminal(tmp_path):
    from deploy.m1 import rsi_capsule_broker as broker
    reply = {'schema': broker.PREFLIGHT, 'ready': True, 'run_id': 'unit-r1', 'configuration_sha256': 'a'*64}
    assert broker.preflight_reply(dict(reply), 'unit-r1', 'a'*64) == reply  # Historical exact reply.
    proof = dict(reply, source_closure={'complete': True, 'module_count': 200}, worker_traversal='kernel', dispatcher='v18-bwrap')
    assert broker.preflight_reply(proof, 'unit-r1', 'a'*64) == proof
    for bad in (dict(proof, source_closure={'complete': False}), dict(reply, dispatcher='local'),
                dict(reply, ready=False), dict(reply, run_id='other'), dict(reply, extra=1)):
        with pytest.raises(ValueError): broker.preflight_reply(bad, 'unit-r1', 'a'*64)
    journal = MemoryJournal()
    assert broker.durable_terminal(journal, {}) is None  # Unclaimed.
    journal.claim({'actor': 'unit'}, {})
    assert broker.durable_terminal(journal, {}) == {'exit_code': None, 'reason': 'LAUNCH_FAILED_BEFORE_START'}
    journal.write('owner.json', {'pid': 7, 'start_ticks': 11, 'boot_id': 'boot'}); journal.acknowledge({'ack': True})
    assert broker.durable_terminal(journal, {}, alive=lambda owner: True) is None
    assert broker.durable_terminal(journal, {}, alive=lambda owner: False)['reason'] == 'LAUNCHER_EXIT_UNOBSERVED'
    journal.write('launcher-exit.json', {'pid': 7, 'wait_status': 512})
    assert broker.durable_terminal(journal, {}, alive=lambda owner: True) == {'exit_code': 2, 'reason': 'LAUNCHER_EXITED'}
    proc = tmp_path / 'proc'; (proc / '7').mkdir(parents=True); boot = tmp_path / 'boot'; boot.write_text('boot\n')
    (proc / '7/stat').write_text('7 (python3) S ' + ' '.join(['0'] * 18) + ' 11 0')
    owner = {'pid': 7, 'start_ticks': 11, 'boot_id': 'boot'}
    assert broker.process_alive(owner, proc=proc, boot=boot)
    assert not broker.process_alive(dict(owner, start_ticks=12), proc=proc, boot=boot)
    assert not broker.process_alive(dict(owner, boot_id='other'), proc=proc, boot=boot)
    assert not broker.process_alive(dict(owner, pid=8), proc=proc, boot=boot)
