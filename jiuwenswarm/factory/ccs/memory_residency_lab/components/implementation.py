"""Half-open liveness intervals; first-fit arena; no claimed optimality."""
from pathlib import Path
import json,subprocess,platform

def integer(x,lo,hi):
    if type(x) is not int or not lo<=x<=hi: raise ValueError('integer outside allowed bounds')
    return x

def normalize(d):
    if not isinstance(d,dict): raise ValueError('request must be object')
    align=integer(d.get('alignment',64),1,4096)
    if align&(align-1): raise ValueError('alignment must be power of two')
    tensors=d.get('tensors')
    if not isinstance(tensors,list) or not 1<=len(tensors)<=128: raise ValueError('1..128 tensors required')
    names=set();out=[]
    for t in tensors:
        name=t.get('name')
        if not isinstance(name,str) or not name or len(name)>64 or name in names: raise ValueError('unique tensor names required')
        names.add(name)
        size=integer(t.get('bytes'),1,64*1024*1024);start=integer(t.get('start'),0,1000000);end=integer(t.get('end'),1,1000001)
        if end<=start: raise ValueError('end must exceed start')
        out.append(dict(name=name,bytes=size,start=start,end=end))
    if sum(t['bytes'] for t in out)>256*1024*1024: raise ValueError('aggregate input exceeds 256 MiB')
    return align,out

def clash(a,b): return a['start']<b['end'] and b['start']<a['end']
def plan(d):
    align,tensors=normalize(d);placed=[]
    for t in sorted(tensors,key=lambda t:(-t['bytes'],t['start'],t['name'])):
        candidate=0
        conflicts=sorted([p for p in placed if clash(p,t)],key=lambda p:p['offset'])
        for p in conflicts:
            if candidate+t['bytes']<=p['offset']: break
            candidate=max(candidate,((p['offset']+p['bytes']+align-1)//align)*align)
        placed.append(dict(t,offset=candidate))
    peak=max(t['offset']+t['bytes'] for t in placed)
    naive=sum(((t['bytes']+align-1)//align)*align for t in tensors)
    lower=max(sum(t['bytes'] for t in tensors if t['start']<=s<t['end']) for s in {t['start'] for t in tensors})
    return {'alignment':align,'allocations':sorted(placed,key=lambda t:t['name']),'arena_bytes':peak,'independent_aligned_bytes':naive,'peak_live_payload_lower_bound':lower,'saved_bytes':naive-peak,'reduction_fraction':1-peak/naive,'interval_convention':'[start,end)','qualification':'static_plan_not_engine_rss'}

def verify(d):
    p=plan(d);a=p['allocations']
    for i,x in enumerate(a):
        for y in a[i+1:]:
            if clash(x,y) and x['offset']<y['offset']+y['bytes'] and y['offset']<x['offset']+x['bytes']: raise ValueError('live allocations alias')
    # Bytearray touches every allocated byte; native experiment is independent implementation.
    arena=bytearray(p['arena_bytes']);active={};checked=0
    for step in sorted({t[e] for t in a for e in ('start','end')}):
        for idx,t in list(active.items()):
            region=arena[t['offset']:t['offset']+t['bytes']]
            if region!=bytes([idx+1])*t['bytes']: raise ValueError('content corruption')
            checked+=len(region)
            if t['end']==step: del active[idx]
        for idx,t in enumerate(a):
            if t['start']==step:
                arena[t['offset']:t['offset']+t['bytes']]=bytes([idx+1])*t['bytes'];active[idx]=t
    return dict(p,correct=True,checked_bytes=checked,allocated_bytes=len(arena))

def native_experiment(d):
    p=plan(d);binary=Path(__file__).resolve().parents[1]/'native_arena'
    if not binary.is_file(): raise ValueError('native binary is not bundled; explicitly build native_arena.cpp on this host using METHOD.md')
    machine=platform.machine().lower();expected={'aarch64':183,'arm64':183,'x86_64':62,'amd64':62}.get(machine)
    header=binary.read_bytes()[:20]
    if len(header)<20 or header[:4]!=b'\x7fELF' or expected is None or int.from_bytes(header[18:20],'little' if header[5]==1 else 'big')!=expected:
        raise ValueError('native_arena binary architecture mismatch; rebuild bundled C++ source explicitly on this host')
    rows=[f"{t['bytes']} {t['start']} {t['end']} {t['offset']}" for t in p['allocations']]
    payload=f"{len(rows)} {p['arena_bytes']}\n"+'\n'.join(rows)+'\n'
    proc=subprocess.run([str(binary)],input=payload,text=True,capture_output=True,timeout=60,check=True)
    return dict(p,native=json.loads(proc.stdout),qualification='native_cpu_scratch_microexperiment_not_engine_rss')
