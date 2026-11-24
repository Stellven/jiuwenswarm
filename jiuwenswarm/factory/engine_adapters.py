"""Versioned Strata protocol and fixed experiment contract; no launch authority."""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path

STRATA = 'strata-v1'
ENV_KEYS = {'DS4_ASYNC_T','DS4_UMA_HEADROOM_GIB','DS4_STORE_GB','DS4_COPY_ALL',
            'DS4_EXPERT_BUDGET_BYTES','DS4_AHEAD','DS4_ENGRAM_THREADS','DS4_ENGRAM_CACHE_MB','STRATA_DS4_REUSE'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def flag(argv, name):
    if argv.count(name) != 1 or argv.index(name)+1 >= len(argv):
        raise ValueError('Exactly one value required for '+name)
    return argv[argv.index(name)+1]


def validate_contract(contract):
    if contract.get('adapter') != STRATA or contract.get('version') != 1:
        raise ValueError('Unsupported Strata contract')
    if contract.get('tolerance') != 'canonical-token-ids-and-finish':
        raise ValueError('Strata requires canonical token identity contract')
    if contract.get('target') != 'spark-gb10':
        raise ValueError('Strata contract target mismatch')
    work = contract['workload']; argv = work['argv']
    if not isinstance(argv,list) or not all(isinstance(v,str) and v and '\0' not in v for v in argv):
        raise ValueError('Invalid fixed engine argv')
    if flag(argv,'--experts') != '6' or flag(argv,'--mmap-experts') != 'on':
        raise ValueError('Full six mapped experts required')
    if any(v in argv for v in ('--serve','--profile','--profile-readonly')):
        raise ValueError('Serve/profile control belongs to host adapter')
    if flag(argv,'--dspark') not in {'none','off','on','auto'}:
        raise ValueError('Invalid draft policy')
    env=work['environment']
    if not isinstance(env,dict) or set(env)-ENV_KEYS or any(not isinstance(v,str) or '\0' in v or '\n' in v for v in env.values()):
        raise ValueError('Unsupported engine environment')
    if env.get('STRATA_DS4_REUSE')!='0':
        raise ValueError('Prefix reuse must be explicitly disabled')
    cases=work['requests']
    if not isinstance(cases,list) or not 1<=len(cases)<=2:
        raise ValueError('One or two requests per cell required')
    for case in cases:
        if (type(case.get('max_new_tokens')) is not int or not 1<=case['max_new_tokens']<=128
            or not isinstance(case.get('ids'),list) or not case['ids']
            or any(type(v) is not int or v<0 for v in case['ids'])):
            raise ValueError('Invalid tokenized workload')
    limits=contract['limits']
    if (limits.get('cpus')!=8 or limits.get('memory_bytes')!=104*2**30 or limits.get('extra_swap_bytes')!=0
        or limits.get('guard_gib')!=8 or type(limits.get('timeout_s')) is not int or not 1<=limits['timeout_s']<=900):
        raise ValueError('Unsupported Spark resource boundary')
    asset=contract['assets']
    if not re.fullmatch('[a-f0-9]{64}',asset['identity_sha256']):
        raise ValueError('Pinned asset identity required')
    if not Path(asset['identity_path']).is_absolute():
        raise ValueError('Absolute asset identity path required')
    return contract


def protocol(contract):
    validate_contract(contract)
    no_draft=flag(contract['workload']['argv'],'--dspark') in {'none','off'}
    return (''.join('GEN '+str(case['max_new_tokens'])+' temperature=0 top_p=1 top_k=1 min_p=0 seed=42 '
        +('spec=0 ' if no_draft else '')+','.join(map(str,case['ids']))+'\n'
        for case in contract['workload']['requests'])+'QUIT\n').encode()


def inspect_assets(contract):
    """Check the sealed full-asset inventory without re-reading weights every cell."""
    validate_contract(contract)
    asset=contract['assets']; path=Path(asset['identity_path'])
    if sha(path)!=asset['identity_sha256']:
        raise ValueError('Asset identity changed')
    inventory=json.loads(path.read_text())
    checks=[]
    for row in inventory['files']:
        stat=Path(row['path']).stat()
        if any(getattr(stat,k)!=row[k] for k in ('st_size','st_mtime_ns','st_ctime_ns')):
            raise ValueError('Model identity metadata changed: '+row['path'])
        if not re.fullmatch('[a-f0-9]{64}',row['sha256']):
            raise ValueError('Full asset hash missing')
        checks.append(dict(path=row['path'],bytes=stat.st_size,sha256=row['sha256']))
    if not checks:
        raise ValueError('Empty model inventory')
    for name,want in inventory.get('pack_files',{}).items():
        if sha(name)!=want:raise ValueError('Pack/tokenizer input changed: '+name)
    return dict(files=checks,total_bytes=sum(v['bytes'] for v in checks),
        identity_sha256=asset['identity_sha256'],verification='Full hashes at intake; stat identity and pack hashes checked per cell')


def parse_protocol(stdout, stderr, contract):
    """Derive native rates and canonical output only from raw retained records."""
    if re.search(r'terminate called|Segmentation fault', stderr):
        raise ValueError('Fatal engine stderr invalidates the run')
    cases=contract['workload']['requests']; rows=[]; ids=[]; ready=False
    for line in stdout.splitlines():
        parts=line.split()
        if not parts:continue
        if parts[0]=='ERR':raise ValueError('Engine protocol error: '+line[:200])
        if parts[0]=='READY':
            if ready:raise ValueError('Duplicate READY')
            ready=True
        elif parts[0]=='T':
            if not ready or len(parts)!=2:raise ValueError('Invalid token framing')
            token=int(parts[1])
            if token<0:raise ValueError('Invalid token id')
            ids.append(token)
            if len(rows)>=len(cases) or len(ids)>cases[len(rows)]['max_new_tokens']:
                raise ValueError('Generated token cap exceeded')
        elif parts[0]=='DONE':
            if len(parts)!=11 or len(rows)>=len(cases):raise ValueError('Invalid DONE framing')
            count,prompt=int(parts[1]),int(parts[2]);prefill,decode=float(parts[3]),float(parts[4])
            finish=parts[5];accepted,offered=int(parts[6]),int(parts[7])
            case=cases[len(rows)]
            if (not ids or count!=len(ids) or prompt!=len(case['ids']) or finish not in {'stop','length'}
                or not all(math.isfinite(v) and v>0 for v in (prefill,decode))
                or not 0<=accepted<=offered or parts[-1]!='0'):
                raise ValueError('Inconsistent DONE evidence or prefix reuse')
            canonical=json.dumps(dict(ids=ids,finish=finish),sort_keys=True,separators=(',',':')).encode()
            rows.append(dict(generated_tokens=count,prompt_tokens=prompt,prefill_ms=prefill,decode_ms=decode,
                decode_ms_per_token=decode/count,decode_tps=count*1000/decode,prefill_tps=prompt*1000/prefill,
                accepted_drafts=accepted,offered_drafts=offered,finish=finish,finish_reason=finish,ids=ids,
                prompt_sha256=hashlib.sha256(json.dumps(case['ids'],separators=(',',':')).encode()).hexdigest(),
                canonical_sha256=hashlib.sha256(canonical).hexdigest()))
            ids=[]
    if not ready or ids or len(rows)!=len(cases):raise ValueError('Incomplete native protocol')
    effective=re.findall(r'experts per word:\s*(\d+)',stderr)
    if not effective or any(v!='6' for v in effective):raise ValueError('Full-six expert engagement missing')
    if flag(contract['workload']['argv'],'--dspark')=='none' and any(r['offered_drafts'] for r in rows):
        raise ValueError('Unexpected draft engagement')
    return dict(requests=rows,effective_experts=6,raw_stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
        raw_stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest(),
        repeat_equal=rows[0]['canonical_sha256']==rows[-1]['canonical_sha256'] if len(rows)>1 else None,
        semantic_accuracy='not_tested',scored_ab_improvement='not_established')


def verify_cell_evidence(content, request):
    """Independently validate the retained boundary, replay and telemetry for a success."""
    from .lab_recorder import GATE, verify_boundary
    contract=request['contract'];work=contract['workload'];limits=contract['limits']
    def read(name):return json.loads(content['cell/'+name])
    intent=read('intent.json');created=read('inspect-created.json');final=read('inspect-final.json')
    if intent['image']!=request['admission']['image']['id']:
        raise ValueError('Collector intent image differs from admission')
    from .strata_lab import execution_environment
    verify_boundary(created,intent,memory_bytes=limits['memory_bytes'],cpus=limits['cpus'],environment=execution_environment(request))
    expected=['-c',GATE,'/opt/strata/strata-dsv41',*work['argv'],'--profile-readonly','--serve']
    if created['Config']['Cmd']!=expected or created['Config']['Entrypoint']!=['/usr/bin/python3']:
        raise ValueError('Actual engine argv differs from fixed contract')
    if (created['Id']!=final['Id'] or final['Image']!=created['Image']
        or final['State']['Running'] or final['State']['Pid']!=0
        or final['State']['ExitCode']!=0 or final['State']['OOMKilled']):
        raise ValueError('Final container identity/state invalid')
    expected_mounts={(str(Path(work[k]).resolve()),str(work[k])) for k in ('pack','model_root')}
    actual_mounts={(m['Source'],m['Destination']) for m in created.get('Mounts',[]) if m['Type']=='bind'}
    if actual_mounts!=expected_mounts:raise ValueError('Model/pack mounts differ from contract')
    devices = created['HostConfig'].get('DeviceRequests') or []
    if len(devices)!=1 or devices[0].get('Driver')!='cdi' or devices[0].get('DeviceIDs')!=['nvidia.com/gpu=0']:
        raise ValueError('Exact GPU device admission missing')
    if content['cell/stdin-wire.log']!=b'FACTORY_EXEC\n'+protocol(contract):
        raise ValueError('Actual replay differs from tokenized workload')
    offsets=dict(stdin=0,stdout=0,stderr=0)
    for i,line in enumerate(content['cell/pipe-events.jsonl'].splitlines()):
        event=json.loads(line);stream=event['stream']
        if event['sequence']!=i or event['offset']!=offsets[stream] or event['truncated']:
            raise ValueError('Pipe sequence, coverage or truncation invalid')
        offsets[stream]+=event['retained_bytes']
    for stream,name in [('stdin','stdin-wire.log'),('stdout','stdout.log'),('stderr','stderr.log')]:
        if offsets[stream]!=len(content['cell/'+name]):raise ValueError('Raw stream byte coverage differs')
    samples=[json.loads(line) for line in content['cell/samples.jsonl'].splitlines()]
    if not samples or any(s['available_bytes']<limits['guard_gib']*2**30 for s in samples):
        raise ValueError('Missing telemetry or host guard violated')
    if any(any(s['memory_events'].get(k,0) for k in ('oom','oom_kill','oom_group_kill')) for s in samples):
        raise ValueError('OOM evidence invalidates measurement')
    return dict(boundary_verified=True,replay_verified=True,telemetry_samples=len(samples))
