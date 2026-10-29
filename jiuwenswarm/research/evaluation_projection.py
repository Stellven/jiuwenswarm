"""IF016 private projections. Shape reuse never supplies product authority."""
from __future__ import annotations

import copy
import json
from importlib.resources import files

from .contracts import ResearchError, validate


def require(condition, message, code='evaluation_authority'):
    if not condition:
        raise ResearchError(code, message)


def private_schema(kind):
    require(kind in PRIVATE_TYPES, 'Unknown private evaluation type')
    return json.loads(files('jiuwenswarm.research_contracts').joinpath('schemas', kind+'.schema.json').read_text('utf-8'))


PRIVATE_TYPES = frozenset('evaluation-runtime evaluation-request evaluation-node-context evaluation-subnode-context evaluation-checking-basis evaluation-scope evaluation-assignment-grant evaluation-call-claim evaluation-tool-claim evaluation-event evaluation-terminal evaluation-export'.split())


def private_record(store, ref, kind):
    require(kind in PRIVATE_TYPES and store.record_kind(ref) == kind, 'Private record kind does not match its immutable Ref')
    value = store.read_record(ref)
    version='1'
    if kind=='evaluation-event':
        identity=value.get('schema')
        require(identity in {'ai4r-evaluation-event:1','ai4r-evaluation-event:2'}, 'Unknown original private event identity')
        version=identity.rsplit(':',1)[1]
    validate('urn:ai4r:private:'+kind+':'+version, value)
    return value


def evaluation_resource_assignments(store,parent_ref):
    """Read only the original approved executable private assignment union.

    Canonical worker provenance is retained, but E2 only executes its selected
    reviewer. E3 reserves its source worker and every originally eligible output
    reviewer before work. This projection grants no liveness or start authority.
    """
    from .evaluation_history import EvaluationReader,encoded
    from .evaluation_inspection import source_closure,parent_projection,assignment_proof,original,admitted_declaration
    parent=private_record(store,parent_ref,'evaluation-node-context')
    request_ref=parent['request_ref'];request=private_record(store,request_ref,'evaluation-request')
    with store._lock:
        row=store.connection.execute('SELECT * FROM evaluation_requests WHERE request_ref=?',(encoded(request_ref),)).fetchone()
    require(row is not None,'Private resource schedule has no original durable request')
    reader=EvaluationReader(store,runtime_ref=request['runtime_ref'])
    runtime,_,actual_ref,request,row,scope_ref,scope=reader._owned_row(dict(row),request['request_id'])
    require(actual_ref==request_ref and scope is not None and scope['actual_node_ref']==parent_ref,
        'Private resource schedule belongs to another original scope')
    source=source_closure(store,runtime,request,scope)
    require(parent_projection(store,parent_ref,request_ref,request,scope,source)==parent,
        'Private resource parent projection differs')
    _,events=reader._journal(request_ref,row,scope_ref)
    grants={}
    for _,event in events:
        ref=event['assignment_grant_ref']
        if ref is not None and encoded(ref) not in grants:
            grants[encoded(ref)]=assignment_proof(store,ref,request_ref,scope_ref,request,scope,parent,source)
    require(grants,'Private resource schedule has no original prepared assignment grant')
    worker=source['source'];selected=[]
    for assignment in parent['subnodes']:
        template=original(store,assignment['template_ref'],'subnode-template')
        require(all(template[key]==assignment[key] for key in ('subnode_id','role','depends_on'))
            and template['capsule_ref']==assignment['capsule_ref'],
            'Private executable assignment differs from its original template')
        if assignment['role']=='work':
            if request['entry_point']=='E3' and assignment['subnode_id']==worker['subnode_id']:
                require(assignment['template_ref']==worker['template_ref']
                    and assignment['capsule_ref']==worker['bindings'][0]['declaration_ref'],
                    'Private source worker differs from original executable assignment')
                selected.append(assignment)
            continue
        if template.get('subject_subnode_id')!=worker['subnode_id']:
            continue
        port=template.get('output_port')
        require(port in {item['name'] for item in worker['outputs']},
            'Private potential reviewer names another source output')
        if request['entry_point']=='E3' or port==scope['selected_output_port']:
            selected.append(assignment)
    require(len(selected)==len({item['subnode_id'] for item in selected}) and selected,
        'Private executable resource schedule is empty or ambiguous')
    for assignment in selected:
        template=original(store,assignment['template_ref'],'subnode-template')
        admitted_declaration(store,assignment['capsule_ref'],template['admission_ref'],source['snapshot'])
    if request['entry_point']=='E2':
        require(len(selected)==1 and selected[0]['role']=='verifier'
            and all(proof[0]['role']=='verifier' and proof[0]['output_port']==scope['selected_output_port']
                and proof[1]['subnode_id']==selected[0]['subnode_id'] for proof in grants.values()),
            'Replay executable schedule is not its one approved selected reviewer')
    else:
        require(request['entry_point']=='E3' and len([item for item in selected if item['role']=='work'])==1
            and any(proof[0]['role']=='worker' for proof in grants.values())
            and all(proof[1]['subnode_id'] in {item['subnode_id'] for item in selected} for proof in grants.values()),
            'Single executable schedule differs from its approved worker/reviewer union')
    return tuple(copy.deepcopy(selected))


