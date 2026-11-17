"""One declaration vocabulary for native CC components and compositions.

Descriptions do not grant execution. Only the operator-selected sealed releases
already admitted by CCService can appear in this executable catalog.
"""
from dataclasses import asdict
import hashlib
import json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def port(spec):
    spec={'kind':spec} if isinstance(spec,str) else spec
    kind=spec['kind']
    schema=spec.get('schema',{'type':'string'} if kind=='text' else {})
    return dict(transport=kind if kind in {'artifact','handle'} else 'value',
        semantic_type='cc:'+kind,required=not spec.get('optional',False),data_schema=schema,
        schema_known='schema' in spec or kind=='text',
        **({'value_kind':kind} if kind in {'json','text'} else {}),
        **{key:spec[key] for key in ('description','media_type') if key in spec})


def export_pool(service):
    host=service.runtime.host
    entries=[];references={};subrefs={}
    declarations={cap.release:host.describe(cap.release) for cap in service.runtime.capabilities.values()}

    def origin(system,path,original,release=None):
        return dict(system=system,repository='trusted-local:sealed-ccstore',revision=None,path=path,
            declaration_sha256=fingerprint(original),original=original,
            **({'release':release} if release else {}))

    def base(identifier,version,name,kind,original,system='workflow',release=None):
        return dict(id=identifier,version=version,name=name,kind=kind,
            origin=origin(system,'releases/'+release+'/cc.yaml' if release else 'operator-workflow-config',original,release),
            inputs={},outputs={},requirements=dict(resources=[],effects=None,backends=None,constraints={}),verification=[])

    for cap in service.runtime.capabilities.values():
        declaration=declarations[cap.release]
        identifier='cc:'+declaration['id']+'/capability/'+cap.capability
        version=declaration['version']
        references[cap.id]=dict(id=identifier,version=version)
        entry=base(identifier,version,cap.name,'operation',declaration,'cc',cap.release)
        entry['inputs']={name:port(cap.input_contracts.get(name,{'kind':kind,'optional':name in cap.optional_inputs})) for name,kind in cap.inputs.items()}
        for name in cap.optional_inputs:
            if name in entry['inputs']:
                entry['inputs'][name]['required']=False
        entry['outputs']={name:port(cap.output_contracts.get(name,kind)) for name,kind in cap.outputs.items()}
        entry['requirements']['effects']=list(cap.changes)
        entry['requirements']['resources']=[dict(category='tool',name=value) for value in declaration['capabilities'][cap.capability].get('needs',[])]
        bindings=declaration['bindings']
        if len(bindings)!=1:
            raise ValueError('A catalog execution profile needs one selected native binding')
        entry['implementation']=dict(type='cc',bundle=dict(id='cc:'+declaration['id'],version=version),
            capability=cap.capability,binding=next(iter(bindings.values())))
        entry['execution_profile']=dict(release=cap.release,managed_inputs=['idem_key'] if cap.lifecycle else [])
        if cap.lifecycle:
            entry['execution_profile'].update(lifecycle=cap.lifecycle,result_ports={name:port(spec) for name,spec in cap.result_contracts.items()})
        entries.append(entry)
    for release,declaration in declarations.items():
        entry=base('cc:'+declaration['id'],declaration['version'],declaration['id'],'collection',declaration,'cc',release)
        entry['members']=[references[cap.id] for cap in service.runtime.capabilities.values() if cap.release==release]
        entries.append(entry)
    for sub in service.registry.subworkflows.values():
        subrefs[sub.id]=dict(id='workflow:subworkflow/'+sub.id,version='sha256:'+fingerprint(asdict(sub)))

    def binding(value):
        value=asdict(value)
        return {'node':value.pop('source'),**{key:item for key,item in value.items() if item is not None and item!='' and not (key=='channel' and item=='outputs')}}

    def add_composite(definition,workflow=False):
        original=asdict(definition)
        ref=dict(id='workflow:workflow/'+definition.id,version='sha256:'+fingerprint(original)) if workflow else subrefs[definition.id]
        entry=base(ref['id'],ref['version'],definition.name,'composite',original)
        entry['inputs']={name:port(kind) for name,kind in definition.inputs.items()}
        steps=definition.subworkflows if workflow else definition.stages
        nodes=[]
        for step in steps:
            reference=subrefs[step.definition] if hasattr(step,'definition') else references[step.stage_id]
            nodes.append(dict(id=step.id,capability=reference,bindings={name:binding(value) for name,value in step.bindings.items()}))
        if workflow:
            outputs=service.registry.expand(definition.id).outputs
        else:
            from .workflow_definitions import PortReference
            _,outputs=service.registry._expand_subworkflow(definition,'catalog/'+definition.id,
                {name:PortReference(None,name,kind) for name,kind in definition.inputs.items()})
        entry['outputs']={name:port(ref.kind) for name,ref in outputs.items()}
        entry['composition']=dict(nodes=nodes,outputs={name:binding(value) for name,value in definition.outputs.items()})
        entries.append(entry)

    for definition in service.registry.subworkflows.values():
        add_composite(definition)
    for definition in service.registry.workflows.values():
        add_composite(definition,True)
    return dict(schema_version='0.2.0',entries=entries)
