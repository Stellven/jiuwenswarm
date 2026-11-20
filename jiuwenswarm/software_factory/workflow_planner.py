"""Contract and model-based planning over the persisted Workflow Library.

The model chooses references and links. Deterministic admission resolves those
references; neither UI presets nor this module contain task-specific DAGs.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from .contracts import StageBlocked, StageFailure
from .workflow_library import WorkflowLibrary, admit_graph, digest, port_kind, write_json

POLICY_PATH = Path(__file__).with_name('workflow_prompts') / 'composer_policy.md'
POLICY = POLICY_PATH.read_text(encoding='utf-8')

CONTRACT_POLICY = """# Contract planner

Start with the requested artifact types. For each required output or input,
find the one registered part and output port that declares that type. Resolve
that part's required inputs in the same way. Reuse a selected part if another
step needs one of its outputs. Apply only parameters declared by the part.

Stop if a producer is missing, ambiguous, or would introduce a cycle. Use the
standard task graph admission to check every version, binding and output.
"""

PROTOCOL = '''Respond with one JSON object, no Markdown.
To use tools: {"tool_calls":[{"name":"library.search","arguments":{"query":"..."}}]}.
Tools:
- library.search(query): find actual workflow cards. Search is retrieval, not a selected plan.
- library.read(workflow_id, version optional): read one actual Workflow and all named parts.
- library.inspect_part(workflow_id, version, subworkflow): read a part and its Agent prompt if applicable.
- library.read_source(workflow_id, version, path): read bounded source evidence inside that project.
You may request multiple independent reads in a response.
After reading each selected Workflow, return one decision for each selected Workflow.
Its selected_parts must match the graph nodes exactly. Explain why those parts fit the request and why unused siblings were omitted.
{"proposal":{"decisions":[{"workflow_id":"...","selected_parts":["..."],"reason":"why these and not the other parts"}],
"graph":{"nodes":[{"id":"task_name","workflow":{"id":"...","version":"sha256:..."},"subworkflow":"part_id","parameters":{},"bindings":{"port":{"node":"other_node or $input","port":"output_port"}}}],
"inputs":{"external_input_name":{"artifact_id":"published artifact id"}},
"outputs":{"deliverable_name":{"node":"producer_node","port":"output_port"}}},
"unmet_requirements":[]}}.
No arbitrary path bindings. Copy versions exactly. Preserve declared semantic types.
Expose all Task Contract required_outputs. Inputs with no ports use {}.
Root inputs can be empty. Node ids must begin with a letter and be unique.
Only include workflow parameters that the part actually needs; pinned source defaults cannot be changed.
Do not execute jobs, modify source or create the graph file yourself. Return the proposal JSON only.
'''


def parse_json(text):
    value = text.strip()
    if value.startswith('```'):
        lines=value.splitlines()
        value='\n'.join(lines[1:-1])
    try:
        result=json.loads(value)
    except (ValueError,TypeError) as error:
        raise StageFailure('invalid_model_output','Planner returned invalid JSON') from error
    if not isinstance(result,dict):
        raise StageFailure('invalid_model_output','Planner response must be an object')
    return result


def feedback_observation(feedback):
    """Bound model context while retaining the complete execution on disk."""
    result={key:feedback.get(key) for key in ('id','status','error')}
    result['graph_revision']=feedback.get('graph',{}).get('graph_revision',0)
    result['nodes']=[]
    for node in feedback.get('nodes',[]):
        value={key:node.get(key) for key in ('id','status','origin','error','outputs')}
        if node.get('status') in {'failed','blocked'}:
            value['commands']=[{**{key:command.get(key) for key in ('argv','exit_code','stdout_path','stderr_path')},
                                'stdout':command.get('stdout','')[-2000:],
                                'stderr':command.get('stderr','')[-4000:]}
                               for attempt in node.get('attempts',[]) for command in attempt.get('commands',[])][-3:]
        result['nodes'].append(value)
    return result


def _port_label(port):
    return port if isinstance(port, str) else port.get('name', port_kind(port))


def compose_contract(resolver, task, *, emit=None, extra_catalogs=(), parameters_for=None, finalize_nodes=None):
    """Choose pinned registered steps by output kind and bind their required inputs."""
    workflows = resolver.list()
    catalogs = [(workflow, 'library') for workflow in workflows]
    catalogs.extend(extra_catalogs)
    keys = [(scope['id'], part['id']) for scope, _ in catalogs for part in scope['subworkflows']]
    readable_ids = {key: '.'.join(key) for key in keys}
    counts = Counter('.'.join(key) for key in keys)
    node_ids = {key: name if len(name) <= 96 and counts[name] == 1 else f'{name[:79]}-{digest(list(key))[:16]}'
                for key, name in readable_ids.items()}
    producers = {}
    for scope, origin in catalogs:
        for component in scope['subworkflows']:
            for name, definition in component['outputs'].items():
                producers.setdefault(port_kind(definition), []).append((scope, origin, component, name))

    nodes, selected = {}, {}
    active = set()
    sequence = 0

    def record(event_type, policy_rule, **fields):
        nonlocal sequence
        if emit is not None:
            sequence += 1
            emit({'sequence': sequence, 'type': event_type, 'policy_rule': policy_rule, **fields})

    def provenance(scope, origin, component):
        if origin == 'build_action':
            return {'origin': origin, 'action': scope['id'] + '.' + component['id']}
        return {'origin': origin, 'workflow': scope['id'], 'part': component['id']}

    def supply(kind, **consumer):
        choices = producers.get(kind, [])
        record('lookup', 'exact-contract', kind=kind, candidates=[
            {'id': node_ids[(scope['id'], component['id'])], 'name': component['name'], 'port': output,
             'label': _port_label(component['outputs'][output]), **provenance(scope, origin, component)}
            for scope, origin, component, output in choices
        ], **consumer)
        if len(choices) != 1:
            code = 'ambiguous_producer' if choices else 'missing_producer'
            raise StageFailure(code, 'A result must have one eligible producer: ' + kind)
        scope, origin, component, output = choices[0]
        node_id = node_ids[(scope['id'], component['id'])]
        source = provenance(scope, origin, component)
        label = _port_label(component['outputs'][output])
        if node_id in active:
            raise StageFailure('graph_cycle', 'Cyclic output requirement: ' + kind)
        if node_id not in nodes:
            if len(nodes) + len(active) >= 40:
                raise StageFailure('invalid_graph', 'Propose between 1 and 40 actual tasks')
            record('select', 'exact-contract', kind=kind, node=node_id, name=component['name'],
                   port=output, label=label, **source, **consumer)
            active.add(node_id)
            parameters = deepcopy(parameters_for(scope, component)) if parameters_for else {}
            bindings = {}
            for port_id, definition in component['inputs'].items():
                if isinstance(definition, str) or definition.get('required', True):
                    input_kind = port_kind(definition)
                    record('need_input', 'dependencies', node=node_id, port=port_id,
                           kind=input_kind, label=_port_label(definition))
                    bindings[port_id] = supply(input_kind, consumer=node_id, input=port_id)
            nodes[node_id] = {'id': node_id, 'workflow': {'id': scope['id'], 'version': scope['version']},
                              'subworkflow': component['id'], 'parameters': parameters, 'bindings': bindings}
            selected[node_id] = {'name': component['name'], 'output': label, 'needed_for': kind, **source}
            if origin == 'library':
                selected[node_id]['workflow_name'] = scope['name']
            active.remove(node_id)
            record('add_node', 'dependencies', node=node_id, name=component['name'],
                   kind=kind, bindings=deepcopy(bindings), **source)
            for port_id, binding in bindings.items():
                contract = component['inputs'][port_id]
                input_kind = port_kind(contract)
                record('bind', 'dependencies', **{'from': binding['node'], 'to': node_id,
                       'output': binding['port'], 'input': port_id, 'kind': input_kind,
                       'label': _port_label(contract)})
        else:
            record('reuse', 'reuse', kind=kind, node=node_id, port=output, label=label, **source, **consumer)
        return {'node': node_id, 'port': output}

    outputs = {}
    for kind in task['required_outputs']:
        record('require_output', 'requested-results', kind=kind)
        outputs[kind] = supply(kind)
    if finalize_nodes:
        finalize_nodes(nodes, record)
    for workflow in workflows:
        for component in workflow['subworkflows']:
            node_id = node_ids[(workflow['id'], component['id'])]
            if node_id not in nodes:
                record('leave_unselected', 'reuse', node=node_id, origin='library', workflow=workflow['id'],
                       part=component['id'], name=component['name'],
                       outputs=[port_kind(port) for port in component['outputs'].values()])
    proposal = {'nodes': list(nodes.values()), 'outputs': outputs}
    graph = admit_graph(resolver, proposal, task)
    record('finalize', 'admission', node_order=[node['id'] for node in graph['nodes']],
           output_kinds=list(graph['outputs']))
    return graph, selected


def _validate_task_contract(task):
    if not isinstance(task, dict) or not isinstance(task.get('description'), str) or not task['description'].strip():
        raise StageFailure('invalid_task_contract', 'Task requires a description')
    outputs = task.get('required_outputs')
    if (not isinstance(outputs, list) or not outputs
            or not all(isinstance(kind, str) and kind for kind in outputs)):
        raise StageFailure('invalid_task_contract', 'Declare required_outputs as semantic artifact kinds')
    if any(not isinstance(task.get(key, {}), dict) for key in ('parameters', 'acceptance', 'source')):
        raise StageFailure('invalid_task_contract', 'parameters, acceptance and source must be objects')
    operations = task.get('parameters', {}).get('operations')
    if operations is not None and (not isinstance(operations, list) or not operations
            or not all(isinstance(operation, str) and operation for operation in operations)):
        raise StageFailure('invalid_task_contract', 'operations must list the required source operations')


def _native_acceptance(task):
    acceptance = task.get('acceptance', {})
    return [{'requirement': key, 'status': 'unverified',
             'reason': 'This Library source/CPU-reference graph does not prove full native model acceptance.'}
            for key in ['native_compile', 'native_model_inference', 'compare_original'] if acceptance.get(key)]


def plan_contract(library: WorkflowLibrary, task: dict, workspace: Path, *, emit=None):
    """Plan an executable graph from exact registered contracts without a model."""
    _validate_task_contract(task)
    supplied = task.get('step_parameters', {})
    if not isinstance(supplied, dict) or any(not isinstance(value, dict) for value in supplied.values()):
        raise StageFailure('invalid_task_contract', 'step_parameters must map part references to parameter objects')
    emit = emit or (lambda *_: None)
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    policy = CONTRACT_POLICY
    policy_file = workspace / 'composer_policy.md'
    policy_sha256 = digest(policy.encode())
    policy_file.write_text(policy, encoding='utf-8')
    write_json(workspace / 'task_contract.json', task)
    emit('planner.started', {'task': task, 'policy': policy, 'policy_sha256': policy_sha256,
                             'planner_type': 'contract'})

    trace = []

    def observe(decision):
        trace.append(decision)
        emit('planner.decision', decision)

    graph, selections = compose_contract(
        library, task, emit=observe,
        parameters_for=lambda scope, part: supplied.get(f"{scope['id']}.{part['id']}", {}),
    )
    by_workflow = {}
    for selection in selections.values():
        by_workflow.setdefault(selection['workflow'], []).append(selection)
    unused = supplied.keys() - {f"{part['workflow']}.{part['part']}" for part in selections.values()}
    if unused:
        raise StageFailure('unused_parameters', 'No selected part for step_parameters: ' + ', '.join(sorted(unused)))
    decisions = [
        {'workflow_id': workflow_id, 'selected_parts': [part['part'] for part in parts],
         'reason': 'Matched declared outputs: ' + ', '.join(part['output'] for part in parts)}
        for workflow_id, parts in by_workflow.items()
    ]
    unmet = _native_acceptance(task)
    graph['unmet_requirements'] = unmet
    graph['policy_ref'] = {'path': str(policy_file), 'sha256': policy_sha256}
    result = {'graph': graph, 'decisions': decisions, 'unmet_requirements': unmet, 'invocations': [],
              'tool_calls': [], 'policy': policy, 'policy_sha256': policy_sha256,
              'planner_type': 'contract', 'decisions_trace': trace}
    write_json(workspace / 'graph.json', graph)
    write_json(workspace / 'planning.json', result)
    emit('planner.graph_created', result)
    return result


class WorkflowPlanner:
    def __init__(self, library: WorkflowLibrary, driver=None):
        self.library=library
        if driver is None:
            from .model_driver import CodexDriver
            driver=CodexDriver()
        self.driver=driver

    def plan(self, task:dict, workspace:Path, *, policy=None, artifacts=None, feedback=None, emit=None, max_turns=8):
        workspace=Path(workspace).resolve();workspace.mkdir(parents=True,exist_ok=True)
        policy=policy or POLICY
        emit=emit or (lambda *_:None)
        _validate_task_contract(task)
        if not isinstance(policy,str) or len(policy)>64_000:
            raise StageFailure('invalid_policy','Policy must be nonempty Markdown text under 64 KB')
        workflows=self.library.list()
        if not workflows:
            raise StageBlocked('library_empty','Import and register actual projects before planning')
        (workspace/'composer_policy.md').write_text(policy)
        write_json(workspace/'task_contract.json',task)
        catalog=[{'id':w['id'],'version':w['version'],'name':w['name'],
                  'repository':w['source']['repository']} for w in workflows]
        available=[{k:a[k] for k in ['id','kind','sha256','producer','size'] if k in a} for a in artifacts or []]
        history=[];seen=set();calls=[];invocations=[]
        if feedback:
            history.append({'previous_execution':feedback_observation(feedback)})
            write_json(workspace/'previous_execution.json',feedback)
        emit('planner.started',{'task':task,'policy':policy,'policy_sha256':digest(policy.encode()),'catalog':catalog})
        for turn in range(max_turns):
            write_json(workspace/'observations.json',history)
            instruction=(policy+'\n\n'+PROTOCOL+'\n\n'+json.dumps({
                'task_contract':task,'library_index':catalog,'available_artifacts':available,
                'previous_tool_results_and_defects':history},ensure_ascii=False))
            emit('planner.model_requested',{'turn':turn+1,'request_sha256':digest(instruction.encode())})
            response=self.driver.run(instruction,workspace,emit=emit,sandbox='read-only',timeout=300)
            invocations.append(response.get('invocation',{}))
            emit('planner.model_response',{'turn':turn+1,'text':response['text'],
                                           'invocation':response.get('invocation',{})})
            try:
                body=parse_json(response['text'])
                if 'tool_calls' in body:
                    if not isinstance(body['tool_calls'],list) or not 1<=len(body['tool_calls'])<=8:
                        raise StageFailure('invalid_tool_request','Request 1-8 bounded tool calls')
                    for request in body['tool_calls']:
                        if not isinstance(request,dict):
                            raise StageFailure('invalid_tool_request','Each tool request must be an object')
                        name=request.get('name');args=request.get('arguments',{})
                        emit('planner.tool_started',{'name':name,'arguments':args})
                        result=self._tool(name,args,seen)
                        receipt={'name':name,'arguments':args,'result':result}
                        calls.append(receipt);history.append(receipt)
                        emit('planner.tool_finished',receipt)
                    continue
                proposal=body.get('proposal')
                if not isinstance(proposal,dict):
                    raise StageFailure('invalid_model_output','Return tool_calls or proposal')
                decisions=proposal.get('decisions',[])
                unmet=deepcopy(proposal.get('unmet_requirements',[]))
                if not isinstance(unmet,list) or not all(isinstance(item,(dict,str)) for item in unmet):
                    raise StageFailure('invalid_unmet_requirements','unmet_requirements must be an array of requirements')
                if (not isinstance(decisions,list) or not decisions
                        or any(not isinstance(d,dict) or not isinstance(d.get('reason'),str)
                               or not d['reason'].strip() or not isinstance(d.get('selected_parts'),list)
                               for d in decisions)):
                    raise StageFailure('missing_selection_reason','Explain why each Workflow/part is selected')
                graph=admit_graph(self.library,proposal,task,artifacts)
                actual_parts={}
                for node in graph['nodes']:
                    ref=node.get('workflow',{})
                    if (ref.get('id'),ref.get('version')) not in seen:
                        raise StageFailure('unread_workflow','Read the actual selected Workflow before planning: '+str(ref.get('id')))
                    actual_parts.setdefault(ref['id'],set()).add(node['subworkflow'])
                explained_parts={}
                for decision in decisions:
                    workflow_id=decision.get('workflow_id')
                    selected=decision['selected_parts']
                    if (not isinstance(workflow_id,str) or workflow_id in explained_parts
                            or not selected or not all(isinstance(part,str) for part in selected)
                            or len(selected)!=len(set(selected))):
                        raise StageFailure('inconsistent_decision','Provide one decision per selected Workflow and list each selected part once')
                    explained_parts[workflow_id]=set(selected)
                if explained_parts!=actual_parts:
                    raise StageFailure('inconsistent_decision','Selection explanations must identify exactly the parts present in the Task Graph')
                if feedback:
                    graph['graph_revision']=feedback.get('graph',{}).get('graph_revision',0)+1
                    graph['previous_execution_ref']=feedback['id']
                unmet.extend(_native_acceptance(task))
                graph['unmet_requirements']=unmet
                graph['policy_ref']={'path':str(workspace/'composer_policy.md'),'sha256':digest(policy.encode())}
                result={'graph':graph,'decisions':decisions,'unmet_requirements':unmet,
                        'invocations':invocations,'tool_calls':calls,'policy':policy,
                        'policy_sha256':digest(policy.encode())}
                write_json(workspace/'proposal.json',proposal);write_json(workspace/'graph.json',graph)
                write_json(workspace/'planning.json',result)
                emit('planner.graph_created',result)
                return result
            except (StageFailure,KeyError,TypeError,ValueError,OSError) as error:
                defect={'code':getattr(error,'code','invalid_proposal'),'message':str(error)}
                history.append({'validation_defect':defect})
                emit('planner.proposal_rejected',defect)
        raise StageFailure('planning_budget_exhausted','Planner did not produce an admissible graph within its model-call budget')

    def _tool(self,name,args,seen):
        if not isinstance(args,dict):
            raise StageFailure('invalid_tool_request','Tool arguments must be an object')
        if name=='library.search':
            return [{'id':w['id'],'version':w['version'],'name':w['name'],
                     'parts':[{'id':p['id'],'name':p['name']} for p in w['subworkflows']]}
                    for w in self.library.search(str(args.get('query','')))[:12]]
        if name=='library.read':
            workflow=self.library.get(args['workflow_id'],args.get('version'))
            seen.add((workflow['id'],workflow['version']))
            return workflow
        if name=='library.inspect_part':
            workflow=self.library.get(args['workflow_id'],args.get('version'))
            seen.add((workflow['id'],workflow['version']))
            part=self.library.resolve(workflow['id'],workflow['version'],args['subworkflow'])
            if part['implementation']['type']=='agent':
                part['instruction']=Path(part['implementation']['prompt_path']).read_text()
            return part
        if name=='library.read_source':
            result=self.library.read_source(args['workflow_id'],args.get('version'),args['path'])
            if len(result['content'])>64_000:
                result.update(total_characters=len(result['content']),truncated=True)
                result['content']=result['content'][:64_000]
            return result
        raise StageFailure('unknown_planner_tool',str(name))
