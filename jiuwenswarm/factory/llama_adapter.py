"""Pinned llama-server Spark binding for existing Builder/Lab and Friday controller."""
import hashlib
import json
import math
from pathlib import Path
import re
from .engine_adapters import sha, flag

ADAPTER='llama-server-v1'
DRIVER=Path(__file__).with_name('llama_http_driver.py')
ENV={'LLAMA_EXPERT_RESIDENCY','LLAMA_EXPERT_STREAMING','LLAMA_EXPERT_CHECKPOINT','LLAMA_EXPERT_PHYSICAL_BYTES',
     'LLAMA_EXPERT_FIXED_BYTES','LLAMA_EXPERT_SEQUENCE_BYTES','LLAMA_EXPERT_WORKSPACE_BYTES','LLAMA_EXPERT_HEADROOM_BYTES',
     'LLAMA_EXPERT_SLOT_BYTES','LLAMA_EXPERT_IO_BYTES','LLAMA_EXPERT_FALLBACK_BYTES','LLAMA_EXPERT_WARM_SET'}


def validate_contract(c):
    if c.get('adapter')!=ADAPTER or c.get('version')!=1 or c.get('target')!='spark-gb10' or c.get('tolerance')!='canonical-token-ids-and-finish':raise ValueError('Invalid llama contract')
    w=c['workload'];args=w['argv'];limits=c['limits']
    if not isinstance(args,list) or not all(isinstance(v,str) and v and '\0' not in v for v in args):raise ValueError('Invalid fixed llama arguments')
    args=args[:-1] if args[-1:]==['--no-warmup'] else args
    if len(args)%2:raise ValueError('Invalid argument pairs')
    allowed={'-m','--shard','--load-mode','--lazy-mode','--override-tensor','--ctx-size','--gpu-layers','--threads','--threads-batch','--parallel','--batch-size','--ubatch-size'}
    if len(set(args[::2]))!=len(args[::2]) or set(args[::2])-allowed:raise ValueError('Unsupported llama arguments')
    for k,v in {'--load-mode':'mmap','--lazy-mode':'on','--parallel':'1'}.items():
        if flag(args,k)!=v:raise ValueError('Required llama argument differs: '+k)
    if flag(args,'-m')!=w['pack']:raise ValueError('Primary shard differs')
    if not 128<=int(flag(args,'--ctx-size'))<=8192:raise ValueError('Context bound')
    for k in ('--threads','--threads-batch'):
        if not 1<=int(flag(args,k))<=limits['cpus']:raise ValueError('Thread bound')
    if not isinstance(w['environment'],dict) or set(w['environment'])-ENV or any(not isinstance(v,str) or '\0' in v or '\n' in v for v in w['environment'].values()):raise ValueError('Invalid expert environment')
    if [w['environment'].get(k,'0') for k in ('LLAMA_EXPERT_RESIDENCY','LLAMA_EXPERT_STREAMING')] not in (['0','0'],['1','1']):raise ValueError('Mixed feature switches')
    cases=w['requests']
    if not isinstance(cases,list) or not 1<=len(cases)<=4:raise ValueError('Bounded requests required')
    for case in cases:
        if set(case)!={'prompt','max_new_tokens'} or not isinstance(case['prompt'],str) or not 1<=len(case['prompt'])<=32768 or type(case['max_new_tokens']) is not int or not 1<=case['max_new_tokens']<=64:raise ValueError('Invalid request bound')
    if any(type(limits[k]) is not int for k in ('timeout_s','guard_gib','memory_bytes','cpus')):raise ValueError('Integer limits required')
    if not (30<=limits['timeout_s']<=900 and 8<=limits['guard_gib']<=32 and 1<=limits['memory_bytes']<=104*2**30 and 1<=limits['cpus']<=8):raise ValueError('Unsafe llama bounds')
    if not re.fullmatch('[a-f0-9]{64}',c['assets']['identity_sha256']):raise ValueError('Asset manifest digest required')
    return c


