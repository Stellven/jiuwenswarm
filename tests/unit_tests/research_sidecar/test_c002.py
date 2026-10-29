import pytest
from jiuwenswarm.research_sidecar.evidence import validate_empirical
from jiuwenswarm.research_records.contracts import ContractData


def test_every_actual_receipt_disjoint_complete_metric_status():
    value={'schema_version':'2.0.0','id':'empirical_results','runs':[
        {'sequence':1,'status':'measured','metrics':{'quality':1},'unmeasured_metrics':{}},
        {'sequence':2,'status':'unmeasured','metrics':{},'unmeasured_metrics':{'quality':'run_failed'}}]}
    assert validate_empirical(value,[{'sequence':1},{'sequence':2}],['quality'],ContractData().validate)==value
    with pytest.raises(ValueError):validate_empirical(value,[{'sequence':1}],['quality'],ContractData().validate)
    value['runs'][1]['metrics']={'quality':1}
    with pytest.raises(ValueError):validate_empirical(value,[{'sequence':1},{'sequence':2}],['quality'],ContractData().validate)
