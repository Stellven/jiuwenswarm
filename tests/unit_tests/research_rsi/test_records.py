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
