"""Finite independently authored mechanical oracles, used only by the referee.

Private label data selects an allowlisted operation and frozen parameters. It
cannot select a Python module, command, arbitrary expression or product client.
Product Tier 2 predictions are recorded separately from these observations.
"""
from .adapters import capsule,verifier,routing
from .evidence import canonical,read_verified
from .frozen_records import strict_json,ref_key


def screening_mechanics(output,*,expected_ids,eligibility):
    scores=output['scores'];ids=[s['idea_id'] for s in scores]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected_ids) or set(eligibility)!=set(expected_ids):raise ValueError('candidate coverage differs from independent fixture')
    ranked=[]
    for row in scores:
        values=[row[key] for key in ('novelty','feasibility','compute_alignment')]
        if any(type(v) is not int or not 1<=v<=5 for v in values):raise ValueError('score dimension is outside fixed rubric scale')
        total=sum(values)
        if type(row['total']) is not int or row['total']!=total or type(row['eligible']) is not bool or row['eligible']!=eligibility[row['idea_id']]:raise ValueError('sum or independent dependency eligibility mismatch')
        if row['eligible']:ranked.append((row['idea_id'],total))
    ranked.sort(key=lambda item:(-item[1],item[0]))
    expected=[{'idea_id':ident,'total':total,'rank':number} for number,(ident,total) in enumerate(ranked,1)]
    if not expected or output['ranking']!=expected or output['selected_idea_id']!=expected[0]['idea_id']:raise ValueError('independently recomputed tie/rank/Top1 mismatch')
    return True


def _artifact(frozen,parameters):
    from .evaluation_records import EvaluationRecords
    if isinstance(frozen,EvaluationRecords):return frozen.output_artifact(parameters)
    if 'artifact_ref' in parameters:return frozen.json_artifact(parameters['artifact_ref'])
    matches=[]
    for raw in frozen.artifacts.values():
        try:value=strict_json(raw)
        except (ValueError,UnicodeError):continue
        if isinstance(value,dict) and value.get('id')==parameters['artifact_id']:matches.append(value)
    if len(matches)!=1:raise ValueError('exact output identity is absent or ambiguous')
    return matches[0]


def _capsule(frozen,parameters):
    observations=[e for e in frozen.of_kind('invocation-observation') if e['record']['cc_name']==parameters['cc_name']]
    expected=parameters['cc_identity']
    if not observations or any(any(e['record'].get(k)!=v for k,v in expected.items()) for e in observations):raise ValueError('wrong selected Capsule or immutable declaration pin')
    gates=[e for e in frozen.of_kind('gate-decision') if e['record']['node_id']==parameters['node_id']]
    node=[e for e in gates if e['record']['scope_kind']=='node' and e['record']['action']=='advance']
    if len(node)!=1:raise ValueError('one actual advancing node gate required')
    gate=node[0]['record']
    invocations=[frozen.resolve(ref,'invocation-observation') for ref in gate['invocation_refs']]
    work=[e for e in invocations if e['cc_name']==parameters['cc_name']]
    reviewers=[e for e in invocations if e['cc_name']!=parameters['cc_name']]
    if not work or not reviewers or any(e['observed_runtime'] is not True or e['model_calls'] is None or e['model_calls']<1 for e in [*work,*reviewers]):raise ValueError('real work and independent verifier invocation required')
    for observation in [*work,*reviewers]:
        traced=[frozen.by_ref.get(ref_key(r)) for r in observation['trace_refs']]
        calls=[e['record'] for e in traced if e and e['kind']=='model-call']
        routes=[e['record'] for e in traced if e and e['kind']=='route-record']
        role='worker' if observation in work else 'verifier'
        if not calls or not routes or not any(c['call_function']==role and c['observed_runtime'] is True for c in calls):raise ValueError('invocation lacks exact separately governed role call')
        for route in routes:routing.validate_evidence(route,calls)
    for name in parameters['required_outputs']:
        _artifact(frozen,{'artifact_id':name})
    commits=[e['record'] for e in frozen.of_kind('acceptance-commit') if e['record']['node_id']==parameters['node_id'] and not e['record']['subnode_id']]
    if not any(node[0]['ref'] in c['gate_decision_refs'] and set(map(ref_key,c['output_refs'].values()))==set(map(ref_key,gate['accepted_refs'])) for c in commits):raise ValueError('exact committed external outputs required')
    frozen.gate_rows()
    for route in frozen.of_kind('route-record'):
        if route['record']['node_id']==parameters['node_id']:routing.validate_evidence(route['record'],[e['record'] for e in frozen.of_kind('model-call')])
    if not any(e['record']['node_id']==parameters['node_id'] for e in frozen.of_kind('route-record')):raise ValueError('actual work/verifier call provenance unavailable')
    return True


