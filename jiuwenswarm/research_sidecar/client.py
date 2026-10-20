"""Authenticated supported research HTTP client, with no product implementation imports."""
import asyncio
import copy
import math
import os
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
    def __init__(self,base_url,token_file,*,transport=None,timeout=30):
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0:raise ClientError('finite client deadline required')
        self.timeout=timeout
        self.transport=transport
        self.evaluation_http_captures=[]
        p=urlsplit(base_url)
        if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.query or p.fragment:raise ClientError('invalid protected target URL')
        path=Path(token_file)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>16384:raise ClientError('invalid token reference')
        if os.name!='nt' and path.stat().st_mode&0o077:raise ClientError('token file must be private')
        token=path.read_text(encoding='utf8').strip()
        if not token or '\n' in token or '\r' in token:raise ClientError('invalid token reference')
        self.http=httpx.AsyncClient(base_url=base_url.rstrip('/'),headers={'Authorization':'Bearer '+token},timeout=timeout,transport=transport,follow_redirects=False,trust_env=False)
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
            self.validate('gate-decision',value['gate_decision'])
            if value['tier1_verdict'] not in {'PASS','FAIL'} or value['tier2_verdict'] not in {'PASS','PASS_WITH_KNOWN_LIMITATIONS','FAIL','NEEDS_REVISION','NOT_RUN'} or type(value['advanced']) is not bool:
                raise ClientError('Invalid replay tier result',status_code=200)
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
        with Path(path).open('rb') as stream:
            value=await self._request('POST','/api/v1/inputs/'+kind,data={'scope_id':scope_id},files={'file':(Path(path).name,stream)})
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
