"""Frozen, input-independent type definitions for an output-only reviewer."""
from __future__ import annotations

import copy
import json
from importlib.resources import files

from ..contracts import contract_schema


def _compact(schema):
    value=copy.deepcopy(schema);definitions=value.pop('$defs',{});selected={}
    def visit(item):
        if isinstance(item,dict):
            ref=item.get('$ref','')
            if ref.startswith('#/$defs/'):
                key=ref[len('#/$defs/'):].split('/',1)[0].replace('~1','/').replace('~0','~')
                if key not in selected and key in definitions:
                    selected[key]=copy.deepcopy(definitions[key]);visit(selected[key])
            for child in item.values():visit(child)
        elif isinstance(item,list):
            for child in item:visit(child)
    visit(value)
    if selected:value['$defs']=selected
    return value


def frozen_output_instructions(base,declaration):
    """Derive only from installed schema IDs in this declaration.

    No request, input artifact, prior output, runtime record or lookup tool is
    accepted. The resulting bytes are frozen into the checking profile before
    calibration and reused unchanged for every invocation of this Capsule.
    """
    output_types={port['name']:{'schema_ref':port['schema_ref'],'required':port['required'],
        'schema':_compact(contract_schema(port['schema_ref']))} for port in declaration['ports']['outputs']}
    context={'declared_output_types':output_types}
    if 'urn:jiuwenswarm:m1-design:common:1.0.0' in json.dumps(context):
        context['common_schema']=json.loads(files('jiuwenswarm.research_contracts').joinpath('schemas/common.schema.json').read_text('utf-8'))
    prefix=(base.decode('utf-8') if isinstance(base,bytes) else base)
    return (prefix+'\n\nFixed definitions of the Capsule\'s declared output types (each schema is an independent document):\n'
        +json.dumps(context,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        +'\nUse these fixed definitions to assess the selected exact output. For a text output, check its declared text constraints; '
        'for an archive projection, assess its shown file contents rather than treating the projection as literal ZIP bytes. '
        'These are type definitions only, not user input or external evidence. No reference lookup is available.').encode('utf-8')
