"""Root disposition of an unknown executed campaign; fresh qualification only.

Every original SQL row, evidence blob and attempt charge is retained. This
protocol appends a separate abandonment, never a successful case or clearance.
Both plan and apply independently read the stopped owned runtime and originals.

Input :1 retains its strict one-pending-start ABI and denial checks. Input :2
adds attempt_ref, observation_ref, failure_ref and observed_prefix to original_refs.
Each prefix row is the exact historical SQL case row plus case_id. The prefix
must be ordered from RSIV-1 and followed by exactly one canonical UNKNOWN kernel
case; all later case charges must remain zero. Historical signed SECURITY_HALTED
prefix records remain preserved and confer no fresh qualification.

Only :2 adds original_sources -> original-sources.json to proof_sha256. That proof
has schema ai4r-rsi-abandonment-original-sources:1 and exactly two files entries:
{path, bytes, sha256, content_b64}, using installed package-relative paths
research_rsi/process_policy.py and research/contracts/rsi_security_cases.py.
Each file is bounded to262144 bytes and matched to the original scope's installed
inventory, whose source build/image is independently rejoined to Root history.
The proof is archived under the same immutable claim/completion. Restricted AST
reads reconstruct old program bytes without executing old source or calling any
security predicate. Raw lifecycle custody is explicitly predicate_verified:false;
UNKNOWN never becomes PASS, and every old case requires fresh qualification.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('_abandonment_repair', HERE / 'rsi_stopped_repair.py')
repair = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repair)
need, encoded, digest, read, closed_json = repair.need, repair.encoded, repair.digest, repair.read, repair.closed_json
PROOF_FILES = {k: v for k, v in repair.PROOF_FILES.items() if k != 'failure'} | {
    'incident': 'incident.json', 'cessation': 'cessation.json'}


def proof_files(request):
    return PROOF_FILES | ({'original_sources':'original-sources.json'} if request.get('schema') == 'ai4r-rsi-security-abandonment-input:2' else {})


def load_input(root, path):
    raw = read(path); value = closed_json(raw)
    fields = {'schema', 'generation', 'authorization', 'bootstrap_generation', 'old_manifest_sha256',
              'new_project', 'worker_container_id', 'signer_container_id', 'original_refs', 'proof_sha256'}
    need(set(value) == fields and value['schema'] in ('ai4r-rsi-security-abandonment-input:1','ai4r-rsi-security-abandonment-input:2'), 'UNKNOWN_ABANDONMENT_INPUT')
    need(all(isinstance(value[k], str) and repair.GENERATION.fullmatch(value[k]) for k in ('generation', 'bootstrap_generation')))
    need(isinstance(value['authorization'], str) and 0 < len(value['authorization']) <= 4096)
    need(repair.sibling('rsi_local').NAME.fullmatch(value['new_project']))
    need(all(repair.HASH.fullmatch(value[k]) for k in ('old_manifest_sha256', 'worker_container_id', 'signer_container_id')))
    need(value['worker_container_id'] != value['signer_container_id'])
    need(path.parent == root / 'config/security-abandonment-inputs' / value['generation'] and path.name == 'input.json', 'FIXED_ABANDONMENT_INPUT_REQUIRED')
    need(set(value['proof_sha256']) == set(proof_files(value)))
    proofs = {}
    for kind, name in proof_files(value).items():
        body = read(path.parent / name)
        need(digest(body) == value['proof_sha256'][kind], 'ABANDONMENT_PROOF_BYTES_DIFFER')
        proofs[kind] = closed_json(body)
    return value, proofs, raw


def _sql_bytes(path, *, sidecar=False):
    # SQLite may create a read-only-to-others WAL under its Root-private 0700
    # state directory. Require its actual native mode without changing it.
    repair.custody(path.parent, directory=True, mode=0o700)
    mode = stat.S_IMODE(path.lstat().st_mode)
    need(mode in ({0o600,0o644} if sidecar else {0o600}), 'UNSAFE_ORIGINAL_SQL_MODE')
    return read(path, mode=mode, limit=256*1024*1024)


class FrozenDatabase:
    """Read retained WAL through a private copy, never checkpoint an original."""
    def __init__(self, path):
        originals = {}
        for suffix in ('', '-wal'):
            original = Path(str(path) + suffix)
            if suffix and not os.path.lexists(original):
                continue
            originals[suffix] = _sql_bytes(original,sidecar=bool(suffix))
        journal = Path(str(path) + '-journal')
        need(not os.path.lexists(journal) or _sql_bytes(journal,sidecar=True) == b'', 'HOT_ROLLBACK_JOURNAL_REQUIRES_SEPARATE_REVIEW')
        self.temp = tempfile.TemporaryDirectory(prefix='rsi-abandonment-read-')
        try:
            root = Path(self.temp.name); os.chmod(root,0o700)
            for suffix, raw in originals.items():
                target = root / ('index.sqlite' + suffix)
                with target.open('xb') as output:
                    os.chmod(target,0o600); output.write(raw)
            need(all(_sql_bytes(Path(str(path)+suffix),sidecar=bool(suffix)) == raw for suffix,raw in originals.items()), 'ORIGINAL_DATABASE_CHANGED_DURING_CAPTURE')
            need(('-wal' in originals) == os.path.lexists(Path(str(path)+'-wal')), 'ORIGINAL_WAL_CHANGED_DURING_CAPTURE')
            self.db = sqlite3.connect((root / 'index.sqlite').as_uri() + '?mode=ro', uri=True)
            self.db.execute('PRAGMA query_only=ON')
            need(self.db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'RETAINED_DATABASE_INTEGRITY_FAILED')
        except BaseException:
            self.temp.cleanup(); raise

    def execute(self, *args):
        return self.db.execute(*args)

    def close(self):
        self.db.close(); self.temp.cleanup()


class OriginalStore:
    """Read-only exact indexed bytes; deliberately never construct SQLiteRunStore."""
    def __init__(self, root):
        self.root = Path(root)
        self.db = FrozenDatabase(self.root / 'state/research.sqlite3')

    def raw(self, pin, kind=None):
        need(isinstance(pin, dict) and set(pin) == {'id', 'sha256'} and repair.HASH.fullmatch(pin['sha256']), 'INVALID_ORIGINAL_REF')
        rows = self.db.execute('SELECT a.sha256,r.kind FROM artifacts a LEFT JOIN records r ON r.id=a.id WHERE a.id=?', (pin['id'],)).fetchall()
        need(len(rows) == 1 and rows[0][0] == pin['sha256'] and (kind is None or rows[0][1] == kind), 'ORIGINAL_INDEX_JOIN_DIFFERS')
        raw = read(self.root / 'artifacts/sha256' / pin['sha256'][:2] / pin['sha256'])
        need(digest(raw) == pin['sha256'], 'ORIGINAL_BLOB_DIFFERS')
        return raw

    def get(self, pin, kind=None):
        return closed_json(self.raw(pin, kind))

    def records(self, kind):
        rows = self.db.execute('SELECT a.id,a.sha256 FROM artifacts a JOIN records r ON r.id=a.id WHERE r.kind=? ORDER BY a.id', (kind,)).fetchall()
        return [({'id': ident, 'sha256': sha}, self.get({'id': ident, 'sha256': sha}, kind)) for ident, sha in rows]

    def close(self):
        self.db.close()


def join_originals(store, ledger, pins):
    """Join retained effects without synthesizing an observation or attempt."""
    from jiuwenswarm.research_rsi.session_policy import validate_private
    from jiuwenswarm.research_rsi.worker import validate_profile
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.contracts.rsi_security import CASES
    fields = {'campaign_status_ref', 'claim_ref', 'effect_start_ref', 'execution_receipt_ref',
              'isolation_probe_ref', 'kernel_group_empty_ref', 'kernel_observation_ref', 'before_ref', 'after_ref'}
    need(set(pins) == fields, 'EXACT_ORIGINAL_EFFECT_CLOSURE_REQUIRED')
    status = store.get(pins['campaign_status_ref'], 'rsi-security-campaign-status')
    claim = store.get(pins['claim_ref'], 'rsi-security-case-claim')
    plan = store.get(claim['plan_ref'], 'rsi-security-campaign-plan')
    validate_private('urn:ai4r:private:rsi-security-campaign-plan:1', plan)
    need(set(plan['case_bindings']) == set(CASES), 'FINITE_ORIGINAL_PLAN_REQUIRED')
    need(set(claim) == {'schema','plan_ref','case_id','session_ref','worker_profile_ref','attack_id','started_at'}
         and claim['schema'] == 'ai4r-rsi-security-case-claim:1'
         and claim['attack_id'] == 'security-case-' + digest(encoded([claim['plan_ref'],claim['case_id']]))[:40], 'ORIGINAL_DERIVED_CLAIM_DIFFERS')
    lineage = digest(encoded(plan['case_bindings']))
    campaign = ledger.execute('SELECT plan_ref,start_ref,result_ref FROM security_campaigns WHERE lineage=?', (lineage,)).fetchall()
    need(ledger.execute('SELECT count(*) FROM security_campaigns').fetchone()[0] == 1
         and ledger.execute('SELECT count(*) FROM security_cases').fetchone()[0] == 1, 'ADDITIONAL_CAMPAIGN_LEDGER_EFFECT_PRESENT')
    need(len(campaign) == 1 and closed_json(campaign[0][0].encode()) == claim['plan_ref']
         and closed_json(campaign[0][2].encode()) == pins['campaign_status_ref'], 'ORIGINAL_CAMPAIGN_LEDGER_DIFFERS')
    campaign_start = store.get(closed_json(campaign[0][1].encode()), 'rsi-security-campaign-start')
    need(set(campaign_start) == {'schema','plan_ref','scope_ref','started_at'} and campaign_start['schema'] == 'ai4r-rsi-security-campaign-start:1')
    need(campaign_start['plan_ref'] == claim['plan_ref'] and campaign_start['scope_ref'] == plan['scope_ref'])
    case = claim['case_id']; binding = plan['case_bindings'][case]
    rows = ledger.execute('SELECT case_id,claim_ref,status,observation_ref,halt_ref,evidence_refs,proof_ref FROM security_cases WHERE lineage=?', (lineage,)).fetchall()
    # This bounded protocol disposes exactly one interrupted kernel execution;
    # additional effects require their own complete independent review.
    need(len(rows) == 1 and rows[0][0] == case and closed_json(rows[0][1].encode()) == pins['claim_ref']
         and rows[0][2:] == ('OUTCOME_UNKNOWN', None, None, '[]', None), 'UNKNOWN_ORIGINAL_CASE_REQUIRED')
    row = status['cases'][case]
    need(status['plan_ref'] == claim['plan_ref'] and status['scope_ref'] == plan['scope_ref'] and status['status'] == 'BLOCKED'
         and set(status['cases']) == {case} and row['claim_ref'] == pins['claim_ref'] and row['status'] == 'OUTCOME_UNKNOWN'
         and row['observation_ref'] is row['halt_ref'] is row['proof_ref'] is None and row['evidence_refs'] == []
         and status['verification'] is None, 'ORIGINAL_UNKNOWN_TERMINAL_DIFFERS')
    counts = status['actual_counts'][case]
    need(all(counts[k] == n for k, n in {'canonical_attempts': 0, 'started_attempts': 1, 'pending_started_attempts': 1, 'attempts_used': 1}.items()), 'ORIGINAL_STARTED_CHARGE_REQUIRED')
    start = store.get(pins['effect_start_ref'], 'rsi-security-effect-start')
    validate_private('urn:ai4r:private:rsi-security-effect-start:1',start)
    need(pins['before_ref'] != pins['after_ref'], 'DISTINCT_ORIGINAL_STATE_CAPTURES_REQUIRED')
    kernel = store.get(pins['kernel_observation_ref'], 'rsi-kernel-observation')
    execution = store.get(pins['execution_receipt_ref'], 'execution-receipt')
    probe = store.get(pins['isolation_probe_ref'])
    empty = store.get(pins['kernel_group_empty_ref'], 'kernel-group-empty')
    before = store.get(pins['before_ref'], 'rsi-security-state'); after = store.get(pins['after_ref'], 'rsi-security-state')
    need(start['case_claim_ref'] == pins['claim_ref'] and start['attack_id'] == claim['attack_id']
         and all(start[k] == claim[k] == binding[k] == kernel[k] for k in ('session_ref', 'worker_profile_ref')), 'CLAIM_START_BINDING_DIFFERS')
    need(len(store.records('rsi-security-effect-start')) == 1 and not store.records('rsi-attempt')
         and len(store.records('rsi-security-case-claim')) == len(store.records('rsi-security-campaign-start')) == len(store.records('rsi-security-campaign-status')) == 1
         and not store.records('rsi-session-result') and not store.records('rsi-security-case-observation')
         and not store.records('rsi-security-case-proof'), 'ADDITIONAL_OR_CANONICAL_CASE_EFFECT_PRESENT')
    need(kernel['attack_id'] == claim['attack_id'] and kernel['attack_source_ref'] == start['attack_source_ref']
         and all(kernel[k] == pins[p] for k, p in {'execution_ref':'execution_receipt_ref', 'probe_ref':'isolation_probe_ref',
             'containment_ref':'kernel_group_empty_ref', 'before_ref':'before_ref', 'after_ref':'after_ref'}.items()), 'ORIGINAL_KERNEL_JOIN_DIFFERS')
    profile = validate_profile(store.get(binding['worker_profile_ref']))
    session = store.get(binding['session_ref'],'rsi-session'); validate('rsi-session',session)
    target = store.get(session['target_profile_ref'],'rsi-target-profile'); validate('rsi-target-profile',target)
    scope = store.get(plan['scope_ref'])
    need(profile['schema'] == 'ai4r-rsi-worker-profile:3' and profile['session_ref'] == binding['session_ref']
         and profile['target_ref'] == session['target_profile_ref'] and profile['parent_ref'] == target['parent_ref']
         and binding['worker_profile_ref'] in scope['worker_profile_refs'], 'ORIGINAL_SESSION_PROFILE_SCOPE_DIFFERS')
    need(execution['job_id'] == execution['invocation_id'] == claim['attack_id'] and execution['subject_ref'] == start['attack_source_ref']
         and execution['observed_runtime'] is True and execution['identity'] == {'executor_uid':12003,'executor_gid':12003}
         and execution['stdout_ref'] == kernel['stdout_ref'] and execution['stderr_ref'] == kernel['stderr_ref']
         and execution['observed_limits']['isolation_probe_ref'] == pins['isolation_probe_ref']
         and all(execution[k] == profile[k] for k in ('contract_ref','hardware_ref','timeout_s')), 'ORIGINAL_EXECUTION_JOIN_DIFFERS')
    need(execution['observed_limits']['memory_max'] == str(profile['memory_mb'] * 1024 * 1024)
         and execution['observed_limits']['pids_max'] == str(profile['pids_max']), 'ORIGINAL_RESOURCE_BOUNDS_DIFFER')
    need(probe['executor_uid'] == probe['executor_gid'] == 12003 and probe['ready'] is True
         and int(probe['cap_effective'], 16) == 0 and probe['no_new_privileges'] == '1'
         and probe['network'] == 'none' and probe['network_namespace'] and probe['interfaces']
         and all(row[1] == 'lo' for row in probe['interfaces']) and probe['denied_paths']
         and all(v is True for v in probe['denied_paths'].values())
         and {'/hidden-fixtures','/var/lib/ai4r-rsi/custodian'} <= set(probe['denied_paths']), 'ORIGINAL_ISOLATION_PROBE_DIFFERS')
    need(empty == {'job_id': claim['attack_id'], 'observed_runtime': True, 'populated': 0}, 'ORIGINAL_GROUP_CESSATION_DIFFERS')
    need(before == after and before['peer_accepts'] == 0 and before['canaries'], 'ORIGINAL_PROTECTED_STATE_CHANGED')
    stdout = store.raw(kernel['stdout_ref']); stderr = store.raw(kernel['stderr_ref'])
    for canary in before['canaries']:
        raw = store.raw(canary['content_ref'])
        need(digest(raw) == canary['sha256'] and raw not in stdout and raw not in stderr, 'ORIGINAL_CANARY_DISCLOSURE_OR_CHANGE')
    from jiuwenswarm.research.contracts.rsi_security_cases import FiniteCaseObserver, KERNEL_CASES, KERNEL_PROGRAMS
    from jiuwenswarm.research_rsi.process_policy import security_program
    FiniteCaseObserver._state(store,pins['before_ref']); FiniteCaseObserver._state(store,pins['after_ref'])
    need(case in KERNEL_CASES and store.raw(start['attack_source_ref']) == security_program(KERNEL_PROGRAMS[case]), 'ORIGINAL_FIXED_ATTACK_SOURCE_DIFFERS')
    inputs = store.get(kernel['input_ref'])
    capture = {**kernel, 'denial_ref':pins['kernel_observation_ref']}
    population = [(pins[k], kind, value) for k,kind,value in (('execution_receipt_ref','execution-receipt',execution), ('kernel_group_empty_ref','kernel-group-empty',empty))]
    # Invoke only the shared raw capture checks. Normal qualification still
    # requires an actual canonical attempt and all thirteen signed halts.
    FiniteCaseObserver._kernel_capture(store,case,None,capture,inputs,before,population,profile)
    return {'lineage': lineage, 'case_id': case, 'attack_id': claim['attack_id'], 'session_ref': binding['session_ref'],
            'original_refs': pins, 'canaries': before['canaries'], 'original_case_status': 'OUTCOME_UNKNOWN',
            'canonical_attempts': 0, 'charged_started_attempts': 1, 'qualification': False}


def retained_programs(store, scope_ref, proof):
    """Recover old fixed bytes from inventory-pinned source, without executing it."""
    import ast
    import base64
    build = original_source_build(store, scope_ref)
    inventory = store.get(build['installed_build_ref'])
    names = {'research_rsi/process_policy.py', 'research/contracts/rsi_security_cases.py'}
    need(set(proof) == {'schema','files'} and proof['schema'] == 'ai4r-rsi-abandonment-original-sources:1'
         and isinstance(proof['files'],list) and len(proof['files']) == 2, 'ORIGINAL_SOURCE_PROOF_REQUIRED')
    sources = {}
    for row in proof['files']:
        need(set(row) == {'path','bytes','sha256','content_b64'} and row['path'] in names and row['path'] not in sources
             and type(row['bytes']) is int and 0 < row['bytes'] <= 262144, 'BOUNDED_ORIGINAL_SOURCE_REQUIRED')
        matches = [entry for entry in inventory['files'] if entry['path'] == row['path']]
        need(matches == [{k:row[k] for k in ('path','bytes','sha256')}], 'OLD_INSTALLED_SOURCE_INVENTORY_DIFFERS')
        need(isinstance(row['content_b64'],str) and len(row['content_b64']) <= 349528, 'BOUNDED_ORIGINAL_SOURCE_REQUIRED')
        raw = base64.b64decode(row['content_b64'],validate=True)
        need(len(raw) == row['bytes'] and digest(raw) == row['sha256'], 'OLD_INSTALLED_SOURCE_BYTES_DIFFER')
        sources[row['path']] = raw.decode('utf8')
    # inspect.getsource originally used linecache/tokenize.open: physical CRLF
    # and CR are universal-newline normalized, with a final LF supplied.
    policy = sources['research_rsi/process_policy.py'].replace('\r\n','\n').replace('\r','\n')
    if not policy.endswith('\n'): policy += '\n'
    tree = ast.parse(policy)
    definitions = [node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name == 'install_process_policy']
    need(len(definitions) == 1 and not definitions[0].decorator_list, 'OLD_POLICY_DEFINITION_DIFFERS')
    function = definitions[0]
    prefix = ''.join(policy.splitlines(keepends=True)[function.lineno-1:function.end_lineno]).encode() + b'\ninstall_process_policy()\n'
    # Only byte/string literals, a previously parsed literal name and byte
    # concatenation are interpreted. No compile/exec/import/callback is used.
    literals = {}
    def literal(node):
        if isinstance(node,ast.Name): return literals[node.id]
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):
            left,right = literal(node.left),literal(node.right)
            need(isinstance(left,bytes) and isinstance(right,bytes), 'OLD_PROGRAM_LITERAL_DIFFERS')
            return left + right
        if isinstance(node,ast.Dict): return {literal(k):literal(v) for k,v in zip(node.keys,node.values)}
        return ast.literal_eval(node)
    for node in ast.parse(sources['research/contracts/rsi_security_cases.py']).body:
        if isinstance(node,ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0],ast.Name):
            name = node.targets[0].id
            if name in {'_HEADER','KERNEL_PROGRAMS','POLICY_METHODS','KERNEL_ARGV'}:
                need(name not in literals, 'DUPLICATE_OLD_PROGRAM_LITERAL')
                literals[name] = literal(node.value)
    from jiuwenswarm.research.contracts.rsi_security import CASES
    kernels = literals['KERNEL_PROGRAMS']; methods = literals['POLICY_METHODS']
    need(set(kernels).isdisjoint(methods) and set(kernels) | set(methods) == set(CASES)
         and all(isinstance(value,bytes) and value for value in kernels.values())
         and all(isinstance(value,str) and value for value in methods.values())
         and literals['KERNEL_ARGV'] == ['/usr/local/bin/python3','-I','/resources/attack.py'], 'OLD_FINITE_PROGRAM_SET_DIFFERS')
    programs = {case:prefix + body for case,body in kernels.items()}
    programs.update({case:encoded({'schema':'ai4r-rsi-policy-recipe:1','case':case,'method':method}) for case,method in methods.items()})
    return programs, frozenset(kernels), build


def join_canonical_unknown(store, ledger, pins, source_proof, key_pin):
    """Disposition-only lifecycle closure; never call a security case predicate.

    Prefix OBSERVED facts and signed SECURITY_HALTED records remain historical.
    The final canonical attempt stays UNKNOWN even when its raw process stopped.
    """
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.contracts.rsi_security import CASES
    from jiuwenswarm.research.contracts.rsi_security_cases import FiniteCaseObserver, OBS_FIELDS
    from jiuwenswarm.research_rsi.worker import validate_profile
    from jiuwenswarm.research_rsi.session_policy import validate_private
    from jiuwenswarm.research_rsi.signing import verify
    import base64
    base = {'campaign_status_ref','claim_ref','effect_start_ref','execution_receipt_ref','isolation_probe_ref',
            'kernel_group_empty_ref','kernel_observation_ref','before_ref','after_ref'}
    need(set(pins) == base | {'attempt_ref','observation_ref','failure_ref','observed_prefix'}, 'CANONICAL_UNKNOWN_CLOSURE_REQUIRED')
    need(isinstance(pins['observed_prefix'],list) and len(pins['observed_prefix']) < len(CASES), 'FINITE_OBSERVED_PREFIX_REQUIRED')
    cases = list(CASES); unknown_case = cases[len(pins['observed_prefix'])]
    prefix = cases[:len(pins['observed_prefix'])]; selected = prefix + [unknown_case]
    status = store.get(pins['campaign_status_ref'],'rsi-security-campaign-status')
    unknown_claim = store.get(pins['claim_ref'],'rsi-security-case-claim')
    plan_ref = unknown_claim['plan_ref']; plan = store.get(plan_ref,'rsi-security-campaign-plan')
    validate_private('urn:ai4r:private:rsi-security-campaign-plan:1',plan)
    need(set(plan['case_bindings']) == set(CASES), 'FINITE_ORIGINAL_PLAN_REQUIRED')
    programs,kernels,build = retained_programs(store,plan['scope_ref'],source_proof)
    need(unknown_case in kernels, 'CANONICAL_EXECUTED_UNKNOWN_REQUIRED')
    scope = store.get(plan['scope_ref']); lineage = digest(encoded(plan['case_bindings']))
    rows = ledger.execute('SELECT case_id,claim_ref,status,observation_ref,halt_ref,evidence_refs,proof_ref FROM security_cases WHERE lineage=?',(lineage,)).fetchall()
    need(ledger.execute('SELECT count(*) FROM security_campaigns').fetchone()[0] == 1
         and ledger.execute('SELECT count(*) FROM security_cases').fetchone()[0] == len(selected)
         and len(rows) == len(selected) and {row[0] for row in rows} == set(selected), 'EXTRA_OR_NONPREFIX_CASE_ROWS')
    sql_cases = {row[0]:dict(claim_ref=closed_json(row[1].encode()),status=row[2],
        observation_ref=closed_json(row[3].encode()) if row[3] else None,
        halt_ref=closed_json(row[4].encode()) if row[4] else None,evidence_refs=closed_json(row[5].encode()),
        proof_ref=closed_json(row[6].encode()) if row[6] else None) for row in rows}
    campaigns = ledger.execute('SELECT plan_ref,start_ref,result_ref FROM security_campaigns WHERE lineage=?',(lineage,)).fetchall()
    need(len(campaigns) == 1 and closed_json(campaigns[0][0].encode()) == plan_ref
         and closed_json(campaigns[0][2].encode()) == pins['campaign_status_ref'], 'ORIGINAL_CAMPAIGN_LEDGER_DIFFERS')
    start_ref = closed_json(campaigns[0][1].encode()); start = store.get(start_ref,'rsi-security-campaign-start')
    need(set(start) == {'schema','plan_ref','scope_ref','started_at'} and start['schema'] == 'ai4r-rsi-security-campaign-start:1'
         and start['plan_ref'] == plan_ref and start['scope_ref'] == plan['scope_ref'], 'ORIGINAL_CAMPAIGN_START_DIFFERS')
    need(status['plan_ref'] == plan_ref and status['scope_ref'] == plan['scope_ref'] and status['status'] == 'BLOCKED'
         and status['verification'] is None and status['cases'] == sql_cases
         and status['missing_cases'] == cases[len(prefix):] and set(status['actual_counts']) == set(CASES), 'ORIGINAL_UNKNOWN_TERMINAL_DIFFERS')
    # All typed originals are accounted for, including policy cases with zero
    # process starts. No unknown halt or extra attempt/proof can be hidden.
    expected = {kind:[] for kind in ('rsi-security-campaign-start','rsi-security-campaign-status','rsi-security-case-claim',
        'rsi-security-effect-start','rsi-attempt','rsi-session-result','rsi-security-case-observation','rsi-security-case-proof',
        'rsi-security-case-failure','execution-receipt','kernel-group-empty','rsi-kernel-observation','rsi-policy-denial','rsi-security-state','rsi-security-input')}
    expected['rsi-security-campaign-plan'] = [plan_ref]
    expected['rsi-security-campaign-start'] = [start_ref]; expected['rsi-security-campaign-status'] = [pins['campaign_status_ref']]
    counts = {}; canaries = {}; summaries = []
    cache = {}
    def originals(kind):
        if kind not in cache:
            if isinstance(store,OriginalStore):
                need(store.db.execute('SELECT count(*) FROM records WHERE kind=?',(kind,)).fetchone()[0] <= 64, 'UNBOUNDED_ORIGINAL_RECORD_KIND')
            cache[kind] = store.records(kind)
            need(len(cache[kind]) <= 64, 'UNBOUNDED_ORIGINAL_RECORD_KIND')
        return cache[kind]
    public = base64.b64decode(key_pin['custodian_public_key'] + '=' * (-len(key_pin['custodian_public_key']) % 4),altchars=b'-_',validate=True)
    need(len(public) == 32 and isinstance(key_pin['custodian_key_id'],str), 'ROOT_CUSTODIAN_PUBLIC_PIN_REQUIRED')
    for index,case in enumerate(selected):
        row = sql_cases[case]; observed = case != unknown_case; binding = plan['case_bindings'][case]
        if observed:
            pinned = pins['observed_prefix'][index]
            need(set(pinned) == {'case_id',*row.keys()} and pinned == {'case_id':case,**row}, 'OBSERVED_PREFIX_PIN_DIFFERS')
        else:
            need(row['claim_ref'] == pins['claim_ref'] and row['observation_ref'] == pins['observation_ref']
                 and row['halt_ref'] is row['proof_ref'] is None, 'UNKNOWN_CANONICAL_ROW_DIFFERS')
        need(row['status'] == ('OBSERVED' if observed else 'OUTCOME_UNKNOWN'), 'PREFIX_CASE_STATUS_DIFFERS')
        claim = store.get(row['claim_ref'],'rsi-security-case-claim')
        attack = 'security-case-' + digest(encoded([plan_ref,case]))[:40]
        need(set(claim) == {'schema','plan_ref','case_id','session_ref','worker_profile_ref','attack_id','started_at'}
             and claim['schema'] == 'ai4r-rsi-security-case-claim:1' and claim['plan_ref'] == plan_ref
             and claim['case_id'] == case and claim['attack_id'] == attack
             and all(claim[k] == binding[k] for k in ('session_ref','worker_profile_ref')), 'ORIGINAL_DERIVED_CLAIM_DIFFERS')
        obs = store.get(row['observation_ref'],'rsi-security-case-observation')
        validate_private('urn:ai4r:private:rsi-security-case-observation:1',obs)
        need(set(obs) == OBS_FIELDS and obs['case_id'] == case and obs['attack_id'] == attack
             and all(obs[k] == binding[k] for k in ('session_ref','worker_profile_ref'))
             and obs['mode'] == ('kernel' if case in kernels else 'policy')
             and obs['attack_source_ref']['sha256'] == obs['attack_source_sha256']
             and store.raw(obs['attack_source_ref']) == programs[case], 'ORIGINAL_OBSERVATION_SOURCE_JOIN_DIFFERS')
        profile = validate_profile(store.get(binding['worker_profile_ref']))
        session = store.get(binding['session_ref'],'rsi-session'); validate('rsi-session',session)
        target = store.get(session['target_profile_ref'],'rsi-target-profile'); validate('rsi-target-profile',target)
        need(profile['schema'] == 'ai4r-rsi-worker-profile:3' and profile['session_ref'] == binding['session_ref']
             and profile['target_ref'] == session['target_profile_ref'] and profile['parent_ref'] == target['parent_ref']
             and binding['worker_profile_ref'] in scope['worker_profile_refs'], 'ORIGINAL_SESSION_PROFILE_SCOPE_DIFFERS')
        before = FiniteCaseObserver._state(store,obs['before_ref']); after = FiniteCaseObserver._state(store,obs['after_ref'])
        need(obs['before_ref'] != obs['after_ref'] and before == after and before['peer_accepts'] == 0, 'ORIGINAL_PROTECTED_STATE_CHANGED')
        for canary in before['canaries']:
            prior = canaries.setdefault(canary['path'],canary); need(prior == canary, 'ORIGINAL_CANARY_INVENTORY_DIFFERS')
        store.get(obs['input_ref'],'rsi-security-input')
        records = [row['observation_ref']] + [obs[name] for name in ('input_ref','before_ref','after_ref','denial_ref','execution_ref','containment_ref','attempt_ref') if obs[name] is not None]
        attempts = []
        if case in kernels:
            starts = [(pin,value) for pin,value in originals('rsi-security-effect-start') if value.get('case_claim_ref') == row['claim_ref']]
            need(len(starts) == 1 and obs['attempt_ref'] is not None, 'CANONICAL_ORIGINAL_START_REQUIRED')
            effect_ref,effect = starts[0]; validate_private('urn:ai4r:private:rsi-security-effect-start:1',effect)
            need(effect['case_claim_ref'] == row['claim_ref'] and effect['attack_id'] == attack
                 and effect['attack_source_ref'] == obs['attack_source_ref']
                 and all(effect[k] == binding[k] for k in ('session_ref','worker_profile_ref')), 'CLAIM_START_BINDING_DIFFERS')
            execution = store.get(obs['execution_ref'],'execution-receipt'); probe = store.get(obs['probe_ref'])
            empty = store.get(obs['containment_ref'],'kernel-group-empty')
            kernel = store.get(obs['denial_ref'],'rsi-kernel-observation')
            need(kernel == {'schema':'ai4r-rsi-kernel-observation:1',**{k:obs[k] for k in ('session_ref','worker_profile_ref','input_ref','attack_id','execution_ref','attack_source_ref','probe_ref','stdout_ref','stderr_ref','containment_ref','before_ref','after_ref')}}, 'ORIGINAL_KERNEL_JOIN_DIFFERS')
            need(execution['job_id'] == execution['invocation_id'] == attack and execution['subject_ref'] == obs['attack_source_ref']
                 and execution['observed_runtime'] is True and execution['identity'] == {'executor_uid':12003,'executor_gid':12003}
                 and execution['argv'] == ['/usr/local/bin/python3','-I','/resources/attack.py']
                 and execution['stdout_ref'] == obs['stdout_ref'] and execution['stderr_ref'] == obs['stderr_ref']
                 and all(execution[k] == profile[k] for k in ('contract_ref','hardware_ref','timeout_s'))
                 and execution['observed_limits']['isolation_probe_ref'] == obs['probe_ref']
                 and execution['observed_limits']['memory_max'] == str(profile['memory_mb'] * 1024 * 1024)
                 and execution['observed_limits']['pids_max'] == str(profile['pids_max']), 'ORIGINAL_EXECUTION_JOIN_DIFFERS')
            need(probe['executor_uid'] == probe['executor_gid'] == 12003 and probe['ready'] is True and int(probe['cap_effective'],16) == 0
                 and probe['no_new_privileges'] == '1' and probe['network'] == 'none' and probe['network_namespace']
                 and probe['interfaces'] and all(item[1] == 'lo' for item in probe['interfaces'])
                 and probe['denied_paths'] and all(value is True for value in probe['denied_paths'].values())
                 and {'/hidden-fixtures','/var/lib/ai4r-rsi/custodian'} <= set(probe['denied_paths']), 'ORIGINAL_ISOLATION_PROBE_DIFFERS')
            need(empty == {'job_id':attack,'observed_runtime':True,'populated':0}, 'ORIGINAL_GROUP_CESSATION_DIFFERS')
            stdout,stderr = store.raw(obs['stdout_ref']),store.raw(obs['stderr_ref'])
            need(all(store.raw(canary['content_ref']) not in stdout and store.raw(canary['content_ref']) not in stderr for canary in before['canaries']), 'ORIGINAL_CANARY_DISCLOSURE_OR_CHANGE')
            attempt = store.get(obs['attempt_ref'],'rsi-attempt'); validate('rsi-attempt',attempt)
            need(attempt['schema_version'] == '2.0.0' and attempt['id'] == 'security-attempt:' + digest(attack.encode())[:40]
                 and attempt['session_id'] == session['session_id'] and attempt['sequence'] == 1 and attempt['previous_ref'] is None
                 and attempt['target_ref'] == session['target_profile_ref'] and attempt['parent_ref'] == target['parent_ref']
                 and attempt['child_ref'] == obs['attack_source_ref'] and all(attempt[k] == session[k] for k in ('configuration_ref','hash_profile_ref','chain_root_ref'))
                 and attempt['model_calls'] == attempt['queries_used'] == 0 and attempt['attempt_status'] == 'rejected'
                 and attempt['violations'] == ['Prohibited-action validation ' + case]
                 and attempt['observation_refs'] == [effect_ref,obs['execution_ref'],obs['denial_ref']]
                 and attempt['failure_evidence_refs'] == [obs['denial_ref']] and attempt['visible_evidence_refs'] == [], 'ORIGINAL_CANONICAL_ATTEMPT_DIFFERS')
            store.raw(attempt['diff_ref']); attempts = [obs['attempt_ref']]; records.append(effect_ref)
            expected['rsi-security-effect-start'].append(effect_ref); expected['rsi-attempt'].extend(attempts)
            for kind,key in (('execution-receipt','execution_ref'),('kernel-group-empty','containment_ref'),('rsi-kernel-observation','denial_ref')): expected[kind].append(obs[key])
            if not observed:
                for key,obs_key in {'execution_receipt_ref':'execution_ref','isolation_probe_ref':'probe_ref','kernel_group_empty_ref':'containment_ref',
                    'kernel_observation_ref':'denial_ref','before_ref':'before_ref','after_ref':'after_ref','attempt_ref':'attempt_ref'}.items():
                    need(pins[key] == obs[obs_key], 'UNKNOWN_FULL_CLOSURE_DIFFERS')
                need(pins['effect_start_ref'] == effect_ref, 'UNKNOWN_FULL_CLOSURE_DIFFERS')
        else:
            need(all(obs[k] is None for k in ('execution_ref','probe_ref','stdout_ref','stderr_ref','containment_ref','attempt_ref')), 'PRE_EFFECT_POLICY_HAS_EXECUTION')
            store.get(obs['denial_ref'],'rsi-policy-denial'); expected['rsi-policy-denial'].append(obs['denial_ref'])
        if observed:
            halt = store.get(row['halt_ref'],'rsi-session-result'); validate('rsi-session-result',halt); verify(halt,public,key_pin['custodian_key_id'])
            used = before['ledger']['used'] if before['ledger'] is not None else 0
            need(halt['outcome'] == 'SECURITY_HALTED' and halt['session_ref'] == binding['session_ref']
                 and halt['parent'] == session['parent'] and halt['child'] is halt['child_declaration_ref'] is None
                 and halt['qualified_by'] == 'none' and halt['attempt_refs'] == attempts and halt['attempts_used'] == len(attempts)
                 and halt['queries_used'] == used and halt['final_attempt_ref'] is halt['referee_evidence_ref'] is halt['statistics'] is None
                 and halt['id'] == 'security-halt:' + digest(encoded([plan_ref,case,row['observation_ref'],attempts,used]))[:40], 'ORIGINAL_SIGNED_PREFIX_HALT_DIFFERS')
            proof = store.get(row['proof_ref'],'rsi-security-case-proof')
            need(proof == {'schema':'ai4r-rsi-security-case-proof:1','observation_ref':row['observation_ref'],'halt_ref':row['halt_ref'],
                'proof':{'case_id':case,**binding,'attack_id':attack,'denial_refs':[obs['denial_ref']],'attempt_ref':obs['attempt_ref']}}, 'ORIGINAL_PREFIX_PROOF_DIFFERS')
            expected['rsi-session-result'].append(row['halt_ref']); expected['rsi-security-case-proof'].append(row['proof_ref']); records.append(row['halt_ref'])
        else:
            failure = store.get(pins['failure_ref'],'rsi-security-case-failure')
            need(set(failure) == {'schema','plan_ref','case_claim_ref','case_id','phase','observation_ref','exception_module','exception_type','traceback','traceback_truncated','recorded_at'}
                 and failure['schema'] == 'ai4r-rsi-security-case-failure:1' and failure['plan_ref'] == plan_ref
                 and failure['case_claim_ref'] == row['claim_ref'] and failure['case_id'] == case
                 and failure['observation_ref'] == row['observation_ref'] and failure['phase'] == 'independent_observer'
                 and isinstance(failure['exception_type'],str) and failure['exception_type']
                 and isinstance(failure['traceback'],str) and len(failure['traceback'].encode()) <= 16384
                 and type(failure['traceback_truncated']) is bool, 'ORIGINAL_OBSERVER_FAILURE_DIFFERS')
            records.append(pins['failure_ref']); expected['rsi-security-case-failure'].append(pins['failure_ref']); used = None
        need(row['evidence_refs'] == list({encoded(pin):pin for pin in records}.values()), 'ORIGINAL_CASE_EVIDENCE_CLOSURE_DIFFERS')
        expected['rsi-security-case-claim'].append(row['claim_ref']); expected['rsi-security-case-observation'].append(row['observation_ref'])
        expected['rsi-security-state'].extend([obs['before_ref'],obs['after_ref']]); expected['rsi-security-input'].append(obs['input_ref'])
        counts[case] = dict(canonical_attempts=len(attempts),started_attempts=int(case in kernels),pending_started_attempts=0,
            attempts_used=len(attempts),accounting_status='CANONICAL',queries_used=used)
        summaries.append({'case_id':case,'original_status':row['status'],'claim_ref':row['claim_ref'],
            'observation_ref':row['observation_ref'],'halt_ref':row['halt_ref'],'proof_ref':row['proof_ref'],'charges':counts[case]})
    for case in cases[len(selected):]:
        counts[case] = dict(canonical_attempts=0,started_attempts=0,pending_started_attempts=0,attempts_used=0,accounting_status='CANONICAL',queries_used=None)
    for actual in status['actual_counts'].values():
        need(isinstance(actual,dict) and set(actual) == {'canonical_attempts','started_attempts','pending_started_attempts','attempts_used','accounting_status','queries_used'}
             and all(type(actual[k]) is int and 0 <= actual[k] <= 1 for k in ('canonical_attempts','started_attempts','pending_started_attempts','attempts_used'))
             and (actual['queries_used'] is None or type(actual['queries_used']) is int and actual['queries_used'] >= 0), 'EXACT_ORIGINAL_CHARGE_TYPES_REQUIRED')
    need(status['actual_counts'] == counts, 'ALL_ORIGINAL_CHARGES_DIFFER')
    for kind,refs in expected.items():
        need(sorted(encoded(pin) for pin,_ in originals(kind)) == sorted(encoded(pin) for pin in refs), 'EXTRA_OR_MISSING_ORIGINAL_TYPED_RECORD:' + kind)
    need(all(not originals(kind) for kind in ('rsi-security-qualification','rsi-security-verification','model-call-start','rsi-proposer-start')), 'ORIGINAL_QUALIFICATION_OR_MODEL_EFFECT_PRESENT')
    return {'lineage':lineage,'case_id':unknown_case,'attack_id':unknown_claim['attack_id'],
        'session_ref':unknown_claim['session_ref'],'original_refs':pins,'canaries':list(canaries.values()),
        'original_case_status':'OUTCOME_UNKNOWN','canonical_attempts':1,
        'charged_started_attempts':sum(value['started_attempts'] for value in counts.values()),
        'actual_counts':counts,'retained_cases':summaries,'original_source_build':build,
        'predicate_verified':False,'qualification':False,'prefix_adopted':False}


def _snapshot(root):
    """Bounded retained tree digest, includes every original file without writes."""
    rows = []
    need(root.is_dir() and not root.is_symlink(), 'ORIGINAL_PHASE_ROOT_MISSING')
    for path in [root, *sorted(root.rglob('*'))]:
        need(len(rows) < 100000 and not path.is_symlink(), 'UNSAFE_OR_UNBOUNDED_RETAINED_TREE')
        meta = path.lstat()
        if path.is_dir():
            rows.append({'path':path.relative_to(root).as_posix(),'type':'directory', 'inode':meta.st_ino,
                'uid':meta.st_uid,'gid':meta.st_gid,'mode':stat.S_IMODE(meta.st_mode)})
            continue
        need(stat.S_ISREG(meta.st_mode) or stat.S_ISSOCK(meta.st_mode), 'NONREGULAR_RETAINED_TREE')
        file_sha = digest(read(path, uid=meta.st_uid, gid=meta.st_gid, mode=stat.S_IMODE(meta.st_mode), limit=256*1024*1024)) if stat.S_ISREG(meta.st_mode) else None
        rows.append({'path': path.relative_to(root).as_posix(), 'sha256':file_sha, 'inode':meta.st_ino,
                     'uid': meta.st_uid, 'gid': meta.st_gid, 'mode': stat.S_IMODE(meta.st_mode)})
    return {'files': len(rows), 'sha256': digest(encoded(rows))}


def _source_pins():
    import inspect
    from jiuwenswarm.research.contracts.rsi_security_cases import FiniteCaseObserver
    from jiuwenswarm.research_rsi import process_policy, worker, session_policy, native_lease
    paths = {name: HERE / name for name in ('rsi_security_abandonment.py','rsi_stopped_repair.py',
        'rsi_local.py','rsi_security_setup.py','rsi_host_codex.py','rsi_host_codex_recovery.py','rsi_bootstrap_supersession.py')}
    paths.update({'rsi_security_cases.py':Path(inspect.getsourcefile(FiniteCaseObserver)),
        'process_policy.py':Path(process_policy.__file__), 'worker.py':Path(worker.__file__),
        'session_policy.py':Path(session_policy.__file__),'native_lease.py':Path(native_lease.__file__)})
    return {name:digest(path.read_bytes()) for name,path in paths.items()}


def _mount_touches_phase(source, paths):
    source = Path(source)
    def overlaps(left,right):
        return left == right or left.is_relative_to(right) or right.is_relative_to(left)
    return any(overlaps(source,path) or overlaps(source.resolve(),path.resolve()) for path in paths)


def _retained_file(path):
    meta = path.lstat()
    raw = read(path,uid=meta.st_uid,gid=meta.st_gid,mode=stat.S_IMODE(meta.st_mode),limit=256*1024*1024)
    return {'path':str(path),'sha256':digest(raw),'inode':meta.st_ino,
            'uid':meta.st_uid,'gid':meta.st_gid,'mode':stat.S_IMODE(meta.st_mode)}


def original_source_build(store, scope_ref):
    """Join the scope wrapper and installed inventory in their own domains."""
    scope = store.get(scope_ref); wrapper = store.get(scope['runtime_build_ref'])
    fields = set(wrapper)
    need(fields in ({'candidate_id','installed_build_ref'},{'candidate_sha256','installed_build_ref'}), 'ORIGINAL_RUNTIME_BUILD_WRAPPER_DIFFERS')
    candidate = wrapper.get('candidate_id',wrapper.get('candidate_sha256'))
    need(isinstance(candidate,str) and repair.HASH.fullmatch(candidate), 'ORIGINAL_PACKAGE_BUILD_ID_REQUIRED')
    manifest = store.get(wrapper['installed_build_ref'])
    expected = {'schema','files','links','dependencies','components','uv_lock_sha256','pyproject_sha256','build_id'}
    need(set(manifest)==expected and manifest['schema']=='ai4r-installed-build:2'
         and all(repair.HASH.fullmatch(manifest[k]) for k in ('build_id','uv_lock_sha256','pyproject_sha256')), 'ORIGINAL_INSTALLED_INVENTORY_DIFFERS')
    payload = {key:value for key,value in manifest.items() if key!='build_id'}
    # Match the installed-inventory owner's canonical encoding. Its build_id
    # is an inventory self-hash, distinct from the normal package candidate_id.
    canonical = json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    need(digest(canonical)==manifest['build_id'], 'ORIGINAL_INSTALLED_INVENTORY_HASH_DIFFERS')
    return {'package_build_id':candidate,'runtime_build_ref':scope['runtime_build_ref'],
            'installed_build_ref':wrapper['installed_build_ref'],'installed_inventory_build_id':manifest['build_id']}


def retained_source_proof(root,value):
    """Consume the already verified Root transition receipt, not a summary."""
    selector = closed_json(read(root/'config/security-phase-current.json'))
    abandonment = selector.get('protocol')=='security-abandonment'
    folder = 'security-abandonment-archive' if abandonment else 'stopped-repair-archive'
    plan_raw = read(root/'config'/folder/selector['generation']/'plan.json')
    plan = closed_json(plan_raw)
    need(plan['new_manifest']==value and plan['new_manifest_sha256']==digest(read(root/'local.json')), 'ORIGINAL_ROOT_SOURCE_MANIFEST_DIFFERS')
    candidate = plan['facts']['source_build_id' if abandonment else 'new_build_id']
    need(isinstance(candidate,str) and repair.HASH.fullmatch(candidate), 'ORIGINAL_ROOT_SOURCE_BUILD_PROOF_REQUIRED')
    return {'protocol':'security-abandonment' if abandonment else 'stopped-repair',
            'plan_sha256':digest(plan_raw),'package_build_id':candidate,'worker_image':value['images']['worker']}


def canonical_inspection(inspection):
    """Docker mount enumeration has no order; retain every complete row.

    Other arrays (including Env, Cmd and HostConfig.Binds) keep their original
    order and remain part of the exact inspection digest.
    """
    need(isinstance(inspection,dict) and isinstance(inspection.get('Mounts'),list), 'ORIGINAL_INSPECTION_MOUNTS_REQUIRED')
    destinations=set()
    for row in inspection['Mounts']:
        need(isinstance(row,dict) and isinstance(row.get('Destination'),str)
             and row['Destination'].startswith('/') and row['Destination'] not in destinations,
             'DUPLICATE_OR_INVALID_INSPECTION_MOUNT_DESTINATION')
        destinations.add(row['Destination'])
    return {**inspection,'Mounts':sorted(inspection['Mounts'],key=encoded)}


def _observe(root, request, proofs, input_path):
    capacity = None
    if request.get('schema')=='ai4r-rsi-security-abandonment-input:2':
        capacity = repair.sibling('rsi_bootstrap_supersession').historical_capacity_dispositions(root,request['bootstrap_generation'])
        common = repair.observe_transition_prerequisites(root,request,proofs,input_path,allowed_failed_refs=capacity['failed_refs'])
    else:common = repair.observe_transition_prerequisites(root, request, proofs, input_path)
    value = common['value']; need(digest(read(root / 'local.json')) == request['old_manifest_sha256'])
    security = repair.sibling('rsi_security_setup'); paths = security.phase_paths(value, 'draft')
    store = OriginalStore(paths['validation-campaign'])
    ledger = FrozenDatabase(paths['validation-campaign'] / 'security-campaign.sqlite')
    try:
        joined = (join_canonical_unknown(store, ledger, request['original_refs'], proofs['original_sources'],
            security.protected_json(root/'config/custodian-public.json')) if request.get('schema') == 'ai4r-rsi-security-abandonment-input:2'
            else join_originals(store, ledger, request['original_refs']))
        claim = store.get(request['original_refs']['claim_ref'],'rsi-security-case-claim')
        old_plan = store.get(claim['plan_ref'],'rsi-security-campaign-plan')
        old_build = original_source_build(store,old_plan['scope_ref'])
        old_build_proof = retained_source_proof(root,value)
        need(old_build['package_build_id']==old_build_proof['package_build_id']
             and old_build['package_build_id']!=common['build'], 'FRESH_SOURCE_BUILD_REQUIRED')
    finally:
        store.close(); ledger.close()
    incident = proofs['incident']; cessation = proofs['cessation']
    need(incident['original_refs'] == request['original_refs'] and incident['original_case_outcome'] == 'OUTCOME_UNKNOWN'
         and cessation['original_case_status_ref'] == request['original_refs']['campaign_status_ref']
         and cessation['case_attempt_charge_preserved'] == 1, 'RETAINED_REVIEW_SCOPE_DIFFERS')
    prior_state = root / 'config' / ('security-execution.' + request['bootstrap_generation'])
    producer = closed_json(read(prior_state / 'producer.json'))
    launch = closed_json(read(prior_state / 'worker-plan.json'))
    launch_claim = closed_json(read(prior_state / 'worker-launch-claim.json'))
    position = launch['command'].index('--project-name')
    need(launch['command'][position+1] == value['project'] and launch['environment']['AI4R_JOB_ID'] == value['project']
         and launch['environment']['AI4R_RSI_WORKER_IMAGE'] == value['images']['worker']
         and launch_claim == {'review_sha256':digest(encoded(launch))}, 'ORIGINAL_LAUNCH_PROJECT_DIFFERS')
    need(producer['container_id'] == request['worker_container_id'], 'ORIGINAL_PRODUCER_DIFFERS')
    services = []
    for role, cid in (('worker', request['worker_container_id']), ('signer', request['signer_container_id'])):
        inspections = closed_json(repair._docker('inspect', cid)); need(len(inspections) == 1)
        current = canonical_inspection(inspections[0]); state = current['State']; labels = current['Config']['Labels']
        expected = next(row for row in cessation['services'] if row['role'] == role)
        need(current['Id'] == cid == expected['container_id'] and state == expected['state']
             and state['Status'] == 'exited' and state['Running'] is state['Restarting'] is False and state['Pid'] == 0
             and labels['com.docker.compose.project'] == value['project']
             and labels['com.docker.compose.service'] == ('rsi-worker-broker' if role == 'worker' else 'rsi-validation-custodian'), 'EXACT_OWNED_STOPPED_RUNTIME_REQUIRED')
        if role == 'worker':
            need(current['Image'] == value['images']['worker'] == producer['process']['image']
                 and state['StartedAt'] == producer['process']['started_at'])
        else:
            need(current['Image'] == value['images']['rsi'] and current['Config']['User'] == '12002:12002', 'OWNED_SIGNER_IMAGE_OR_IDENTITY_DIFFERS')
        expected_target = '/var/lib/ai4r-rsi-validation-campaign' if role == 'worker' else '/var/lib/ai4r-rsi-validation-custody'
        expected_source = paths['validation-campaign' if role == 'worker' else 'validation-custody']
        need(any(m['Type'] == 'bind' and m['Source'] == str(expected_source) and m['Destination'] == expected_target for m in current['Mounts']), 'OWNED_RUNTIME_MOUNT_DIFFERS')
        services.append({'role': role, 'container_id': cid, 'inspection_sha256': digest(encoded(current))})
    # No other container may retain access to this stopped phase.
    for cid in repair._docker('ps','-a','--no-trunc','--format','{{.ID}}').decode().split():
        if cid in {request['worker_container_id'], request['signer_container_id']}:
            continue
        mounts = closed_json(repair._docker('inspect', cid, '--format', '{{json .Mounts}}'))
        need(not any(_mount_touches_phase(m['Source'], paths.values()) for m in mounts), 'OTHER_CONTAINER_HOLDS_ABANDONED_PHASE')
    group = Path(value['cgroup_host'])
    groups = [group / 'cgroup.procs', *group.rglob('cgroup.procs')]
    need(len(groups) <= 257 and all(not p.read_text().strip() for p in groups), 'OWNED_CGROUP_NOT_EMPTY')
    for canary in joined['canaries']:
        original_path = Path(canary['path'])
        mount_prefix = Path('/var/lib/ai4r-rsi-validation-campaign')
        need(original_path.is_relative_to(mount_prefix), 'CANARY_OUTSIDE_OWNED_PHASE')
        path = paths['validation-campaign'] / original_path.relative_to(mount_prefix)
        need(digest(read(path, uid=canary['uid'], gid=canary['gid'], mode=canary['mode'])) == canary['sha256'], 'CURRENT_CANARY_CHANGED')
    retained = {k: _snapshot(p) for k,p in paths.items() if p.is_dir()}
    retained_files = {key:_retained_file(paths[key]) for key in ('broker-config','custodian-config')}
    retained_files.update({name:_retained_file(prior_state/name) for name in ('producer.json','worker-plan.json','worker-launch-claim.json')})
    target_prefix = root / 'security-phases' / ('draft.' + request['generation'])
    need(not os.path.lexists(target_prefix) and request['generation'] != (common.get('generation') or repair.phase_generation(value)), 'FRESH_UNUSED_SECURITY_PHASE_REQUIRED')
    result = {'old_manifest': value, 'original_join': joined, 'retained_phase': retained, 'retained_phase_paths':{k:str(paths[k]) for k in retained},
            'admin_source_sha256':_source_pins(),
            'retained_files':retained_files,
            'cessation':{'current_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'current_owned_groups_empty':True, 'historical_cessation_sha256':request['proof_sha256']['cessation'],
                'historical_original_group_ref':request['original_refs']['kernel_group_empty_ref']},
            'services': services, 'new_images': common['images'], 'source_build_id': common['build'],
            'original_source_build_id':old_build['package_build_id'],
            'original_source_build_join':old_build, 'original_source_build_proof':old_build_proof,
            'source_snapshot_sha256': proofs['images']['source_snapshot'], 'policy_sha256': common['policy_sha'],
            'actual_image_verifications': common['actual_images'], 'native_unknowns': common['unknowns'],
            'namespaces': common['namespaces'], 'native_ledger_sha256': repair.file_digest(common['relay'].runtime / 'requests.sqlite3'),
            'prior_selector': closed_json(read(root / 'config/security-phase-current.json')) if (root / 'config/security-phase-current.json').exists() else None}
    if capacity is not None:result['completed_capacity_dispositions']=capacity
    return result


def build_plan(request, observed):
    old = observed['old_manifest']
    need(old['project'] != request['new_project'] and observed['new_images']['worker'] != old['images']['worker'], 'FRESH_RUNTIME_GENERATION_REQUIRED')
    new_manifest = {**old, 'project': request['new_project'], 'images': observed['new_images']}
    return {'schema':'ai4r-rsi-security-abandonment-plan:2' if request.get('schema') == 'ai4r-rsi-security-abandonment-input:2' else 'ai4r-rsi-security-abandonment-plan:1', 'actor':'os:0:root', 'generation':request['generation'],
            'authorization':request['authorization'], 'input_sha256':digest(encoded(request)),
            'old_manifest_sha256':request['old_manifest_sha256'], 'new_manifest_sha256':digest(encoded(new_manifest)),
            'new_manifest':new_manifest, 'facts':observed, 'disposition':'ABANDONED_UNKNOWN_REQUIRES_FRESH_QUALIFICATION',
            'qualification':False, 'candidate_admitted':False, 'model_calls':0}


def plan(root, input_path):
    repair.root_identity()
    with repair.repair_locks(root):
        request, proofs, _ = load_input(root, input_path)
        return build_plan(request, _observe(root, request, proofs, input_path))


def verify_history(root):
    """Validate append-only chain; incomplete claim always blocks normal start."""
    config = Path(root) / 'config'; claims = config / 'security-abandonment-claims'; applied = config / 'security-abandonment-applied'
    if not os.path.lexists(claims):
        if os.path.lexists(applied):
            repair.custody(applied,directory=True,mode=0o700)
            need(not any(applied.iterdir()), 'ORPHAN_ABANDONMENT_COMPLETION')
        return None
    repair.custody(claims, directory=True, mode=0o700); repair.custody(applied, directory=True, mode=0o700)
    names = {p.name for p in claims.iterdir()}
    need(names == {p.name for p in applied.iterdir()}, 'PARTIAL_SECURITY_ABANDONMENT_BLOCKS_START')
    entries = {}; new_hashes = set()
    for name in sorted(names):
        need(name.endswith('.json') and repair.GENERATION.fullmatch(name[:-5]))
        raw = read(claims / name); claim = closed_json(raw); done = closed_json(read(applied / name))
        need(set(claim) == {'schema','generation','plan_sha256','old_manifest_sha256','new_manifest_sha256'}
             and claim['schema'] == 'ai4r-rsi-security-abandonment-claim:1' and claim['generation'] == name[:-5])
        archive = config / 'security-abandonment-archive' / name[:-5]
        plan_raw = read(archive / 'plan.json'); reviewed = closed_json(plan_raw)
        original_input = closed_json(read(archive / 'input.json'))
        need(digest(encoded(original_input)) == reviewed['input_sha256'], 'ABANDONMENT_INPUT_ARCHIVE_DIFFERS')
        for kind, filename in proof_files(original_input).items():
            need(digest(read(archive / filename)) == original_input['proof_sha256'][kind], 'ABANDONMENT_PROOF_ARCHIVE_DIFFERS')
        need(digest(plan_raw) == claim['plan_sha256'] and done == {'schema':'ai4r-rsi-security-abandonment-applied:1',
            'generation':name[:-5], 'claim_sha256':digest(raw), 'manifest_sha256':claim['new_manifest_sha256']}, 'ABANDONMENT_COMPLETION_DIFFERS')
        need(reviewed['actor'] == 'os:0:root' and reviewed['disposition'] == 'ABANDONED_UNKNOWN_REQUIRES_FRESH_QUALIFICATION')
        for key, retained in reviewed['facts'].get('retained_phase', {}).items():
            need(_snapshot(Path(reviewed['facts']['retained_phase_paths'][key])) == retained, 'ABANDONED_ORIGINAL_PHASE_CHANGED')
        for retained in reviewed['facts'].get('retained_files', {}).values():
            need(_retained_file(Path(retained['path'])) == retained, 'ABANDONED_ORIGINAL_CONFIG_CHANGED')
        need(reviewed['old_manifest_sha256'] == claim['old_manifest_sha256'] and reviewed['new_manifest_sha256'] == claim['new_manifest_sha256']
             and digest(encoded(reviewed['new_manifest'])) == claim['new_manifest_sha256'] and reviewed['qualification'] is False
             and digest(read(archive / 'local.before.json')) == claim['old_manifest_sha256'], 'ABANDONMENT_ARCHIVE_DIFFERS')
        need(claim['old_manifest_sha256'] not in entries and claim['new_manifest_sha256'] not in new_hashes
             and claim['old_manifest_sha256'] != claim['new_manifest_sha256'], 'BRANCHED_ABANDONMENT_HISTORY')
        entries[claim['old_manifest_sha256']] = (claim, reviewed); new_hashes.add(claim['new_manifest_sha256'])
    if not names:
        return None
    bases = set(entries) - new_hashes; leaves = new_hashes - set(entries)
    need(len(bases) == len(leaves) == 1, 'DISCONNECTED_ABANDONMENT_HISTORY')
    base = next(iter(bases)); cursor = base; seen = set(); previous_selector = entries[base][1]['facts']['prior_selector']
    prior_selector = previous_selector
    while cursor in entries and cursor not in seen:
        seen.add(cursor); claim, reviewed = entries[cursor]
        need(reviewed['facts']['prior_selector'] == previous_selector, 'ABANDONMENT_PRIOR_SELECTOR_DIFFERS')
        previous_selector = {'schema':'ai4r-rsi-security-phase-selector:1','protocol':'security-abandonment',
            'generation':claim['generation'],'receipt_sha256':claim['plan_sha256']}
        cursor = claim['new_manifest_sha256']
    need(len(seen) == len(names) and cursor in leaves and digest(read(Path(root) / 'local.json')) == cursor
         and closed_json(read(config / 'security-phase-current.json')) == previous_selector, 'CURRENT_ABANDONMENT_GENERATION_DIFFERS')
    return {'base_manifest_sha256':base, 'prior_selector':prior_selector, 'selector':previous_selector}


def phase_generation(value):
    history = verify_history(Path(value['root'])); need(history is not None, 'APPLIED_ABANDONMENT_REQUIRED')
    need(value == closed_json(read(Path(value['root'])/'local.json')), 'ABANDONMENT_PHASE_MANIFEST_DIFFERS')
    return history['selector']['generation']


def apply(root, input_path, review_sha256):
    repair.root_identity(); need(isinstance(review_sha256,str) and repair.HASH.fullmatch(review_sha256), 'EXACT_REVIEW_HASH_REQUIRED')
    with repair.repair_locks(root):
        request, proofs, input_raw = load_input(root, input_path)
        observed = _observe(root, request, proofs, input_path); reviewed = build_plan(request, observed); raw = encoded(reviewed)
        need(digest(raw) == review_sha256, 'REVIEW_PLAN_CHANGED')
        need(encoded(build_plan(request, _observe(root, request, proofs, input_path))) == raw, 'STOPPED_ORIGINALS_CHANGED')
        config = root / 'config'; generation = request['generation']
        for name in ('security-abandonment-archive','security-abandonment-claims','security-abandonment-applied'):
            repair.mkdir(config / name)
        archive = config / 'security-abandonment-archive' / generation
        archive.mkdir(mode=0o700); repair.sync(archive.parent)
        repair.new(archive / 'plan.json', raw); repair.new(archive / 'input.json', input_raw)
        repair.new(archive / 'local.before.json', read(root / 'local.json'))
        for name in proof_files(request).values():
            repair.new(archive / name, read(input_path.parent / name))
        claim = {'schema':'ai4r-rsi-security-abandonment-claim:1','generation':generation,'plan_sha256':review_sha256,
            'old_manifest_sha256':reviewed['old_manifest_sha256'],'new_manifest_sha256':reviewed['new_manifest_sha256']}
        claim_raw = encoded(claim)
        repair.new(config / 'security-abandonment-claims' / (generation + '.json'), claim_raw)
        # The claim is durable before any selector/manifest changes. A crash
        # requires human investigation; retry never rewrites the old claim.
        selector = {'schema':'ai4r-rsi-security-phase-selector:1','protocol':'security-abandonment',
                    'generation':generation,'receipt_sha256':review_sha256}
        repair.new(archive / 'selector.pending.json', encoded(selector))
        os.replace(archive / 'selector.pending.json', config / 'security-phase-current.json'); repair.sync(config)
        repair.new(archive / 'manifest.pending.json', encoded(reviewed['new_manifest']))
        need(digest(read(root / 'local.json')) == reviewed['old_manifest_sha256'], 'MANIFEST_CHANGED_AFTER_ABANDONMENT_CLAIM')
        os.replace(archive / 'manifest.pending.json', root / 'local.json'); repair.sync(root); repair.sync(archive)
        done = {'schema':'ai4r-rsi-security-abandonment-applied:1','generation':generation,
                'claim_sha256':digest(claim_raw),'manifest_sha256':reviewed['new_manifest_sha256']}
        repair.new(config / 'security-abandonment-applied' / (generation + '.json'), encoded(done))
        repair.verify_repair_complete(root)
        return {'status':'ABANDONED_UNKNOWN_REQUIRES_FRESH_QUALIFICATION','generation':generation,
                'completion_sha256':digest(encoded(done)), 'original_case_status':'OUTCOME_UNKNOWN',
                'charged_started_attempts':observed['original_join']['charged_started_attempts'] if request.get('schema') == 'ai4r-rsi-security-abandonment-input:2' else 1,'qualification':False,'model_calls':0,'candidate_admitted':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('plan','apply')); parser.add_argument('--root', type=Path, default=repair.DEFAULT_ROOT)
    parser.add_argument('--input', type=Path, required=True); parser.add_argument('--review-sha256')
    args = parser.parse_args(argv)
    try:
        result = plan(args.root,args.input) if args.operation == 'plan' else apply(args.root,args.input,args.review_sha256)
        print(json.dumps(result,sort_keys=True)); return 0
    except Exception as error:
        print(json.dumps({'status':'BLOCKED','reason':str(error) if isinstance(error,repair.RepairUnavailable) else 'PROTECTED_ABANDONMENT_METADATA_UNAVAILABLE'})); return 2


if __name__ == '__main__':
    raise SystemExit(main())
