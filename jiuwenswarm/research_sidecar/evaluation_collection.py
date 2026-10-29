"""Fresh GET-only evidence generation for an already submitted E3 evaluation."""
import argparse
import asyncio
import copy
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile

import httpx
from .client import ResearchClient
from .evidence import canonical,read_verified,relative,write_once
from .evaluation_records import EvaluationRecords

ROW_KEYS=('run_id','campaign_id','case_id','case_version','config_id','repeat_index')
CONFIG_KEYS={'schema','original_root','new_root','row','expected_request','original_pins','base_url','http_authority'}


class GetOnlyTransport(httpx.AsyncBaseTransport):
    """Reject an accidental submission before any network bytes are written."""
    def __init__(self,inner=None):self.inner=inner or httpx.AsyncHTTPTransport(trust_env=False)
    async def handle_async_request(self,request):
        if request.method!='GET':raise ValueError('Collection permits GET only')
        return await self.inner.handle_async_request(request)
    async def aclose(self):await self.inner.aclose()


def validate_source(config):
    if set(config)!=CONFIG_KEYS or config['schema']!='evaluation-collection:1':raise ValueError('Invalid collection config')
    row=config['row'];expected=config['expected_request']
    if set(row)!=set(ROW_KEYS) or not isinstance(row['run_id'],str) or relative(row['run_id']).name!=row['run_id']:
        raise ValueError('Invalid scheduled row')
    old=Path(config['original_root']);new=Path(config['new_root'])
    if not old.is_absolute() or not new.is_absolute() or any(p.is_symlink() for p in (old,*old.parents,new,*new.parents)):
        raise ValueError('Unsafe collection root')
    old=old.resolve(strict=True);new=new.resolve()
    if new.exists() or new.is_relative_to(old) or old.is_relative_to(new):raise ValueError('Fresh separate generation required')
    prefix='runs/'+row['run_id']+'/'
    required={prefix+'run_record.json',prefix+'evaluation-request.json','ledger.sqlite'}
    pins=config['original_pins']
    if not isinstance(pins,dict) or not required<=set(pins) or set(pins)-required-{'ledger.sqlite-wal'}:
        raise ValueError('Exact original record/request/ledger pins required')
    if (old/'ledger.sqlite-wal').exists()!=('ledger.sqlite-wal' in pins):raise ValueError('Unpinned ledger WAL')
    raw={name:read_verified(old,{'path':name,'sha256':digest},max_bytes=128*1024*1024) for name,digest in pins.items()}
    previous=json.loads(raw[prefix+'run_record.json']);request=json.loads(raw[prefix+'evaluation-request.json'])
    if (request!=expected or any(previous.get(k)!=row[k] for k in ROW_KEYS)
            or previous.get('request_id')!=expected.get('request_id') or previous.get('entry_mode')!='single_cc'
            or expected.get('campaign_id')!=row['campaign_id'] or expected.get('case_id')!=row['case_id']):
        raise ValueError('Original row or request differs')
    fingerprint=hashlib.sha256(canonical({'entry_mode':'single_cc','request':expected})).hexdigest()
    # SQLite readers can create SHM beside a WAL database even with mode=ro.
    # Query an exact pinned DB+WAL copy, never the historical directory itself.
    with tempfile.TemporaryDirectory(prefix='evaluation-collection-ledger-') as temporary:
        snapshot=Path(temporary)/'ledger.sqlite'
        snapshot.write_bytes(raw['ledger.sqlite'])
        if 'ledger.sqlite-wal' in raw:(Path(temporary)/'ledger.sqlite-wal').write_bytes(raw['ledger.sqlite-wal'])
        with closing(sqlite3.connect(snapshot.as_uri()+'?mode=ro',uri=True)) as db:
            db.execute('BEGIN')
            claim=db.execute('SELECT fingerprint FROM attempts WHERE id=?',(row['run_id'],)).fetchone()
            events=[{'sequence':r[0],'kind':r[1],'payload':json.loads(r[2])} for r in db.execute(
                'SELECT seq,kind,payload FROM events WHERE id=? ORDER BY seq',(row['run_id'],))]
    if claim!=(fingerprint,) or not any(e['kind']=='evaluation_submitting' and
        e['payload']=={'request_id':expected['request_id'],'entry_mode':'single_cc'} for e in events):
        raise ValueError('Original durable submission is absent or different')
    for name,data in raw.items():
        if read_verified(old,{'path':name,'sha256':pins[name]},max_bytes=128*1024*1024)!=data:
            raise ValueError('Original history changed')
    return old,new,previous,raw,events


