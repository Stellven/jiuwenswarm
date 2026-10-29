"""C001 replay and live causal-gate observations have separate proof obligations."""


def validate_citation(decision):
    if decision['tier1']!='FAIL' or decision['tier2']!='NOT_RUN' or decision['advanced'] or decision['verifier_calls']!=0:raise ValueError('C001 unsupported citation must reject before Tier 2')
    return True


def validate_live_order(records,*,expected_advance,require_delay_barrier=False):
    if records.get('mode')!='actual' or records.get('scheduler_kind')!='live':raise ValueError('recording replay scheduler is not live gate proof')
    predecessor=records.get('predecessor_node');successor=records.get('successor_node')
    if not predecessor or not successor or predecessor==successor:raise ValueError('frozen predecessor/successor identities required')
    commits={x['commit_id']:x for x in records.get('accepted_outputs',[]) if x['node_id']==predecessor and not x['subnode_id']}
    gates={(e['ref']['id'],e['ref']['sha256']):e['record'] for e in records.get('gates',[])}
    starts=records.get('successor_starts',[])
    starts=[x for x in starts if x['node_id']==successor]
    if expected_advance and not starts:raise ValueError('live successor start evidence absent')
    if not expected_advance and starts:raise ValueError('successor advanced despite locked gate')
    if not expected_advance and not any(x['node_id']==successor and x.get('skipped_because') for x in records.get('locked_nodes',[])):raise ValueError('absence of a start alone does not establish actual locked/skipped successor')
    if require_delay_barrier:
        barriers=records.get('barrier_observations',[])
        if not any(x.get('state')=='held' and x.get('predecessor_node')==predecessor and x.get('successor_node')==successor
                and x.get('successor_dispatched') is False and x.get('acceptance_committed') is False for x in barriers):
            raise ValueError('actual held persistence barrier observation required')
    for start in starts:
        predecessors=[x for x in start['predecessor_commits'] if x['node_id']==predecessor]
        if not predecessors:raise ValueError('dispatch lacks exact predecessor acceptance commit')
        for captured in predecessors:
            commit=commits.get(captured['commit_id']);ref=captured['artifact_ref']
            if not commit or captured['attempt_id']!=commit['attempt_id'] or commit['output_refs'].get(captured['port'])!=ref:raise ValueError('dispatch-to-commit identity mismatch')
            if ref not in [x['ref'] for x in start['bound_input_refs']]:raise ValueError('successor did not consume the exact committed output')
            decisions=[gates.get((r['id'],r['sha256'])) for r in commit['gate_decision_refs']]
            if not decisions or any(g is None or g['scope_kind']!='node' or g['action']!='advance' or g['node_id']!=predecessor or g['attempt_id']!=commit['attempt_id'] for g in decisions):raise ValueError('acceptance lacks exact advancing node gate')
            if not any(ref in g['accepted_refs'] for g in decisions):raise ValueError('consumed output absent from committed node gate')
    return True
