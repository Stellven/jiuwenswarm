import hashlib
import io
import json
import zipfile
import pytest
from jiuwenswarm.research_sidecar.evidence import unpack_authorized_archive


def archive(name='output.json',payload=b'{}',digest=None,extra=False):
    manifest={'schema_version':'1.0.0','id':'retrieval:a','run_id':'r','artifact_refs':[{'id':'artifact:a','sha256':digest or hashlib.sha256(payload).hexdigest()}],
        'audience':'researcher','files':[{'path':name,'artifact_ref':{'id':'artifact:a','sha256':digest or hashlib.sha256(payload).hexdigest()},'media_type':'application/json','audience':'researcher'}],'redactions':[]}
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('client_retrieval.json',json.dumps(manifest));z.writestr(name,payload)
        if extra:z.writestr('foreign.json',b'secret')
    return stream.getvalue()


def test_exact_bytes_audience_and_unsafe_missing_swapped_unexpected():
    manifest,files=unpack_authorized_archive(archive(),run_id='r',audience='researcher')
    assert files['output.json']==b'{}'
    for raw in [archive('../escape'),archive(digest='a'*64),archive(extra=True)]:
        with pytest.raises(ValueError):unpack_authorized_archive(raw,run_id='r',audience='researcher')
    with pytest.raises(ValueError):unpack_authorized_archive(archive(),run_id='foreign',audience='researcher')
