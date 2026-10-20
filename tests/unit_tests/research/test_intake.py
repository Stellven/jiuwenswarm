import asyncio

import pytest

from jiuwenswarm.research.intake import extract_document, qualify_intake
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


def test_utf8_extraction_preserves_original_codepoints_and_newlines():
    data='A\r\n😀e\u0301'.encode('utf-8')
    assert asyncio.run(extract_document('notes.md',data,timeout_s=1))==data
    with pytest.raises(ResearchError):asyncio.run(extract_document('notes.txt',b'\xff',timeout_s=1))


def test_intake_does_not_read_caller_paths_and_requires_live_owned_upload(tmp_path):
    store=SQLiteRunStore(tmp_path);ref=store.put_blob(b'protected')
    principal=Principal('alice',frozenset({'project'}),frozenset({'ingest'}))
    result=qualify_intake(store,principal,'Investigate latency',[],workspace_id='project',profile_ref=ref,workspace_ref=ref,input_directory_ref=ref)
    intake=store.read_record(result)
    assert store.read_blob(intake['request_ref'])==b'Investigate latency'
    assert intake['source_refs']==[]
    with pytest.raises(ResearchError):
        qualify_intake(store,principal,'x',['C:/private.txt'],workspace_id='project',profile_ref=ref,workspace_ref=ref,input_directory_ref=ref)