def inspect_assets(c):
    from .ccs.performance_baseline.model_layout import inspect_gguf
    asset=c['assets'];p=Path(asset['identity_path'])
    if sha(p)!=asset['identity_sha256']:raise ValueError('Asset identity manifest changed')
    manifest=json.loads(p.read_text());result=[]
    for f in manifest['files']:
        p=Path(f['path']);st=p.stat()
        if st.st_size!=f['size']:raise ValueError('Asset size changed')
        header=inspect_gguf(p,expected_header_sha256=f['header_sha256'])
        result.append(dict(path=str(p),size=st.st_size,mtime_ns=st.st_mtime_ns,header_sha256=f['header_sha256'],retained_sha256=f['retained_sha256'],full_hash_rechecked=False))
    paths={r['path'] for r in result}
    if c['workload']['pack'] not in paths or flag(c['workload']['argv'],'--shard') not in paths:raise ValueError('Unadmitted model shard')
    return result


def command(root,c):
    from .contract import atomic_json
    p=root/'http-input.json';atomic_json(p,c)
    driver=root/'llama-http-driver.py';driver.write_bytes(DRIVER.read_bytes())
    return ['/usr/bin/python3',str(driver),str(p)],[(c['workload']['model_root'],c['workload']['model_root']),(str(driver),str(driver)),(str(p),str(p))]


def parse_protocol(stdout,stderr,c):
    records=[json.loads(line) for line in stdout.splitlines() if line.strip()]
    launches=[r for r in records if r.get('event')=='launch'];ready=[r for r in records if r.get('event')=='ready']
    if len(launches)!=1 or launches[0]['argv']!=['/opt/llamacpp/llama-server',*c['workload']['argv'],'--host','127.0.0.1','--port','18080'] or not re.fullmatch('[a-f0-9]{64}',launches[0]['executable_sha256']):raise ValueError('Binary/argv proof missing')
    if len(ready)!=1 or ready[0]['status']!=200 or json.loads(ready[0]['body']).get('status')!='ok':raise ValueError('Ready endpoint proof missing')
    rows=[]
    for i,case in enumerate(c['workload']['requests']):
        request=[r for r in records if r.get('event')=='request' and r['index']==i]
        ends=[r for r in records if r.get('event')=='request_end' and r['index']==i]
        stream=[r for r in records if r.get('event')=='sse' and r['index']==i and r['raw']!='[DONE]']
        if len(request)!=1 or len(ends)!=1 or not stream:raise ValueError('Incomplete HTTP evidence')
        body=request[0]['body'];ids=body['prompt']
        if not ids or len(ids)>2048 or any(type(v) is not int or v<0 for v in ids):raise ValueError('Invalid input IDs')
        if body!=dict(prompt=ids,n_predict=case['max_new_tokens'],temperature=0,seed=0,stream=True,return_tokens=True,cache_prompt=False):raise ValueError('Changed request policy')
        tokens=[];text='';first=None;last=None;final=None;previous=0
        for r in stream:
            if type(r['elapsed_ns']) is not int or r['elapsed_ns']<previous:raise ValueError('Invalid client clock sequence')
            previous=r['elapsed_ns'];v=json.loads(r['raw'])
            if final is not None:raise ValueError('SSE after final')
            ts=v.get('tokens',[])
            if not isinstance(ts,list) or any(type(t) is not int or t<0 for t in ts):raise ValueError('Invalid output IDs')
            tokens+=ts;text+=v.get('content','')
            if ts:
                if first is None:first=r['elapsed_ns']
                last=r['elapsed_ns']
            if v.get('stop') is True:final=v
        if not final or not tokens or len(tokens)>case['max_new_tokens'] or final.get('stop_type') not in ('limit','eos','word'):raise ValueError('Missing bounded output or stop reason')
        if final.get('truncated'):raise ValueError('Truncated input')
        if len(tokens)!=final.get('tokens_predicted'):raise ValueError('Output token count differs from final SSE')
        if ends[0]['elapsed_ns']<previous:raise ValueError('Invalid completion clock')
        canonical=json.dumps([ids,tokens,final['stop_type'],final.get('stopping_word','')],separators=(',',':'))
        rows.append(dict(input_ids=ids,output_ids=tokens,content=text,stop_type=final['stop_type'],canonical_sha256=hashlib.sha256(canonical.encode()).hexdigest(),client_ttft_ms=first/1e6,client_completion_ms=ends[0]['elapsed_ns']/1e6,client_decode_tps=(len(tokens)-1)*1e9/(last-first) if len(tokens)>1 and last>first else None,native_timings=final.get('timings',{}),generated_tokens=len(tokens),native_decode_tps=final.get('timings',{}).get('predicted_per_second'),decode_ms=final.get('timings',{}).get('predicted_ms'),prefill_ms=final.get('timings',{}).get('prompt_ms')))
    on=c['workload']['environment'].get('LLAMA_EXPERT_STREAMING')=='1'
    if on and (not re.search(r'expert_weights registered_tensors=\d+',stderr) or not re.search(r'expert_weights effective slots=',stderr)):raise ValueError('Candidate activation missing')
    counters=[dict((k,int(v)) for k,v in re.findall(r'(\w+)=(\d+)',line)) for line in stderr.splitlines() if 'expert_weights final ' in line]
    if on and (not counters or sum(x.get('fills',0) for x in counters)==0 or any(x.get('failures') or x.get('leases') or x.get('outstanding') for x in counters)):raise ValueError('Successful engagement/retirement missing')
    return dict(requests=rows,repeat_equal=len(rows)>1 and all(r['canonical_sha256']==rows[0]['canonical_sha256'] for r in rows),executable_sha256=launches[0]['executable_sha256'],engagement=dict(enabled=on,counters=counters),semantic_accuracy='not_tested',scored_ab_improvement='not_established')


