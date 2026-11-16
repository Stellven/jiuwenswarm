"""Two bounded observer runs using a retained qualified image; no speed acceptance.

Operator entry point, separate from CPU CCs. Uses the existing guarded recorder,
immutable image, source/asset witnesses and an exclusive lab lease. No builds.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from jiuwenswarm.factory import benchmark as bm, benchmark_worker as worker, lab_recorder as recorder
from jiuwenswarm.factory.fixed_placement_benchmark import validate_build
from jiuwenswarm.factory.lab_lifecycle import atomic_json, inspect_owned, load_intent, recover_run
from jiuwenswarm.factory.ccs.strata_budget_workbench.component import verify_startup
from jiuwenswarm.ccv2.ccv2 import Host


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--run',action='store_true')
    p.add_argument('--only-arm',choices=['baseline','candidate'])
    p.add_argument('--retry-of',type=Path,help='Retained failed diagnostic result; does not overwrite it')
    a=p.parse_args();root=a.root.resolve();out=a.output.resolve()
    if out.exists():raise ValueError('Use a fresh owned output directory')
    prior=root/'night-branch-engine-v2'
    contract=json.loads((prior/'contract.json').read_text())
    model_source=root/'projects/fixed-placement/src/dsv41/ds4_main.cpp'
    dataset_path=Path(contract['dataset_path'])
    if sha(dataset_path)!=contract['dataset_sha256']:raise ValueError('Dataset identity changed')
    data=json.loads(dataset_path.read_text())
    base_contract=json.loads((root/'fixed-placement-campaign-v1/fixed-aa-contract.json').read_text())
    validate_build(base_contract)
    if base_contract['image']['id'] != contract['image']:raise ValueError('Qualified image differs')
    if bm.validate_assets(base_contract)!=contract['assets']:raise ValueError('Retained asset identity differs')
    case=copy.deepcopy(data['speed'][0]);case['max_new_tokens']=50
    retained={}
    for arm,cell in [('baseline','cell-001-A'),('candidate','cell-003-C')]:
        lines=(prior/'run-001'/cell/'speed/stdout.log').read_text().splitlines();tokens=[]
        for line in lines:
            if line.startswith('T '):tokens.append(int(line[2:]))
            if line.startswith('DONE '):break
        retained[arm]=tokens
    if retained['baseline'][:49]!=retained['candidate'][:49] or retained['baseline'][49]==retained['candidate'][49]:
        raise ValueError('Retained first-divergence precondition differs')
    profiles={key:copy.deepcopy(contract['profiles'][arm]) for key,arm in [('baseline','A'),('candidate','C')]}
    for profile in profiles.values():
        profile['args'][profile['args'].index('--eos')+1]='-1'
    out.mkdir(parents=True)
    package=out/'package'
    shutil.copytree(REPO/'jiuwenswarm/factory/ccs/numerical_investigation_lab',package,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    sys.path.insert(0,str(package))
    from components import digest
    from capture_adapter import SOURCE_MAIN_SHA256, MARKER
    if sha(model_source)!=SOURCE_MAIN_SHA256:raise ValueError('Native source does not match reviewed capture adapter')
    host=Host(out/'ccstore',python=sys.executable);release=host.prepare(package)
    def call(cap,inputs):
        receipt=host.call(release,cap,inputs,grants=['process.exec'])
        if receipt['state']!='succeeded':raise ValueError('CC failed: '+cap+' '+str(receipt.get('diagnostics',receipt['reason'])))
        return receipt['outputs']['result']
    common=dict(model='sha256:'+digest(contract['assets']),tokenizer='sha256:'+digest(data['provenance']['tokenizer']),
        source='89ae0ee6123597636ef162dec826230186c00f3b',precision='IST-DAS-2.00bpw;kv-fp4',routing='full-six-static-no-drafts')
    spec=call('replay_spec',dict(baseline_identity=dict(common,profile=digest(profiles['baseline'])),
        candidate_identity=dict(common,profile=digest(profiles['candidate'])),prompt_ids=case['ids'],
        teacher_ids=retained['baseline'][:49],step=49,vocabulary_size=129280,treatment_fields=['profile'],
        comparison_policy=dict(declaration_id='diagnostic-exact-vectors-v1',absolute_tolerance=0,relative_tolerance=0,top_k=8)))['spec']
    atomic_json(out/'replay-spec.json',spec)
    plans={arm:call('capture_plan',dict(profile=profile,spec=spec,arm=arm,dump_prefix='/tmp/strata-logits')) for arm,profile in profiles.items()}
    pins={str(f.relative_to(REPO)):sha(f) for f in [Path(__file__),*[REPO/'jiuwenswarm/factory'/name for name in bm.EXECUTION_FILES]]}
    policy=dict(schema='operator-ds4-logit-diagnostic/1',order=[a.only_arm] if a.only_arm else ['baseline','candidate'],max_cells=1 if a.only_arm else 2,
        phase_timeout_s=300,deadline_epoch=time.time()+700,image=contract['image'],spec_sha256=digest(spec),
        source_main_sha256=SOURCE_MAIN_SHA256,profiles=profiles,package_release=release,source_pins=pins,
        origin_contract_sha256=sha(prior/'contract.json'),source_dataset_sha256=sha(dataset_path),
        assets=contract['assets'],performance_claim=False,promotion_authorized=False,
        scope='One captured logit row per arm with exact shared-history check; observer timings ineligible.')
    if a.retry_of is not None:
        old=json.loads(a.retry_of.read_text())
        if old.get('state')!='failed':raise ValueError('Retry origin must be a failed result')
        policy['retry_origin']={'path':str(a.retry_of.resolve()),'sha256':sha(a.retry_of),'prior_gpu_cells':old['gpu_cells']}
    atomic_json(out/'policy.json',policy)
    if not a.run:
        print(json.dumps(dict(prepared=str(out),gpu_executed=False,replay_requires_fresh_output=True)));return
    captures={};parsed={};result=dict(state='failed',gpu_cells=0)
    try:
        for arm in policy['order']:
            if time.time()>policy['deadline_epoch']-60:raise TimeoutError('Diagnostic deadline exhausted')
            if any(sha(REPO/f)!=h for f,h in pins.items()):raise ValueError('Execution source changed')
            if sha(model_source)!=SOURCE_MAIN_SHA256:raise ValueError('Capture source changed')
            if bm.validate_assets(base_contract)!=policy['assets']:raise ValueError('Assets changed')
            worker.admission(policy['image'])
            profile=profiles[arm];plan=plans[arm]
            phase=out/arm
            argv=['/usr/bin/python3','/numerical-cc/capture_wrapper.py','--vocabulary-size','129280','--',
                '/opt/strata/strata-dsv41',*profile['args'],'--profile-readonly','--serve']
            print(json.dumps(dict(event='start',arm=arm)),flush=True)
            report=recorder.run_container(argv,output=phase,image=policy['image'],
                mounts=[(v,v) for v in base_contract['workload'].values()]+[(str(package),'/numerical-cc')],
                gpu=True,environment=profile['environment'],protocol=(plan['request']+'\nQUIT\n').encode(),
                timeout_s=300,interval_ms=1000,guard_gib=8,memory_bytes=104*2**30,cpus=8,lease_root=root/'lab-lease')
            result['gpu_cells']+=1
            if not worker._successful(report):raise RuntimeError('Recorder failed: '+str(report.get('reason')))
            stderr=(phase/'stderr.log').read_text()
            parsed[arm]=bm.parse_native((phase/'stdout.log').read_text(),stderr,[case])
            verify_startup(dict(stderr=stderr,budget_bytes=76000000000))
            rows=[line[len(MARKER):] for line in stderr.splitlines() if line.startswith(MARKER)]
            if len(rows)!=1:raise ValueError('Missing/duplicate capture witness')
            atomic_json(out/(arm+'-row.json'),json.loads(rows[0]))
            imported=call('import_capture',dict(spec=spec,arm=arm,evidence_root=str(out),dump_path=arm+'-row.json',
                transcript_path=arm+'/stdout.log',stdin_path=arm+'/stdin-wire.log',profile=profile,source_main_sha256=SOURCE_MAIN_SHA256))
            captures[arm]=imported['capture']
            atomic_json(out/(arm+'-capture.json'),imported)
            print(json.dumps(dict(event='captured',arm=arm,outputs=50)),flush=True)
        if a.only_arm:
            result.update(state='complete',scope='Single arm capture; compare separately with verified matching evidence')
            return
        comparison=call('compare_logits',dict(spec=spec,baseline=captures['baseline'],candidate=captures['candidate']))
        comparison['historical_output_prefix_matches']={arm:parsed[arm]['requests'][0]['ids']==retained[arm][:50] for arm in policy['order']}
        comparison['native_top_choice_matches']={arm:comparison[arm]['top'][0]['token_id']==parsed[arm]['requests'][0]['ids'][49] for arm in policy['order']}
        if not all(comparison['native_top_choice_matches'].values()):raise ValueError('Captured row argmax does not match native output49')
        comparison['performance_claim']=False
        atomic_json(out/'comparison.json',comparison)
        result.update(state='complete',comparison='comparison.json')
    except BaseException as exc:
        result['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        cleanup=[]
        for arm in policy['order']:
            phase=out/arm
            if (phase/'intent.json').exists():
                if inspect_owned(load_intent(phase)) is not None:recover_run(phase,reason='numerical_diagnostic_exit')
                cleanup.append(dict(arm=arm,container_absent=inspect_owned(load_intent(phase)) is None))
        atomic_json(out/'cleanup.json',cleanup);atomic_json(out/'result.json',result)
        atomic_json(out/'MANIFEST.json',{str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*'))
            if f.is_file() and f.name!='MANIFEST.json' and '__pycache__' not in f.parts and f.suffix not in {'.sqlite','.lock'} and not f.name.endswith(('-wal','-shm'))})


if __name__=='__main__':main()
