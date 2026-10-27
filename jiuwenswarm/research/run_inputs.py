"""Host-captured ordinary run inputs, with no execution or service authority."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass

from .contracts import ResearchError,validate
from .run_input_types import typed_resource
from .state import json_bytes

BUFFER_FIELDS={'schema','id','run_id','account_id','workspace_id','intake_ref','source_refs'}
BINDING_FIELDS={'schema','id','run_id','account_id','workspace_id','intake_ref',
    'base_resource_inventory_ref','resource_inventory_ref','buffer_ref','read_refs'}
PROVENANCE_FIELDS={'original_parent_ref','original_run_id','run_plan_ref','input_binding_ref',
    'base_resource_inventory_ref','resource_inventory_ref','input_read_refs'}


def require(condition,message):
    if not condition:raise ResearchError('run_inputs',message)


@dataclass(frozen=True,slots=True)
class OriginalRunInputInventory:
    """Read-only original provenance; this object installs no capability."""
    _encoded: bytes

    @property
    def record(self):
        return json.loads(self._encoded)

    @classmethod
    def from_record(cls,value):
        require(type(value) is dict and set(value)==PROVENANCE_FIELDS,
            'Original input-inventory provenance is not closed')
        require(type(value['original_run_id']) is str and bool(value['original_run_id']),
            'Original input-inventory run is absent')
        for key in PROVENANCE_FIELDS-{'original_run_id','input_read_refs'}:
            validate('Ref',value[key])
        refs=value['input_read_refs']
        # Qualified-intake source_refs has the existing maximum64; request and
        # buffer add two references, without adding a new product allowance.
        require(type(refs) is list and 2<=len(refs)<=64+2,
            'Original input read population differs from qualified intake bounds')
        for ref in refs:validate('Ref',ref)
        require(len(refs)==len({(ref['id'],ref['sha256']) for ref in refs}),
            'Original input read population is ambiguous')
        return cls(json_bytes(value))


def identity(kind,run_id):
    return kind+':'+hashlib.sha256(run_id.encode('utf-8')).hexdigest()


def _intake(store,run):
    ref=run['submission']['intake_ref']
    require(store.record_kind(ref)=='qualified-intake','Run intake lacks its original indexed kind')
    intake=store.read_record(ref,contract_id='qualified-intake')
    require(intake['user_id']==run['account_id'],'Qualified intake belongs to another account')
    docs=[];resources=[];ids=set()
    for upload_ref in intake['upload_refs']:
        require(store.record_kind(upload_ref)=='client-upload','Qualified upload has another original kind')
        upload=store.read_record(upload_ref,contract_id='client-upload')
        require(upload['user_id']==run['account_id'] and upload['scope_id']==run['workspace_id']
            and upload['status']=='uploaded' and upload['id'] not in ids,
            'Qualified upload belongs to another actor/workspace or is ambiguous')
        ids.add(upload['id'])
        if upload['kind']=='docs':docs.append(upload['text_sha256'])
        else:resources.append(upload['content_sha256'])
    require([ref['sha256'] for ref in intake['source_refs']]==docs
        and [ref['sha256'] for ref in intake['resource_refs']]==resources,
        'Qualified captured document/resource order differs from original uploads')
    store.read_blob(intake['request_ref']).decode('utf-8',errors='strict')
    for document_ref in intake['source_refs']:
        raw=store.read_blob(document_ref)
        require(not raw.startswith(b'%PDF-') and bool(raw.strip()),'Qualified document has no extracted text')
        raw.decode('utf-8',errors='strict')
    return ref,intake


def _inventory(store,base_ref,intake,buffer_ref):
    base=store.read_record(base_ref,contract_id='resource-inventory')
    keys=[item['resource_key'] for item in base['resources']]
    require(len(keys)==len(set(keys)),'Prepared resource inventory is ambiguous')
    replacements={
        'original_request':typed_resource({'resource_key':'original_request','kind':'file','available':True,'quantity':None,'ref':intake['request_ref']}),
        'local_document_buffer':typed_resource({'resource_key':'local_document_buffer','kind':'dataset','available':True,
            'quantity':len(intake['source_refs']),'ref':buffer_ref})}
    result=copy.deepcopy(base)
    for index,item in enumerate(result['resources']):
        key=item['resource_key']
        if key in replacements:
            require(item['kind'] in {'file','dataset'},'Reserved request/document alias names an incompatible physical/host resource')
            result['resources'][index]=replacements.pop(key)
        else:result['resources'][index]=typed_resource(item)
    result['resources'].extend(replacements.values())
    result['id']='run_inputs_'+hashlib.sha256(json_bytes([base_ref,intake['request_ref'],buffer_ref])).hexdigest()[:40]
    validate('resource-inventory',result)
    return result


def prepare_run_inputs(store,run_id,principal,protected):
    """Only a fresh allocated ordinary submit calls this capture operation."""
    from .state import SQLiteRunStore
    require(type(store) is SQLiteRunStore,'Actual protected run Store is required')
    require(protected.get('finite_e1_binding_ref') is None and protected.get('profile_id') is None,
        'Qualified finite/profile snapshots cannot be rebound')
    run=store.get_run(run_id,account_id=principal.account_id)
    principal.require('submit',run['workspace_id'])
    require(run['state']=='pending' and not store.cancellation_requested(run_id),
        'Stopped or already issued run cannot capture fresh inputs')
    require(not list(store.iter_records(run_id=run_id,kinds=('run-input-binding',))),
        'Run input preparation was already consumed; reconcile without replay')
    intake_ref,intake=_intake(store,run)
    require(run['submission']['configuration_ref']==protected['configuration_ref']
        and all(intake[key]==protected[key] for key in ('profile_ref','workspace_ref','input_directory_ref')),
        'Run input capture differs from protected initialization/qualified intake')
    buffer={'schema':'ai4r-local-document-buffer:1','id':identity('local-document-buffer',run_id),
        'run_id':run_id,'account_id':run['account_id'],'workspace_id':run['workspace_id'],
        'intake_ref':intake_ref,'source_refs':copy.deepcopy(intake['source_refs'])}
    buffer_ref=store.append_record('local-document-buffer',buffer)
    inventory=_inventory(store,protected['resource_inventory_ref'],intake,buffer_ref)
    inventory_ref=store.put_record('resource-inventory',inventory,scope={'run_id':run_id})
    reads=[intake['request_ref'],*intake['source_refs'],buffer_ref]
    require(len(reads)==len({(ref['id'],ref['sha256']) for ref in reads}),'Current run input references are ambiguous')
    binding={'schema':'ai4r-run-input-binding:1','id':identity('run-input-binding',run_id),
        'run_id':run_id,'account_id':run['account_id'],'workspace_id':run['workspace_id'],'intake_ref':intake_ref,
        'base_resource_inventory_ref':protected['resource_inventory_ref'],'resource_inventory_ref':inventory_ref,
        'buffer_ref':buffer_ref,'read_refs':reads}
    store.append_record('run-input-binding',binding)
    # Validate the exact immutable published joins before using the context.
    local_document_refs(store,buffer_ref,inventory_ref=inventory_ref,intake_ref=intake_ref)
    context=copy.deepcopy(protected);context['resource_inventory_ref']=inventory_ref
    authority=context['authority_ceiling']
    for ref in reads:
        if ref not in authority['resource_reads']:authority['resource_reads'].append(copy.deepcopy(ref))
    return context


def prepare_linked_run_inputs(store,original_run_id,linked_run_id,protected,*,principal,base_protected):
    """Capture only the transactionally allocated ordinary replan's own inputs."""
    from .state import SQLiteRunStore
    require(type(store) is SQLiteRunStore,'Actual protected run Store is required')
    require(protected.get('finite_e1_binding_ref') is None and protected.get('profile_id') is None,
        'Qualified finite/profile snapshots cannot be rebound')
    original=store.get_run(original_run_id);linked=store.get_run(linked_run_id,account_id=original['account_id'])
    require(principal is not None and principal.account_id==original['account_id'] and type(base_protected) is dict,
        'Original authenticated caller/pre-capture context is unavailable; no replay or inferred grant')
    principal.require('submit',original['workspace_id'])
    require(original['state']=='halted' and original['reason']=='plan_infeasible'
        and original['submission'].get('plan_source')=='planned'
        and linked['workspace_id']==original['workspace_id'] and linked['state']=='pending',
        'Linked capture is not newly allocated ordinary planned infeasibility work')
    with store._lock:
        parent_lineage=store.connection.execute('SELECT * FROM plan_lineage WHERE run_id=?',(original_run_id,)).fetchone()
        child_lineage=store.connection.execute('SELECT * FROM plan_lineage WHERE run_id=?',(linked_run_id,)).fetchone()
    require(parent_lineage is not None and child_lineage is not None
        and parent_lineage['linked_run_id']==linked_run_id and parent_lineage['depth']==1
        and child_lineage['depth']==2 and child_lineage['root_run_id']==parent_lineage['root_run_id']
        and child_lineage['linked_run_id'] is None,'Linked run has no exact bounded original lineage')
    original_intake_ref,original_intake=_intake(store,original)
    linked_intake_ref,linked_intake=_intake(store,linked)
    outcome_ref=linked_intake.get('prior_plan_outcome_ref')
    require(outcome_ref is not None and store.record_kind(outcome_ref)=='plan-outcome',
        'Linked intake lacks its original plan outcome')
    outcomes=[row for row in store.iter_records(run_id=original_run_id,kinds=('plan-outcome',)) if row['ref']==outcome_ref]
    require(len(outcomes)==1,'Linked outcome belongs to another original run')
    outcome=store.read_record(outcome_ref,contract_id='plan-outcome')
    require(outcome['outcome']=='plan_infeasible' and outcome['attempt_depth']==1
        and outcome['linked_attempt_id']==linked_run_id and outcome['next_stage']=='intention_compiler'
        and store.is_accepted(outcome['brief_ref'],run_id=original_run_id),
        'Linked work differs from its original accepted Brief/outcome')
    require(linked_intake==dict(original_intake,id=linked_intake['id'],prior_plan_outcome_ref=outcome_ref)
        and linked['submission']==dict(original['submission'],id=linked['submission']['id'],
            client_request_id=linked['submission']['client_request_id'],intake_ref=linked_intake_ref),
        'Linked work changes the original qualified inputs or protected submission')
    rows=list(store.iter_records(run_id=original_run_id,kinds=('run-input-binding',)))
    require(len(rows)==1,'Original run input binding is absent or ambiguous')
    binding=rows[0]['record']
    # This reopens all original actor/intake/buffer/base/derived joins, rather
    # than accepting a base Ref or read list supplied by the linked caller.
    local_document_refs(store,binding['buffer_ref'],inventory_ref=protected['resource_inventory_ref'],
        intake_ref=original_intake_ref,run_id=original_run_id)
    context=copy.deepcopy(base_protected)
    require(context['resource_inventory_ref']==binding['base_resource_inventory_ref']
        and store.record_kind(context['resource_inventory_ref'])=='resource-inventory',
        'Original prepared inventory has another indexed kind')
    expected=copy.deepcopy(context);expected['resource_inventory_ref']=binding['resource_inventory_ref']
    for ref in binding['read_refs']:
        if ref not in expected['authority_ceiling']['resource_reads']:
            expected['authority_ceiling']['resource_reads'].append(copy.deepcopy(ref))
    require(expected==protected,'Original pre-capture context does not reconstruct the actual parent context')
    # The standard fresh-allocation guard forbids a second capture. Start from
    # the actual frozen pre-capture context, never subtract guessed authority
    # or treat a derived inventory as the separately installed science base.
    return prepare_run_inputs(store,linked_run_id,principal,context)


