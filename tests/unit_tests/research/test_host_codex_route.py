"""Offline host-account routing fixtures. Never start Codex, SSH, or a model."""
import asyncio
import copy
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from jiuwenswarm.research import local_model_codex as helper
from tests.unit_tests.research.test_host_codex_helper import FakeProcess, EMAIL
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.local_models import (LocalModelClient, validate_catalog,
    native_codex_response, native_absolute_path)
from jiuwenswarm.research.local_model_relay import LocalModelRelay, HostCodexBackend, BackendRouter, backend_output, host_backend_output
from jiuwenswarm.research.providers import ProviderError

ROOT=Path(__file__).resolve().parents[3]
PIN='a'*64
PROMPT='Original prompt; $(not-a-command)\n'


def document():
    return {'schema':'ai4r-local-model-catalog:1','gateway_id':'host-fixture',
        'backend':{'kind':'host-codex-app-server','host_python':'/mnt/fixture/python.exe',
            'codex_executable':'C:/fixture/codex.exe','working_directory':'C:/fixture/work',
            'codex_sha256':'b'*64,'account_fingerprint':'c'*64},
        'transport':{'socket_path':'/run/ai4r-local-model/model.sock',
            'session_file':'/run/ai4r-local-model-config/session.json','peer_uid':1000,'socket_mode':0o660},
        'models':[{'id':'local-host-codex61','name':'Host native fixture','model_name':'gpt-6.1-sol',
            'revision':'fixture-r1','enabled':True,'context_window':32768,'max_prompt_bytes':2048,
            'timeout_s':30,'reasoning_effort':'medium'}]}


def binding():
    doc=document()
    return {'model':doc['models'][0],**{key:doc[key] for key in ('backend','transport','gateway_id')},'binding_sha256':PIN}


def native(*,outcome='completed',error=None):
    value={'schema':'ai4r-host-codex-response:1','requested_model':'gpt-6.1-sol',
        'account_fingerprint':'c'*64,'binary_sha256':'b'*64,'reasoning_effort':'medium',
        'thread_start':{'thread':{'id':'thread-fixture'},'model':'gpt-6.1-sol','reasoningEffort':'medium'},
        'turn_start':{'turn':{'id':'turn-fixture','status':'inProgress','items':[]}},
        'turn_completed':{'threadId':'thread-fixture','turn':{'id':'turn-fixture','status':'completed',
            'items':[{'id':'message-fixture','type':'agentMessage','text':'  original output }\n'}]}},
        'wire_frames':[],'error_code':error,'outcome':outcome}
    def add(direction,payload):value['wire_frames'].append({'direction':direction,'raw':json.dumps(payload)+'\n'})
    add('out',{'id':1,'method':'thread/start','params':{'model':'gpt-6.1-sol','config':{'model_reasoning_effort':'medium'}}})
    add('in',{'id':1,'result':value['thread_start']})
    add('out',{'id':2,'method':'turn/start','params':{'threadId':'thread-fixture','model':'gpt-6.1-sol',
        'input':[{'type':'text','text':PROMPT}]}})
    add('in',{'id':2,'result':value['turn_start']})
    add('in',{'method':'thread/tokenUsage/updated','params':{'threadId':'thread-fixture','turnId':'turn-fixture',
        'tokenUsage':{'last':{'inputTokens':12,'outputTokens':7}}}})
    if outcome=='completed':add('in',{'method':'turn/completed','params':value['turn_completed']})
    else:value['turn_completed']=None
    return value


def response(value):
    return dict(outcome=value['outcome'],http_status=None,response_text=json.dumps(value),
        provider_request_id=(value['turn_start'] or {}).get('turn',{}).get('id'))


def preturn(*,error='auth_failed',resolved=False):
    value=native(outcome='failed',error=error)
    value['turn_start']=None;value['turn_completed']=None
    value['wire_frames']=value['wire_frames'][:2] if resolved else []
    if not resolved:
        value['thread_start']=None;value['account_fingerprint']=None
    return value


