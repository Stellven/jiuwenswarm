"""Authenticated supported research HTTP client, with no product implementation imports."""
import asyncio
import copy
import math
import os
import hashlib
import json
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit,quote
import httpx
from jiuwenswarm.research_records.contracts import ContractData


class ClientError(ValueError):
    def __init__(self,message,*,status_code=None,response_record=None):
        super().__init__(message);self.status_code=status_code;self.response_record=copy.deepcopy(response_record)


class DropSubmitReplyOnce(httpx.AsyncBaseTransport):
    """Finite controlled transport fault after an actual HTTP response.

    The protected campaign job opts in before execution. It never retries or
    changes the request, and records only credential-free transport facts.
    """
    def __init__(self,inner):self.inner=inner;self.dropped=False;self.observations=[]
    async def handle_async_request(self,request):
        response=await self.inner.handle_async_request(request)
        if not self.dropped and request.method=='POST' and request.url.path=='/api/v1/runs' and response.status_code<300:
            self.dropped=True
            self.observations.append({'method':'POST','path':'/api/v1/runs','observed_reply_status':response.status_code,
                'fault':'discard_successful_submit_reply_once','actual_response_received':True})
            await response.aclose()
            raise httpx.ReadTimeout('Controlled delivery loss after an actual response; reconcile without resend',request=request)
        return response
    async def aclose(self):await self.inner.aclose()


