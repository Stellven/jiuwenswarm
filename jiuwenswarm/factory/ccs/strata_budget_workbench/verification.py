import copy,json
from pathlib import Path
from component import TOOLS

def verify():
 calls=json.loads(Path(__file__).with_name('EXAMPLES.json').read_text())['calls']
 original=copy.deepcopy(calls[0]['inputs']['request']['profile'])
 out=TOOLS['apply'](calls[0]['inputs']['request'])
 assert calls[0]['inputs']['request']['profile']==original
 want=copy.deepcopy(original);want['environment']['DS4_EXPERT_BUDGET_BYTES']='68000000000'
 assert out['profile']==want and out['admission_granted'] is False
 for bad in [True,0,-1,2**40,'68000000000']:
  try:TOOLS['apply'](dict(profile=original,budget_bytes=bad))
  except ValueError:pass
  else:raise AssertionError('Invalid budget accepted')
 request=calls[1]['inputs']['request'];assert TOOLS['verify_startup'](request)['resident_experts']==8000
 for text in [request['stderr'].replace('safe=80000000000','safe=60000000000'),request['stderr'].replace('layer=0 ','layer=1 '),request['stderr'].replace('fnv1a64=0000000000000000','fnv1a64=0000000000000001')]:
  try:TOOLS['verify_startup'](dict(stderr=text,budget_bytes=68000000000))
  except ValueError:pass
  else:raise AssertionError('Invalid placement accepted')
 m=TOOLS['summarize_memory'](calls[2]['inputs']['request']);assert m['cgroup_kernel_peak_bytes']==120 and m['host_sampled_min_available_bytes']==1000
 assert TOOLS['summarize_memory'](dict(samples=[{}]))['cgroup_kernel_peak_bytes'] is None
 return dict(passed=True,scope='CPU reference only')
if __name__=='__main__':print(json.dumps(verify()))
