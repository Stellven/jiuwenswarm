import asyncio
import base64
import hashlib
import json
import pytest
from jiuwenswarm.research_sidecar.adapters.rsi import freeze_public_export


def test_public_export_preserves_original_bytes_and_ref_closure(tmp_path):
    data=b'{"session_id":"s"}';ref={'id':'opaque-session','sha256':hashlib.sha256(data).hexdigest()}
    value={'state':'terminal','records':[{'kind':'rsi-session','ref':ref,'bytes_base64':base64.b64encode(data).decode()}]}
    rows=freeze_public_export(tmp_path,value,validate=lambda *_:None)
    assert (tmp_path/rows[0]['path']).read_bytes()==data
    with pytest.raises(ValueError):freeze_public_export(tmp_path/'bad',{**value,'records':[dict(value['records'][0],bytes_base64=base64.b64encode(data+b' ').decode())]},validate=lambda *_:None)


def test_arbitrary_export_kind_cannot_disclose_custodian_store(tmp_path):
    raw=b'{}';ref={'id':'a','sha256':hashlib.sha256(raw).hexdigest()}
    with pytest.raises(ValueError):freeze_public_export(tmp_path,{'state':'terminal','records':[{'kind':'hidden-fixtures','ref':ref,'bytes_base64':base64.b64encode(raw).decode()}]},validate=lambda *_:None)
