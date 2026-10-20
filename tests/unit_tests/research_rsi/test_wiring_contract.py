import pytest
from jiuwenswarm.research_rsi.child_runner import ChildRunner


def test_wrong_ports_fail_without_executing():
    assert ChildRunner.wiring({'input':'schema:1'},{'input':'schema:1'})['executed'] is False
    with pytest.raises(ValueError):ChildRunner.wiring({'input':'schema:1'},{'wrong':'schema:1'})
