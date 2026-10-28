"""Offline abandonment joins and crash guards; no operational recovery/model call."""
import copy
import importlib.util
import os
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_host_codex_recovery.py'
spec = importlib.util.spec_from_file_location('tested_host_recovery', SOURCE)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def specimen():
    h = lambda text: recovery.digest(text.encode())
    catalog = h('fixed catalog'); binding = h('same backend and subscription')
    evidence = {}
    policies = []
    for prefix in ('old', 'new'):
        sources = {key: h(prefix + ':' + key) for key in recovery.SOURCE_PATHS}
        sources['research/resources/host_codex/model_catalog.json'] = catalog
        request = dict(model='gpt-6.1-sol', reasoning_effort='medium', tools=[], additional_tools=[],
            tools_count=0, functions_count=0, recursive_tool_locations=[], actual_system_guard_present=True,
            exact_public_user_present=True, authorization_present=False, cookie_present=False, proxy_authorization_present=False)
        proof = dict(schema='ai4r-offline-native-tools-wire-proof:1', helper_source_sha256=sources['research/local_model_codex.py'],
            native_binary_sha256=h('same native binary'), real_auth_or_account_files_used=False,
            real_generation_performed=False, cases=[dict(real_provider_called=False, account_rpc_sent=False,
                resolved_model='gpt-6.1-sol', resolved_effort='medium', catalog_source_sha256=catalog, http_requests=[request])])
        evidence[prefix + '_no_tools_proof'] = recovery.encoded(proof)
        qualification = dict(schema='ai4r-rsi-host-codex-no-tools:1', native_version='0.163.0', model='gpt-6.1-sol',
            reasoning_effort='medium', helper_sha256=sources['research/local_model_codex.py'], model_catalog_sha256=catalog,
            binary_sha256=h('same native binary'), proof_sha256=recovery.digest(evidence[prefix + '_no_tools_proof']),
            tool_names=[], tools_count=0, functions_count=0, additional_tools_count=0)
        evidence[prefix + '_qualification'] = recovery.encoded(qualification)
        policy = dict(schema='ai4r-rsi-host-codex-policy:1', model='gpt-6.1-sol', reasoning_effort='medium',
            binding_sha256=binding, qualification_sha256=recovery.digest(evidence[prefix + '_qualification']), source_sha256=sources)
        policy['sha256'] = recovery.digest(recovery.encoded(policy)); policies.append(policy)
    old, new = policies
    profile = dict(schema='ai4r-rsi-host-codex:1', catalog={'same': 'fixed source'}, session={'private': 'retained local capability'},
        qualification=recovery.document(evidence['old_qualification']), policy_sha256=old['sha256'])
    evidence['old_profile'] = recovery.encoded(profile)
    cid = h('exact owned container')
    local = dict(schema='ai4r-rsi-cloud-native-host-cessation-observation:1', owned_container_id=cid,
        original_start={'owner_pid': 1, 'pid_namespace': 'pid:[123]'}, prior_pid_namespace='pid:[123]',
        identity_receipt={'container_id': cid}, matching_processes=[], matching_native_container_ids=[], process_scan_errors=[],
        lifecycle_events=[{'Action': action, 'Actor': {'ID': cid}} for action in ('create', 'start', 'die', 'destroy')],
        observed_at='2026-10-26T03:00:00Z')
    evidence['local_cessation'] = recovery.encoded(local)
    evidence['windows_cessation'] = recovery.encoded(dict(schema='ai4r-rsi-host-windows-scoped-process-observation:1',
        status='OBSERVED', owned_process_count=0, processes=[], remote_termination_inferred=False,
        observed_at_utc='2026-10-26T03:00:00Z'))
    evidence['authorization'] = recovery.encoded(dict(schema='ai4r-host-codex-recovery-authorization:1',
        actor='os:0:root', request_id='request-original', prior_policy_sha256=old['sha256'], successor_policy_sha256=new['sha256'],
        purpose=recovery.PURPOSE, authorization='Explicit controlled test authorization for a fresh bounded run; no terminal claim.',
        recorded_at='2026-10-26T03:01:00Z'))
    row = ('request-original', h('exact payload'), '{"outcome":"outcome_unknown","charge":1}')
    diagnostic = recovery.encoded(dict(schema='ai4r-backend-receipt:1', request_id=row[0], payload_sha256=row[1],
        backend_kind='host-codex-app-server', binding_sha256=binding))
    return dict(row=row, diagnostic_raw=diagnostic, evidence=evidence, prior_policy=old, successor_policy=new)


