"""Host admission tests with explicitly simulated GPU evidence reader."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
from jiuwenswarm.factory.acceptance import validate_broad_campaign
from jiuwenswarm.factory.store import Store

@pytest.fixture
def campaign(tmp_path, monkeypatch):
    from jiuwenswarm.factory import benchmark
    store = Store(tmp_path/'store')
    templates, cycles, reports = [], [], {}
    store.create_task(dict(task_id='p', objective='test broad gate', constraints={}))
    for stage in ('aa', 'confirm'):
        c = dict(adapter='strata-benchmark-v3', campaign_stage=stage, image={'id':'fixed'},
            assets={'id':'fixed'}, dataset_sha256='fixed', workload={'id':'fixed'},
            arms={'A':{'args':[]}}, order=list('AB' if stage=='aa' else 'ABBA'))
        path=tmp_path/(stage+'.json');path.write_text(json.dumps(c))
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        child_digest=hashlib.sha256((json.dumps(c,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()
        templates.append(dict(id=stage,path=str(path),sha256=digest))
        store.create_task(dict(task_id=stage,objective='child',constraints={'factory_loop_parent':'p'}))
        attempt=store.create_attempt(stage,dict(kind='lab',idem_key=stage,fingerprint=stage,
            request=dict(contract=c,contract_sha256=child_digest)))
        store.transition_attempt(stage,attempt['attempt_id'],'running')
        store.transition_attempt(stage,attempt['attempt_id'],'succeeded')
        cycles.append(dict(state='collected',contract=c,request={'template_id':stage},
            template_sha256=digest,contract_sha256=child_digest,child_task_id=stage,attempt_id=attempt['attempt_id']))
        root=store.home/'benchmark-spool'/attempt['attempt_id'];root.mkdir(parents=True)
        (root/'config.json').write_text(json.dumps(dict(task_id=stage,attempt_id=attempt['attempt_id'])))
        reports[stage]=dict(verdict='aa_valid' if stage=='aa' else 'accept',performance_acceptance_evaluated=stage=='confirm',
            promotion_authorized=False,gates={'aa_timing_stable':True},quality={'case_count':64},verification=dict(raw_files_verified=True,
            independent_native_parse=True,complete_cells=len(c['order'])))
    with store._transaction():
        store._db.execute('UPDATE tasks SET constraints=? WHERE task_id=?',(json.dumps({'factory_loop':{'templates':templates}}),'p'))
        store._db.execute('CREATE TABLE factory_loop_cycles (task_id TEXT,record TEXT)')
        for c in cycles:store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?)',('p',json.dumps(c)))
    monkeypatch.setattr(benchmark,'validate_contract',lambda c:c)
    calls=[]
    def analyze(c,root):
        calls.append(str(root));return copy.deepcopy(reports[c['campaign_stage']])
    monkeypatch.setattr(benchmark,'analyze_files',analyze)
    yield SimpleNamespace(store=store,cycles=cycles,reports=reports,calls=calls)
    store.close()


def test_requires_independent_raw_reanalysis(campaign):
    validate_broad_campaign(campaign.store,'p')
    assert len(campaign.calls)==2

@pytest.mark.parametrize('failure',['aa','quality','incomplete','promotion','drift'])
def test_false_claims_cannot_accept(campaign,failure):
    if failure=='aa':campaign.reports['aa']['verdict']='aa_invalid'
    elif failure=='quality':campaign.reports['confirm']['quality']['case_count']=8
    elif failure=='incomplete':campaign.reports['confirm']['verification']['complete_cells']=2
    elif failure=='drift':campaign.reports['aa']['gates']['aa_timing_stable']=False
    else:campaign.reports['confirm']['promotion_authorized']=True
    with pytest.raises(ValueError):validate_broad_campaign(campaign.store,'p')


def test_raw_attempt_substitution_refused(campaign):
    c=campaign.cycles[0]
    p=campaign.store.home/'benchmark-spool'/c['attempt_id']/'config.json'
    p.write_text(json.dumps(dict(task_id='other',attempt_id=c['attempt_id'])))
    with pytest.raises(ValueError,match='another attempt'):validate_broad_campaign(campaign.store,'p')


def test_diagnostic_parent_cannot_accept(campaign):
    from jiuwenswarm.factory.acceptance import validate
    with campaign.store._transaction():
        campaign.store._db.execute('UPDATE tasks SET constraints=? WHERE task_id=?',
            (json.dumps({'nonpromoting_diagnostics': {'origin_task': 'old'}}), 'p'))
    with pytest.raises(ValueError, match='cannot accept'):
        validate(campaign.store, 'p')
