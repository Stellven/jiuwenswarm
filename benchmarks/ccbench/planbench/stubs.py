"""Stub replies for --stub runs and the unit tests. No model is involved.

A stub is built from a task's reference plan (referee/gold.json) by a *variant*:
  good        the reference plan (an infeasible task gets a one-line INFEASIBLE with the right reason)
  unbindable  the first step is dropped and the second step is bound straight to the supplied input
  fabricated  an invented capability name and an invented input key
  infeasible  a generic INFEASIBLE with no reason that matches the fault
  wrong_input binds the decoy input where the task has one (otherwise = good)
  partial     (skill only) the good plan labelled "feasible": "partial"
The same neutral plan is rendered in each arm's own dialect (plan-proposal JSON for CC, the
neutral JSON object for the skill arm). The skill dialect adds the quirks real replies have
(prose around the JSON, bare capability names, "input:KEY" sources, its own output names).
"""
import sys
sys.dont_write_bytecode = True
import copy
import json
import re

VARIANTS = ('good', 'unbindable', 'fabricated', 'infeasible', 'wrong_input', 'partial')

GENERIC_REASON = 'No available capability can complete this request.'


def neutral(task, gold, variant):
    """Return a neutral plan (or an infeasible dict) for the variant."""
    g = gold[task['id']]
    if variant == 'infeasible':
        return {'kind': 'infeasible', 'reason': GENERIC_REASON}
    if not g['feasible']:
        if variant in ('good',):
            word = re.sub(r'\\.|\(|\)|\?|\|.*', '', g['reason_regex'].split('|')[0]) or 'missing'
            return {'kind': 'infeasible', 'reason': 'Cannot be done: %s is required (%s).' % (word, g['missing'])}
        # a plan for an infeasible task: use some plausible executable chain
        return {'kind': 'plan', 'complete_claim': variant != 'partial', 'issues': [], 'final': 's1',
                'steps': [{'id': 's1', 'capability': 'utility.calculate', 'outputs': ['result'], 'depends_on': [], 'covers': ['D1'],
                           'criteria': [], 'inputs': [{'param': 'packet', 'src': {'external': next(iter(task['inputs']))}}]}]}
    plan = copy.deepcopy(g['reference_plan'])
    steps = plan['steps']
    if variant == 'unbindable':
        first, second = steps[0], steps[1]
        second['inputs'][0]['src'] = copy.deepcopy(first['inputs'][0]['src'])
        second['depends_on'] = []
        plan['steps'] = steps[1:]
    elif variant == 'fabricated':
        steps[0]['capability'] = 'utility.table_summarize'
        steps[0]['inputs'][0]['src'] = {'external': 'dataset_main'}
    elif variant == 'wrong_input' and g['decoys']:
        for s in steps:
            for i in s['inputs']:
                if i['src'].get('external') in {k for k in task['inputs']} - set(g['decoys']):
                    i['src'] = {'external': g['decoys'][0]}
    elif variant == 'partial':
        plan['complete_claim'] = False
    return plan


# ----------------------------------------------------------------------------------------------
# skill dialect
# ----------------------------------------------------------------------------------------------

def to_skill_reply(plan, quirks=True):
    if plan['kind'] == 'infeasible':
        return json.dumps({'feasible': False, 'reason': plan['reason'], 'steps': [], 'final_step': None})
    steps = []
    for s in plan['steps']:
        inputs = {}
        for i in s['inputs']:
            src = i['src']
            inputs[i['param']] = ('input:' + src['external']) if 'external' in src else src['step']
        cap = s['capability']
        steps.append({'id': s['id'], 'capability': cap.split('.', 1)[1] if quirks and cap.startswith('utility.') and cap.count('.') == 1 and s['id'].endswith('1') else cap,
                      'inputs': inputs, 'depends_on': s['depends_on'], 'covers': s['covers'],
                      'success_criteria': s.get('criteria') or ['The step output contains the requested result.']})
    obj = {'feasible': True if plan.get('complete_claim', True) else 'partial', 'reason': '', 'steps': steps, 'final_step': plan.get('final')}
    body = json.dumps(obj, indent=2)
    return ('Here is the plan.\n```json\n' + body + '\n```\n') if quirks else body