def local_document_refs(store,buffer_ref,*,inventory_ref=None,intake_ref=None,run_id=None):
    """Read exact original buffer custody; this supplies no live authority."""
    validate('Ref',buffer_ref)
    require(store.record_kind(buffer_ref)=='local-document-buffer','Buffer has another indexed original kind')
    buffer=store.read_record(buffer_ref)
    require(set(buffer)==BUFFER_FIELDS and buffer['schema']=='ai4r-local-document-buffer:1'
        and buffer['id']==identity('local-document-buffer',buffer['run_id'])
        and store.record_ref(buffer['id'])==buffer_ref,'Original closed run buffer identity differs')
    run=store.get_run(buffer['run_id'],account_id=buffer['account_id'])
    require(run['workspace_id']==buffer['workspace_id'] and (run_id is None or run['id']==run_id)
        and run['submission']['intake_ref']==buffer['intake_ref']
        and (intake_ref is None or intake_ref==buffer['intake_ref']),
        'Run buffer belongs to another original actor/workspace/intake')
    original_ref,intake=_intake(store,run)
    require(original_ref==buffer['intake_ref'] and buffer['source_refs']==intake['source_refs'],
        'Run buffer changed the original extracted document order')
    rows=list(store.iter_records(run_id=run['id'],kinds=('run-input-binding',)))
    require(len(rows)==1,'Original run input binding is missing or ambiguous')
    binding=rows[0]['record']
    require(set(binding)==BINDING_FIELDS and binding['schema']=='ai4r-run-input-binding:1'
        and binding['id']==identity('run-input-binding',run['id']) and store.record_ref(binding['id'])==rows[0]['ref']
        and all(binding[key]==buffer[key] for key in ('run_id','account_id','workspace_id','intake_ref'))
        and binding['buffer_ref']==buffer_ref
        and binding['read_refs']==[intake['request_ref'],*intake['source_refs'],buffer_ref]
        and (inventory_ref is None or inventory_ref==binding['resource_inventory_ref']),
        'Original run input binding differs from its exact buffer/context')
    require(store.record_kind(binding['resource_inventory_ref'])=='resource-inventory',
        'Derived run inventory has another original indexed kind')
    actual=store.read_record(binding['resource_inventory_ref'],contract_id='resource-inventory')
    require(actual==_inventory(store,binding['base_resource_inventory_ref'],intake,buffer_ref),
        'Derived run inventory changed prepared scientific/host resources')
    return copy.deepcopy(buffer['source_refs'])


