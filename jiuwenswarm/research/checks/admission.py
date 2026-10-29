"""Declaration host checks. Claimed guarantees never choose mandatory checks."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import math
import re
from pathlib import PurePosixPath

from ..contracts import ResearchError, validate


def rubric_checks(raw):
    """Screening source admission checks, independent of the work scorer."""
    value=None;structure=False;complete=False
    try:
        value=json.loads(raw.decode('utf-8'));validate('screening-rubric',value);structure=True
        names=[d['name'] for d in value['dimensions']]
        dependencies=[d['id'] for d in value['forbidden_dependencies']]
        complete=(len(names)==3 and set(names)=={'novelty','feasibility','compute_alignment'}
            and all(len(d['anchors'])==5 and {a['score'] for a in d['anchors']}==set(range(1,6)) for d in value['dimensions'])
            and len(dependencies)==len(set(dependencies))
            and all(term==term.lower() for d in value['forbidden_dependencies'] for term in d['match_terms']))
    except (ResearchError,ValueError,UnicodeError,KeyError,TypeError):pass
    return [{'check_id':key,'outcome':'PASS' if passed else 'FAIL','reason':reason,'evidence_refs':[]} for key,passed,reason in
        [('rubric_structure',structure,'Actual Screening body rubric matches the exact source field contract'),
         ('rubric_dimensions_complete',complete,'Source dimensions/anchor sets/dependency identities are complete and unique')]]


def verify_self_test(store,test,declaration_ref,body_refs,observed,*,memory_mb=None,actor=None,configuration_ref=None,execution_profile_ref=None):
    try:
        return _verify_self_test(store,test,declaration_ref,body_refs,observed,memory_mb=memory_mb,actor=actor,
            configuration_ref=configuration_ref,execution_profile_ref=execution_profile_ref)
    except ResearchError:raise
    except (ValueError,TypeError,KeyError,IndexError,AttributeError) as error:
        raise ResearchError('self_test_evidence','Malformed original candidate-test evidence cannot grant admission') from error


def _verify_self_test(store,test,declaration_ref,body_refs,observed,*,memory_mb=None,actor=None,configuration_ref=None,execution_profile_ref=None):
    """Verify protected original execution evidence, never a confinement flag.

    The separate root broker owns the actual candidate-test producer. No
    ordinary admitted invocation or candidate callback can mint its proof.
    """
    def require(value,reason):
        if not value:raise ResearchError('self_test_evidence',reason)
    if not isinstance(observed,dict) or set(observed)!={'id','sha256'}:
        raise ResearchError('self_test_unavailable','An original protected self-test result Ref is required')
    validate('Ref',observed);proof=store.read_record(observed)
    validate('urn:jiuwenswarm:m1-private:admission-self-test-result:1',proof)
    require(store.record_kind(observed)=='admission-self-test-result','Self-test evidence was not captured by the protected producer')
    test_ref=body_refs[test['ref']['ref']]
    require(proof.get('declaration_ref')==declaration_ref and proof.get('test_id')==test['id']
        and proof.get('test_ref')==test_ref and proof.get('body_refs')==body_refs,'Self-test proof names different declaration/test/body bytes')
    job_ref=proof.get('job_ref');job=store.read_record(job_ref)
    validate('urn:jiuwenswarm:m1-private:admission-self-test-job:1',job)
    require(store.record_kind(job_ref)=='admission-self-test-job' and job.get('declaration_ref')==declaration_ref
        and job.get('test_id')==test['id'] and job.get('test_ref')==test_ref and job.get('body_refs')==body_refs
        and job.get('configuration_ref')==proof.get('configuration_ref'),'Self-test result differs from the protected issued candidate job')
    request_ref=job['admission_request_ref'];request=store.read_record(request_ref)
    validate('urn:jiuwenswarm:m1-private:admission-self-test-request:1',request)
    require(store.record_kind(request_ref)=='admission-self-test-request' and request['operation']=='library_admit'
        and all(request[key]==job[key] for key in ('declaration_ref','test_id','body_refs','configuration_ref','execution_profile_ref','created_at','expires_at')),
        'Issued candidate job differs from its original admission authority')
    if actor is not None:require(request['actor_id']==actor.account_id,'Candidate job belongs to another admission actor')
    if memory_mb is not None:require(request['admission_memory_mb']==memory_mb,'Candidate request does not use the actual admission memory')
    if configuration_ref is not None:require(job['configuration_ref']==configuration_ref,'Candidate request names another protected configuration')
    if execution_profile_ref is not None:require(job['execution_profile_ref']==execution_profile_ref,'Candidate request names another approved execution profile')
    store.read_blob(job['configuration_ref']);profile=store.read_record(job['execution_profile_ref'])
    require(store.record_kind(job['execution_profile_ref'])=='admission-execution-profile'
        and profile['schema']=='ai4r-admission-execution-profile:1' and profile['configuration_ref']==job['configuration_ref']
        and profile['driver_ref']==job['driver_ref'],'The actual protected driver/profile closure differs')
    store.read_blob(job['driver_ref']);store.read_blob(profile['runtime_ref'])
    receipt_ref=proof.get('execution_receipt_ref');receipt=store.read_record(receipt_ref)
    require(store.record_kind(receipt_ref) in {'execution-receipt','admission-self-test-execution'}
        and receipt.get('contract_ref')==job_ref and receipt.get('observed_runtime') is True
        and receipt.get('termination_reason')=='completed' and receipt.get('exit_code')==0,'No actual successful confined self-test driver execution')
    elapsed=receipt.get('wall_time_s');timeout=receipt.get('timeout_s');limits=job.get('limits',{})
    declaration=store.read_record(declaration_ref,contract_id='capsule-declaration')
    require(type(elapsed) in (int,float) and math.isfinite(elapsed) and 0<=elapsed
        and type(timeout) in (int,float) and math.isfinite(timeout) and elapsed<=timeout<=limits.get('time_s',-1)
        and timeout<=declaration['budget']['per_call']['wall_s'],'Self-test exceeded the actual declared time allowance')
    if memory_mb is not None:require(type(limits.get('memory_mb')) is int and 0<limits['memory_mb']<=memory_mb,'Self-test memory allowance widens admission')
    require(all(limits[key]<=profile['limits'][key] for key in ('time_s','memory_mb','pids_max')),'Candidate job widens its frozen execution profile')
    def kernel(record):
        require(record.get('contract_ref')==job_ref and record.get('observed_runtime') is True
            and record.get('termination_reason')=='completed' and record.get('exit_code')==0,'Actual driver/candidate kernel execution did not complete')
        wall,cap=record.get('wall_time_s'),record.get('timeout_s')
        require(type(wall) in (int,float) and type(cap) in (int,float) and math.isfinite(wall) and math.isfinite(cap)
            and 0<=wall<=cap<=limits['time_s'],'Actual driver/candidate time exceeded its exact job')
        observed_limits=record.get('observed_limits',{});probe=store.read_record(observed_limits.get('isolation_probe_ref'))
        try:
            confined=probe.get('ready') is True and probe.get('executor_uid')==probe.get('executor_gid')==10002
            confined=confined and int(probe.get('cap_effective','1'),16)==0 and probe.get('no_new_privileges')=='1'
            confined=confined and probe.get('network')=='none' and bool(probe.get('denied_paths')) and all(value is True for value in probe['denied_paths'].values())
            confined=confined and observed_limits.get('network')=='none' and 0<int(observed_limits.get('memory_max','0'))<=limits['memory_mb']*1024*1024
            confined=confined and 0<int(observed_limits.get('pids_max','0'))<=limits['pids_max']
        except (ValueError,TypeError,KeyError):confined=False
        require(confined,'Actual confined identity/memory/PID/network observation is unavailable or exceeds its job')
        store.read_blob(record['stderr_ref'])
        try:return json.loads(store.read_blob(record['stdout_ref']).decode('utf-8'))
        except (ValueError,UnicodeError) as error:raise ResearchError('self_test_evidence','Malformed original kernel output') from error
    reported=kernel(receipt)
    stdout=store.read_blob(receipt['stdout_ref']);store.read_blob(receipt['stderr_ref'])
    try:reported=json.loads(stdout.decode('utf-8'))
    except (ValueError,UnicodeError) as error:raise ResearchError('self_test_evidence','The actual self-test driver did not report a typed end state') from error
    require(isinstance(reported,dict) and reported.get('end_state')==proof.get('end_state')==test['expects'],'Actual self-test end state differs from its declaration')
    outputs=proof.get('output_refs');require(isinstance(outputs,list),'Actual self-test output inventory is unavailable')
    for ref in outputs:validate('Ref',ref);store.read_blob(ref)
    require((test['expects']=='pass' and bool(outputs) and proof.get('reason_code') is None)
        or (test['expects']!='pass' and not outputs and proof.get('reason_code')==test['expects']),'Self-test output/failure shape contradicts its actual end state')
    require(proof['driver_execution_ref']==proof['execution_receipt_ref'],'Result does not identify its actual driver assertion receipt')
    require(not proof['model_call_refs'] and not declaration['needs']['injects'],'An unsupported model-capable self-test adapter cannot qualify as pure execution')
    candidates={};candidate_refs=proof['candidate_execution_refs']
    require(0<len(candidate_refs)<=profile['max_candidate_calls'],'Actual candidate execution count exceeds the fixed adapter')
    for candidate_ref in candidate_refs:
        candidate=store.read_record(candidate_ref)
        validate('urn:jiuwenswarm:m1-private:admission-self-test-candidate-execution:1',candidate)
        require(store.record_kind(candidate_ref)=='admission-self-test-candidate-execution' and candidate['id'] not in candidates
            and candidate['job_ref']==job_ref and candidate['declaration_ref']==declaration_ref and candidate['body_refs']==body_refs,
            'Candidate execution is missing, repeated or bound to foreign bytes')
        candidate_receipt_ref=candidate['execution_receipt_ref']
        require(store.record_kind(candidate_receipt_ref) in {'execution-receipt','admission-self-test-execution'},'Candidate has no original protected kernel receipt')
        actual=kernel(store.read_record(candidate_receipt_ref))
        require(isinstance(actual,dict) and set(actual)=={'end_state','outputs','reason_code'} and actual['end_state']==candidate['end_state']
            and actual['reason_code']==candidate['reason_code'] and set(actual['outputs'])==set(candidate['output_refs']),
            'Host candidate capture differs from its original kernel stdout')
        inputs=store.read_record(candidate['input_ref']);input_specs={p['name']:p for p in declaration['ports']['inputs']}
        require(isinstance(inputs,dict) and not set(inputs)-set(input_specs) and all(not p['required'] or name in inputs for name,p in input_specs.items()),'Candidate input ports differ from its exact declaration')
        for name,value in inputs.items():validate(input_specs[name]['schema_ref'],value)
        if test['kind']=='fixture':require(store.read_record(test_ref)==inputs,'Fixture invocation did not use its exact original input bytes')
        specs={p['name']:p for p in declaration['ports']['outputs']}
        if candidate['end_state']=='pass':
            require(candidate['reason_code'] is None and not set(actual['outputs'])-set(specs)
                and all(not p['required'] or name in actual['outputs'] for name,p in specs.items()),'Candidate output ports differ from the declared closure')
            for name,value in actual['outputs'].items():
                validate(specs[name]['schema_ref'],value)
                from ..state import json_bytes
                require(store.read_blob(candidate['output_refs'][name])==json_bytes(value),'Candidate output Ref does not name its actual original bytes')
        else:require(not actual['outputs'] and candidate['reason_code']==candidate['end_state']
            and candidate['end_state'] in {m['reason_code'] for m in declaration['guarantees']['failure_modes']},'Candidate failure is not an actual declared no-output state')
        candidates[candidate['id']]=(candidate,actual)
    require(isinstance(reported,dict) and set(reported)=={'end_state','outputs','reason_code','candidate_call_id'}
        and reported['candidate_call_id'] in candidates,'Driver did not identify its actual captured candidate invocation')
    candidate,actual=candidates[reported['candidate_call_id']]
    require(reported==dict(actual,candidate_call_id=candidate['id']) and candidate['end_state']==proof['end_state']
        and candidate['reason_code']==proof['reason_code'] and list(candidate['output_refs'].values())==outputs,
        'Driver assertion/result does not match the exact host-owned candidate output inventory')
    return proof


def declaration_checks(declaration: dict, body_bytes: dict[str, bytes], *, secret_names=frozenset()) -> list[dict]:
    validate("capsule-declaration", declaration)
    results = []
    def check(identity, condition, reason):
        results.append({"check_id": identity, "outcome": "PASS" if condition else "FAIL",
                        "reason": reason, "evidence_refs": []})
    identity, needs, changes = (declaration[k] for k in ("identity", "needs", "changes"))
    check("m1_kind_admitted", identity["kind"] in {"agent", "tool"}
          and not any(identity.get(k) for k in ("members", "structure", "wiring", "remote")), "Only M1 agent/tool declarations are executable")
    network = needs["network"]
    check("network_consistent", (network["mode"] == "none" and network["direction"] == "none" and not network["allowlist"])
          or (network["mode"] == "allowlist" and network["direction"] == "egress" and bool(network["allowlist"])), "Network mode/direction/allowlist must agree")
    evolution = declaration["evolution"]
    protected = identity["name"] in {"research.verifier", "research.benchmark", "research.evaluation"}
    check("rsi_mode_allowed", evolution["rsi"] in {"none", "propose"} and (not protected or evolution["rsi"] == "none"), "Protected checking/evaluation capsules cannot evolve")
    check("rsi_cannot_grant", not evolution["may_change"] if evolution["rsi"] == "none" else True, "No-change mode grants no mutation")
    allowed = evolution["may_change"]
    def valid_mutation(item):
        if item in {"/identity/body", "/identity/carrier"}:
            return True
        if not isinstance(item,str) or not item.startswith('files:'):return False
        path=item[6:]
        return bool(path) and not path.startswith(('/', '\\')) and '..' not in PurePosixPath(path).parts and '\\' not in path and ':' not in path
    check("may_change_entries_valid", all(valid_mutation(v) for v in allowed), "Only relative body globs and carrier/body pointers are mutable")
    child = identity.get("lineage")
    check("rsi_child_has_lineage", child is None or child.get("relation") not in {"rollback_of", "composes", "fuses"}, "Derived child lineage must be complete")
    external = needs.get("external", [])
    check("dependencies_pinned", all((bool(e.get("pin")) and bool(e.get("lockfile")) and not e.get("floating")) if e.get("kind") == "package" else not e.get("lockfile") for e in external), "Packages are pinned with lockfiles; other dependency kinds have none")
    check('dependency_hashes_match',all(pin['ref'] in body_bytes and hashlib.sha256(body_bytes[pin['ref']]).hexdigest()==pin['sha256']
          for dependency in external for pin in (dependency.get('pin'),dependency.get('lockfile')) if pin),
          'Every dependency and package lock matches its exact declared byte pin')
    requested_secrets = needs.get("secrets", [])
    names = [v["name"] for v in requested_secrets]
    check("secrets_allowed", len(names) == len(set(names)) and all(v in secret_names for v in names), "Only approved unique secret names may be requested")
    modes = declaration["guarantees"].get("failure_modes", [])
    ids = [m.get("reason_code") for m in modes]
    check("failure_modes_valid", len(ids) == len(set(ids)) and all(isinstance(k, str) and re.fullmatch("[a-z][a-z0-9_]*", k) for k in ids)
          and all(m.get("retriable") is False and bool(m.get("when", "").strip()) for m in modes), "Failure modes are unique non-retriable snake_case")
    tests = declaration["guarantees"].get("self_tests", [])
    test_ids = [t["id"] for t in tests]
    check("failure_modes_have_self_tests", len(test_ids) == len(set(test_ids)) and all(t["expects"] in ["pass", *ids] for t in tests)
          and all(any(t["expects"] == mode for t in tests) for mode in ids), "Every declared failure mode has a matching self-test")
    check("human_interaction_none", needs.get("human_interaction", "none") == "none", "M1 has no human wait during execution")
    severity = {"pure": 0, "read_only": 1, "idempotent": 2, "compensable": 3, "irreversible": 4}
    required = 0
    safe = True
    for effect in changes["effects"]:
        if effect["op"] == "model_invoke":
            continue
        scoped = effect.get("reversibility") == "scoped"
        if effect.get("idempotent"):
            required = max(required, 0 if scoped else 1)
        else:
            required = max(required, 3 if scoped or effect.get("reversibility") in {"inverse", "compensate"} else 4)
        safe = safe and effect.get("risk", {}).get("severity") != "high"
    check("effect_class_matches_effects", safe and severity[changes["effect_class"]] >= required and changes["effect_class"] != "irreversible", "Effects fit declared class and M1 policy")
    body = identity["body"]
    paths = [v["path"] for v in body]
    hashes = all(p in body_bytes and hashlib.sha256(body_bytes[p]).hexdigest() == item["sha256"] for p, item in zip(paths, body))
    carrier = identity["carrier"]
    hashes = hashes and carrier["ref"] in body_bytes and hashlib.sha256(body_bytes[carrier["ref"]]).hexdigest() == carrier["sha256"]
    check("body_hashes_match", hashes and len(paths) == len(set(paths)), "Every body/carrier hash matches its exact supplied bytes")
    return results
