"""Independent declaration-based structural checker; never executes a plan.

Counts distinct defect instances, not merely defective classes. No product
validator is called by check(); product_gate() is a separate diagnostic.
"""
import copy
import json
import re
from collections import Counter
from library import build_library, declared_payload

DEFECTS = ('unknown_capability', 'unknown_or_missing_port', 'type_incompatible_binding',
    'unsatisfied_required_input', 'cycle_or_unordered_dependency', 'uncovered_obligation',
    'missing_acceptance_criterion', 'acceptance_not_machine_checkable', 'over_budget',
    'effect_or_authority_violation', 'infeasible_task_planned_anyway',
    'feasible_task_declared_infeasible', 'invented_input_or_resource')


def normalize_undeclared(plan_json):
    if not isinstance(plan_json, dict) or not isinstance(plan_json.get('nodes'), list):
        raise ValueError('Expected object with nodes array')
    p = copy.deepcopy(plan_json)
    for n in p['nodes']:
        if not isinstance(n, dict):
            raise ValueError('Node must be an object')
        for key in ('inputs', 'outputs', 'acceptance_criteria', 'depends_on'):
            n.setdefault(key, [])
            if not isinstance(n[key], list):
                raise ValueError(key + ' must be an array')
        if not all(isinstance(x, dict) and isinstance(x.get('name'), str) and isinstance(x.get('source'), str) for x in n['inputs']):
            raise ValueError('Inputs need name and source strings')
        if not all(isinstance(x, str) for x in n['outputs'] + n['depends_on']):
            raise ValueError('Output and dependency names must be strings')
        if not isinstance(n.get('limits', {}), dict):
            raise ValueError('limits must be object')
        n.setdefault('limits', {})
        n.setdefault('covers', [])
    return p


def normalize_declared(plan_proposal_json):
    p = plan_proposal_json
    if not isinstance(p, dict) or not isinstance(p.get('nodes'), list):
        raise ValueError('Expected plan-proposal object')
    coverage = p.get('coverage', [])
    nodes = []
    for n in p['nodes']:
        inputs = []
        for port in n.get('inputs', []):
            future = port.get('future') or {}
            source = (str(future.get('producer_node', '')) + '.' + str(future.get('port', ''))) if port.get('source_kind') == 'future_output' else 'external:' + str(port.get('run_input_key', ''))
            inputs.append(dict(port, source=source))
        nodes.append(dict(id=n.get('node_id'), capability=n.get('cc', {}).get('cc_name'), inputs=inputs,
            outputs=[o['name'] for o in n.get('outputs', [])], output_metadata=n.get('outputs', []),
            acceptance_criteria=n.get('acceptance_criteria', n.get('suggested_checks', [])),
            depends_on=n.get('predecessors', []), limits=n.get('limits', {}),
            covers=list(set(n.get('requirement_ids', []) + n.get('deliverable_ids', []) +
                [c['item_id'] for c in coverage if n.get('node_id') in c.get('node_ids', []) and 'item_id' in c])),
            cc=n.get('cc'), objective=n.get('objective', ''), authority=n.get('authority'),
            effect_class=n.get('effect_class')))
    return normalize_undeclared(dict(nodes=nodes, limits=p.get('limits'), notes=p.get('notes', '')))


def parse_reply(raw, condition):
    text = raw.strip()
    if text.startswith('INFEASIBLE:'):
        return {'infeasible': True, 'reason': text[len('INFEASIBLE:'):].strip(), 'bounded': '\n' not in text and len(text) <= 300}
    # Accept a single fenced JSON response, but never extract a convenient
    # embedded graph from explanatory text or discard additional text.
    if text.startswith('```json\n') and text.endswith('\n```'):
        text = text[8:-4]
    value = json.loads(text)
    if isinstance(value, dict) and value.get('infeasible') is True:
        reason = str(value.get('reason', ''))
        return dict(infeasible=True, reason=reason, bounded=bool(reason) and len(reason) <= 288)
    return (normalize_declared if condition == 'A' else normalize_undeclared)(value)


