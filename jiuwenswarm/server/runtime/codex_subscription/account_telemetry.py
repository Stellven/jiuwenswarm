"""Safe informational projection of packaged Codex 0.144.4 account limits.

This is private native account telemetry, never model-call tokens or cost.
Unknown protocol properties are intentionally not copied into protected evidence.
"""
from __future__ import annotations

import json


READ_SCHEMA_SHA256='26bed5356b0b7abd8f3f5bdd2f55d16123e340b038afee26a35d5470f4c17f5b'
UPDATE_SCHEMA_SHA256='18667a04b74ed14480d4d7f6fdb412b47a4ccb25ae7d1d3b89b53120a18dddea'
PLANS=frozenset('free go plus pro prolite team self_serve_business_usage_based business enterprise_cbp_usage_based enterprise edu unknown'.split())
REACHED=frozenset('rate_limit_reached workspace_owner_credits_depleted workspace_member_credits_depleted workspace_owner_usage_limit_reached workspace_member_usage_limit_reached'.split())


def _nullable(parse):
    return lambda value:None if value is None else parse(value)


def _integer(value,bits=64):
    if type(value) is not int or not -(2**(bits-1))<=value<2**(bits-1):raise ValueError('Invalid protocol integer')
    return value


def _string(value):
    if not isinstance(value,str):raise ValueError('Invalid protocol string')
    return value


def _boolean(value):
    if type(value) is not bool:raise ValueError('Invalid protocol boolean')
    return value


def _enum(values):
    def parse(value):
        if not isinstance(value,str) or value not in values:raise ValueError('Invalid protocol enum')
        return value
    return parse


def _object(fields,required=()):
    def parse(value):
        if not isinstance(value,dict) or not set(required)<=value.keys():raise ValueError('Invalid protocol object')
        return {key:parse_field(value[key]) for key,parse_field in fields.items() if key in value}
    return parse


WINDOW=_object({'usedPercent':lambda v:_integer(v,32),'resetsAt':_nullable(_integer),
    'windowDurationMins':_nullable(_integer)},('usedPercent',))
CREDITS=_object({'hasCredits':_boolean,'unlimited':_boolean,'balance':_nullable(_string)},('hasCredits','unlimited'))
SPEND=_object({'limit':_string,'used':_string,'remainingPercent':lambda v:_integer(v,32),
    'resetsAt':_integer},('limit','used','remainingPercent','resetsAt'))
BUCKET=_object({'limitId':_nullable(_string),'limitName':_nullable(_string),'planType':_nullable(_enum(PLANS)),
    'primary':_nullable(WINDOW),'secondary':_nullable(WINDOW),'credits':_nullable(CREDITS),
    'individualLimit':_nullable(SPEND),'rateLimitReachedType':_nullable(_enum(REACHED))})
RESET_CREDIT=_object({'id':_string,'grantedAt':_integer,'expiresAt':_nullable(_integer),
    'resetType':_enum({'codexRateLimits','unknown'}),'status':_enum({'available','redeeming','redeemed','unknown'}),
    'description':_nullable(_string),'title':_nullable(_string)},('id','grantedAt','resetType','status'))


def _reset_rows(value):
    if not isinstance(value,list):raise ValueError('Invalid reset-credit rows')
    return [RESET_CREDIT(row) for row in value]


RESET_SUMMARY=_object({'availableCount':_integer,'credits':_nullable(_reset_rows)},('availableCount',))


def _buckets(value):
    if not isinstance(value,dict) or any(not isinstance(key,str) for key in value):raise ValueError('Invalid bucket map')
    return {key:BUCKET(row) for key,row in value.items()}


def safe_limits(value,*,notification=False):
    fields={'rateLimits':BUCKET}
    if not notification:fields.update(rateLimitsByLimitId=_nullable(_buckets),rateLimitResetCredits=_nullable(RESET_SUMMARY))
    result=_object(fields,('rateLimits',))(value)
    # Same finite envelope bound as the pinned private transport; no truncation.
    if len(json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8'))>4*1024*1024:
        raise ValueError('Account telemetry envelope exceeds private transport bound')
    return result


def missing_fields(values):
    missing={}
    for key in ('rateLimitsByLimitId','rateLimitResetCredits'):
        if values.get(key) is None:missing[key]='not_reported_by_packaged_runtime'
    buckets=[('rateLimits',values['rateLimits'])]
    buckets += [('rateLimitsByLimitId.'+key,value) for key,value in (values.get('rateLimitsByLimitId') or {}).items()]
    for name,bucket in buckets:
        for key in ('primary','secondary','credits','individualLimit','planType','rateLimitReachedType'):
            if bucket.get(key) is None:missing[name+'.'+key]='not_reported_by_packaged_runtime'
        if bucket.get('credits') is not None and bucket['credits'].get('balance') is None:
            missing[name+'.credits.balance']='not_reported_by_packaged_runtime'
    return missing
