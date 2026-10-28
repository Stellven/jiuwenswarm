"""Synthetic Root evidence only; no models, real fixtures or deployment."""
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
spec = importlib.util.spec_from_file_location('development_publication', ROOT/'deploy/m1/rsi_development_publication.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def baseline():
    body = b'def rank(scores):\n    return sorted(scores)\n'
    declaration = p.encoded({'identity': {'name': 'research.screening', 'version_label': 'fixture',
        'body': [{'path': 'ranking.py', 'sha256': p.sha(body)}]}})
    value = {'workspace_id': 'local', 'target_id': 'screening-ranking',
        'target_name': 'Screening ranking helper', 'mutable_path': 'ranking.py',
        'parent_body_ref': {'id': 'body', 'sha256': p.sha(body)},
        'parent_declaration_ref': {'id': 'declaration', 'sha256': p.sha(declaration)},
        'published_at': '2026-10-26T00:00:00Z'}
    return value, body, declaration


def test_pre_run_baseline_contains_only_original_code_and_unknown_standing():
    value, body, declaration = baseline()
    packet = p.baseline_publication(value, body, declaration)
    view = packet['snapshot']; node = view['nodes'][0]
    assert packet['workspace_id'] == 'local' and view['runs'] == []
    assert node['hash'] == p.sha(body) and node['parent_id'] is None
    assert node['security_status'] == 'NOT_APPLICABLE'
    assert node['evaluation_status'] == node['admission_status'] == node['activation_status'] == 'unknown'
    assert node['correctness'] is node['speed'] is node['noise'] is None
    assert packet['candidates'][0]['candidate_code'].encode() == body
    assert not view['targets'][0]['run']['allowed']
    assert not node['admit']['allowed'] and not node['activate']['allowed']


@pytest.mark.parametrize('fault', ['body', 'declaration', 'declared_path'])
def test_baseline_refuses_changed_or_undeclared_parent_source(fault):
    value, body, declaration = baseline()
    if fault == 'body': body += b'# changed'
    if fault == 'declaration': declaration += b' '
    if fault == 'declared_path': value['mutable_path'] = 'other.py'
    with pytest.raises(ValueError): p.baseline_publication(value, body, declaration)


class Evidence:
    evaluator = Path('/synthetic-root')

    def __init__(self):
        self.rows = {}; self.root_rows = {}; self.files = {}

    def put(self, value, *, root=False, raw=False, opaque=False):
        data = value if raw else p.encoded(value)
        digest = p.sha(data)
        pin = {'id': ('blob:' + digest) if opaque else digest+'.json', 'sha256': digest}
        self.rows[digest] = data
        if root: self.root_rows[digest] = data
        return pin

    def read(self, pin): return self.rows[pin['sha256']]
    def root_read(self, pin): return self.root_rows[pin['sha256']]
    def read_file(self, path, owner): return self.files[path.name]


def case():
    evidence = Evidence()
    parent = evidence.put(b'def rank_opportunities(scores):\n    return scores\n', raw=True, opaque=True)
    child = evidence.put(b'def rank_opportunities(scores):\n    return list(scores)\n', raw=True)
    tests = [evidence.put({'synthetic_test': index}) for index in range(12)]
    inputs = [evidence.put({'synthetic_input': index}, root=True) for index in range(12)]
    program = evidence.put(b'# Explicit synthetic program, never executed\n', raw=True, root=True)
    value = {'run_id': 'synthetic-run', 'development_plan_sha256': 'a'*64,
             'fixtures': [{'test_ref': test, 'input_ref': inputs[index]} for index, test in enumerate(tests)],
             'program_ref': program, 'target_id': 'target', 'target_name': 'Synthetic target',
             'mutable_path': 'research/capsules/ranking.py', 'workspace_id': 'test-workspace',
             'result_sha256': 'b'*64, 'published_at': '2026-10-26T00:00:00Z', 'setup_model_calls': 23}
    owner = {'schema': 'ai4r-rsi-development-evaluator-owner:1', 'id': value['run_id'],
             'plan_sha256': value['development_plan_sha256'], 'uid': 0, 'gid': 0,
             'groups': [], 'pid': 123, 'start_ticks': 456,
             'bounded_executor': {'admin_adapter_sha256':'c'*64,'executor_source_sha256':'d'*64}}
    hardware = evidence.put({'synthetic_hardware':True})
    execution = evidence.put({'schema':'ai4r-rsi-development-public-execution:1', 'id':value['run_id'],
        'parent_ref':parent,'public_fixtures':value['fixtures'],'worker_program_ref':program,
        'hardware_ref':hardware,'maximum_jobs':24,'maximum_candidates':1,'security':'UNQUALIFIED',
        'security_campaigns':'DEFERRED','hidden_evaluation':False,'final_evaluation':False,'signing':False,
        'qualification_ref':None,'package_ref':None,'admission_ref':None,'activation_ref':None,
        'admin_runner_sha256':'c'*64,'canonical_executor_sha256':'d'*64,'resource_bounds':{'timeout_s':5}})
    evidence.files['owner.json'] = p.encoded(owner)
    evidence.files['complete.json'] = p.encoded({
        'schema': 'ai4r-rsi-development-evaluator-completion:1', 'id': value['run_id'],
        'plan_sha256': value['development_plan_sha256'], 'status': 'STOPPED',
        'owner_sha256': p.sha(p.encoded(owner))})
    def summary(body_ref, role):
        proofs = []
        for index, test in enumerate(tests):
            ident='development-'+p.sha(p.encoded([value['run_id'],role,index]))[:40]
            start = evidence.put({'schema': 'ai4r-rsi-development-execution-start:1',
                'id': ident, 'candidate_ref': body_ref,
                'test_ref': test, 'input_ref': inputs[index], 'program_ref': program,
                'role': role, 'run_id': value['run_id'], 'case_index': index}, root=True)
            output = evidence.put(b'{}', root=True, raw=True)
            error = evidence.put(b'', root=True, raw=True)
            probe = evidence.put({'synthetic_probe': True}, root=True)
            # Actual V18 receipt has no run_id/validation_ref/baseline_ref.
            receipt = {'subject_ref': body_ref, 'contract_ref':execution,'hardware_ref':hardware,
                'job_id':ident,'invocation_id':ident,'repeat_index':index,'sequence':1,'seed':0,'role':'treatment',
                'observed_runtime':True,'timeout_s':5,
                'argv':['/usr/local/bin/python3','-I','/resources/worker.py'],
                'identity':{'executor_uid':12003,'executor_gid':12003},'termination_reason': 'completed',
                'exit_code': 0, 'wall_time_s': 0.25, 'stdout_ref': output,
                'stderr_ref': error, 'observed_limits': {'isolation_probe_ref': probe,
                    'admin_output_adapter_sha256':'c'*64,'admin_kernel_source_sha256':'d'*64}}
            proofs.append(evidence.put({'schema': 'ai4r-rsi-development-visible-check:1',
                'start_ref': start, 'test_ref': test, 'candidate_ref': body_ref,
                'input_ref': inputs[index], 'program_ref': program,
                'receipt': receipt, 'passed': True, 'group_empty': True}, root=True))
        return {'passed': True, 'passed_count': 12, 'executions': 12,
                'evidence_refs': proofs, 'visible_selection_time_s': 3.0}
    parent_summary, child_summary = summary(parent, 'parent'), summary(child, 'candidate')
    declaration = {'identity': {'name': 'research.screening', 'version_label': 'synthetic-child',
                              'body': [{'path': value['mutable_path'], 'sha256': child['sha256']}]}}
    declaration_ref = evidence.put(declaration)
    diff = evidence.put({'format': 'ai4r-body-diff-v1', 'files': [
        {'path': value['mutable_path'], 'before_ref': parent, 'after_ref': child}]})
    result = {'schema': 'ai4r-rsi-development-result:1', 'id': value['run_id'],
        'status': 'VISIBLE_EVALUATED_UNQUALIFIED', 'security': 'UNQUALIFIED',
        'security_campaigns': 'DEFERRED', 'hidden_evaluation': 'NOT_RUN', 'final_evaluation': 'NOT_RUN',
        'evaluator_exit_code': 0, 'qualification_ref': None, 'package_ref': None,
        'admission_ref': None, 'activation_ref': None, 'model_calls': 2,
        'generating_model': 'gpt-6.1-sol', 'parent_body_ref': parent,
        'candidate': {'child_ref': child, 'diff_ref': diff, 'child_declaration_ref': declaration_ref,
            'child': {'cc_name': 'research.screening', 'cc_version': 'synthetic-child',
                      'declaration_sha256': declaration_ref['sha256']}, 'mandatory_passed': True,
            'evidence_refs': child_summary['evidence_refs'], 'visible_selection_time_s': 3.0},
        'rationale': 'Explicit synthetic candidate, never executed.',
        'parent_visible': parent_summary, 'candidate_visible': child_summary,
        'private_native_trace': 'MUST NEVER BE PUBLISHED'}
    return value, result, evidence


def test_actual_visible_results_are_separate_from_security_and_every_gate_denies():
    value, result, evidence = case()
    packet = p.publication(value, result, evidence)
    baseline, child = packet['snapshot']['nodes']
    assert packet['workspace_id'] == 'test-workspace'
    assert packet['snapshot']['targets'][0]['active_hash'] is None
    assert (child['correctness'], child['security_status'], child['evaluation_status']) == (
        '12/12 visible checks', 'SECURITY_DEFERRED', 'passed')
    assert 'uncalibrated' in child['speed'] and child['noise'] == 'Not measured'
    assert baseline['admission_status'] == baseline['activation_status'] == 'unknown'
    assert child['admission_status'] == 'unadmitted' and child['activation_status'] == 'inactive'
    assert child['parent_id'] == baseline['id']
    assert all(not node[action]['allowed'] for node in packet['snapshot']['nodes'] for action in ('admit', 'activate'))
    assert 'MUST NEVER BE PUBLISHED' not in json.dumps(packet)
    assert len(child['evidence_refs']) == 12 and len(packet['candidates']) == 2


@pytest.mark.parametrize('fault', ['qualification', 'hidden', 'model', 'calls', 'owner', 'count', 'time', 'test-set', 'diff'])
def test_forged_claim_or_scope_stops_before_publication(fault):
    value, result, evidence = case()
    if fault == 'qualification': result['qualification_ref'] = result['parent_body_ref']
    if fault == 'hidden': result['hidden_evaluation'] = 'PASSED'
    if fault == 'model': result['generating_model'] = 'substitute-model'
    if fault == 'calls': result['model_calls'] = 1
    if fault == 'owner': evidence.files['owner.json'] += b' '
    if fault == 'count': result['candidate_visible']['passed_count'] = 11
    if fault == 'time': result['candidate_visible']['visible_selection_time_s'] = 2.0
    if fault == 'test-set': value['fixtures'][0]['test_ref'] = evidence.put({'foreign': True})
    if fault == 'diff':
        result['candidate']['diff_ref'] = evidence.put({'format': 'ai4r-body-diff-v1', 'files': []})
    with pytest.raises(ValueError): p.publication(value, result, evidence)


def test_controller_cannot_replace_root_evaluation_facts():
    value, result, evidence = case()
    pin = result['candidate_visible']['evidence_refs'][0]
    record = json.loads(evidence.rows[pin['sha256']]); record['passed'] = False
    evidence.rows[pin['sha256']] = p.encoded(record)
    with pytest.raises(ValueError, match='Root original'):
        p.publication(value, result, evidence)


@pytest.mark.parametrize('fault',['job','repeat','legacy-run','contract-run','contract-tests','adapter'])
def test_v18_receipt_joins_reject_foreign_context_without_inventing_missing_fields(fault):
    value,result,evidence=case()
    original=result['candidate_visible']['evidence_refs'][0]
    proof=json.loads(evidence.read(original));receipt=proof['receipt']
    assert not {'run_id','validation_ref','baseline_ref'}.intersection(receipt)
    if fault=='job':receipt['job_id']='foreign-job'
    elif fault=='repeat':receipt['repeat_index']=1
    elif fault=='legacy-run':receipt['run_id']='foreign-run'
    elif fault=='adapter':receipt['observed_limits']['admin_output_adapter_sha256']='f'*64
    else:
        contract=json.loads(evidence.read(receipt['contract_ref']))
        if fault=='contract-run':contract['id']='foreign-run'
        else:contract['public_fixtures']=[]
        receipt['contract_ref']=evidence.put(contract)
    changed=evidence.put(proof,root=True)
    result['candidate_visible']['evidence_refs'][0]=changed
    with pytest.raises(ValueError):p.publication(value,result,evidence)


def test_failed_visible_case_remains_visible_without_becoming_qualified():
    value, result, evidence = case()
    pin = result['candidate_visible']['evidence_refs'][0]
    record = json.loads(evidence.rows[pin['sha256']]); record['passed'] = False
    changed = evidence.put(record, root=True)
    result['candidate_visible'].update(passed=False, passed_count=11)
    result['candidate_visible']['evidence_refs'][0] = changed
    result['candidate']['evidence_refs'] = result['candidate_visible']['evidence_refs']
    result['candidate']['mandatory_passed'] = False
    child = p.publication(value, result, evidence)['snapshot']['nodes'][1]
    assert child['correctness'] == '11/12 visible checks'
    assert child['evaluation_status'] == 'failed'
    assert child['security_status'] == 'SECURITY_DEFERRED' and not child['admit']['allowed']
