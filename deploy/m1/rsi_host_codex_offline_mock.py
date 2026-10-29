from pathlib import Path
import json,hashlib,socket,threading,sys,os
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
if sys.flags.optimize:
 raise RuntimeError('Offline mock must run with assertions enabled')
CAPTURE=Path(sys.argv[1]).resolve()
assert not CAPTURE.exists()
CAPTURE.open('xb').close()
EXPECTED_SYSTEM='Execute the supplied governed instruction. Tools are unavailable.'
PUBLIC_USER='Public offline test: return exactly {"ok":true}.'
def h(raw):return hashlib.sha256(raw).hexdigest()
def shape(tool):
 result={'type':tool.get('type'),'name':tool.get('name')}
 if isinstance(tool.get('function'),dict):
  result['function_name']=tool['function'].get('name');params=tool['function'].get('parameters') or {}
 else:params=tool.get('parameters') or {}
 if isinstance(params,dict):result.update(parameter_names=sorted((params.get('properties') or {}).keys()),required=params.get('required',[]))
 if isinstance(tool.get('tools'),list):result['tools']=[shape(v) for v in tool['tools'] if isinstance(v,dict)]
 return result
def additional_shape(value):
 result=[]
 def walk(item,path):
  if isinstance(item,dict):
   if 'name' in item or 'type' in item:
    entry={'path':path,'field_names':sorted(item)}
    for key in ('name','type'):
     if isinstance(item.get(key),str):entry[key]=item[key]
    if isinstance(item.get('parameters'),dict):entry['parameter_names']=sorted((item['parameters'].get('properties') or {}).keys())
    result.append(entry)
   for key,child in item.items():
    if key not in {'description','text','instructions','input'}:walk(child,path+'.'+key)
  elif isinstance(item,list):
   for index,child in enumerate(item):walk(child,path+'['+str(index)+']')
 walk(value,'additional_tools')
 return result
def recursive_tool_locations(value):
 result=[]
 def walk(item,path):
  if isinstance(item,dict):
   for key,child in item.items():
    if key in {'tools','functions'} and isinstance(child,list):
     result.append({'path':path+'.'+key,'count':len(child),'entries':[shape(t) for t in child if isinstance(t,dict)]})
    if isinstance(child,(dict,list)):walk(child,path+'.'+key)
  elif isinstance(item,list):
   for index,child in enumerate(item):walk(child,path+'['+str(index)+']')
 walk(value,'$')
 return result
class Server(ThreadingHTTPServer):
 allow_reuse_address=False
 def server_bind(self):
  super().server_bind()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  size=int(self.headers.get('Content-Length','0'));assert 0<size<=1024*1024
  raw=self.rfile.read(size);value=json.loads(raw)
  tools=value.get('tools') or [];instructions=value.get('instructions')
  roles=[]
  for item in value.get('input',[]):
   if not isinstance(item,dict):continue
   content=item.get('content');text=content if isinstance(content,str) else ''.join(part.get('text','') for part in content if isinstance(part,dict) and isinstance(part.get('text'),str)) if isinstance(content,list) else ''
   roles.append({'role':item.get('role'),'type':item.get('type'),'content_chars':len(text),'content_sha256':h(text.encode())})
  def text(item):
   content=item.get('content',[])
   return content if isinstance(content,str) else ''.join(part.get('text','') for part in content if isinstance(part,dict) and isinstance(part.get('text'),str)) if isinstance(content,list) else ''
  developer_texts=[text(item) for item in value.get('input',[]) if isinstance(item,dict) and item.get('role')=='developer']
  user_texts=[text(item) for item in value.get('input',[]) if isinstance(item,dict) and item.get('role')=='user']
  request={'reasoning_effort':(value.get('reasoning') or {}).get('effort'),'actual_system_guard_present':any(EXPECTED_SYSTEM in item for item in developer_texts),'expected_system_sha256':h(EXPECTED_SYSTEM.encode()),'exact_public_user_present':PUBLIC_USER in user_texts,'cookie_present':'Cookie' in self.headers,'proxy_authorization_present':'Proxy-Authorization' in self.headers,'path':self.path,'field_names':sorted(value),'model':value.get('model'),
   'recursive_tool_locations':recursive_tool_locations(value),'functions_count':len(value.get('functions') or []),'tools_count':len(tools),'tools':[shape(t) for t in tools if isinstance(t,dict)],
   'additional_tools':[additional_shape(item) for item in value.get('input',[]) if isinstance(item,dict) and item.get('type')=='additional_tools'],
   'instructions_chars':len(instructions) if isinstance(instructions,str) else None,
   'instructions_sha256':h(instructions.encode()) if isinstance(instructions,str) else None,
   'input_shape':roles,'authorization_present':'Authorization' in self.headers,'mock_generation_performed':False}
  with CAPTURE.open('ab') as stream:
   stream.write((json.dumps(request,sort_keys=True)+'\n').encode());stream.flush();os.fsync(stream.fileno())
  payload=b'{"error":{"message":"Offline mock rejects generation","type":"invalid_request_error","code":"offline_mock_400"}}'
  self.send_response(400);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 def do_GET(self):
  self.send_response(400);self.end_headers()

server=Server(('127.0.0.1',5175),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
watchdog=threading.Timer(45,lambda:os._exit(3));watchdog.daemon=True;watchdog.start()
print(json.dumps({'status':'MOCK_READY','host':'127.0.0.1','port':5175}),flush=True)
try:sys.stdin.buffer.read(1)
finally:server.shutdown();server.server_close();thread.join(timeout=3);watchdog.cancel()
