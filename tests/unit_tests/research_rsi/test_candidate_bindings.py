"""Original-byte join mechanics only; no operational security qualification."""
import copy
import os

import pytest

from jiuwenswarm.research_rsi.candidate_bindings import (
    bind_candidate,binding_id,CandidateResolver,public_candidate_resolver,validate_binding)
from jiuwenswarm.research_rsi.fixed_resources import CombinedRecords
from jiuwenswarm.research_rsi.records import RecordStore,encoded
from tests.unit_tests.research_rsi.fixture_package import make_unit_package


@pytest.fixture
def joined(tmp_path):
    f=make_unit_package(tmp_path/'core');records=RecordStore(tmp_path/'records')
    store=CombinedRecords(records,core=f['store'])
    try:yield f,records,store
    finally:records.close();f['store'].close()


def bind(f,store):
    return bind_candidate(store,session_ref=f['package']['session_ref'],
        candidate_ref=f['attempt']['child_ref'],declaration_ref=f['package']['child_declaration_ref'])


def test_binding_uses_original_scope_and_private_immutable_index_across_restart(joined):
    f,records,store=joined;pin=bind(f,store)
    resolver=CandidateResolver(read=store.read,locate=records.candidate_binding_ref)
    assert resolver(f['package']['session_ref'],f['attempt']['child_ref'])==f['package']['child_declaration_ref']
    assert bind(f,store)==pin
    replacement=copy.deepcopy(store.get(pin));replacement['declaration_ref']=f['session']['parent_declaration_ref']
    with pytest.raises(ValueError,match='immutable'):records.record_candidate_binding(replacement)
    records.db.close();records.db=__import__('sqlite3').connect(records.root/'index.sqlite',isolation_level=None)
    assert records.candidate_binding_ref(f['package']['session_ref'],f['attempt']['child_ref'])==pin


def test_publisher_receives_only_exact_binding_and_deterministic_alias(joined):
    f,records,store=joined;published={}
    class Publisher:
        def put_ref(self,pin,raw):published[pin['id']]=(pin,raw)
    store.publisher=Publisher()
    pin=bind(f,store);alias=binding_id(f['package']['session_ref'],f['attempt']['child_ref'])
    assert published[alias]==({'id':alias,'sha256':pin['sha256']},records.read(pin))
    assert published[pin['id']]==(pin,records.read(pin))
    assert len(published)==2


@pytest.mark.parametrize('field',['session_ref','candidate_ref','target_ref','parent_declaration_ref','body_path'])
def test_binding_cannot_substitute_any_frozen_join(joined,field):
    f,records,store=joined;pin=bind(f,store);value=store.get(pin)
    value[field]='outside.py' if field=='body_path' else f['session']['configuration_ref']
    with pytest.raises((ValueError,KeyError)):validate_binding(value,store.read)


def test_candidate_resolver_checks_exact_indexed_subject_not_payload_resemblance(joined):
    f,records,store=joined;pin=bind(f,store)
    absent=CandidateResolver(read=lambda *_:pytest.fail('No binding was indexed'),locate=lambda *_:None)
    assert absent(f['package']['session_ref'],f['attempt']['child_ref']) is None
    foreign=CandidateResolver(read=store.read,locate=lambda *_:pin)
    with pytest.raises(ValueError,match='another subject'):
        foreign(f['session']['configuration_ref'],f['attempt']['child_ref'])
    corrupt=CandidateResolver(read=lambda _:b'{}',locate=lambda *_:pin)
    with pytest.raises(ValueError,match='bytes changed'):
        corrupt(f['package']['session_ref'],f['attempt']['child_ref'])


def test_actual_linux_public_alias_closure_and_ambiguous_publication_refusal(joined,tmp_path):
    if os.name!='posix':return # OriginalBytes mode custody is a Linux boundary.
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    from jiuwenswarm.research_rsi.worker import PublicBytes
    f,records,store=joined
    publication=OriginalBytes(tmp_path/'public',writable=True);store.publisher=publication
    pin=bind(f,store)
    value=store.get(pin)
    # The approved owner publishes only the original closure used by the join;
    # an unrelated private fixture remains absent from the public index.
    secret=records.put({'unit_private_fixture':'must never be traversed'})
    for ref in (f['package']['session_ref'],f['session']['target_profile_ref'],
            f['session']['parent_declaration_ref'],f['package']['child_declaration_ref'],
            f['attempt']['child_ref'],f['attempt']['parent_ref']):
        publication.put_ref(ref,store.read(ref))
    resolver=public_candidate_resolver(PublicBytes([publication.root]))
    assert resolver(f['package']['session_ref'],f['attempt']['child_ref'])==value['declaration_ref']
    assert secret['id'] not in publication.index()
    other=OriginalBytes(tmp_path/'other-public',writable=True)
    changed=copy.deepcopy(value);changed['body_path']='foreign.py';raw=encoded(changed)
    import hashlib
    alias=binding_id(value['session_ref'],value['candidate_ref'])
    other.put_ref({'id':alias,'sha256':hashlib.sha256(raw).hexdigest()},raw)
    ambiguous=public_candidate_resolver(PublicBytes([publication.root,other.root]))
    with pytest.raises(ValueError,match='Ambiguous'):ambiguous(value['session_ref'],value['candidate_ref'])


def test_installed_resolver_never_satisfies_missing_full_security_evidence(joined):
    from jiuwenswarm.research_rsi.qualification import captured_qualification
    f,records,store=joined;bind(f,store)
    guard=captured_qualification(store,f['session']['configuration_ref'],kind_reader=f['store'].record_kind,
        candidate_resolver=CandidateResolver(read=store.read,locate=records.candidate_binding_ref))
    assert guard._subject('trial',f['package']['session_ref'],f['attempt']['child_ref'])==f['session']
    with pytest.raises(ValueError):guard.require('trial',session_ref=f['package']['session_ref'],candidate_ref=f['attempt']['child_ref'])
