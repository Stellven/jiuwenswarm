"""Owned Library import, planning and workflow execution endpoints."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Literal
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict

from .contracts import StageBlocked, StageFailure
from .workflow_library import WorkflowLibrary, write_json
from .workflow_planner import WorkflowPlanner, POLICY


JOB_KINDS = {'imports', 'plans', 'executions', 'builds'}


class ImportRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    repository_url:str
    revision:str|None=None


class PlanRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    task:dict
    policy:str|None=None
    previous_execution_id:str|None=None
    planner: Literal['agent', 'contract'] = 'agent'


class ExecuteRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan_id:str


class BuildRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task: dict


class LibraryService:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.library=WorkflowLibrary(self.root)
        self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='workflow-library')
        self.lock=threading.RLock()

    def directory(self,kind,job_id):
        if kind not in JOB_KINDS or not re.fullmatch(r'[a-f0-9]{32}',job_id):
            raise FileNotFoundError(job_id)
        return self.root/kind/job_id

    def read_build_product(self, job_id):
        directory = self.directory('builds', job_id)
        path = (directory / 'guided-replay.json').resolve(strict=True)
        if not path.is_relative_to(directory):
            raise ValueError('Build product outside its owned workspace')
        return path.read_bytes()

    def get(self,kind,job_id,owner):
        path=self.directory(kind,job_id)
        if not (path/'job.json').is_file():raise FileNotFoundError(job_id)
        with self.lock:
            job=json.loads((path/'job.json').read_text())
            if job['owner_id']!=owner:raise FileNotFoundError(job_id)
            live_path=path/'runtime'/job_id/'run.json'
            if kind=='executions' and live_path.exists() and job['status'] in {'pending','running'}:
                live=json.loads(live_path.read_text())
                job.update(live)
                job['owner_id']=owner
            events_path=path/'library-events.jsonl'
            job['events']=[json.loads(line) for line in events_path.read_text().splitlines()] if events_path.exists() else []
            finished=any(event['type'] in {'job.finished','job.failed','job.blocked'} for event in job['events'])
            if job['status'] in {'completed','verified','failed','blocked'} and not finished:
                job['runtime_status']=job['status']
                job['status']='running'
            if kind=='executions':
                unmet=job.get('unmet_requirements',job.get('graph',{}).get('unmet_requirements',[]))
                job['acceptance_status']='incomplete' if job['status']=='verified' and unmet else job['status']
        return job

    def update(self,kind,job_id,**fields):
        path=self.directory(kind,job_id)/'job.json'
        with self.lock:
            job=json.loads(path.read_text());job.update(fields);write_json(path,job)

    def emit(self,kind,job_id,event_type,payload):
        directory=self.directory(kind,job_id)
        with self.lock:
            path=directory/'library-events.jsonl'
            sequence=sum(1 for _ in path.open())+1 if path.exists() else 1
            event={'sequence':sequence,'time':datetime.now(timezone.utc).isoformat(),
                   'type':event_type,'payload':payload}
            with path.open('a') as stream:stream.write(json.dumps(event,allow_nan=False)+'\n')

    def start(self,kind,owner,body):
        job_id=uuid.uuid4().hex;path=self.directory(kind,job_id);path.mkdir(parents=True)
        write_json(path/'job.json',{'id':job_id,'owner_id':owner,'status':'pending','kind':kind,
                                  'request':body,'created_at':datetime.now(timezone.utc).isoformat()})
        self.pool.submit(self._work,kind,job_id,owner,body)
        return self.get(kind,job_id,owner)

    def _work(self,kind,job_id,owner,body):
        emit=lambda event,payload:self.emit(kind,job_id,event,payload)
        self.update(kind,job_id,status='running');emit('job.started',{'id':job_id,'kind':kind})
        try:
            if kind=='imports':
                from .workflow_imports import import_project
                bundle=import_project(self.root/'projects'/job_id,body['repository_url'],
                                      revision=body.get('revision'),emit=emit)
                emit('library.registration_started',{'workflow_id':bundle['id']})
                registered=self.library.register(bundle)
                self.update(kind,job_id,workflow=registered,status='completed')
                emit('library.workflow_registered',{'workflow':registered})
            elif kind=='plans' and body.get('planner') == 'contract':
                from .workflow_planner import plan_contract
                result = plan_contract(self.library, body['task'], self.directory(kind, job_id), emit=emit)
                self.update(kind, job_id, status='completed', **result)
            elif kind=='plans':
                feedback=None
                if body.get('previous_execution_id'):
                    prior=self.get('executions',body['previous_execution_id'],owner)
                    if prior['status'] not in {'verified','failed','blocked'}:
                        raise StageFailure('run_not_settled','Wait for the actual previous execution to settle')
                    feedback={k:prior.get(k) for k in ['id','status','graph','nodes','error','outputs']}
                    write_json(self.directory(kind,job_id)/'previous_execution.json',feedback)
                    emit('planner.execution_feedback_bound',{'execution_id':prior['id'],'status':prior['status']})
                result=WorkflowPlanner(self.library).plan(body['task'],self.directory(kind,job_id),
                    policy=body.get('policy'),artifacts=self.available_artifacts(owner),feedback=feedback,emit=emit)
                self.update(kind,job_id,status='completed',**result)
            elif kind == 'builds':
                from .functional_live import run_live_workflow
                from .guided_replay import SCHEMA

                result = run_live_workflow(self.directory(kind, job_id), body['task'],
                                           run_id=job_id, emit=emit, source_root=self.root / 'build-sources')
                status = result['status']
                if status not in {'verified', 'failed', 'blocked'}:
                    raise StageFailure('invalid_build_status', 'Live workflow did not settle')
                product = None
                if status == 'verified':
                    raw = self.read_build_product(job_id)
                    replay = json.loads(raw)
                    if replay.get('schema') != SCHEMA or replay.get('provenance', {}).get('runId') != job_id:
                        raise StageFailure('invalid_build_product', 'Saved product does not belong to this build')
                    product = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
                snapshot = {key: result[key] for key in ('graph', 'nodes', 'outputs', 'error') if key in result}
                self.update(kind, job_id, status=status, product=product, product_ready=product is not None,
                            **snapshot)
            else:
                plan=self.get('plans',body['plan_id'],owner)
                if plan['status']!='completed' or not plan.get('graph'):
                    raise StageFailure('plan_not_admitted','Use a completed, program-validated plan')
                from .workflow_runtime import WorkflowExecutor
                result=WorkflowExecutor(self.library,self.directory(kind,job_id)/'runtime').run(
                    plan['graph'],run_id=job_id,emit=emit)
                self.update(kind,job_id,**{k:v for k,v in result.items() if k not in {'events','owner_id','id'}})
                self.update(kind,job_id,unmet_requirements=plan.get('unmet_requirements',[]))
            terminal=json.loads((self.directory(kind,job_id)/'job.json').read_text())
            emit('job.finished',{'id':job_id,'status':terminal['status']})
        except Exception as error:
            status='blocked' if isinstance(error,StageBlocked) else 'failed'
            detail={'code':getattr(error,'code','execution_error'),'message':str(error),
                    'details':getattr(error,'details',{})}
            self.update(kind,job_id,status=status,error=detail)
            emit('job.'+status,{'error':detail})

    def available_artifacts(self,owner):
        result=[]
        for path in sorted((self.root/'executions').glob('*/job.json'),reverse=True):
            try:run=self.get('executions',path.parent.name,owner)
            except (FileNotFoundError,ValueError):continue
            verified={n['id'] for n in run.get('nodes',[]) if n.get('status')=='verified'}
            for value in run.get('artifacts',[]):
                file=Path(value['path'])
                if value.get('producer') in verified and file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==value['sha256']:
                    result.append(value)
        return result[-200:]


def create_library_router(root,owner):
    service=LibraryService(root)
    from .library_evidence import ComponentChecks, EvidenceConflict, import_materials, import_material, latest_model_attempt
    checks=ComponentChecks(service.root.parent,service.root)
    router=APIRouter(prefix='/library',tags=['Workflow Library'])

    async def identity(request,action='status'):
        return await owner(request,action)

    def known(kind,job_id,account):
        try:return service.get(kind,job_id,account)
        except (FileNotFoundError,ValueError):raise HTTPException(404,'Unknown owned Library operation')

    def recorded(operation,*arguments):
        try:return operation(*arguments)
        except FileNotFoundError:raise HTTPException(404,'Unknown owned Library evidence')
        except (EvidenceConflict,OSError,ValueError,KeyError,TypeError,UnicodeError) as error:
            raise HTTPException(409,str(error))

    def import_snapshot(job_id,account):
        value=known('imports',job_id,account)
        try:value['materials']=import_materials(service.root,value)
        except (EvidenceConflict,OSError,ValueError,KeyError,TypeError) as error:
            value['materials']=[];value['material_error']=str(error)
        return value

    @router.get('')
    async def library(request:Request):
        await identity(request)
        values=service.library.list()
        return {'workflows':values,'count':len(values),'schema':'factory.workflow-library.v1'}

    @router.get('/policy')
    async def policy(request:Request):
        await identity(request)
        return {'content':POLICY,'sha256':hashlib.sha256(POLICY.encode()).hexdigest()}

    @router.get('/model-connection')
    async def recorded_model_connection(request:Request):
        return {'attempt':recorded(latest_model_attempt,service.root.parent,await identity(request))}

    @router.get('/imports')
    async def import_history(request:Request):
        account=await identity(request)
        values=[]
        for path in (service.root/'imports').glob('*/job.json'):
            try:values.append(import_snapshot(path.parent.name,account))
            except HTTPException as error:
                if error.status_code!=404:raise
        return {'jobs':sorted(values,key=lambda value:value.get('created_at',''),reverse=True)}

    @router.get('/imports/{job_id}')
    async def imported_source(request:Request,job_id:str):
        return import_snapshot(job_id,await identity(request))

    @router.get('/imports/{job_id}/materials/{material_id}')
    async def imported_material(request:Request,job_id:str,material_id:str):
        account=await identity(request)
        job=known('imports',job_id,account)
        return recorded(import_material,service.root,job,material_id)

    @router.get('/checks')
    async def component_checks(request:Request):
        return {'checks':checks.list(await identity(request))}

    @router.get('/checks/{check_id}')
    async def component_check(request:Request,check_id:str):
        return recorded(checks.get,check_id,await identity(request))

    @router.get('/checks/{check_id}/artifacts/{artifact_id}')
    async def component_artifact(request:Request,check_id:str,artifact_id:str):
        path,artifact=recorded(checks.artifact,check_id,artifact_id,await identity(request))
        return FileResponse(path,filename=path.name,headers={
            'X-Content-SHA256':artifact['sha256'],'X-Content-Type-Options':'nosniff'})

    @router.get('/checks/{check_id}/artifacts/{artifact_id}/file')
    async def component_project_file(request:Request,check_id:str,artifact_id:str,path:str):
        member,digest=recorded(checks.project_file,check_id,artifact_id,path,await identity(request))
        return FileResponse(member,filename=member.name,media_type='text/plain',headers={
            'X-Content-SHA256':digest,'X-Content-Type-Options':'nosniff'})

    @router.get('/source')
    async def source(request:Request,workflow_id:str,path:str,version:str|None=None):
        await identity(request)
        try:return service.library.read_source(workflow_id,version,path)
        except (StageFailure,OSError,UnicodeError) as error:raise HTTPException(422,str(error))

    @router.post('/import',status_code=202)
    async def import_repository(request:Request,body:ImportRequest):
        account=await identity(request,'submit')
        from .workflow_imports import PROJECTS
        if body.repository_url not in PROJECTS:raise HTTPException(422,'Select STRATA or GoogleTest')
        return service.start('imports',account,body.model_dump())

    @router.post('/plan',status_code=202)
    async def plan(request:Request,body:PlanRequest):
        account=await identity(request,'submit')
        if body.previous_execution_id:known('executions',body.previous_execution_id,account)
        return service.start('plans',account,body.model_dump())

    @router.post('/execute',status_code=202)
    async def execute(request:Request,body:ExecuteRequest):
        account=await identity(request,'submit')
        value=known('plans',body.plan_id,account)
        if value['status']!='completed' or not value.get('graph'):raise HTTPException(409,'Planner has not produced an admitted graph')
        return service.start('executions',account,body.model_dump())

    @router.post('/build', status_code=202)
    async def start_build(request: Request, body: BuildRequest):
        account = await identity(request, 'submit')
        from .functional_live import validate_live_task

        try:
            task = validate_live_task(body.task)
        except (StageFailure, ValueError) as error:
            raise HTTPException(422, {'code': getattr(error, 'code', 'invalid_task'), 'message': str(error)})
        return service.start('builds', account, {'task': task})

    @router.get('/builds')
    async def build_history(request: Request):
        account = await identity(request)
        jobs = []
        for path in (service.root / 'builds').glob('*/job.json'):
            try:
                job = service.get('builds', path.parent.name, account)
            except (FileNotFoundError, ValueError):
                continue
            jobs.append({key: job[key] for key in ('id', 'kind', 'status', 'request', 'created_at',
                                                   'product_ready', 'error') if key in job})
        return {'jobs': sorted(jobs, key=lambda job: job['created_at'], reverse=True)}

    @router.get('/builds/{job_id}/product')
    async def build_product(request: Request, job_id: str):
        job = known('builds', job_id, await identity(request))
        if job['status'] != 'verified' or not job.get('product'):
            raise HTTPException(409, 'Build product is available only after verification')
        try:
            raw = service.read_build_product(job_id)
        except (OSError, ValueError):
            raise HTTPException(409, 'Published build product is unavailable')
        sha256 = job['product']['sha256']
        if len(raw) != job['product']['size'] or hashlib.sha256(raw).hexdigest() != sha256:
            raise HTTPException(409, 'Published build product changed')
        return Response(raw, media_type='application/json', headers={
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
            'X-Content-SHA256': sha256})

    @router.get('/artifacts/{run_id}/{artifact_id}')
    async def artifact(request:Request,run_id:str,artifact_id:str):
        account=await identity(request)
        run=known('executions',run_id,account)
        value=next((v for v in run.get('artifacts',[]) if v['id']==artifact_id),None)
        if value is None:raise HTTPException(404,'Artifact has not been published')
        try:path=Path(value['path']).resolve(strict=True)
        except OSError:raise HTTPException(409,'Published artifact file is no longer available')
        if not path.is_relative_to(service.directory('executions',run_id)):
            raise HTTPException(403,'Artifact outside its owned run')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=value['sha256']:raise HTTPException(409,'Artifact bytes changed')
        return FileResponse(path,filename=path.name,headers={'X-Content-SHA256':value['sha256']})

    @router.get('/artifacts/{run_id}/{artifact_id}/file')
    async def project_file(request:Request,run_id:str,artifact_id:str,path:str):
        account=await identity(request)
        run=known('executions',run_id,account)
        value=next((v for v in run.get('artifacts',[]) if v['id']==artifact_id),None)
        if not value or value.get('kind')!='source.project':raise HTTPException(404,'Unknown published source project')
        try:
            manifest_path=Path(value['path']).resolve(strict=True)
            owned=service.directory('executions',run_id).resolve()
            if not manifest_path.is_relative_to(owned):raise HTTPException(403,'Project outside its owned run')
            if hashlib.sha256(manifest_path.read_bytes()).hexdigest()!=value['sha256']:
                raise HTTPException(409,'Published project manifest changed')
            manifest=json.loads(manifest_path.read_text())
            if manifest.get('schema')!='factory.source-project.v1':raise HTTPException(409,'Invalid project manifest')
            expected=manifest['files'].get(path)
            if not expected:raise HTTPException(404,'File is not published in this project')
            project=Path(manifest['source_dir']).resolve(strict=True)
            member=(project/path).resolve(strict=True)
            if not project.is_relative_to(owned) or not member.is_relative_to(project):
                raise HTTPException(403,'File outside its owned project')
            if not member.is_file() or hashlib.sha256(member.read_bytes()).hexdigest()!=expected:
                raise HTTPException(409,'Published source file changed')
        except (OSError,ValueError,KeyError,TypeError):
            raise HTTPException(409,'Published source project is unavailable')
        return FileResponse(member,filename=member.name,media_type='text/plain',
                            headers={'X-Content-SHA256':expected,'X-Content-Type-Options':'nosniff'})

    async def snapshot(request:Request,kind:str,job_id:str):
        account=await identity(request)
        if kind not in JOB_KINDS:raise HTTPException(404)
        return known(kind,job_id,account)

    async def events(request:Request,kind:str,job_id:str,after:int=0):
        account=await identity(request)
        known(kind,job_id,account)
        if after<0:raise HTTPException(422,'Invalid event cursor')
        async def frames():
            cursor=after
            while not await request.is_disconnected():
                value=known(kind,job_id,account)
                for event in value['events']:
                    if event['sequence']>cursor:
                        yield 'id: '+str(event['sequence'])+'\nevent: library\ndata: '+json.dumps(event)+'\n\n'
                        cursor=event['sequence']
                if any(event['type'] in {'job.finished','job.failed','job.blocked'} for event in value['events']):break
                await asyncio.sleep(.2)
        return StreamingResponse(frames(),media_type='text/event-stream',
                                 headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

    @router.get('/builds/{job_id}/stream')
    async def build_stream(request: Request, job_id: str, after: int = 0):
        return await events(request, 'builds', job_id, after)

    router.add_api_route('/{kind}/{job_id}',snapshot,methods=['GET'])
    router.add_api_route('/{kind}/{job_id}/events',events,methods=['GET'])
    return router
