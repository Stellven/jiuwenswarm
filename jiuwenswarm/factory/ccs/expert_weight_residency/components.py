"""Deterministic static placement from admitted allocations and training demand."""
from collections import Counter
from fractions import Fraction
import hashlib
import json
import re


def integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= 2**63-1:
        raise ValueError('Invalid bounded '+name)
    return value


def identity(row):
    return (row['checkpoint'],integer(row['layer'],'layer'),integer(row['expert'],'expert'),row['layout'])


def plan(inputs):
    ceiling=integer(inputs['physical_bytes'],'physical_bytes',1)
    allocations={}
    for row in inputs['allocations']:
        if row['kind'] not in ('fixed','workspace','headroom') or not isinstance(row['id'],str) or not row['id']:
            raise ValueError('Explicit physical allocation identity and kind required')
        value=(row['kind'],integer(row['bytes'],'allocation'))
        if row['id'] in allocations and allocations[row['id']]!=value:
            raise ValueError('Conflicting shared allocation')
        allocations[row['id']]=value
    contexts=inputs['contexts']
    if not contexts or len(contexts)>32:
        raise ValueError('Bounded admitted context reservations required')
    sequences=[integer(c['sequence_bytes'],'sequence_bytes') for c in contexts]
    reserved=sum(v[1] for v in allocations.values())+max(sequences)
    if reserved>=ceiling:
        return dict(status='infeasible',reserved_bytes=reserved,physical_bytes=ceiling,execution_authorized=False)
    capacity=ceiling-reserved
    fallback=integer(inputs['fallback_bytes'],'fallback_bytes',1)
    io=integer(inputs['max_inflight_bytes'],'max_inflight_bytes',1)
    if fallback>capacity or io>capacity:
        return dict(status='infeasible',reserved_bytes=reserved,slot_bytes=capacity,execution_authorized=False)
    checkpoint=inputs['checkpoint']
    if not isinstance(checkpoint,str) or not re.fullmatch('[a-f0-9]{64}',checkpoint):
        raise ValueError('Pinned checkpoint manifest SHA256 required')
    inventory={}
    if len(inputs['inventory'])>100000 or len(inputs['trace'])>100000:
        raise ValueError('Bounded inventory and training trace required')
    names=set()
    for row in inputs['inventory']:
        key=identity(row)
        if key[0]!=checkpoint or not isinstance(key[3],str) or len(key[3])>128:
            raise ValueError('Checkpoint/layout identity differs')
        tensor=row['tensor']
        if not isinstance(tensor,str) or not re.fullmatch(r'blk\.'+str(key[1])+r'\.ffn_(gate|up|down)_exps\.weight',tensor):
            raise ValueError('Expert tensor role/layer mismatch')
        name=tensor+':'+str(key[2])
        size=integer(row['bytes'],'expert bytes',1)
        if key in inventory or name in names:raise ValueError('Duplicate semantic expert/tensor identity')
        inventory[key]=(name,size);names.add(name)
    training=set(inputs['training_requests']);heldout=set(inputs.get('evaluation_requests',[]))
    if not training or training & heldout:raise ValueError('Distinct training and evaluation request IDs required')
    counts=Counter()
    for row in inputs['trace']:
        if row['request'] not in training:continue
        key=identity(row)
        if key not in inventory:raise ValueError('Training demand lacks admitted byte identity')
        counts[key]+=1
    selected=[];used=0;env_names=[]
    for key in sorted(counts,key=lambda k:(-Fraction(counts[k],inventory[k][1]),k)):
        name,size=inventory[key]
        if size>capacity-fallback-used:continue
        if len(','.join(env_names+[name]))>32768:continue
        env_names.append(name);used+=size
        selected.append(dict(checkpoint=key[0],layer=key[1],expert=key[2],layout=key[3],tensor= name.rsplit(':',1)[0],bytes=size,training_demands=counts[key]))
    totals={kind:sum(v[1] for v in allocations.values() if v[0]==kind) for kind in ('fixed','workspace','headroom')}
    env={'LLAMA_EXPERT_RESIDENCY':'1','LLAMA_EXPERT_STREAMING':'1','LLAMA_EXPERT_CHECKPOINT':checkpoint,
         'LLAMA_EXPERT_PHYSICAL_BYTES':str(ceiling),'LLAMA_EXPERT_FIXED_BYTES':str(totals['fixed']),
         'LLAMA_EXPERT_SEQUENCE_BYTES':str(max(sequences)),'LLAMA_EXPERT_WORKSPACE_BYTES':str(totals['workspace']),
         'LLAMA_EXPERT_HEADROOM_BYTES':str(totals['headroom']),'LLAMA_EXPERT_SLOT_BYTES':str(capacity),
         'LLAMA_EXPERT_IO_BYTES':str(io),'LLAMA_EXPERT_FALLBACK_BYTES':str(fallback),'LLAMA_EXPERT_WARM_SET':','.join(env_names)}
    result=dict(status='planned',physical_bytes=ceiling,reserved_bytes=reserved,slot_bytes=capacity,
        context_slot_bytes=[ceiling-sum(v[1] for v in allocations.values())-s for s in sequences],
        selected=selected,warm_bytes=used,fallback_bytes=fallback,effective_environment=env,
        io_cap_bytes=io,io_uses_slot_storage=True,execution_authorized=False,
        policy='frozen training frequency per packed byte; demand-warmed protected set plus idle LRU fallback',
        limitations=['Declared reservations require host validation; this is not physical-memory measurement.',
                     'Original mmap and OS page cache remain; owned slots can duplicate file-backed pages.',
                     'Training replay is not a DeepSeek timing or hit-rate claim.'])
    result['manifest_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result


def dispatch(capability, inputs):
    if capability=='plan':return plan(inputs)
    raise ValueError('Unknown capability')