def test_review_preserves_unknown_exact_bytes_charge_and_private_session():
    args = specimen(); before = copy.deepcopy(args)
    result = recovery.build_review(**args)
    assert args == before
    receipt = result['receipt']; assert receipt['result_sha256'] == recovery.digest(args['row'][2].encode())
    assert receipt['original_outcome'] == 'outcome_unknown' and receipt['provider_termination'] == 'UNPROVEN'
    assert receipt['automatic_replay'] is False and receipt['prior_budget_preserved'] is True
    assert recovery.document(result['new_profile'])['session'] == recovery.document(args['evidence']['old_profile'])['session']
    assert result['review']['native_lease_released'] is False


@pytest.mark.parametrize('fault', ['null', 'completed', 'diagnostic', 'same_policy', 'cross_policy', 'tools', 'additional_tools',
    'binary', 'pid_namespace', 'wrong_container', 'live_windows', 'remote_claim', 'authorization', 'proof_bytes'])
def test_review_rejects_inexact_abandonment(fault):
    args = specimen()
    if fault == 'null': args['row'] = (*args['row'][:2], None)
    elif fault == 'completed': args['row'] = (*args['row'][:2], '{"outcome":"completed"}')
    elif fault == 'diagnostic': args['diagnostic_raw'] = recovery.encoded({'schema': 'wrong'})
    elif fault == 'same_policy': args['successor_policy'] = args['prior_policy']
    elif fault == 'cross_policy': args['successor_policy']['binding_sha256'] = '0' * 64
    else:
        key = {'tools': 'new_no_tools_proof', 'additional_tools': 'old_no_tools_proof', 'binary': 'new_qualification',
            'pid_namespace': 'local_cessation', 'wrong_container': 'local_cessation', 'live_windows': 'windows_cessation',
            'remote_claim': 'windows_cessation', 'authorization': 'authorization', 'proof_bytes': 'old_no_tools_proof'}[fault]
        value = recovery.document(args['evidence'][key])
        if fault in ('tools', 'additional_tools'):
            value['cases'][0]['http_requests'][0]['tools' if fault == 'tools' else 'additional_tools'] = ['forbidden']
        elif fault == 'binary': value['binary_sha256'] = '0' * 64
        elif fault == 'pid_namespace': value['prior_pid_namespace'] = 'pid:[foreign]'
        elif fault == 'wrong_container': value['lifecycle_events'][0]['Actor']['ID'] = '0' * 64
        elif fault == 'live_windows': value['owned_process_count'] = 1
        elif fault == 'remote_claim': value['remote_termination_inferred'] = True
        elif fault == 'authorization': value['successor_policy_sha256'] = '0' * 64
        elif fault == 'proof_bytes': value['unapproved_extension'] = True
        args['evidence'][key] = recovery.encoded(value)
    with pytest.raises(ValueError): recovery.build_review(**args)


@pytest.mark.parametrize('field,value', [('tools', ['forbidden']), ('additional_tools', ['forbidden']),
    ('functions_count', 1), ('tools_count', False), ('recursive_tool_locations', ['input']),
    ('authorization_present', True), ('actual_system_guard_present', False)])
def test_no_tools_semantics_reject_even_before_any_hash_join(field, value):
    args = specimen(); q = recovery.document(args['evidence']['new_qualification'])
    proof = recovery.document(args['evidence']['new_no_tools_proof'])
    proof['cases'][0]['http_requests'][0][field] = value
    with pytest.raises(ValueError):
        recovery.no_tools(q, proof, args['successor_policy']['source_sha256'])


ROOT_ONLY = pytest.mark.skipif(os.name != 'posix' or os.geteuid() != 0, reason='Actual Root custody/flock controls require Linux Root')


@ROOT_ONLY
def test_runtime_lock_excludes_another_owner(tmp_path):
    os.chmod(tmp_path, 0o700)
    with recovery.runtime_lock(tmp_path):
        with pytest.raises(BlockingIOError):
            with recovery.runtime_lock(tmp_path): pass


