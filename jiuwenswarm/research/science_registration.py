"""Installed scientific-operation mappings, distinct from captured data.

Only the fixed root bootstrap constructs this object after installed build and
factory verification. Actual prerequisite checks remain mandatory per start
and per effect. Current CPU-only factories cannot qualify GPU operations.
"""
from __future__ import annotations

import copy
import json
import os

from .attempt_resources import AttemptResourceDisposition,attempt_resource_disposition
from .contracts import ResearchError,validate
from .executor import ExecutorBlocked,RestrictedExecutor
from .science_runtime import OPERATIONS,decode_science_runtime_record


_SEAL=object()
FACTORIES=('job_factory','provisioner','hardware_probe','verify_mount','environment_verifier','score_result')
INPUT_ALIASES=frozenset(('original_request','local_document_buffer'))
INVENTORY_MISMATCH='Supplied resource inventory differs from the original frozen plan'


def _require(ok,reason):
    if not ok:raise ExecutorBlocked(reason)


class _InstalledRunMapping:
    """Instance-bound, non-transportable registration; its record is only data."""
    __slots__=('_owner','_parent_ref','_template_ref','_encoded')

    def __init__(self,owner,parent_ref,assignment,entry,*,provenance,derived,seal):
        _require(seal is _SEAL,'INSTALLED_SCIENCE_REGISTRATION_REQUIRED')
        owner._current()
        _require(entry in owner.definition.record['execution_bindings'],
                 'SCIENCE_ORIGINAL_EXECUTION_MAPPING_REQUIRED')
        effective=copy.deepcopy(entry)
        if derived:
            _require(provenance is not None
                and entry['resource_inventory_ref']==provenance['base_resource_inventory_ref'],
                'SCIENCE_ORIGINAL_BASE_MAPPING_REQUIRED')
            effective['resource_inventory_ref']=copy.deepcopy(provenance['resource_inventory_ref'])
        # No operation, admission, policy, implementation or permission changes.
        self._owner=owner
        self._parent_ref=copy.deepcopy(parent_ref)
        self._template_ref=copy.deepcopy(assignment['template_ref'])
        self._encoded=json.dumps(effective,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

    def entry(self,owner,parent_ref,assignment):
        _require(owner is self._owner and parent_ref==self._parent_ref
            and assignment['template_ref']==self._template_ref,'SCIENCE_INSTALLED_MAPPING_SCOPE_CHANGED')
        owner._current()
        return json.loads(self._encoded)


class InstalledScienceRuntime:
    def __init__(self,*,store,backend,runtime_ref,definition,seal):
        _require(seal is _SEAL and os.geteuid()==0 and type(backend) is RestrictedExecutor,
                 'INSTALLED_SCIENCE_REGISTRATION_REQUIRED')
        self.store,self.backend=store,backend
        self.runtime_ref=copy.deepcopy(runtime_ref);self.definition=definition
        self._installed_store,self._installed_backend=store,backend
        self._runtime_pin=copy.deepcopy(runtime_ref)
        self._definition_pin=definition
        self._record_pin=definition.record
        self.factories={name:getattr(backend,name,None) for name in FACTORIES}
        _require(all(callable(value) for value in self.factories.values()),'PROTECTED_EXECUTION_FACTORIES_UNAVAILABLE')
        self._agent_service=None
        if any('builder_action' in row['operations'] for row in self._record_pin.get('execution_bindings',[])):
            self._agent_service=getattr(backend,'builder_agent_service',None)
            _require(callable(getattr(self._agent_service,'action',None)),'BUILDER_AGENT_SERVICE_UNAVAILABLE')

    def _current(self):
        _require(self.backend.execution_mode == self.definition.record.get('execution_mode','restricted'),
                 'SCIENCE_EXECUTION_MODE_CHANGED')
        if self.backend.execution_mode == 'm1_app_process':
            _require(self.backend.runtime_ref == self.runtime_ref, 'SCIENCE_RUNTIME_CAPTURE_CHANGED')
        _require(os.geteuid()==0 and self.store is self._installed_store
                 and self.backend is self._installed_backend
                 and self.runtime_ref==self._runtime_pin and self.definition is self._definition_pin
                 and self.definition.record==self._record_pin
                 and getattr(self.backend,'science_registration',None) is self,
                 'SCIENCE_REGISTRATION_NOT_INSTALLED')
        _require(all(getattr(self.backend,name,None) is value for name,value in self.factories.items()),
                 'SCIENCE_INSTALLED_FACTORY_CHANGED')
        if self._agent_service is not None:
            _require(getattr(self.backend,'builder_agent_service',None) is self._agent_service,
                     'SCIENCE_INSTALLED_BUILDER_AGENT_CHANGED')
        _require(self.store.record_kind(self.runtime_ref)=='science-runtime'
                 and self.store.read_record(self.runtime_ref)==self.definition.record,'SCIENCE_RUNTIME_CAPTURE_CHANGED')

    def _template_mappings(self,parent,assignment):
        template=self.store.read_record(assignment['template_ref'])
        _require(self.store.record_kind(assignment['template_ref'])=='subnode-template'
                 and template['capsule_ref']==assignment['capsule_ref']
                 and template['role']==assignment['role'] and template['subnode_id']==assignment['subnode_id'],
                 'SCIENCE_ASSIGNMENT_TEMPLATE_MISMATCH')
        declaration=self.store.read_record(assignment['capsule_ref'],contract_id='capsule-declaration')
        admission=self.store.read_record(template['admission_ref'],contract_id='library-admission')
        _require(self.store.record_kind(template['admission_ref'])=='library-admission'
                 and admission['status']=='admitted' and admission['candidate_ref']==assignment['capsule_ref']
                 and admission['cc']==template['cc'],'SCIENCE_ORIGINAL_ADMISSION_REQUIRED')
        implementations=[template['body_refs'][body['path']] for body in declaration['identity']['body']]
        dependencies=[template['body_refs'][pin['ref']] for dependency in declaration['needs']['external']
                      for key in ('pin','lockfile') if (pin:=dependency.get(key))]
        expected={'configuration_ref':parent['configuration_ref'],'policy_ref':parent['policy_ref'],
                  'declaration_ref':assignment['capsule_ref'],'implementation_refs':implementations,
                  'dependency_refs':dependencies,'admission_ref':template['admission_ref']}
        entries=[entry for entry in self.definition.record['execution_bindings']
                 if all(entry[key]==value for key,value in expected.items())]
        return entries

    def _original_inputs(self,parent_ref,parent,disposition):
        from .run_inputs import OriginalRunInputInventory,resolve_original_run_inputs
        if hasattr(self.store,'resolve_original_run_inputs'):
            proof=self.store.resolve_original_run_inputs(parent_ref)
        else:
            proof=resolve_original_run_inputs(self.store,parent_ref)
        if proof is None:return None
        _require(type(proof) is OriginalRunInputInventory,'ORIGINAL_RUN_INPUT_PROOF_REQUIRED')
        record=proof.record
        _require(type(record) is dict and set(record)=={'original_parent_ref','original_run_id','run_plan_ref',
            'input_binding_ref','base_resource_inventory_ref','resource_inventory_ref','input_read_refs'},
            'ORIGINAL_RUN_INPUT_PROOF_REQUIRED')
        for key in ('original_parent_ref','run_plan_ref','input_binding_ref',
                    'base_resource_inventory_ref','resource_inventory_ref'):
            validate('Ref',record[key])
        reads=record['input_read_refs']
        _require(type(reads) is list and reads,'ORIGINAL_RUN_INPUT_READS_REQUIRED')
        for ref in reads:validate('Ref',ref)
        _require(len(reads)==len({(ref['id'],ref['sha256']) for ref in reads}),
                 'ORIGINAL_RUN_INPUT_READS_AMBIGUOUS')
        kind=self.store.record_kind(parent_ref)
        source_ref=parent['source_node_ref'] if kind=='evaluation-node-context' else parent_ref
        _require(record['original_parent_ref']==source_ref
            and self.store.record_kind(source_ref)=='node-execution-contract',
            'ORIGINAL_RUN_INPUT_PARENT_MISMATCH')
        source=self.store.read_record(source_ref,contract_id='node-execution-contract')
        _require(record['original_run_id']==source['run_id'],'ORIGINAL_RUN_INPUT_RUN_MISMATCH')
        for ref in (record['base_resource_inventory_ref'],record['resource_inventory_ref']):
            _require(self.store.record_kind(ref)=='resource-inventory','ORIGINAL_RESOURCE_INVENTORY_REQUIRED')
        base=self.store.read_record(record['base_resource_inventory_ref'],contract_id='resource-inventory')
        current=self.store.read_record(record['resource_inventory_ref'],contract_id='resource-inventory')
        _require([item for item in base['resources'] if item['resource_key'] not in INPUT_ALIASES]
            ==[item for item in current['resources'] if item['resource_key'] not in INPUT_ALIASES],
            'SCIENCE_NONINPUT_RESOURCE_CHANGED')
        aliases={item['resource_key']:item for item in current['resources'] if item['resource_key'] in INPUT_ALIASES}
        _require(set(aliases)==INPUT_ALIASES
            and aliases['original_request']['kind']=='file'
            and aliases['local_document_buffer']['kind']=='dataset'
            and all(item['available'] is True and item['ref'] in reads for item in aliases.values()),
            'SCIENCE_CAPTURED_INPUT_ALIASES_REQUIRED')
        _require(all(mode=='read' for _,key,mode in disposition.resource_uses if key in INPUT_ALIASES),
                 'SCIENCE_INPUT_ALIAS_EFFECT_FORBIDDEN')
        return record

    def _resolve(self,contract):
        self._current();parent_ref=contract['node_contract_ref'];parent=self.store.read_record(parent_ref)
        classified={}
        def classify(inventory_ref=None):
            if hasattr(self.store,'attempt_resource_disposition'):
                result=self.store.attempt_resource_disposition(parent_ref,resource_inventory_ref=inventory_ref)
            else:
                result=attempt_resource_disposition(self.store,parent_ref,resource_inventory_ref=inventory_ref)
            _require(type(result) is AttemptResourceDisposition,'WHOLE_ATTEMPT_RESOURCE_BINDING_REQUIRED')
            return result
        original=classify()
        provenance=self._original_inputs(parent_ref,parent,original)
        def applicable(ref):
            key=(ref['id'],ref['sha256'])
            if key not in classified:
                try:
                    classified[key]=classify(ref)
                except ResearchError as error:
                    # Only this exact strict frozen-plan mismatch excludes an
                    # otherwise registered inventory. Corrupt scope must raise.
                    if error.code!='attempt_resources' or error.message!=INVENTORY_MISMATCH:raise
                    classified[key]=None
            return classified[key]
        executable=set(original.assignment_refs)
        mappings={};inventories=[]
        for assignment in parent['subnodes']:
            if (assignment['template_ref']['id'],assignment['template_ref']['sha256']) not in executable:continue
            entries=self._template_mappings(parent,assignment)
            exact=[entry for entry in entries if applicable(entry['resource_inventory_ref']) is not None]
            _require(len(exact)<=1,'SCIENCE_EXECUTION_MAPPING_AMBIGUOUS')
            derived=False
            if exact:
                selected=exact[0]
            elif provenance is not None:
                bases=[entry for entry in entries
                    if entry['resource_inventory_ref']==provenance['base_resource_inventory_ref']]
                _require(len(bases)<=1,'SCIENCE_EXECUTION_MAPPING_AMBIGUOUS')
                selected=bases[0] if bases else None
                derived=selected is not None
            else:
                selected=None
            if selected is None:continue
            mapping=_InstalledRunMapping(self,parent_ref,assignment,selected,
                provenance=provenance,derived=derived,seal=_SEAL)
            entry=mapping.entry(self,parent_ref,assignment)
            if provenance is not None:
                _require(entry['resource_inventory_ref']==provenance['resource_inventory_ref'],
                         'SCIENCE_FROZEN_DERIVED_INVENTORY_MISMATCH')
            mappings[assignment['subnode_id']]=mapping
            inventories.append(entry['resource_inventory_ref'])
        _require(inventories and all(ref==inventories[0] for ref in inventories),'WHOLE_PARENT_SCIENCE_MAPPING_UNAVAILABLE')
        ref=inventories[0]
        _require(self.store.record_kind(ref)=='resource-inventory','ORIGINAL_RESOURCE_INVENTORY_REQUIRED')
        # The pure helper reconstructs every sibling, not merely this child's
        # host calls. The custody proxy exposes only that finite read operation.
        result=applicable(ref)
        _require(type(result) is AttemptResourceDisposition and result.requires_broker,
                 'WHOLE_ATTEMPT_RESOURCE_BINDING_REQUIRED')
        inventory=self.store.read_record(ref,contract_id='resource-inventory')
        resources={item['resource_key']:item for item in inventory['resources']}
        for _,key,mode in result.resource_uses:
            resource=resources.get(key)
            _require(resource is not None and resource['available'] is True,'SCIENCE_RESOURCE_UNAVAILABLE')
            if resource['kind']=='gpu':
                # Current SameSandboxHardwareCapture explicitly rejects GPU
                # device profiles. A declared JSON flag cannot install one.
                raise ExecutorBlocked('GPU_SCIENTIFIC_FACTORY_UNAVAILABLE')
            _require(mode!='exclusive','UNSUPPORTED_EXCLUSIVE_RESOURCE_DOMAIN')
        _require(self.definition.record['gpu_required'] is False,'GPU_SCIENTIFIC_FACTORY_UNAVAILABLE')
        return result,parent_ref,parent,mappings

    def disposition(self,contract):
        return self._resolve(contract)[0]

    async def validate_preparation(self,preparation_ref,prepared,response):
        self._current()
        from .invocation_start import validate_invocation_preparation
        if hasattr(self.store,'validate_invocation_preparation'):
            child=self.store.validate_invocation_preparation(preparation_ref,response)
        else:
            child=validate_invocation_preparation(self.store,preparation_ref,response)
        _require(child==response['contract'],'PREPARED_CUSTODY_MISMATCH')
        failures=self.backend.prerequisites()
        _require(not failures,';'.join(failures) if failures else 'SCIENCE_RUNTIME_UNAVAILABLE')
        self.disposition(child)

    def require_operation(self,binding,operation,contract):
        self._current()
        _require(operation in OPERATIONS,'INVALID_EXECUTOR_OPERATION')
        _,parent_ref,parent,mappings=self._resolve(contract)
        _require(self.store.read_record(binding['contract_ref'])==contract and len(contract['bindings'])==1,
                 'SCIENCE_ORIGINAL_ACTIVE_CHILD_REQUIRED')
        assignments=[item for item in parent['subnodes'] if item['subnode_id']==contract['subnode_id']]
        _require(len(assignments)==1,'SCIENCE_ORIGINAL_ASSIGNMENT_REQUIRED')
        installed=mappings.get(contract['subnode_id'])
        _require(type(installed) is _InstalledRunMapping,'SCIENCE_OPERATION_NOT_REGISTERED')
        mapping=installed.entry(self,parent_ref,assignments[0])
        _require(operation in mapping['operations'],'SCIENCE_OPERATION_NOT_REGISTERED')
        selected=contract['bindings'][0]
        for key in ('declaration_ref','implementation_refs','dependency_refs','admission_ref'):
            _require(selected[key]==mapping[key],'SCIENCE_EXECUTION_MAPPING_MISMATCH')
        _require(not self.backend.prerequisites(),'SCIENCE_RUNTIME_PREREQUISITES_UNAVAILABLE')


def install_science_runtime(*,store,backend,runtime_ref):
    """Fixed root bootstrap only; startup data alone never invokes this port."""
    _require(os.name=='posix' and os.geteuid()==0 and type(backend) is RestrictedExecutor,
             'PROTECTED_ROOT_SCIENCE_FACTORY_REQUIRED')
    from .state import SQLiteRunStore
    from .store_custody import CustodyStore
    _require(type(store) in (SQLiteRunStore,CustodyStore),'SCIENCE_CUSTODY_INSTANCE_REQUIRED')
    validate('Ref',runtime_ref)
    _require(store.record_kind(runtime_ref)=='science-runtime','ORIGINAL_SCIENCE_RUNTIME_REQUIRED')
    definition=decode_science_runtime_record(store.read_record(runtime_ref))
    from .native_ports import verify_installed_build
    _require(definition.record['build_id']==verify_installed_build(),'SCIENCE_BUILD_QUALIFICATION_MISMATCH')
    registration=InstalledScienceRuntime(store=store,backend=backend,runtime_ref=runtime_ref,definition=definition,seal=_SEAL)
    backend.science_registration=registration
    return registration
