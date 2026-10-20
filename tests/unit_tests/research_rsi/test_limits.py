import pytest
from jiuwenswarm.research_rsi.profiles import Limits, ProfileError


def test_source_ceilings_cannot_be_widened():
    assert Limits().max_attempts==20
    for k,v in [('max_attempts',21),('max_no_progress',6),('wall_s',3601),('per_call_s',301),('session_query_limit',31),('lifetime_query_limit',91),('wall_s',0)]:
        with pytest.raises(ProfileError): Limits.from_mapping({k:v})
    with pytest.raises(ProfileError): Limits.from_mapping({'wall_s':10,'per_call_s':11})
