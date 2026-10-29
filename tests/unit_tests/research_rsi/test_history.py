"""Offline history controls; fixtures are signed metadata, not RSI qualification."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

from jiuwenswarm.research_rsi.history import inspect_history
from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.signing import Signer
from jiuwenswarm.research_records.contracts import ContractData


def make_history(root, *, key='captured', signed=True, journal=False, uncertain=True):
    records=RecordStore(root/'records');jobs=root/'jobs';jobs.mkdir(mode=0o700)
    signer=Signer.generate('unit:historical-custodian')
    public=signer.public_bytes() if key=='captured' else Signer.generate(signer.key_id).public_bytes()
    configuration=records.put({'rsi':{'custodian_key_id':signer.key_id if key!='unavailable' else None,
        'custodian_public_key':base64.urlsafe_b64encode(public).decode().rstrip('=') if key!='unavailable' else None}})
    opaque=records.put({'unit':'Frozen historical metadata; no current runtime/model/qualification'})
    secret=records.put({'private_preparation':'unit-never-export-private-preparation'})
    session=dict(schema_version='1.0.0',id='offline_history_session',session_id='unit:offline-history',
        target_profile_ref=opaque,parent=dict(cc_name='research.screening',cc_version='unit-history',declaration_sha256=opaque['sha256']),
        parent_declaration_ref=opaque,improver_ref=opaque,scoring_adapter_ref=opaque,configuration_ref=configuration,
        hash_profile_ref=opaque,chain_root_ref=opaque,limits=dict(max_attempts=20,max_no_progress=5,wall_s=3600,per_call_s=300,
            session_query_limit=30,lifetime_query_limit=90),pass_count_repeats=1,
        qualification=dict(min_pass_rate_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3,warmup_batches=5,paired_rounds=7),
        started_by='unit:historical-operator',frozen_at='2026-10-25T00:00:00Z')
    ContractData().validate('rsi-session',session)
    cache=records.put(session);session_ref={'id':'old:opaque-session','sha256':cache['sha256']}
    job_raw=encoded({'schema':'ai4r-rsi-session-job:1','session_ref':session_ref})
    job_ref={'id':'job_offline_history','sha256':hashlib.sha256(job_raw).hexdigest()}
    (jobs/(job_ref['id']+'.json')).write_bytes(job_raw)
    records.claim_job(job_ref);records.bind_job_session(job_ref,session_ref)
    context=records.put({'record_kind':'rsi-session-history-context:1','session_ref':session_ref,'session_bytes_ref':cache,
        'parent_ref':opaque,**{name:session[name] for name in ('parent_declaration_ref','target_profile_ref','hash_profile_ref',
            'chain_root_ref','configuration_ref','improver_ref','scoring_adapter_ref')}})
    records.begin_session_history(session['session_id'],session_ref,context)
    result=dict(schema_version='2.0.0',id='offline_history_result',session_ref=session_ref,outcome='NO_IMPROVEMENT',
        parent=session['parent'],child=None,child_declaration_ref=None,attempt_refs=[],final_attempt_ref=None,
        referee_evidence_ref=None,qualified_by='none',statistics=None,attempts_used=0,queries_used=0,
        stop_reason='Unit historical metadata only; no operational improvement claim',limitations=['No execution or qualification represented'],
        recorded_at='2026-10-25T00:00:01Z')
    population={'record_kind':'rsi-terminal-population:1','session_ref':session_ref,'context_ref':context,
        'proposer_start_refs':[],'attempt_refs':[],'queries_used':0}
    records.stage_terminal(session['session_id'],session_ref,context,population,result,containment_uncertain=uncertain)
    if signed:
        actual=signer.sign(result);ContractData().validate('rsi-session-result',actual)
        result_ref=records.complete_terminal(session['session_id'],session_ref,context,actual)
        records.finish_job(job_ref,{'state':'terminal','result':[actual,result_ref]})
        records.advance_phase(session['session_id'],session_ref,'PREFLIGHT',expected_revision=0)
        records.advance_phase(session['session_id'],session_ref,'CLOSED',expected_revision=1,terminal_result_ref=result_ref)
    if journal:(records.root/'index.sqlite-journal').write_bytes(b'unit: unresolved journal; never recover it')
    assert (records.root/'index.sqlite-wal').stat().st_size>0
    return records,job_ref,secret,opaque


def _restore_root_owner(root):
    os.chown(root,0,0);os.chmod(root,0o700)
    for directory,dirs,files in os.walk(root):
        for name in dirs:os.chown(Path(directory)/name,0,0);os.chmod(Path(directory)/name,0o700)
        for name in files:os.chown(Path(directory)/name,0,0)


def run_offline_fixture(*,key='captured',signed=True,journal=False,uncertain=True,foreign=False):
    root=Path(tempfile.mkdtemp(prefix='rsi-history-control-',dir='/dev/shm'))
    oldmask=os.umask(0o077)
    writer=None;config_path=None
    try:
        writer,job,secret,binding=make_history(root,key=key,signed=signed,journal=journal,uncertain=uncertain)
        config=dict(schema='ai4r-rsi-jobs-service:1',socket_path=str(root/'never-open.sock'),allowed_peer_uids=[0],
            record_root=str(root/'records'),job_root=str(root/'jobs'),binding_id='native-isolated-v1',resource_binding_ref=binding,
            allowed_job_refs=[job])
        descriptor,path=tempfile.mkstemp(prefix='rsi-history-root-config-',suffix='.json',dir='/tmp')
        config_path=Path(path)
        with os.fdopen(descriptor,'wb') as stream:stream.write(encoded(config))
        os.chmod(config_path,0o444)
        # The original writer deliberately stays open: current commits remain
        # in WAL, and no history read may checkpoint or modify original SHM.
        for path in sorted(list(root.rglob('*')),key=lambda value:len(value.parts),reverse=True):os.chown(path,12001,12001)
        os.chown(root,12001,12001)
        requested={'id':'job_foreign','sha256':'a'*64} if foreign else job
        program=r'''
import base64,hashlib,json,os,pathlib,sys
os.setgid(12001);os.setuid(12001)
from jiuwenswarm.research_rsi.history import inspect_history
root=pathlib.Path(sys.argv[1])
def originals():
 return {str(path.relative_to(root)):(hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_mtime_ns,path.stat().st_mode,path.stat().st_uid)
  for path in root.rglob('*') if path.is_file()}
before=originals()
try:value=inspect_history(sys.argv[2],json.loads(sys.argv[3]),export=True)
except PermissionError:value={'error':'PermissionError'}
assert originals()==before,'Original history files changed'
print(json.dumps(value,sort_keys=True))
'''
        process=subprocess.run([sys.executable,'-B','-c',program,str(root),str(config_path),json.dumps(requested)],
            capture_output=True,text=True,timeout=30)
        assert process.returncode==0,process.stderr
        return json.loads(process.stdout),secret
    finally:
        _restore_root_owner(root)
        if writer is not None:writer.close()
        shutil.rmtree(root)
        if config_path is not None:config_path.unlink(missing_ok=True)
        os.umask(oldmask)


@pytest.mark.parametrize('uncertain',[False,True])
def test_offline_signed_history_reads_committed_wal_without_any_original_write(uncertain):
    if sys.platform!='linux' or os.geteuid()!=0:return
    value,secret=run_offline_fixture(uncertain=uncertain)
    assert value['state']=='terminal' and value['offline'] is True
    assert value['signature']['status']=='verified' and value['containment_uncertain'] is uncertain
    assert value['stop_acknowledged'] is False
    assert value['progress']['phase']=='CLOSED' and value['opportunity']['status']=='unavailable'
    assert {row['kind'] for row in value['records']}=={'rsi-session-result','rsi-session'}
    assert secret not in [row['ref'] for row in value['records']]
    for row in value['records']:
        raw=base64.b64decode(row['bytes_base64'],validate=True)
        assert hashlib.sha256(raw).hexdigest()==row['ref']['sha256']
        assert b'unit-never-export-private-preparation' not in raw


@pytest.mark.parametrize('mode',['unavailable','invalid','unsigned','journal'])
def test_missing_original_key_is_explicit_but_invalid_or_unresolved_history_never_recovers(mode):
    if sys.platform!='linux' or os.geteuid()!=0:return
    value,_=run_offline_fixture(key=mode if mode in ('unavailable','invalid') else 'captured',signed=mode!='unsigned',journal=mode=='journal')
    if mode=='unavailable':
        assert value['state']=='terminal' and value['signature']['status']=='unavailable'
    else:
        assert value['state']=='outcome_unknown' and 'records' not in value
    assert value['stop_acknowledged'] is False


def test_offline_history_requires_original_job_allowlist_before_opening_history():
    if sys.platform!='linux' or os.geteuid()!=0:return
    value,_=run_offline_fixture(foreign=True)
    assert value=={'error':'PermissionError'}


def test_offline_api_does_not_accept_an_unrooted_configuration_dictionary():
    with pytest.raises((TypeError,ValueError)):
        inspect_history({'record_root':'caller-selected'}, {'id':'job_foreign','sha256':'a'*64})
