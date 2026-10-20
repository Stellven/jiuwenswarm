"""Protected authority policy controls, not endpoint qualification evidence."""
import hashlib
import json
from datetime import datetime,timezone
import pytest
from jiuwenswarm.research.routing_authority import PublicRoutingExport,RoutingAuthority
from jiuwenswarm.research.state import SQLiteRunStore,json_bytes
from jiuwenswarm.research.router_client import PlatformIntegrityError


def test_public_export_preserves_opaque_refs_without_copying_other_store_bytes(tmp_path):
    store=SQLiteRunStore(tmp_path/'state');allowed=store.put_blob(b'accepted input',record_id='opaque:input')
    secret=store.put_blob(b'private account sentinel',record_id='private:sentinel')
    export=PublicRoutingExport(store,tmp_path/'public')
    export.publish([allowed]);index=json.loads((tmp_path/'public/ref-index.json').read_bytes())
    assert index['refs'][allowed['id']]['sha256']==allowed['sha256']
    assert secret['id'] not in index['refs']
    assert not any(b'private account sentinel' in p.read_bytes() for p in (tmp_path/'public').rglob('*') if p.is_file())
    store.close()


def test_authority_refuses_missing_real_qualification_and_rechecks_revocation(tmp_path):
    store=SQLiteRunStore(tmp_path/'state');now=datetime(2026,10,16,tzinfo=timezone.utc)
    endpoint=store.put_blob(json_bytes({'provider_id':'unit','base_url':'https://unit.invalid/v1','models':[{'model_id':'unit.executor','provider_model_name':'unit'}],
        'credential_env_var':'UNIT_KEY','timeout_s':30,'enabled':True}))
    deployment=store.put_blob(json_bytes({'model_id':'unit.executor','provider':'unit','provider_model_name':'unit','adapter_id':'native-openai-chat-v1','revision':'unit:1','endpoint_ref':endpoint}))
    qualification=store.put_blob(json_bytes({'schema':'ai4r-api-qualification:1','deployment_ref':deployment,'endpoint_ref':endpoint,'adapter_revision':'unit:1',
        'call_functions':['worker'],'task_categories':['software_systems_and_performance'],'declaration_sha256s':['a'*64],'profile_refs':[],
        'checks':[],'model_call_ref':None,'observed_runtime':False,'qualified_at':'2026-10-16T00:00:00Z','expires_at':'2026-10-17T00:00:00Z'}))
    status=tmp_path/'status.json';status.write_bytes(json_bytes({'schema':'ai4r-deployment-status:1','entries':[{'deployment_ref':deployment,'enabled':True,'revoked':False}]}))
    binding={'schema':'ai4r-routing-authority:1','router_socket':str(tmp_path/'router.sock'),'adapter_revision':'unit:1','catalog_ref':qualification,
        'profile_refs':[],'development_profiles_ref':qualification,'deployment_grants':[{'deployment_ref':deployment,'endpoint_ref':endpoint,'qualification_ref':qualification}],
        'status_path':str(status),'export_root':str(tmp_path/'public'),'audit_root':str(tmp_path/'audit')}
    authority=RoutingAuthority(store,binding,clock=lambda:now)
    with pytest.raises(ValueError,match='qualification'):authority.resolve_deployment(deployment,'worker')
    status.write_bytes(json_bytes({'schema':'ai4r-deployment-status:1','entries':[{'deployment_ref':deployment,'enabled':False,'revoked':True}]}))
    with pytest.raises(ValueError,match='revoked'):authority.resolve_deployment(deployment,'worker')
    store.close()
