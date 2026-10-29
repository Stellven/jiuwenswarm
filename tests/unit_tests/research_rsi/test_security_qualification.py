"""Explicit controlled authorities are test composition, never13-case evidence."""
import pytest


@pytest.mark.parametrize('operation',['session_start','proposal','trial','oracle','package','admit','activate'])
def test_default_private_qualification_blocks_every_new_effect(operation):
    from jiuwenswarm.research_rsi.qualification import require_qualification
    with pytest.raises(ValueError,match='qualification'):
        require_qualification(None,operation,session_ref={'id':'session','sha256':'a'*64})


def test_a_boolean_or_incomplete_return_is_not_qualification_authority():
    from jiuwenswarm.research_rsi.qualification import require_qualification
    class Forged:
        def require(self,*args,**kwargs):return {'qualified':True}
    for value in (True,Forged()):
        with pytest.raises(ValueError):require_qualification(value,'trial',session_ref={'id':'session','sha256':'a'*64})
