"""Finite admission closure. Private calibration/fixture references stay opaque.

Both publisher and inbox importer use this definition. JSON resemblance never
causes recursive traversal of target profiles, model diagnostics, or source code.
"""
import hashlib
import json
from . import ResearchError,validate


def candidate_public_closure(package,read):
    validate('candidate-package',package)
    rows={};total=0
    def add(pin,contract=None):
        nonlocal total
        validate('Ref',pin);key=(pin['id'],pin['sha256'])
        if key not in rows:
            raw=read(pin)
            if not isinstance(raw,bytes) or not 0<=len(raw)<=4*1024*1024 or hashlib.sha256(raw).hexdigest()!=pin['sha256']:
                raise ResearchError('rsi_refs','Exact public candidate original is unavailable')
            total+=len(raw)
            if len(rows)>=5000 or total>64*1024*1024:raise ResearchError('rsi_refs','Candidate public closure exceeds its transport bound')
            rows[key]=(dict(pin),raw)
        raw=rows[key][1]
        if contract is None:return raw
        try:value=json.loads(raw)
        except (ValueError,UnicodeError) as error:raise ResearchError('rsi_refs','Required candidate record is malformed') from error
        validate(contract,value);return value
    session=add(package['session_ref'],'rsi-session')
    result=add(package['session_result_ref'],'rsi-session-result')
    target=add(package['target_profile_ref'],'rsi-target-profile')
    add(package['referee_evidence_ref'],'rsi-referee-evidence')
    add(package['parent_declaration_ref'],'capsule-declaration')
    child=add(package['child_declaration_ref'],'capsule-declaration')
    provenance=add(package['provenance_ref'],'candidate-provenance')
    add(package['diff_ref'])
    add(target['parent_ref']);add(provenance['parent_ref'])
    if result['session_ref']!=package['session_ref'] or session['target_profile_ref']!=package['target_profile_ref']:
        raise ResearchError('rsi_refs','Candidate closure names another session or target')
    add(session['hash_profile_ref'])
    genesis=json.loads(add(session['chain_root_ref']))
    # A budget contains counts/resource bounds, never fixture IDs or labels.
    if genesis.get('final_budget_ref') is not None:
        add(genesis['final_budget_ref'],'urn:ai4r:private:rsi-final-budget:1')
    if len(result['attempt_refs'])>session['limits']['max_attempts']:
        raise ResearchError('rsi_refs','Candidate attempts exceed the frozen session limit')
    for pin in result['attempt_refs']:
        attempt=add(pin,'rsi-attempt')
        for field in ('child_ref','diff_ref'):
            if attempt[field] is not None:add(attempt[field])
        for field in ('failure_evidence_refs','visible_evidence_refs','observation_refs'):
            for evidence in attempt[field]:add(evidence)
    for pin in provenance['implementation_refs']:add(pin)
    for pin in provenance['evidence_refs']:add(pin)
    lineage=child['identity'].get('lineage',{})
    prompt=lineage.get('provenance',{}).get('prompt_ref')
    if prompt is not None:add(prompt)
    # In particular: do not follow target.calibration_ref/protected_refs,
    # diagnosis/preparation refs, hidden evaluator captures, or model accounts.
    return tuple(rows.values())
