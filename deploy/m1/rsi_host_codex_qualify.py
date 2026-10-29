"""Actual pinned 0.163 offline wire measurement; mock400, no account API/auth."""
from pathlib import Path
import asyncio,hashlib,importlib.util,json,tempfile,time,subprocess
import sys
if sys.flags.optimize:
 raise RuntimeError('Offline qualification must run with assertions enabled')
from collections import Counter
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--binary',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
SOURCE=args.source.resolve(strict=True); BINARY=args.binary.resolve(strict=True)
OUTPUT=args.output.resolve(); E=OUTPUT.parent
assert not OUTPUT.exists()
EXPECTED='2692c8c7bb2cf8b0aefe638741fc90236f4b824c59578ce84994f9de58200993'
assert hashlib.sha256(BINARY.read_bytes()).hexdigest()==EXPECTED
HELPER_SHA=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
CATALOG=SOURCE.parent/'resources'/'host_codex'/'model_catalog.json'
CATALOG_SHA='4b7773a08802e8e6bed67235babc173657784a3e422026688965afd6837f4364'
assert hashlib.sha256(CATALOG.read_bytes()).hexdigest()==CATALOG_SHA
spec=importlib.util.spec_from_file_location('offline_host_helper',SOURCE);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)

def h(raw):return hashlib.sha256(raw).hexdigest()

async def probe(label):
 with tempfile.TemporaryDirectory(prefix='ai4r-codex-0163-offline-') as directory:
  root=Path(directory);home=root/'codex-home';work=root/'empty-work';home.mkdir();work.mkdir()
  env=helper.child_environment(root);env['CODEX_HOME']=str(home);env['HOME']=str(root);env['USERPROFILE']=str(root)
  env['APPDATA']=str(root/'AppData/Roaming');env['LOCALAPPDATA']=str(root/'AppData/Local')
  catalog_path=root/'native-no-tools-catalog.json';catalog_path.write_bytes(CATALOG.read_bytes())
  argv=helper.arguments(BINARY,'medium',catalog_path)
  command_line_chars=len(subprocess.list2cmdline(argv));assert command_line_chars<32767
  process=await asyncio.create_subprocess_exec(*argv,cwd=work,env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=2*1024*1024,creationflags=0x08000000)
  methods=Counter();seq=0
  async def rpc(method,params):
   nonlocal seq
   seq+=1;ident=seq;process.stdin.write((json.dumps({'id':ident,'method':method,'params':params})+'\n').encode());await process.stdin.drain()
   while True:
    raw=await asyncio.wait_for(process.stdout.readline(),15)
    assert raw,'Native AppServer exited before response'
    obj=json.loads(raw)
    if obj.get('method'):methods[obj['method']]+=1
    if obj.get('id')==ident and 'method' not in obj:
     assert 'error' not in obj, {'stage':method,'error_code':(obj.get('error') or {}).get('code')}
     return obj.get('result')
  start=len(read_captured())
  try:
   await rpc('initialize',{'clientInfo':{'name':'ai4r_host_codex','version':'1'},'capabilities':{'experimentalApi':True}})
   process.stdin.write(b'{"method":"initialized"}\n');await process.stdin.drain()
   config={**helper.native_thread_configuration('medium',catalog_path),
    'model_providers.ai4r_governed.name':'AI4Research governed subscription',
    'model_providers.ai4r_governed.wire_api':'responses','model_providers.ai4r_governed.requires_openai_auth':False,
    'model_providers.ai4r_governed.base_url':'http://127.0.0.1:5175/v1','model_providers.ai4r_governed.supports_websockets':False,
    'model_providers.ai4r_governed.request_max_retries':0,'model_providers.ai4r_governed.stream_max_retries':0}
   result=await rpc('thread/start',{'cwd':str(work),'sandbox':'read-only','approvalPolicy':'never','modelProvider':'ai4r_governed',
    'model':'gpt-6.1-sol','ephemeral':True,'allowProviderModelFallback':False,'developerInstructions':helper.SYSTEM,'config':config})
   assert result.get('model')=='gpt-6.1-sol' and result.get('reasoningEffort')=='medium'
   tid=result['thread']['id']
   await rpc('turn/start',{'threadId':tid,'input':[{'type':'text','text':'Public offline test: return exactly {"ok":true}.'}],
    'model':'gpt-6.1-sol','approvalPolicy':'never'})
   deadline=time.monotonic()+12
   while time.monotonic()<deadline:
    raw=await asyncio.wait_for(process.stdout.readline(),max(.01,deadline-time.monotonic()))
    if not raw:break
    value=json.loads(raw);method=value.get('method');methods[method or '<rpc-response>']+=1
    if method=='turn/completed':break
   captured=read_captured()[start:]
   assert captured and all(not item['authorization_present'] for item in captured)
   assert len(captured)==1
   wire=captured[0]
   assert wire['recursive_tool_locations']==[] and wire['additional_tools']==[] and wire['tools_count']==0 and wire['functions_count']==0
   assert wire['model']=='gpt-6.1-sol' and wire['reasoning_effort']=='medium' and wire['exact_public_user_present'] and wire['actual_system_guard_present']
   assert wire['expected_system_sha256']==h(helper.SYSTEM.encode()) and wire['cookie_present']==False and wire['proxy_authorization_present']==False
   assert h(SOURCE.read_bytes())==HELPER_SHA
   assert not (home/'auth.json').exists() and not (root/'auth.json').exists()
   return {'label':label,'resolved_model':result.get('model'),'resolved_effort':result.get('reasoningEffort'),
    'windows_quoted_command_line_chars':command_line_chars,'actual_builder_names':['arguments','native_thread_configuration'],'catalog_source_sha256':CATALOG_SHA,'method_counts':dict(methods),'http_requests':captured,'account_rpc_sent':False,'real_provider_called':False,'home_was_empty':True}
  finally:
   if process.returncode is None:process.kill()
   await asyncio.wait_for(process.wait(),3)
def read_captured():
 path=OUTPUT.with_suffix('.requests.jsonl')
 return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]
async def main():
 mock=await asyncio.create_subprocess_exec(__import__('sys').executable,'-B',
  str(Path(__file__).with_name('rsi_host_codex_offline_mock.py')),str(OUTPUT.with_suffix('.requests.jsonl')),
  stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,creationflags=0x08000000)
 try:
  ready=json.loads(await asyncio.wait_for(mock.stdout.readline(),15));assert ready['status']=='MOCK_READY'
  hardened=await probe('actual-captured-source-helper-builders')
  result={'schema':'ai4r-offline-native-tools-wire-proof:1','native_version':'0.163.0','native_binary_sha256':EXPECTED,
   'helper_source_sha256':h(SOURCE.read_bytes()),'mock_endpoint':'http://127.0.0.1:5175/v1','mock_status':400,
   'real_auth_or_account_files_used':False,'real_generation_performed':False,'cases':[hardened]}
  OUTPUT.open('x',encoding='utf-8').write(json.dumps(result,indent=2)+'\n')
  print(json.dumps({'status':'OFFLINE_NATIVE_WIRE_PROVED','proof_sha256':h(OUTPUT.read_bytes()),'helper_sha256':HELPER_SHA,'model_calls':0,'proof':str(OUTPUT)}))
 finally:
  if mock.stdin is not None:mock.stdin.close()
  try:await asyncio.wait_for(mock.wait(),5)
  except TimeoutError:
   mock.kill();await mock.wait()
if __name__=='__main__':asyncio.run(main())