def compact(value, *, full=True):
    return helper.pack_bundle(value,value['wire_frames'],full=full,
        observed_frames=len(value['wire_frames']),
        observed_bytes=sum(len(frame['raw'].encode('utf-8')) for frame in value['wire_frames']))


def refused():
    value=native()
    value['outcome']='failed';value['error_code']='provider_error'
    value['wire_frames'][-1:-1]=[
        {'direction':'in','raw':json.dumps({'id':999,'method':'item/commandExecution/requestApproval',
            'params':{'threadId':'thread-fixture','turnId':'turn-fixture'}})+'\n'},
        {'direction':'out','raw':json.dumps({'id':999,'error':{'code':-32601,
            'message':'Tools and approvals are unavailable.'}})+'\n'}]
    return value


class HostCodexCatalogTests(unittest.TestCase):
    def test_closed_operator_policy_and_stdlib_validator_agree(self):
        self.assertEqual(validate_catalog(document()),document())
        spec=importlib.util.spec_from_file_location('codex_operator_fixture',ROOT/'deploy/m1/local_model_operator.py')
        operator=importlib.util.module_from_spec(spec);spec.loader.exec_module(operator)
        self.assertEqual(operator.validate_catalog(document()),document())
        for field,value in [('host_python','C:/fixture/python.exe'),('codex_executable','//server/share/codex.exe'),
            ('working_directory','C:/fixture/../private'),('codex_sha256','invalid'),('account_fingerprint','invalid')]:
            changed=document();changed['backend'][field]=value
            for validator,error in ((validate_catalog,ResearchError),(operator.validate_catalog,ValueError)):
                with self.assertRaises(error):validator(changed)
        for extra in ('max_output_tokens','temperature','enable_thinking'):
            changed=document();changed['models'][0][extra]=1
            with self.assertRaises(ResearchError):validate_catalog(changed)
        changed=document();changed['models'][0]['reasoning_effort']='xhigh'
        with self.assertRaises(ResearchError):validate_catalog(changed)
        changed=document();changed['backend']['base_url']='http://127.0.0.1:8000/v1'
        with self.assertRaises(ResearchError):validate_catalog(changed)

    def test_native_path_custody_is_static_and_canonical(self):
        for value in ('C:/fixture/codex.exe','/opt/fixture/codex'):
            self.assertTrue(native_absolute_path(value))
        for value in ('C:\\fixture\\codex.exe','relative','//server/share/file','C:/a/../file','/a//file','/a/./file','/a/line\n'):
            self.assertFalse(native_absolute_path(value))


