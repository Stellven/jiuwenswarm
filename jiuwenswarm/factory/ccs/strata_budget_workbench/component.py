"""Fixed-budget profile transforms and native evidence checks, no execution."""
import copy
import re


def budget(value):
    if type(value) is not int or not 1024**3 <= value <= 128*1024**3:
        raise ValueError('Budget must be integer bytes between 1 and 128 GiB; native safe admission remains required')
    return value


def profile(value):
    if not isinstance(value, dict) or set(value) != {'args', 'environment'}:
        raise ValueError('Expected args/environment profile')
    args=value['args']
    if not isinstance(args, list) or len(args)>128 or any(not isinstance(x,str) or len(x)>4096 for x in args):
        raise ValueError('Invalid argument list')
    for flag,want in [('--experts','6'),('--dspark','none'),('--cpu-threads','8')]:
        if args.count(flag)!=1 or args.index(flag)+1>=len(args) or args[args.index(flag)+1]!=want:
            raise ValueError('Full-six static eight-worker profile required')
    if args.count('--no-expert-cache')!=1:
        raise ValueError('Static expert placement required')
    env=value['environment']
    if not isinstance(env,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in env.items()):
        raise ValueError('Environment must be string mapping')
    if env.get('DS4_AHEAD')!='0' or env.get('STRATA_DS4_REUSE')!='0':
        raise ValueError('Hold lookahead and prefix reuse disabled')
    if 'DS4_EXPERT_BUDGET_BYTES' in env:
        raw=env['DS4_EXPERT_BUDGET_BYTES']
        if not re.fullmatch('[1-9][0-9]*',raw):raise ValueError('Invalid fixed budget')
        budget(int(raw))
    return copy.deepcopy(value)


def apply(request):
    out=profile(request['profile']);size=budget(request['budget_bytes'])
    out['environment']['DS4_EXPERT_BUDGET_BYTES']=str(size)
    return dict(profile=out, changed_field='environment.DS4_EXPERT_BUDGET_BYTES',
                safe_runtime_admission_required=True, admission_granted=False,
                scope='Profile construction only; requires a qualified fixed-budget engine image')


def verify_startup(request):
    text=request['stderr'];want=budget(request['budget_bytes'])
    if not isinstance(text,str) or len(text)>2*1024*1024:raise ValueError('Bounded native stderr required')
    budgets=re.findall(r'^ds4: fixed expert budget requested=(\d+) effective=(\d+) safe=(\d+) bytes$',text,re.M)
    layers=re.findall(r'^ds4: fixed placement layer=(\d+) experts=(\d+) resident=(\d+) fnv1a64=([a-f0-9]{16})$',text,re.M)
    aggregate=re.findall(r'^ds4: fixed placement layers=(\d+) fnv1a64=([a-f0-9]{16})$',text,re.M)
    for prefix, rows in [('ds4: fixed expert budget ',budgets),
                         ('ds4: fixed placement layer=',layers),
                         ('ds4: fixed placement layers=',aggregate)]:
        if sum(line.startswith(prefix) for line in text.splitlines()) != len(rows):
            raise ValueError('Malformed native placement evidence')
    if len(budgets)!=1 or tuple(map(int,budgets[0][:2]))!=(want,want) or int(budgets[0][2])<want:
        raise ValueError('Fixed-budget safe admission missing or differs')
    if len(layers)!=40 or [int(v[0]) for v in layers]!=list(range(40)) or any(int(v[1])!=384 or not 0<=int(v[2])<=384 for v in layers):
        raise ValueError('Complete 40-layer placement required')
    if len(aggregate)!=1 or aggregate[0][0]!='40':raise ValueError('Aggregate placement missing')
    h=14695981039346656037
    for row in layers:
        for byte in int(row[3],16).to_bytes(8,'little'):h=((h^byte)*1099511628211)&((1<<64)-1)
    if f'{h:016x}'!=aggregate[0][1]:raise ValueError('Placement aggregate differs')
    return dict(requested_budget_bytes=want,effective_budget_bytes=want,safe_budget_bytes=int(budgets[0][2]),
                resident_experts=sum(int(v[2]) for v in layers),layers=layers,aggregate=aggregate[0],
                numerical_equivalence_established=False)


def summarize_memory(request):
    samples=request['samples']
    if not isinstance(samples,list) or not 1<=len(samples)<=10000:raise ValueError('Bounded nonempty samples required')
    if any(not isinstance(sample,dict) for sample in samples):raise ValueError('Memory samples must be objects')
    def maximum(key):
        values=[s[key] for s in samples if s.get(key) is not None]
        if any(type(x) is not int or x<0 for x in values):raise ValueError('Memory bytes must be nonnegative integers')
        return max(values) if values else None
    available=[s['available_bytes'] for s in samples if s.get('available_bytes') is not None]
    if any(type(x) is not int or x<0 for x in available):raise ValueError('Invalid host available bytes')
    return dict(cgroup_kernel_peak_bytes=maximum('cgroup_peak'),cgroup_sampled_max_bytes=maximum('cgroup_current'),
                host_sampled_min_available_bytes=min(available) if available else None,
                scope='Cgroup accounting and host estimates are separate, not additive GPU/system memory totals',
                exact_gpu_peak_measured=False,samples=len(samples))


TOOLS=dict(apply=apply,verify_startup=verify_startup,summarize_memory=summarize_memory)
