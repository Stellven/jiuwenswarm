from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
import os
import pytest
from jiuwenswarm.research_rsi.package import write_candidate,build_candidate,publish_candidate
from jiuwenswarm.research_rsi.signing import Signer


def test_nonqualified_never_writes_inbox_even_with_valid_signature(tmp_path):
    signer=Signer.generate('test:custodian')
    result=signer.sign({'outcome':'NO_IMPROVEMENT','qualified_by':'none','statistics':None})
    evidence=signer.sign({'id':'referee:test'})
    with pytest.raises((ValueError,PermissionError)):
        write_candidate({},session_result=result,referee_evidence=evidence,public_key=signer.public_bytes(),key_id='test:custodian',
            read_ref=lambda r:b'',validate=lambda n,v:None,inbox=tmp_path/'inbox',custodian_uid=os.geteuid() if hasattr(os,'geteuid') else 0)
    assert not (tmp_path/'inbox').exists()


def test_package_is_constructed_from_selected_proposed_attempt_and_exact_originals(tmp_path):
    from .fixture_package import make_unit_package
    from jiuwenswarm.research_records.contracts import ContractData
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    value=make_unit_package(tmp_path/'core');store=value['store'];validate=ContractData().validate
    result_ref=value['put'](value['result']);index=store.ref_index()
    def body(digest):
        ident=next(ident for ident,row in index.items() if row['sha256']==digest)
        return {'id':ident,'sha256':digest}
    package=build_candidate(result_ref,read_ref=store.read_blob,put_record=value['put'],resolve_body_ref=body,
        public_key=value['signer'].public_bytes(),key_id='unit:custodian',validate=validate,qualification=ControlledQualification())
    assert package['diff_ref']==value['attempt']['diff_ref'] and package['mutable_paths_touched']==['ranking_parent.txt']
    provenance=store.read_record(package['provenance_ref'])
    assert provenance['parent_ref']==value['attempt']['parent_ref']
    publication=OriginalBytes(tmp_path/'inbox',writable=True)
    refs=publish_candidate(package,read_public=store.read_blob,publication=publication,qualification=ControlledQualification())
    assert result_ref in refs and publication.get(result_ref)==value['result']
    with pytest.raises(ValueError,match='original'):
        publish_candidate(package,read_public=lambda _:(_ for _ in ()).throw(ValueError('private original unavailable')),publication=publication,qualification=ControlledQualification())
    store.close()
