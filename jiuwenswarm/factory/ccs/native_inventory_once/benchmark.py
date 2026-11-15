"""CPU-only fixed current-environment inventory ABBA and isolated Host comparison.

This developer benchmark is not a native capsule capability. It cannot grant
itself effects; the only test calls explicitly grant process.exec to the fixed
bundled workflow analysis capsule. The original host source is never modified.
"""
import argparse
import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from inventory import fresh_inventory, repeated_metadata_reads
from verification import verify

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

def timed(fn):
    start = time.perf_counter_ns()
    value = fn()
    return (time.perf_counter_ns()-start)/1e9, value

def traced(fn):
    tracemalloc.start()
    try:
        _, value = timed(fn)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak, value

def comparison(rows):
    medians = {mode:statistics.median(r['elapsed_s'] for r in rows if r['mode']==mode)
               for mode in ['baseline','candidate']}
    return {**{mode+'_median_s':value for mode,value in medians.items()},
            'ratio_baseline_over_candidate':medians['baseline']/medians['candidate']}

def candidate_source():
    target = REPO/'jiuwenswarm/ccv2/ccv2.py'
    raw = target.read_bytes()
    component = json.loads((HERE/'COMPONENT.json').read_text())
    if hashlib.sha256(raw).hexdigest() != component['base_sha256']:
        raise ValueError('core source changed: re-review and regenerate component before comparing')
    before = raw.decode()
    helper = '''def _package_inventory():
    """Fresh inventory with one metadata parse per distribution; no cache."""
    inventory = []
    for distribution in importlib.metadata.distributions():
        metadata = distribution.metadata
        name = metadata['Name']
        if name:
            inventory.append([name, metadata['Version']])
    return sorted(inventory)


'''
    after = before.replace('class Host:\n',helper+'class Host:\n',1).replace(
        "sorted([d.metadata['Name'], d.version] for d in importlib.metadata.distributions() if d.metadata['Name'])",
        '_package_inventory()',1)
    patch = ''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                    fromfile='a/jiuwenswarm/ccv2/ccv2.py',tofile='b/jiuwenswarm/ccv2/ccv2.py'))
    assert patch == (HERE/component['patch']).read_text()
    assert hashlib.sha256(patch.encode()).hexdigest() == component['patch_sha256']
    return before, after

def compare_host(output, inventory):
    from jiuwenswarm.ccv2.ccv2 import Host
    before, after = candidate_source()
    copy_path = output.parent/'isolated_candidate_ccv2.py'
    copy_path.write_text(after)
    module_name = 'jiuwenswarm.ccv2._inventory_once_benchmark_candidate'
    module_spec = importlib.util.spec_from_file_location(module_name,copy_path)
    candidate = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = candidate
    module_spec.loader.exec_module(candidate)
    source_bundle = HERE.parent/'cc_workflow_lab'
    hosts = {'baseline':Host(output.parent/'baseline-ccstore',python=sys.executable),
             'candidate':candidate.Host(output.parent/'candidate-ccstore',python=sys.executable)}
    releases = {mode:host.prepare(source_bundle) for mode,host in hosts.items()}
    assert releases['baseline'] == releases['candidate']
    fixture = json.loads((source_bundle/'fixtures/qualification.json').read_text())
    spec = {'receipts':fixture['receipts']}
    expected = None
    ids = []
    def invoke(mode):
        nonlocal expected
        receipt = hosts[mode].call(releases[mode],'analyze_receipts',{'spec':spec},grants=['process.exec'])
        assert receipt['state']=='succeeded', receipt
        assert receipt['provenance']['packages'] == inventory
        if expected is None:
            expected = receipt['outputs']
        assert receipt['outputs'] == expected
        ids.append({'mode':mode,'call':receipt['call']})
        return receipt
    warmups = {}
    for mode in hosts:
        warmups[mode], _ = timed(lambda mode=mode:invoke(mode))
    rows = []
    for mode in ['baseline','candidate','candidate','baseline']*2:
        elapsed, _ = timed(lambda mode=mode:invoke(mode))
        rows.append({'mode':mode,'elapsed_s':elapsed})
    # No grant may be manufactured by the optimization.
    denied = hosts['candidate'].call(releases['candidate'],'analyze_receipts',{'spec':spec},grants=[])
    assert denied['state']=='blocked' and denied['reason']=='DENIED'
    # A fresh call still records mutated current metadata, not a cached snapshot.
    # Real package files are not changed; fake mutation controls are in verify().
    return {'release':releases['baseline'],'baseline_source_sha256':hashlib.sha256(before.encode()).hexdigest(),
            'candidate_source_sha256':hashlib.sha256(after.encode()).hexdigest(),
            'warmups_s':warmups,'rounds':rows,'summary':comparison(rows),'receipt_calls':ids,
            'outputs_equal':True,'provenance_inventory_equal':True,
            'missing_grant_rejected':True,'denied_call':denied['call']}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output).resolve()
    if output.exists() or (output.parent/'baseline-ccstore').exists():
        raise ValueError('choose a new evidence directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    negative_checks=verify()
    operations={'baseline':lambda:repeated_metadata_reads(importlib.metadata.distributions),
                'candidate':lambda:fresh_inventory(importlib.metadata.distributions)}
    reference=operations['baseline']()
    assert operations['candidate']()==reference
    rows=[]
    for mode in ['baseline','candidate','candidate','baseline']*3:
        elapsed,result=timed(operations[mode])
        assert result==reference
        rows.append({'mode':mode,'elapsed_s':elapsed})
    memory={}
    for mode in operations:
        peak,result=traced(operations[mode])
        assert result==reference
        memory[mode]={'peak_python_bytes':peak,'scope':'separate traced Python allocations; not RSS or child memory'}
    # One extra parse would change equality if a custom Distribution.version
    # overrides standard-library semantics. This component supports the actual
    # importlib.metadata installed distributions, as verified here.
    data={'scope':'CPU actual current-environment fresh inventory; no cache or GPU claim',
          'python':sys.executable,'sys_path':sys.path,'platform':platform.platform(),
          'inventory_sha256':hashlib.sha256(json.dumps(reference,separators=(',',':')).encode()).hexdigest(),
          'distribution_rows':len(reference),'inventory':reference,
          'rounds':rows,'summary':comparison(rows),'memory':memory,'negative_checks':negative_checks,
          'host_comparison':compare_host(output,reference),'gpu_tested':False,'admission_granted':False}
    output.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'inventory':data['summary'],'host':data['host_comparison']['summary'],'output':str(output)},indent=2))

if __name__=='__main__':
    main()