def verify_cell_evidence(content,request):
    from .lab_recorder import GATE,verify_boundary
    c=request['contract'];limits=c['limits']
    def read(n):return json.loads(content['cell/'+n])
    intent=read('intent.json');created=read('inspect-created.json');final=read('inspect-final.json')
    if intent['image']!=request['admission']['image']['id']:raise ValueError('Image differs')
    verify_boundary(created,intent,memory_bytes=limits['memory_bytes'],cpus=limits['cpus'],environment=c['workload']['environment'])
    config_path=str(Path(intent['output']).parent/'http-input.json')
    if created['Config']['Cmd']!=['-c',GATE,'/usr/bin/python3',str(Path(intent['output']).parent/'llama-http-driver.py'),config_path]:raise ValueError('Driver identity differs')
    if hashlib.sha256(content['llama-http-driver.py']).hexdigest()!=request['execution_sha256']['llama_http_driver.py']:raise ValueError('Driver source changed')
    if json.loads(content['http-input.json'])!=c:raise ValueError('Driver input differs')
    if created['Id']!=final['Id'] or final['State']['Running'] or final['State']['Pid'] or final['State']['ExitCode'] or final['State']['OOMKilled']:raise ValueError('Final container state invalid')
    expected_mounts={(str(Path(c['workload']['model_root']).resolve()),c['workload']['model_root']),(config_path,config_path),(str(Path(config_path).with_name('llama-http-driver.py')),str(Path(config_path).with_name('llama-http-driver.py')))}
    if {(m['Source'],m['Destination']) for m in created['Mounts'] if m['Type']=='bind'}!=expected_mounts:raise ValueError('Unexpected mounts')
    devices=created['HostConfig'].get('DeviceRequests') or []
    if len(devices)!=1 or devices[0].get('Driver')!='cdi' or devices[0].get('DeviceIDs')!=['nvidia.com/gpu=0']:raise ValueError('GPU admission differs')
    if content['cell/stdin-wire.log']!=b'FACTORY_EXEC\n':raise ValueError('Unexpected stdin')
    offsets=dict(stdin=0,stdout=0,stderr=0)
    for i,line in enumerate(content['cell/pipe-events.jsonl'].splitlines()):
        v=json.loads(line);s=v['stream']
        if v['sequence']!=i or v['offset']!=offsets[s] or v['truncated']:raise ValueError('Pipe coverage invalid')
        offsets[s]+=v['retained_bytes']
    for s,n in [('stdin','stdin-wire.log'),('stdout','stdout.log'),('stderr','stderr.log')]:
        if offsets[s]!=len(content['cell/'+n]):raise ValueError('Pipe length mismatch')
    samples=[json.loads(x) for x in content['cell/samples.jsonl'].splitlines()]
    if not samples or any(s['available_bytes']<limits['guard_gib']*2**30 or any(s['memory_events'].get(k,0) for k in ('oom','oom_kill','oom_group_kill')) for s in samples):raise ValueError('Memory guard violated')
    return dict(boundary_verified=True,replay_verified=True,telemetry_samples=len(samples))
