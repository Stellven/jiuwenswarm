import hashlib
import json
import pytest
from jiuwenswarm.research_sidecar.frozen_records import FrozenRecords


def capture(tmp_path, records):
    files=[]
    for number,(kind,record) in enumerate(records):
        raw=json.dumps(record).encode();ref={'id':kind+':'+str(number),'sha256':hashlib.sha256(raw).hexdigest()}
        name=f'evidence/{number:04d}-{kind}.json';p=tmp_path/name;p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
        files.append({'path':name,'artifact_ref':ref,'media_type':'application/json','audience':'researcher'})
    manifest={'run_id':'run:a','audience':'researcher','artifact_refs':[f['artifact_ref'] for f in files],'files':files}
    (tmp_path/'client_retrieval.json').write_text(json.dumps(manifest))
    return files


def test_original_byte_records_and_foreign_run_rejected(tmp_path):
    rows=capture(tmp_path,[('dispatch-start',{'run_id':'run:a','node_id':'hypothesis','predecessor_commits':[],'bound_input_refs':[]})])
    records=FrozenRecords(tmp_path,validate=lambda *_:None)
    assert records.of_kind('dispatch-start')[0]['record']['node_id']=='hypothesis'
    raw=tmp_path/rows[0]['path'];raw.write_bytes(raw.read_bytes()+b' ')
    with pytest.raises(ValueError):FrozenRecords(tmp_path,validate=lambda *_:None)


def test_internal_record_filename_does_not_grant_contract_authority(tmp_path):
    capture(tmp_path,[('gate-decision',{'run_id':'run:a','action':'advance'})])
    def reject(name,value):raise ValueError('schema absent')
    with pytest.raises(ValueError):FrozenRecords(tmp_path,validate=reject)


def test_gate_references_must_resolve_to_exact_exported_bytes(tmp_path):
    capture(tmp_path,[('gate-decision',{'run_id':'run:a','deterministic_result_ref':{'id':'missing','sha256':'a'*64},'assessment_ref':None,'invocation_refs':[]})])
    records=FrozenRecords(tmp_path,validate=lambda *_:None)
    with pytest.raises(ValueError):records.gate_rows()
