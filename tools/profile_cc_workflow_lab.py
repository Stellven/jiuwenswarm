"""Profile one CPU Host call with retained receipts; no core host changes."""
from pathlib import Path
import argparse,cProfile,json,pstats,sys,time,tracemalloc
from jiuwenswarm.ccv2.ccv2 import Host
parser=argparse.ArgumentParser(description='CPU-only single-call Host profile; run separately from timing trials')
parser.add_argument('--measurements',required=True)
args=parser.parse_args()
measurements=Path(args.measurements).resolve()
root=measurements.parent
data=json.loads(measurements.read_text())
host=Host(root/'ccstore',python=sys.executable)
fixture=json.loads((Path(__file__).resolve().parents[1]/'jiuwenswarm/factory/ccs/cc_workflow_lab/fixtures/qualification.json').read_text())
warm=host.call(data['cold_seal']['release'],'analyze_receipts',{'spec':{'receipts':fixture['receipts'][:3]}},grants=['process.exec'])
assert warm['state']=='succeeded'
profiler=cProfile.Profile();profiler.enable()
r=host.call(data['cold_seal']['release'],'analyze_receipts',{'spec':{'receipts':fixture['receipts'][:3]}},grants=['process.exec'])
profiler.disable();assert r['state']=='succeeded'
stats=pstats.Stats(profiler)
rows=[{'file':key[0],'line':key[1],'function':key[2],'primitive_calls':value[0],'calls':value[1],'self_s':value[2],'cumulative_s':value[3]} for key,value in stats.stats.items()]
rows.sort(key=lambda x:x['cumulative_s'],reverse=True)
tracemalloc.start();start=time.perf_counter()
m=host.call(data['cold_seal']['release'],'analyze_receipts',{'spec':{'receipts':fixture['receipts'][:3]}},grants=['process.exec'])
elapsed=time.perf_counter()-start;current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
output={'scope':'Single warm-process fresh actual Host call cProfile after one unprofiled warmup; extra tracemalloc role measured separately from ABBA because profiling changes overhead','receipt_call':r['call'],'profile_total_s':stats.total_tt,'top_cumulative':rows[:35],'host_traced_allocation_role':{'elapsed_s':elapsed,'peak_python_bytes':peak,'current_python_bytes':current,'receipt_call':m['call'],'scope':'Host Python only; child memory not included'}}
(root/'host-profile.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
