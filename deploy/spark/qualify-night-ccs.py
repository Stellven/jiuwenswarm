"""Finite CPU qualification smoke for the new standalone night-method packages.

No GPU/native binary invocation, Docker, network or engine execution. Branch
workbench integration is exercised separately through tests and live Controller.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from jiuwenswarm.ccv2.ccv2 import Host,load

CAPS={'strata_budget_workbench':['apply','verify_startup','summarize_memory'],
      'memory_residency_lab':['plan','verify'], 'gpu_kernel_lab':['evaluate'],
      'cc_workflow_lab':['analyze_receipts','design_workflow','benchmark_fixture','run_batch']}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    host=Host(out/'ccstore',session_grants=['process.exec'],python=sys.executable)
    results=[]
    for name,caps in CAPS.items():
        package=REPO/'jiuwenswarm/factory/ccs'/name
        examples=json.loads((package/'EXAMPLES.json').read_text())
        if 'calls' in examples:examples={c['capability']:c['inputs'] for c in examples['calls']}
        release=host.prepare(package)
        start=time.monotonic()
        checked=subprocess.run([sys.executable,str(package/'verification.py')],capture_output=True,text=True,timeout=30)
        record=dict(package=name,release=release,verification=dict(returncode=checked.returncode,stdout=checked.stdout,stderr=checked.stderr,elapsed_s=time.monotonic()-start),calls=[])
        for cap in caps:
            start=time.monotonic();receipt=host.call(release,cap,examples[cap]);record['calls'].append(dict(capability=cap,elapsed_s=time.monotonic()-start,receipt=receipt))
        record['source_sha256']={str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
        (out/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n');results.append(record)
    passed=all(r['verification']['returncode']==0 and all(c['receipt']['state']=='succeeded' for c in r['calls']) for r in results)
    summary=dict(passed=passed,packages=len(results),native_cpu_calls=sum(len(r['calls']) for r in results),gpu_calls=0,model_acceptance=False,scope='CPU reference verification and native CC transport only',releases={r['package']:r['release'] for r in results})
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
    if not passed:raise SystemExit(1)
if __name__=='__main__':main()
