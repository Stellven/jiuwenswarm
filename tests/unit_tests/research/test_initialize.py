"""Supported native initializer dispatch stays explicit and fail closed."""
import pytest


def test_native_initializer_routes_m1_without_legacy_workspace_reset(monkeypatch):
    import jiuwenswarm.init_workspace as native
    import jiuwenswarm.research.initialize as initialize
    seen=[]
    monkeypatch.setenv('JIUWENSWARM_M1_PROFILE','1')
    monkeypatch.setattr(initialize,'main',lambda:seen.append('explicit-catalog-init') or 2)
    monkeypatch.setattr(native,'run_init',lambda **kw:pytest.fail('M1 must never invoke legacy destructive init'))
    assert native.main()==2 and seen==['explicit-catalog-init']


@pytest.mark.asyncio
async def test_missing_protected_locator_cannot_create_policy_or_defaults(tmp_path,monkeypatch):
    import jiuwenswarm.research.initialize as initialize
    monkeypatch.setenv('JIUWENSWARM_M1_PROFILE','1')
    monkeypatch.setattr(initialize.os,'geteuid',lambda:10001)
    monkeypatch.setenv('JIUWENSWARM_M1_STATE',str(tmp_path/'state'))
    monkeypatch.delenv('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS',raising=False)
    with pytest.raises(initialize.ResearchError,match='initialization_blocked'):
        await initialize.initialize_profile()
    assert not (tmp_path/'state').exists()
