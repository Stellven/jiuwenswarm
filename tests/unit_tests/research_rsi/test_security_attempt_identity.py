"""Actual attempt-contract regression; no kernel or qualification claim."""
import copy
import pytest

from jiuwenswarm.research.contracts import validate, ResearchError
from jiuwenswarm.research_rsi.security_driver import security_attempt_id
from tests.unit_tests.research_rsi.fixture_package import make_unit_package


def test_security_claim_identity_fits_canonical_attempt_without_relaxing_contract(tmp_path):
    fixture=make_unit_package(tmp_path/'core')
    try:
        original=copy.deepcopy(fixture['attempt'])
        attack='security-case-'+'a'*40
        original['id']='security-attempt:'+attack
        assert len(original['id'])==71
        with pytest.raises(ResearchError):validate('rsi-attempt',original)
        original['id']=security_attempt_id(attack)
        validate('rsi-attempt',original)
        assert len(original['id'])<=64
        assert security_attempt_id(attack)==original['id']
        assert security_attempt_id('security-case-'+'b'*40)!=original['id']
        assert fixture['attempt']['id']!=original['id']
    finally:fixture['store'].close()

