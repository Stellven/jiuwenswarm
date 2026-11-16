"""Re-import retained diagnostic evidence without rerunning an engine."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import benchmark as bm


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    roots={'baseline':a.baseline.resolve(),'candidate':a.candidate.resolve()}
    specs=[json.loads((root/'replay-spec.json').read_text()) for root in roots.values()]
    if specs[0]!=specs[1]:raise ValueError('Different frozen histories or comparison policies')
    spec=specs[0]
    policies={arm:json.loads((root/'policy.json').read_text()) for arm,root in roots.items()}
    for key in ['image','source_main_sha256','profiles','assets','source_dataset_sha256']:
        if policies['baseline'][key]!=policies['candidate'][key]:raise ValueError('Different '+key)
    if sha(roots['baseline']/'package/capture_wrapper.py')!=sha(roots['candidate']/'package/capture_wrapper.py'):
        raise ValueError('Different observer implementation')
    host=Host(out/'ccstore',python=sys.executable)
    release=host.prepare(REPO/'jiuwenswarm/factory/ccs/numerical_investigation_lab')
    def call(cap,inputs):
        r=host.call(release,cap,inputs,grants=['process.exec'])
        if r['state']!='succeeded':raise ValueError(str(r.get('diagnostics',r['reason'])))
        return r['outputs']['result']
    captures={};tokens={};witnesses={}
    for arm,root in roots.items():
        phase=root/arm
        report=json.loads((phase/'report.json').read_text())
        if not (report['reason']=='completed' and report['container_exit_code']==0
                and report['container_removed'] and report['quiescent'] and not report['container_oom_killed']):
            raise ValueError('Incomplete engine/cleanup boundary')
        manifest=json.loads((root/'MANIFEST.json').read_text())
        for name in ['policy.json','replay-spec.json','package/capture_wrapper.py',arm+'-row.json',arm+'/stdout.log',arm+'/stdin-wire.log',arm+'/report.json',arm+'/stderr.log']:
            if sha(root/name)!=manifest[name]:raise ValueError('Retained artifact changed: '+name)
        imported=call('import_capture',dict(spec=spec,arm=arm,evidence_root=str(root),dump_path=arm+'-row.json',
            transcript_path=arm+'/stdout.log',stdin_path=arm+'/stdin-wire.log',profile=policies[arm]['profiles'][arm],
            source_main_sha256=policies[arm]['source_main_sha256']))
        captures[arm]=imported['capture'];write(out/(arm+'-import.json'),imported)
        case={'id':'retained-shared-history','ids':spec['prompt_ids'],'max_new_tokens':50}
        parsed=bm.parse_native((phase/'stdout.log').read_text(),(phase/'stderr.log').read_text(),[case])
        tokens[arm]=parsed['requests'][0]['ids']
        witnesses[arm]=dict(root=str(root),policy_sha256=sha(root/'policy.json'),manifest_sha256=sha(root/'MANIFEST.json'),
            stdout_sha256=sha(phase/'stdout.log'),wrapper_sha256=sha(root/'package/capture_wrapper.py'))
    comparison=call('compare_logits',dict(spec=spec,baseline=captures['baseline'],candidate=captures['candidate']))
    matches={arm:comparison[arm]['top'][0]['token_id']==tokens[arm][49] for arm in roots}
    if not all(matches.values()):raise ValueError('Captured row argmax differs from emitted native token')
    divergence=call('first_divergence',dict(baseline_ids=tokens['baseline'],candidate_ids=tokens['candidate'],baseline_finish='length',candidate_finish='length'))
    result=dict(comparison=comparison,first_divergence=divergence,native_top_choice_matches=matches,
        witnesses=witnesses,package_release=release,scope='Two observer-enabled GPU captures, common history verified; no speed or quality acceptance',
        promotion_authorized=False,observer_overhead_measured=False,layer_cause_established=False)
    write(out/'analysis.json',result)
    write(out/'token-check.json',dict(baseline_ids=tokens['baseline'],candidate_ids=tokens['candidate'],baseline_finish='length',candidate_finish='length'))
    write(out/'MANIFEST.json',{str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file()
        and f.name!='MANIFEST.json' and f.suffix not in {'.sqlite','.lock'} and not f.name.endswith(('-wal','-shm'))})
    print(json.dumps(dict(output=str(out),first_difference=divergence['first_different_index'],
        max_absolute_difference=comparison['maximum_absolute_difference'],same_top_choice=comparison['same_top_choice'])))


if __name__=='__main__':main()