async def collect(config,client):
    old,new,previous,originals,events=validate_source(config)
    row=config['row'];expected=config['expected_request'];request_id=expected['request_id']
    # These are the only two client operations this collector can issue.
    reconciled=await client.evaluation_request(request_id)
    if (reconciled.get('request_id')!=request_id or reconciled.get('status')!='completed'
            or reconciled.get('invalid_for_product') is not True or not isinstance(reconciled.get('result'),dict)):
        raise ValueError('Scoped original evaluation is not completed')
    raw=await client.evaluation_export_archive(request_id)
    frozen=EvaluationRecords.from_archive(raw,request_id=request_id,campaign_id=row['campaign_id'],
        audience='researcher',expected_request=expected)
    frozen.require_complete()
    if frozen.request['entry_point']!='E3' or frozen.response()!=reconciled['result'] or reconciled['result']['status']!='completed':
        raise ValueError('Original E3 response differs from authenticated GET')
    # Verify the historical input again after network observation, before publication.
    validate_source(config)
    path=new/'runs'/row['run_id'];new.mkdir(parents=True,exist_ok=False)
    exports=[]
    def retain(name,data,kind):
        pin=write_once(path/name,data);exports.append({'artifact_type':kind,'path':name,'sha256':pin['sha256']})
    prefix='runs/'+row['run_id']+'/'
    retain('source-history/run_record.json',originals[prefix+'run_record.json'],'prior-run-record')
    retain('evaluation-request.json',originals[prefix+'evaluation-request.json'],'evaluation-source-request')
    retain('source-history/ledger-events.json',events,'original-submission-events')
    retain('evaluation-reconciliation.json',reconciled,'evaluation-get-reconciliation')
    retain('evaluation-result.json',reconciled['result'],'evaluation-http-result')
    retain('evaluation-export-received.zip',raw,'evaluation-original-zip')
    frozen.freeze(path/'evaluation-export')
    exports.extend([{'artifact_type':'evaluation-original-zip','path':'evaluation-export/archive.zip','sha256':hashlib.sha256(raw).hexdigest()},
        *[{'artifact_type':'evaluation-manifest' if name=='evaluation_export.json' else 'evaluation-original',
           'path':'evaluation-export/'+name,'sha256':hashlib.sha256(data).hexdigest()} for name,data in frozen.entries.items()]])
    retain('evaluation-http-captures.json',{'responses':getattr(client,'evaluation_http_captures',[])},'evaluation-http-captures')
    calls=frozen.model_call_rows();record=copy.deepcopy(previous)
    record.update(launched=True,started_at=None,ended_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        elapsed_s=None,active_s=None,external_wait_s=None,outcome='completed',exports=exports,model_calls=calls)
    record['outcome_detail']={'terminal_status':'completed','stage':'read_only_collection',
        'reason':reconciled['result'].get('reason'),'product_decision':None}
    record['cost']={'usage_available':bool(calls) and all(c['input_tokens'] is not None and c['output_tokens'] is not None for c in calls),
        'total_calls':len(calls),'by_role':{role:sum(c['role']==role for c in calls) for role in {c['role'] for c in calls}},
        'monetary':None,'price_schedule_ref':None,'note':'Exact original ModelCalls; no new model execution.'}
    record['limitations']=[*previous.get('limitations',[]),
        'Fresh GET-only evidence collection of the original submitted E3 request; prior run record retained unchanged. Collection end time is not execution end time; original start and provider latency remain unavailable.']
    retain('collection-generation.json',{'schema':'evaluation-collection-generation:1','original_root':str(old),
        'original_pins':config['original_pins'],'request_id':request_id,'row':row,'new_submission':False,
        'launched_basis':'Authenticated scoped GET agrees with complete validated original E3 request/export.'},'collection-generation')
    record['exports']=exports
    write_once(path/'run_record.json',record)
    for name in originals:read_verified(old,{'path':name,'sha256':config['original_pins'][name]},max_bytes=128*1024*1024)
    return record


async def run(config,credential_file):
    validate_source(config)
    client=ResearchClient(config['base_url'],credential_file,timeout=120,
        http_authority=config['http_authority'],transport=GetOnlyTransport())
    try:return await collect(config,client)
    finally:await client.http.aclose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--credential-file',type=Path,required=True)
    args=parser.parse_args();record=asyncio.run(run(json.loads(args.config.read_bytes()),args.credential_file))
    print(json.dumps({'run_id':record['run_id'],'outcome':record['outcome'],'new_submission':False}))


if __name__=='__main__':main()
