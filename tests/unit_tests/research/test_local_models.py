"""Offline local model interfaces. Every provider response below is a fixture."""
import asyncio
import copy
import json
import os
from pathlib import Path
import secrets
import tempfile
from time import monotonic
import unittest

from jiuwenswarm.research.local_models import LocalModelCatalog,LocalModelClient,validate_catalog,PROTOCOL
from jiuwenswarm.research.model_settings import ModelSettingsOwner
from jiuwenswarm.research.providers import ProviderError
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore

ROOT=Path(__file__).resolve().parents[3]


def document():
    value=json.loads((ROOT/'deploy/m1/local-models.example.json').read_bytes())
    model=value['models'][0]
    model.update(id='local-unit',name='Unit fixture',model_name='unit-model',revision='unit-revision',enabled=True)
    return value


def response(model='unit-model',finish='stop',text='original model text\n'):
    return dict(outcome='completed',http_status=200,provider_request_id='unit-http-request',
        response_text=json.dumps({'model':model,'choices':[{'message':{'content':text},'finish_reason':finish}],
                                  'usage':{'prompt_tokens':12,'completion_tokens':4}}))


class FakeClient:
    def __init__(self,binding):self.binding=binding;self.trace=[]
    def preflight(self):pass
    async def invoke(self,prompt,**kwargs):
        self.trace=[('out','local-model/request-prepared',{'prompt':prompt}),('in','local-model/result',response())]
        return {'text':'original model text\n','identity':{'effective':'unit-model','basis':'provider response.model'},
                'usage':{'input_tokens':12,'output_tokens':4},'provider_request_id':'unit-http-request','observed_runtime':True}


class LocalModelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'catalog.json'
        self.uid=os.geteuid() if os.name=='posix' else 0
        self.write(document())
        self.catalog=LocalModelCatalog(self.path,owner_uid=self.uid)
        self.store=SQLiteRunStore(self.root/'store');self.addCleanup(self.store.close)
        self.owner=ModelSettingsOwner(self.store,self.root/'private/keys.json',local_catalog=self.catalog,local_client_factory=FakeClient)

    def write(self,value):
        self.path.write_text(json.dumps(value),encoding='utf-8');self.path.chmod(0o600)

    def select(self):
        return self.owner.settings({'account_id':'unit-account','action':'select','values':{'preset_id':'local-unit'}})

    def freeze(self,ident='unit-run',parent=None):
        self.store.allocate_run('unit-account','request:'+ident,'a'*64,ident,'local',{},[])
        self.owner.freeze({'account_id':'unit-account','run_id':ident,'parent_run_id':parent})
        return self.owner.for_call({'run_id':ident})

    def test_catalog_rejects_commands_public_http_and_unknown_options(self):
        for section,key,value in [('backend','target','user@host; echo unsafe'),('backend','base_url','http://example.org/v1'),
                                   ('backend','base_url','http://localhost:8000/v1'),('transport','socket_path','/a/../b')]:
            doc=document();doc[section][key]=value
            with self.assertRaises((ValueError,ResearchError)):validate_catalog(doc)
        doc=document();doc['models'][0]['arbitrary_command']='not allowed'
        with self.assertRaises(ResearchError):validate_catalog(doc)

    def test_local_selection_needs_no_api_key_and_freezes_real_policy(self):
        status=self.select();choice=next(x for x in status['choices'] if x['id']=='local-unit')
        self.assertFalse(choice['requires_api_key']);self.assertTrue(choice['configured'])
        selected=self.freeze()
        self.assertNotIn('credential_id',selected)
        deployment=self.store.read_record(selected['deployment_ref'])
        endpoint=self.store.read_record(deployment['endpoint_ref'])
        self.assertEqual(endpoint['binding_sha256'],self.catalog.resolve('local-unit')['binding_sha256'])
        self.assertEqual(deployment['provider_model_name'],'unit-model')
        self.assertNotIn('capability',json.dumps(endpoint))
        self.owner.settings({'account_id':'unit-account','action':'select','values':{'preset_id':'codex'}})
        self.owner.preflight(selected)
        self.assertEqual(self.owner.for_call({'run_id':'unit-run'})['preset_id'],'local-unit')

    def test_ui_cannot_install_url_credential_or_unknown_local_choice(self):
        for action,values in [('save',{'preset_id':'local-unit','api_key':'must-not-store'}),
                              ('select',{'preset_id':'local-unit','base_url':'http://elsewhere'}),
                              ('select',{'preset_id':'local-unknown'})]:
            with self.assertRaises(ResearchError):self.owner.settings({'account_id':'unit-account','action':action,'values':values})

    def test_host_codex_selection_freezes_adapter_and_redacts_host_paths(self):
        doc=document()
        doc['backend']={'kind':'host-codex-app-server','host_python':'/operator/python',
            'codex_executable':'C:/operator/codex.exe','working_directory':'D:/operator/work',
            'codex_sha256':'a'*64,'account_fingerprint':'b'*64}
        model=doc['models'][0]
        for key in ('max_output_tokens','temperature','enable_thinking'):model.pop(key)
        model['reasoning_effort']='medium'
        self.write(doc)
        self.select();selected=self.freeze()
        deployment=self.store.read_record(selected['deployment_ref'])
        endpoint=self.store.read_record(deployment['endpoint_ref'])
        self.assertEqual(deployment['adapter_id'],'private-host-codex-v1')
        self.assertEqual(set(endpoint['backend']),{'kind','codex_sha256','account_fingerprint'})
        self.assertEqual(endpoint['binding_sha256'],self.catalog.resolve('local-unit')['binding_sha256'])
        self.owner.preflight(selected)
        doc['backend']['working_directory']='D:/operator/new-work';self.write(doc)
        with self.assertRaises(ProviderError):self.owner.preflight(selected)

    def test_account_revocation_and_operator_revision_change_block_old_binding(self):
        self.select();selected=self.freeze()
        self.owner.settings({'account_id':'unit-account','action':'remove','values':{'preset_id':'local-unit'}})
        with self.assertRaises(ProviderError):self.owner.preflight(selected)
        self.select()
        with self.assertRaises(ProviderError):self.owner.preflight(selected)
        next_selection=self.freeze('unit-next')
        doc=document();doc['models'][0]['revision']='unit-new-revision';self.write(doc)
        with self.assertRaises(ProviderError):self.owner.preflight(next_selection)

    def test_continuation_keeps_original_binding_and_cannot_escape_revocation(self):
        self.select();original=self.freeze()
        continuation=self.freeze('unit-child',parent='unit-run')
        self.assertEqual(original['deployment_ref'],continuation['deployment_ref'])
        self.owner.settings({'account_id':'unit-account','action':'remove','values':{'preset_id':'local-unit'}})
        with self.assertRaises(ProviderError):self.owner.preflight(continuation)

    def test_broken_optional_catalog_does_not_disable_subscription_selection(self):
        self.path.write_text('{broken')
        result=self.owner.settings({'account_id':'unit-account','action':'select','values':{'preset_id':'codex'}})
        self.assertEqual(result['selected_id'],'codex');self.assertTrue(result['local_endpoints_unavailable'])

    def test_existing_bridge_captures_original_local_trace_and_identity(self):
        from jiuwenswarm.research.bridge import GovernedBridge
        self.select();self.freeze()
        ref={'id':'unit-pin','sha256':'a'*64}
        context=dict(run_id='unit-run',node_id='unit-node',subnode_id='unit-worker',attempt_id='unit-attempt',
            invocation_id='unit-invocation',execution_id='unit-execution',call_ordinal=1,call_id='unit-call',
            call_claim_ref=ref,contract_ref=ref,call_function='worker',model_selection_profile_ref=ref,deployment_ref=ref,
            limits={'time_s':5,'model_calls':1,'memory_mb':64},execution_deadline_monotonic_s=monotonic()+5,
            router={'enabled':False,'deadline_s':30,'profile_ref':None})
        bridge=GovernedBridge(persist=self.store.append_record,authorize=lambda _:context,revalidate=lambda _:context,
                              subscription_service=object(),manual_models=self.owner,read_evidence=self.store.read_blob)
        result=asyncio.run(bridge.call({},'Unit fixture prompt.'))
        self.assertEqual(result['text'],'original model text\n')
        call=self.store.read_record(result['call_ref'])
        self.assertEqual(call['identity']['effective'],'unit-model')
        traces=[r for r in call['evidence_refs'] if self.store.record_kind(r)=='native-governed-trace']
        self.assertEqual(len(traces),1)
        trace=self.store.read_record(traces[0]);self.assertEqual(len(trace['event_refs']),2)
        raw=self.store.read_record(self.store.read_record(trace['event_refs'][1])['raw_ref'])
        self.assertEqual(json.loads(raw['payload']['response_text'])['choices'][0]['message']['content'],'original model text\n')

    def _uncertain_bridge(self,fail_trace):
        from jiuwenswarm.research.bridge import GovernedBridge,BridgeError
        class UnknownClient(FakeClient):
            async def invoke(self,prompt,**kwargs):
                self.trace=[('out','local-model/request-prepared',{'prompt':prompt})]
                raise ProviderError('network_error',outcome_unknown=True,
                    observation={'observed_runtime':True,'identity':{'effective':None},'usage':{}})
        self.owner.local_client_factory=UnknownClient
        self.select();self.freeze()
        if fail_trace:
            def broken(*args,**kwargs):raise OSError('offline simulated audit failure')
            self.owner._capture_local_trace=broken
        ref={'id':'unit-pin','sha256':'a'*64}
        context=dict(run_id='unit-run',node_id='unit-node',subnode_id='unit-worker',attempt_id='unit-attempt',
            invocation_id='unit-invocation',execution_id='unit-execution',call_ordinal=1,call_id='unit-call',
            call_claim_ref=ref,contract_ref=ref,call_function='worker',model_selection_profile_ref=ref,deployment_ref=ref,
            limits={'time_s':5,'model_calls':1,'memory_mb':64},execution_deadline_monotonic_s=monotonic()+5,
            router={'enabled':False,'deadline_s':30,'profile_ref':None})
        bridge=GovernedBridge(persist=self.store.append_record,authorize=lambda _:context,revalidate=lambda _:context,
                              subscription_service=object(),manual_models=self.owner,read_evidence=self.store.read_blob)
        async def run():
            with self.assertRaises(BridgeError) as caught:await bridge.call({},'Offline uncertain fixture')
            call=self.store.read_record(caught.exception.call_ref)
            self.assertEqual(call['outcome'],'outcome_unknown');self.assertIsNone(call['ended_at'])
            with self.assertRaises(BridgeError) as containment:
                await bridge.contain_run({'authorized':True,'run_id':'unit-run','request_id':'unit-cancel'})
            self.assertEqual(containment.exception.code,'CONTAINMENT_UNCERTAIN')
        asyncio.run(run())

    def test_lost_local_reply_never_reports_remote_containment(self):
        self._uncertain_bridge(False)

    def test_failed_trace_capture_preserves_original_delivery_uncertainty(self):
        self._uncertain_bridge(True)