class NativeWireTests(unittest.TestCase):
    def test_original_identity_native_usage_and_unrepaired_text(self):
        bundle,observation,text=native_codex_response(json.dumps(native()),binding(),prompt=PROMPT)
        self.assertEqual(text,'  original output }\n')
        self.assertEqual(observation['identity'],{'effective':'gpt-6.1-sol','basis':'host Codex app-server resolved model'})
        self.assertEqual(observation['usage']['input_tokens'],12)
        self.assertEqual(observation['usage']['output_tokens'],7)
        self.assertEqual(observation['provider_request_id'],'turn-fixture')

    def test_pins_prompt_model_turn_and_tool_frames_cannot_be_substituted(self):
        changes=[]
        value=native();value['account_fingerprint']='d'*64;changes.append(value)
        value=native();value['binary_sha256']='d'*64;changes.append(value)
        value=native();frame=json.loads(value['wire_frames'][2]['raw']);frame['params']['input'][0]['text']='changed';value['wire_frames'][2]['raw']=json.dumps(frame);changes.append(value)
        value=native();value['turn_completed']['turn']['id']='foreign';changes.append(value)
        for method in ('model/rerouted','item/commandExecution/started'):
            value=native();value['wire_frames'].append({'direction':'in','raw':json.dumps({'method':method,'params':{}})});changes.append(value)
        value=native();value['wire_frames'].append({'direction':'in','raw':json.dumps({'id':50,'method':'item/tool/request','params':{}})});changes.append(value)
        value=native();value['thread_start']['reasoningEffort']='high';changes.append(value)
        for value in changes:
            with self.assertRaises((ResearchError,ValueError)):
                native_codex_response(json.dumps(value),binding(),prompt=PROMPT)

    def test_pre_auth_failure_and_pre_turn_timeout_are_known_without_identity(self):
        for code in ('auth_failed','timeout','invalid_request'):
            value=preturn(error=code)
            if code!='auth_failed':value['binary_sha256']=None
            _,observation,_=native_codex_response(json.dumps(value),binding(),prompt=PROMPT)
            self.assertIsNone(observation['identity']['effective'])
            self.assertIsNone(observation['provider_request_id'])

    def test_native_resolved_model_rejection_is_failed_before_any_turn(self):
        value=preturn(error='invalid_output',resolved=True)
        value['thread_start']['model']='other-model'
        frame=json.loads(value['wire_frames'][1]['raw']);frame['result']=value['thread_start']
        value['wire_frames'][1]['raw']=json.dumps(frame)
        _,observation,_=native_codex_response(json.dumps(value),binding(),prompt=PROMPT)
        self.assertEqual(observation['identity']['effective'],'other-model')
        self.assertEqual(observation['identity']['basis'],'host Codex app-server pre-turn model resolution')

    def test_unacknowledged_native_turn_cannot_be_claimed_failed(self):
        value=native(outcome='failed',error='timeout')
        with self.assertRaises(ResearchError):native_codex_response(json.dumps(value),binding(),prompt=PROMPT)

    def test_v2_original_frames_refs_counts_and_legacy_many_small_frames(self):
        value=native()
        value['wire_frames'][-1:-1]=[{'direction':'in','raw':json.dumps({'method':'item/agentMessage/delta',
            'params':{'threadId':'thread-fixture','turnId':'turn-fixture','delta':'x'}})+'\n'}]*4200
        for receipt in (value,compact(value)):
            _,observation,text=native_codex_response(json.dumps(receipt),binding(),prompt=PROMPT)
            self.assertEqual(text,'  original output }\n')
            self.assertEqual(observation['provider_request_id'],'turn-fixture')

    def test_v2_invalid_refs_counts_and_false_success_are_rejected(self):
        changes=[]
        value=compact(native());value['turn_completed']=True;changes.append(value)
        value=compact(native());value['turn_completed']=value['turn_start'];changes.append(value)
        value=compact(native());value['thread_start']=-1;changes.append(value)
        value=compact(native());value['evidence']['observed_frames']=True;changes.append(value)
        value=compact(native());value['evidence']['observed_bytes']-=1;changes.append(value)
        value=compact(native());value['evidence']['observed_frames']+=1;changes.append(value)
        value=compact(native());value['evidence']['full_original_trace']=False;value['evidence']['unavailable_reason']='wire_budget';changes.append(value)
        value=compact(native());value['wire_frames'][0]['raw_b64']='bad!';changes.append(value)
        for value in changes:
            with self.assertRaises((ResearchError,ValueError)):
                native_codex_response(json.dumps(value),binding(),prompt=PROMPT)

    def test_incomplete_empty_failure_cannot_hide_a_dispatched_turn(self):
        value=compact(native(outcome='failed',error='invalid_output'))
        value.update(thread_start=None,turn_start=None,turn_completed=None,wire_frames=[],account_fingerprint=None,binary_sha256=None)
        value['evidence'].update(full_original_trace=False,unavailable_reason='wire_budget')
        with self.assertRaises(ResearchError):
            native_codex_response(json.dumps(value),binding(),prompt=PROMPT)

    def test_matching_refusal_without_terminal_retains_unknown_original_receipt(self):
        value=refused();value['outcome']='outcome_unknown';value['error_code']='CONTAINMENT_UNCERTAIN'
        value['turn_completed']=None;value['wire_frames'].pop()
        bundle,observation,text=native_codex_response(json.dumps(compact(value)),binding(),prompt=PROMPT)
        self.assertEqual(bundle['outcome'],'outcome_unknown')
        self.assertEqual(observation['provider_request_id'],'turn-fixture')

    def test_only_original_matching_owned_refusal_and_actual_terminal_are_known_failed(self):
        value=refused()
        native_codex_response(json.dumps(compact(value)),binding(),prompt=PROMPT)
        changes=[]
        value=refused();value['wire_frames'].pop(-2);changes.append(value)
        value=refused();frame=json.loads(value['wire_frames'][-3]['raw']);frame['params']['threadId']='foreign';value['wire_frames'][-3]['raw']=json.dumps(frame);changes.append(value)
        value=refused();frame=json.loads(value['wire_frames'][-3]['raw']);frame['params']['turnId']='foreign';value['wire_frames'][-3]['raw']=json.dumps(frame);changes.append(value)
        value=refused();frame=json.loads(value['wire_frames'][-2]['raw']);frame['id']=998;value['wire_frames'][-2]['raw']=json.dumps(frame);changes.append(value)
        value=refused();frame=json.loads(value['wire_frames'][-2]['raw']);frame['result']={};value['wire_frames'][-2]['raw']=json.dumps(frame);changes.append(value)
        value=refused();value['wire_frames'][-3],value['wire_frames'][-2]=value['wire_frames'][-2],value['wire_frames'][-3];changes.append(value)
        value=refused();value['outcome']='completed';value['error_code']=None;changes.append(value)
        value=refused();value['turn_completed']=None;value['wire_frames'].pop();changes.append(value)
        for status in ('inProgress',None,'made-up'):
            value=refused();value['turn_completed']['turn']['status']=status
            value['wire_frames'][-1]['raw']=json.dumps({'method':'turn/completed','params':value['turn_completed']})
            changes.append(value)
        for value in changes:
            with self.assertRaises((ResearchError,ValueError)):
                native_codex_response(json.dumps(compact(value)),binding(),prompt=PROMPT)


