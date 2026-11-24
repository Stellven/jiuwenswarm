"""Scoped native prefill experiments, independent of benchmark v1/v2 policy."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
from statistics import median
import sys

from . import benchmark
from .contract import atomic_json
from .engine_adapters import sha
from .jobs import Jobs, metadata
from .store import NotFound, encoded
from .strata_prefill import apply

ADAPTER = 'strata-prefill-scoped-v1'
EXECUTION_FILES = ('prefill_workbench.py', 'prefill_worker.py', 'benchmark.py', 'benchmark_worker.py', 'benchmark_analysis.py',
    'benchmark_data.py', 'strata_prefill.py', 'strata_components.py', 'engine_adapters.py', 'strata_lab.py',
    'lab_recorder.py', 'lab_lifecycle.py', 'targets.py')
SCOPE = 'prefill_microbenchmark'


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def validate_contract(c):
    if (c.get('adapter') != ADAPTER or c.get('version') != 1 or type(c.get('version')) is not int or c.get('scope') != SCOPE or
        c.get('primary_metric') != 'median_native_prefill_ms' or
        c.get('tolerance') != 'deterministic-single-token-with-cross-arm-agreement'):
        raise ValueError('Unsupported scoped prefill contract')
    if c.get('stage') not in ('screen', 'confirm') or c['order'] != list('AB' if c['stage']=='screen' else 'ABBA'):
        raise ValueError('Stage requires frozen screen AB or confirm ABBA order')
    if c.get('target') != 'spark-gb10' or not re.fullmatch(r'sha256:[a-f0-9]{64}', c['image']['id']):
        raise ValueError('Pinned Spark image required')
    if (c.get('warmup_requests') != 4 or c.get('measured_requests') != 3 or c.get('max_new_tokens') != 1
        or type(c.get('max_new_tokens')) is not int or c.get('minimum_speedup') != 1.05):
        raise ValueError('Scoped workload and gate are fixed')
    if set(c['arms']) != {'A','B'} or set(c['workload']) != {'pack','model_root'}:
        raise ValueError('Exactly two arms and fixed model mounts required')
    a,b=c['arms']['A'],c['arms']['B']
    if b != apply(a,512)['profile']:
        raise ValueError('Only native prefill chunk 256 to 512 may differ')
    flags={'--pack':c['workload']['pack'],'--max-context':'8192','--eos':'1','--vision':'off',
        '--dspark':'none','--prefill-chunk':'256','--cpu-threads':'8','--vram-experts':'1.0',
        '--reserve-mib':'16384','--ssd-cache':'0','--mmap-experts':'on','--experts':'6','--dspark-conf':'0.65'}
    if (len(a['args']) != len(flags)*2+2 or a['args'].count('--verbose')!=1 or
        a['args'].count('--no-expert-cache')!=1 or
        any(benchmark.flag(a['args'],key)!=value for key,value in flags.items())):
        raise ValueError('Fixed native full-six static configuration required')
    ids=c['prompt']['ids']
    if (not isinstance(ids,list) or len(ids)!=512 or any(type(v)is not int or v<0 for v in ids)
        or c['prompt']['sha256'] != digest(ids)):
        raise ValueError('Pinned identical 512-token prompt required')
    files=c['prompt']['tokenizer_files']
    if (not isinstance(files,dict) or not 3<=len(files)<=16 or any(
        not isinstance(name,str) or '..' in Path(name).parts or
        not re.fullmatch('[a-f0-9]{64}',value) for name,value in files.items())):
        raise ValueError('Pinned tokenizer files required')
    if not {'vocab.json','token_type.json','tokenizer.json'}.issubset({Path(name).name for name in files}):
        raise ValueError('Frozen tokenizer tables missing')
    if c['limits'] != dict(cpus=8,memory_bytes=104*2**30,guard_gib=8,extra_swap_bytes=0,timeout_s=300):
        raise ValueError('Scoped resource limits changed')
    if type(c.get('campaign_timeout_s')) is not int or not 1<=c['campaign_timeout_s']<=1800:
        raise ValueError('Bounded campaign deadline required')
    if (set(c['execution_sha256']) != set(EXECUTION_FILES) or
        any(not re.fullmatch('[a-f0-9]{64}',v) for v in c['execution_sha256'].values())):
        raise ValueError('Complete scoped execution source closure required')
    return c


def design(base_contract, prompt_ids, tokenizer_files, stage='screen'):
    c={key:copy.deepcopy(base_contract[key]) for key in ('image','assets','workload','workspace_root')}
    a=copy.deepcopy(base_contract['arms']['A'])
    c.update(adapter=ADAPTER,version=1,scope=SCOPE,primary_metric='median_native_prefill_ms',
        tolerance='deterministic-single-token-with-cross-arm-agreement',target='spark-gb10',stage=stage,
        order=list('AB' if stage=='screen' else 'ABBA'),arms={'A':a,'B':apply(a,512)['profile']},
        warmup_requests=4,measured_requests=3,max_new_tokens=1,minimum_speedup=1.05,
        prompt=dict(ids=copy.deepcopy(prompt_ids),sha256=digest(prompt_ids),tokenizer_files=copy.deepcopy(tokenizer_files)),
        limits=dict(cpus=8,memory_bytes=104*2**30,guard_gib=8,extra_swap_bytes=0,timeout_s=300),
        campaign_timeout_s=900 if stage=='screen' else 1800,
        execution_sha256={name:sha(Path(__file__).with_name(name)) for name in EXECUTION_FILES})
    return validate_contract(c)


def verify_inputs(c):
    root=Path(c['workspace_root']).resolve()
    for name,want in c['prompt']['tokenizer_files'].items():
        path=(root/name).resolve()
        allowed=(root,Path(c['workload']['pack']).resolve()/'tokenizer')
        if not any(path.is_relative_to(folder) for folder in allowed) or sha(path)!=want:
            raise ValueError('Frozen tokenizer input changed')
    return benchmark.validate_assets(c)


def cases(c):
    return [dict(id=f'repeat-{i}',ids=c['prompt']['ids'],max_new_tokens=1) for i in range(7)]


def parse_native(stdout, stderr, c, arm):
    """One-token replay permits zero decode-loop time without inventing rates."""
    experts=re.findall(r'experts per word:\s*(\d+)',stderr)
    chunks=re.findall(r'prompts in chunks of (\d+)\)',stderr)
    expected=benchmark.flag(c['arms'][arm]['args'],'--prefill-chunk')
    if (not experts or any(v!='6' for v in experts) or not chunks or any(v!=expected for v in chunks)
        or re.search(r'terminate called|Segmentation fault',stderr)):
        raise ValueError('Missing full-six/effective chunk or fatal native evidence')
    rows=[]; ids=[];ready=False
    for line in stdout.splitlines():
        parts=line.split()
        if not parts:continue
        if parts[0]=='ERR':raise ValueError('Native protocol error')
        if parts[0]=='READY':
            if ready:raise ValueError('Duplicate READY')
            ready=True
        elif parts[0]=='T':
            if not ready or len(parts)!=2 or ids or len(rows)>=7:raise ValueError('Invalid single-token framing')
            token=int(parts[1])
            if token<0 or token==1:raise ValueError('Invalid token or EOS in fixed replay')
            ids=[token]
        elif parts[0]=='DONE':
            if len(parts)!=11 or not ids or len(rows)>=7:raise ValueError('Invalid DONE framing')
            pp,dt=float(parts[3]),float(parts[4])
            if (parts[1:3]!=['1','512'] or parts[5]!='length' or
                any(int(v)!=0 for v in parts[6:]) or not math.isfinite(pp) or pp<=0 or not math.isfinite(dt) or dt<0):
                raise ValueError('Invalid fixed replay timings, drafts, finish or prefix reuse')
            rows.append(dict(ids=ids,finish='length',prompt_tokens=512,generated_tokens=1,
                prefill_ms=pp,decode_ms=dt,accepted_drafts=0,offered_drafts=0,prefix_reused=0,
                canonical_sha256=digest(dict(ids=ids,finish='length'))))
            ids=[]
    if not ready or ids or len(rows)!=7:raise ValueError('Incomplete native replay')
    return dict(requests=rows,effective_experts=6,effective_prefill_chunk=int(expected))


def verify_cell(c,arm,path):
    from .lab_recorder import GATE, verify_boundary
    from .benchmark_worker import _successful
    read=lambda name:json.loads((path/name).read_text())
    report,intent,created,final=(read(name) for name in ('report.json','intent.json','inspect-created.json','inspect-final.json'))
    if not _successful(report) or intent['image']!=c['image']['id']:
        raise ValueError('Incomplete scoped cell or image mismatch')
    verify_boundary(created,intent,memory_bytes=c['limits']['memory_bytes'],cpus=8,environment=c['arms'][arm]['environment'])
    if (created['Config']['Cmd']!=['-c',GATE,*benchmark.phase_args(c,arm,'speed')]
        or created['Config']['Entrypoint']!=['/usr/bin/python3'] or created['Id']!=final['Id']
        or final['Image']!=c['image']['id'] or final['State']['Running'] or final['State']['Pid']!=0
        or final['State']['ExitCode']!=0 or final['State']['OOMKilled']):
        raise ValueError('Scoped engine boundary/exit differs')
    devices=created['HostConfig'].get('DeviceRequests') or []
    mounts={(m['Source'],m['Destination']) for m in created['Mounts'] if m['Type']=='bind'}
    if (len(devices)!=1 or devices[0].get('Driver')!='cdi' or devices[0].get('DeviceIDs')!=['nvidia.com/gpu=0']
        or mounts!={(str(Path(v).resolve()),str(v)) for v in c['workload'].values()}):
        raise ValueError('Scoped model/GPU mounts differ')
    if (path/'stdin-wire.log').read_bytes()!=b'FACTORY_EXEC\n'+benchmark.protocol(cases(c),arm,c):
        raise ValueError('Frozen input replay differs')
    offsets=dict(stdin=0,stdout=0,stderr=0)
    for i,line in enumerate((path/'pipe-events.jsonl').read_text().splitlines()):
        event=json.loads(line);stream=event['stream']
        if event['sequence']!=i or event['offset']!=offsets[stream] or event['truncated']:
            raise ValueError('Scoped raw pipe coverage invalid')
        offsets[stream]+=event['retained_bytes']
    for stream,name in [('stdin','stdin-wire.log'),('stdout','stdout.log'),('stderr','stderr.log')]:
        if offsets[stream]!=(path/name).stat().st_size:raise ValueError('Raw coverage differs')
    samples=[json.loads(line) for line in (path/'samples.jsonl').read_text().splitlines()]
    if not samples or any(s['available_bytes']<8*2**30 or any(s['memory_events'].get(k,0)
        for k in ('oom','oom_kill','oom_group_kill')) for s in samples):
        raise ValueError('Host guard or OOM invalidates scoped evidence')
    return parse_native((path/'stdout.log').read_text(),(path/'stderr.log').read_text(),c,arm)


def analyze(c,cells):
    validate_contract(c)
    if len(cells)!=len(c['order']) or [v['arm'] for v in cells]!=c['order']:
        raise ValueError('Complete frozen cell order required')
    identities=set(); medians={'A':[],'B':[]}
    for cell in cells:
        rows=cell['requests']
        if len(rows)!=7:raise ValueError('Four warmups and three measured requests required')
        for row in rows:
            if (row['generated_tokens']!=1 or row['prompt_tokens']!=512 or row['finish']!='length'
                or len(row['ids'])!=1 or row['ids'][0]==1 or row['prefix_reused'] or row['accepted_drafts'] or row['offered_drafts']):
                raise ValueError('Fixed token correctness evidence invalid')
            if not math.isfinite(row['prefill_ms']) or row['prefill_ms']<=0:raise ValueError('Invalid prefill timing')
            identities.add(digest(dict(ids=row['ids'],finish=row['finish'])))
        medians[cell['arm']].append(median(row['prefill_ms'] for row in rows[4:]))
    correct=len(identities)==1
    ratio=median(medians['A'])/median(medians['B'])
    separated=min(medians['A'])>max(medians['B'])
    trend=correct and ratio>=1.05
    signal=trend and separated and c['stage']=='confirm'
    verdict=('scoped_correctness_failed' if not correct else
             'screen_complete' if c['stage']=='screen' else 'scoped_improvement' if signal else 'no_scoped_improvement')
    return dict(verdict=verdict,scope=SCOPE,stage=c['stage'],execution_complete=True,
        promotion_authorized=False,overall_quality_acceptance=False,full_quality_claim=False,integration_check_required=True,
        gates=dict(single_token_repeatability_and_cross_arm_agreement=correct,minimum_5pct_signal=trend,
                   all_candidate_cell_medians_below_all_baseline=separated),
        prefill=dict(metric='median_native_prefill_ms',cell_medians=medians,speedup_A_over_B=ratio,
                     scope_performance_signal=signal,screen_trend=trend),
        cells=cells,limitations=['Identical 512-token prompt and one output token only; no full-generation quality claim.',
            'Four warmups excluded; three within-process repeats are not independent process replicates.',
            'Small-N AB/ABBA scoped signal, not statistical proof or end-to-end speedup.',
            'First initialization and storage cache are outside the primary metric.'])


def analyze_files(c,root,*,task_id,attempt_id):
    from .benchmark_worker import check_source_pins
    validate_contract(c);check_source_pins(c);verify_inputs(c)
    manifest=json.loads((root/'manifest.json').read_text())
    config=json.loads((root/'config.json').read_text());campaign=json.loads((root/'campaign.json').read_text())
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'
        and not p.name.endswith('.lock') and not p.name.startswith('.')}
    if (config['contract']!=c or campaign['execution_outcome']!='ok' or campaign['evidence_completeness']!='complete'
        or manifest['state']!='complete' or manifest['task_id']!=config['task_id']
        or manifest['attempt_id']!=config['attempt_id'] or config['task_id']!=task_id
        or config['attempt_id']!=attempt_id or campaign['task_id']!=task_id
        or campaign['attempt_id']!=attempt_id or campaign.get('source_identity')!=c['execution_sha256']
        or set(manifest['files'])!=actual):
        raise ValueError('Frozen scoped evidence identity/coverage differs')
    for name,want in manifest['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or path.is_symlink() or sha(path)!=want:
            raise ValueError('Changed or escaping scoped evidence')
    return dict(analyze(c,[dict(arm=arm,**verify_cell(c,arm,root/f'cell-{i:03d}-{arm}'/'prefill'))
        for i,arm in enumerate(c['order'],1)]),verification=dict(raw_files_verified=True,
            independent_native_parse=True,complete_cells=len(c['order'])))


class Workbench:
    def __init__(self,store):self.store=store;self.jobs=Jobs(store)

    def submit(self,task_id,contract_id,idem_key):
        task=self.store.get_task(task_id)
        if contract_id!=task['contract_id']:raise ValueError('Scoped workbench must use operator task contract')
        path=Path(contract_id);c=validate_contract(json.loads(path.read_text()));identity=sha(path)
        if task['constraints'].get('benchmark_contract_sha256')!=identity:
            raise ValueError('Scoped contract identity changed')
        request=dict(adapter=ADAPTER,contract=c,contract_path=str(path),contract_sha256=identity)
        environment=dict(FACTORY_HOME=str(self.store.home),PYTHONPATH=str(Path(c['workspace_root'])/'sources/cc-dgx-spark'))
        parent=task.get('constraints',{}).get('factory_loop_parent')
        if parent:
            from .mission_supervisor import mission_root
            request.update(quiet_required=True,quiet_root=str(mission_root(self.store.home,parent)))
            environment['FACTORY_PREFILL_QUIET_ROOT']=request['quiet_root']
        argv=[os.environ.get('FACTORY_HOST_PYTHON',sys.executable),'-m','jiuwenswarm.factory.prefill_worker',
            '--contract',str(path),'--contract-sha256',identity,'--output',str(self.store.home/'prefill-spool'/'{attempt_id}'),
            '--task',task_id,'--attempt','{attempt_id}']
        return self.jobs.submit(task_id,'lab',request,idem_key,'gpu',argv,c['campaign_timeout_s']+120,environment)

    def status(self,task_id,attempt_id):
        attempt=self.jobs._get(attempt_id)
        if attempt['task_id']!=task_id or attempt['request'].get('adapter')!=ADAPTER:
            raise ValueError('Scoped attempt belongs to another task or adapter')
        return self.jobs.status(attempt_id)

    def result(self,task_id,attempt_id):
        attempt=self.status(task_id,attempt_id)
        if os.environ.get('FACTORY_BRIDGE_DIR'):
            from .bridge import call
            reply=call('prefill_workbench_result',task_id=task_id,attempt_id=attempt_id)
            reply.check_returncode();return json.loads(reply.stdout)
        result=dict(attempt_id=attempt_id,state=attempt['state'],analysis=None)
        if attempt['state'] not in {'succeeded','failed','cancelled'}:return result
        obs_id=attempt_id+':observation'
        try:existing=self.store.read(task_id,obs_id)
        except NotFound:existing=None
        root=self.store.home/'prefill-spool'/attempt_id
        try:
            if attempt['state']!='succeeded':raise ValueError('Scoped campaign did not complete')
            analysis=analyze_files(attempt['request']['contract'],root,task_id=task_id,attempt_id=attempt_id)
        except (ValueError,KeyError,OSError,RuntimeError) as exc:
            analysis=dict(verdict='inconclusive',scope=SCOPE,promotion_authorized=False,
                overall_quality_acceptance=False,full_quality_claim=False,error=type(exc).__name__+': '+str(exc),execution_complete=False)
        if existing:
            if (existing.get('kind')!='scoped_prefill_result' or existing.get('values')!=analysis
                or existing.get('host_run')!={'attempt_id':attempt_id}):
                raise ValueError('Scoped result observation identity is occupied or raw evidence changed')
            result['analysis']=analysis
            return result
        refs=[]
        for path in sorted(root.rglob('*')):
            if path.is_file() and not path.is_symlink() and not path.name.endswith('.lock'):
                art=self.store.put_artifact(task_id,attempt_id+':'+str(path.relative_to(root)),path,'application/octet-stream',attempt_id)
                refs.append(art['artifact_id'])
        self.store.append_observation(task_id,dict(obs_id=obs_id,kind='scoped_prefill_result',values=analysis,
            source_artifacts=refs,host_run={'attempt_id':attempt_id},limitations='Native prefill microbenchmark only; separate integration check required.'))
        metadata(self.store,attempt,result_refs=refs+[obs_id]);result['analysis']=analysis
        return result


def dispatch(store,task_id,capability,inputs):
    from .api import fields
    if capability in {'submit','status','result'}:
        fields(inputs,{'contract_id','idem_key'} if capability=='submit' else {'attempt_id'},
            {'contract_id','idem_key'} if capability=='submit' else {'attempt_id'})
        if hasattr(store,'_check'):store._check(task_id,write=True);store=store._store
        return {'result':getattr(Workbench(store),capability)(task_id,**inputs)}
    if capability=='inspect':
        fields(inputs,{})
        c=validate_contract(json.loads(Path(store.get_task(task_id)['contract_id']).read_text()))
        result=dict(adapter=ADAPTER,scope=SCOPE,contract=c,execution_performed=False)
    elif capability=='design':
        fields(inputs,{'base_contract','prompt_ids','tokenizer_files','stage'}, {'base_contract','prompt_ids','tokenizer_files'})
        result=design(**inputs)
    elif capability=='apply':
        fields(inputs,{'base_profile','chunk_tokens'},{'base_profile','chunk_tokens'})
        result=apply(**inputs)
    elif capability=='verify_profile':
        fields(inputs,{'profile','chunk_tokens'},{'profile','chunk_tokens'})
        result=apply(inputs['profile'],inputs['chunk_tokens'])
        if result['change']['changed']:raise ValueError('Profile does not already request expected chunk')
        result.update(effective_requested_chunk=inputs['chunk_tokens'],runtime_engagement='not_measured')
    else:raise ValueError('Unknown scoped prefill capability')
    return {'result':result}
