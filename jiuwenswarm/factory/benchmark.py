"""Versioned public-task regression and fixed-workload Strata speed experiments.

This is a new benchmark contract; it does not relax historical byte/token goldens.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from .contract import atomic_json
from .engine_adapters import sha, inspect_assets
from .jobs import Jobs, metadata
from .store import encoded, NotFound

ADAPTER='strata-benchmark-v1'
PREFILL_ADAPTER='strata-benchmark-v2'
ADAPTERS={ADAPTER,PREFILL_ADAPTER,'strata-benchmark-v3','strata-benchmark-v4','strata-benchmark-v5','strata-construction-v1'}
EXECUTION_FILES=('benchmark.py','benchmark_worker.py','benchmark_analysis.py','benchmark_data.py','lab_recorder.py','lab_lifecycle.py')
V2_EXECUTION_FILES=EXECUTION_FILES+('strata_prefill.py','strata_components.py','strata_lab.py','engine_adapters.py','targets.py')


def flag(args,name):
    if args.count(name)!=1 or args.index(name)+1>=len(args):raise ValueError('Exactly one value required: '+name)
    return args[args.index(name)+1]


def _validate_v1_contract(c):
    if c.get('adapter')!=ADAPTER or c.get('version')!=1 or c.get('stage') not in {'pilot','main'}:
        raise ValueError('Unsupported standard benchmark contract')
    if c.get('tolerance')!='arc-exact-answer-regression-v1':raise ValueError('Wrong benchmark correctness policy')
    if c.get('target')!='spark-gb10':raise ValueError('Wrong benchmark target')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',c['image']['id']):raise ValueError('Immutable image required')
    a,b=c['arms']['A'],c['arms']['B']
    if any('DS4_EXPERT_BUDGET_BYTES' in arm['environment'] for arm in (a,b)):
        raise ValueError('Fixed placement requires the source-qualified v4 adapter')
    aa,bb=a['args'],b['args']
    if not all(isinstance(x,str) and '\0' not in x for x in aa+bb):raise ValueError('Invalid engine argv')
    if a['environment']!=b['environment']:raise ValueError('More than one treatment variable')
    if len(aa)!=len(bb) or [i for i,(x,y) in enumerate(zip(aa,bb)) if x!=y]!=[aa.index('--dspark')+1]:
        raise ValueError('Only the drafting activation value may differ')
    if flag(aa,'--dspark')!='none' or flag(bb,'--dspark')!='on':raise ValueError('Expected no-draft A versus verified-draft B')
    for arm in (a,b):
        args=arm['args']
        for key,value in [('--experts','6'),('--mmap-experts','on'),('--cpu-threads','8'),('--reserve-mib','16384'),
                          ('--vram-experts','1.0'),('--dspark-conf','0.65'),('--eos','1'),
                          ('--max-context','8192'),('--vision','off'),('--prefill-chunk','256'),('--ssd-cache','0'),
                          ('--pack',c['workload']['pack'])]:
            if flag(args,key)!=value:raise ValueError('Frozen configuration changed: '+key)
        if '--no-expert-cache' not in args or any(v in args for v in ('--serve','--profile','--profile-readonly')):
            raise ValueError('Static expert cache and host-owned serve controls required')
        if arm['environment'].get('STRATA_DS4_REUSE')!='0':raise ValueError('Prefix reuse must be disabled')
        from .engine_adapters import ENV_KEYS
        if (set(arm['environment'])-ENV_KEYS or any(not isinstance(v,str) or '\0' in v or '\n' in v
                for v in arm['environment'].values())):raise ValueError('Unapproved engine environment')
    want=['A','B'] if c['stage']=='pilot' else ['A','B','B','A']*2
    if c['order']!=want:raise ValueError('Predeclared pilot or two-block ABBA order required')
    lim=c['limits']
    if (lim['cpus']!=8 or lim['memory_bytes']!=104*2**30 or lim['guard_gib']!=8
        or lim.get('extra_swap_bytes',0)!=0 or lim['quality_timeout_s']!=900 or lim['speed_timeout_s']!=300):
        raise ValueError('Benchmark resource policy changed')
    gate=c['gates']
    if gate!=dict(minimum_accuracy=0.5,minimum_speedup=1.05,confidence=0.95,bootstrap_resamples=20000,seed=42,
                  correctness='no_per_question_regression'):
        raise ValueError('Benchmark acceptance gates differ from the predeclared v1 policy')
    if not isinstance(c.get('campaign_timeout_s'),int) or not 1<=c['campaign_timeout_s']<=5400:
        raise ValueError('Campaign deadline outside bounds')
    if set(c['execution_sha256'])!=set(EXECUTION_FILES):raise ValueError('Complete execution identity required')
    if any(not re.fullmatch('[a-f0-9]{64}',v) for v in c['execution_sha256'].values()):raise ValueError('Invalid source identity')
    if not re.fullmatch('[a-f0-9]{64}',c['dataset_sha256']):raise ValueError('Dataset identity required')
    return c


def validate_contract(c):
    """Preserve historical policies; construction comparisons have separate admission."""
    if c.get("adapter") == "strata-construction-v1":
        from .construction_comparison import validate_contract as validate_construction
        return validate_construction(c)
    if c.get('adapter') == 'strata-benchmark-v5':
        from .fixed_screen_benchmark import validate_contract as validate_screens
        return validate_screens(c)
    if c.get('adapter') == 'strata-benchmark-v4':
        from .fixed_placement_benchmark import validate_contract as validate_fixed
        return validate_fixed(c)
    if c.get('adapter') == 'strata-benchmark-v3':
        from .broad_benchmark import validate_contract as validate_broad
        return validate_broad(c)
    if c.get('adapter') != PREFILL_ADAPTER:
        return _validate_v1_contract(c)
    if (c.get('version') != 2 or c.get('component') != 'strata.prefill_chunk'
            or c.get('primary_metric') != 'prefill_plus_decode_output_tokens_per_second'):
        raise ValueError('Unsupported v2 prefill contract identity or metric')
    if set(c['execution_sha256']) != set(V2_EXECUTION_FILES):
        raise ValueError('Complete v2 execution identity required')
    if any(not re.fullmatch('[a-f0-9]{64}', v) for v in c['execution_sha256'].values()):
        raise ValueError('Invalid v2 source identity')
    import copy
    from .strata_prefill import apply
    a, b = c['arms']['A'], c['arms']['B']
    expected = apply(a, 512)['profile']
    if b != expected or flag(a['args'], '--prefill-chunk') != '256':
        raise ValueError('v2 requires exactly prefill chunk 256 versus 512')
    if flag(a['args'], '--dspark') != 'none':
        raise ValueError('v2 requires dspark none in both arms')
    # Validate all existing frozen dataset/resource/quality obligations using an
    # internal copy shaped as v1. The admitted v2 contract remains untouched.
    shaped = copy.deepcopy(c)
    shaped.update(adapter=ADAPTER, version=1)
    shaped['execution_sha256'] = {name: c['execution_sha256'][name] for name in EXECUTION_FILES}
    args = shaped['arms']['B']['args']
    args[args.index('--prefill-chunk')+1] = '256'
    args[args.index('--dspark')+1] = 'on'
    _validate_v1_contract(shaped)
    return c


def load_dataset(c):
    if sha(c['dataset_path'])!=c['dataset_sha256']:raise ValueError('Pinned benchmark dataset changed')
    d=json.loads(Path(c['dataset_path']).read_text())
    if len(d['quality'])!=64 or len(d['pilot'])!=2 or len(d['speed'])!=4:raise ValueError('Benchmark case count differs')
    if len({v['id'] for v in d['quality']})!=64:raise ValueError('Duplicate test questions')
    if {v['id'] for v in d['quality']} & {v['id'] for v in d['pilot']}:raise ValueError('Pilot/test overlap')
    for case in d['quality']+d['pilot']+d['speed']:
        if not case['ids'] or any(type(v)is not int or v<0 for v in case['ids']):raise ValueError('Invalid tokenized input')
    if any(len(v['ids'])!=512 or v['max_new_tokens']!=128 for v in d['speed']):raise ValueError('Speed workload must be fixed pg512/tg128')
    if any(v['max_new_tokens']!=8 or v['expected_letter'] not in v['allowed_letters'] for v in d['quality']+d['pilot']):
        raise ValueError('Quality answer policy changed')
    return d


def validate_assets(c):
    # Reuse the proven asset identity verifier; the shim is not a scored contract.
    shim=dict(adapter='strata-v1',version=1,target='spark-gb10',tolerance='canonical-token-ids-and-finish',assets=c['assets'],
        workload=dict(argv=c['arms']['A']['args'],environment=c['arms']['A']['environment'],requests=[{'ids':[0],'max_new_tokens':1}]),
        limits=dict(cpus=8,memory_bytes=104*2**30,extra_swap_bytes=0,guard_gib=8,timeout_s=900))
    return inspect_assets(shim)


def phase_cases(c,d,phase):
    if c.get('adapter') in ('strata-benchmark-v3','strata-benchmark-v4','strata-benchmark-v5','strata-construction-v1'):
        from .broad_benchmark import phase_cases as broad_cases
        return broad_cases(c,d,phase)
    if phase=='quality':return d['pilot'] if c['stage']=='pilot' else d['quality']
    if phase=='speed':return d['speed'][:2] if c['stage']=='pilot' else d['speed']
    raise ValueError('Unknown benchmark phase')


def phase_args(c,arm,phase):
    args=list(c['arms'][arm]['args']);args[args.index('--eos')+1]='1' if phase=='quality' else '-1'
    return ['/opt/strata/strata-dsv41',*args,'--profile-readonly','--serve']


def protocol(cases,arm,contract=None):
    spec = (flag(contract['arms'][arm]['args'], '--dspark') == 'on') if contract is not None else arm == 'B'
    return (''.join(f"GEN {v['max_new_tokens']} temperature=0 top_p=1 top_k=1 min_p=0 seed=42 spec={int(spec)} "
        +','.join(map(str,v['ids']))+'\n' for v in cases)+'QUIT\n').encode()


def parse_native(stdout,stderr,cases):
    if re.search(r'terminate called|Segmentation fault',stderr):raise ValueError('Fatal native stderr')
    experts=re.findall(r'experts per word:\s*(\d+)',stderr)
    if not experts or any(v!='6' for v in experts):raise ValueError('Full-six expert engagement missing')
    rows=[];ids=[];ready=False
    for line in stdout.splitlines():
        s=line.split()
        if not s:continue
        if s[0]=='ERR':raise ValueError('Native error: '+line[:200])
        if s[0]=='READY':
            if ready:raise ValueError('Duplicate READY')
            ready=True
        elif s[0]=='T':
            if not ready or len(s)!=2 or len(rows)>=len(cases):raise ValueError('Invalid token framing')
            ids.append(int(s[1]))
            if ids[-1]<0 or len(ids)>cases[len(rows)]['max_new_tokens']:raise ValueError('Invalid token/cap')
        elif s[0]=='DONE':
            if len(s)!=11 or len(rows)>=len(cases):raise ValueError('Invalid DONE framing')
            n,p=int(s[1]),int(s[2]);pp,dt=float(s[3]),float(s[4]);accepted,offered=int(s[6]),int(s[7])
            case=cases[len(rows)]
            if (n!=len(ids) or n<1 or p!=len(case['ids']) or s[5] not in {'stop','length'} or int(s[-1])!=0
                or not 0<=accepted<=offered or not all(math.isfinite(v) and v>0 for v in (pp,dt))):
                raise ValueError('Native request count/timing/engagement inconsistent')
            rows.append(dict(case_id=case['id'],ids=ids,generated_tokens=n,prompt_tokens=p,prefill_ms=pp,decode_ms=dt,
                decode_tps=n*1000/dt,prefill_tps=p*1000/pp,finish=s[5],prefix_reused=int(s[-1]),
                accepted_drafts=accepted,offered_drafts=offered,
                canonical_sha256=hashlib.sha256(encoded({'ids':ids,'finish':s[5]}).encode()).hexdigest()))
            ids=[]
    if not ready or ids or len(rows)!=len(cases):raise ValueError('Incomplete native protocol')
    return dict(requests=rows,effective_experts=6)


def verify_prefill_engagement(c, arm, parsed, stderr):
    if c.get('adapter') == 'strata-construction-v1':
        from .construction_comparison import engagement
        return engagement(c, arm, parsed, stderr)
    """Fail closed when allocation fallback or an override masks the v2 knob."""
    if c.get('adapter') == 'strata-benchmark-v5':
        from .fixed_screen_benchmark import engagement as screen_engagement
        return screen_engagement(c,arm,parsed,stderr)
    if c.get('adapter') == 'strata-benchmark-v4':
        from .fixed_placement_benchmark import engagement as fixed_engagement
        return fixed_engagement(c,arm,parsed,stderr)
    if c.get('adapter') == 'strata-benchmark-v3':
        from .broad_benchmark import engagement
        return engagement(c, arm, parsed, stderr)
    if c.get('adapter') != PREFILL_ADAPTER:
        return
    chunks = re.findall(r'prompts in chunks of (\d+)\)', stderr)
    expected = flag(c['arms'][arm]['args'], '--prefill-chunk')
    if not chunks or any(chunk != expected for chunk in chunks):
        raise ValueError('Effective native prefill chunk differs or is missing')
    if any(row['accepted_drafts'] != 0 or row['offered_drafts'] != 0 for row in parsed['requests']):
        raise ValueError('Drafts must remain disabled in both v2 phases')
    parsed['effective_prefill_chunk'] = int(expected)


def verify_phase(c,arm,phase,path,cases):
    from .lab_recorder import verify_boundary,GATE
    report=json.loads((path/'report.json').read_text())
    if not(report['reason']=='completed' and report['quiescent'] and report['container_removed'] and report['container_exit_code']==0
        and report['evidence_completeness']=='complete'):
        raise ValueError('Incomplete/failed benchmark phase: '+str(path))
    intent=json.loads((path/'intent.json').read_text());created=json.loads((path/'inspect-created.json').read_text())
    final=json.loads((path/'inspect-final.json').read_text())
    from .construction_comparison import image_for
    expected_image = image_for(c, arm)
    if c.get('adapter') == 'strata-construction-v1':
        build = json.loads((path.parent/(phase+'-result.json')).read_text())
        expected_binary = c['baseline_executable_sha256'] if arm=='A' or c['campaign_stage']=='aa' else c['lineage']['executable_sha256']
        if build.get('executable_sha256') != expected_binary:
            raise ValueError('Executed binary identity differs from built artifact')
    if intent['image']!=expected_image:raise ValueError('Image differs from admitted contract')
    verify_boundary(created,intent,memory_bytes=c['limits']['memory_bytes'],cpus=8,environment=c['arms'][arm]['environment'])
    if created['Config']['Cmd']!=['-c',GATE,*phase_args(c,arm,phase)] or created['Config']['Entrypoint']!=['/usr/bin/python3']:
        raise ValueError('Actual benchmark argv differs')
    if (created['Id']!=final['Id'] or final['Image']!=expected_image or final['State']['Running']
        or final['State']['Pid']!=0 or final['State']['ExitCode']!=0 or final['State']['OOMKilled']):
        raise ValueError('Final state or image invalid')
    devices=created['HostConfig'].get('DeviceRequests') or []
    if len(devices)!=1 or devices[0].get('Driver')!='cdi' or devices[0].get('DeviceIDs')!=['nvidia.com/gpu=0']:
        raise ValueError('Wrong GPU device')
    mounts={(m['Source'],m['Destination']) for m in created['Mounts'] if m['Type']=='bind'}
    if mounts!={(str(Path(v).resolve()),str(v)) for v in c['workload'].values()}:raise ValueError('Mount scope changed')
    if (path/'stdin-wire.log').read_bytes()!=b'FACTORY_EXEC\n'+protocol(cases,arm,c):raise ValueError('Input wire differs')
    offsets=dict(stdin=0,stdout=0,stderr=0)
    for i,line in enumerate((path/'pipe-events.jsonl').read_text().splitlines()):
        e=json.loads(line);stream=e['stream']
        if e['sequence']!=i or e['offset']!=offsets[stream] or e['truncated']:raise ValueError('Pipe coverage invalid')
        offsets[stream]+=e['retained_bytes']
    for stream,name in [('stdin','stdin-wire.log'),('stdout','stdout.log'),('stderr','stderr.log')]:
        if offsets[stream]!=(path/name).stat().st_size:raise ValueError('Raw coverage differs')
    samples=[json.loads(line) for line in (path/'samples.jsonl').read_text().splitlines()]
    if not samples or any(s['available_bytes']<8*2**30 or any(s['memory_events'].get(k,0) for k in ('oom','oom_kill','oom_group_kill')) for s in samples):
        raise ValueError('Host guard or OOM evidence invalid')
    parsed=parse_native((path/'stdout.log').read_text(),(path/'stderr.log').read_text(),cases)
    verify_prefill_engagement(c, arm, parsed, (path/'stderr.log').read_text())
    parsed['min_host_available_bytes']=min(s['available_bytes'] for s in samples)
    return parsed


def analyze_files(c,root):
    d=load_dataset(c);cells=[]
    manifest=json.loads((root/'manifest.json').read_text())
    config=json.loads((root/'config.json').read_text())
    campaign=json.loads((root/'campaign.json').read_text())
    if (config['contract']!=c or campaign['execution_outcome']!='ok' or campaign['evidence_completeness']!='complete'
        or manifest['state']!='complete' or manifest['task_id']!=config['task_id']
        or manifest['attempt_id']!=config['attempt_id']):raise ValueError('Campaign identity/completeness differs')
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'
        and not p.name.endswith('.lock') and not p.name.startswith('.')}
    if set(manifest['files'])!=actual:raise ValueError('Evidence manifest coverage differs')
    for name,want in manifest['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path)!=want:raise ValueError('Changed/escaping evidence: '+name)
    for i,arm in enumerate(c['order'],1):
        item=dict(index=i,arm=arm)
        for phase in ('quality','speed'):
            cases=phase_cases(c,d,phase);path=root/f'cell-{i:03d}-{arm}'/phase
            item[phase]=verify_phase(c,arm,phase,path,cases);item[phase]['cases']=cases
        cells.append(item)
    from .benchmark_data import load_decoder,decode_answer
    if c.get('adapter') == 'strata-construction-v1':
        from .construction_comparison import analyze
    elif c.get('adapter') == 'strata-benchmark-v5':
        from .fixed_screen_benchmark import analyze
    elif c.get('adapter') == 'strata-benchmark-v4':
        from .fixed_placement_benchmark import analyze
    elif c.get('adapter') == 'strata-benchmark-v3':
        from .broad_benchmark import analyze
    else:
        from .benchmark_analysis import analyze
    tokenizer=load_decoder(Path(c['workspace_root']),d['provenance']['tokenizer']['files'])
    result=analyze(c,d,cells,lambda ids,letters:decode_answer(ids,tokenizer,letters,eos_id=1))
    result['verification']=dict(raw_files_verified=True,independent_native_parse=True,complete_cells=len(cells))
    return result


class Benchmark:
    def __init__(self,store):
        self.store=store;self.jobs=Jobs(store)

    def submit(self,task_id,contract_id,idem_key):
        task=self.store.get_task(task_id)
        if contract_id!=task['contract_id']:raise ValueError('Benchmark must use the operator task contract')
        path=Path(contract_id);c=validate_contract(json.loads(path.read_text()));digest=sha(path)
        if task['constraints'].get('benchmark_contract_sha256')!=digest:raise ValueError('Benchmark contract identity changed')
        load_dataset(c)
        # Host worker checks large read-only assets before admission; agent containers
        # intentionally cannot access the model directories or Docker.
        if not os.environ.get('FACTORY_BRIDGE_DIR'):validate_assets(c)
        request=dict(adapter=c['adapter'],contract=c,contract_path=str(path),contract_sha256=digest)
        argv=[os.environ.get('FACTORY_HOST_PYTHON',sys.executable),'-m','jiuwenswarm.factory.benchmark_worker','--contract',str(path),'--contract-sha256',digest,
            '--output',str(self.store.home/'benchmark-spool'/'{attempt_id}'),'--task',task_id,'--attempt','{attempt_id}']
        environment = dict(FACTORY_HOME=str(self.store.home),
                           PYTHONPATH=str(Path(c['workspace_root'])/'sources/cc-dgx-spark'))
        if c['adapter'] == 'strata-construction-v1':
            if not {'process.exec', 'gpu.use'} <= set(task['allowed_effects']):
                raise ValueError('Independent engine comparison requires process.exec and gpu.use grants')
            from .construction_comparison import verify_lineage
            if not os.environ.get('FACTORY_BRIDGE_DIR'):
                verify_lineage(self.store, c)
            from .execution_binding import worker_environment
            environment.update(worker_environment(task['constraints']['execution_binding']))
        parent = task.get('constraints', {}).get('factory_loop_parent')
        if parent:
            from .mission_supervisor import mission_root
            request.update(quiet_required=True, quiet_root=str(mission_root(self.store.home, parent)))
            environment['FACTORY_BENCHMARK_QUIET_ROOT'] = request['quiet_root']
        return self.jobs.submit(task_id,'lab',request,idem_key,'gpu',argv,c['campaign_timeout_s']+120,
            environment)

    def status(self,task_id,attempt_id):
        attempt=self.jobs._get(attempt_id)
        if attempt['task_id']!=task_id or attempt['request'].get('adapter') not in ADAPTERS:raise ValueError('Benchmark belongs to another task')
        return self.jobs.status(attempt_id)

    def result(self,task_id,attempt_id):
        if os.environ.get('FACTORY_BRIDGE_DIR'):
            self.status(task_id,attempt_id)  # Scope check before delegating host-only analysis.
            from .bridge import call
            value=call('benchmark_result',task_id=task_id,attempt_id=attempt_id)
            value.check_returncode()
            return json.loads(value.stdout)
        attempt=self.status(task_id,attempt_id);root=self.store.home/'benchmark-spool'/attempt_id
        result=dict(attempt_id=attempt_id,state=attempt['state'],analysis=None)
        if attempt['state'] not in {'succeeded','failed','cancelled'}:return result
        obs_id=attempt_id+':observation'
        try:result['analysis']=self.store.read(task_id,obs_id)['values'];return result
        except NotFound:pass
        try:
            if attempt['state']!='succeeded':raise ValueError('Campaign did not complete; retain partial evidence')
            analysis=analyze_files(attempt['request']['contract'],root)
        except (ValueError,KeyError,OSError,RuntimeError) as exc:analysis=dict(verdict='inconclusive',error=type(exc).__name__+': '+str(exc),execution_complete=False)
        refs=[]
        for path in sorted(root.rglob('*')):
            if path.is_file() and not path.is_symlink() and not path.name.endswith('.lock'):
                ref=self.store.put_artifact(task_id,attempt_id+':'+str(path.relative_to(root)),path,'application/octet-stream',attempt_id)
                refs.append(ref['artifact_id'])
        self.store.append_observation(task_id,dict(obs_id=obs_id,kind='lab_result',values=analysis,
            source_artifacts=refs,host_run={'attempt_id':attempt_id},limitations='Sampled generative ARC regression plus fixed-workload native speed; not an official full benchmark score.'))
        metadata(self.store,attempt,result_refs=refs+[obs_id]);result['analysis']=analysis
        return result
