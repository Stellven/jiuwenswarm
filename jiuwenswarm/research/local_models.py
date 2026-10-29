"""Operator-approved private model endpoints. No public HTTP policy bypass.

Only a protected catalog chooses the SSH backend and local RPC transport. User
settings select an existing ID; they cannot supply URLs, paths or commands.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import os
from pathlib import Path,PurePosixPath,PureWindowsPath
import re
import stat
from urllib.parse import urlsplit
import uuid

from .contracts import ResearchError
from .providers import ProviderError
from .bridge import observed_usage

PROTOCOL = "ai4r-local-model:1"
CODEX_EFFORTS = frozenset({'medium'})
CODEX_BACKEND_FIELDS = {'kind','host_python','codex_executable','codex_sha256','account_fingerprint','working_directory'}
CODEX_MODEL_FIELDS = {'id','name','model_name','revision','enabled','context_window','max_prompt_bytes','timeout_s','reasoning_effort'}
CODEX_BUNDLE_FIELDS = {'schema','requested_model','account_fingerprint','binary_sha256','reasoning_effort',
                       'thread_start','turn_start','turn_completed','wire_frames','error_code','outcome'}
CODEX_ERRORS = {None,'auth_failed','invalid_request','provider_error','timeout','network_error','invalid_output','CONTAINMENT_UNCERTAIN'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()


def require(ok,reason="Invalid operator local-model catalog"):
    if not ok: raise ResearchError("validation",reason)


def native_absolute_path(value,*,posix_only=False):
    if (not isinstance(value,str) or not value or '\\' in value or any(ord(c)<32 or 127<=ord(c)<=159 for c in value)
            or value.startswith('//') or any(part in {'.','..'} for part in value.split('/'))):return False
    if value.startswith('/'):
        return str(PurePosixPath(value))==value
    return (not posix_only and re.fullmatch(r'[A-Z]:/[^:]+',value) is not None
            and PureWindowsPath(value).is_absolute() and str(PureWindowsPath(value)).replace('\\','/')==value)


def protected_json(path,*,owner_uid,private=False,max_bytes=128*1024):
    path=Path(path)
    require(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),"Invalid local-model file custody")
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=max_bytes,"Invalid local-model file custody")
        if os.name=="posix":
            require(info.st_uid==owner_uid and not info.st_mode & (0o077 if private else 0o022),"Invalid local-model file custody")
        with os.fdopen(fd,"rb",closefd=False) as stream: raw=stream.read(max_bytes+1)
    finally: os.close(fd)
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,"Duplicate local-model JSON field")
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def validate_catalog(value):
    require(isinstance(value,dict) and set(value)=={"schema","gateway_id","backend","transport","models"}
            and value["schema"]=="ai4r-local-model-catalog:1")
    require(isinstance(value["gateway_id"],str) and re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}",value["gateway_id"]))
    backend=value["backend"]
    require(isinstance(backend,dict))
    codex=backend.get('kind')=='host-codex-app-server'
    if codex:
        require(set(backend)==CODEX_BACKEND_FIELDS)
        require(native_absolute_path(backend['host_python'],posix_only=True))
        for field in ('codex_executable','working_directory'):require(native_absolute_path(backend[field]))
        for field in ('codex_sha256','account_fingerprint'):
            require(isinstance(backend[field],str) and re.fullmatch('[a-f0-9]{64}',backend[field]))
    else:
        require(set(backend)=={"kind","target","base_url"} and backend["kind"]=="ssh-loopback-openai")
        require(isinstance(backend["target"],str) and len(backend["target"])<=255
                and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(?:@[A-Za-z0-9][A-Za-z0-9.-]*)?",backend["target"]))
        url=urlsplit(backend["base_url"])
        require(url.scheme=="http" and url.hostname in {"127.0.0.1","::1"}
                and url.port is not None and 1<=url.port<=65535 and url.path=="/v1"
                and not (url.username or url.password or url.query or url.fragment),"SSH model upstream must be same-host loopback /v1")
    transport=value["transport"]
    require(isinstance(transport,dict) and set(transport)=={"socket_path","session_file","peer_uid","socket_mode"})
    require(type(transport["peer_uid"]) is int and transport["peer_uid"]>=0
            and type(transport["socket_mode"]) is int and transport["socket_mode"] in {0o600,0o660})
    for key in ("socket_path","session_file"):
        path=transport[key]
        require(isinstance(path,str) and path.startswith("/") and "\\" not in path and "/../" not in path
                and not any(ord(c)<32 for c in path) and str(PurePosixPath(path))==path
                and all(p not in {'.','..'} for p in PurePosixPath(path).parts),"Canonical absolute local-model transport path required")
    require(transport["socket_path"]!=transport["session_file"])
    require(isinstance(value["models"],list) and len(value["models"])<=32)
    seen=set()
    fields={"id","name","model_name","revision","enabled","context_window","max_output_tokens","max_prompt_bytes","timeout_s","temperature","enable_thinking"}
    if codex:fields=CODEX_MODEL_FIELDS
    for model in value["models"]:
        require(isinstance(model,dict) and set(model)==fields)
        require(isinstance(model["id"],str) and re.fullmatch(r"local-[a-z0-9][a-z0-9_.-]{0,55}",model["id"]) and model["id"] not in seen)
        seen.add(model["id"])
        for key in ("name","model_name","revision"):
            require(isinstance(model[key],str) and 0<len(model[key])<=256 and not any(ord(c)<32 for c in model[key]))
        require(type(model["enabled"]) is bool)
        if codex:require(isinstance(model['reasoning_effort'],str) and model['reasoning_effort'] in CODEX_EFFORTS)
        else:require(type(model['enable_thinking']) is bool)
        bounds=(("context_window",1048576),("max_prompt_bytes",256*1024))
        if not codex:bounds+=(("max_output_tokens",32768),)
        for key,maximum in bounds:
            require(type(model[key]) is int and 0<model[key]<=maximum)
        if not codex:require(model["max_output_tokens"]<=model["context_window"])
        numbers=(("timeout_s",1,600),) if codex else (("timeout_s",1,600),("temperature",0,2))
        for key,low,high in numbers:
            require(type(model[key]) in {int,float} and math.isfinite(model[key]) and low<=model[key]<=high)
    return copy.deepcopy(value)


def native_codex_response(raw,binding,*,prompt):
    """Validate original native wire evidence; never manufacture HTTP/model data."""
    from .router_client import decode_frame
    require(isinstance(raw,str) and len(raw.encode())<=1024*1024)
    bundle=decode_frame(raw.encode())
    from .local_model_codex import unpack_bundle
    require(isinstance(bundle,dict))
    incomplete=bundle.get('schema')=='ai4r-host-codex-response:2' and isinstance(bundle.get('evidence'),dict) and bundle['evidence'].get('full_original_trace') is False
    bundle=unpack_bundle(bundle)
    backend,policy=binding['backend'],binding['model']
    require(isinstance(bundle,dict) and set(bundle)==CODEX_BUNDLE_FIELDS)
    require(bundle['schema']=='ai4r-host-codex-response:1'
            and bundle['requested_model']==policy['model_name']
            and bundle['reasoning_effort']==policy['reasoning_effort'])
    require(bundle['outcome'] in ('completed','failed','outcome_unknown')
            and (bundle['error_code'] is None or isinstance(bundle['error_code'],str))
            and bundle['error_code'] in CODEX_ERRORS)
    require(all(bundle[k] is None or isinstance(bundle[k],dict) for k in ('thread_start','turn_start','turn_completed')))
    require(isinstance(bundle['wire_frames'],list))
    early_failure=(bundle['outcome']=='failed' and not bundle['wire_frames']
        and all(bundle[k] is None for k in ('thread_start','turn_start','turn_completed'))
        and bundle['error_code'] not in {None,'CONTAINMENT_UNCERTAIN'})
    for field,key in (('account_fingerprint','account_fingerprint'),('binary_sha256','codex_sha256')):
        require(bundle[field]==backend[key] or early_failure and bundle[field] is None)
    frames=[]
    server_requests=[];refusals=[]
    for wire in bundle['wire_frames']:
        require(isinstance(wire,dict) and set(wire)=={'direction','raw'}
                and wire['direction'] in ('out','in') and isinstance(wire['raw'],str))
        parsed=decode_frame(wire['raw'].encode())
        require(isinstance(parsed,dict))
        method=parsed.get('method','')
        require(isinstance(method,str) and method!='model/rerouted')
        incoming_request=wire['direction']=='in' and bool(method) and 'id' in parsed
        refusal=wire['direction']=='out' and not method
        if wire['direction']=='out':require(method in {'thread/start','turn/start','turn/interrupt'} or refusal)
        if incoming_request:server_requests.append(parsed)
        if refusal:refusals.append(parsed)
        # A server request is accepted only as evidence of an exact closed
        # refusal followed by this turn's actual terminal, never authorization.
        if not incoming_request:
            require(not any(part in method.lower() for part in ('commandexecution','command/','filechange','tool')))
        item=(parsed.get('params') or {}).get('item') if isinstance(parsed.get('params'),dict) else None
        if isinstance(item,dict):require(item.get('type') in {'agentMessage','reasoning','userMessage','contextCompaction'})
        frames.append((wire['direction'],parsed))
    starts={}
    for name in ('thread/start','turn/start'):
        requests=[f for direction,f in frames if direction=='out' and f.get('method')==name]
        require(len(requests)<=1)
        if requests:
            req=requests[0];params=req.get('params')
            require(isinstance(params,dict) and params.get('model')==policy['model_name'])
            require(type(req.get('id')) in {str,int})
            starts[name]=req
            if name=='thread/start':
                require(isinstance(params.get('config'),dict)
                        and params['config'].get('model_reasoning_effort')==policy['reasoning_effort'])
    observation={'identity':{'effective':None,'basis':'effective model not observed'},
                 'usage':observed_usage(),'provider_request_id':None,'observed_runtime':True}
    preturn_rejected=(bundle['outcome']=='failed' and bundle['error_code']=='invalid_output'
        and 'turn/start' not in starts and bundle['turn_start'] is None and bundle['turn_completed'] is None)
    thread_id=turn_id=None
    for name,key in (('thread/start','thread_start'),('turn/start','turn_start')):
        result=bundle[key]
        if result is None:continue
        require(name in starts)
        replies=[f for direction,f in frames if direction=='in' and f.get('id')==starts[name]['id'] and 'result' in f]
        require(len(replies)==1 and replies[0]['result']==result and 'error' not in replies[0])
        if name=='thread/start':
            require(preturn_rejected or result.get('model')==policy['model_name']
                    and result.get('reasoningEffort')==policy['reasoning_effort'] and isinstance(result.get('thread'),dict))
            thread_id=(result.get('thread') or {}).get('id') if isinstance(result.get('thread'),dict) else None
            require(preturn_rejected or isinstance(thread_id,str) and bool(thread_id))
            if isinstance(result.get('model'),str) and result['model']:
                observation['identity']={'effective':result['model'],'basis':
                    'host Codex app-server pre-turn model resolution' if preturn_rejected else 'host Codex app-server resolved model'}
        else:
            require(isinstance(result.get('turn'),dict))
            turn_id=result['turn'].get('id');require(isinstance(turn_id,str) and bool(turn_id))
            observation['provider_request_id']=turn_id
    turn_request=starts.get('turn/start')
    if turn_request:
        params=turn_request['params']
        require(thread_id is not None and params.get('threadId')==thread_id
                and ('effort' not in params or params['effort']==policy['reasoning_effort']))
        inputs=params.get('input')
        require(isinstance(inputs,list) and len(inputs)==1 and isinstance(inputs[0],dict)
                and inputs[0].get('type')=='text' and inputs[0].get('text')==prompt
                and set(inputs[0])<={'type','text','text_elements'} and inputs[0].get('text_elements',[])==[])
    if server_requests or refusals:
        require(bundle['outcome'] in {'failed','outcome_unknown'}
                and bundle['error_code'] in {'provider_error','invalid_output','CONTAINMENT_UNCERTAIN'}
                and (bundle['outcome']=='outcome_unknown' or bundle['turn_completed'] is not None)
                and thread_id is not None and turn_id is not None)
        require(len(server_requests)==len(refusals))
        request_ids=[]
        for request in server_requests:
            params=request.get('params')
            ident=request.get('id')
            require(type(ident) in {str,int} and ident not in request_ids
                    and isinstance(params,dict) and params.get('threadId')==thread_id
                    and params.get('turnId')==turn_id)
            request_ids.append(ident)
            matches=[reply for reply in refusals if type(reply.get('id')) is type(ident) and reply.get('id')==ident]
            require(len(matches)==1 and set(matches[0])=={'id','error'}
                    and matches[0]['error']=={'code':-32601,'message':'Tools and approvals are unavailable.'})
            request_position=next(i for i,(direction,frame) in enumerate(frames) if frame is request)
            refusal_position=next(i for i,(direction,frame) in enumerate(frames) if frame is matches[0])
            terminal_positions=[i for i,(direction,frame) in enumerate(frames)
                if direction=='in' and frame.get('method')=='turn/completed' and frame.get('params')==bundle['turn_completed']]
            require(request_position < refusal_position
                    and (bundle['turn_completed'] is None or len(terminal_positions)==1 and refusal_position < terminal_positions[0]))
    interrupts=[frame for direction,frame in frames if direction=='out' and frame.get('method')=='turn/interrupt']
    require(len(interrupts)<=1 and all(frame.get('params')=={'threadId':thread_id,'turnId':turn_id} for frame in interrupts))
    usages=[];items=[]
    for direction,frame in frames:
        if direction!='in':continue
        params=frame.get('params')
        if not isinstance(params,dict):continue
        if frame.get('method') in {'thread/tokenUsage/updated','item/completed','turn/completed'}:
            require(thread_id is not None and params.get('threadId')==thread_id)
            if turn_id is not None:require(params.get('turnId',turn_id)==turn_id)
        if frame.get('method')=='thread/tokenUsage/updated':
            usage=params.get('tokenUsage');require(isinstance(usage,dict) and isinstance(usage.get('last'),dict))
            usages.append(usage['last'])
        if frame.get('method')=='item/completed' and isinstance(params.get('item'),dict):items.append(params['item'])
    if usages:
        usage=usages[-1]
        observation['usage']=observed_usage({'input_tokens':usage.get('inputTokens'),'output_tokens':usage.get('outputTokens')})
    terminal=bundle['turn_completed']
    if incomplete and bundle['outcome']=='failed':
        require(terminal is not None and thread_id is not None and turn_id is not None and turn_request is not None)
    if terminal is not None:
        require(thread_id is not None and turn_id is not None and terminal.get('threadId')==thread_id)
        notifications=[f for direction,f in frames if direction=='in' and f.get('method')=='turn/completed' and f.get('params')==terminal]
        require(len(notifications)==1 and isinstance(terminal.get('turn'),dict) and terminal['turn'].get('id')==turn_id
                and terminal['turn'].get('status') in {'completed','interrupted','failed'})
        require(terminal.get('turnId',turn_id)==turn_id)
        terminal_items=terminal['turn'].get('items')
        if terminal_items is not None:
            require(isinstance(terminal_items,list))
            if terminal_items:items=terminal_items
    for item in items:
        require(isinstance(item,dict) and item.get('type') in {'agentMessage','reasoning','userMessage','contextCompaction'})
    texts=[item.get('text') for item in items if item.get('type')=='agentMessage']
    require(all(isinstance(text,str) for text in texts))
    text=''.join(texts)
    if bundle['outcome']=='completed':
        require(bundle['error_code'] is None and terminal is not None
                and terminal['turn'].get('status')=='completed' and not terminal['turn'].get('error')
                and bool(text.strip()) and thread_id is not None and turn_id is not None)
    elif bundle['outcome']=='failed':
        require(bundle['error_code'] not in {None,'CONTAINMENT_UNCERTAIN'}
                and (turn_request is None or terminal is not None))
    return bundle,observation,text


class LocalModelCatalog:
    def __init__(self,path=None,*,owner_uid=0):
        self.path=Path(path) if path else None
        self.owner_uid=owner_uid

    def snapshot(self):
        if self.path is None: return None
        return validate_catalog(protected_json(self.path,owner_uid=self.owner_uid))

    def resolve(self,endpoint_id,binding_sha256=None):
        document=self.snapshot()
        require(document is not None,"Local model endpoint is not installed")
        matches=[m for m in document["models"] if m["id"]==endpoint_id]
        require(len(matches)==1 and matches[0]["enabled"],"Local model endpoint is unavailable or revoked")
        binding={"gateway_id":document["gateway_id"],"backend":document["backend"],
                 "transport":document["transport"],"model":matches[0]}
        digest=hashlib.sha256(canonical(binding)).hexdigest()
        require(binding_sha256 is None or digest==binding_sha256,"Frozen local-model endpoint changed")
        return {**binding,"binding_sha256":digest}

    def models(self):
        document=self.snapshot()
        return [] if document is None else document["models"]


class LocalModelClient:
    def __init__(self,binding,*,rpc_factory=None):
        self.binding=copy.deepcopy(binding)
        self.rpc_factory=rpc_factory
        self.trace=[]

    def preflight(self):
        transport=self.binding["transport"]
        path=Path(transport["socket_path"])
        try:
            require(os.name=="posix" and not any(p.is_symlink() for p in (path,*path.parents)))
            meta=path.lstat()
            require(stat.S_ISSOCK(meta.st_mode) and meta.st_uid==transport["peer_uid"]
                    and stat.S_IMODE(meta.st_mode)==transport["socket_mode"])
            session=protected_json(transport["session_file"],owner_uid=os.geteuid(),private=True,max_bytes=16384)
            require(isinstance(session,dict) and set(session)=={"session_id","capability"}
                    and all(isinstance(v,str) and 16<=len(v)<=256 for v in session.values()))
        except (OSError,ValueError,ResearchError):
            raise ProviderError("auth_failed") from None
        return session

    async def invoke(self,prompt,*,timeout_s,call_function):
        model=self.binding["model"]
        if (call_function not in {"worker","planner"} or not isinstance(prompt,str) or not prompt.strip()
                or len(prompt.encode())>model["max_prompt_bytes"] or type(timeout_s) not in {int,float}
                or not math.isfinite(timeout_s) or timeout_s<=0):
            raise ProviderError("invalid_request")
        session=self.preflight()
        if self.rpc_factory is None:
            from .private_rpc import PrivateRPCClient
            factory=PrivateRPCClient
        else: factory=self.rpc_factory
        transport=self.binding["transport"]
        client=factory(transport["socket_path"],protocol=PROTOCOL,peer_uid=transport["peer_uid"],
                       socket_mode=transport["socket_mode"],**session)
        request_id=uuid.uuid4().hex
        request={"request_id":request_id,"endpoint_id":model["id"],"binding_sha256":self.binding["binding_sha256"],
                 "model":model["model_name"],"prompt":prompt,"timeout_s":min(timeout_s,model["timeout_s"])}
        self.trace.append(("out","local-model/request-prepared",copy.deepcopy(request)))
        observation={"identity":{"effective":None,"basis":"effective model not observed"},
                     "usage":observed_usage(),"provider_request_id":None,"observed_runtime":True}
        try:
            reply=await client.call("invoke",request,timeout_s=request["timeout_s"])
        except asyncio.CancelledError:
            raise ProviderError("CONTAINMENT_UNCERTAIN",outcome_unknown=True,observation=observation) from None
        except Exception:
            raise ProviderError("network_error",outcome_unknown=True,observation=observation) from None
        if (not isinstance(reply,dict) or set(reply)!={"request_id","binding_sha256","outcome","http_status","response_text","provider_request_id"}
                or reply["request_id"]!=request_id or reply["binding_sha256"]!=self.binding["binding_sha256"]):
            raise ProviderError("invalid_output",outcome_unknown=True,observation=observation)
        self.trace.append(("in","local-model/result",copy.deepcopy(reply)))
        observation["provider_request_id"]=reply["provider_request_id"]
        if self.binding['backend']['kind']=='host-codex-app-server' and isinstance(reply['response_text'],str):
            try:
                bundle,observation,text=native_codex_response(reply['response_text'],self.binding,prompt=prompt)
                require(reply['http_status'] is None and reply['outcome']==bundle['outcome']
                        and reply['provider_request_id']==observation['provider_request_id'])
            except (KeyError,TypeError,ValueError,ResearchError):
                raise ProviderError('invalid_output',outcome_unknown=True,observation=observation) from None
            if bundle['outcome']=='completed':return {'text':text,**observation}
            code=bundle['error_code'] or 'network_error'
            raise ProviderError(code,outcome_unknown=bundle['outcome']=='outcome_unknown',observation=observation)
        if self.binding['backend']['kind']=='host-codex-app-server' and reply['outcome']=='completed':
            raise ProviderError('invalid_output',outcome_unknown=True,observation=observation)
        if reply["outcome"]=="outcome_unknown":
            raise ProviderError("network_error",outcome_unknown=True,observation=observation)
        if reply["outcome"]!="completed":
            status=reply["http_status"]
            code="auth_failed" if status in {401,403} else "rate_limited" if status==429 else "invalid_request" if type(status) is int and 400<=status<500 else "provider_error"
            raise ProviderError(code,observation=observation)
        try:
            raw=reply["response_text"]
            require(isinstance(raw,str) and len(raw.encode())<=1024*1024)
            from .router_client import decode_frame
            response=decode_frame(raw.encode())
            require(isinstance(response,dict) and isinstance(response.get("model"),str) and bool(response["model"]))
            usage=response.get("usage") or {}
            require(isinstance(usage,dict))
            observation.update(identity={"effective":response["model"],"basis":"provider response.model"},
                               usage=observed_usage({"input_tokens":usage.get("prompt_tokens"),"output_tokens":usage.get("completion_tokens")}))
            choices=response["choices"]
            require(isinstance(choices,list) and len(choices)==1 and isinstance(choices[0],dict))
            message=choices[0]["message"]
            require(isinstance(message,dict) and isinstance(message.get("content"),str) and bool(message["content"].strip())
                    and not message.get("tool_calls") and choices[0].get("finish_reason")=="stop")
        except (KeyError,TypeError,ValueError,ResearchError):
            raise ProviderError("invalid_output",observation=observation) from None
        return {"text":message["content"],**observation}