@ROOT_ONLY
def test_incomplete_claim_blocks_and_exact_completion_is_bound_to_disposition(tmp_path):
    os.chmod(tmp_path, 0o700); result = recovery.build_review(**specimen()); review = result['review']
    for part in ('recovery-claims', 'recovery-applied', 'relay', 'relay/reconciliations'):
        recovery._directory(tmp_path / part)
    name = review['successor_policy_sha256'] + '.json'
    claim = {key: review[key] for key in recovery.CLAIM_FIELDS - {'schema', 'plan_sha256'}}
    claim.update(schema='ai4r-host-codex-recovery-claim:1', plan_sha256='1' * 64)
    raw = recovery.encoded(claim); recovery.write_new(tmp_path / 'recovery-claims' / name, raw)
    with pytest.raises(ValueError): recovery.verify_recovery_complete(tmp_path)
    receipt = recovery.encoded(result['receipt'])
    target = tmp_path / 'relay/reconciliations' / (recovery.digest(review['request_id'].encode()) + '.json')
    recovery.write_new(target, receipt)
    complete = dict(schema='ai4r-host-codex-recovery-applied:1', claim_sha256=recovery.digest(raw),
        successor_policy_sha256=review['successor_policy_sha256'], disposition_sha256=recovery.digest(receipt),
        profile_sha256=review['successor_profile_sha256'], recorded_at=review['recorded_at'])
    recovery.write_new(tmp_path / 'recovery-applied' / name, recovery.encoded(complete))
    recovery.verify_recovery_complete(tmp_path)
    target.write_bytes(receipt + b' ')
    with pytest.raises(ValueError): recovery.verify_recovery_complete(tmp_path)


@ROOT_ONLY
@pytest.mark.parametrize('crash', [False, True])
def test_apply_never_opens_ledger_or_changes_session_and_partial_apply_blocks(tmp_path, monkeypatch, crash):
    root = tmp_path / 'root'; run = tmp_path / 'run'; root.mkdir(mode=0o700); run.mkdir(mode=0o710)
    os.chown(run, 0, 13000)
    recovery._directory(root / 'relay'); recovery._directory(root / 'relay/backend-receipts')
    args = specimen(); prepared = recovery.build_review(**args)
    prepared.update(catalog_raw=b'{"same":"catalog"}', session_raw=b'{"private":"same"}', input_raw=b'{}',
        runtime_qualification_raw=args['evidence']['old_qualification'], row=args['row'])
    ledger = root / 'relay/requests.sqlite3'; original = b'Original ledger bytes and unknown charge; deliberately not a SQLite database'
    recovery.write_new(ledger, original); prepared['ledger_sha256'] = recovery.digest(original)
    recovery.write_new(root / 'profile.json', args['evidence']['old_profile'])
    globalq = tmp_path / 'qualification.json'; recovery.write_new(globalq, args['evidence']['old_qualification'], mode=0o400)
    recovery.write_new(run / 'qualification.json', args['evidence']['old_qualification'], gid=13000, mode=0o640)
    recovery.write_new(run / 'catalog.json', prepared['catalog_raw'], gid=13000, mode=0o640)
    recovery.write_new(run / 'session.json', prepared['session_raw'], uid=12001, gid=12001, mode=0o400)
    stem = recovery.digest(args['row'][0].encode())
    recovery.write_new(root / 'relay/backend-receipts' / (stem + '.json'), args['diagnostic_raw'])
    monkeypatch.setattr(recovery, 'prepare', lambda *a, **kw: prepared)
    monkeypatch.setattr(recovery, '_stopped', lambda *a: None)
    if crash:
        monkeypatch.setattr(recovery, 'replace', lambda *a, **kw: (_ for _ in ()).throw(OSError('Controlled write fault')))
    invoke = lambda: recovery.apply(tmp_path / 'input.json', recovery.digest(recovery.encoded(prepared['review'])),
        root=root, run=run, qualification=globalq)
    if crash:
        with pytest.raises(OSError): invoke()
        with pytest.raises(ValueError): recovery.verify_recovery_complete(root)
    else:
        assert invoke()['status'] == 'APPLIED_UNKNOWN_PRESERVED'
        recovery.verify_recovery_complete(root)
        assert recovery.document((root / 'profile.json').read_bytes())['policy_sha256'] == args['successor_policy']['sha256']
    assert ledger.read_bytes() == original
    assert (run / 'session.json').read_bytes() == prepared['session_raw']
    assert (run / 'catalog.json').read_bytes() == prepared['catalog_raw']