# ----------------------------------------------------------------------------------------------
# CC dialect: a complete plan-proposal for the pinned schema
# ----------------------------------------------------------------------------------------------

def to_cc_reply(plan, task, refs, lib):
    """Render a neutral plan as a plan-proposal JSON string (or the INFEASIBLE line)."""
    if plan['kind'] == 'infeasible':
        return 'INFEASIBLE: ' + plan['reason'][:280]
    entries = {e['cc_name']: e for e in lib['library_snapshot']['entries']}
    b = task['brief']
    d_ids = [d['id'] for d in b['deliverables']]
    req = [r['id'] for r in b['mandatory_requirements']]
    steps = plan['steps']
    used = {i['src']['step'] for s in steps for i in s['inputs'] if 'step' in i['src']}
    leaf = [s['id'] for s in steps if s['id'] not in used][-1]
    by_step = {s['id']: entries.get(s['capability']) for s in steps}

    def out_ports(e):
        # Output port names and types come from the library entry (the product retypes outputs, e.g. table_packet).
        if not e:
            return [dict(name='result', artifact_type='work_packet', required=True)]
        return [dict(name=p['name'], artifact_type=p['artifact_type'], required=p['required']) for p in e['output_ports']]
    nodes = []
    for s in steps:
        e = entries.get(s['capability'])
        pin = (dict(cc_name=e['cc_name'], cc_version=e['cc_version'], declaration_sha256=e['declaration_sha256'])
               if e else dict(cc_name=s['capability'], cc_version='m1-1', declaration_sha256='0' * 64))
        ins = []
        for i in s['inputs']:
            src = i['src']
            port = next((p for p in (e['input_ports'] if e else [])), None)
            pname = port['name'] if port else i['param']
            atype = port['artifact_type'] if port else 'work_packet'
            if 'external' in src:
                ins.append(dict(name=pname, artifact_type=atype, required=True, source_kind='accepted_ref', run_input_key=src['external'], accepted_ref=None, future=None))
            else:
                produced = out_ports(by_step[src['step']])[0]
                ins.append(dict(name=pname, artifact_type=atype, required=True, source_kind='future_output', run_input_key=None, accepted_ref=None,
                                future=dict(producer_node=src['step'], port=produced['name'], artifact_type=produced['artifact_type'])))
        lim = dict(time_s=30, model_calls=0, memory_mb=256)
        nodes.append(dict(node_id=s['id'], cc=pin, objective='Run %s on the packet.' % s['capability'],
                          requirement_ids=req, deliverable_ids=d_ids if s['id'] == leaf else [],
                          predecessors=sorted({i['src']['step'] for i in s['inputs'] if 'step' in i['src']}), inputs=ins,
                          outputs=out_ports(e), limits=lim,
                          suggested_checks=['result_schema', 'result_integrity']))
    coverage = [dict(item_id=x['id'], item_kind=k, node_ids=[leaf] if k != 'requirement' else [s['id'] for s in steps])
                for k, f in (('requirement', 'mandatory_requirements'), ('deliverable', 'deliverables'), ('evidence_obligation', 'evidence_obligations'))
                for x in b[f]]
    proposal = dict(schema_version='3.0.0', id='plan.' + task['id'].replace('_', '-')[:40], brief_ref=refs['brief'], library_snapshot_ref=refs['library_snapshot'],
                    resource_inventory_ref=refs['resource_inventory'], policy_ref=refs['plan_policy'], plan_source='planned',
                    nodes=nodes, coverage=coverage, topic_hints=[], limits=dict(time_s=30 * len(nodes), model_calls=0, memory_mb=256), notes='')
    return json.dumps(proposal)
