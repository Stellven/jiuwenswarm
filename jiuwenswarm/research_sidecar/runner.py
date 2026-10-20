"""Serial scheduled attempts with immutable unsuccessful evidence and no retries."""
import asyncio
from datetime import datetime,timezone
import time
import uuid
import httpx
from .evidence import write_once,freeze_archive,read_verified
from .reconcile import submit_once
from .client import ClientError


def utc():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _evaluation_capture_inventory(directory,captures,*,entry_mode,request_id):
    """Index immutable response bytes, including a crash's earlier captures."""
    import base64,hashlib,json,os,re,stat
    from urllib.parse import quote
    from .evidence import canonical
    allowed={('GET','/api/v1/evaluation/requests/'+quote(request_id,safe='')),
        ('POST','/api/v1/evaluation/'+('node-replay' if entry_mode=='node_replay' else 'single-cc'))}
    def load(name):
        target=directory/name
        fd=os.open(target,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(fd,'rb') as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>16*1024*1024:
                raise ValueError('HTTP capture is not one bounded regular file')
            data=stream.read(16*1024*1024+1)
        if len(data)>16*1024*1024:raise ValueError('HTTP capture exceeds read bound')
        digest=hashlib.sha256(data).hexdigest()
        value=json.loads(data)
        if not isinstance(value,dict) or set(value)!={'responses'} or not isinstance(value['responses'],list) or not value['responses']:
            raise ValueError('Invalid HTTP capture inventory')
        for response in value['responses']:
            if not isinstance(response,dict) or set(response)!={'method','path','status_code','body_base64','sha256'}:
                raise ValueError('Invalid HTTP capture metadata')
            if (response['method'],response['path']) not in allowed or type(response['status_code']) is not int or not 100<=response['status_code']<=599:
                raise ValueError('HTTP capture differs from frozen evaluation request')
            try:body=base64.b64decode(response['body_base64'],validate=True)
            except (ValueError,TypeError):raise ValueError('Invalid HTTP capture encoding') from None
            if hashlib.sha256(body).hexdigest()!=response['sha256']:raise ValueError('HTTP response byte digest mismatch')
        if name!='evaluation-http-captures.json' and name!='evaluation-http-captures-'+digest+'.json':
            raise ValueError('HTTP capture filename digest mismatch')
        return {'artifact_type':'evaluation-http-captures','path':name,'sha256':digest}
    names=[]
    for item in directory.iterdir():
        if item.name=='evaluation-http-captures.json' or re.fullmatch(r'evaluation-http-captures-[0-9a-f]{64}\.json',item.name):
            names.append(item.name)
    if len(names)>4096:raise ValueError('HTTP capture inventory exceeds file bound')
    # The original filename precedes digest companions; every original stays exact.
    names.sort(key=lambda name:(name!='evaluation-http-captures.json',name))
    rows=[load(name) for name in names]
    if captures:
        payload=canonical({'responses':captures});digest=hashlib.sha256(payload).hexdigest()
        if not any(row['sha256']==digest for row in rows):
            name='evaluation-http-captures.json' if not rows else 'evaluation-http-captures-'+digest+'.json'
            try:write_once(directory/name,payload)
            except FileExistsError:pass
            captured=load(name)
            if captured['sha256']!=digest:raise ValueError('HTTP capture identity conflict')
            rows.append(captured)
    return rows


class Runner:
    def __init__(self,client,ledger,root):self.client,self.ledger,self.root=client,ledger,root
    def _record(self,row,case,inventory,request_id,additional_inventory_ids=()):
        return {'schema':'run-record:1',**{k:row[k] for k in ('run_id','campaign_id','case_id','case_version','config_id','repeat_index')},
            'entry_mode':case['entry_mode'],'inventory_ids':[inventory['inventory_id'],*additional_inventory_ids],
            'app_pins':{k:None for k in ('app_build','client_contract_version','capsule_catalogue_sha256','planner','router','verifier','runtime_config_sha256')},'pins_match':False,
            'requested_seed':case.get('seed'),'effective_seed':None,'request_id':request_id,'app_run_id':None,'launched':False,
            'submitted_at':None,'started_at':None,'ended_at':None,'elapsed_s':None,'active_s':None,'external_wait_s':None,
            'outcome':'blocked','outcome_detail':{'terminal_status':None,'stage':'preflight','reason':None,'product_decision':None},
            'population':'isolated_module','exports':[],'gate_decisions':[],'downstream_actions':[],'model_calls':[],
            'cost':{'usage_available':False,'total_calls':0,'by_role':{},'monetary':None,'price_schedule_ref':None,'note':'No attributable usage observation.'},
            'evaluation_labels':[],'fault_ids':[],'checkpoints':[],
            'execution_peaks_ref':None,'limitations':[],'intervention':'none'}
    async def execute(self,row,case,*,inventory,submission,expected_pins,deadline_s=300,poll_s=.25,additional_inventory_ids=()):
        if case['entry_mode'] in {'node_replay','single_cc'}:
            return await self.execute_evaluation(row,case,inventory=inventory,submission=submission,expected_pins=expected_pins,deadline_s=deadline_s,additional_inventory_ids=additional_inventory_ids)
        request_id=submission['client_request_id'];start=time.monotonic()
        record=self._record(row,case,inventory,request_id,additional_inventory_ids)
        record['fault_ids']=[submission['fault_id']] if submission.get('fault_id') else []
        path=self.root/'runs'/row['run_id']
        try:
            if inventory['readiness']!='ready':record['outcome_detail']['reason']='host_inventory_blocked';return record
            if self.client is None:record['outcome_detail']['reason']='scoped_client_credential_unavailable';return record
            readiness=await self.client.readiness()
            record['app_pins'].update(app_build=readiness['build_id'],client_contract_version=readiness['client_contract_version'],
                capsule_catalogue_sha256=readiness['pins']['library_snapshot_sha256'],
                router=readiness['pins']['router_version'] if readiness['pins']['router_enabled'] else 'none')
            record['pins_match']=all(readiness['pins'].get(k)==v for k,v in expected_pins.items())
            if not readiness['ready'] or not record['pins_match']:
                record['outcome_detail']['reason']='readiness_or_pin_mismatch';return record
            operation=case.get('required_operation','submit')
            if operation not in readiness['operations']:
                record['outcome_detail']['reason']='entry_point_unavailable';return record
            record['submitted_at']=utc()
            value=await submit_once(self.client,submission,self.ledger,row['run_id'])
            record['launched']=True
            run_id=value.get('run_id')
            if not run_id:record['outcome']='interrupted';record['outcome_detail']['reason']='delivery_unknown';return record
            record['app_run_id']=run_id;record['started_at']=utc()
            while time.monotonic()-start<deadline_s:
                status=await self.client.status(run_id)
                terminal=status.get('status')
                if terminal in {'completed','partial','halted','paused','cancelled','interrupted'}:break
                await asyncio.sleep(min(poll_s,max(0,deadline_s-(time.monotonic()-start))))
            else:
                record['outcome']='interrupted';record['outcome_detail']['reason']='observation_deadline';return record
            record['outcome_detail']={'terminal_status':terminal,'stage':status.get('stage'),'reason':'; '.join(status.get('reasons',[])) or None,'product_decision':None}
            record['outcome']='completed' if terminal=='completed' else 'interrupted' if terminal in {'paused','cancelled','interrupted'} else 'failed'
            raw=await self.client.export_archive(run_id)
            from jiuwenswarm.research_records.contracts import ContractData
            exported=freeze_archive(path/'export',raw,run_id=run_id,audience='researcher',validate=ContractData().validate)
            record['exports']=[{'artifact_type':'client-retrieval','path':'export/client_retrieval.json','sha256':__import__('hashlib').sha256((path/'export/client_retrieval.json').read_bytes()).hexdigest()},
                *[{'artifact_type':f['media_type'],'path':'export/'+f['path'],'sha256':f['artifact_ref']['sha256']} for f in exported['files']]]
            from .frozen_records import FrozenRecords
            frozen=FrozenRecords(path/'export')
            record['gate_decisions']=frozen.gate_rows()
            record['downstream_actions']=frozen.downstream_rows()
            record['model_calls']=frozen.model_call_rows()
            record['cost']['total_calls']=len(record['model_calls'])
            for call in record['model_calls']:record['cost']['by_role'][call['role']]=record['cost']['by_role'].get(call['role'],0)+1
            record['cost']['usage_available']=bool(record['model_calls']) and all(c['input_tokens'] is not None and c['output_tokens'] is not None for c in record['model_calls'])
            decision_ref=status.get('decision_ref')
            if decision_ref:
                decision=frozen.resolve(decision_ref)
                record['outcome_detail']['product_decision']=decision.get('verdict') or decision.get('decision')
            if terminal=='completed' and not status['accepted_refs']:
                record['outcome']='failed';record['limitations'].append('Completed status did not expose accepted result references.')
            write_once(path/'terminal-status.json',status)
            record['limitations'].append('Case-specific independent output/causal validation is required before scoring.')
            return record
        except (httpx.TransportError,TimeoutError):
            record['outcome']='interrupted' if record['launched'] else 'blocked';record['outcome_detail']['reason']='transport_unavailable';return record
        except ClientError as exc:
            record['outcome']='failed' if record['launched'] else 'blocked'
            record['outcome_detail']['reason']='supported_client_refusal'
            if exc.response_record is not None:
                captured=write_once(path/'client-error.json',exc.response_record)
                record['exports'].append({'artifact_type':'client-error','path':'client-error.json','sha256':captured['sha256']})
                record['outcome_detail']['product_decision']=exc.response_record['category']
            write_once(path/'http-refusal.json',{'http_status':exc.status_code,'source_error_available':exc.response_record is not None})
            return record
        except ValueError:
            record['outcome']='failed' if record['launched'] else 'blocked';record['outcome_detail']['reason']='unsupported_or_refused_contract';return record
        finally:
            transport_observations=getattr(self.client,'transport_observations',[])
            if transport_observations:
                captured=write_once(path/'transport-observations.json',{'mode':'actual_http_transport','observations':transport_observations})
                record['exports'].append({'artifact_type':'transport-observations','path':'transport-observations.json','sha256':captured['sha256']})
                write_once(path/'client-ledger-events.json',self.ledger.events(row['run_id']))
            record['ended_at']=utc();record['elapsed_s']=time.monotonic()-start
            write_once(path/'run_record.json',record)

    async def execute_evaluation(self,row,case,*,inventory,submission,expected_pins,deadline_s=300,additional_inventory_ids=()):
        from .reconcile import evaluation_once
        from .evidence import canonical
        import hashlib,json
        mode=case['entry_mode'];request_id=submission['request_id'];path=self.root/'runs'/row['run_id']
        try:write_once(path/'evaluation-request.json',submission)
        except FileExistsError:
            read_verified(path,{'path':'evaluation-request.json','sha256':hashlib.sha256(canonical(submission)).hexdigest()})
        # A repeated scheduled row is reconciliation only. Its immutable result
        # is not rewritten with a new timestamp or a fresh readiness decision.
        if (path/'run_record.json').exists():
            history=path/'run_record.json'
            if history.is_symlink() or not history.is_file() or history.stat().st_nlink!=1 or history.stat().st_size>16*1024*1024:raise ValueError('Unsafe historical evaluation record')
            previous=json.loads(history.read_bytes())
            if any(previous[k]!=row[k] for k in ('run_id','campaign_id','case_id','case_version','config_id','repeat_index')) or previous['request_id']!=request_id or previous['entry_mode']!=mode:raise ValueError('Historical evaluation row differs from frozen schedule')
            if previous['launched'] and self.client is not None:await evaluation_once(self.client,mode,submission,self.ledger,row['run_id'])
            return previous
        record=self._record(row,case,inventory,request_id,additional_inventory_ids);start=time.monotonic()
        claimed=self.ledger.claimed(row['run_id'],{'entry_mode':mode,'request':submission})
        capture_start=len(getattr(self.client,'evaluation_http_captures',[]))
        try:
            record['launched']=claimed
            if self.client is None:
                record['outcome']='interrupted' if claimed else 'blocked';record['outcome_detail']['reason']='scoped_client_credential_unavailable';return record
            if not claimed:
                if inventory['readiness']!='ready':record['outcome_detail']['reason']='host_inventory_blocked';return record
                readiness=await self.client.readiness()
                record['app_pins'].update(app_build=readiness['build_id'],client_contract_version=readiness['client_contract_version'],
                    capsule_catalogue_sha256=readiness['pins']['library_snapshot_sha256'],router=readiness['pins']['router_version'] if readiness['pins']['router_enabled'] else 'none')
                record['pins_match']=all(readiness['pins'].get(k)==v for k,v in expected_pins.items())
                # Independent E2/E3 does not inherit the whole E1 ready flag.
                if mode not in readiness['operations'] or readiness['evaluation_profile']!=submission['evaluation_profile_id'] or not record['pins_match']:
                    record['outcome_detail']['reason']='evaluation_operation_profile_or_pins_unavailable';return record
                record['submitted_at']=utc()
            else:
                record['limitations'].append('Recovered durable claim without an original run record; original start time/pins remain unavailable and reconciliation sends no new effect.')
            remaining=deadline_s-(time.monotonic()-start)
            if remaining<=0:raise TimeoutError
            async with asyncio.timeout(remaining):value=await evaluation_once(self.client,mode,submission,self.ledger,row['run_id'])
            record['launched']=True;record['started_at']=record['submitted_at']
            if value.get('delivery')=='unknown':
                record['outcome']='interrupted';record['outcome_detail']['reason']='evaluation_delivery_unknown';return record
            captured=write_once(path/'evaluation-result.json',value)
            record['exports']=[{'artifact_type':'evaluation-http-result','path':'evaluation-result.json','sha256':captured['sha256']},
                {'artifact_type':'evaluation-source-request','path':'evaluation-request.json','sha256':hashlib.sha256(canonical(submission)).hexdigest()}]
            # A response summary cannot replace any original measurement,
            # checking, claim, start or native packet needed by the referee.
            async with asyncio.timeout(max(.001,deadline_s-(time.monotonic()-start))):
                raw=await self.client.evaluation_export_archive(request_id)
            received=write_once(path/'evaluation-export-received.zip',raw)
            record['exports'].append({'artifact_type':'evaluation-original-zip','path':'evaluation-export-received.zip','sha256':received['sha256']})
            from .evaluation_records import EvaluationRecords
            frozen=EvaluationRecords.from_archive(raw,request_id=request_id,campaign_id=row['campaign_id'],
                audience='researcher',expected_request=submission)
            frozen.freeze(path/'evaluation-export')
            record['exports'].extend([{'artifact_type':'evaluation-original-zip','path':'evaluation-export/archive.zip','sha256':received['sha256']},
                *[{'artifact_type':'evaluation-manifest' if name=='evaluation_export.json' else 'evaluation-original',
                    'path':'evaluation-export/'+name,'sha256':hashlib.sha256(payload).hexdigest()} for name,payload in frozen.entries.items()]])
            if frozen.response()!=value:raise ValueError('HTTP result differs from captured original terminal response')
            record['model_calls']=frozen.model_call_rows()
            record['cost']['total_calls']=len(record['model_calls'])
            record['cost']['usage_available']=bool(record['model_calls']) and all(c['input_tokens'] is not None and c['output_tokens'] is not None for c in record['model_calls'])
            for call in record['model_calls']:record['cost']['by_role'][call['role']]=record['cost']['by_role'].get(call['role'],0)+1
            if mode=='node_replay':
                decision=value['gate_decision'];record['outcome']='completed' if decision['action']=='advance' else 'failed'
                record['outcome_detail'].update(product_decision=decision['action'],terminal_status='evaluation_replay',reason=value['reason'])
            else:
                record['outcome']='completed' if value['status']=='completed' else 'blocked' if value['status']=='blocked' else 'failed'
                record['outcome_detail'].update(terminal_status=value['status'],reason=value['reason'])
            record['cost']['note']='Usage comes only from exact journal-owned original ModelCall bytes; unobserved quantities remain null.'
            record['limitations'].append('Original evaluation evidence is frozen separately from ordinary product exports; independent case obligations still require the credential-free referee.')
            record['limitations'].append('Evaluation result is invalid_for_product; E2 recording actions do not prove actual live scheduler release or locking.')
            return record
        except ClientError as error:
            if getattr(error,'evaluation_delivery_unknown',False):record['launched']=True;record['outcome']='interrupted'
            record['outcome_detail']['reason']='evaluation_http_refused'
            if error.response_record is not None:
                captured=write_once(path/'client-error.json',error.response_record)
                record['exports'].append({'artifact_type':'client-error','path':'client-error.json','sha256':captured['sha256']})
            return record
        except (httpx.TransportError,TimeoutError):
            issued=any(event['kind']=='evaluation_submitting' for event in self.ledger.events(row['run_id']))
            record['launched']=issued;record['outcome']='interrupted' if issued else 'blocked';record['outcome_detail']['reason']='evaluation_transport_unknown';return record
        except (ValueError,KeyError,TypeError,OSError):
            record['outcome']='failed' if record['launched'] else 'blocked'
            record['outcome_detail'].update(reason='evaluation_original_evidence_incomplete',product_decision=None)
            record['limitations'].append('The exact original export/response closure was not established. Retained HTTP and ZIP bytes are diagnostic evidence; independent acceptance is withheld.')
            return record
        finally:
            captures=getattr(self.client,'evaluation_http_captures',[])[capture_start:]
            record['exports'].extend(_evaluation_capture_inventory(path,captures,entry_mode=mode,request_id=request_id))
            write_once(path/'client-ledger-events.json',self.ledger.events(row['run_id']))
            record['ended_at']=utc();record['elapsed_s']=time.monotonic()-start
            write_once(path/'run_record.json',record)

    def blocked(self,row,case,inventory,reason,additional_inventory_ids=()):
        record=self._record(row,case,inventory,'not-submitted:'+row['run_id'],additional_inventory_ids)
        record['outcome_detail']['reason']=reason;record['ended_at']=utc()
        write_once(self.root/'runs'/row['run_id']/'run_record.json',record)
        return record

    async def execute_rsi(self,row,case,*,inventory,port,signer,deadline_s=300,poll_s=.25,additional_inventory_ids=()):
        """A separately granted workbench job; no product submit/token is used."""
        from .adapters.rsi import freeze_public_export,read_public_export,validate_public_session
        from jiuwenswarm.research_records.contracts import ContractData
        import json
        start=time.monotonic();path=self.root/'runs'/row['run_id']
        record=self._record(row,case,inventory,'workbench:'+port.job_ref['id'],additional_inventory_ids)
        try:
            if inventory['readiness']!='ready':record['outcome_detail']['reason']='host_inventory_blocked';return record
            record['submitted_at']=utc();record['launched']=True
            state=await port.start(port.job_ref);record['started_at']=utc()
            while state['state'] in {'started','running'} and time.monotonic()-start<deadline_s:
                await asyncio.sleep(min(poll_s,max(0,deadline_s-(time.monotonic()-start))))
                state=await port.operation('session_inspect',timeout=min(30,max(.001,deadline_s-(time.monotonic()-start))))
            if state['state']!='terminal':
                record['outcome']='interrupted';record['outcome_detail']['reason']='workbench_'+state['state'];return record
            exported=await port.operation('session_export')
            rows=freeze_public_export(path/'rsi-export',exported,validate=ContractData().validate)
            decoded={}
            for r in rows:decoded.setdefault(r['kind'],[]).append(json.loads(read_verified(path/'rsi-export',r)))
            if len(decoded.get('rsi-session-result',[]))!=1 or len(decoded.get('rsi-session',[]))!=1:raise ValueError('one exact terminal result/session required')
            result=decoded['rsi-session-result'][0];session=decoded['rsi-session'][0]
            public=bytes.fromhex(signer['public_key_hex'])
            validate_public_session(read_public_export(path/'rsi-export'),public_key=public,key_id=signer['key_id'])
            calls=decoded.get('model-call',[])
            record['model_calls']=[{'call_ref':next(r['ref'] for r in rows if r['kind']=='model-call' and json.loads(read_verified(path/'rsi-export',r))==call),
                'role':call['call_function'],'requested_model':call['identity']['requested'],'effective_model':call['identity']['effective'],
                'identity_basis':call['identity']['basis'],'duration_s':None,'outcome':call['outcome'],'input_tokens':call['usage']['input_tokens'],
                'output_tokens':call['usage']['output_tokens'],'cost':call['usage']['cost_amount']} for call in calls]
            record['cost']['total_calls']=len(calls)
            for call in calls:record['cost']['by_role'][call['call_function']]=record['cost']['by_role'].get(call['call_function'],0)+1
            record['cost']['usage_available']=bool(calls) and all(call['usage']['input_tokens'] is not None and call['usage']['output_tokens'] is not None for call in calls)
            record['app_run_id']=session['session_id']
            record['limitations'].append('Workbench job/session/signature pins are retained; ordinary product readiness pins were not observed on this separate job port.')
            record['outcome']='completed' if result['outcome'] in {'QUALIFIED','NO_IMPROVEMENT','UNEVALUATED_CANDIDATE','INCONCLUSIVE'} else 'interrupted' if result['outcome']=='CANCELLED' else 'failed'
            record['outcome_detail']={'terminal_status':result['outcome'],'stage':'rsi_session','reason':result['stop_reason'],'product_decision':result['outcome']}
            record['exports']=[{'artifact_type':r['kind'],'path':'rsi-export/'+r['path'],'sha256':r['sha256']} for r in rows]
            record['limitations'].extend(result.get('limitations',[]))
            return record
        except (OSError,ValueError,TimeoutError,asyncio.IncompleteReadError):
            record['outcome']='interrupted' if record['launched'] else 'blocked';record['outcome_detail']['reason']='protected_workbench_evidence_unavailable';return record
        finally:
            record['ended_at']=utc();record['elapsed_s']=time.monotonic()-start
            write_once(path/'run_record.json',record)
