"""Offline IF016 original-byte reader. This object grants no execution authority.

Only the authenticated producer's finite export and typed request-local journal
are consumed. Source records remain source provenance; private projections are
never registered as product records. A valid archive alone proves no live model,
scientific resource, containment or resource-release outcome.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from jiuwenswarm.research_records.contracts import ContractData
from .evidence import canonical, relative, write_once, read_verified, _evidence_directory
from .frozen_records import ref_key, strict_json


PRIVATE = {
    'request':'evaluation-request', 'runtime':'evaluation-runtime',
    'scope':'evaluation-scope', 'terminal':'evaluation-terminal',
    'assignment_grant':'evaluation-assignment-grant',
    'model_claim':'evaluation-call-claim', 'tool_claim':'evaluation-tool-claim',
    'check_plan':'evaluation-checking-basis',
}
SOURCE_SHAPES = {
    'library-snapshot':'library-snapshot', 'evaluation-profile':'evaluation-profile',
    'source_contract':'subnode-execution-contract', 'source_node':'node-execution-contract',
    'source_check_plan':'bound-check-plan', 'source_observation':'invocation-observation',
    'source_host_record':'invocation-observation', 'observation':'invocation-observation',
    'deterministic_result':'deterministic-check-result', 'verifier_check':'deterministic-check-result',
    'assessment':'verifier-assessment', 'review_context':'review-context',
    'model_call':'model-call', 'route':'route-record',
    'source_declaration':'capsule-declaration', 'source_admission':'library-admission',
    'source_check_profile':'checking-profile', 'source_check_bundle':'check-bundle',
}
CONTROL = {'request','scope','terminal','event','assignment_grant'}
PROVENANCE = {'source_check_plan','source_node','source_template','source_observation','source_host_record',
    'source_declaration','source_admission','source_check_profile','source_check_bundle',
    'source_instructions','source_body','source_runner','source_input','library-snapshot','evaluation-profile'}
MODEL_PROVENANCE = {'source_model_selection','source_model_deployment','source_model_endpoint'}
START_SCHEMAS = {'execution_preparation':'urn:ai4r:private:invocation-preparation:1',
    'execution_preflight':'urn:ai4r:private:scientific-attempt-preflight:1',
    'execution_activation':'urn:ai4r:private:scientific-attempt-activation:1'}


def require(condition, reason):
    if not condition:raise ValueError(reason)


def safe_path(value):
    require(isinstance(value,str) and str(relative(value))==value and value not in {'.',''}, 'noncanonical evaluation member path')
    return value


def zip_projection(raw):
    """Recompute the pinned textual projection from original bytes only."""
    blocks=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries=archive.infolist()
        require(len(entries)<=4096 and len({e.filename for e in entries})==len(entries)
            and sum(e.file_size for e in entries)<=128*1024*1024,'original ZIP projection exceeds bounded policy')
        for entry in sorted(entries,key=lambda e:e.filename.encode('utf-8')):
            require(not entry.is_dir() and not entry.flag_bits&1 and not stat.S_ISLNK(entry.external_attr>>16)
                and entry.file_size<=256*1024,'unsupported original ZIP projection member')
            data=archive.read(entry);text=data.decode('utf-8')
            blocks.append(f'path: {entry.filename}\nsha256: {hashlib.sha256(data).hexdigest()}\nsize: {len(data)}\n---\n{text}\n===\n')
    return ''.join(blocks).encode('utf-8')


class EvaluationRecords:
    """An immutable original snapshot, independently joined before scoring."""

    @classmethod
    def from_frozen(cls,destination,*,request_id,campaign_id,audience='researcher',expected_request=None,inventory=None):
        root=Path(destination)
        require(not any(p.is_symlink() for p in (root,*root.parents)),'symlink frozen evaluation directory')
        if inventory is None:raise ValueError('frozen evaluation export requires the retained run inventory')
        rows={};inventory_paths=set()
        for row in inventory:
            path=row['path']
            require(path not in inventory_paths,'duplicate retained export inventory path')
            inventory_paths.add(path)
            if path.startswith('evaluation-export/'):rows[path]=row
        archive_row=rows.get('evaluation-export/archive.zip')
        require(archive_row is not None,'original evaluation ZIP is not pinned by the retained run')
        raw=read_verified(root.parent,archive_row,max_bytes=128*1024*1024)
        value=cls.from_archive(raw,request_id=request_id,campaign_id=campaign_id,audience=audience,expected_request=expected_request)
        for name,payload in value.entries.items():
            path='evaluation-export/'+name;row=rows.get(path)
            require(row is not None and row['sha256']==hashlib.sha256(payload).hexdigest(),'frozen original member differs from retained run pins')
            require(read_verified(root.parent,row,max_bytes=128*1024*1024)==payload,'frozen member differs from original archive')
        require(set(rows)=={'evaluation-export/'+name for name in value.entries}|{'evaluation-export/archive.zip'},'unbound frozen evaluation inventory entry')
        pending=[root];members=set();count=0
        while pending:
            with os.scandir(pending.pop()) as children:
                for child in children:
                    count+=1;require(count<=32768 and not child.is_symlink(),'unsafe/oversized frozen evaluation tree')
                    path=Path(child.path)
                    if child.is_dir(follow_symlinks=False):pending.append(path)
                    else:
                        require(child.is_file(follow_symlinks=False),'nonregular frozen evaluation member')
                        members.add(path.relative_to(root).as_posix())
        require(members=={*value.entries,'archive.zip'},'unbound frozen evaluation file')
        return value

    @classmethod
    def from_archive(cls, raw, *, request_id, campaign_id, audience, expected_request=None,
                     max_bytes=128*1024*1024, max_files=4096):
        require(isinstance(raw,bytes) and len(raw)<=max_bytes, 'evaluation archive transfer bound')
        require(audience in {'researcher','reviewer'}, 'unsupported evaluation audience')
        value=cls();value.contracts=ContractData();value.validate=value.contracts.validate
        value.raw=raw;value.entries={};value.by_ref={};value.by_kind={}
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries=archive.infolist();names=[safe_path(e.filename) for e in entries]
                require(0<len(entries)<=max_files+1 and len(set(n.casefold() for n in names))==len(names)
                    and names.count('evaluation_export.json')==1, 'duplicate or missing evaluation manifest')
                require(sum(e.file_size for e in entries)<=max_bytes, 'evaluation expanded archive bound')
                for entry in entries:
                    mode=stat.S_IFMT(entry.external_attr>>16)
                    require(not entry.is_dir() and mode in {0,stat.S_IFREG} and not entry.flag_bits&1
                        and entry.compress_type in {zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED},
                        'nonregular or encrypted evaluation member')
                    payload=archive.read(entry)
                    require(len(payload)==entry.file_size, 'evaluation member length mismatch')
                    value.entries[entry.filename]=payload
            value.manifest=strict_json(value.entries['evaluation_export.json'])
            value.validate('urn:ai4r:private:evaluation-export:1',value.manifest)
            manifest=value.manifest
            require(manifest['audience']==audience, 'evaluation audience mismatch')
            unsigned={k:v for k,v in manifest.items() if k!='id'}
            require(manifest['id']=='evaluation-export:'+hashlib.sha256(canonical(unsigned)).hexdigest(),
                'evaluation manifest identity differs from original content')
            expected={};identities=set()
            for row in manifest['files']:
                path=safe_path(row['path']);key=ref_key(row['artifact_ref']);identity=(row['kind'],key)
                require(path!='evaluation_export.json' and path not in expected and identity not in identities,
                    'duplicate evaluation member or typed Ref')
                require(row['audience']==audience, 'foreign evaluation file audience')
                payload=value.entries.get(path)
                require(payload is not None and len(payload)==row['byte_length']
                    and hashlib.sha256(payload).hexdigest()==key[1], 'missing or swapped evaluation original bytes')
                if key in value.by_ref:require(value.by_ref[key]==payload,'conflicting evaluation Ref bytes')
                value.by_ref[key]=payload
                value.by_kind[identity]=row
                expected[path]=row;identities.add(identity)
            require(set(value.entries)=={'evaluation_export.json',*expected}, 'unexpected evaluation member')
            seen=set();present=set()
            for row in manifest['required_evidence']:
                require(row['evidence_id'] not in seen, 'duplicate required-evidence identity');seen.add(row['evidence_id'])
                if row['status']=='present':
                    file=expected.get(row['path'])
                    require(file is not None and (file['kind'],file['artifact_ref'])==(row['kind'],row['artifact_ref']),
                        'required evidence names another original file')
                    present.add(row['path'])
            require(present==set(expected), 'unpromised evaluation file')
            value._verify(request_id,campaign_id,expected_request)
            return value
        except (zipfile.BadZipFile,KeyError,TypeError,UnicodeError,IndexError,RecursionError,RuntimeError,NotImplementedError) as error:
            raise ValueError('invalid evaluation original-byte archive') from error

    def bytes_ref(self,ref):
        require(ref_key(ref) in self.by_ref, 'required evaluation original Ref is absent')
        return self.by_ref[ref_key(ref)]

    def json_ref(self,ref,kind=None):
        if kind is not None:require((kind,ref_key(ref)) in self.by_kind,'evaluation typed Ref mismatch')
        return strict_json(self.bytes_ref(ref))

    def rows(self,kind):
        return [row for (k,_),row in self.by_kind.items() if k==kind]

    def private(self,ref,kind):
        value=self.json_ref(ref,kind)
        self.validate('urn:ai4r:private:'+PRIVATE[kind]+':1',value)
        return value

    def source_record(self,ref,kind):
        value=self.json_ref(ref,kind)
        if kind in SOURCE_SHAPES:self.validate(SOURCE_SHAPES[kind],value)
        return value

    def model_call_rows(self):
        from datetime import datetime
        result=[]
        for row in self.rows('model_call'):
            call=self.json_ref(row['artifact_ref'],'model_call');duration=None
            if call['started_at'] and call['ended_at']:
                duration=(datetime.fromisoformat(call['ended_at'].replace('Z','+00:00'))
                    -datetime.fromisoformat(call['started_at'].replace('Z','+00:00'))).total_seconds()
                require(duration>=0,'model-call clock order differs')
            result.append({'call_ref':row['artifact_ref'],'role':call['call_function'] if call['call_function'] in {'worker','verifier','planner'} else 'other',
                'requested_model':call['identity']['requested'],'effective_model':call['identity']['effective'],
                'identity_basis':call['identity']['basis'],'duration_s':duration,'outcome':call['outcome'],
                'input_tokens':call['usage']['input_tokens'],'output_tokens':call['usage']['output_tokens'],'cost':call['usage']['cost_amount']})
        return result

    def output_artifact(self,parameters):
        allowed={ref_key(pin) for _,measured in self.measurements for pin in measured['output_refs'].values()}
        allowed.update(map(ref_key,self.source_outputs.values()))
        if 'artifact_ref' in parameters:
            require(ref_key(parameters['artifact_ref']) in allowed,'oracle targets an unmeasured private output')
            return strict_json(self.json_or_bytes_output(parameters['artifact_ref']))
        matches=[]
        for row in self.rows('output'):
            if ref_key(row['artifact_ref']) not in allowed:continue
            try:value=self.json_ref(row['artifact_ref'],'output')
            except (ValueError,UnicodeError):continue
            if isinstance(value,dict) and value.get('id')==parameters['artifact_id']:matches.append(value)
        require(len(matches)==1,'exact private output is absent or ambiguous');return matches[0]

    def require_complete(self):
        require(self.terminal is not None and self.terminal['state'] not in {'started','outcome_unknown'}
            and not any(r['status']=='unavailable' for r in self.manifest['required_evidence']),
            'original evaluation export is explicitly incomplete')
        return self

    def response(self):
        self.require_complete()
        require(self.terminal['result_ref'] is not None,'evaluation terminal has no original response')
        return self.json_ref(self.terminal['result_ref'],'result')['result']

    def replay_observation(self,*,node_id,output_port):
        require(self.request['entry_point']=='E2' and self.source['node_id']==node_id
            and self.scope['selected_output_port']==output_port,'oracle targets another original E2 source/port')
        response=self.response()
        return {'tier1':response['tier1_verdict'],'tier2':response['tier2_verdict'],
            'advanced':response['advanced'],'verifier_calls':sum(c['role']=='verifier' for c in self.model_call_rows())}

    def _source_closure(self):
        """Follow only explicit selected source/template edges, never arbitrary Refs."""
        self.source=None;self.source_outputs={};allowed=set()
        if self.scope is None:
            require(not any(self.rows(kind) for kind in PROVENANCE),'unprepared request invents source provenance')
            return
        scope=self.scope;request_ref=self.manifest['request_ref']
        def original(ref,kind):
            ref_key(ref);allowed.add((kind,ref_key(ref)))
            return self.source_record(ref,kind)
        source=self.source=original(scope['source_contract_ref'],'source_contract')
        eligibility_kinds={kind for kind in ('evaluation-profile','library-snapshot') if self.rows(kind)}
        require(not eligibility_kinds or len(eligibility_kinds)==2,'partial original frozen eligibility closure')
        if eligibility_kinds:
            profile=original(self.runtime['profile_ref'],'evaluation-profile')
            snapshot=self.library_snapshot=original(self.runtime['library_snapshot_ref'],'library-snapshot')
            declaration_ref=source['bindings'][0]['declaration_ref']
            declaration=original(declaration_ref,'source_declaration')
            pin={'cc_name':declaration['identity']['name'],'cc_version':declaration['identity']['version_label'],
                'declaration_sha256':declaration_ref['sha256']}
            require(self.runtime['library_snapshot_ref']['sha256']==profile['library_snapshot_sha256']
                and profile['profile_id']==self.json_ref(self.request['normalized_request_ref'],'normalized_request')['evaluation_profile_id']
                and self.request['entry_point'] in profile['allowed_entry_points']
                and profile['invalid_for_product'] is True
                and sum(all(entry.get(k)==v for k,v in pin.items()) for entry in snapshot['entries'])==1,
                'original frozen snapshot/profile subject differs')
        parent=self.source_parent=original(source['node_contract_ref'],'source_node')
        plan=self.source_plan=original(scope['source_check_plan_ref'],'source_check_plan')
        # The enclosing source template is captured provenance; only the
        # actual assignment templates below require the strict JSON shape.
        parent_template_key=('source_template',ref_key(parent['template_ref']))
        allowed.add(parent_template_key)
        require(parent_template_key in self.by_kind,'original enclosing template bytes are absent')
        self.bytes_ref(parent['template_ref'])
        node=self.json_ref(scope['actual_node_ref'],'actual_contract')
        self.validate('urn:ai4r:private:evaluation-node-context:1',node)
        require(node['request_ref']==request_ref and node['run_id']==scope['private_run_id']
            and node['source_contract_ref']==scope['source_contract_ref']
            and node['source_node_ref']==source['node_contract_ref']
            and node['source_template_ref']==parent['template_ref']
            and node['source_check_plan_ref']==scope['source_check_plan_ref']
            and node['source_binding_ref']==scope['source_binding_ref']
            and node['attempt_id']==parent['node_id']+'-a1' and node['revision']==1
            and all(node[k]==parent[k] for k in ('node_id','objective','requirement_ids','inputs','outputs','input_refs',
                'required_outputs','evidence_obligations','authority_ceiling','subnodes','checking_profile_ref','policy_ref','configuration_ref')),
            'private node differs from its exact original source projection')
        require(plan['contract_ref']==scope['source_contract_ref'] and plan['node_contract_ref']==source['node_contract_ref']
            and source['configuration_ref']==parent['configuration_ref']==self.runtime['configuration_ref']
            and source['policy_ref']==parent['policy_ref']==plan['policy_ref']==self.runtime['policy_ref']
            and plan['profile_ref']==source['checking_profile_ref'], 'original policy/configuration/checking joins differ')
        require(all(node['node_limits'][k]==min(parent['node_limits'][k],self.request['limits'][k])
            and scope['limits'][k]==self.request['limits'][k] for k in self.request['limits']),
            'private source projection changes the original limits')
        require(len(source['bindings'])==1 and source['bindings'][0]['role']=='work', 'one original work binding required')
        template_refs=[source['template_ref']]
        template_refs += [self.json_ref(row['artifact_ref'],'assignment_grant')['contract_ref'] for row in self.rows('assignment_grant')]
        template_refs=[source['template_ref'],*[self.json_ref(ref,'actual_contract')['source_template_ref'] for ref in template_refs[1:]]]
        templates={}
        for ref in template_refs:
            if ref_key(ref) in templates:continue
            template=original(ref,'source_template');templates[ref_key(ref)]=template
            require(isinstance(template,dict) and {'capsule_ref','admission_ref','body_refs','ports','check_bundle_ref','checking_profile_ref','role','subnode_id','cc'}<=set(template),
                'original assignment template is unavailable')
            declaration=original(template['capsule_ref'],'source_declaration')
            admission=original(template['admission_ref'],'source_admission')
            profile=original(template['checking_profile_ref'],'source_check_profile')
            bundle=original(template['check_bundle_ref'],'source_check_bundle')
            require(admission['candidate_ref']==template['capsule_ref'] and admission['status']=='admitted'
                and template['ports']==declaration['ports']
                and template['cc']=={'cc_name':declaration['identity']['name'],'cc_version':declaration['identity']['version_label'],
                    'declaration_sha256':template['capsule_ref']['sha256']}, 'original template/declaration/admission pins differ')
            instruction=profile['instruction_ref'];allowed.add(('source_instructions',ref_key(instruction)))
            self.bytes_ref(instruction)
            require(('source_instructions',ref_key(instruction)) in self.by_kind, 'original check instructions absent')
            paths=[body['path'] for body in declaration['identity']['body']]
            paths += [pin['ref'] for dependency in declaration['needs']['external'] for field in ('pin','lockfile') if (pin:=dependency.get(field))]
            for path in paths:
                pin=template['body_refs'][path];allowed.add(('source_body',ref_key(pin)))
                require(('source_body',ref_key(pin)) in self.by_kind,'original selected body/dependency bytes absent')
                self.bytes_ref(pin)
            require(all(template['body_refs'][body['path']]['sha256']==body['sha256']
                for body in declaration['identity']['body']), 'original Capsule body differs from its declaration hash')
            for check in bundle['checks']:
                pin=check['runner_ref'];allowed.add(('source_runner',ref_key(pin)))
                require(('source_runner',ref_key(pin)) in self.by_kind,'original pinned check runner absent')
                self.bytes_ref(pin)
        self.templates=templates
        template=templates[ref_key(source['template_ref'])];binding=source['bindings'][0]
        declaration=self.source_record(binding['declaration_ref'],'source_declaration')
        require(template['capsule_ref']==binding['declaration_ref'] and template['admission_ref']==binding['admission_ref']
            and template['role']=='work' and template['subnode_id']==source['subnode_id']
            and binding['implementation_refs']==[template['body_refs'][body['path']] for body in declaration['identity']['body']]
            and binding['dependency_refs']==[template['body_refs'][pin['ref']] for dependency in declaration['needs']['external']
                for field in ('pin','lockfile') if (pin:=dependency.get(field))], 'original source implementation/dependency/template closure differs')
        self.declaration=declaration
        admitted=self.source_record(binding['admission_ref'],'source_admission');per=declaration['budget']['per_call']
        ceilings={'time_s':per['wall_s'],'model_calls':per['invocations'] if any(i['service_key']=='audited_model_bridge'
            for i in declaration['needs']['injects']) else 0,'memory_mb':admitted['memory_mb']}
        require(all(source['subnode_limits'][k]<=min(parent['node_limits'][k],ceilings[k])
            and binding['limits'][k]<=min(parent['node_limits'][k],ceilings[k]) and self.request['limits'][k]<=parent['node_limits'][k]
            for k in ceilings),'original source/request widens immutable declaration/parent ceilings')
        authority=binding['effective_authority'];ceiling=parent['authority_ceiling'];network=declaration['needs']['network']
        require(all(value in ceiling[k] for k in ('network_allowlist','resource_reads','write_roots','tools') for value in authority[k])
            and (authority['network']=='none' or ceiling['network']=='allowlist' and network['mode']=='allowlist'
                and all(value in network['allowlist'] for value in authority['network_allowlist'])),
            'original source authority widens immutable parent/declaration')
        for direction in ('inputs','outputs'):
            expected={p['name']:p for p in declaration['ports'][direction]}
            require(len(source[direction])==len(expected) and {p['name'] for p in source[direction]}==set(expected)
                and all(p['required']==expected[p['name']]['required']
                    and self.contracts.schemas.get(p['contract_id'],{'$ref':p['contract_id']})
                    ==self.contracts.schemas.get(expected[p['name']]['schema_ref'],{'$ref':expected[p['name']]['schema_ref']})
                    for p in source[direction]), 'original source port/declaration contracts differ')
        require(source['input_refs']==[ref for port in source['inputs'] for ref in port['artifact_refs']], 'original source input flattening differs')
        for pin in source['input_refs']:
            allowed.add(('source_input',ref_key(pin)))
            require(('source_input',ref_key(pin)) in self.by_kind,'original input bytes absent');self.bytes_ref(pin)
        profile=self.profile=self.source_record(plan['profile_ref'],'source_check_profile')
        bundle=self.source_record(template['check_bundle_ref'],'source_check_bundle')
        mandatory=plan['mandatory_deterministic'];semantic=plan['mandatory_semantic']
        require(template['checking_profile_ref']==plan['profile_ref'] and len(mandatory)==len(set(mandatory))
            and {c['check_id'] for c in bundle['checks'] if c['blocking']}|{'host_contract','host_identity','host_limits','host_authority'}<=set(mandatory)
            and template['check_bundle_ref'] in plan['runner_refs']
            and len(semantic)==len(set(semantic)) and set(semantic)=={c['criterion_id'] for c in profile['criteria'] if c['blocking']},
            'original mandatory check/semantic coverage differs')
        bound=self.json_ref(scope['source_binding_ref'],'source_binding')
        normal=self.json_ref(self.request['normalized_request_ref'],'normalized_request')
        if self.request['entry_point']=='E2':
            fields={'id','contract_ref','check_plan_ref','output_refs','original_observation_ref','verifier_cc_id','host_records'}
            outputs=bound.get('output_refs')
            require(isinstance(outputs,dict) and 0<len(outputs)<=64 and all(isinstance(p,str) and p for p in outputs),'invalid original E2 output inventory')
            if bound.get('schema')=='ai4r-node-replay-binding:2':
                require(set(bound)==fields|{'schema','selected_output_port'} and bound['selected_output_port'] in outputs,'invalid original selected-port replay binding')
                selected=bound['selected_output_port']
            else:
                require(set(bound)==fields and len(outputs)==1,'invalid original historical replay binding');selected=next(iter(outputs))
            observed=original(scope['source_observation_ref'],'source_observation')
            require(bound['contract_ref']==scope['source_contract_ref'] and bound['check_plan_ref']==scope['source_check_plan_ref']
                and bound['original_observation_ref']==scope['source_observation_ref'] and observed['contract_ref']==scope['source_contract_ref']
                and observed['output_refs']==scope['source_output_refs'] and selected==scope['selected_output_port']
                and set(outputs)<={p['name'] for p in source['outputs']}, 'original E2 source/observation/selected-port joins differ')
            remaining=list(outputs.items());ordered={}
            for pin in observed['output_refs']:
                found=next(((i,name) for i,(name,value) in enumerate(remaining) if value==pin),None)
                require(found is not None,'original E2 ordered output missing');index,name=found;ordered[name]=remaining.pop(index)[1]
                require(('output',ref_key(pin)) in self.by_kind,'original E2 complete output bytes absent')
            require(not remaining,'original E2 extra output inventory');self.source_outputs=ordered
            require(normal['node_id']==source['node_id'] and normal['verifier_cc_id']==bound['verifier_cc_id']
                and normal['declaration']['sha256']==binding['declaration_ref']['sha256']
                and normal['output']['sha256']==outputs[selected]['sha256'], 'scheduled E2 request differs from original selected subject')
            require(len(normal['host_records'])==len(bound['host_records']),'original E2 host inventory differs')
            for offered,item in zip(normal['host_records'],bound['host_records']):
                require(set(item)=={'record_type','ref'} and item['record_type'] in {'runtime_observation','identity_record','budget_record','tool_observation'}
                    and offered['record_type']==item['record_type']
                    and offered['sha256']==item['ref']['sha256'],'original E2 host pin differs')
                host=original(item['ref'],'source_host_record');require(host['contract_ref']==scope['source_contract_ref'],'foreign original host record')
        else:
            require(scope['source_binding_ref']==scope['source_contract_ref'] and bound==source
                and scope['source_observation_ref'] is None and not scope['source_output_refs'] and scope['selected_output_port'] is None,
                'single-CC request invents an original replay producer')
            require((normal['capsule_id'],normal['capsule_version'],normal['capsule_declaration_sha256'])
                ==(declaration['identity']['name'],declaration['identity']['version_label'],binding['declaration_ref']['sha256'])
                and [(p['port'],p['sha256']) for p in normal['inputs']]
                ==[(p['name'],ref['sha256']) for p in source['inputs'] for ref in p['artifact_refs']],
                'single-CC request differs from original declaration/inputs')
        actual={(kind,key) for kind,key in self.by_kind if kind in PROVENANCE}
        require(actual=={entry for entry in allowed if entry[0] in PROVENANCE}, 'unbound or missing finite original source provenance')

    def _verify(self,request_id,campaign_id,expected_request):
        manifest=self.manifest;request_ref=manifest['request_ref'];scope_ref=manifest['scope_ref']
        request=self.request=self.private(request_ref,'request')
        runtime=self.runtime=self.private(request['runtime_ref'],'runtime')
        require(request['request_id']==request_id and runtime['campaign_id']==campaign_id,
            'evaluation request/campaign belongs to another schedule')
        slots=[row for row in runtime['slots'] if row['slot_id']==request['slot_id']]
        require(len(slots)==1 and all(slots[0][key]==request[key] for key in ('request_id','entry_point','case_id','limits'))
            and slots[0]['request_sha256']==request['fingerprint'], 'evaluation request differs from its frozen slot')
        original=self.json_ref(request['original_request_ref'],'original_request')
        normalized=self.json_ref(request['normalized_request_ref'],'normalized_request')
        expected=copy.deepcopy(original)
        if request['entry_point']=='E2':expected.setdefault('host_records',[])
        require(expected==normalized and hashlib.sha256(canonical([request['entry_point'],normalized])).hexdigest()==request['fingerprint'],
            'evaluation original and normalized request differ')
        require(manifest['original_request_ref']==request['original_request_ref']
            and manifest['normalized_request_ref']==request['normalized_request_ref']
            and normalized['request_id']==request_id and normalized['campaign_id']==campaign_id
            and normalized['case_id']==request['case_id'], 'evaluation original request closure differs')
        if expected_request is not None:
            supplied=copy.deepcopy(expected_request)
            if request['entry_point']=='E2':supplied.setdefault('host_records',[])
            require(supplied==normalized,'evaluation export differs from the scheduled source request')
        self.scope=self.private(scope_ref,'scope') if scope_ref else None
        if self.scope:
            require(self.scope['request_ref']==request_ref and all(self.scope[k]==request[k]
                for k in ('started_unix_ns','deadline_unix_ns')), 'evaluation scope changed original epoch')
            require(self.scope['source_binding_ref']==manifest['source_binding_ref'],'evaluation source binding differs')
        events=[];cursor=manifest['through_event_ref'];visited=set()
        while cursor is not None:
            key=ref_key(cursor)
            require(key not in visited and len(events)<16384,'cyclic or oversized evaluation journal');visited.add(key)
            event=self.json_ref(cursor,'event')
            version=event.get('schema')
            require(version in {'ai4r-evaluation-event:1','ai4r-evaluation-event:2'},'unknown evaluation event identity')
            self.validate('urn:ai4r:private:evaluation-event:'+version[-1],event)
            require(event['request_ref']==request_ref and event['scope_ref'] in (None,scope_ref), 'foreign evaluation journal scope')
            events.append((cursor,event));cursor=event['previous_event_ref']
        events.reverse();self.events=events
        require(events and events[0][1]['kind']=='claimed' and len(events)==len(self.rows('event')),
            'incomplete or unbound evaluation journal')
        for index,(_,event) in enumerate(events):require(event['sequence']==index,'noncontiguous evaluation journal')
        require(len(self.rows('request'))==1 and self.rows('request')[0]['artifact_ref']==request_ref
            and ([row['artifact_ref'] for row in self.rows('scope')]==[scope_ref] if scope_ref else not self.rows('scope')),
            'unbound private control rows')
        grant_refs={ref_key(event['assignment_grant_ref']) for _,event in events if event['assignment_grant_ref'] is not None}
        require(grant_refs=={ref_key(row['artifact_ref']) for row in self.rows('assignment_grant')}, 'unbound private assignment grants')
        self._source_closure()
        self._model_selection_closure()
        self._grants(request_ref,scope_ref)
        captured={(e['capture_kind'],ref_key(e['capture_ref'])) for _,e in events if e['kind']=='captured'}
        capture_names=set()
        for _,event in events:
            grant_ref=event['assignment_grant_ref']
            grant=self.private(grant_ref,'assignment_grant') if grant_ref else None
            if grant:require(grant['request_ref']==request_ref and grant['scope_ref']==scope_ref,'foreign journal assignment')
            if event['kind']!='captured':continue
            kind=event['capture_kind'];ref=event['capture_ref'];capture_names.add(kind)
            require((kind,ref_key(ref)) in self.by_kind,'captured evaluation bytes are absent or have another kind')
            self._capture(kind,ref,grant_ref,grant,request_ref)
        require(all((kind,ref_key(ref)) in captured for kind,ref in (
            ('original_request',request['original_request_ref']),('normalized_request',request['normalized_request_ref']),
            ('runtime',request['runtime_ref']),('source_binding',manifest['source_binding_ref']))), 'missing original evaluation control captures')
        allowed=CONTROL|PROVENANCE|MODEL_PROVENANCE|capture_names|{'native_packet'}
        require(all(kind in allowed for kind,_ in self.by_kind),'unknown or canonical-kind evaluation member')
        self._native_closure()
        self._measurements()
        self._terminal(request_ref,scope_ref)
        self._response_closure()
        self._scientific_order()

    def _model_selection_closure(self):
        """Read only exact optional runtime-owned account selection edges."""
        self.account_model_deployment=None
        actual={(kind,key) for kind,key in self.by_kind if kind in MODEL_PROVENANCE}
        ref=self.runtime.get('account_model_selection_ref')
        if ref is None:
            require(not actual,'unbound original account model selection');return
        expected={('source_model_selection',ref_key(ref))}
        selection=self.json_ref(ref,'source_model_selection')
        common={'schema_version','id','run_id','account_id','mode','preset_id'}
        if selection.get('mode')=='codex':
            extra={'chatgpt_model','deployment_ref'} if selection.get('chatgpt_model') else set()
            require(selection.get('preset_id')=='codex','original subscription model choice differs')
        elif selection.get('platform_id')=='operator-local':
            extra={'local_binding_id','local_binding_sha256','platform_id','deployment_ref'}
            require(isinstance(selection.get('preset_id'),str) and selection['preset_id'].startswith('local-'),
                'original local model choice differs')
        else:extra={'credential_id','platform_id','deployment_ref'}
        require(set(selection)==common|extra and selection.get('schema_version')=='1.0.0'
            and selection.get('id')==ref['id'] and selection.get('account_id')==self.runtime['account_id']
            and selection.get('mode') in {'codex','api'}
            and (self.source is None or selection.get('run_id')==self.source['run_id']),
            'original account model choice belongs to another source/account')
        if selection.get('deployment_ref') is not None:
            pin=selection['deployment_ref'];expected.add(('source_model_deployment',ref_key(pin)))
            deployment=self.json_ref(pin,'source_model_deployment')
            require(set(deployment)=={'model_id','provider_model_name','provider','endpoint_ref','adapter_id','revision'},
                'original account model deployment shape differs')
            self.account_model_deployment=deployment
            pin=deployment['endpoint_ref'];expected.add(('source_model_endpoint',ref_key(pin)))
            endpoint=self.json_ref(pin,'source_model_endpoint')
            require(isinstance(endpoint,dict),'original account model endpoint is not metadata')
            if selection.get('platform_id')=='operator-local':
                require(set(endpoint)=={'provider_id','transport','gateway_id','binding_sha256','backend','model'}
                    and endpoint['provider_id']=='operator-local' and endpoint['transport']=='authenticated-unix-rpc'
                    and endpoint['binding_sha256']==selection['local_binding_sha256']
                    and endpoint['model']['id']==selection['preset_id']
                    and deployment['provider_model_name']==endpoint['model']['model_name'],
                    'original local model deployment/endpoint binding differs')
            elif selection.get('chatgpt_model'):
                require(endpoint=={'provider_id':'chatgpt','transport':'packaged-app-server-subscription'}
                    and deployment['model_id']==deployment['provider_model_name']==selection['chatgpt_model'],
                    'original subscription model deployment/endpoint differs')
            else:
                require(set(endpoint)=={'provider_id','base_url','models','credential_env_var','timeout_s','enabled'}
                    and endpoint['provider_id']==selection['platform_id']
                    and deployment['provider']==selection['platform_id']
                    and endpoint['credential_env_var']=='AI4R_SELECTED_API_KEY',
                    'original API model deployment/endpoint differs')
        require(actual==expected,'unbound or missing finite original account model provenance')

    def _grants(self,request_ref,scope_ref):
        assignments=set()
        for row in self.rows('assignment_grant'):
            grant=self.private(row['artifact_ref'],'assignment_grant')
            require(grant['request_ref']==request_ref and grant['scope_ref']==scope_ref and self.scope is not None,
                'foreign evaluation assignment')
            child=self.json_ref(grant['contract_ref'],'actual_contract')
            self.validate('urn:ai4r:private:evaluation-subnode-context:1',child)
            basis=self.private(grant['check_plan_ref'],'check_plan')
            key=(grant['role'],grant['output_port']);require(key not in assignments,'duplicate private role/port grant');assignments.add(key)
            require(child['request_ref']==request_ref and child['node_contract_ref']==self.scope['actual_node_ref']
                and child['source_subject_ref']==self.scope['source_contract_ref']
                and child['role']==grant['role'] and child['output_port']==grant['output_port']
                and basis['request_ref']==request_ref and basis['assignment_context_ref']==grant['contract_ref']
                and basis['node_context_ref']==self.scope['actual_node_ref'], 'private assignment projection closure differs')
            node=self.json_ref(self.scope['actual_node_ref'],'actual_contract')
            require(grant['source_contract_ref']==self.scope['source_contract_ref']
                and child['run_id']==self.scope['private_run_id'] and child['attempt_id']==node['attempt_id']
                and child['revision']==1
                and all(child[k]==self.source[k] for k in ('node_id','objective','requirement_ids','evidence_obligations','policy_ref','configuration_ref'))
                and child['input_refs']==[ref for port in child['inputs'] for ref in port['artifact_refs']]
                and len(child['bindings'])==1 and child['bindings'][0]['limits']==grant['limits'],
                'private assignment changes source identity/inputs/limits')
            template=self.templates[ref_key(child['source_template_ref'])]
            binding=child['bindings'][0];declaration=self.source_record(template['capsule_ref'],'source_declaration')
            require(binding['declaration_ref']==template['capsule_ref'] and binding['admission_ref']==template['admission_ref']
                and binding['implementation_refs']==[template['body_refs'][body['path']] for body in declaration['identity']['body']]
                and binding['dependency_refs']==[template['body_refs'][pin['ref']] for dependency in declaration['needs']['external']
                    for field in ('pin','lockfile') if (pin:=dependency.get(field))], 'private assignment changed its exact template/body/dependency pins')
            require(all(grant['limits'][k]<=min(child['subnode_limits'][k],node['node_limits'][k],self.request['limits'][k])
                for k in grant['limits']), 'private assignment widens original ceilings')
            if grant['role']=='worker':
                expected_binding=copy.deepcopy(self.source['bindings'][0]);expected_binding['limits']={k:min(self.source['bindings'][0]['limits'][k],child['subnode_limits'][k]) for k in grant['limits']}
                require(self.request['entry_point']=='E3' and grant['output_port'] is None
                    and child['source_template_ref']==self.source['template_ref'] and binding['role']=='work'
                    and all(child[k]==self.source[k] for k in ('subnode_id','inputs','outputs','input_refs','required_outputs','checking_profile_ref'))
                    and all(child['subnode_limits'][k]==min(self.source['subnode_limits'][k],self.request['limits'][k]) for k in grant['limits'])
                    and binding==expected_binding,
                    'single-CC worker differs from original source projection')
            else:
                candidates=[p for p in self.source_parent['subnodes'] if p['role']=='verifier' and p['subnode_id']==child['subnode_id']]
                require(self.request['entry_point']=='E2' and grant['output_port']==self.scope['selected_output_port']
                    and len(candidates)==1 and candidates[0]['template_ref']==child['source_template_ref']
                    and candidates[0]['capsule_ref']==binding['declaration_ref'] and binding['role']=='verifier'
                    and template['subject_subnode_id']==self.source['subnode_id'] and template['output_port']==grant['output_port'],
                    'private reviewer is not the exact selected source assignment')
                expected=[('subject_declaration',self.source['bindings'][0]['declaration_ref']),
                    ('subject_output',self.source_outputs[grant['output_port']])]
                require([(p['name'],p['artifact_refs']) for p in child['inputs']]==[(name,[ref]) for name,ref in expected]
                    and binding['effective_authority']=={'network':'none','network_allowlist':[],
                        'resource_reads':[ref for _,ref in expected],'write_roots':[],'tools':[]}
                    and grant['limits']['model_calls']==1, 'private reviewer replays inputs or widens authority')
                per=declaration['budget']['per_call'];admitted=self.source_record(template['admission_ref'],'source_admission')
                ceilings={'time_s':min(per['wall_s'],self.profile['time_s']),'model_calls':1,'memory_mb':admitted['memory_mb']}
                require(self.profile['model_call_limit']==1 and child['subnode_limits']==binding['limits']
                    and all(grant['limits'][k]==min(ceilings[k],node['node_limits'][k],self.request['limits'][k]) for k in ceilings)
                    and child['checking_profile_ref']==template['checking_profile_ref']==self.source_plan['profile_ref']
                    and {p['name'] for p in child['outputs']}=={p['name'] for p in declaration['ports']['outputs']}
                    and child['required_outputs']==[p['name'] for p in child['outputs'] if p['required']],
                    'private reviewer changes original declaration/profile/ceiling projection')
            self._basis(basis,child=child)
            require(grant['deadline_unix_ns']<=self.request['deadline_unix_ns']
                and grant['started_unix_ns']>=self.request['started_unix_ns'], 'private assignment resets original deadline')

    def _basis(self,basis,*,child=None):
        source=self.source;plan=self.source_plan
        require(self.scope is not None and basis['request_ref']==self.manifest['request_ref']
            and basis['node_context_ref']==self.scope['actual_node_ref']
            and basis['source_contract_ref']==self.scope['source_contract_ref']
            and basis['source_check_plan_ref']==self.scope['source_check_plan_ref']
            and basis['profile_ref']==plan['profile_ref'] and basis['policy_ref']==plan['policy_ref'], 'foreign private checking basis')
        if child is None:
            require(self.request['entry_point']=='E2' and basis['assignment_context_ref'] is None
                and basis['mode']=='replay_subject' and basis['output_port']==self.scope['selected_output_port'],
                'unassigned checking basis is not original replay subject')
            expected_inputs=source['input_refs'];template_ref=source['template_ref'];mandatory=plan['mandatory_deterministic'];runners=plan['runner_refs']
            semantic=[c['criterion_id'] for c in self.profile['criteria'] if c['blocking'] and c['target_port'] in (None,self.scope['selected_output_port'])]
        else:
            expected_inputs=child['input_refs'];template_ref=child['source_template_ref'];semantic=[]
            if child['role']=='worker':
                require(basis['mode']=='worker_output' and basis['output_port'] is None,'wrong private worker checking mode')
                mandatory=plan['mandatory_deterministic'];runners=plan['runner_refs']
            else:
                require(basis['mode']=='verifier_output' and basis['output_port']==child['output_port'],'wrong private verifier checking mode')
                template=self.templates[ref_key(template_ref)];bundle=self.source_record(template['check_bundle_ref'],'source_check_bundle')
                mandatory=list(dict.fromkeys([*[c['check_id'] for c in bundle['checks'] if c['blocking']],
                    'host_contract','host_identity','host_limits','host_authority']))
                runners=list({pin['sha256']:pin for pin in [template['check_bundle_ref'],*[c['runner_ref'] for c in bundle['checks']]]}.values())
        require(basis['source_template_ref']==template_ref and basis['input_refs']==expected_inputs
            and basis['mandatory_deterministic']==mandatory and basis['mandatory_semantic']==semantic
            and basis['runner_refs']==runners, 'private checking basis changes original template/input/check coverage')

    def _capture(self,kind,ref,grant_ref,grant,request_ref):
        if kind in PRIVATE:
            value=self.private(ref,kind)
            if kind=='check_plan':
                self._basis(value,child=self.json_ref(grant['contract_ref'],'actual_contract') if grant else None)
                require(grant is None or ref==grant['check_plan_ref'] and value['assignment_context_ref']==grant['contract_ref'],
                    'private checking capture differs from its exact grant')
            if kind in {'model_claim','tool_claim'}:
                require(grant is not None and value['request_ref']==request_ref
                    and value['scope_ref']==grant['scope_ref']
                    and value['assignment_grant_ref']==grant_ref
                    and all(value[k]==grant[k] for k in ('execution_id','invocation_id','contract_ref')),
                    'private call/tool claim belongs to another assignment')
        elif kind=='actual_contract':
            value=self.json_ref(ref,kind);schema=value.get('schema')
            require(schema in {'ai4r-evaluation-node-context:1','ai4r-evaluation-subnode-context:1'},
                'canonical source masquerades as private evaluation context')
            self.validate('urn:ai4r:private:'+schema[5:],value)
            require(value['request_ref']==request_ref and self.scope is not None,'foreign private evaluation context')
            if schema=='ai4r-evaluation-node-context:1':
                require(ref==self.scope['actual_node_ref'] and grant_ref is None,'private parent is not the exact scope target')
            else:require(grant is not None and grant['contract_ref']==ref,'private child lacks its exact assignment')
        elif kind in SOURCE_SHAPES:
            value=self.json_ref(ref,kind);self.validate(SOURCE_SHAPES[kind],value)
            if grant and 'contract_ref' in value:
                expected=self.scope['source_contract_ref'] if kind=='review_context' else grant['contract_ref']
                require(value['contract_ref']==expected,'captured evidence belongs to another contract')
            if kind=='source_contract':require(ref==self.scope['source_contract_ref'],'captured original source differs from scope')
            if kind=='deterministic_result':
                basis=self.private(value['check_plan_ref'],'check_plan')
                self._basis(basis,child=self.json_ref(grant['contract_ref'],'actual_contract') if grant else None)
                require(grant is None or value['check_plan_ref']==grant['check_plan_ref'],'captured checks changed exact grant basis')
            if kind=='observation' and grant:
                child=self.json_ref(grant['contract_ref'],'actual_contract')
                require(all(value[k]==child[k] for k in ('run_id','node_id','subnode_id','attempt_id')),
                    'private observation differs from actual assignment')
                binding=child['bindings'][0];template=self.templates[ref_key(child['source_template_ref'])]
                require(all(value[k]==template['cc'][k] for k in ('cc_name','cc_version','declaration_sha256'))
                    and value['input_refs']==child['input_refs'] and value['binding_id']==binding['id']
                    and value['observed_runtime'] is True,'private observation changed immutable Capsule/input/binding identity')
        elif kind in START_SCHEMAS:
            value=self.json_ref(ref,kind);self.validate(START_SCHEMAS[kind],value)
        elif kind in {'result','failure','measurement','containment'}:
            value=self.json_ref(ref,kind)
            require(isinstance(value,dict) and value.get('accepted') is False
                and (kind=='measurement' or value.get('invalid_for_product') is True), 'evaluation evidence claims product authority')

    def _owned_capture(self,ref,kinds,grant_ref=None):
        kinds={kinds} if isinstance(kinds,str) else set(kinds)
        matches=[e for _,e in self.events if e['kind']=='captured' and e['capture_kind'] in kinds
            and e['capture_ref']==ref and (grant_ref is None or e['assignment_grant_ref']==grant_ref)]
        require(matches,'original evidence lacks its request-local typed capture')
        return matches

    def _native_closure(self):
        """Join only journal-owned packets; do not infer a live provider call."""
        natives={'prompt','route','model_start','model_call','model_refusal','tool_observation','trace'}
        allowed_packets=set();claims={};starts={}
        for _,event in self.events:
            if event['kind']!='captured' or event['capture_kind']!='model_claim':continue
            claim=self.private(event['capture_ref'],'model_claim');key=(ref_key(event['assignment_grant_ref']),claim['call_id'])
            require(key not in claims,'duplicate original model-call claim identity')
            grant=self.private(event['assignment_grant_ref'],'assignment_grant')
            if grant['role']=='verifier':
                port=self.scope['selected_output_port'];output=self.bytes_ref(self.source_outputs[port])
                contract=next(p['contract_id'] for p in self.source['outputs'] if p['name']==port)
                if self.contracts.schemas.get(contract)==self.contracts.schemas.get('poc-artifact-bundle'):output=zip_projection(output)
                criteria=[c for c in self.profile['criteria'] if c['target_port'] in (None,port)]
                instructions=self.bytes_ref(self.profile['instruction_ref']).decode('utf-8')+'\nCriteria for this output:\n'+json.dumps(criteria,ensure_ascii=False)
                payload=json.dumps({'subject_declaration':self.bytes_ref(self.source['bindings'][0]['declaration_ref']).decode('utf-8'),
                    'subject_output':output.decode('utf-8')},ensure_ascii=False)
                expected=hashlib.sha256((instructions+'\n\n<subject_payload>\n'+payload+'\n</subject_payload>').encode('utf-8')).hexdigest()
                require(claim['expected_prompt_sha256']==expected,'reviewer claim changed the exact original source/profile prompt')
            claims[key]=(event,claim)
        for row in self.rows('assignment_grant'):
            key=ref_key(row['artifact_ref']);grant=self.private(row['artifact_ref'],'assignment_grant')
            ordinals=[claim['call_ordinal'] for (owner,_),(_,claim) in claims.items() if owner==key]
            require(sorted(ordinals)==list(range(1,len(ordinals)+1)) and len(ordinals)<=grant['limits']['model_calls'],
                'original private model claim ordinal/ceiling differs')
        require(len(claims)<=self.request['limits']['model_calls'],'original request model-call ceiling exceeded')
        for _,event in self.events:
            kind=event['capture_kind']
            if event['kind']!='captured' or kind not in natives:continue
            grant_ref=event['assignment_grant_ref'];require(grant_ref is not None,'native evidence lacks its exact assignment')
            grant=self.private(grant_ref,'assignment_grant');child=self.json_ref(grant['contract_ref'],'actual_contract')
            value=self.json_ref(event['capture_ref'],kind)
            require(isinstance(value,dict),'native evidence is not a record')
            if kind=='route' and self.account_model_deployment is not None:
                require(value.get('model_id')==self.account_model_deployment['model_id'],
                    'original private route differs from the frozen account model choice')
            if kind=='trace':continue
            if kind=='prompt':require(set(value)=={'id','run_id','invocation_id','call_id','prompt'},'original prompt shape differs')
            if kind=='model_start':require(set(value)=={'id','run_id','invocation_id','execution_id','call_id','call_claim_ref','contract_ref',
                'route_id','route_ref','input_ref','started_at'},'original model start shape differs')
            if kind=='model_refusal':require(set(value)=={'id','run_id','node_id','subnode_id','attempt_id','invocation_id','execution_id','call_id',
                'call_claim_ref','contract_ref','route_ref','input_ref','route_decision_ref','reason_code','recorded_at'},'original model refusal shape differs')
            for field,expected in {**{k:child[k] for k in ('run_id','node_id','subnode_id','attempt_id')},
                **{k:grant[k] for k in ('execution_id','invocation_id','contract_ref')}}.items():
                if field in value:require(value[field]==expected,'native evidence belongs to another private assignment')
            if kind=='tool_observation':continue
            call_id=value.get('call_id',value.get('id') if kind=='model_call' else None)
            if call_id is None:
                # Prompts are addressed by the exact claim's expected byte hash.
                if kind=='prompt':
                    require(any(c['expected_prompt_sha256']==event['capture_ref']['sha256'] and key[0]==ref_key(grant_ref)
                        for key,(_,c) in claims.items()),'prompt bytes are not pinned by the exact private claim')
                    continue
                # Route records carry invocation identity; the corresponding
                # call/start names the exact immutable route Ref below.
                require(kind=='route','native packet has no exact call identity');continue
            pair=claims.get((ref_key(grant_ref),call_id));require(pair is not None,'native call has no original private claim')
            claim_event,claim=pair
            require(claim_event['sequence']<event['sequence'],'native evidence precedes its private claim')
            if 'call_claim_ref' in value:require(value['call_claim_ref']==claim_event['capture_ref'],'native call changed claim Ref')
            if kind=='prompt':
                require(isinstance(value.get('prompt'),str) and (claim['expected_prompt_sha256'] is None
                    or hashlib.sha256(value['prompt'].encode('utf-8')).hexdigest()==claim['expected_prompt_sha256']),
                    'native prompt changed the original claim hash')
            if kind in {'model_start','model_refusal'}:
                prompt=self.json_ref(value['input_ref'],'prompt')
                require(prompt.get('call_id')==claim['call_id'] and isinstance(prompt.get('prompt'),str)
                    and (claim['expected_prompt_sha256'] is None or hashlib.sha256(prompt['prompt'].encode('utf-8')).hexdigest()==claim['expected_prompt_sha256']),
                    'native start/refusal changed exact prompt')
                self._owned_capture(value['input_ref'],'prompt',grant_ref)
                if value.get('route_ref') is not None:self._owned_capture(value['route_ref'],'route',grant_ref)
            if kind=='model_start':
                key=(ref_key(grant_ref),call_id);require(key not in starts,'duplicate original model start')
                route=self.json_ref(value['route_ref'],'route')
                require(value['id']==call_id+':start' and value['route_id']==route['route_id'],'original model start changed route identity')
                starts[key]=(event,value)
            if kind=='model_call':
                key=(ref_key(grant_ref),call_id);require(key in starts and starts[key][0]['sequence']<event['sequence'],
                    'model outcome lacks its earlier exact captured start')
                require(value['id']==claim['call_id'] and value['observed_runtime'] is True,'model call claims another or synthetic runtime')
                route=self.json_ref(starts[key][1]['route_ref'],'route')
                require(value['started_at']==starts[key][1]['started_at'] and value['purpose']=='task_execution'
                    and value['call_function']==grant['role'] and value['model_selection_profile_ref']==self.runtime['model_selection_profile_ref']
                    and value['identity']['requested']==route['model_id'] and value['route_decision_ref']==route['route_decision_ref'],
                    'original call changed start/role/profile/route provenance')
                for pin in value['evidence_refs']:self.bytes_ref(pin)
        scope_fields={'run_id','node_id','subnode_id','attempt_id','execution_id','invocation_id','call_id','contract_ref','model_call_start_ref'}
        for row in self.rows('trace'):
            ref=row['artifact_ref'];value=self.json_ref(ref,'trace');events=self._owned_capture(ref,'trace')
            grant_ref=events[0]['assignment_grant_ref'];grant=self.private(grant_ref,'assignment_grant')
            child=self.json_ref(grant['contract_ref'],'actual_contract');scope=value.get('scope')
            require(isinstance(scope,dict) and set(scope)==scope_fields
                and all(scope[k]==child[k] for k in ('run_id','node_id','subnode_id','attempt_id'))
                and all(scope[k]==grant[k] for k in ('execution_id','invocation_id','contract_ref')),'native trace scope differs')
            start=self.json_ref(scope['model_call_start_ref'],'model_start');self._owned_capture(scope['model_call_start_ref'],'model_start',grant_ref)
            require(all(start[k]==scope[k] for k in ('run_id','execution_id','invocation_id','call_id','contract_ref')),'native trace changed original start')
            if value.get('schema')=='ai4r-native-governed-trace:1':
                require(set(value)=={'schema','scope','status','event_refs'} and value['status'] in {'completed','failed','interrupted'}
                    and isinstance(value['event_refs'],list) and len(value['event_refs'])<=16384
                    and len(set(map(ref_key,value['event_refs'])))==len(value['event_refs']),'invalid native trace summary')
                refs=value['event_refs']
            else:refs=[ref]
            for index,pin in enumerate(refs):
                self._owned_capture(pin,'trace',grant_ref);packet=self.json_ref(pin,'trace')
                require(set(packet)=={'schema','scope','sequence','direction','method','raw_ref'}
                    and packet['schema']=='ai4r-native-governed-trace-event:1' and packet['scope']==scope
                    and type(packet['sequence']) is int and packet['sequence']>=0
                    and (refs==[ref] or packet['sequence']==index) and packet['direction'] in {'in','out'}
                    and isinstance(packet['method'],str) and not packet['method'].startswith(('account/','login/','auth/')),'invalid/private native trace event')
                raw=self.json_ref(packet['raw_ref'],'native_packet');allowed_packets.add(ref_key(packet['raw_ref']))
                require(isinstance(raw,dict) and not str(raw.get('method','')).startswith(('account/','login/','auth/'))
                    and ('method' not in raw or raw['method']==packet['method']),'native raw packet method differs or is private')
        require(allowed_packets=={ref_key(r['artifact_ref']) for r in self.rows('native_packet')},'unbound original native packet')

    def _checked(self,ref,*,subjects,kind='deterministic_result'):
        value=self.json_ref(ref,kind);basis=self.private(value['check_plan_ref'],'check_plan')
        self._owned_capture(value['check_plan_ref'],'check_plan')
        require(value['subject_ref']==subjects[0] and value.get('subject_refs',[value['subject_ref']])==subjects,
            'private checks changed exact measured subject order')
        ids=[row['check_id'] for row in value['results']]
        require(len(ids)==len(set(ids)) and set(basis['mandatory_deterministic'])<=set(ids),'private check coverage is missing or duplicate')
        for result in value['results']:
            for evidence in result['evidence_refs']:self.bytes_ref(evidence)
        return value,basis

    def _measurements(self):
        self.measurements=[]
        fields={'id','contract_ref','accepted','status','output_refs','deterministic_ref','observation_ref',
            'assessment_refs','verifier_check_refs','observation_refs','trace_refs','failure','elapsed_s','recorded_at'}
        for row in self.rows('measurement'):
            measured=self.json_ref(row['artifact_ref'],'measurement');self.measurements.append((row['artifact_ref'],measured))
            publications=self._owned_capture(row['artifact_ref'],'measurement');require(len(publications)==1,'ambiguous original measurement publication')
            require(set(measured)==fields and measured['accepted'] is False and measured['status'] in {'completed','failed','blocked','interrupted'}
                and isinstance(measured['output_refs'],dict) and type(measured['elapsed_s']) in (int,float)
                and math.isfinite(measured['elapsed_s']) and measured['elapsed_s']>=0,'invalid original trial measurement')
            observation_kind='source_observation' if self.request['entry_point']=='E2' else 'observation'
            observed=self.json_ref(measured['observation_ref'],observation_kind)
            require(observed['contract_ref']==measured['contract_ref'],'measurement changed original observed contract')
            if self.request['entry_point']=='E2':
                require(measured['contract_ref']==self.scope['source_contract_ref'] and measured['observation_ref']==self.scope['source_observation_ref']
                    and publications[0]['assignment_grant_ref'] is None
                    and all(self.source_outputs.get(port)==pin for port,pin in measured['output_refs'].items()),'replay measurement changed original source/output')
            else:
                child=self.json_ref(measured['contract_ref'],'actual_contract')
                assigned=publications[0]['assignment_grant_ref'];require(assigned is not None,'worker measurement has no exact assignment')
                grant=self.private(assigned,'assignment_grant')
                require(grant['role']=='worker' and grant['contract_ref']==measured['contract_ref'],'measurement targets another worker grant')
                self._owned_capture(measured['observation_ref'],'observation',assigned)
                require(child['role']=='worker' and not measured['assessment_refs'] and not measured['verifier_check_refs']
                    and not measured['observation_refs'] and sorted(map(ref_key,observed['output_refs']))==sorted(map(ref_key,measured['output_refs'].values()))
                    and set(measured['output_refs'])<={p['name'] for p in child['outputs']},
                    'single-CC measurement invents verifier/Gate evidence or changes outputs')
            for pin in measured['output_refs'].values():self.json_or_bytes_output(pin)
            subjects=[pin for pin in observed['output_refs'] if pin in measured['output_refs'].values()] or [measured['observation_ref']]
            self._owned_capture(measured['deterministic_ref'],'deterministic_result')
            require(all(e['assignment_grant_ref']==publications[0]['assignment_grant_ref']
                for e in self._owned_capture(measured['deterministic_ref'],'deterministic_result')),
                'measurement checks belong to another original assignment')
            checked,basis=self._checked(measured['deterministic_ref'],subjects=subjects)
            require(basis['assignment_context_ref']==(measured['contract_ref'] if self.request['entry_point']=='E3' else None),
                'measurement checks belong to another private assignment')
            require(len(measured['assessment_refs'])==len(measured['verifier_check_refs'])<=1,'replay semantic evidence population differs')
            for assessment_ref,checked_ref in zip(measured['assessment_refs'],measured['verifier_check_refs']):
                assessment=self.json_ref(assessment_ref,'assessment');reviewer=self._owned_capture(assessment_ref,'assessment')[0]['assignment_grant_ref']
                require(reviewer is not None,'assessment has no exact original reviewer grant')
                reviewer_grant=self.private(reviewer,'assignment_grant');require(reviewer_grant['role']=='verifier','assessment came from a non-reviewer assignment')
                context=self.json_ref(assessment['review_context_ref'],'review_context');self._owned_capture(assessment['review_context_ref'],'review_context',reviewer)
                selected=self.source_outputs[self.scope['selected_output_port']]
                require(context['subject_ref']==selected and context['contract_ref']==self.scope['source_contract_ref']
                    and context['check_plan_ref']==checked['check_plan_ref'] and context['deterministic_result_ref']==measured['deterministic_ref']
                    and context['input_refs']==self.source['input_refs'] and context['observations']==[measured['observation_ref']],
                    'semantic review changed original selected subject/checks/inputs/observation')
                criteria=set(context['criteria'])
                profile_criteria=[c for c in self.profile['criteria'] if c['target_port'] in (None,self.scope['selected_output_port'])]
                findings=[f['criterion_id'] for f in assessment['findings']]
                require(criteria==set(basis['mandatory_semantic']) and len(findings)==len(set(findings))
                    and set(findings)=={c['criterion_id'] for c in profile_criteria},
                    'semantic assessment changed required criterion coverage')
                # The original selected output can be a ZIP projection in the
                # prompt. Such a projection must itself be captured output.
                if assessment['subject_ref']!=selected:
                    projected=self.json_or_bytes_output(assessment['subject_ref'])
                    require(projected==zip_projection(self.bytes_ref(selected)),'semantic assessment targets different projected bytes')
                require(all(f['evidence_refs']==[self.source['bindings'][0]['declaration_ref'],assessment['subject_ref']]
                    for f in assessment['findings']),'semantic findings changed exact declaration/subject evidence')
                failed=[f['outcome'] for f in assessment['findings'] if f['criterion_id'] in criteria and f['outcome']!='PASS']
                verdict=(next(kind for kind in ('FAIL','ENVIRONMENT_BLOCKED','INCONCLUSIVE') if kind in failed) if failed
                    else 'PASS' if all(f['outcome']=='PASS' for f in assessment['findings']) and not assessment['uncertainties'] and not assessment['limitations']
                    else 'PASS_WITH_KNOWN_LIMITATIONS')
                require(assessment['verdict']==verdict and (verdict not in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'}
                    or assessment['required_correction'] is None),'semantic verdict does not follow original findings')
                self._owned_capture(checked_ref,'verifier_check',reviewer);verifier,reviewer_basis=self._checked(checked_ref,subjects=[assessment_ref],kind='verifier_check')
                require(verifier['check_plan_ref']==reviewer_grant['check_plan_ref'],'reviewer mechanics changed exact assignment basis')
                require(all(r['outcome']=='PASS' for r in verifier['results'] if r['check_id'] in reviewer_basis['mandatory_deterministic']),
                    'semantic assessment lacks mandatory reviewer mechanics')
                reviewer_observations=[self.json_ref(pin,'observation') for pin in measured['observation_refs']
                    if any(e['assignment_grant_ref']==reviewer for e in self._owned_capture(pin,'observation'))]
                require(reviewer_observations and all(o['contract_ref']==reviewer_grant['contract_ref'] and assessment_ref in o['output_refs']
                    for o in reviewer_observations),'semantic assessment lacks its exact actual reviewer observation')
            for pin in measured['observation_refs']:
                self._owned_capture(pin,'observation');self.json_ref(pin,'observation')
            for pin in measured['trace_refs']:
                self._owned_capture(pin,{'trace','model_call','route','model_start','model_refusal'});self.bytes_ref(pin)
            for pin in observed['trace_refs']:
                # Original E2 observation traces are source provenance and are
                # deliberately not a new private invocation's usage evidence.
                if observation_kind=='observation':self._owned_capture(pin,{'trace','model_call','route','model_start','model_refusal'})
            if measured['status']=='completed':
                require(measured['failure'] is None and (set(measured['output_refs'])==set(self.source_outputs) if self.request['entry_point']=='E2'
                    else set(self.json_ref(measured['contract_ref'],'actual_contract')['required_outputs'])<=set(measured['output_refs']))
                    and all(result['outcome']=='PASS' for result in checked['results'] if result['check_id'] in basis['mandatory_deterministic']),
                    'completed measurement lacks actual mandatory outputs/checks')

    def json_or_bytes_output(self,ref):
        require(('output',ref_key(ref)) in self.by_kind,'measured output is not request-owned original bytes')
        return self.bytes_ref(ref)

    def _response_closure(self):
        if self.terminal is None or self.terminal['result_ref'] is None:return
        require(len(self.terminal['measurement_refs'])==1,'original response needs one exact measurement')
        measured_ref=self.terminal['measurement_refs'][0];measured=self.json_ref(measured_ref,'measurement')
        observed=self.json_ref(measured['observation_ref']);checked=self.json_ref(measured['deterministic_ref'],'deterministic_result')
        basis=self.private(checked['check_plan_ref'],'check_plan');result=self.json_ref(self.terminal['result_ref'],'result')['result']
        require(isinstance(result,dict) and result.get('invalid_for_product') is True and type(result.get('duration_s')) in (int,float)
            and math.isfinite(result['duration_s']) and result['duration_s']>=measured['elapsed_s'],'response origin/duration differs from actual measurement')
        if self.request['entry_point']=='E3':
            require(set(result)=={'invocation_id','status','output_refs','check_results','tool_effects_observed','model_calls','reason','duration_s','invalid_for_product'}
                and result['invocation_id']==observed['id'] and result['status']==(measured['status'] if measured['status'] in {'completed','failed','blocked'} else 'failed')
                and result['output_refs']==measured['output_refs']
                and result['check_results']==[{'check_id':r['check_id'],'status':r['outcome']} for r in checked['results']]
                and result['tool_effects_observed']==(observed['effects'] or None)
                and result['reason']==(measured['failure'] or ('Complete tool-effect observation unavailable' if not observed['effects'] else None)),
                'single-CC response differs from original measurement')
        else:
            eligible=all(r['outcome']=='PASS' for r in checked['results'] if r['check_id'] in basis['mandatory_deterministic'])
            assessment_ref=measured['assessment_refs'][0] if measured['assessment_refs'] else None
            tier2=self.json_ref(assessment_ref,'assessment')['verdict'] if assessment_ref else 'NOT_RUN'
            verdict=tier2 if eligible and assessment_ref and not measured['failure'] else 'FAIL'
            action='advance' if verdict in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'} and not measured['failure'] else 'halt'
            decision={'contract_ref':self.scope['source_contract_ref'],'check_plan_ref':checked['check_plan_ref'],
                'output_port':self.scope['selected_output_port'],'output_refs':[measured['output_refs'][self.scope['selected_output_port']]],
                'deterministic_result_ref':measured['deterministic_ref'],'assessment_ref':assessment_ref,
                'verifier_check_ref':measured['verifier_check_refs'][0] if measured['verifier_check_refs'] else None,
                'verdict':verdict,'action':action,'reasons':[measured['failure'] or 'All mandatory checks and selected semantic criteria passed'],
                'accepted':False,'invalid_for_product':True}
            require(set(result)=={'replay_id','tier1_verdict','tier2_verdict','gate_decision','advanced','persisted_at','downstream_action',
                'reason','evidence_refs','model_calls','duration_s','invalid_for_product'}
                and result['tier1_verdict']==('PASS' if eligible else 'FAIL') and result['tier2_verdict']==tier2
                and result['gate_decision']==decision and result['reason']==measured['failure'],
                'E2 response differs from exact original selected measurement')
            if result['persisted_at'] is None:
                require(result['evidence_refs']==[measured_ref] and result['advanced'] is False and result['downstream_action']=='locked'
                    and not self.rows('evaluation_gate') and not self.rows('recording_action'),'unrecorded replay invents recording action')
            else:
                require(len(result['evidence_refs'])==2 and result['evidence_refs'][0]==measured_ref,'recording evidence population differs')
                gate_ref=result['evidence_refs'][1];self._owned_capture(gate_ref,'evaluation_gate');gate=self.json_ref(gate_ref,'evaluation_gate')
                require(set(gate)=={'id','decision','persisted_at','invalid_for_product'} and gate['invalid_for_product'] is True
                    and gate['decision']==decision and gate['persisted_at']==result['persisted_at']
                    and result['advanced'] is (action=='advance') and result['downstream_action']==('started' if action=='advance' else 'halted'),
                    'recording Gate changed original decision')
                actions=self.rows('recording_action');require(len(actions)==1,'recording action absent or ambiguous')
                recorded=self.json_ref(actions[0]['artifact_ref'],'recording_action')
                require(set(recorded)=={'id','gate_ref','at','action','scheduler_kind','invalid_for_product'} and recorded['gate_ref']==gate_ref
                    and recorded['action']==result['downstream_action'] and recorded['scheduler_kind']=='recording'
                    and recorded['invalid_for_product'] is True,'recording action changed original Gate')
        calls=result.get('model_calls');actual=self.model_call_rows()
        require(isinstance(calls,list) and len(calls)==len(actual),'response omits original captured ModelCall population')
        by_ref={ref_key(row['call_ref']):row for row in actual}
        require(len(by_ref)==len(actual),'duplicate captured ModelCall')
        for row in calls:
            converted=dict(row,cost=row['cost']['amount'] if isinstance(row.get('cost'),dict) else row.get('cost'))
            require(converted==by_ref.pop(ref_key(row['call_ref']),None),'response ModelCall summary differs from original bytes')

    def _terminal(self,request_ref,scope_ref):
        terminals=self.rows('terminal');self.terminal=None
        require(len(terminals)<=1,'multiple evaluation terminals')
        links=[(index,event) for index,(_,event) in enumerate(self.events) if event['kind']=='terminal']
        if not terminals:
            require(not links and self.manifest['request_state'] in {'started','outcome_unknown'}
                and self.manifest['result_ref'] is None and self.manifest['failure_ref'] is None
                and not self.manifest['measurement_refs'], 'evaluation manifest invents an uncaptured terminal')
            return
        ref=terminals[0]['artifact_ref'];terminal=self.terminal=self.private(ref,'terminal')
        require(len(links)==1 and links[0][1]['capture_ref']==ref
            and links[0][1]['previous_event_ref']==terminal['through_event_ref']
            and terminal['request_ref']==request_ref and terminal['scope_ref']==scope_ref
            and terminal['state']==self.manifest['request_state'], 'evaluation terminal lacks its original journal prefix')
        prefix={(e['capture_kind'],ref_key(e['capture_ref'])) for _,e in self.events[:links[0][0]] if e['kind']=='captured'}
        for key,kind in (('result_ref','result'),('failure_ref','failure')):
            require(self.manifest[key]==terminal[key] and (terminal[key] is None
                or (kind,ref_key(terminal[key])) in prefix), 'terminal promises uncaptured original evidence')
        require(self.manifest['measurement_refs']==terminal['measurement_refs']
            and all(('measurement',ref_key(ref)) in prefix for ref in terminal['measurement_refs']), 'terminal measurement closure differs')
        for kind in ('result','failure'):
            pin=terminal[kind+'_ref']
            if pin is None:continue
            body=self.json_ref(pin,kind)
            require(set(body)==({'id','result','accepted','invalid_for_product'} if kind=='result'
                else {'id','reason','accepted','invalid_for_product'}),'invalid original terminal wrapper')
            if kind=='failure':require(isinstance(body['reason'],str) and bool(body['reason']),'empty terminal failure reason')
        cancellations=[e for _,e in self.events[:links[0][0]] if e['kind']=='cancellation_requested']
        cancel_ids=[e['reason'][len('Original cancel identity: '):] for e in cancellations
            if isinstance(e['reason'],str) and e['reason'].startswith('Original cancel identity: ')]
        require(len(set(cancel_ids))<=1 and all(cancel_ids),'ambiguous original cancellation identity')
        containment=terminal['containment_ref']
        if containment is not None:
            require(('containment',ref_key(containment)) in prefix and len(cancel_ids)==1,'terminal containment has no original cancellation prefix')
            receipt=self.json_ref(containment,'containment')
            require(set(receipt)=={'id','request_ref','cancel_id','scope_ref','no_started_assignments','receipts','accepted','invalid_for_product'}
                and receipt['request_ref']==request_ref and receipt['scope_ref']==scope_ref and receipt['cancel_id']==cancel_ids[0]
                and type(receipt['no_started_assignments']) is bool and isinstance(receipt['receipts'],list)
                and receipt['no_started_assignments'] is (not any(e['kind']=='assignment_started' for _,e in self.events[:links[0][0]]))
                and (receipt['no_started_assignments'] or receipt['receipts'])
                and all(isinstance(item,dict) and item.get('contained') is True
                    and item.get('run_id')==self.scope['private_run_id'] and item.get('request_id')==cancel_ids[0]
                    for item in receipt['receipts']),'original containment does not prove this request/cancellation')
            captured=self._owned_capture(containment,'containment')[0]
            require(any(e['sequence']<captured['sequence'] for e in cancellations),'containment precedes original cancellation')
        if terminal['state']=='cancelled':
            require(containment is not None and terminal['result_ref'] is None and terminal['failure_ref'] is not None,
                'cancelled terminal lacks original containment/failure')
        if terminal['state']=='completed':
            require(terminal['result_ref'] is not None and terminal['measurement_refs'] and not cancellations,
                'completed evaluation lacks actual result/measurement or contradicts cancellation')
        if cancellations and terminal['result_ref'] is not None:
            require(terminal['state'] in {'failed','outcome_unknown'} and terminal['failure_ref'] is not None
                and len(terminal['measurement_refs'])==1,'cleanup response lacks original failed measurement')
            measured=self.json_ref(terminal['measurement_refs'][0],'measurement')
            result=self.json_ref(terminal['result_ref'],'result')['result'];failure=self.json_ref(terminal['failure_ref'],'failure')['reason']
            require(measured['status'] in {'failed','blocked'} and isinstance(result,dict) and result.get('invalid_for_product') is True
                and failure==measured['failure']==result.get('reason'),'cleanup response changed original failure')
            if terminal['state']=='outcome_unknown':require(failure=='containment_uncertain' and containment is None,'unknown cleanup claims containment')
            else:require(containment is not None,'failed cleanup lacks actual containment')
        # A terminal cannot promise evidence first captured after publication.
        for pin in terminal['measurement_refs']:
            measured=self.json_ref(pin,'measurement')
            edges=[('deterministic_result',measured['deterministic_ref']),
                *[('assessment',r) for r in measured['assessment_refs']],*[('verifier_check',r) for r in measured['verifier_check_refs']],
                *[('observation',r) for r in measured['observation_refs']]]
            if self.request['entry_point']=='E3':
                edges.append(('observation',measured['observation_ref']))
                edges.extend(('output',r) for r in measured['output_refs'].values())
            require(all((kind,ref_key(ref)) in prefix for kind,ref in edges),'terminal measurement relies on late captured evidence')
            require(all(any((kind,ref_key(ref)) in prefix for kind in ('trace','model_call','route','model_start','model_refusal'))
                for ref in measured['trace_refs']),'terminal measurement relies on late native evidence')

    def _scientific_order(self):
        captured={};started=set()
        for _,event in self.events:
            grant=event['assignment_grant_ref']
            if grant is None:
                require(not (event['kind']=='captured' and event['capture_kind'] in START_SCHEMAS),
                    'scientific receipt lacks its original assignment')
                continue
            key=ref_key(grant);slots=captured.setdefault(key,{})
            if event['kind']=='captured' and event['capture_kind'] in START_SCHEMAS:
                kind=event['capture_kind'];require(kind not in slots,'duplicate scientific start capture')
                require(key not in started,'scientific receipt was captured after assignment start')
                slots[kind]=event['capture_ref']
                value=self.json_ref(event['capture_ref'],kind)
                if kind=='execution_preparation':
                    assigned=self.private(grant,'assignment_grant')
                    require(value['assignment_grant_ref']==grant and all(value[k]==assigned[k]
                        for k in ('contract_ref','invocation_id','execution_id')),
                        'scientific preparation differs from original assignment')
                    child=self.json_ref(assigned['contract_ref'],'actual_contract')
                    allowance=min(assigned['limits']['time_s'],child['subnode_limits']['time_s'],
                        child['bindings'][0]['limits']['time_s'])
                    require(assigned['started_unix_ns']<=value['recorded_unix_ns']
                        <value['deadline_unix_ns']<=assigned['deadline_unix_ns']
                        and value['deadline_unix_ns']-value['recorded_unix_ns']<=int(allowance*1_000_000_000),
                        'scientific preparation widens its original remaining child allowance')
                elif kind=='execution_preflight':
                    require(value['preparation_ref']==slots.get('execution_preparation'),'scientific preflight precedes preparation')
                else:
                    require(value['preflight_ref']==slots.get('execution_preflight'),'scientific activation precedes preflight')
                    preflight=self.json_ref(value['preflight_ref'],'execution_preflight')
                    require(value['broker_instance_id']==preflight['broker_instance_id'],'scientific broker identity changed')
            if event['kind']=='assignment_started':
                require(key not in started,'duplicate original assignment start')
                if event['schema']=='ai4r-evaluation-event:2' or slots:
                    require(set(slots)==set(START_SCHEMAS),'scientific assignment starts before original receipt capture')
                    preparation=self.json_ref(slots['execution_preparation'],'execution_preparation')
                    preflight=self.json_ref(slots['execution_preflight'],'execution_preflight')
                    activation=self.json_ref(slots['execution_activation'],'execution_activation')
                    require(preparation['recorded_unix_ns']<=preflight['recorded_unix_ns']<=activation['recorded_unix_ns']
                        <=event['recorded_unix_ns']<preparation['deadline_unix_ns'],'scientific receipt/start chronology differs')
                started.add(key)

    def freeze(self,destination):
        dest=Path(destination)
        require(not dest.exists() and not dest.is_symlink(),'frozen evaluation export identity already exists')
        _evidence_directory(dest.parent)
        with tempfile.TemporaryDirectory(prefix='.evaluation-',dir=dest.parent) as temporary:
            staging=Path(temporary)
            if os.name=='posix':staging.chmod(0o2750)
            for name,payload in self.entries.items():write_once(staging/name,payload)
            write_once(staging/'archive.zip',self.raw)
            os.rename(staging,dest)
        return copy.deepcopy(self.manifest)