def resolve_original_run_inputs(store,parent_ref):
    """IF001r3 finite original-Store query; never choose or register a runtime.

    The parent alone determines all returned provenance. The existing whole-
    parent validator and frozen-inventory equality remain the single readers
    of canonical/private dispatch and executable-assignment ownership.
    """
    from .state import SQLiteRunStore
    from .attempt_resources import attempt_resource_disposition,_frozen_inventory
    require(type(store) is SQLiteRunStore,'Actual original Store is required')
    validate('Ref',parent_ref)
    attempt_resource_disposition(store,parent_ref)
    parent=store.read_record(parent_ref)
    if store.record_kind(parent_ref)=='evaluation-node-context':
        original_ref=parent['source_node_ref']
    else:
        original_ref=parent_ref
    require(store.record_kind(original_ref)=='node-execution-contract',
        'Original input inventory parent is not canonical')
    original=store.read_record(original_ref,contract_id='node-execution-contract')
    run_id=original['run_id']
    bindings=list(store.iter_records(run_id=run_id,kinds=('run-input-binding',)))
    if not bindings:return None
    require(len(bindings)==1,'Original run input binding is ambiguous')
    bound=bindings[0];binding=bound['record']
    require(type(binding) is dict and set(binding)==BINDING_FIELDS,
        'Original run input binding is not closed')
    inventory_ref=_frozen_inventory(store,original_ref,original,None)
    require(inventory_ref is not None,'Original input binding has no required frozen plan')
    local_document_refs(store,binding['buffer_ref'],inventory_ref=inventory_ref,run_id=run_id)
    require(store.record_kind(binding['base_resource_inventory_ref'])=='resource-inventory',
        'Original registered base inventory has another kind')
    run=store.get_run(run_id,account_id=binding['account_id'])
    require(run['id']==run_id and run['workspace_id']==binding['workspace_id']
        and run['submission']['configuration_ref']==original['configuration_ref']
        and run['submission'].get('profile_id') is None
        and not list(store.iter_records(run_id=run_id,kinds=('finite-e1-plan-binding',))),
        'Original ordinary run input binding changes its protected execution scope')
    dispatches=[row for row in store.iter_records(run_id=run_id,
        kinds=('dispatch-preparation','dispatch-start'))
        if row['record'].get('node_contract_ref')==original_ref]
    require(dispatches and all(row['record']['run_plan_ref'] is not None for row in dispatches),
        'Original input binding has no exact frozen dispatch')
    plan_ref=dispatches[0]['record']['run_plan_ref']
    require(all(row['record']['run_plan_ref']==plan_ref for row in dispatches),
        'Original input binding has ambiguous frozen dispatches')
    require(store.record_kind(plan_ref)=='run-plan','Original input plan has another kind')
    plan=store.read_record(plan_ref,contract_id='run-plan')
    require(plan['resource_inventory_ref']==inventory_ref
        and plan['configuration_ref']==original['configuration_ref']
        and plan['policy_ref']==original['policy_ref'],'Original input plan pins differ')
    # A produced Brief is captured JSON bytes, not a host record-kind row.
    # Its current-run Compiler commit and advancing Gate establish custody.
    from .binding import committed_output_proof
    compiler=committed_output_proof(store,run_id,'intention_compiler')
    require(compiler['outputs']=={'brief':plan['brief_ref']},
        'Original input plan Brief lacks its exact committed Compiler output')
    brief=store.read_record(plan['brief_ref'],contract_id='research-brief')
    require(brief['intake_ref']==binding['intake_ref'],
        'Original input plan Brief belongs to another qualified intake')
    # Compare original protected insertion order, not caller timestamps. All
    # queried identities are already independently derived and hash-checked.
    ordered_refs=[binding['buffer_ref'],inventory_ref,bound['ref'],plan_ref,
        *[row['ref'] for row in dispatches]]
    identities=[ref['id'] for ref in ordered_refs]
    require(len(identities)==len(set(identities)),'Original input capture identities overlap')
    with store._lock:
        marks=store.connection.execute('SELECT rowid,id FROM records WHERE id IN ('
            +','.join('?' for _ in identities)+')',identities).fetchall()
    order={row['id']:row['rowid'] for row in marks}
    require(set(order)==set(identities)
        and order[binding['buffer_ref']['id']]<order[inventory_ref['id']]<order[bound['ref']['id']]
        <order[plan_ref['id']]
        and all(order[plan_ref['id']]<order[row['ref']['id']] for row in dispatches),
        'Original run input capture did not precede its frozen plan/dispatch')
    return OriginalRunInputInventory.from_record({
        'original_parent_ref':original_ref,'original_run_id':run_id,'run_plan_ref':plan_ref,
        'input_binding_ref':bound['ref'],'base_resource_inventory_ref':binding['base_resource_inventory_ref'],
        'resource_inventory_ref':inventory_ref,'input_read_refs':binding['read_refs']})
