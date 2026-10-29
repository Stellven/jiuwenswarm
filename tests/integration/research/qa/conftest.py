"""Read-only observers of one already executed, frozen four-case campaign.

These tests never call an app, create a run or load a worker credential. Missing
actual campaign evidence is a failure, never a skip or a replacement execution.
"""
import os
from pathlib import Path
import pytest
from jiuwenswarm.research_sidecar.frozen_records import strict_json,FrozenRecords
from jiuwenswarm.research_sidecar.evaluation_records import EvaluationRecords
from jiuwenswarm.research_sidecar.evidence import read_verified
from jiuwenswarm.research_sidecar.cases import schedule,validate_visible_case
from jiuwenswarm.research_sidecar.campaign import validate_campaign


def pytest_addoption(parser):
    parser.addoption('--qa-campaign-root',default=None)
    parser.addoption('--qa-results-root',default=None)
    parser.addoption('--qa-check',default=None)


@pytest.fixture
def frozen_campaign(request):
    value=request.config.getoption('--qa-campaign-root')
    if not value:pytest.fail('Required actual CLI campaign root was not supplied; observer does not run another case.')
    if not hasattr(os,'geteuid') or os.geteuid()!=11002:pytest.fail('Required protected benchmark_referee UID 11002 is absent.')
    if any(k in os.environ for k in ('AI4R_QA_JOB','AI4R_APP_TOKEN','AI4R_RSI_JOB_SOCKET','AI4R_RSI_CUSTODIAN_SOCKET')) or any(k.endswith('_API_KEY') for k in os.environ):pytest.fail('Referee inherited a forbidden control/model/custodian credential configuration.')
    if Path('/var/run/docker.sock').exists():pytest.fail('Referee must not have the Docker socket.')
    root=Path(value).resolve(strict=True)
    results_value=request.config.getoption('--qa-results-root')
    if not results_value:pytest.fail('Required exact CLI results root was not supplied.')
    results_root=Path(results_value).resolve(strict=True)
    campaign=strict_json((root/'campaign.json').read_bytes());registry=strict_json((root/'module-map.json').read_bytes());cases=[]
    for pin in campaign['cases']:
        case=strict_json(read_verified(root,{'path':'cases/'+pin['case_id']+'/case.json','sha256':pin['case_sha256']}));validate_visible_case(case)
        cases.append({**case,'module':registry[case['case_id']]})
    validate_campaign(campaign,cases)
    assert results_root.name==campaign['campaign_id'],'Results directory differs from frozen campaign identity.'
    for name in ('campaign.json','schedule.json','module-map.json',*('cases/'+p['case_id']+'/case.json' for p in campaign['cases'])):
        assert (root/name).read_bytes()==(results_root/name).read_bytes(),'CLI frozen definition copy differs from the original campaign.'
    rows=strict_json((root/'schedule.json').read_bytes())
    assert rows==schedule(campaign,cases),'Actual campaign schedule differs from frozen definitions.'
    return {'root':root,'results_root':results_root,'campaign':campaign,'cases':cases,'rows':rows,'check':request.config.getoption('--qa-check')}


@pytest.fixture
def label_for_case():
    def load(case):
        root=Path(os.environ.get('AI4R_QA_LABELS','/bench-private/labels')).resolve(strict=True)
        raw=read_verified(root,{'path':case['referee_ref']['label_id']+'/referee.json','sha256':case['referee_ref']['referee_sha256']})
        label=strict_json(raw)
        assert (label['case_id'],label['case_version'])==(case['case_id'],case['case_version'])
        return label
    return load


@pytest.fixture
def actual_runs(frozen_campaign):
    def load(module,variants=None,require_invocation=True):
        rows=[r for r in frozen_campaign['rows'] if r['module']==module and (variants is None or r['variant_id'] in variants)]
        assert rows,'Required frozen case/variant population absent.'
        observed=[]
        for row in rows:
            folder=frozen_campaign['results_root']/'runs'/row['run_id'];run=strict_json((folder/'run_record.json').read_bytes())
            for key in ('run_id','campaign_id','case_id','case_version','config_id','repeat_index'):assert run[key]==row[key]
            assert run['launched'] is True,'Readiness-only or blocked preflight cannot prove actual module integration.'
            assert run['outcome'] not in {'blocked','interrupted'},'Required actual case did not reach an observed supported terminal path.'
            for export in run['exports']:read_verified(folder,export)
            case=next(c for c in frozen_campaign['cases'] if c['case_id']==row['case_id'])
            assert run['entry_mode']==case['entry_mode'],'Retained run changes its frozen entry mode.'
            if module=='rsi':
                assert run['app_run_id'],'Actual RSI session identity is absent.'
                frozen=None
            elif run['entry_mode'] in {'node_replay','single_cc'}:
                assert run['app_run_id'] is None,'Private evaluation must not invent an ordinary product run identity.'
                requests=[export for export in run['exports'] if export['path']=='evaluation-request.json']
                assert len(requests)==1,'Exact original scheduled evaluation request pin is absent or ambiguous.'
                submitted=strict_json(read_verified(folder,requests[0]))
                for key in ('request_id','campaign_id','case_id'):assert submitted[key]==run[key]
                frozen=EvaluationRecords.from_frozen(folder/'evaluation-export',request_id=run['request_id'],
                    campaign_id=run['campaign_id'],expected_request=submitted,inventory=run['exports']).require_complete()
                assert frozen.request['entry_point']==('E2' if run['entry_mode']=='node_replay' else 'E3')
                if require_invocation:
                    # E2 reuses the original subject observation; only an eligible
                    # selected reviewer is fresh. E3 owns its actual worker.
                    kind='source_observation' if run['entry_mode']=='node_replay' else 'observation'
                    assert frozen.rows(kind),'Exact original/private invocation observation is absent.'
            else:
                assert run['app_run_id'],'Actual ordinary product run identity is absent.'
                frozen=FrozenRecords(folder/'export');assert frozen.run_id==run['app_run_id']
                if require_invocation:assert frozen.of_kind('invocation-observation'),'Actual raw invocation observation is absent.'
            observed.append((row,case,run,folder,frozen))
        return observed
    return load