class EvaluationProjectionAdapter:
    """Installed capability bound to one actual authority/store/runtime.

    Every load checks the durable ledger before interpreting structurally reused
    fields. A freshly captured lookalike record has no dispatch authority.
    """
    def __init__(self, authority):
        from .evaluation_authority import EvaluationAuthority
        require(type(authority) is EvaluationAuthority, 'Only an installed evaluation owner can create projections')
        self.owner, self.store = authority, authority.store

    def create_node_context(self, request_ref):
        return self.owner._create_node(request_ref)

    def create_assignment_context(self, scope_ref, role, output_port):
        return self.owner._create_assignment_context(scope_ref, role, output_port)

    def create_checking_basis(self, scope_ref, assignment_context_ref, mode):
        return self.owner._create_basis(scope_ref, assignment_context_ref, mode)

    def load_execution(self, assignment_grant_ref):
        owner = self.owner
        grant = private_record(self.store, assignment_grant_ref, 'evaluation-assignment-grant')
        row = owner._assignment(grant['execution_id'])
        require(row is not None and json.loads(row['grant_ref']) == assignment_grant_ref,
                'Assignment is not the exact durable registered grant')
        request = owner._request(grant['request_ref'])
        scope = owner._scope(grant['scope_ref'])
        require(scope['request_ref'] == grant['request_ref'] and request['runtime_ref'] == owner.runtime_ref,
                'Assignment belongs to another private request')
        child = private_record(self.store, grant['contract_ref'], 'evaluation-subnode-context')
        basis = private_record(self.store, grant['check_plan_ref'], 'evaluation-checking-basis')
        expected_child, expected_basis = owner._assignment_projection(scope, grant['role'], grant['output_port'],
            child_id=child['id'], basis_id=basis['id'], child_ref=grant['contract_ref'])
        require(child == expected_child and basis == expected_basis,
                'Private execution projection differs from original approved closure')
        require(basis['assignment_context_ref'] == grant['contract_ref'] and child['request_ref'] == grant['request_ref'],
                'Private checking basis targets a different assignment')
        owner._current_runtime()
        return copy.deepcopy(grant), child, basis

    def host_check_context(self, scope_ref, assignment_grant_ref=None):
        scope = self.owner._scope(scope_ref)
        if assignment_grant_ref is None:
            source, plan, parent, _, _, _ = self.owner._source(scope['request_ref'])
            return source, plan, parent
        grant, child, basis = self.load_execution(assignment_grant_ref)
        require(grant['scope_ref'] == scope_ref, 'Host checks belong to another request')
        return child, basis, private_record(self.store, scope['actual_node_ref'], 'evaluation-node-context')

    def register_capture(self, assignment_grant_ref, capture_kind, capture_ref):
        return self.owner.register_capture(assignment_grant_ref, capture_kind, capture_ref)
