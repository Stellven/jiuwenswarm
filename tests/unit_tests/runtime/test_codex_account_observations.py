"""Independent vectors from the packaged 0.144.4 generated account schemas.

The transport is an explicit double; this suite performs no account/network call.
"""
import asyncio
import json

import pytest

from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
from jiuwenswarm.server.runtime.codex_subscription.account_telemetry import safe_limits


def limits():
    bucket={'limitId':'codex','limitName':'Codex','planType':'plus',
        'primary':{'usedPercent':17,'windowDurationMins':300,'resetsAt':1792190000},
        'secondary':None,'credits':{'hasCredits':True,'unlimited':False,'balance':'12.50'},
        'individualLimit':{'limit':'100','used':'3','remainingPercent':97,'resetsAt':1792190000}}
    return {'rateLimits':bucket,'rateLimitsByLimitId':{'codex':bucket},
        'rateLimitResetCredits':{'availableCount':2,'credits':None}}


class AccountDouble:
    def __init__(self):
        self.listeners=set();self.email='one@example.invalid';self.response=limits();self.failure=False;self.change_during_read=False;self.calls=[]
    async def start(self):pass
    def emit(self,name,params):
        for fn in tuple(self.listeners):fn(name,params)
    async def request(self,method,params):
        self.calls.append((method,params))
        if method=='account/read':return {'account':{'type':'chatgpt','email':self.email,'planType':'plus'}}
        assert method=='account/rateLimits/read' and params=={}
        if self.failure:raise CodexError('RUNTIME_ERROR')
        if self.change_during_read:
            self.email='two@example.invalid';self.emit('account/updated',{'authMode':'chatgpt','planType':'plus'})
        return self.response


def test_protocol_projection_preserves_nulls_and_observed_zero_without_cost_conversion():
    raw=limits();raw['rateLimits']['primary']['usedPercent']=0
    raw['apiKey']='private sentinel';raw['rateLimits']['loginUrl']='private sentinel'
    result=safe_limits(raw)
    assert result['rateLimits']['primary']['usedPercent']==0
    assert result['rateLimits']['secondary'] is None
    assert result['rateLimitResetCredits']=={'availableCount':2,'credits':None}
    assert result['rateLimits']['credits']['balance']=='12.50'
    assert 'private sentinel' not in json.dumps(result)
    assert not {'input_tokens','output_tokens','cost_amount','currency'} & result.keys()
    with pytest.raises(ValueError):safe_limits({'rateLimits':{'primary':{'usedPercent':True}}})
    with pytest.raises(ValueError):safe_limits({'rateLimits':{},'rateLimitResetCredits':{'availableCount':float('nan')}})


def test_durable_writer_receives_attributed_separate_read_and_sparse_event(tmp_path):
    transport=AccountDouble();service=SubscriptionService(tmp_path,transport=transport);captured=[]
    service.set_account_observer(lambda kind,row:captured.append((kind,row)))
    assert asyncio.run(service.status())['state']=='ready'
    kind,row=captured[-1]
    assert kind=='subscription-account-observation' and row['informational_only'] is True
    assert row['account_fingerprint'] and row['epoch']==service.epoch
    assert row['source']['method']=='account/rateLimits/read' and row['source']['runtime_version']=='0.144.4'
    assert row['values']['rateLimitsByLimitId']['codex']['credits']['balance']=='12.50'
    transport.emit('account/rateLimits/updated',{'rateLimits':{'limitId':'codex','primary':None,'credits':None}})
    sparse=captured[-1][1]
    assert sparse['source']['method']=='account/rateLimits/updated' and sparse['sparse_update'] is True
    assert sparse['values']['rateLimits']['credits'] is None
    assert service.last_account_observation['values']['rateLimits']['credits']['balance']=='12.50'
    assert not any('consume' in method for method,_ in transport.calls)


def test_errors_and_identity_change_do_not_retain_another_accounts_balance(tmp_path):
    transport=AccountDouble();service=SubscriptionService(tmp_path,transport=transport);captured=[]
    service.set_account_observer(lambda kind,row:captured.append(row))
    asyncio.run(service.status());first=captured[-1]
    transport.change_during_read=True
    assert asyncio.run(service.status())['state']=='ready'
    assert captured[-1]['values'] is None and captured[-1]['unavailable_reason']=='account_identity_changed_during_read'
    assert service.last_account_observation is None
    transport.change_during_read=False;transport.failure=True
    assert asyncio.run(service.status())['state']=='ready'
    assert captured[-1]['values'] is None and captured[-1]['unavailable_reason']=='account_limits_read_failed'
    assert captured[-1]['account_fingerprint']!=first['account_fingerprint']
    service.set_account_observer(lambda *_:(_ for _ in ()).throw(OSError('private storage error')))
    assert asyncio.run(service.status())['state']=='ready'
    assert service.account_observation_state=={'status':'unavailable','reason':'observation_persistence_failed'}


def test_account_observations_survive_actual_store_reopen_as_private_records(tmp_path):
    from jiuwenswarm.research.state import SQLiteRunStore
    transport=AccountDouble();service=SubscriptionService(tmp_path/'profile',transport=transport)
    store=SQLiteRunStore(tmp_path/'state',recover=False)
    service.set_account_observer(store.append_record)
    assert asyncio.run(service.status())['state']=='ready'
    store.close()
    reopened=SQLiteRunStore(tmp_path/'state',recover=False)
    rows=list(reopened.iter_records(kinds={'subscription-account-observation'}))
    assert len(rows)==1
    observation=reopened.read_record(rows[0]['ref'])
    assert observation['values']['rateLimitResetCredits']['availableCount']==2
    assert observation['source']['schema_sha256']=='26bed5356b0b7abd8f3f5bdd2f55d16123e340b038afee26a35d5470f4c17f5b'
    assert transport.email not in json.dumps(observation)
    assert not list(reopened.iter_records(kinds={'model-call'}))
    reopened.close()