class ResearchClient:
    def __init__(self,base_url,token_file,*,transport=None,timeout=30,http_authority=None):
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0:raise ClientError('finite client deadline required')
        self.timeout=timeout
        self.transport=transport
        self.evaluation_http_captures=[]
        p=urlsplit(base_url)
        if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.query or p.fragment:raise ClientError('invalid protected target URL')
        headers={}
        if http_authority is not None:
            if (not isinstance(http_authority,str) or not http_authority or len(http_authority)>253
                    or not http_authority.isascii() or any(character.isspace() or ord(character)<33 or ord(character)==127 for character in http_authority)
                    or any(character in http_authority for character in '/\\?#@,%')):
                raise ClientError('HTTP authority must be an explicit host with optional port')
            try:
                authority=urlsplit('//'+http_authority)
                if (not authority.hostname or authority.path or authority.query or authority.fragment or authority.username is not None
                        or authority.password is not None or http_authority.endswith(':') or authority.port is not None and not 1<=authority.port<=65535):
                    raise ValueError()
                if ':' not in authority.hostname and re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',authority.hostname) is None:
                    raise ValueError()
            except ValueError:raise ClientError('HTTP authority must be an explicit host with optional port') from None
            headers['Host']=http_authority
        path=Path(token_file)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>16384:raise ClientError('invalid token reference')
        if os.name!='nt' and path.stat().st_mode&0o077:raise ClientError('token file must be private')
        token=path.read_text(encoding='utf8').strip()
        if not token or '\n' in token or '\r' in token:raise ClientError('invalid token reference')
        headers['Authorization']='Bearer '+token
        self.http_authority=http_authority
        self.http=httpx.AsyncClient(base_url=base_url.rstrip('/'),headers=headers,timeout=timeout,transport=transport,follow_redirects=False,trust_env=False)
        self.validate=ContractData().validate
    @property
    def transport_observations(self):return copy.deepcopy(getattr(self.transport,'observations',[]))
    async def _request(self,method,path,**kwargs):
        async with asyncio.timeout(self.timeout):
            response=await self.http.request(method,path,**kwargs)
            if path.startswith('/api/v1/evaluation/'):
                import base64,hashlib
                self.evaluation_http_captures.append({'method':method,'path':path,'status_code':response.status_code,
                    'body_base64':base64.b64encode(response.content).decode('ascii'),'sha256':hashlib.sha256(response.content).hexdigest()})
            if response.status_code>=300:
                error=None
                try:
                    error=response.json();self.validate('client-error',error)
                    if error['category'] not in {'auth','validation','not_found','conflict','unavailable','internal'}:raise ValueError('Unknown error category')
                except (ValueError,KeyError,TypeError):error=None
                raise ClientError('product HTTP refused operation: '+str(response.status_code),status_code=response.status_code,response_record=error)
            value=response.json()
        if not isinstance(value,(dict,list)):raise ClientError('unsupported response contract')
        return value
    def _evaluation_result(self,value,entry_mode):
        common={'model_calls','duration_s','reason','invalid_for_product'}
        fields=({'replay_id','tier1_verdict','tier2_verdict','gate_decision','advanced','persisted_at','downstream_action','evidence_refs'}
                if entry_mode=='node_replay' else {'invocation_id','status','output_refs','check_results','tool_effects_observed'})
        if not isinstance(value,dict) or set(value)!=common|fields or value['invalid_for_product'] is not True:
            raise ClientError('Unsupported evaluation response contract',status_code=200)
        if not isinstance(value['model_calls'],list) or type(value['duration_s']) not in (int,float) or not math.isfinite(value['duration_s']) or value['duration_s']<0:
            raise ClientError('Invalid actual evaluation observations',status_code=200)
        if entry_mode=='node_replay':
            decision = value['gate_decision']
            if isinstance(decision, dict) and decision.get('invalid_for_product') is True:
                self.validate('urn:ai4r:evaluation-recording-decision:1.0.0', decision)
            else:
                self.validate('gate-decision', decision)
            if value['tier1_verdict'] not in {'PASS','FAIL'} or value['tier2_verdict'] not in {'PASS','PASS_WITH_KNOWN_LIMITATIONS','FAIL','NEEDS_REVISION','INCONCLUSIVE','ENVIRONMENT_BLOCKED','NOT_RUN'} or type(value['advanced']) is not bool:
                raise ClientError('Invalid replay tier result',status_code=200)
            if value['advanced'] and (value['tier1_verdict'] != 'PASS' or value['tier2_verdict'] not in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'}):
                raise ClientError('Non-advancing replay verdict cannot advance',status_code=200)
        elif value['status'] not in {'completed','failed','blocked'} or not isinstance(value['output_refs'],dict) or not isinstance(value['check_results'],list):
            raise ClientError('Invalid single-Capsule result',status_code=200)
        return value
    async def evaluate(self,entry_mode,payload):
        if entry_mode not in {'node_replay','single_cc'} or not isinstance(payload,dict) or not all(isinstance(payload.get(k),str) and payload[k] for k in ('request_id','campaign_id','case_id','evaluation_profile_id')):
            raise ClientError('Exact finite evaluation request required')
        path='/api/v1/evaluation/'+('node-replay' if entry_mode=='node_replay' else 'single-cc')
        try:return self._evaluation_result(await self._request('POST',path,json=payload),entry_mode)
        except ClientError:raise
        except (ValueError,KeyError,TypeError):raise ClientError('Unsupported evaluation response',status_code=200) from None
    async def evaluation_request(self,request_id):
        try:
            value=await self._request('GET','/api/v1/evaluation/requests/'+quote(request_id,safe=''))
            if not isinstance(value,dict) or set(value)!={'request_id','status','result','failure_ref','invalid_for_product'} or value['request_id']!=request_id or value['invalid_for_product'] is not True or value['status'] not in {'started','completed','failed','interrupted'}:
                raise ClientError('Unsupported evaluation reconciliation',status_code=200)
            if value['result'] is not None:self._evaluation_result(value['result'],'node_replay' if 'replay_id' in value['result'] else 'single_cc')
            return value
        except ClientError:raise
        except (ValueError,KeyError,TypeError):raise ClientError('Unsupported evaluation reconciliation',status_code=200) from None
    async def evaluation_export_archive(self,request_id,audience='researcher',max_bytes=128*1024*1024):
        if (not isinstance(request_id,str) or not request_id or audience not in {'researcher','reviewer'}
            or type(max_bytes) is not int or not 0<max_bytes<=128*1024*1024):
            raise ClientError('bounded scoped evaluation export required')
        path='/api/v1/evaluation/requests/'+quote(request_id,safe='')
        async with asyncio.timeout(self.timeout):
            async with self.http.stream('GET',path,params={'audience':audience},headers={'Accept':'application/zip'}) as response:
                if response.status_code!=200 or response.headers.get('content-type','').split(';')[0]!='application/zip':
                    raise ClientError('authorized evaluation original-byte export unavailable',status_code=response.status_code)
                chunks=[];size=0
                async for chunk in response.aiter_bytes(chunk_size=64*1024):
                    size+=len(chunk)
                    if size>max_bytes:raise ClientError('evaluation export exceeds bounded transport policy')
                    chunks.append(chunk)
                return b''.join(chunks)
    async def readiness(self):
        value=await self._request('GET','/api/v1/readiness');self.validate('client-readiness',value);return value
    async def context(self):
        value=await self._request('GET','/api/v1/context')
        if not isinstance(value,dict) or value.get('schema_version')!='1.0.0' or not isinstance(value.get('defaults'),dict):
            raise ClientError('unsupported client context')
        return value
    async def prepare_intake(self,task,upload_refs=(),*,workspace_id=None):
        if not isinstance(task,str) or not task.strip() or not isinstance(upload_refs,(list,tuple)) or any(not isinstance(ref,str) for ref in upload_refs):
            raise ClientError('original task text and explicit upload identifiers required')
        value=await self._request('POST','/api/v1/intakes',json={'task':task,'upload_refs':list(upload_refs),'workspace_id':workspace_id})
        if (not isinstance(value,dict) or value.get('schema_version')!='1.0.0' or value.get('qualified') is not True
                or not isinstance(value.get('submission_defaults'),dict)):
            raise ClientError('unsupported qualified intake response')
        self.validate('Ref',value['intake_ref'])
        return value
    async def events(self,run_id,after=0):
        if type(after) is not int or after<0:raise ClientError('nonnegative event cursor required')
        value=await self._request('GET','/api/v1/runs/'+quote(run_id,safe='')+'/events',params={'after':after})
        if (not isinstance(value,dict) or value.get('schema_version')!='1.0.0' or value.get('run_id')!=run_id
                or not isinstance(value.get('events'),list) or type(value.get('next_after')) is not int):
            raise ClientError('unsupported events response')
        return value
    async def artifacts(self,run_id,audience='researcher'):
        value=await self._request('GET','/api/v1/runs/'+quote(run_id,safe='')+'/artifacts',params={'audience':audience})
        if (not isinstance(value,dict) or value.get('schema_version')!='1.0.0' or value.get('run_id')!=run_id
                or value.get('audience')!=audience or not isinstance(value.get('artifacts'),list)):
            raise ClientError('unsupported artifact manifest')
        content={key:item for key,item in value.items() if key!='manifest_sha256'}
        digest=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        if digest!=value.get('manifest_sha256'):raise ClientError('artifact manifest hash mismatch')
        names=set();identities=set()
        for item in value['artifacts']:
            path=item.get('path','')
            if (not isinstance(path,str) or re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*',path) is None
                    or any(part in {'.','..'} for part in path.split('/')) or ':' in path or path in names
                    or not isinstance(item.get('artifact_id'),str) or item['artifact_id'] in identities
                    or type(item.get('size')) is not int or item['size']<0 or not isinstance(item.get('sha256'),str)
                    or re.fullmatch('[0-9a-f]{64}',item['sha256']) is None):
                raise ClientError('unsafe artifact inventory')
            names.add(path);identities.add(item['artifact_id'])
        return value
    async def _stream_file(self,path,destination,*,params=None,sha256=None,size=None,max_bytes=1024*1024*1024,headers=None):
        if type(max_bytes) is not int or max_bytes<=0 or size is not None and (type(size) is not int or size<0 or size>max_bytes):
            raise ClientError('bounded download size required')
        if sha256 is not None and (not isinstance(sha256,str) or re.fullmatch('[0-9a-f]{64}',sha256) is None):
            raise ClientError('expected SHA256 required')
        target=Path(destination).absolute()
        if any(parent.is_symlink() for parent in (target,*target.parents)) or not target.parent.is_dir():
            raise ClientError('download destination must have existing safe directories')
        if target.exists():
            if not target.is_file() or sha256 is None or size is None or target.stat().st_size!=size:
                raise ClientError('download destination conflicts with existing evidence')
            digest=hashlib.sha256()
            with target.open('rb') as stream:
                for chunk in iter(lambda:stream.read(64*1024),b''):digest.update(chunk)
            if digest.hexdigest()!=sha256:raise ClientError('existing evidence hash mismatch')
            return {'path':str(target),'size':size,'sha256':sha256}
        temporary=target.parent/('.download-'+uuid.uuid4().hex)
        digest=hashlib.sha256();total=0
        try:
            descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            with os.fdopen(descriptor,'wb') as stream:
                async with asyncio.timeout(self.timeout):
                    async with self.http.stream('GET',path,params=params,headers=headers) as response:
                        if response.status_code!=200:raise ClientError('artifact download unavailable',status_code=response.status_code)
                        declared=response.headers.get('content-length')
                        if declared is not None and (not declared.isdigit() or int(declared)>max_bytes or size is not None and int(declared)!=size):
                            raise ClientError('artifact response size mismatch')
                        async for chunk in response.aiter_bytes(chunk_size=64*1024):
                            total+=len(chunk)
                            if total>max_bytes or size is not None and total>size:raise ClientError('artifact exceeds declared size')
                            stream.write(chunk);digest.update(chunk)
                if size is not None and total!=size or sha256 is not None and digest.hexdigest()!=sha256:
                    raise ClientError('artifact byte identity mismatch')
                stream.flush();os.fsync(stream.fileno())
            # Link publishes atomically without overwriting a concurrent writer.
            os.link(temporary,target)
            if os.name=='posix':
                fd=os.open(target.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
                try:os.fsync(fd)
                finally:os.close(fd)
            return {'path':str(target),'size':total,'sha256':digest.hexdigest()}
        finally:temporary.unlink(missing_ok=True)
    async def download_artifact(self,run_id,artifact_id,destination,*,sha256,size,max_bytes=1024*1024*1024,audience='researcher'):
        return await self._stream_file('/api/v1/runs/'+quote(run_id,safe='')+'/artifacts/'+quote(artifact_id,safe=''),destination,
            params={'audience':audience},sha256=sha256,size=size,max_bytes=max_bytes)
    async def stream_export_archive(self,run_id,destination,*,audience='researcher',max_bytes=1024*1024*1024):
        return await self._stream_file('/api/v1/runs/'+quote(run_id,safe='')+'/export',destination,
            params={'audience':audience},max_bytes=max_bytes,headers={'Accept':'application/zip'})
    async def confirm_collection(self,run_id,manifest_sha256,artifacts,audience='researcher'):
        value=await self._request('POST','/api/v1/runs/'+quote(run_id,safe='')+'/collection-confirmation',
            json={'manifest_sha256':manifest_sha256,'artifacts':artifacts,'audience':audience})
        if (not isinstance(value,dict) or value.get('schema_version')!='1.0.0' or value.get('run_id')!=run_id
                or value.get('manifest_sha256')!=manifest_sha256 or value.get('status')!='confirmed'):
            raise ClientError('unsupported collection confirmation')
        return value
    async def submit(self,payload):
        self.validate('client-submission',payload)
        value=await self._request('POST','/api/v1/runs',json=payload);self.validate('client-status',value);return value
    async def reconcile(self,client_request_id):
        value=await self._request('GET','/api/v1/runs',params={'client_request_id':client_request_id})
        self.validate('client-status',value)
        return value
    async def status(self,run_id):
        value=await self._request('GET','/api/v1/runs/'+quote(run_id,safe=''));self.validate('client-status',value);return value
    async def export(self,run_id,audience='researcher'):
        value=await self._request('GET','/api/v1/runs/'+quote(run_id,safe='')+'/export',params={'audience':audience});self.validate('client-retrieval',value);return value
    async def export_archive(self,run_id,audience='researcher',max_bytes=64*1024*1024):
        async with asyncio.timeout(self.timeout):
            async with self.http.stream('GET','/api/v1/runs/'+quote(run_id,safe='')+'/export',params={'audience':audience},headers={'Accept':'application/zip'}) as response:
                if response.status_code!=200 or response.headers.get('content-type','').split(';')[0]!='application/zip':raise ClientError('authorized original-byte export unavailable',status_code=response.status_code)
                chunks=[];size=0
                async for chunk in response.aiter_bytes():
                    size+=len(chunk)
                    if size>max_bytes:raise ClientError('export exceeds bounded transport policy')
                    chunks.append(chunk)
                return b''.join(chunks)
    async def cancel(self,run_id,request_id):
        value=await self._request('POST','/api/v1/runs/'+quote(run_id,safe='')+'/cancel',json={'request_id':request_id});self.validate('client-cancellation',value);return value
    async def upload(self,kind,scope_id,path):
        if kind not in {'docs','repo','datasets'}:raise ClientError('unsupported upload kind')
        path=Path(path)
        digest=hashlib.sha256(path.read_bytes()).hexdigest();size=path.stat().st_size
        async def existing():
            matches=[value for value in await self.list_uploads(scope_id)
                     if value['scope_id']==scope_id and value['kind']==kind
                     and value['filename']==path.name and value['status']=='uploaded']
            if not matches:return None
            if len(matches)!=1 or matches[0]['content_sha256']!=digest or matches[0]['size_bytes']!=size:
                raise ClientError('upload filename is occupied by different retained input bytes',status_code=409)
            return matches[0]
        value=await existing()
        if value is not None:return value
        try:
            with path.open('rb') as stream:
                value=await self._request('POST','/api/v1/inputs/'+kind,data={'scope_id':scope_id},files={'file':(path.name,stream)})
        except ClientError as exc:
            if exc.status_code!=409:raise
            # Reconcile an identical concurrent upload; never overwrite/delete
            # inputs or replay product work to recover a filename collision.
            value=await existing()
            if value is None:raise
        self.validate('client-upload',value);return value
    async def list_uploads(self,scope_id):
        values=await self._request('GET','/api/v1/inputs',params={'scope_id':scope_id})
        if not isinstance(values,list):raise ClientError('unsupported upload list contract')
        for value in values:self.validate('client-upload',value)
        return values
    async def delete_upload(self,upload_id):
        value=await self._request('DELETE','/api/v1/inputs/'+quote(upload_id,safe=''))
        self.validate('client-upload',value);return value
    async def close(self):await self.http.aclose()
