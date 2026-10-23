"""Input-dependent compiler checks; semantic review never receives these inputs."""

from __future__ import annotations

from .engine import CheckError
from ..contracts import validate
from ..target_comparisons import check_target_comparisons


def walk(value):
    yield value
    if isinstance(value,dict):
        for child in value.values():yield from walk(child)
    elif isinstance(value,list):
        for child in value:yield from walk(child)


def unique_ids(value,check_id):
    ids=[item['id'] for item in walk(value) if isinstance(item,dict) and 'id' in item and 'sha256' not in item]
    if len(ids)!=len(set(ids)):raise CheckError(check_id,'Local IDs are not unique')


def check_intent(intent,intake,store,observation=None):
    validate('intent-ir',intent);unique_ids(intent,'intent_schema')
    allowed=[intake['request_ref'],*intake['source_refs']]
    if intent['request_ref']!=intake['request_ref'] or any(ref not in allowed for ref in intent['context_refs']):
        raise CheckError('exact_identity','Intent references a source outside qualified intake')
    for value in walk(intent):
        if not isinstance(value,dict) or not {'source_ref','start','end'}.issubset(value):continue
        if value['source_ref'] not in allowed:raise CheckError('source_spans','Span names an unqualified source')
        text=store.read_blob(value['source_ref']).decode('utf-8',errors='strict')
        if not 0<=value['start']<value['end']<=len(text):raise CheckError('source_spans','Span is empty or outside Unicode code-point bounds')
    if observation is not None and (observation['outcome']!='success' or not observation['observed_runtime']):
        raise CheckError('exact_identity','Pinned invocation did not complete observably')


def _pointer(value,pointer):
    if not isinstance(pointer,str) or not pointer.startswith('/'):raise KeyError(pointer)
    for key in pointer[1:].split('/'):
        key=key.replace('~1','/').replace('~0','~')
        value=value[int(key)] if isinstance(value,list) else value[key]
    return value


def check_brief(brief,intent,intake,store,*,intent_ref,intake_ref,policy,policy_ref):
    validate('research-brief',brief);unique_ids(brief,'brief_schema')
    try:check_target_comparisons(brief)
    except ValueError as exc:raise CheckError('brief_schema',str(exc)) from exc
    if brief['intake_ref']!=intake_ref or brief['intent_ref']!=intent_ref:
        raise CheckError('source_identity','Brief is not bound to exact accepted Intent/intake')
    allowed=[intent_ref,intake_ref,policy_ref,intake['request_ref'],*intake['source_refs'],*intake['resource_refs']]
    for value in walk(brief):
        if isinstance(value,dict) and set(value)=={'id','sha256'}:
            store.read_blob(value)
            if value not in allowed:raise CheckError('source_identity','Brief refers to unqualified source bytes')
    if set(map(lambda r:(r['id'],r['sha256']),brief['resource_refs']))!=set(map(lambda r:(r['id'],r['sha256']),intake['resource_refs'])):
        raise CheckError('source_identity','Brief resource inventory changed')
    for assumption in brief['assumptions']:
        if assumption['authority_ref']!=policy_ref:raise CheckError('source_identity','Default authority is not the protected policy')
        for pointer in assumption['affected_fields']:
            try:target=_pointer(brief,pointer)
            except (KeyError,IndexError,ValueError,TypeError):raise CheckError('source_identity','Assumption pointer does not exist') from None
            if not isinstance(target,dict) or target.get('origin')!='system_default':raise CheckError('source_identity','Applied default must point to an attributable default field')
            if target.get('category')!='hardware' or target.get('normalized_value')!=policy['hardware_profile']:
                raise CheckError('source_identity','No authority for this actual default')
    defaults=[v for v in walk(brief) if isinstance(v,dict) and v.get('origin')=='system_default']
    pointed=[]
    for a in brief['assumptions']:
        pointed.extend(_pointer(brief,p) for p in a['affected_fields'])
    if any(item not in pointed for item in defaults):raise CheckError('source_identity','An applied default lacks an assumption')
    mandatory={r['id'] for r in brief['mandatory_requirements']}
    for field in ('acceptance_expectations','evidence_obligations','target_metrics'):
        if any(not set(item['requirement_ids']).issubset(mandatory) for item in brief[field]):raise CheckError('requirement_coverage','Unknown requirement link')
    for field in ('acceptance_expectations','evidence_obligations'):
        if not mandatory.issubset({rid for item in brief[field] for rid in item['requirement_ids']}):raise CheckError('requirement_coverage','Mandatory requirement has no acceptance/evidence link')
    # Stable producer-preserved item IDs make the mechanical coverage observable;
    # they do not assert semantic entailment or judge a paraphrase's truth.
    for before,after in [('constraints','constraints'),('user_targets','target_metrics'),('in_scope','in_scope')]:
        covered={v['id'] for v in brief[after]}
        unresolved='\n'.join(str(v) for v in brief['unresolved_items'])
        for item in intent[before]:
            if item['id'] not in covered and item['id'] not in unresolved:
                raise CheckError('requirement_coverage','Intent item is absent without an explicit unresolved disposition: '+item['id'])


def compiler_checks(ctx,inputs,outputs):
    declaration=ctx.store.read_record(ctx.contract['bindings'][0]['declaration_ref'])
    name=declaration['identity']['name'];ids=['intent_schema','source_spans','exact_identity'] if name=='intent.compiler' else ['brief_schema','source_identity','requirement_coverage']
    error=None
    try:
        if name=='intent.compiler':check_intent(outputs['intent'],inputs['request'],ctx.store,ctx.observation)
        else:check_brief(outputs['brief'],inputs['intent'],inputs['intake'],ctx.store,intent_ref=ctx.input_ref('intent'),intake_ref=ctx.input_ref('intake'),policy=inputs['defaults'],policy_ref=ctx.input_ref('defaults'))
    except Exception as exc:
        error=exc
    return [{'check_id':key,'outcome':'FAIL' if error else 'PASS','reason':str(error) if error else 'Exact compiler structure/source/coverage invariant satisfied',
             'evidence_refs':list(ctx.output_refs.values())+list(ctx.contract['input_refs'])} for key in ids]
