"""Future CPU tests: run only after both active fixed screens and controllers stop."""
import copy
import pytest
from test_broad_benchmark import contract as broad_contract
from jiuwenswarm.factory import throughput_workbench as workbench
from jiuwenswarm.factory.strata_components import apply as legacy_apply

@pytest.fixture
def profile(broad_contract):
    profile=copy.deepcopy(broad_contract['arms']['A'])
    profile['environment']['DS4_EXPERT_BUDGET_BYTES']='76000000000'
    return profile

@pytest.mark.parametrize('setting,value',[('ahead',1),('cpu_threads',6)])
def test_fixed_budget_context_preserved_while_one_setting_changes(profile,setting,value):
    original=copy.deepcopy(profile);result=workbench.apply(profile,setting,value)
    assert profile==original
    assert result['profile']['environment']['DS4_EXPERT_BUDGET_BYTES']=='76000000000'
    assert result['change']['changed'] and len(result['change']['changed_paths'])==1
    assert result['change']['maximum_changed_variables']==1
    assert result['change']['execution_authorized'] is False
    proof=workbench.dispatch(None,None,'verify_profile',dict(base_profile=profile,candidate_profile=result['profile'],setting=setting,value=value))
    assert proof['result']['configuration_verified'] is True

@pytest.mark.parametrize('value',['76000000001','0','bad',76000000000,None])
def test_other_fixed_budget_context_not_admitted(profile,value):
    profile['environment']['DS4_EXPERT_BUDGET_BYTES']=value
    with pytest.raises(ValueError):workbench.apply(profile,'ahead',1)


def test_historical_drafting_component_still_rejects_new_context(profile):
    with pytest.raises(ValueError,match='Unsupported Strata component environment'):legacy_apply(profile,False)


def test_unapproved_environment_does_not_hide_behind_fixed_context(profile):
    profile['environment']['UNAPPROVED_CONTEXT']='1'
    with pytest.raises(ValueError,match='Unsupported Strata component environment'):workbench.apply(profile,'ahead',1)