class ClientTests(unittest.TestCase):
    def binding(self):
        doc=document()
        return dict(model=doc['models'][0],backend=doc['backend'],transport=doc['transport'],gateway_id=doc['gateway_id'],binding_sha256='a'*64)

    def client(self,result):
        calls=[]
        class RPC:
            def __init__(self,*args,**kwargs):pass
            async def call(self,operation,payload,**kwargs):
                calls.append(payload)
                if isinstance(result,BaseException):raise result
                return dict(request_id=payload['request_id'],binding_sha256=payload['binding_sha256'],**result)
        client=LocalModelClient(self.binding(),rpc_factory=RPC)
        client.preflight=lambda:{'session_id':'unit-session-secret','capability':'unit-capability-secret'}
        return client,calls

    def test_response_bytes_model_identity_and_usage_are_not_rewritten(self):
        client,calls=self.client(response(model='actually-served-model'))
        result=asyncio.run(client.invoke('unit prompt',timeout_s=2,call_function='worker'))
        self.assertEqual(result['identity']['effective'],'actually-served-model')
        self.assertEqual(result['text'],'original model text\n')
        self.assertEqual(result['usage']['input_tokens'],12);self.assertEqual(len(calls),1)
        self.assertNotIn('secret',json.dumps(client.trace))

    def test_truncated_content_is_rejected_without_repair_and_usage_retained(self):
        client,calls=self.client(response(finish='length',text='{"unfinished":'))
        with self.assertRaises(ProviderError) as raised:asyncio.run(client.invoke('unit prompt',timeout_s=2,call_function='worker'))
        self.assertEqual(raised.exception.code,'invalid_output')
        self.assertEqual(raised.exception.observation['usage']['input_tokens'],12)
        self.assertEqual(len(calls),1)

    def test_cancellation_is_uncertain_and_never_retried(self):
        client,calls=self.client(asyncio.CancelledError())
        with self.assertRaises(ProviderError) as raised:asyncio.run(client.invoke('unit prompt',timeout_s=2,call_function='worker'))
        self.assertEqual(raised.exception.code,'CONTAINMENT_UNCERTAIN');self.assertTrue(raised.exception.outcome_unknown)
        self.assertEqual(len(calls),1)

    def test_prompt_limit_blocks_before_rpc(self):
        client,calls=self.client(response())
        with self.assertRaises(ProviderError):asyncio.run(client.invoke('x'*300000,timeout_s=2,call_function='worker'))
        self.assertEqual(calls,[])


