"""Set the Family column of contracts/index-*.md tables (idempotent: the maps below are authoritative).
Usage: python add_family.py [files...]

Family rules are in contracts/principles.md. A def that is only a part of one bigger message is a Helper even when indexed.
"""
import re
import sys
from pathlib import Path

V = Path(__file__).resolve().parent.parent
HELPERS = {'ref', 'id', 'hash', 'ext', 'nullable_ref', 'reason', 'system_ref', 'trial_ref', 'oracle_ref', 'evidence_manifest_ref',
           'time', 'error', 'plan_finding_code', 'rsi_attack_result', 'trial_file', 'skill_issue', 'rsi_state', 'attempt_disposition',
           'sample_values', 'check_run', 'library_entry', 'finding', 'selection', 'objective_binding', 'step', 'model_call', 'artifact',
           'deviation', 'measurement', 'seed', 'check_result', 'call_descriptor', 'doctor_check', 'benchmark_sample', 'model_call_scope',
           'scoped_capture_ref', 'model_call_limits', 'ablation_action', 'token_usage', 'check_call', 'exit_code', 'step_envelope', 'runner_turn_entry', 'rsi_trial', 'rsi_security_clearance', 'planning_reservation', 'model_call_reservation', 'profile_ref', 'evidence_ref'}
FRAMES = {'tool_host_frame', 'skill_turn_frame', 'runner_event'}
EVENTS = {'event_envelope'}
PROFILES = {'experiment_profile', 'benchmark_profiles', 'retry_profile', 'execution_profile', 'ablation_study'}
REPORTS = {'doctor_report', 'run_status_view', 'readiness', 'benchmark_export', 'rsi_verify_boundary_report',
           'intent_fidelity_review', 'author_kit_report', 'measurement_evidence', 'execution_evidence', 'syntax_check_evidence',
           'halt_report', 'cli_json_output', 'run_handle', 'export_handle', 'intent_repair_record'}
RECORDS = {'planner_proposal', 'admission_decision', 'routing_decision', 'abort_request_run_never', 'private_model_capture',
           'experimental_advance', 'experimental_gate_evidence', 'local_session_token', 'run_manifest', 'commit_batch_manifest',
           'evaluator_manifest', 'fixture_set_manifest', 'planted_child_manifest', 'rsi_attack_scenario'}
CALLS = {'model_client_call', 'model_client_reply', 'runner_response', 'workflow_start_args', 'plan_validation', 'launch_result',
         'freeze_result', 'deliver_result', 'poc_execute_result', 'measurement_result', 'auth_result', 'admission_decision_never',
         'model_bridge_result', 'record_input_request', 'gate_result', 'gate_request', 'abort_request_run', 'run_checks_result',
         'rsi_session_result', 'oracle_session_result', 'oracle_aggregate_result', 'library_snapshot_result', 'catalogue_result',
         'intake_result', 'resource_snapshot_result', 'abort_request', 'planner_request', 'validation_request', 'routing_request',
         'activation_record_never'}


def family(d):
    if d in HELPERS:
        return 'Helper'
    if d in FRAMES:
        return 'Frame'
    if d in EVENTS:
        return 'Event'
    if d in PROFILES:
        return 'Profile'
    if d in REPORTS:
        return 'Report'
    if d in RECORDS or d.startswith('system_record'):
        return 'Record'
    if d in CALLS or d.endswith('_request') or d.endswith('_result') or d.endswith('_response'):
        return 'Call'
    return 'Record'


ROWRE = re.compile(r'^\| `([a-z0-9_.-]+\.schema\.json)#([a-z_0-9]+)` \|(.*)$')
for p in ([Path(a) for a in sys.argv[1:]] or sorted((V / 'contracts').glob('index-*.md'))):
    lines = p.read_text(encoding='utf-8').split('\n')
    out = []
    for l in lines:
        if l.startswith('| Schema def |') and 'Family' not in l:
            l = l.replace('| Schema def |', '| Schema def | Family |', 1)
        elif re.match(r'^\|---', l) and out and out[-1].startswith('| Schema def | Family') and l.count('|') < out[-1].count('|'):
            l = '|---|---' + l[4:]
        else:
            m = ROWRE.match(l)
            if m:
                rest = re.sub(r'^ (Call|Record|Event|Frame|Profile|Report|Helper) \|', '', m.group(3))
                l = f'| `{m.group(1)}#{m.group(2)}` | {family(m.group(2))} |{rest}'
        out.append(l)
    p.write_text('\n'.join(out), encoding='utf-8', newline='\n')
    print('family column in', p.name)
