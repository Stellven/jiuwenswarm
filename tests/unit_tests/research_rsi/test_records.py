import json
import pytest
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.signing import Signer,verify


def test_exact_bytes_hash_chain_and_real_signature(tmp_path):
    store=RecordStore(tmp_path); raw=b'{"text":"x"}\n'
    ref=store.put_bytes(raw);assert store.read(ref)==raw
    signer=Signer.generate('disposable-test-key')
    signed=signer.sign({'id':'result:a','outcome':'NO_IMPROVEMENT'})
    verify(signed,signer.public_bytes(),'disposable-test-key')
    signed['outcome']='QUALIFIED'
    with pytest.raises(ValueError):verify(signed,signer.public_bytes(),'disposable-test-key')
    a=store.append_attempt('session:a',{'sequence':1,'previous_ref':None,'child_ref':ref})
    with pytest.raises(ValueError):store.append_attempt('session:a',{'sequence':3,'previous_ref':a})


def test_private_import_preserves_opaque_core_identity_across_restart_without_paths(tmp_path):
    import hashlib
    raw=b'original core declaration bytes\n';ref={'id':'core:declaration/opaque-parent','sha256':hashlib.sha256(raw).hexdigest()}
    store=RecordStore(tmp_path)
    assert store.put_ref(ref,raw)==ref and store.read(ref)==raw
    assert store.put_ref(ref,raw)==ref
    changed=dict(ref,sha256=hashlib.sha256(b'changed').hexdigest())
    with pytest.raises(ValueError,match='immutable'):store.put_ref(changed,b'changed')
    with pytest.raises(ValueError):store.read(changed)
    store.close();store=RecordStore(tmp_path)
    try:
        assert store.read(ref)==raw
        assert not (tmp_path/'core:declaration').exists()
        with pytest.raises(FileNotFoundError):store.read(dict(ref,id='../not-a-filesystem-path'))
    finally:store.close()
