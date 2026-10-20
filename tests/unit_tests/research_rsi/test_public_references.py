import hashlib
import pytest
from jiuwenswarm.research_rsi.public_references import prepare


def test_pinned_reference_no_redirect_or_hash_drift(tmp_path):
    raw=b'public reference'
    pin={'url':'https://example.org/ref','revision':'v1','license':'MIT','sha256':hashlib.sha256(raw).hexdigest()}
    assert prepare(pin,tmp_path/'one',allowed_origins={'https://example.org'},fetch=lambda u:(u,raw))['sha256']==pin['sha256']
    with pytest.raises(ValueError):prepare(pin,tmp_path/'two',allowed_origins={'https://example.org'},fetch=lambda u:('https://evil.test/ref',raw))
    with pytest.raises(ValueError):prepare(pin,tmp_path/'three',allowed_origins={'https://example.org'},fetch=lambda u:(u,b'changed'))
