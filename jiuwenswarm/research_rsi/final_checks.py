"""Custodian-owned reconciliation before any final hidden inputs are released."""
from .profiles import freeze_profile


def verify_final_integrity(*,session,attempt_ref,target_ref,parent_ref,child_ref,configuration_ref,store,validate):
    validate('rsi-session',session)
    target=store.get(target_ref);parent=store.get(session['parent_declaration_ref'])
    validate('capsule-declaration',parent);freeze_profile(target,parent,validate)
    identity=parent['identity']
    expected_parent={'cc_name':identity['name'],'cc_version':identity['version_label'],
        'declaration_sha256':session['parent_declaration_ref']['sha256']}
    if (session['parent']!=expected_parent or session['target_profile_ref']!=target_ref
            or target['parent_declaration_ref']!=session['parent_declaration_ref']
            or target['parent_ref']!=parent_ref or configuration_ref!=session['configuration_ref']):
        raise ValueError('Final integrity prerequisite: original parent/target/configuration differs')
    if any(target[key]!=session[key] for key in ('configuration_ref','improver_ref','scoring_adapter_ref')):
        raise ValueError('Final integrity prerequisite: target context changed')
    genesis=store.get(session['chain_root_ref'])
    if any(genesis.get(key)!=value for key,value in {'session_id':session['session_id'],
            'target_ref':target_ref,'hash_profile_ref':session['hash_profile_ref'],'interface_revision':'M1-IF-009@r2'}.items()):
        raise ValueError('Final integrity prerequisite: genesis binding changed')
    for pin in (parent_ref,child_ref,session['hash_profile_ref'],session['configuration_ref'],
            session['improver_ref'],session['scoring_adapter_ref'],*target['required_test_refs'],*target['protected_refs']):
        store.read(pin)
    if child_ref['sha256']==parent_ref['sha256'] or any(child_ref['sha256']==ref['sha256'] for ref in target['protected_refs']):
        raise ValueError('Final integrity prerequisite: child aliases original/protected material')
    finalist=store.get(attempt_ref);validate('rsi-attempt',finalist)
    if finalist['attempt_status']!='proposed' or finalist['child_ref']!=child_ref:
        raise ValueError('Final integrity prerequisite: selected attempt is not the assessed proposal')
    sequence=finalist['sequence'];query_ceiling=session['limits']['session_query_limit']
    if not 1<=sequence<=session['limits']['max_attempts']:raise ValueError('Final integrity prerequisite: attempt limit exceeded')
    seen=set();pin=attempt_ref
    while pin is not None:
        key=(pin['id'],pin['sha256'])
        if key in seen or sequence<1:raise ValueError('Final integrity prerequisite: invalid attempt chain')
        seen.add(key);attempt=store.get(pin);validate('rsi-attempt',attempt)
        expected={'schema_version':'2.0.0','session_id':session['session_id'],'sequence':sequence,
            'target_ref':target_ref,'parent_ref':parent_ref,'configuration_ref':configuration_ref,
            'hash_profile_ref':session['hash_profile_ref'],'chain_root_ref':session['chain_root_ref']}
        if any(attempt.get(k)!=v for k,v in expected.items()) or attempt['violations'] or attempt['queries_used']>query_ceiling:
            raise ValueError('Final integrity prerequisite: attempt scope, violations or query history differs')
        for ref in attempt['visible_evidence_refs']+attempt['failure_evidence_refs']+attempt['observation_refs']:store.read(ref)
        for field in ('child_ref','diff_ref'):
            if attempt[field] is not None:store.read(attempt[field])
        query_ceiling=attempt['queries_used'];sequence-=1;pin=attempt['previous_ref']
    if sequence!=0:raise ValueError('Final integrity prerequisite: predecessor history is incomplete')
    diff=store.get(finalist['diff_ref'])
    expected_file={'path':target['mutable_paths'][0],'before_ref':parent_ref,'after_ref':child_ref}
    if diff!={'format':'ai4r-body-diff-v1','files':[expected_file]}:
        raise ValueError('Final integrity prerequisite: actual mutation differs from the one authorized body')
    return True
