"""Scoped acceptance host-boundary tests; all runtime analyses are explicit fakes."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory.acceptance import validate_scoped_prefill
from jiuwenswarm.factory.store import Store


@pytest.fixture
def scoped_gate(tmp_path, monkeypatch):
    from jiuwenswarm.factory import prefill_workbench
    contract=dict(adapter='strata-prefill-scoped-v1',version=1,stage='confirm',
        scope='prefill_microbenchmark',contract_id='scoped-test-confirm')
    path=tmp_path/'confirm.json';path.write_text(json.dumps(contract))
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    store=Store(tmp_path/'home')
    store.create_task(dict(task_id='parent',objective='Scoped host gate',target='spark-gb10',
        contract_id=str(path),constraints={'factory_loop':{'templates':[dict(id='confirm',path=str(path),sha256=digest)]}}))
    store.create_task(dict(task_id='child',objective='Owned scoped attempt',contract_id=str(path),
        constraints={'factory_loop_parent':'parent'}))
    attempt=store.create_attempt('child',dict(kind='lab',idem_key='one',fingerprint='fake',
        request=dict(adapter='strata-prefill-scoped-v1',contract=contract,contract_sha256=digest)))
    store.transition_attempt('child',attempt['attempt_id'],'running')
    store.transition_attempt('child',attempt['attempt_id'],'succeeded')
    cycle=dict(state='collected',contract=contract,request={'template_id':'confirm'},
        template_sha256=digest,contract_sha256=digest,child_task_id='child',attempt_id=attempt['attempt_id'])
    with store._transaction():
        store._db.execute('CREATE TABLE factory_loop_cycles (task_id TEXT NOT NULL,record TEXT NOT NULL)')
        store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?)',('parent',json.dumps(cycle)))
    report=dict(verdict='scoped_improvement',scope='prefill_microbenchmark',stage='confirm',
        execution_complete=True,promotion_authorized=False,full_quality_claim=False,
        verification=dict(raw_files_verified=True,independent_native_parse=True,complete_cells=4),
        gates=dict(single_token_repeatability_and_cross_arm_agreement=True,minimum_5pct_signal=True,
                   all_candidate_cell_medians_below_all_baseline=True))
    result=dict(state='succeeded',analysis=report)
    calls=[]
    class FakeWorkbench:
        def __init__(self,host):assert host is store
        def result(self,task,identifier):
            calls.append((task,identifier));return copy.deepcopy(result)
    monkeypatch.setattr(prefill_workbench,'Workbench',FakeWorkbench)
    def save_cycle(value):
        with store._transaction():
            store._db.execute('UPDATE factory_loop_cycles SET record=? WHERE task_id=?',(json.dumps(value),'parent'))
    yield SimpleNamespace(store=store,path=path,contract=contract,cycle=cycle,attempt=attempt,
        report=report,result=result,calls=calls,save_cycle=save_cycle)
    store.close()


def check(gate):return validate_scoped_prefill(gate.store.scoped('parent'),'parent',gate.contract)


def test_valid_scoped_confirm_revalidates_owned_host_result(scoped_gate):
    gate=scoped_gate
    check(gate)
    assert gate.calls==[('child',gate.attempt['attempt_id'])]


def test_spoofed_observation_without_ledger_cannot_authorize(scoped_gate):
    gate=scoped_gate
    with gate.store._transaction():gate.store._db.execute('DROP TABLE factory_loop_cycles')
    gate.store.append_observation('parent',dict(kind='scoped_prefill_result',values=gate.report))
    with pytest.raises(ValueError,match='ledger-bound'):check(gate)
    assert not gate.calls


@pytest.mark.parametrize('mutation', ['screen','not_collected','other_parent','different_contract'])
def test_nonconfirm_or_unowned_ledger_cannot_authorize(scoped_gate,mutation):
    gate=scoped_gate
    if mutation=='screen':
        gate.contract=dict(gate.contract,stage='screen')
    elif mutation=='not_collected':
        gate.cycle['state']='submitted';gate.save_cycle(gate.cycle)
    elif mutation=='other_parent':
        with gate.store._transaction():gate.store._db.execute("UPDATE factory_loop_cycles SET task_id='other'")
    else:
        gate.cycle['contract']=dict(gate.contract,contract_id='different');gate.save_cycle(gate.cycle)
    with pytest.raises(ValueError):check(gate)
    assert not gate.calls


@pytest.mark.parametrize('mutation', ['template_id','template_digest','template_file'])
def test_admitted_template_identity_is_required(scoped_gate,mutation):
    gate=scoped_gate
    if mutation=='template_id':gate.cycle['request']['template_id']='outside-policy'
    elif mutation=='template_digest':gate.cycle['template_sha256']='0'*64
    else:gate.path.write_text(json.dumps(dict(gate.contract,changed=True)))
    gate.save_cycle(gate.cycle)
    with pytest.raises(ValueError,match='template'):check(gate)
    assert not gate.calls


@pytest.mark.parametrize('mutation', ['wrong_child','wrong_adapter','wrong_contract','wrong_contract_digest','wrong_parent','not_lab'])
def test_child_attempt_identity_is_required(scoped_gate,mutation):
    gate=scoped_gate
    if mutation=='wrong_child':gate.cycle['child_task_id']='parent'
    elif mutation=='wrong_parent':
        with gate.store._transaction():
            gate.store._db.execute('UPDATE tasks SET constraints=? WHERE task_id=?',(json.dumps({'factory_loop_parent':'other'}),'child'))
    else:
        request=copy.deepcopy(gate.attempt['request']);kind='lab'
        if mutation=='wrong_adapter':request['adapter']='strata-v1'
        if mutation=='wrong_contract':request['contract']=dict(gate.contract,contract_id='wrong')
        if mutation=='wrong_contract_digest':request['contract_sha256']='0'*64
        if mutation=='not_lab':kind='build'
        with gate.store._transaction():
            gate.store._db.execute('UPDATE attempts SET request=?,kind=? WHERE task_id=? AND attempt_id=?',
                (json.dumps(request),kind,'child',gate.attempt['attempt_id']))
    gate.save_cycle(gate.cycle)
    with pytest.raises(ValueError,match='ownership or contract'):check(gate)
    assert not gate.calls


@pytest.mark.parametrize('section,key,value',[
    ('result','state','failed'),('report','verdict','screen_complete'),('report','scope','overall_speed'),
    ('report','stage','screen'),('report','execution_complete',False),('report','promotion_authorized',True),
    ('report','full_quality_claim',True),('verification','raw_files_verified',False),
    ('verification','independent_native_parse',False),('verification','complete_cells',2),
    ('gates','single_token_repeatability_and_cross_arm_agreement',False),
    ('gates','minimum_5pct_signal',False),('gates','all_candidate_cell_medians_below_all_baseline',False),
])
def test_host_report_must_pass_every_scoped_boundary(scoped_gate,section,key,value):
    gate=scoped_gate
    target=gate.result if section=='result' else gate.report if section=='report' else gate.report[section]
    target[key]=value
    with pytest.raises(ValueError,match='host-verified'):check(gate)
    assert gate.calls==[('child',gate.attempt['attempt_id'])]
