"""Custodian integrity recomputation from exact records, never caller verdicts."""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from jiuwenswarm.research_rsi.final_checks import verify_final_integrity
from jiuwenswarm.research.contracts import validate
from tests.unit_tests.research_rsi.fixture_package import make_unit_package


@pytest.mark.parametrize('fault',[None,'scope','diff','chain','configuration','protected_copy'])
def test_final_integrity_recomputes_mutation_and_original_frozen_bindings(tmp_path,fault):
    f=make_unit_package(tmp_path);store=SimpleNamespace(get=f['store'].read_record,read=f['store'].read_blob)
    attempt=deepcopy(f['attempt']);target=store.get(f['session']['target_profile_ref'])
    try:
        if fault=='scope':
            diff=store.get(attempt['diff_ref']);diff['files'][0]['path']='screening_prompt.txt';attempt['diff_ref']=f['put'](diff)
        elif fault=='diff':
            diff=store.get(attempt['diff_ref']);diff['files'][0]['before_ref']=attempt['child_ref'];attempt['diff_ref']=f['put'](diff)
        elif fault=='chain':attempt['sequence']=2
        elif fault=='configuration':attempt['configuration_ref']=attempt['child_ref']
        elif fault=='protected_copy':attempt['child_ref']=target['protected_refs'][0]
        pin=f['put'](attempt)
        arguments=dict(session=f['session'],attempt_ref=pin,target_ref=f['session']['target_profile_ref'],
            parent_ref=target['parent_ref'],child_ref=attempt['child_ref'],configuration_ref=f['session']['configuration_ref'],
            store=store,validate=validate)
        if fault is None:assert verify_final_integrity(**arguments) is True
        else:
            with pytest.raises(ValueError):verify_final_integrity(**arguments)
    finally:f['store'].close()