@unittest.skipUnless(os.name=='posix','Linux/WSL private RPC integration')
class PrivateRPCTests(unittest.TestCase):
    def test_socket_export_preserves_setgid_directory_and_private_runtime(self):
        from jiuwenswarm.research.private_rpc import PrivateRPCServer
        import stat
        async def run():
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);export=root/'export';export.mkdir();export.chmod(0o2710)
                private=root/'private';private.mkdir(mode=0o700)
                group=export.stat().st_gid
                server=PrivateRPCServer(export/'model.sock',protocol=PROTOCOL,
                    session_id='offline-session',capability='offline-capability',handlers={'invoke':lambda p:{}},
                    allowed_uids={os.geteuid()},socket_mode=0o660,directory_mode=0o2710)
                await server.start()
                try:
                    info=(export/'model.sock').stat()
                    self.assertTrue(stat.S_ISSOCK(info.st_mode));self.assertEqual(info.st_gid,group)
                    self.assertEqual(stat.S_IMODE(info.st_mode),0o660)
                    self.assertEqual(stat.S_IMODE(export.stat().st_mode),0o2710)
                    self.assertEqual(stat.S_IMODE(private.stat().st_mode),0o700)
                finally:await server.close()
        asyncio.run(run())

    def test_client_to_real_private_rpc_relay_with_fixture_backend(self):
        from jiuwenswarm.research.local_model_relay import LocalModelRelay
        from jiuwenswarm.research.private_rpc import PrivateRPCServer
        async def run():
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);runtime=root/'runtime';runtime.mkdir(mode=0o700)
                doc=document();doc['transport'].update(socket_path=str(runtime/'model.sock'),session_file=str(runtime/'session.json'),
                                                     peer_uid=os.geteuid(),socket_mode=0o600)
                path=root/'catalog.json';path.write_text(json.dumps(doc));path.chmod(0o600)
                session={'session_id':secrets.token_hex(16),'capability':secrets.token_hex(32)}
                session_path=runtime/'session.json';session_path.write_text(json.dumps(session));session_path.chmod(0o600)
                catalog=LocalModelCatalog(path,owner_uid=os.geteuid());seen=[]
                async def backend(binding,payload):seen.append(payload);return response()
                relay=LocalModelRelay(catalog,runtime,backend=backend)
                server=PrivateRPCServer(runtime/'model.sock',protocol=PROTOCOL,allowed_uids={os.geteuid()},handlers={'invoke':relay.invoke},**session)
                await server.start()
                try:
                    result=await LocalModelClient(catalog.resolve('local-unit')).invoke('offline RPC fixture',timeout_s=2,call_function='worker')
                    self.assertEqual(result['text'],'original model text\n');self.assertEqual(len(seen),1)
                finally:await server.close();relay.close()
        asyncio.run(run())


if __name__=='__main__':unittest.main()
