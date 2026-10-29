"""Publish a finite, workspace-bound view of actual development-run evidence.

This publisher grants no run, qualification, Library or activation authority.
Only Root may publish; the browser receives code and measured public-check
summaries, never native traces, account data or private fixture records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat


SCHEMA = 'ai4r-rsi-development-publication-input:1'
LIMIT = 4 * 1024 * 1024
FIELDS = {'schema', 'workspace_id', 'run_id', 'target_id', 'target_name',
          'mutable_path', 'record_root', 'core_root', 'evaluator_root',
          'result_sha256', 'development_plan_sha256', 'fixtures', 'program_ref',
          'setup_model_calls', 'published_at', 'publication_directory',
          'expected_previous_sha256'}
BASELINE_SCHEMA = 'ai4r-rsi-development-baseline-input:1'
BASELINE_FIELDS = {'schema', 'workspace_id', 'target_id', 'target_name',
                   'mutable_path', 'parent_body_path', 'parent_body_ref',
                   'parent_declaration_path', 'parent_declaration_ref',
                   'published_at', 'publication_directory', 'expected_previous_sha256'}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def closed_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate publication field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite publication value'))


def hash_value(value):
    need(isinstance(value, str) and len(value) == 64
         and all(c in '0123456789abcdef' for c in value), 'Exact hash required')


def ref(value):
    need(isinstance(value, dict) and set(value) == {'id', 'sha256'}
         and isinstance(value['id'], str) and bool(value['id']), 'Exact evidence Ref required')
    hash_value(value['sha256'])


def protected(path, owner, *, directory=False):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'Unsafe publication path')
    for parent in (path, *path.parents):
        info = parent.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not info.st_mode & 0o022,
             'Writable or linked publication ancestry')
        need(info.st_uid in {0, owner}, 'Publication ancestry owner differs')
    info = path.lstat()
    need(info.st_uid == owner, 'Publication source owner differs')
    need(stat.S_ISDIR(info.st_mode) if directory else
         stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= LIMIT,
         'Publication source kind or size differs')
    return path


class Evidence:
    def __init__(self, value):
        self.records = protected(value['record_root'], 12001, directory=True)
        self.core = protected(value['core_root'], 12001, directory=True)
        self.evaluator = protected(value['evaluator_root'], 0, directory=True)
        self.originals = {}

    def read_file(self, path, owner):
        raw = protected(path, owner).read_bytes()
        need(len(raw) <= LIMIT, 'Evidence exceeds finite publication limit')
        self.originals[str(path)] = sha(raw)
        return raw

    def read(self, pin):
        ref(pin)
        candidates = (self.records / (pin['sha256'] + '.json'),
                      self.core / 'artifacts/sha256' / pin['sha256'][:2] / pin['sha256'])
        for path in candidates:
            if path.exists():
                raw = self.read_file(path, 12001)
                need(sha(raw) == pin['sha256'], 'Evidence bytes differ from Ref')
                return raw
        raise ValueError('Explicit publication evidence is absent')

    def root_read(self, pin):
        ref(pin)
        raw = self.read_file(self.evaluator / 'captures' / (pin['sha256'] + '.json'), 0)
        need(sha(raw) == pin['sha256'], 'Root evaluator evidence differs')
        return raw


def receipt_context(receipt, start, fixtures, run_id, role, index, read, *,
                    body_ref, baseline_ref, program_ref, bounded_executor):
    """Join the actual V18 receipt to its Root start and captured job contract.

    V18 emits subject/job/invocation/contract identities. Run, validation and
    baseline identities live in the Root start and execution contract instead.
    """
    ident = 'development-' + sha(encoded([run_id, role, index]))[:40]
    need(start['id'] == ident and receipt['job_id'] == receipt['invocation_id'] == ident
         and receipt['subject_ref'] == body_ref and receipt['repeat_index'] == index
         and receipt['sequence'] == 1 and receipt['seed'] == 0 and receipt['role'] == 'treatment'
         and receipt['observed_runtime'] is True
         and receipt['argv'] == ['/usr/local/bin/python3', '-I', '/resources/worker.py']
         and receipt['identity'] == {'executor_uid': 12003, 'executor_gid': 12003},
         'Execution receipt identity differs')
    # If a newer ABI supplies these fields, conflicting values still fail.
    for key, expected in (('run_id', run_id), ('validation_ref', start['test_ref']), ('baseline_ref', baseline_ref)):
        need(key not in receipt or receipt[key] == expected, 'Execution receipt context conflicts')
    contract = closed_json(read(receipt['contract_ref']))
    need(contract['schema'] == 'ai4r-rsi-development-public-execution:1' and contract['id'] == run_id
         and contract['parent_ref'] == baseline_ref and contract['public_fixtures'] == fixtures
         and contract['worker_program_ref'] == program_ref and contract['hardware_ref'] == receipt['hardware_ref']
         and contract['maximum_jobs'] == 24 and contract['maximum_candidates'] == 1
         and contract['security'] == 'UNQUALIFIED' and contract['security_campaigns'] == 'DEFERRED'
         and contract['hidden_evaluation'] is contract['final_evaluation'] is contract['signing'] is False
         and all(contract[key] is None for key in ('qualification_ref', 'package_ref', 'admission_ref', 'activation_ref')),
         'Captured development execution contract differs')
    limits = receipt['observed_limits']
    need(contract['admin_runner_sha256'] == bounded_executor['admin_adapter_sha256']
         and contract['canonical_executor_sha256'] == bounded_executor['executor_source_sha256']
         and limits['admin_output_adapter_sha256'] == contract['admin_runner_sha256']
         and limits['admin_kernel_source_sha256'] == contract['canonical_executor_sha256']
         and receipt['timeout_s'] == contract['resource_bounds']['timeout_s'],
         'Actual executor provenance differs')


def visible_checks(summary, body_ref, fixtures, run_id, role, read, root_read, *, baseline_ref, program_ref, bounded_executor):
    """Derive counts/times from Root originals, independently of result scalars."""
    need(isinstance(summary, dict) and set(summary) == {
        'passed', 'passed_count', 'executions', 'evidence_refs', 'visible_selection_time_s'},
        'Closed visible-check summary required')
    pins = summary['evidence_refs']
    need(isinstance(pins, list) and len(pins) == 12
         and len({encoded(p) for p in pins}) == 12, 'Twelve distinct checks required')
    expected_tests = [row['test_ref'] for row in fixtures]
    found, invocations, passed, elapsed = [], set(), 0, 0.0
    for index, pin in enumerate(pins):
        raw = root_read(pin)
        need(read(pin) == raw, 'Controller check differs from Root original')
        proof = closed_json(raw)
        need(set(proof) == {'schema', 'start_ref', 'test_ref', 'input_ref', 'program_ref', 'candidate_ref',
                            'receipt', 'passed', 'group_empty'}
             and proof['schema'] == 'ai4r-rsi-development-visible-check:1'
             and proof['candidate_ref'] == body_ref and type(proof['passed']) is bool
             and proof['group_empty'] is True, 'Visible check scope differs')
        need(proof['test_ref'] == fixtures[index]['test_ref']
             and proof['input_ref'] == fixtures[index]['input_ref'] and proof['program_ref'] == program_ref,
             'Exact public input or installed program differs')
        start = closed_json(root_read(proof['start_ref']))
        need(start['schema'] == 'ai4r-rsi-development-execution-start:1'
             and start['candidate_ref'] == body_ref and start['test_ref'] == proof['test_ref']
             and start['input_ref'] == proof['input_ref'] and start['program_ref'] == program_ref
             and start['role'] == role and start['run_id'] == run_id and start['case_index'] == index,
             'Root execution start differs')
        root_read(proof['input_ref']); root_read(program_ref)
        receipt = proof['receipt']
        receipt_context(receipt, start, fixtures, run_id, role, index, read,
                        body_ref=body_ref, baseline_ref=baseline_ref, program_ref=program_ref,
                        bounded_executor=bounded_executor)
        need(receipt['invocation_id'] not in invocations, 'Execution invocation was reused')
        invocations.add(receipt['invocation_id'])
        if proof['passed']:
            need(receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0,
                 'A failed execution cannot pass')
        wall = receipt['wall_time_s']
        need(type(wall) in (int, float) and math.isfinite(wall) and 0 <= wall <= 3600,
             'Actual execution time unavailable')
        for raw_pin in (receipt['stdout_ref'], receipt['stderr_ref'],
                        receipt['observed_limits']['isolation_probe_ref']):
            root_read(raw_pin)  # Validate closure; raw contents are never published.
        found.append(proof['test_ref']); passed += int(proof['passed']); elapsed += wall
    need(len({encoded(p) for p in found}) == 12
         and {encoded(p) for p in found} == {encoded(p) for p in expected_tests},
         'Visible test set differs from authorized public tests')
    need(summary['executions'] == 12 and type(summary['executions']) is int
         and summary['passed_count'] == passed and type(summary['passed_count']) is int
         and summary['passed'] is (passed == 12)
         and type(summary['visible_selection_time_s']) in (int, float)
         and math.isclose(summary['visible_selection_time_s'], elapsed, rel_tol=1e-9, abs_tol=1e-9),
         'Published summary differs from actual checks')
    return passed, elapsed, pins


def publication(value, result, evidence):
    need(result['schema'] == 'ai4r-rsi-development-result:1'
         and result['id'] == value['run_id']
         and result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED'
         and result['security'] == 'UNQUALIFIED' and result['security_campaigns'] == 'DEFERRED'
         and result['hidden_evaluation'] == result['final_evaluation'] == 'NOT_RUN'
         and result['evaluator_exit_code'] == 0 and type(result['evaluator_exit_code']) is int,
         'A completed unqualified development result is required')
    need(all(result[key] is None for key in ('qualification_ref', 'package_ref', 'admission_ref', 'activation_ref')),
         'Development evidence cannot grant qualification or admission')
    need(type(result['model_calls']) is int and result['model_calls'] == 2
         and result['generating_model'] == 'gpt-6.1-sol', 'Observed two-call model provenance required')
    complete = closed_json(evidence.read_file(evidence.evaluator / 'complete.json', 0))
    need(set(complete) == {'schema', 'id', 'plan_sha256', 'status', 'owner_sha256'}
         and complete['schema'] == 'ai4r-rsi-development-evaluator-completion:1'
         and complete['id'] == value['run_id']
         and complete['plan_sha256'] == value['development_plan_sha256'] and complete['status'] == 'STOPPED',
         'Root evaluator completion differs from reviewed run')
    owner_raw = evidence.read_file(evidence.evaluator / 'owner.json', 0)
    need(sha(owner_raw) == complete['owner_sha256'], 'Root evaluator owner changed')
    owner = closed_json(owner_raw)
    need(owner['schema'] == 'ai4r-rsi-development-evaluator-owner:1'
         and owner['id'] == value['run_id'] and owner['plan_sha256'] == value['development_plan_sha256']
         and owner['uid'] == owner['gid'] == 0 and owner['groups'] == []
         and type(owner['pid']) is int and owner['pid'] > 0
         and type(owner['start_ticks']) is int and owner['start_ticks'] > 0,
         'Root evaluator identity differs')
    candidate = result['candidate']
    parent_ref, child_ref = result['parent_body_ref'], candidate['child_ref']
    parent = evidence.read(parent_ref).decode('utf8'); child = evidence.read(child_ref).decode('utf8')
    need(len(parent) <= 262144 and len(child) <= 262144, 'Candidate code exceeds UI disclosure limit')
    need(parent_ref['sha256'] != child_ref['sha256'], 'An unchanged body is not a new capsule')
    diff = closed_json(evidence.read(candidate['diff_ref']))
    need(diff == {'format': 'ai4r-body-diff-v1', 'files': [
        {'path': value['mutable_path'], 'before_ref': parent_ref, 'after_ref': child_ref}]},
        'Candidate diff exceeds the one authorized path')
    declaration = closed_json(evidence.read(candidate['child_declaration_ref']))
    need(declaration['identity']['name'] == candidate['child']['cc_name']
         and declaration['identity']['version_label'] == candidate['child']['cc_version']
         and candidate['child_declaration_ref']['sha256'] == candidate['child']['declaration_sha256']
         and any(row['path'] == value['mutable_path'] and row['sha256'] == child_ref['sha256']
                 for row in declaration['identity']['body']), 'Actual child declaration differs')
    parent_count, parent_time, parent_checks = visible_checks(
        result['parent_visible'], parent_ref, value['fixtures'], value['run_id'], 'parent', evidence.read, evidence.root_read,
        baseline_ref=parent_ref, program_ref=value['program_ref'], bounded_executor=owner['bounded_executor'])
    child_count, child_time, child_checks = visible_checks(
        result['candidate_visible'], child_ref, value['fixtures'], value['run_id'], 'candidate', evidence.read, evidence.root_read,
        baseline_ref=parent_ref, program_ref=value['program_ref'], bounded_executor=owner['bounded_executor'])
    need(candidate['mandatory_passed'] is (child_count == 12)
         and candidate['evidence_refs'] == child_checks, 'Assessment differs from actual visible evidence')
    reason = 'Security campaign deferred; this development candidate is unqualified. Human operator integration is not installed.'
    gate = lambda: {'allowed': False, 'blocker': reason}
    parent_id = 'base:' + parent_ref['sha256']; child_id = 'candidate:' + child_ref['sha256']
    def node(ident, body, count, elapsed, checks, *, baseline):
        return {'id': ident, 'target_id': value['target_id'], 'run_id': None if baseline else value['run_id'],
                'parent_id': None if baseline else parent_id, 'hash': body['sha256'],
                'label': 'Workbench base' if baseline else candidate['child']['cc_name'] + ' · ' + candidate['child']['cc_version'],
                'evaluation_status': 'passed' if count == 12 else 'failed',
                'security_status': 'NOT_APPLICABLE' if baseline else 'SECURITY_DEFERRED',
                'admission_status': 'unknown' if baseline else 'unadmitted', 'activation_status': 'unknown' if baseline else 'inactive',
                'correctness': f'{count}/12 visible checks',
                'speed': f'{elapsed:.6g}s total execution wall time; uncalibrated', 'noise': 'Not measured',
                'evidence_refs': checks, 'operator_receipts': [], 'admit': gate(), 'activate': gate()}
    rationale = result['rationale']
    need(isinstance(rationale, str) and 0 < len(rationale) <= 4096, 'Bounded actual rationale required')
    rows = [node(parent_id, parent_ref, parent_count, parent_time, parent_checks, baseline=True),
            node(child_id, child_ref, child_count, child_time, child_checks, baseline=False)]
    return {'workspace_id': value['workspace_id'], 'snapshot': {
        'schema_version': '1', 'revision': value['result_sha256'], 'generated_at': value['published_at'],
        'availability': 'AVAILABLE', 'blocker': reason,
        'targets': [{'id': value['target_id'], 'name': value['target_name'], 'parent_hash': parent_ref['sha256'],
                     'active_hash': None, 'run': gate()}],
        'runs': [{'id': value['run_id'], 'target_id': value['target_id'], 'stage': 'development_evaluation',
                  'status': 'COMPLETED_UNQUALIFIED', 'blockers': [reason], 'activity': [
                      {'id': value['run_id'] + ':generation', 'at': value['published_at'],
                       'stage': 'development_evaluation', 'status': 'COMPLETED_UNQUALIFIED',
                       'summary': 'Diagnosis and proposal completed with ' + result['generating_model']
                                  + '; visible checks evaluated; security campaign deferred.'}],
                  'budget': {'elapsed_seconds': None, 'limit_seconds': 3600,
                             'setup_calls': value['setup_model_calls'], 'diagnosis_calls': 1, 'proposal_calls': 1,
                             'generation_call_limit': 2, 'cost': None, 'currency': None}}], 'nodes': rows},
        'candidates': [
            {'node_id': ident, 'candidate_hash': body_ref['sha256'], 'path': value['mutable_path'],
             'parent_code': parent, 'candidate_code': code, 'rationale': None if ident == parent_id else rationale,
             'blocker': reason}
            for ident, body_ref, code in ((parent_id, parent_ref, parent), (child_id, child_ref, child))]}


def plan(input_path):
    raw = protected(input_path, 0).read_bytes(); value = closed_json(raw)
    need(set(value) == FIELDS and value['schema'] == SCHEMA, 'Closed publication input required')
    for key in ('workspace_id', 'run_id', 'target_id', 'target_name', 'published_at', 'mutable_path'):
        need(isinstance(value[key], str) and 0 < len(value[key]) <= 512, 'Finite publication identity required')
    need(not value['mutable_path'].startswith('/') and '..' not in Path(value['mutable_path']).parts,
         'Relative authorized path required')
    for key in ('result_sha256', 'development_plan_sha256'): hash_value(value[key])
    if value['expected_previous_sha256'] is not None: hash_value(value['expected_previous_sha256'])
    need(type(value['setup_model_calls']) is int and 0 <= value['setup_model_calls'] <= 10000,
         'Measured setup-call count required')
    need(isinstance(value['fixtures'], list) and len(value['fixtures']) == 12,
         'Exact public test set required')
    for row in value['fixtures']:
        need(isinstance(row, dict) and set(row) == {'test_ref', 'input_ref'}, 'Closed public test/input pair required')
        ref(row['test_ref']); ref(row['input_ref'])
    need(len({encoded(row['test_ref']) for row in value['fixtures']}) == 12, 'Distinct public tests required')
    ref(value['program_ref'])
    evidence = Evidence(value)
    result_raw = evidence.read_file(evidence.records / 'development-result.json', 12001)
    need(sha(result_raw) == value['result_sha256'], 'Development result changed')
    packet = publication(value, closed_json(result_raw), evidence)
    packet_raw = encoded(packet); need(len(packet_raw) <= 2 * 1024 * 1024, 'Public packet exceeds UI contract')
    directory = protected(value['publication_directory'], 0, directory=True)
    metadata = directory.stat()
    need(metadata.st_gid == 10001 and stat.S_IMODE(metadata.st_mode) == 0o750,
         'Dedicated public directory must be Root:10001 mode0750')
    target = directory / 'publication.json'
    previous = sha(protected(target, 0).read_bytes()) if target.exists() else None
    need(previous == value['expected_previous_sha256'], 'Previous public revision differs')
    facts = {'schema': 'ai4r-rsi-development-publication-plan:1', 'input_sha256': sha(raw),
             'source_sha256': sha(Path(__file__).read_bytes()), 'result_sha256': value['result_sha256'],
             'originals': evidence.originals, 'publication_sha256': sha(packet_raw),
             'previous_sha256': previous, 'target': str(target), 'workspace_id': value['workspace_id'],
             'candidate_hash': packet['snapshot']['nodes'][1]['hash'], 'qualification': False,
             'admission_or_activation': False, 'model_calls': 0}
    return value, facts, packet_raw


def baseline_publication(value, body, declaration):
    """Show actual frozen parent source before a run, without claiming standing."""
    ref(value['parent_body_ref']); ref(value['parent_declaration_ref'])
    need(sha(body) == value['parent_body_ref']['sha256']
         and sha(declaration) == value['parent_declaration_ref']['sha256'],
         'Baseline original bytes differ')
    identity = closed_json(declaration)['identity']
    pins = identity.get('body', []) + [identity.get('carrier', {})]
    need(any(row.get('path', row.get('ref')) == value['mutable_path']
             and row.get('sha256') == sha(body) for row in pins),
         'Baseline mutable path is not declared by the frozen capsule')
    code = body.decode('utf8')
    need(len(code) <= 262144, 'Baseline code exceeds public contract')
    node_id = 'base:' + sha(body)
    blocker = 'Development experiment only; security campaign deferred. No admission or activation authority.'
    denied = {'allowed': False, 'blocker': blocker}
    revision = sha(encoded({key: value[key] for key in
        ('workspace_id', 'target_id', 'mutable_path', 'parent_body_ref', 'parent_declaration_ref')}))
    return {'workspace_id': value['workspace_id'], 'snapshot': {
        'schema_version': '1', 'revision': revision, 'generated_at': value['published_at'],
        'availability': 'AVAILABLE', 'blocker': None,
        'targets': [{'id': value['target_id'], 'name': value['target_name'],
                     'parent_hash': sha(body), 'active_hash': None, 'run': dict(denied)}],
        'runs': [], 'nodes': [{'id': node_id, 'target_id': value['target_id'],
            'run_id': None, 'parent_id': None, 'hash': sha(body),
            'label': identity['name'] + ' ' + identity['version_label'],
            'security_status': 'NOT_APPLICABLE', 'evaluation_status': 'unknown',
            'admission_status': 'unknown', 'activation_status': 'unknown',
            'correctness': None, 'speed': None, 'noise': None,
            'evidence_refs': [value['parent_body_ref'], value['parent_declaration_ref']],
            'operator_receipts': [], 'admit': dict(denied), 'activate': dict(denied)}]},
        'candidates': [{'node_id': node_id, 'candidate_hash': sha(body),
            'path': value['mutable_path'], 'parent_code': code, 'candidate_code': code,
            'rationale': None, 'blocker': blocker}]}


def baseline_plan(input_path):
    raw = protected(input_path, 0).read_bytes(); value = closed_json(raw)
    need(set(value) == BASELINE_FIELDS and value['schema'] == BASELINE_SCHEMA,
         'Closed baseline publication input required')
    for key in ('workspace_id', 'target_id', 'target_name', 'mutable_path', 'published_at'):
        need(isinstance(value[key], str) and 0 < len(value[key]) <= 512,
             'Finite baseline identity required')
    need(not value['mutable_path'].startswith('/') and '\\' not in value['mutable_path']
         and '..' not in Path(value['mutable_path']).parts, 'Relative authorized path required')
    body = protected(value['parent_body_path'], 0).read_bytes()
    declaration = protected(value['parent_declaration_path'], 0).read_bytes()
    packet = baseline_publication(value, body, declaration); packet_raw = encoded(packet)
    need(len(packet_raw) <= 2 * 1024 * 1024, 'Public packet exceeds UI contract')
    directory = protected(value['publication_directory'], 0, directory=True)
    metadata = directory.stat()
    need(metadata.st_gid == 10001 and stat.S_IMODE(metadata.st_mode) == 0o750,
         'Dedicated public directory must be Root:10001 mode0750')
    target = directory / 'publication.json'
    previous = sha(protected(target, 0).read_bytes()) if target.exists() else None
    need(previous == value['expected_previous_sha256'], 'Previous public revision differs')
    facts = {'schema': 'ai4r-rsi-development-baseline-plan:1',
        'input_sha256': sha(raw), 'source_sha256': sha(Path(__file__).read_bytes()),
        'parent_body_sha256': sha(body), 'parent_declaration_sha256': sha(declaration),
        'publication_sha256': sha(packet_raw), 'previous_sha256': previous,
        'target': str(target), 'workspace_id': value['workspace_id'],
        'revision': packet['snapshot']['revision'], 'qualification': False,
        'admission_or_activation': False, 'model_calls': 0}
    return value, facts, packet_raw


def _publish(input_path, reviewed, planner):
    value, facts, raw = planner(input_path)
    need(sha(encoded(facts)) == reviewed, 'Exact publication-plan review required')
    need(planner(input_path)[1] == facts, 'Publication facts changed before effect')
    claim = Path(input_path).with_name(Path(input_path).name + '.' + reviewed + '.claim.json')
    fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encoded({'schema': 'ai4r-rsi-development-publication-claim:1', 'plan_sha256': reviewed}))
        stream.flush(); os.fsync(stream.fileno())
    directory = Path(value['publication_directory']); temporary = directory / ('.publication-' + reviewed + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o440)
    with os.fdopen(fd, 'wb') as stream:
        os.fchown(stream.fileno(), 0, 10001); os.fchmod(stream.fileno(), 0o440)
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, directory / 'publication.json')
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return {'status': 'PUBLIC_DEVELOPMENT_VIEW_PUBLISHED_UNQUALIFIED',
            'publication_sha256': sha(raw), 'plan_sha256': reviewed, 'qualification': False}


def publish(input_path, reviewed):
    return _publish(input_path, reviewed, plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('plan', 'publish', 'baseline-plan', 'baseline-publish'))
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--review-sha256')
    args = parser.parse_args()
    need(os.name == 'posix' and os.geteuid() == 0, 'Publisher requires the Linux Root operator')
    planner = baseline_plan if args.operation.startswith('baseline-') else plan
    result = planner(args.input)[1] if args.operation.endswith('plan') else _publish(args.input, args.review_sha256, planner)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