def check(plan, task, expected, library=None):
    lib = library or build_library()
    policy = lib['plan_policy']
    defects = []
    def add(kind, detail):
        defects.append(dict(defect=kind, detail=detail))
    if plan.get('infeasible'):
        if expected['feasible']:
            add('feasible_task_declared_infeasible', plan.get('reason', ''))
        elif not plan.get('bounded', True) or not any(t in plan.get('reason', '').lower() for t in expected.get('reason_terms', [])):
            add('uncovered_obligation', 'INFEASIBLE reply must be bounded and name the actual missing capability/input or ceiling')
        return result(defects, 0, 0, [], not defects)
    if not expected['feasible']:
        add('infeasible_task_planned_anyway', expected['missing_capability_or_input'])
    entries = {e['cc_name']: e for e in lib['library_snapshot']['entries']}
    nodes = plan.get('nodes', [])
    byid = {n.get('id'): n for n in nodes}
    if len(byid) != len(nodes) or any(not isinstance(n.get('id'), str) or not n['id'] for n in nodes):
        add('cycle_or_unordered_dependency', 'Duplicate or absent node identity')
    payload = declared_payload(task, lib)
    hosts = {r['run_input_key']: r for r in payload['protected_host_bindings']['records']}
    inventory = {r['resource_key']: r for r in task['resource_inventory']['resources']}
    external = dict(task.get('supplied_inputs', {}))
    external['brief'] = dict(artifact_type='research_brief', schema_ref='urn:jiuwenswarm:m1-design:research-brief:3.0.0')
    covered, total_ac, good_ac = set(), 0, 0
    if plan.get('authority') or plan.get('permissions'):
        add('effect_or_authority_violation', 'Plan claims additional authority/permissions')
    for n in nodes:
        nid, cap = n.get('id'), n.get('capability')
        e = entries.get(cap)
        for dep in n.get('depends_on', []):
            if dep not in byid or dep == nid:
                add('cycle_or_unordered_dependency', f'{nid}: invalid predecessor {dep}')
        if not e or not e['selectable_by_planner']:
            add('unknown_capability', f'{nid}: {cap}')
            criteria = n.get('acceptance_criteria', [])
            if not criteria:
                add('missing_acceptance_criterion', str(nid))
            for criterion in criteria:
                total_ac += 1
                add('acceptance_not_machine_checkable', f'{nid}: no admitted output/check for {criterion}')
            # An input with no source is still a defect even on a hallucinated node.
            for p in n.get('inputs', []):
                if not p.get('source'):
                    add('unsatisfied_required_input', f'{nid}.{p.get("name")} is unbound')
            continue
        ip = {p['name']: p for p in e['input_ports']}
        op = {p['name']: p for p in e['output_ports']}
        given = [p['name'] for p in n.get('inputs', [])]
        out = n.get('outputs', [])
        for names, ports, direction in [(given, ip, 'input'), (out, op, 'output')]:
            for name in set(names):
                if name not in ports or names.count(name) > 1:
                    add('unknown_or_missing_port', f'{nid}: unknown/duplicate {direction} {name}')
            for name, port in ports.items():
                if port['required'] and name not in names:
                    add('unknown_or_missing_port', f'{nid}: missing {direction} {name}')
                    if direction == 'input':
                        add('unsatisfied_required_input', f'{nid}.{name}')
        if n.get('cc') and any(n['cc'].get(k) != e[k] for k in ('cc_name', 'cc_version', 'declaration_sha256')):
            add('unknown_capability', f'{nid}: wrong exact release pin')
        for p in n.get('output_metadata', []):
            if p['name'] in op and p.get('artifact_type') != op[p['name']]['artifact_type']:
                add('type_incompatible_binding', f'{nid}.{p["name"]}: wrong output type')
        for p in n.get('inputs', []):
            own = ip.get(p['name'])
            source = p.get('source', '')
            actual = None
            if not source:
                add('unsatisfied_required_input', f'{nid}.{p["name"]}: no source')
                continue
            if source.startswith('external:'):
                key = source[9:]
                if key in hosts:
                    h = hosts[key]
                    actual = {'artifact_type': h['artifact_type']}
                    producers = [byid[d] for d in n['depends_on'] if d in byid and byid[d]['capability'] == h['producer_cc']]
                    if h['direct_predecessor_required'] and len(producers) != 1:
                        add('unsatisfied_required_input', f'{nid}: host {key} lacks unique direct producer')
                    if key == 'environment_lock' and not inventory.get(key, {}).get('ref'):
                        add('unsatisfied_required_input', f'{nid}: missing prepared environment lock')
                    if p.get('source_kind') not in (None, 'host_record'):
                        add('invented_input_or_resource', f'{nid}: {key} requires host_record binding')
                elif key == 'search_scope':
                    actual = {'artifact_type': 'search_scope'}
                    if not inventory.get('local_document_buffer', {}).get('ref'):
                        add('unsatisfied_required_input', f'{nid}: search_scope lacks original documents')
                elif key in external and (key == 'brief' or inventory.get(key, {}).get('available') and inventory.get(key, {}).get('ref')):
                    actual = external[key]
                else:
                    add('invented_input_or_resource', f'{nid}: unavailable external input {key}')
                    add('unsatisfied_required_input', f'{nid}.{p["name"]}: {key}')
                if p.get('accepted_ref') is not None:
                    add('invented_input_or_resource', f'{nid}: literal accepted artifact ref')
            elif '.' in source:
                producer, port = source.rsplit('.', 1)
                prev = byid.get(producer)
                if not prev or producer not in n['depends_on']:
                    add('cycle_or_unordered_dependency', f'{nid}: {source} is not a direct predecessor binding')
                pe = entries.get(prev.get('capability')) if prev else None
                actual = next((v for v in pe['output_ports'] if v['name'] == port), None) if pe else None
                if not actual or not prev or port not in prev.get('outputs', []):
                    add('unknown_or_missing_port', f'{nid}: nonexistent producer output {source}')
                    add('unsatisfied_required_input', f'{nid}.{p["name"]}: {source}')
            else:
                add('invented_input_or_resource', f'{nid}: unsupported source {source}')
                add('unsatisfied_required_input', f'{nid}.{p["name"]}')
            if own and actual and (actual['artifact_type'] != own['artifact_type'] or actual.get('schema_ref', own['schema_ref']) != own['schema_ref'] or p.get('artifact_type', own['artifact_type']) != own['artifact_type']):
                add('type_incompatible_binding', f'{nid}.{p["name"]}: {source}')
        for need in e['resource_needs']:
            r = inventory.get(need['resource_key'])
            if not r or not r['available'] or (need['min_quantity'] is not None and (r['quantity'] is None or r['quantity'] < need['min_quantity'])):
                add('invented_input_or_resource', f'{nid}: absent required resource {need["resource_key"]}')
        if e['effect_class'] not in policy['allowed_effect_classes'] or (e['network_mode'] != 'none' and not policy['allow_network']) or n.get('effect_class') not in (None, e['effect_class']) or n.get('authority'):
            add('effect_or_authority_violation', f'{nid}: effect/network/authority claim')
        authority_text = str(n.get('objective', '')) + ' ' + str(plan.get('notes', '')) + ' ' + str(n.get('acceptance_criteria', []))
        if re.search(r'(?i)\b(skip|waive|disable|bypass)\b.{0,60}\b(check|gate|verif)', authority_text):
            add('effect_or_authority_violation', f'{nid}: requested check waiver')
        for dim in ('time_s', 'model_calls', 'memory_mb'):
            v = n['limits'].get(dim)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= e['max_limits'][dim]:
                add('over_budget', f'{nid}: invalid or excessive {dim}')
        criteria = n.get('acceptance_criteria', [])
        if not criteria:
            add('missing_acceptance_criterion', str(nid))
        anchors = [*op, *lib['checks'].get(cap, [])]
        for criterion in criteria:
            total_ac += 1
            text = criterion if isinstance(criterion, str) else json.dumps(criterion, sort_keys=True)
            # Token boundaries prevent output 'result' matching 'results' or
            # 'summary' matching an invented 'summary_fake' check.
            if text.strip() and any(re.search(r'(?<![\w])' + re.escape(a) + r'(?![\w])', text) for a in anchors):
                good_ac += 1
            else:
                add('acceptance_not_machine_checkable', f'{nid}: {text}')
        covered.update(n.get('covers', []))
    # Graph ordering means explicit DAG dependencies; JSON node list order is
    # immaterial, matching the product's topological-sort semantics.
    remaining = {n.get('id'): set(n.get('depends_on', [])) & set(byid) for n in nodes}
    while remaining:
        ready = [k for k, deps in remaining.items() if not deps]
        if not ready:
            add('cycle_or_unordered_dependency', 'Dependency cycle')
            break
        for k in ready:
            remaining.pop(k)
        for deps in remaining.values():
            deps.difference_update(ready)
    for obligation in expected['obligations']:
        if obligation not in covered:
            add('uncovered_obligation', obligation)
    chosen = {n.get('capability') for n in nodes}
    for cap in expected['required_capabilities']:
        # Exact-type variants retain the original declared operation.
        if cap not in chosen and cap + '_typed' not in chosen:
            add('uncovered_obligation', 'Required work absent: ' + cap)
    for key in expected['required_inputs']:
        if not any(p.get('source') == 'external:' + key for n in nodes for p in n.get('inputs', [])):
            add('unsatisfied_required_input', 'Required task input unused: ' + key)
    if len(nodes) > policy['max_nodes']:
        add('over_budget', 'Node ceiling')
    for dim, ceiling in policy['aggregate_limits'].items():
        values = [n['limits'].get(dim, 0) for n in nodes]
        values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        total = sum(values)  # Benchmark explicitly sums all node reservations.
        if total > ceiling:
            add('over_budget', 'Aggregate ' + dim)
        if total < expected.get('minimum_limits', {}).get(dim, 0):
            add('uncovered_obligation', 'Mandatory reservation ' + dim)
    return result(defects, good_ac, total_ac, sorted(c for c in chosen if isinstance(c, str)), expected['feasible'])


