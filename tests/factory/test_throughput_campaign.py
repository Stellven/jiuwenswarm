import copy
import time
import pytest

from jiuwenswarm.factory.throughput_campaign import judge, placement
from jiuwenswarm.factory.throughput_campaign import Campaign


def cell(arm, rate):
    return dict(arm=arm,placement={'layers':'fixed'},requests=[dict(ids=[1,2],finish='length',decode_tps=rate)]*2)


def test_confirmation_requires_exactness_and_conservative_target():
    cells=[cell('A',10),cell('B',12),cell('B',11.5),cell('A',10.2)]
    report=judge('confirm',cells,.1,.05)
    assert report['verdict']=='target_met'
    assert report['baseline_tokens_s']==10.1
    cells[2]['requests'][1]=dict(ids=[1,3],finish='length',decode_tps=100)
    assert judge('confirm',cells,.1,.05)['verdict']=='inconclusive'


def test_average_gain_cannot_hide_slow_candidate_or_unstable_baseline():
    cells=[cell('A',10),cell('B',20),cell('B',10.5),cell('A',10)]
    assert judge('confirm',cells,.1,.05)['verdict']=='target_not_met'
    cells[-1]=cell('A',11)
    assert judge('confirm',cells,.1,.05)['verdict']=='inconclusive'


def test_screen_is_not_acceptance_and_order_cannot_be_changed():
    cells=[cell('A',10),cell('B',12)]
    assert judge('screen',cells,.1,.05)['verdict']=='screen_positive'
    with pytest.raises(ValueError):judge('confirm',cells,.1,.05)
    cells[1]['placement']={'layers':'changed'}
    assert judge('screen',cells,.1,.05)['verdict']=='inconclusive'


def test_complete_placement_required():
    lines=['ds4: fixed expert budget requested=76 effective=76 safe=80 bytes']
    lines += [f'ds4: fixed placement layer={i} experts=384 resident=200 fnv1a64=0123456789abcdef' for i in range(40)]
    lines += ['ds4: fixed placement layers=40 fnv1a64=0123456789abcdef']
    assert len(placement('\n'.join(lines),'76')['layers'])==40
    with pytest.raises(ValueError):placement('\n'.join(lines[:-2]+lines[-1:]),'76')


def test_admission_caps_gpu_processes_and_reuses_keys(store, tmp_path, monkeypatch):
    contract=dict(adapter='strata-v1',version=1,target='spark-gb10',tolerance='canonical-token-ids-and-finish',
        assets={'identity_path':str(tmp_path/'assets.json'),'identity_sha256':'a'*64},
        workload={'argv':['--experts','6','--mmap-experts','on','--dspark','none','--cpu-threads','8'],
                  'environment':{'STRATA_DS4_REUSE':'0','DS4_EXPERT_BUDGET_BYTES':'76000000000'},
                  'requests':[{'ids':[1,2],'max_new_tokens':64}]*2},
        limits={'cpus':8,'memory_bytes':104*2**30,'extra_swap_bytes':0,'guard_gib':8,'timeout_s':300})
    policy=dict(contract=contract,deadline=time.time()+100,max_gpu_processes=2,
        baseline_image={'tag':'factory/strata:fixture','id':'sha256:'+'a'*64},
        allowed_environment={'DS4_AHEAD':['0','1']},allowed_arguments={'--cpu-threads':['6','8']})
    store.create_task(dict(task_id='throughput',objective='Synthetic admission check',
        constraints={'throughput_campaign':policy},allowed_effects=['process.exec','gpu.use']))
    campaign=Campaign(store,'throughput')
    def submit(task,kind,request,key,*args):
        return store.create_attempt(task,dict(kind=kind,request=request,idem_key=key,fingerprint=key))
    monkeypatch.setattr(campaign.jobs,'submit',submit)
    monkeypatch.setattr(campaign,'status',lambda aid:store.read('throughput',aid))
    with pytest.raises(ValueError,match='envelope'):
        campaign.submit({'stage':'screen','environment':{'STRATA_DS4_REUSE':'1'}},'bad')
    with pytest.raises(ValueError,match='A/A'):
        campaign.submit({'stage':'screen'},'early')
    first=campaign.submit({'stage':'aa'},'one')
    assert campaign.submit({'stage':'aa'},'one')['attempt_id']==first['attempt_id']
    with pytest.raises(ValueError,match='different'):
        campaign.submit({'stage':'screen'},'one')
    with pytest.raises(ValueError,match='allowance'):
        campaign.submit({'stage':'aa'},'two')
