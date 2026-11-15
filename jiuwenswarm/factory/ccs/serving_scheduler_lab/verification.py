"""Package-attached bounded scheduling invariants."""
import reference as r

def verify():
    requests=[dict(id=str(i),prompt_tokens=20+i,decode_tokens=7,arrival=i%3) for i in range(12)]
    spec=dict(requests=requests,token_budget=3,prefill_chunk=2,max_active=4,prefill_reserve=1,max_steps=1000)
    s=r.schedule(spec)
    assert s['complete'] and len(s['completed'])==12
    assert all(x['tokens']<=3 and x['active']<=4 for x in s['trace'])
    assert all(x['prefilled']==x['prompt'] and x['decoded']==7 for x in s['completed'])
    assert all(x['finished']>=x['admitted']>=x['arrival'] for x in s['completed'])
    a=r.analyze(dict(trace=s['trace'],token_budget=3))
    assert a['prefill_tokens']==sum(x['prompt_tokens'] for x in requests) and a['decode_tokens']==84
    # Four ready decodes compete for one decode slot; rotation must serve each.
    s=r.schedule(dict(requests=[dict(id=str(i),prompt_tokens=1,decode_tokens=3) for i in range(4)],token_budget=1,prefill_chunk=1,max_active=4,prefill_reserve=0,max_steps=100))
    assert s['complete'] and {a['id'] for row in s['trace'] for a in row['allocations'] if a['phase']=='decode'}==set('0123')
    fair=r.schedule(dict(requests=[dict(id='decode',prompt_tokens=1,decode_tokens=30),dict(id='new',prompt_tokens=8,decode_tokens=1,arrival=3)],token_budget=2,prefill_chunk=1,max_active=2,prefill_reserve=1,max_steps=100))
    assert fair['complete']
    finished={x['id']:x['finished'] for x in fair['completed']}
    assert finished['new']<finished['decode']
    limited=r.schedule(dict(spec,max_steps=1));assert not limited['complete'] and limited['unfinished']
    return {'passed':True,'checks':['bounded-token-budget','bounded-admission','finite-request-completion','decode-rotation','prefill-reservation-progress','exact-token-accounting','bounded-step-truncation'],'scope':'CPU reference only','factory_qualification':False}
