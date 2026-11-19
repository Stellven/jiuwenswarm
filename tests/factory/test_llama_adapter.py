"""Independent HTTP evidence parsing and bounded adapter contracts, CPU only."""
import copy
import json
from pathlib import Path
import pytest
from jiuwenswarm.factory import llama_adapter as a


def contract():
 return dict(adapter=a.ADAPTER,version=1,target='spark-gb10',tolerance='canonical-token-ids-and-finish',
  assets=dict(identity_path='/assets.json',identity_sha256='a'*64),
  workload=dict(pack='/models/first.gguf',model_root='/models',environment={'LLAMA_EXPERT_STREAMING':'0','LLAMA_EXPERT_RESIDENCY':'0'},
   argv=['-m','/models/first.gguf','--shard','/models/engram.gguf','--load-mode','mmap','--lazy-mode','on','--parallel','1','--ctx-size','4096','--threads','8','--threads-batch','8','--no-warmup'],
   requests=[dict(prompt='x',max_new_tokens=2)]*2),limits=dict(timeout_s=600,guard_gib=8,memory_bytes=96*2**30,cpus=8))


def records(c):
 r=[dict(event='launch',argv=['/opt/llamacpp/llama-server',*c['workload']['argv'],'--host','127.0.0.1','--port','18080'],executable_sha256='b'*64),dict(event='ready',status=200,body='{"status":"ok"}')]
 for i in range(2):
  r.append(dict(event='request',index=i,body=dict(prompt=[1,2],n_predict=2,temperature=0,seed=0,stream=True,return_tokens=True,cache_prompt=False)))
  for j in range(2):r.append(dict(event='sse',index=i,elapsed_ns=(j+1)*1000000,raw=json.dumps(dict(tokens=[3+j],content='a',stop=False))))
  r.append(dict(event='sse',index=i,elapsed_ns=3000000,raw=json.dumps(dict(tokens=[],content='',stop=True,stop_type='limit',tokens_predicted=2,tokens_cached=4,truncated=False,timings={}))))
  r.append(dict(event='request_end',index=i,elapsed_ns=4000000))
 return r


def test_canonical_outputs_and_client_clocks():
 c=contract();assert a.validate_contract(c)==c
 r=a.parse_protocol('\n'.join(map(json.dumps,records(c))),'',c)
 assert r['repeat_equal'] and r['requests'][0]['output_ids']==[3,4]
 assert r['requests'][0]['client_ttft_ms']==1 and r['requests'][0]['client_decode_tps']==1000
 assert r['scored_ab_improvement']=='not_established'


@pytest.mark.parametrize('case',['network','threads','memory','deadline','draft','switches','prompt'])
def test_invalid_admission(case):
 c=contract()
 if case=='network':c['workload']['argv']+=['--host','0.0.0.0']
 elif case=='threads':c['workload']['argv'][c['workload']['argv'].index('--threads')+1]='99'
 elif case=='memory':c['limits']['memory_bytes']=105*2**30
 elif case=='deadline':c['limits']['timeout_s']=99999
 elif case=='draft':c['workload']['argv']=['--model-draft','file']+c['workload']['argv']
 elif case=='switches':c['workload']['environment']['LLAMA_EXPERT_STREAMING']='1'
 else:c['workload']['requests'][0]['max_new_tokens']=True
 with pytest.raises(ValueError):a.validate_contract(c)


@pytest.mark.parametrize('case',['missing','clock','nan','changed_request','binary','count','truncated','activation'])
def test_raw_evidence_rejection(case):
 c=contract();r=records(c)
 if case=='missing':r=[x for x in r if x['event']!='request_end']
 elif case=='clock':r[4]['elapsed_ns']=1
 elif case=='nan':r[4]['elapsed_ns']=float('nan')
 elif case=='changed_request':r[2]['body']['temperature']=1
 elif case=='binary':r[0]['executable_sha256']='forged'
 elif case in ('count','truncated'):
  raw=json.loads(r[5]['raw']);raw['tokens_predicted' if case=='count' else 'truncated']=9;r[5]['raw']=json.dumps(raw)
 else:c['workload']['environment'].update(LLAMA_EXPERT_STREAMING='1',LLAMA_EXPERT_RESIDENCY='1')
 with pytest.raises(ValueError):a.parse_protocol('\n'.join(map(json.dumps,r)),'',c)