class NativeClientTests(unittest.IsolatedAsyncioTestCase):
    def client(self,result):
        class RPC:
            def __init__(self,*args,**kwargs):pass
            async def call(self,operation,payload,**kwargs):
                return {'request_id':payload['request_id'],'binding_sha256':PIN,**result}
        client=LocalModelClient(binding(),rpc_factory=RPC)
        client.preflight=lambda:{'session_id':'fixture','capability':'fixture-capability'}
        return client

    async def test_completed_native_text_and_trace_are_original(self):
        result=response(native());client=self.client(result)
        value=await client.invoke(PROMPT,timeout_s=10,call_function='worker')
        self.assertEqual(value['text'],'  original output }\n')
        self.assertEqual(client.trace[-1][2]['response_text'],result['response_text'])
        self.assertIsNone(client.trace[-1][2]['http_status'])

    async def test_partial_native_unknown_retains_identity_usage_and_original_bundle(self):
        result=response(native(outcome='outcome_unknown',error='CONTAINMENT_UNCERTAIN'))
        client=self.client(result)
        with self.assertRaises(ProviderError) as caught:
            await client.invoke(PROMPT,timeout_s=10,call_function='worker')
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual(caught.exception.code,'CONTAINMENT_UNCERTAIN')
        self.assertEqual(caught.exception.observation['identity']['effective'],'gpt-6.1-sol')
        self.assertEqual(caught.exception.observation['usage']['input_tokens'],12)
        self.assertEqual(client.trace[-1][2]['response_text'],result['response_text'])


class NativeRelayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.runtime=Path(self.temp.name);self.runtime.chmod(0o700)
        self.custody=patch('jiuwenswarm.research.local_model_relay.private_path') if os.name=='nt' else None
        if self.custody:self.custody.start()
        class Catalog:
            def resolve(self,*args,**kwargs):return binding()
        self.backend=AsyncMock(return_value=response(native()))
        self.relay=LocalModelRelay(Catalog(),self.runtime,backend=self.backend)
        self.payload={'request_id':'native-one','endpoint_id':'local-host-codex61','binding_sha256':PIN,
            'model':'gpt-6.1-sol','prompt':PROMPT,'timeout_s':10}

    def tearDown(self):
        self.relay.close()
        if self.custody:self.custody.stop()
        self.temp.cleanup()

    async def test_native_completed_has_no_fabricated_http_status_and_is_replayed(self):
        result=await self.relay.invoke(self.payload)
        self.assertEqual(result['outcome'],'completed');self.assertIsNone(result['http_status'])
        self.assertEqual(result,await self.relay.invoke(self.payload));self.backend.assert_awaited_once()

    async def test_known_pre_turn_auth_failure_does_not_latch_new_effects(self):
        self.backend.side_effect=[response(preturn()),response(native())]
        failed=await self.relay.invoke(self.payload)
        self.assertEqual(failed['outcome'],'failed');self.assertIsNone(failed['http_status'])
        second=await self.relay.invoke({**self.payload,'request_id':'native-two'})
        self.assertEqual(second['outcome'],'completed')

    async def test_native_unknown_keeps_raw_partial_and_blocks_new_effects(self):
        original=response(native(outcome='outcome_unknown',error='CONTAINMENT_UNCERTAIN'))
        self.backend.return_value=original
        result=await self.relay.invoke(self.payload)
        self.assertEqual(result['response_text'],original['response_text'])
        self.assertEqual(await self.relay.invoke(self.payload),result)
        with self.assertRaises(ResearchError):await self.relay.invoke({**self.payload,'request_id':'native-two'})
        self.backend.assert_awaited_once()


    async def helper_receipt(self,**options):
        binary=self.runtime/('fixture.exe' if os.name=='nt' else 'fixture-codex')
        binary.write_bytes(b'offline helper fixture')
        actual=binding()
        actual['backend']={**actual['backend'],'codex_executable':str(binary),
            'working_directory':str(self.runtime),'codex_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'account_fingerprint':hashlib.sha256(EMAIL.encode()).hexdigest()}
        processes=[]
        async def spawn(*args,**kwargs):
            process=FakeProcess(**options);processes.append(process);return process
        result=await helper.execute_async({'model':actual['model'],'prompt':PROMPT,'timeout_s':2,
            **{key:actual['backend'][key] for key in ('codex_executable','working_directory','codex_sha256','account_fingerprint')}},
            spawn=spawn,profile_resolver=lambda:self.runtime)
        stdout=helper._json(result).encode('utf-8')
        return actual,backend_output(stdout,0,host_backend_output),stdout,processes

    async def test_actual_helper_refusal_reaches_client_as_known_failed_without_extra_effect(self):
        actual,receipt,stdout,processes=await self.helper_receipt(tool_request=True)
        self.relay.catalog=Mock();self.relay.catalog.resolve.return_value=actual
        self.backend.return_value=receipt
        relay=self.relay
        class RPC:
            def __init__(self,*args,**kwargs):pass
            async def call(self,method,payload,timeout_s):return await relay.invoke(payload)
        client=LocalModelClient(actual,rpc_factory=RPC)
        client.preflight=Mock(return_value={'session_id':'a'*32,'capability':'b'*32})
        with self.assertRaises(ProviderError) as failure:
            await client.invoke(PROMPT,timeout_s=10,call_function='worker')
        self.assertEqual(failure.exception.code,'provider_error')
        self.assertFalse(failure.exception.outcome_unknown)
        self.backend.assert_awaited_once()
        self.assertEqual(sum(msg.get('method')=='turn/start' for msg in processes[0].requests),1)
        self.assertEqual(sum(msg.get('method')=='turn/interrupt' for msg in processes[0].requests),1)
        self.assertEqual([msg for msg in processes[0].requests if msg.get('id')==999],
            [{'id':999,'error':{'code':-32601,'message':'Tools and approvals are unavailable.'}}])
        self.assertEqual(self.relay.db.execute("SELECT COUNT(*) FROM requests WHERE result IS NULL OR json_extract(result,'$.outcome')='outcome_unknown'").fetchone()[0],0)

    async def test_actual_helper_overflow_preserves_private_stdout_and_known_terminal(self):
        actual,receipt,stdout,processes=await self.helper_receipt(deltas=5000,hang=True)
        self.relay.catalog=Mock();self.relay.catalog.resolve.return_value=actual
        self.backend.return_value=receipt
        result=await self.relay.invoke(self.payload)
        self.assertEqual(result['outcome'],'failed')
        self.assertNotIn('_private_evidence',result)
        _,observation,_=native_codex_response(result['response_text'],actual,prompt=PROMPT)
        self.assertEqual(observation['provider_request_id'],'turn-1')
        files=list((self.runtime/'backend-receipts').glob('*.receipt'))
        self.assertEqual(len(files),1);self.assertEqual(files[0].read_bytes(),stdout)
        diagnostic=json.loads(next((self.runtime/'backend-receipts').glob('*.json')).read_bytes())
        self.assertEqual(diagnostic['reason'],'accepted')
        self.assertFalse(diagnostic['counts']['full_original_trace'])
        self.assertEqual(diagnostic['counts']['terminal_status'],'interrupted')
        self.assertGreater(diagnostic['counts']['observed_wire_frames'],diagnostic['counts']['wire_frames'])

    async def test_malformed_private_carrier_keeps_original_stdout_and_cannot_complete(self):
        value=response(native());value['_private_evidence']={'schema':'untrusted'}
        stdout=json.dumps(value).encode()
        receipt=backend_output(stdout,0,host_backend_output)
        self.assertEqual(receipt.original_bytes,stdout)
        self.assertEqual(receipt.transport_error,'invalid_json')
        self.backend.return_value=receipt
        result=await self.relay.invoke(self.payload)
        self.assertEqual(result['outcome'],'outcome_unknown')
        files=list((self.runtime/'backend-receipts').glob('*.receipt'))
        self.assertEqual(files[0].read_bytes(),stdout)

    async def test_backend_dispatches_fixed_host_program_with_prompt_only_on_stdin(self):
        result=response(native())
        class Input:
            def __init__(self):self.data=b''
            def write(self,raw):self.data+=raw
            async def drain(self):pass
            def close(self):pass
        class Output:
            def __init__(self):self.data=json.dumps(result).encode()
            async def read(self,count):
                chunk,self.data=self.data[:count],self.data[count:]
                return chunk
        process=Mock();process.stdin=Input();process.stdout=Output();process.returncode=None
        process.stderr=Output();process.stderr.data=b''
        async def wait():process.returncode=0
        process.wait=wait
        with patch('asyncio.create_subprocess_exec',AsyncMock(return_value=process)) as spawn:
            actual=await HostCodexBackend()(binding(),self.payload)
        self.assertEqual(actual,result)
        argv=spawn.await_args.args
        self.assertEqual(argv[:3],('/mnt/fixture/python.exe','-B','-c'))
        self.assertNotIn(PROMPT,str(argv))
        wire=json.loads(process.stdin.data)
        self.assertEqual(set(wire),{'model','prompt','timeout_s','codex_executable','codex_sha256','account_fingerprint','working_directory'})
        self.assertEqual(wire['prompt'],PROMPT)
        router=BackendRouter();router.codex=AsyncMock(return_value=result);router.ssh=AsyncMock()
        self.assertEqual(await router(binding(),self.payload),result);router.ssh.assert_not_awaited()


if __name__=='__main__':unittest.main()