def result(defects, good, total, caps, handling):
    counts = Counter(d['defect'] for d in defects)
    return dict(valid=not defects, defects=defects, counts={k: counts[k] for k in DEFECTS},
        machine_checkable=good, acceptance_total=total, capability_set=caps, infeasible_handling_correct=handling)


def score_raw(raw, condition, task, expected, library=None):
    try:
        value = parse_reply(raw, condition)
        scored = check(value, task, expected, library)
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        scored = result([dict(defect='uncovered_obligation', detail='Unparseable/malformed plan: ' + str(exc))], 0, 0, [], False)
        scored['parse_error'] = str(exc)
    if condition == 'A':
        scored['product_gate_failures'] = product_gate(raw, task, library)
    return scored


def product_gate(raw, task, library=None):
    from jiuwenswarm.research.binding import plan_checks
    from jiuwenswarm.research.planning import parse_planner_reply
    lib = library or build_library()
    p = declared_payload(task, lib)
    try:
        kind, candidate = parse_planner_reply(raw)
        if kind == 'infeasible':
            return []
        _, rows = plan_checks(candidate, p['brief'], p['library_snapshot'], p['resource_inventory'], p['plan_policy'],
            plan_source='planned', expected_refs={k: p[k] for k in ('brief_ref', 'library_snapshot_ref', 'resource_inventory_ref', 'policy_ref')})
        return [r for r in rows if r['outcome'] == 'FAIL']
    except Exception as exc:
        return [dict(check_id='plan_proposal_schema', outcome='FAIL', reason=str(exc))]
