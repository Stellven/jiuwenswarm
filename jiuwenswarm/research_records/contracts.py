"""Validate side records using only the generated neutral contract publication."""
from importlib.resources import files
import json
from jsonschema import Draft202012Validator
from referencing import Registry,Resource


class ContractData:
    def __init__(self):
        root=files('jiuwenswarm.research_contracts');registry=Registry();self.schemas={}
        for file in (root/'schemas').iterdir():
            if file.name.endswith('.json'):
                schema=json.loads(file.read_bytes())
                if '$id' in schema:
                    registry=registry.with_resource(schema['$id'],Resource.from_contents(schema))
                    # Private/native data identities are deliberately absent
                    # from the public catalog. They still have explicit pinned
                    # schemas for offline consumers; this supplies validation,
                    # never a producer registration or execution capability.
                    self.schemas[schema['$id']]={'$ref':schema['$id']}
        for entry in json.loads((root/'catalog.json').read_bytes())['contracts']:
            self.schemas[entry['name']]={'$ref':entry['schema_id']}
            self.schemas[entry['schema_id']]={'$ref':entry['schema_id']}
        # Generated current field contracts intentionally override historical
        # standalone aliases where the authoritative lookup selects them.
        for name,entry in json.loads((root/'contract_lookup.json').read_bytes())['contracts'].items():
            ref=entry['schema_id']+('#/$defs/'+entry['definition'] if entry['definition'] else '')
            self.schemas[name]={'$ref':ref}
        self.registry=registry
    def validate(self,name,value):
        if isinstance(value,dict):
            if name=='route-record' and value.get('schema_version')=='4.0.0':
                name='urn:ai4r:automatic-route-record:4.0.0'
            if name=='route-record' and value.get('schema_version')=='3.0.0':
                name='urn:ai4r:automatic-route-record:3.0.0'
            if name=='route-record' and value.get('schema_version')=='2.0.0':
                name='urn:ai4r:manual-route-record:2.0.0'
            elif name=='invocation-observation' and value.get('schema_version')=='4.0.0':
                name='urn:ai4r:invocation-observation:4.0.0'
        if name not in self.schemas:raise ValueError('unknown contract identity')
        if next(Draft202012Validator(self.schemas[name],registry=self.registry).iter_errors(value),None) is not None:raise ValueError('contract validation failed: '+name)
