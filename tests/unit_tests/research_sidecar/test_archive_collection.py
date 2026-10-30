import asyncio
import hashlib
import io
import json
import zipfile

import pytest

from jiuwenswarm.research_sidecar.archive_collection import collect_archive, encoded


def fixture(*,unsafe=False,bad_hash=False,deep_readable=False):
    rows=[('report.md',b'# Actual output\n','text/markdown'),('evidence/after.json',b'{"actual":true}','application/json')]
    if deep_readable:rows[0]=('records/'+('long_original_trace_scope/'*12)+'report.markdown',rows[0][1],'text/markdown')
    files=[];artifacts=[]
    for index,(path,raw,media) in enumerate(rows):
        ref={'id':'original:'+str(index),'sha256':hashlib.sha256(raw).hexdigest()}
        files.append({'path':path,'artifact_ref':ref,'media_type':media,'audience':'researcher'})
        original_path='evidence/before.json' if path=='evidence/after.json' else path
        artifacts.append({'artifact_id':hashlib.sha256(encoded([original_path,ref])).hexdigest(),
            'path':original_path,'sha256':ref['sha256'],'size':len(raw),'media_type':media})
    retrieval={'schema_version':'1.0.0','id':'retrieval:fixture','run_id':'run:fixture','audience':'researcher',
               'artifact_refs':[item['artifact_ref'] for item in files],'files':files,'redactions':[]}
    source={'schema_version':'1.0.0','run_id':'run:fixture','audience':'researcher','artifacts':artifacts}
    source['manifest_sha256']=hashlib.sha256(encoded(source)).hexdigest()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('client_retrieval.json',encoded(retrieval))
        for index,(path,raw,_) in enumerate(rows):
            archive.writestr('../unsafe' if unsafe and index==0 else path,b'corrupt' if bad_hash and index==0 else raw)
    return source,buffer.getvalue()


class ArchiveClient:
    def __init__(self,raw):self.raw=raw;self.calls=0
    async def stream_export_archive(self,run_id,destination,**kwargs):
        self.calls+=1;destination.write_bytes(self.raw)


def invoke(client,source,destination,**kwargs):
    return asyncio.run(collect_archive(client,'run:fixture',source,destination,
        max_archive_bytes=1024*1024,max_total_bytes=1024*1024,max_member_bytes=1024*1024,**kwargs))


def test_original_archive_references_survive_ordinal_path_drift_and_resume(tmp_path):
    source,raw=fixture();client=ArchiveClient(raw);destination=tmp_path/'artifacts'/'originals.zip'
    result=invoke(client,source,destination,max_extract_files=1)
    assert result['verified_members']==2 and len(result['extracted'])==1
    assert destination.read_bytes()==raw
    actual=json.loads((tmp_path/'artifacts/originals.inventory.json').read_bytes())
    assert actual['client_retrieval']['files'][1]['path']=='evidence/after.json'
    assert source['artifacts'][1]['path']=='evidence/before.json'
    assert (tmp_path/'artifacts/readable/report.md').read_bytes()==b'# Actual output\n'
    assert invoke(client,source,destination,max_extract_files=1)==result and client.calls==1


@pytest.mark.parametrize('options',[{'unsafe':True},{'bad_hash':True}])
def test_unsafe_or_wrong_original_bytes_never_publish_archive(tmp_path,options):
    source,raw=fixture(**options);client=ArchiveClient(raw);destination=tmp_path/'originals.zip'
    with pytest.raises(ValueError):invoke(client,source,destination)
    assert not destination.exists() and not list(tmp_path.glob('.archive-transfer-*'))


def test_same_bytes_under_different_reference_are_not_interchangeable(tmp_path):
    source,raw=fixture()
    source['artifacts'][0]['artifact_id']=hashlib.sha256(encoded(['report.md',{'id':'foreign','sha256':source['artifacts'][0]['sha256']}])).hexdigest()
    source['manifest_sha256']=hashlib.sha256(encoded({k:v for k,v in source.items() if k!='manifest_sha256'})).hexdigest()
    with pytest.raises(ValueError,match='reference identity'):invoke(ArchiveClient(raw),source,tmp_path/'originals.zip')


def test_deep_readable_paths_are_portable_and_original_paths_remain_in_archive(tmp_path):
    source,raw=fixture(deep_readable=True);destination=tmp_path/'originals.zip'
    result=invoke(ArchiveClient(raw),source,destination,max_extract_files=1)
    copied=next(iter(result['extracted']))
    from pathlib import Path
    path=Path(copied['path']);relative=path.relative_to(tmp_path/'readable')
    assert len(str(relative))<=80 and len(relative.parts)==1
    assert path.read_bytes()==b'# Actual output\n'
    with zipfile.ZipFile(destination) as archive:
        assert source['artifacts'][0]['path'] in archive.namelist()
    inventory=json.loads((tmp_path/'originals.inventory.json').read_bytes())
    assert inventory['client_retrieval']['files'][0]['path']==source['artifacts'][0]['path']


def test_metadata_ceiling_admits_a_completed_planned_poc_run():
    """Live run pl13: 59,740 retained files gave a 33,790,417-byte client_retrieval.json, past the old 32 MiB cap."""
    from jiuwenswarm.research_sidecar.archive_collection import METADATA_CEILING_BYTES
    from jiuwenswarm.research_sidecar.sequential_cases import DEFAULT_LIMITS
    limit = min(METADATA_CEILING_BYTES, max(1024 * 1024, DEFAULT_LIMITS['archive_member_limit'] * 2048))
    assert limit >= 33_790_417 and limit <= 128 * 1024 * 1024
