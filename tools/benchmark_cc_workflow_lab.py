"""Explicit CPU-only actual-Host benchmark. Not callable by the capsule.

Run with the repository on PYTHONPATH. Outputs raw observations and independent
ABBA round medians. Never claims GPU, inference kernel, or model quality gains.
"""
import argparse
import hashlib
import importlib.util
import json
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path
from jiuwenswarm.ccv2.ccv2 import Host, tree_files

BUNDLE = Path(__file__).resolve().parents[1]/'jiuwenswarm/factory/ccs/cc_workflow_lab'
module_spec = importlib.util.spec_from_file_location('workflow_benchmark_target', BUNDLE/'workflow.py')
workflow = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(workflow)

def measure(fn):
    start = time.perf_counter_ns()
    value = fn()
    return (time.perf_counter_ns()-start)/1e9, value

def summarize(rows):
    return {'raw_s': rows, 'median_s': statistics.median(rows)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    fixture = workflow.fixture()
    names = sorted({row['package'] for row in fixture['receipts']})
    jobs = [{'operation':'analyze_receipts', 'spec':{'receipts':[row for row in fixture['receipts'] if row['package']==name]}} for name in names]
    expected = [workflow.analyze_receipts(job['spec']) for job in jobs]
    data = {'scope':'CPU actual-Host overhead only; no GPU or inference kernel measurement',
            'python': sys.executable, 'platform': platform.platform(),
            'fixture_sha256': hashlib.sha256((BUNDLE/'fixtures/qualification.json').read_bytes()).hexdigest(),
            'input_sha256': hashlib.sha256(json.dumps(jobs,sort_keys=True).encode()).hexdigest(),
            'historical_qualification_summary': workflow.analyze_receipts(fixture),
            'roles':{},'rounds':[], 'gpu_tested':False, 'admission_granted':False}
    output_path = Path(args.output).resolve()
    store = output_path.parent/'ccstore'
    if store.exists():
        raise ValueError('choose a new output directory for a genuinely cold store')
    store.mkdir(parents=True)
    data['receipt_store'] = str(store)
    host = Host(store, python=sys.executable)
    cold_s, release = measure(lambda:host.prepare(BUNDLE))
    data['cold_seal']={'elapsed_s':cold_s, 'release':release, 'scope':'first seal in empty store; OS caches uncontrolled'}
    for name, operation, repeats in [('source_tree_hash',lambda:tree_files(BUNDLE),7),
                                     ('warm_prepare',lambda:host.prepare(BUNDLE),7),
                                     ('direct_analysis_all_seven',lambda:[workflow.analyze_receipts(j['spec']) for j in jobs],7)]:
        samples = [measure(operation)[0] for _ in range(repeats)]
        data['roles'][name]=summarize(samples)
    packet = {'capability':'analyze_receipts','inputs':{'spec':jobs[0]['spec']}}
    def native():
        child=subprocess.run([sys.executable,str(BUNDLE/'run.py')],input=json.dumps(packet),text=True,capture_output=True,check=True)
        result=json.loads(child.stdout)
        assert result['outcome']=='ok' and result['outputs']['result']==expected[0]
    data['roles']['native_interpreter_import_protocol_and_analysis']=summarize([measure(native)[0] for _ in range(7)])
    # A single unscored warmup for each path; fresh invocation keys throughout.
    def run(mode):
        if mode=='batch':
            receipt=host.call(release,'run_batch',{'spec':{'jobs':jobs}},grants=['process.exec'])
            assert receipt['state']=='succeeded',receipt
            results=[r['result'] for r in receipt['outputs']['result']['results']]
        else:
            results=[]
            for job in jobs:
                current=host.prepare(BUNDLE) if mode=='prepare_each' else release
                receipt=host.call(current,job['operation'],{'spec':job['spec']},grants=['process.exec'])
                assert receipt['state']=='succeeded',receipt
                results.append(receipt['outputs']['result'])
        assert results==expected
        return results
    for mode in ['prepare_each','reuse_release','batch']:
        warm_s,_=measure(lambda mode=mode:run(mode))
        data.setdefault('warmups',{})[mode]=warm_s
    # Two independent ABBA comparisons; report each sample and order.
    for comparator in ['reuse_release','batch']:
        modes=['prepare_each',comparator,comparator,'prepare_each']*2
        for index,mode in enumerate(modes):
            elapsed,_=measure(lambda mode=mode:run(mode))
            data['rounds'].append({'comparison':comparator,'index':index,'mode':mode,'elapsed_s':elapsed,
                                   'native_calls':1 if mode=='batch' else 7,
                                   'prepare_calls':7 if mode=='prepare_each' else 0})
    for comparator in ['reuse_release','batch']:
        rows=[r for r in data['rounds'] if r['comparison']==comparator]
        baseline=statistics.median(r['elapsed_s'] for r in rows if r['mode']=='prepare_each')
        candidate=statistics.median(r['elapsed_s'] for r in rows if r['mode']==comparator)
        data.setdefault('comparisons',{})[comparator]={'baseline_median_s':baseline,'candidate_median_s':candidate,
                                                       'ratio_baseline_over_candidate':baseline/candidate}
    # Replay is a cache semantics check, excluded from fresh-work trials.
    first_s,first=measure(lambda:host.call(release,'analyze_receipts',{'spec':jobs[0]['spec']},key='replay-negative-control',grants=['process.exec']))
    replay_s,replay=measure(lambda:host.call(release,'analyze_receipts',{'spec':jobs[0]['spec']},key='replay-negative-control',grants=['process.exec']))
    assert first['call']==replay['call']
    bad=host.call(release,'run_batch',{'spec':{'jobs':[{'operation':'exec','spec':{}}]}},grants=['process.exec'])
    assert bad['state']=='failed',bad
    data['negative_checks']={'replay_same_call_id':True,'fresh_s':first_s,'replay_s':replay_s,
                              'external_batch_operation_rejected':True,'rejection_reason':bad['reason']}
    # Measure the finite instrumented analysis through the actual host.
    measured=host.call(release,'benchmark_fixture',{'spec':{'repeats':7}},grants=['process.exec'])
    assert measured['state']=='succeeded',measured
    data['instrumented_fixture']=measured['outputs']['result']
    data['parent_process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    data['rss_scope']='Linux process lifetime high water, not per-operation incremental RSS'
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'comparisons':data['comparisons'],'negative_checks':data['negative_checks'],'output':str(path)},indent=2))

if __name__=='__main__':
    main()
