"""Admit original packed expert ranges, never synthesized compact layouts."""
import re

SUPPORTED={'f32':(1,4),'iq2_xxs':(256,66),'iq2_xs':(256,74),'iq1_m':(256,56)}
PIN='9048bad8d6e3a0f9f1726e238e451181c7e02613'


def uint(value):
    if type(value) is not int or not 0<=value<=2**63-1:raise ValueError('Invalid bounded range value')
    return value


def ranges(inputs):
    if inputs['source_commit']!=PIN:raise ValueError('Unsupported source seam')
    checkpoint=inputs['checkpoint']
    if not isinstance(checkpoint,str) or not re.fullmatch('[a-f0-9]{64}',checkpoint):raise ValueError('Checkpoint identity required')
    t=inputs['tensor'];shape=t['shape'];stride=uint(t['expert_stride']);offset=uint(t['offset']);extent=uint(t['bytes'])
    if len(shape)!=3 or any(uint(n)<1 for n in shape):raise ValueError('Three positive tensor dimensions required')
    if t['layout'] not in SUPPORTED:raise ValueError('Unsupported packed layout')
    block,width=SUPPORTED[t['layout']];columns,rows,experts=shape
    if columns%block or stride!=columns//block*width*rows or extent!=stride*experts:
        raise ValueError('Packed extent/stride mismatch')
    shard=t['shard'];file_size=uint(shard['size'])
    if not re.fullmatch('[a-f0-9]{64}',shard['sha256']) or offset>file_size or extent>file_size-offset:
        raise ValueError('Shard identity or range mismatch')
    match=re.fullmatch(r'blk\.([0-9]+)\.ffn_(gate|up|down)_exps\.weight',t['name'])
    if not match:raise ValueError('Only routed expert tensors are admitted')
    selected=inputs['selected_ids']
    if not isinstance(selected,list) or not selected or len(selected)>4096:raise ValueError('Bounded authoritative routed set required')
    if any(uint(e)>=experts for e in selected):raise ValueError('Expert ID outside tensor')
    layout=t['name']+':'+t['layout']+':'+str(columns)+':'+str(rows)
    return dict(checkpoint=checkpoint,source_commit=PIN,selected_ids=list(selected),
        ranges=[dict(key=[checkpoint,int(match[1]),e,layout],shard_sha256=shard['sha256'],
                     offset=offset+e*stride,bytes=stride) for e in dict.fromkeys(selected)],
        row_order_unchanged=True,mixture_weights_unchanged=True,prefetch=False,
        consumer='ARM ordinary CPU MUL_MAT_ID; compact tiled view unverified; CPU_REPACK/CUDA unsupported',
        execution_authorized=False,engram_included=False)


def integration(inputs):
    if inputs.get('source_commit')!=PIN:raise ValueError('Unsupported source seam')
    return dict(source_commit=PIN,patch_material='integration_patch',
        requires_materials=['streaming_source','streaming_api'],
        requires_releases={'engine.expert_weight_residency_builder':'residency_header'},
        activation={'LLAMA_EXPERT_RESIDENCY':'1','LLAMA_EXPERT_STREAMING':'1'},
        rollback={'LLAMA_EXPERT_RESIDENCY':'0','LLAMA_EXPERT_STREAMING':'0'},
        required_budget_receipt='engine.expert_weight_residency_builder.plan',
        existing_path=['factory.source_workbench','factory.builder','factory.lab_client','factory.methodology_ab'],
        hardware_admitted=False,third_cc='pending profile evidence')


def dispatch(capability, inputs):
    if capability=='ranges':return ranges(inputs)
    if capability=='integration':return integration(inputs)
    raise ValueError('Unknown capability')
