"""Validation for explicitly captured M1 ordinary-process execution evidence.

M1 proves the process identity and privilege settings. It does not claim a
per-job network namespace, cgroup memory ceiling, or PID ceiling.
"""
from __future__ import annotations


def validate_process_evidence(store, raw, *, expected_uid, expected_gid,
                              contract_ref=None, invocation_id=None, job_id=None,
                              memory_bytes=None, pids_max=None, expected_runtime_ref=None):
    """Return True only for evidence joined to an original schema-5 runtime.

    Legacy receipts return False so callers can continue their existing strict
    isolation-probe path unchanged.
    """
    if type(raw) is not dict or raw.get('execution_mode') != 'm1_app_process':
        return False
    try:
        if (raw.get('observed_runtime') is not True or raw.get('runtime_ref') is None
                or (expected_runtime_ref is not None and raw.get('runtime_ref') != expected_runtime_ref)
                or (contract_ref is not None and raw.get('contract_ref') != contract_ref)
                or (invocation_id is not None and raw.get('invocation_id') != invocation_id)
                or (job_id is not None and raw.get('job_id') != job_id)):
            return False
        limits = raw['observed_limits']
        if (limits.get('execution_mode') != 'm1_app_process'
                or limits.get('network') != 'inherited'
                or limits.get('memory_max') is not None or limits.get('pids_max') is not None
                or 'isolation_probe_ref' in limits):
            return False
        proof_ref = limits.get('process_observation_ref')
        proof = store.read_record(proof_ref) if isinstance(proof_ref, dict) else None
        if (type(proof) is not dict or proof.get('schema') != 'ai4r-m1-process:1'
                or proof.get('execution_mode') != 'm1_app_process'
                or proof.get('runtime_ref') != raw['runtime_ref']
                or proof.get('job_id') != raw.get('job_id')
                or proof.get('contract_ref') != raw.get('contract_ref')
                or proof.get('invocation_id') != raw.get('invocation_id')
                or proof.get('ready') is not True
                or proof.get('executor_uid') != expected_uid
                or proof.get('executor_gid') != expected_gid
                or proof.get('no_new_privileges') != '1'
                or int(proof.get('cap_effective', '-1'), 16) != 0
                or type(proof.get('cpu_affinity')) is not list or not proof['cpu_affinity']
                or proof.get('cwd') in (None, '') or proof.get('mode') != 'm1_app_process'):
            return False
        if memory_bytes is not None or pids_max is not None:
            return False
        runtime_ref = raw['runtime_ref']
        if store.record_kind(runtime_ref) != 'science-runtime':
            return False
        runtime = store.read_record(runtime_ref)
        if (runtime.get('schema') != 'ai4r-science-runtime:5'
                or runtime.get('execution_mode') != 'm1_app_process'
                or type(runtime.get('execution_bindings')) is not list):
            return False
        # Join this exact child and its selected binding to a configuration-
        # and policy-matched mapping in the pinned original runtime.
        child = store.read_record(raw['contract_ref'])
        parent_ref = child.get('node_contract_ref')
        parent = store.read_record(parent_ref) if parent_ref else None
        bindings = child.get('bindings')
        if type(parent) is not dict or type(bindings) is not list or len(bindings) != 1:
            return False
        selected = bindings[0]
        candidates = [row for row in runtime['execution_bindings']
                      if row.get('configuration_ref') == parent.get('configuration_ref')
                      and row.get('policy_ref') == parent.get('policy_ref')
                      and row.get('declaration_ref') == selected.get('declaration_ref')
                      and row.get('implementation_refs') == selected.get('implementation_refs')
                      and row.get('dependency_refs') == selected.get('dependency_refs')
                      and row.get('admission_ref') == selected.get('admission_ref')]
        if len(candidates) != 1:
            return False
        # The root broker records an immutable execution attestation at
        # launch. This binds the captured runtime to this actual job rather
        # than accepting any other captured schema-5 runtime with a matching
        # configuration.
        attested = [item['record'] for item in store.iter_records(
            run_id=child.get('run_id'), kinds=('m1_process_execution',))
            if item.get('record', {}).get('job_id') == raw.get('job_id')
            and item.get('record', {}).get('contract_ref') == raw.get('contract_ref')
            and item.get('record', {}).get('invocation_id') == raw.get('invocation_id')]
        return (len(attested) == 1 and attested[0].get('runtime_ref') == runtime_ref
                and attested[0].get('receipt') == {key:value for key,value in raw.items() if key!='trusted_scoring_ref'})
    except (KeyError, TypeError, ValueError, OSError):
        return False