def live_records(frozen,run_folder,parameters):
    status=strict_json((run_folder/'terminal-status.json').read_bytes())
    if status['run_id']!=frozen.run_id:raise ValueError('foreign terminal status')
    # A status snapshot is observation only; durable commit/dispatch identities
    # below remain necessary for release. Skipped causes are copied verbatim.
    return {'mode':'actual','scheduler_kind':'live',**{k:parameters[k] for k in ('predecessor_node','successor_node')},
        'accepted_outputs':[e['record'] for e in frozen.of_kind('acceptance-commit')],
        'gates':frozen.of_kind('gate-decision'),'successor_starts':[e['record'] for e in frozen.of_kind('dispatch-start')],
        'locked_nodes':[n for n in status['node_statuses'] if n['skipped_because']],
        'barrier_observations':[e['record'] for e in frozen.of_kind('gate-persistence-barrier')]}


def evaluate_checks(label,frozen,run,run_folder):
    """Return only actually evaluated check observations; missing inputs withhold."""
    from .evaluation_records import EvaluationRecords
    private=isinstance(frozen,EvaluationRecords)
    evidence=[run['run_id']+('/evaluation-export/evaluation_export.json' if private else '/export/client_retrieval.json')]
    observations={}
    for check in label['mandatory_checks']:
        if check['kind']!='deterministic':continue
        definition=label['labels'].get(check['check_id'],{});oracle=definition.get('oracle');p=definition.get('parameters',{})
        if oracle not in {'screening_mechanics','capsule_gate','citation_replay','live_gate','governed_route','required_export','exact_output','rsi_session_integrity'}:continue
        try:
            if oracle=='rsi_session_integrity':
                from .adapters.rsi import read_public_export,validate_public_session
                exported=read_public_export(run_folder/'rsi-export')
                validate_public_session(exported,public_key=bytes.fromhex(p['public_key_hex']),key_id=p['key_id'])
            elif frozen is None:continue
            elif oracle=='screening_mechanics':
                output=_artifact(frozen,p);frozen.validate('screening-result',output)
                screening_mechanics(output,expected_ids=p['expected_ids'],eligibility=p['eligibility'])
            elif oracle=='capsule_gate':
                if private:raise ValueError('private evaluation does not prove an ordinary Capsule Gate')
                _capsule(frozen,p)
            elif oracle=='citation_replay':
                if private:
                    verifier.validate_citation(frozen.replay_observation(node_id=p['node_id'],output_port=p.get('output_port')))
                else:
                    rows=[g for g in frozen.gate_rows() if g['node_id']==p['node_id'] and g['output_port']==p.get('output_port')]
                    if len(rows)!=1:raise ValueError('one exact replay gate expected')
                    row=rows[0]
                    verifier_calls=sum(c['role']=='verifier' for c in frozen.model_call_rows())
                    verifier.validate_citation({'tier1':row['tier1_verdict'],'tier2':row['tier2_verdict'],'advanced':row['advanced'],'verifier_calls':verifier_calls})
            elif oracle=='live_gate':
                if private:raise ValueError('private recording replay cannot prove live scheduler causality')
                verifier.validate_live_order(live_records(frozen,run_folder,p),expected_advance=p['expected_advance'],require_delay_barrier=p.get('require_delay_barrier',False))
            elif oracle=='governed_route':
                if private:raise ValueError('ordinary governed-route case requires its ordinary product export')
                routes=[e['record'] for e in frozen.of_kind('route-record') if e['record']['node_id']==p['node_id']]
                if not routes:raise ValueError('actual protected route records absent')
                for route in routes:routing.validate_evidence(route,[e['record'] for e in frozen.of_kind('model-call')])
            elif oracle=='required_export':
                if private:
                    if not frozen.rows(p['kind']):raise ValueError('required exact private record kind absent')
                elif not any(e['kind']==p['kind'] for e in frozen.records):raise ValueError('required protected record absent')
            elif oracle=='exact_output':
                if _artifact(frozen,p)!=p['expected']:raise ValueError('independent exact output mismatch')
            observations[check['check_id']]={'passed':True,'reason':'Independent frozen mechanical oracle passed.','evidence':evidence}
        except (ValueError,KeyError,TypeError,OSError,UnicodeError):
            observations[check['check_id']]={'passed':False,'reason':'Independent mechanical obligation was not established by the frozen exact bytes.','evidence':evidence}
    return observations
