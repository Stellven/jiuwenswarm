"""Original whole-parent resource classification; never an execution grant.

Read-only captured data can use the model path. Every physical/shared or
unresolved resource goes through the protected broker before any sibling.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from .contracts import ResearchError, contract_schema, validate


@dataclass(frozen=True)
class AttemptResourceDisposition:
    parent_ref: tuple[str, str]
    parent_identity: tuple[str, str, str]
    requires_broker: bool
    assignment_refs: tuple[tuple[str, str], ...]
    resource_uses: tuple[tuple[str, str, str], ...]


def _require(ok, detail):
    if not ok:
        raise ResearchError('attempt_resources', detail)


def _record(store, ref, kind, contract=None):
    validate('Ref', ref)
    _require(store.record_kind(ref) == kind, 'Original resource context has a different indexed kind')
    value = store.read_record(ref, **({'contract_id': contract} if contract else {}))
    _require(type(value) is dict, 'Original resource context is not a record')
    return value


def _pair(ref):
    validate('Ref', ref)
    return ref['id'], ref['sha256']


def _frozen_inventory(store, parent_ref, parent, supplied_ref):
    """Resolve the captured dispatch's inventory, never a caller omission.

    The fixed compiler has no RunPlan. A frozen-plan node has an inert
    original dispatch-preparation before native preflight, then its actual
    dispatch-start after activation. Both bind the exact immutable parent to
    the same plan, including a private evaluation's original source parent.
    """
    bindings = []
    for kind in ('run-plan-binding', 'finite-e1-plan-binding'):
        rows = list(store.iter_records(run_id=parent['run_id'], kinds=(kind,)))
        _require(len(rows) <= 1, 'Original run has ambiguous protected plan bindings')
        if not rows:
            continue
        value = rows[0]['record']
        if kind == 'run-plan-binding':
            _require(set(value) == {'id', 'run_id', 'plan_ref', 'recorded_at'}
                     and value['id'].startswith('run-plan-binding:'), 'Original run-plan binding is malformed')
        else:
            # Reuse the existing finite, read-only original-evidence validator;
            # a second hand-authored finite qualification interpretation would
            # create another authority for the same frozen plan.
            from .finite_evaluation import finite_evidence_refs
            proof = finite_evidence_refs(store, parent['run_id'])
            _require(proof is not None and proof['plan_binding_ref'] == rows[0]['ref'],
                     'Finite plan binding differs from its original protected qualification')
        _require(value['run_id'] == parent['run_id'], 'Protected plan binding belongs to another run')
        validate('Ref', value['plan_ref'])
        bindings.append(value['plan_ref'])
    _require(not bindings or all(ref == bindings[0] for ref in bindings),
             'Original protected run plan bindings disagree')
    starts = []
    for row in store.iter_records(run_id=parent['run_id'], kinds=('dispatch-preparation', 'dispatch-start')):
        start = row['record']
        if start.get('node_contract_ref') == parent_ref:
            fields = {'id', 'run_id', 'node_id', 'recorded_at', 'node_contract_ref', 'run_plan_ref',
                      'predecessor_commits', 'bound_input_refs'}
            _require(set(start) == fields and start['id'].startswith(row['kind'] + ':')
                     and start['run_id'] == parent['run_id'] and start['node_id'] == parent['node_id'],
                     'Original resource dispatch identity differs')
            starts.append(start)
    if not starts:
        for ref in bindings:
            known = _record(store, ref, 'run-plan', 'run-plan')
            _require(not (known['source_ref'] == parent['template_ref']
                          and any(node['node_id'] == parent['node_id'] for node in known['nodes'])),
                     'Frozen-plan parent has no original inert preparation or actual dispatch')
        return supplied_ref
    plan_ref = starts[0]['run_plan_ref']
    _require(all(start['run_plan_ref'] == plan_ref
                 and start['bound_input_refs'] == starts[0]['bound_input_refs']
                 and start['predecessor_commits'] == starts[0]['predecessor_commits'] for start in starts),
             'Original whole-parent preparation/start dispatch is ambiguous')
    if plan_ref is None:
        for ref in bindings:
            known = _record(store, ref, 'run-plan', 'run-plan')
            _require(not (known['source_ref'] == parent['template_ref']
                          and any(node['node_id'] == parent['node_id'] for node in known['nodes'])),
                     'Frozen-plan parent has a null original dispatch plan')
        return supplied_ref
    _require(not bindings or plan_ref == bindings[0],
             'Original dispatch differs from the protected frozen run-plan binding')
    plan = _record(store, plan_ref, 'run-plan', 'run-plan')
    nodes = [node for node in plan['nodes'] if node['node_id'] == parent['node_id']]
    work = [item for item in parent['subnodes'] if item['role'] == 'work']
    _require(plan['frozen'] is True and len(nodes) == 1 and len(work) == 1
             and plan['configuration_ref'] == parent['configuration_ref']
             and plan['policy_ref'] == parent['policy_ref']
             and plan['source_ref'] == parent['template_ref']
             and nodes[0]['limits'] == parent['node_limits']
             and nodes[0]['node_id'] == work[0]['subnode_id']
             and nodes[0]['cc']['declaration_sha256'] == work[0]['capsule_ref']['sha256'],
             'Frozen resource plan differs from the original whole-parent dispatch')
    inventory_ref = plan['resource_inventory_ref']
    _require(supplied_ref is None or supplied_ref == inventory_ref,
             'Supplied resource inventory differs from the original frozen plan')
    return inventory_ref


def _data_inputs(store, parent, *, inventory_ref=None,original_run_id=None):
    """Source-owned data associations, without inferring a host permission.

    An original request is reached through the exact qualified intake (direct
    compiler input or a captured Brief's intake_ref). Unknown typed resources
    never acquire a read-only exemption just by being labelled read.
    """
    original_requests = set()
    associated = {};brief_refs=[];search_scopes=[];paper_buffers=[]
    for port in parent['inputs']:
        _require(type(port) is dict and type(port.get('artifact_refs')) is list,
                 'Parent input association is malformed')
        for ref in port['artifact_refs']:
            raw = store.read_blob(ref)
            try:
                schema = contract_schema(port['contract_id'])
            except ResearchError:
                continue
            try:
                value = json.loads(raw)
                validate(port['contract_id'], value)
            except (ResearchError, ValueError, UnicodeError):
                continue
            qualified = contract_schema('qualified-intake')
            brief_schema = contract_schema('research-brief')
            direct_intake = schema == qualified
            if schema == brief_schema:
                brief_refs.append(ref)
                intake_ref = value['intake_ref']
                value = store.read_record(intake_ref, contract_id='qualified-intake')
                schema = qualified
            if schema == qualified:
                request_ref = value['request_ref']
                readable = request_ref in parent['authority_ceiling']['resource_reads']
                if direct_intake:
                    _require(readable,'Qualified original request exceeds the original read ceiling')
                # Brief lineage does not transfer raw-input read permission.
                # A declared original_request resource still needs an exact
                # readable association below or the protected broker path.
                if readable:
                    store.read_blob(request_ref)
                    original_requests.add(_pair(request_ref))
            if schema == contract_schema('resource-snapshot'):
                for key in ('baseline_resource', 'validation_resource'):
                    if port['name'] == key or value['id'] == key:
                        associated.setdefault(key, set()).add(_pair(ref))
            if schema == contract_schema('environment-lock'):
                associated.setdefault('environment_lock', set()).add(_pair(ref))
            if schema == contract_schema('search-scope'):
                _require(store.record_kind(ref)=='search-scope' and ref in parent['input_refs']
                    and ref in parent['authority_ceiling']['resource_reads'],
                    'Search scope lacks its original indexed input/read association')
                search_scopes.append(value)
            if port['contract_id'] == 'urn:ai4r:paper-document-buffer:1.0.0':
                _require(port['name'] == 'documents' and port['required'] is True
                    and len(port['artifact_refs']) == 1 and ref in parent['input_refs']
                    and ref in parent['authority_ceiling']['resource_reads'],
                    'Paper document buffer lacks its exact typed input/read association')
                paper_buffers.append(ref)
    if paper_buffers:
        from .summary_planning import validate_summary_documents
        from .unified_planning import paper_workflow_allowed
        _require(paper_workflow_allowed(store.read_record(parent['policy_ref'], contract_id='plan-policy'))
            and len(paper_buffers) == 1 and len(brief_refs) == 1 and inventory_ref is not None,
            'Paper document input is outside the exact protected summary policy/Brief/inventory')
        paper_inventory = store.read_record(inventory_ref, contract_id='resource-inventory')
        buffers = [item for item in paper_inventory['resources'] if item['resource_key'] == 'local_document_buffer']
        _require(len(buffers) == 1 and buffers[0]['ref'] == paper_buffers[0],
            'Typed paper input differs from the original frozen buffer inventory')
        brief = store.read_record(brief_refs[0], contract_id='research-brief')
        validate_summary_documents(store, brief, paper_inventory, inventory_ref, parent['authority_ceiling'])
        from .run_inputs import local_document_refs
        local_document_refs(store,paper_buffers[0],inventory_ref=inventory_ref,
            intake_ref=brief['intake_ref'],run_id=original_run_id)
        associated.setdefault('local_document_buffer',set()).add(_pair(paper_buffers[0]))
    for scope in search_scopes:
        _require(scope['brief_ref'] in brief_refs,'Original Search scope names another bound Brief')
        brief=store.read_record(scope['brief_ref'],contract_id='research-brief')
        if inventory_ref is not None:
            inventory=store.read_record(inventory_ref,contract_id='resource-inventory')
            buffers=[item for item in inventory['resources'] if item['resource_key']=='local_document_buffer']
            _require(len(buffers)<=1,'Original local document buffer inventory is ambiguous')
            if buffers and buffers[0]['ref'] is not None:
                buffer_ref=buffers[0]['ref']
                try:kind=store.record_kind(buffer_ref)
                except ResearchError as error:
                    if error.code!='evidence_unavailable':raise
                    kind=None
                if kind=='local-document-buffer':
                    from .run_inputs import local_document_refs
                    documents=local_document_refs(store,buffer_ref,inventory_ref=inventory_ref,
                        intake_ref=brief['intake_ref'],run_id=original_run_id)
                    _require(buffer_ref in parent['authority_ceiling']['resource_reads']
                        and scope['local_document_refs']==(documents if 'local_documents' in scope['connectors'] else []),
                        'Original run buffer/scope/document read provenance differs')
                    associated.setdefault('local_document_buffer',set()).add(_pair(buffer_ref))
        for ref in scope['local_document_refs']:
            _require(ref in parent['authority_ceiling']['resource_reads'],
                'Original Search local document exceeds the parent read ceiling')
            raw=store.read_blob(ref)
            _require(not raw.startswith(b'%PDF-') and bool(raw.strip()),'Search local resource is not captured extracted text')
            try:raw.decode('utf-8',errors='strict')
            except UnicodeError as error:raise ResearchError('attempt_resources','Search local resource is not captured UTF-8 text') from error
            associated.setdefault('local_document_buffer',set()).add(_pair(ref))
    if original_requests:
        associated['original_request'] = original_requests
    return associated


def attempt_resource_disposition(store, parent_ref, *, resource_inventory_ref=None):
    """Validate the frozen entire assignment union before classifying it.

    The original indexed dispatch resolves its frozen RunPlan inventory.
    An optional inventory is consistency input from the protected config,
    never a caller-selected resource or skip flag.
    The result supplies no service, lease, liveness or operation authority.
    """
    from .state import SQLiteRunStore
    _require(type(store) is SQLiteRunStore, 'Original protected Store is required for resource classification')
    kind = store.record_kind(parent_ref)
    private = kind == 'evaluation-node-context'
    if private:
        parent = _record(store, parent_ref, kind, 'urn:ai4r:private:evaluation-node-context:1')
        original = _record(store, parent['source_node_ref'], 'node-execution-contract', 'node-execution-contract')
        original_ref = parent['source_node_ref']
        _require(parent['subnodes'] == original['subnodes']
                 and all(parent[key] == original[key] for key in ('node_id', 'inputs', 'input_refs',
                         'authority_ceiling', 'configuration_ref', 'policy_ref')),
                 'Private whole-parent resource provenance differs from its original')
    else:
        parent = _record(store, parent_ref, 'node-execution-contract', 'node-execution-contract')
        original = parent
        original_ref = parent_ref
    _require(parent['input_refs'] == [ref for p in parent['inputs'] for ref in p['artifact_refs']],
             'Original whole-parent input order differs')
    assignments = parent['subnodes']
    _require(assignments and len({row['subnode_id'] for row in assignments}) == len(assignments),
             'Whole-parent assignments are empty or ambiguous')
    executable = tuple(assignments)
    if private:
        from .evaluation_projection import evaluation_resource_assignments
        executable = evaluation_resource_assignments(store, parent_ref)
        _require(type(executable) is tuple and executable
                 and len({item['subnode_id'] for item in executable}) == len(executable)
                 and all(item in assignments for item in executable),
                 'Private executable resource union differs from original approved assignments')
    executable_ids = {item['subnode_id'] for item in executable}
    inventory = None
    resource_inventory_ref = _frozen_inventory(store, original_ref, original, resource_inventory_ref)
    if resource_inventory_ref is not None:
        inventory = _record(store, resource_inventory_ref, 'resource-inventory', 'resource-inventory')
        keys = [row['resource_key'] for row in inventory['resources']]
        _require(len(keys) == len(set(keys)), 'Frozen resource inventory aliases are ambiguous')
        inventory = {row['resource_key']: row for row in inventory['resources']}
    associated = _data_inputs(store,parent,inventory_ref=resource_inventory_ref,original_run_id=original['run_id'])
    needs_broker = False
    resource_uses, assignment_refs = [], []
    for assignment in assignments:
        template = _record(store, assignment['template_ref'], 'subnode-template')
        _require(template['capsule_ref'] == assignment['capsule_ref']
                 and template['role'] == assignment['role']
                 and template['subnode_id'] == assignment['subnode_id']
                 and template['depends_on'] == assignment['depends_on'],
                 'Resource assignment differs from its exact original template')
        admission = _record(store, template['admission_ref'], 'library-admission', 'library-admission')
        # Raw admitted declaration blobs are legitimate; a different indexed
        # kind still refuses. Its admitted candidate and exact SHA join first.
        _require(admission['status'] == 'admitted' and admission['candidate_ref'] == assignment['capsule_ref']
                 and admission['cc'] == template['cc']
                 and template['cc']['declaration_sha256'] == assignment['capsule_ref']['sha256'],
                 'Resource declaration is not the exact originally admitted candidate')
        try:
            declaration_kind = store.record_kind(assignment['capsule_ref'])
        except ResearchError as error:
            if error.code != 'evidence_unavailable':
                raise
            declaration_kind = None
        _require(declaration_kind in (None, 'capsule-declaration'), 'Resource declaration has another indexed kind')
        declaration = store.read_record(assignment['capsule_ref'], contract_id='capsule-declaration')
        identity = declaration['identity']
        _require(template['ports'] == declaration['ports']
                 and admission['cc'] == {'cc_name': identity['name'], 'cc_version': identity['version_label'],
                                        'declaration_sha256': assignment['capsule_ref']['sha256']},
                 'Original resource declaration/template/identity differs')
        for body in identity['body']:
            ref = template['body_refs'][body['path']]
            _require(ref['sha256'] == body['sha256'], 'Original admitted body pin differs')
            store.read_blob(ref)
        for dependency in declaration['needs']['external']:
            for field in ('pin', 'lockfile'):
                pin = dependency.get(field)
                if pin:
                    ref = template['body_refs'][pin['ref']]
                    _require(ref['sha256'] == pin['sha256'], 'Original dependency pin differs')
                    store.read_blob(ref)
        # Preserve validation of the complete canonical provenance above;
        # only the original approved private schedule can execute below.
        # E2's historical producing worker never becomes a resource duty.
        if assignment['subnode_id'] not in executable_ids:
            continue
        assignment_refs.append(_pair(assignment['template_ref']))
        for need in declaration['needs']['resources']:
            key, mode = need['resource_key'], need['mode']
            resource_uses.append((assignment['subnode_id'], key, mode))
            if mode != 'read':
                needs_broker = True; continue
            if inventory is not None:
                resource = inventory.get(key)
                if (resource is None or resource['available'] is not True
                        or resource['kind'] not in {'file', 'dataset', 'repository'}):
                    needs_broker = True; continue
                ref = resource.get('ref')
                if ref is None or _pair(ref) not in associated.get(key, set()):
                    needs_broker = True
            elif not associated.get(key):
                needs_broker = True
        # Effects are not permissions. A mutable source declaration cannot
        # escape native preflight merely by omitting its resource inventory.
        if declaration['changes']['effect_class'] not in {'pure', 'read_only'}:
            needs_broker = True
    return AttemptResourceDisposition(_pair(parent_ref),
        tuple(parent[key] for key in ('run_id', 'node_id', 'attempt_id')),
        needs_broker, tuple(assignment_refs), tuple(resource_uses))
