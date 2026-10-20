import pytest
from jiuwenswarm.research_sidecar.ledger import Ledger


def test_immutable_attempt_no_blind_resend(tmp_path):
    ledger=Ledger(tmp_path/'ledger.sqlite')
    assert ledger.claim('run:a',{'prompt':'visible'})
    assert not ledger.claim('run:a',{'prompt':'visible'})
    with pytest.raises(ValueError):ledger.claim('run:a',{'prompt':'changed'})
    ledger.event('run:a','delivery_ambiguous',{'launched':True})
    assert ledger.events('run:a')[0]['kind']=='delivery_ambiguous'
