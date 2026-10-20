from .fixture_package import make_unit_package
from jiuwenswarm.research_records.contracts import ContractData
from jiuwenswarm.research_rsi.signing import verify


def test_complete_v2_signed_unit_vectors_keep_earlier_final_and_rejected_history(tmp_path):
    value=make_unit_package(tmp_path)
    validate=ContractData().validate
    for name,key in [('rsi-session-result','result'),('rsi-referee-evidence','referee'),('rsi-attempt','attempt'),('rsi-attempt','rejected'),('candidate-package','package')]:validate(name,value[key])
    verify(value['result'],value['signer'].public_bytes(),'unit:custodian')
    assert value['result']['attempts_used']==2 and value['result']['final_attempt_ref']==value['result']['attempt_refs'][0]
    assert value['result']['statistics']['parent_passed']==20/3
    value['store'].close()
