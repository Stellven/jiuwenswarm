"""Actual supported HTTP boundary using an already executed frozen fault row.

No fresh workload is created here. Required scoped resources/records are failures
when absent, and idempotent repeats must preserve the exact existing run.
"""
import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from jiuwenswarm.research_records.contracts import ContractData
from jiuwenswarm.research_sidecar.client import ResearchClient,ClientError
from jiuwenswarm.research_sidecar.evidence import read_verified,unpack_authorized_archive,write_once
from jiuwenswarm.research_sidecar.frozen_records import strict_json,FrozenRecords,ref_key


@pytest.fixture
def actual_job():
    assert hasattr(os,'geteuid') and os.geteuid()==11001,'Required actual runner UID11001 is absent.'
    assert not Path('/var/run/docker.sock').exists()
    path=Path(os.environ.get('AI4R_QA_JOB','/run/ai4r-qa/job.json'))
    assert path.is_file() and not path.is_symlink(),'Required protected scoped job grant is absent.'
    job=strict_json(path.read_bytes())
    fault=job.get('delivery_fault')
    assert isinstance(fault,dict) and set(fault)=={'mode','run_id'} and fault['mode']=='discard_successful_submit_reply_once','Required pre-frozen actual delivery-loss row grant is absent.'
    root=Path(os.environ.get('AI4R_QA_ROOT','/bench'));folder=root/'campaigns'/job['campaign_id']
    results=root/'results'/job['campaign_id']/'runs'/fault['run_id']
    run=strict_json((results/'run_record.json').read_bytes())
    submission=strict_json(read_verified(folder,job['submissions'][fault['run_id']]))
    assert run['launched'] is True and run['app_run_id'] and run['request_id']==submission['client_request_id']
    return job,results,run,submission


def test_actual_lost_reply_reconciles_one_run_and_idempotent_replay_creates_no_new_calls(actual_job):
    job,folder,run,submission=actual_job
    transport=strict_json((folder/'transport-observations.json').read_bytes())
    assert transport=={'mode':'actual_http_transport','observations':[{'method':'POST','path':'/api/v1/runs',
        'observed_reply_status':200,'fault':'discard_successful_submit_reply_once','actual_response_received':True}]}
    events=strict_json((folder/'client-ledger-events.json').read_bytes())
    assert sum(e['kind']=='submitting' for e in events)==1
    assert sum(e['kind']=='delivery_ambiguous' for e in events)==1
    reconciled=[e for e in events if e['kind']=='reconciled']
    assert len(reconciled)==1 and reconciled[0]['payload']['response']['run_id']==run['app_run_id']
    frozen=FrozenRecords(folder/'export');before={ref_key(e['ref']) for e in frozen.of_kind('model-call')}
    async def check():
        client=ResearchClient(job['base_url'],job['token_file'])
        try:
            readiness=await client.readiness()
            assert readiness['ready'] is True and all(readiness['pins'].get(k)==v for k,v in job['expected_readiness_pins'].items())
            same=await client.submit(submission)
            assert same['run_id']==run['app_run_id']
            assert (await client.reconcile(submission['client_request_id']))['run_id']==run['app_run_id']
            changed={**submission,'id':'submission:controlled-conflict'}
            assert changed!=submission
            with pytest.raises(ClientError) as conflict:await client.submit(changed)
            assert conflict.value.status_code==409 and conflict.value.response_record['category']=='conflict'
            raw=await client.export_archive(run['app_run_id'])
            manifest,files=unpack_authorized_archive(raw,run_id=run['app_run_id'],audience='researcher',validate=ContractData().validate)
            observed={ref_key(row['artifact_ref']) for row in manifest['files'] if row['path'].endswith('-model-call.json')}
            assert observed==before,'Idempotent/changed-content requests caused or lost a model-call observation.'
            assert files and len(files)==len(manifest['files'])
            write_once(Path('/evidence')/'client-boundary-original-export.zip',raw)
        finally:await client.close()
    asyncio.run(check())


def test_actual_unauthenticated_and_scoped_refusals_return_only_source_errors(actual_job):
    job,_,run,_=actual_job
    control=job.get('scope_refusal')
    assert isinstance(control,dict) and set(control)=={'token_file','run_id'},'Required separately issued wrong-scope control token is absent.'
    assert control['run_id']==run['app_run_id']
    async def check():
        async with httpx.AsyncClient(base_url=job['base_url'],timeout=30,trust_env=False,follow_redirects=False) as anonymous:
            response=await anonymous.get('/api/v1/readiness')
            assert response.status_code==401
            error=response.json();ContractData().validate('client-error',error)
            assert error['category']=='auth' and error['evidence_refs']==[]
        foreign=ResearchClient(job['base_url'],control['token_file'])
        try:
            with pytest.raises(ClientError) as refusal:await foreign.export(run['app_run_id'])
            assert refusal.value.status_code in {401,403}
            assert refusal.value.response_record['category']=='auth'
        finally:await foreign.close()
    asyncio.run(check())
