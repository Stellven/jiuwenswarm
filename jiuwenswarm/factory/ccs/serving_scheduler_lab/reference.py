"""Bounded discrete token scheduler; times are estimates, not hardware measurements."""

def number(v,name,lo=0,hi=100000):
    if type(v) is not int or not lo<=v<=hi: raise ValueError(name+' outside bounded integer range')
    return v

def schedule(spec):
    budget=number(spec['token_budget'],'token_budget',1,4096)
    chunk=number(spec['prefill_chunk'],'prefill_chunk',1,4096)
    slots=number(spec.get('max_active',16),'max_active',1,256)
    max_steps=number(spec.get('max_steps',10000),'max_steps',1,100000)
    reserve=number(spec.get('prefill_reserve',1),'prefill_reserve',0,budget)
    requests=spec['requests']
    if not isinstance(requests,list) or len(requests)>256: raise ValueError('requests must be list <=256')
    pending=[]; seen=set()
    for r in requests:
        rid=r['id']
        if not isinstance(rid,str) or not rid or rid in seen: raise ValueError('unique nonempty request IDs required')
        seen.add(rid)
        p=number(r['prompt_tokens'],'prompt_tokens',1); d=number(r['decode_tokens'],'decode_tokens')
        pending.append(dict(id=rid,arrival=number(r.get('arrival',0),'arrival'),prompt=p,decode=d,prefilled=0,decoded=0))
    pending.sort(key=lambda r:r['arrival']); active=[]; done=[]; trace=[]
    prefill_cursor=0; decode_cursor=0
    for tick in range(max_steps):
        while pending and pending[0]['arrival']<=tick and len(active)<slots:
            r=pending.pop(0); r['admitted']=tick; active.append(r)
        if not active and not pending: break
        prefills=[r for r in active if r['prefilled']<r['prompt']]
        decodes=[r for r in active if r['prefilled']==r['prompt'] and r['decoded']<r['decode']]
        allocations=[]; remaining=budget
        # Reserve prefill work so a sustained decode population cannot starve new prompts.
        decode_limit=budget-min(reserve,budget) if prefills else budget
        if decodes:
            start=decode_cursor%len(decodes)
            for r in (decodes[start:]+decodes[:start])[:decode_limit]:
                r['decoded']+=1; remaining-=1
                r.setdefault('first_token',tick)
                allocations.append(dict(id=r['id'],phase='decode',tokens=1))
            decode_cursor+=max(1,min(len(decodes),decode_limit))
        if prefills and remaining:
            start=prefill_cursor%len(prefills)
            for r in prefills[start:]+prefills[:start]:
                if not remaining: break
                n=min(chunk,remaining,r['prompt']-r['prefilled'])
                r['prefilled']+=n; remaining-=n
                allocations.append(dict(id=r['id'],phase='prefill',tokens=n))
            prefill_cursor+=1
        trace.append(dict(tick=tick,allocations=allocations,tokens=budget-remaining,active=len(active)))
        for r in list(active):
            if r['prefilled']==r['prompt'] and r['decoded']==r['decode']:
                r['finished']=tick; done.append(r); active.remove(r)
    unfinished=[r['id'] for r in active+pending]
    return {'trace':trace,'completed':done,'unfinished':unfinished,'complete':not unfinished,
            'steps':len(trace),'scope':'CPU schedule reference; each decode token retains full checkpoint routing',
            'timing_measured':False,'admission':'FIFO arrival, bounded active slots, bounded token budget',
            'fairness':'round robin within decode and prefill; nonzero prefill reserve required for continuous-arrival starvation bound'}

def analyze(spec):
    trace=spec['trace']; budget=number(spec['token_budget'],'token_budget',1,4096)
    if not isinstance(trace,list) or len(trace)>100000: raise ValueError('trace too long')
    cost_p=spec.get('prefill_ms_per_token',1); cost_d=spec.get('decode_ms_per_token',1)
    for v in (cost_p,cost_d):
        if type(v) not in (int,float) or not 0<=v<=1000000: raise ValueError('cost must be finite bounded nonnegative number')
    total=0; prefill=decode=0; timeline=[]
    for row in trace:
        p=d=0
        for a in row['allocations']:
            n=number(a['tokens'],'tokens',1,4096)
            if a['phase']=='prefill': p+=n
            elif a['phase']=='decode': d+=n
            else: raise ValueError('unknown phase')
        if p+d>budget or row['tokens']!=p+d: raise ValueError('token budget/trace accounting violation')
        elapsed=p*cost_p+d*cost_d
        timeline.append({'tick':row['tick'],'start_ms':total,'end_ms':total+elapsed})
        total+=elapsed; prefill+=p; decode+=d
    return {'prefill_tokens':prefill,'decode_tokens':decode,'estimated_ms':total,'timeline':timeline,
            'utilization':(prefill+decode)/(len(trace)*budget) if trace else 0,
            'timing_measured':False,'assumption':'additive constant per-token service costs; no overlap, kernel, I/O or bandwidth model'}

def compare(spec):
    arms=spec['arms']
    if not isinstance(arms,list) or not 1<=len(arms)<=8: raise ValueError('1..8 arms required')
    results=[]
    for arm in arms:
        if not isinstance(arm,dict) or set(arm)-{'token_budget','prefill_chunk','max_active','max_steps','prefill_reserve'}: raise ValueError('arms can vary scheduler parameters only')
        config=dict(spec['workload']); config.update(arm)
        result=schedule(config)
        results.append({'configuration':arm,'schedule':result,'analysis':analyze(dict(trace=result['trace'],token_budget=config['token_budget'],**spec.get('costs',{})))})
    return {'arms':results,'comparable_workload':True,'performance_claim':False}
