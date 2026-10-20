import pytest
from jiuwenswarm.research_rsi.targets.text import validate_text_target


def test_conditional_text_missing_native_path_is_blocked_not_omitted():
    with pytest.raises(RuntimeError,match='BLOCKED'):validate_text_target({},native_headless_ready=False)
    with pytest.raises(ValueError):validate_text_target({'required_test_refs':['r'],'mutable_paths':['referee.md']},native_headless_ready=True)
