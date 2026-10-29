"""Planner carrier: node limits are the capsule's declared max_limits when they fit.

Live run pl3 (2026-10-29): the model gave Screening 120 s; its two reserved
60 s reviews left no worker time and the node ended budget_exhausted.
"""
import json

from jiuwenswarm.research.capsules.planner import fill_declared_limits

PIN = {'cc_name': 'research.screening', 'cc_version': 'm1-4', 'declaration_sha256': 'a' * 64}
SEARCH = {'cc_name': 'research.search', 'cc_version': 'm1-3', 'declaration_sha256': 'b' * 64}
SNAPSHOT = {'entries': [
    {**PIN, 'selectable_by_planner': True, 'max_limits': {'time_s': 240, 'model_calls': 3, 'memory_mb': 16384}},
    {**SEARCH, 'selectable_by_planner': True, 'max_limits': {'time_s': 360, 'model_calls': 3, 'memory_mb': 16384}}]}
POLICY = {'aggregate_limits': {'time_s': 10800, 'model_calls': 80, 'memory_mb': 16384}}


def _proposal(screening_time=120):
    return json.dumps({'limits': {'time_s': 420, 'model_calls': 6, 'memory_mb': 16384}, 'nodes': [
        {'node_id': 'search', 'cc': SEARCH, 'limits': {'time_s': 300, 'model_calls': 3, 'memory_mb': 16384}},
        {'node_id': 'screening', 'cc': PIN, 'limits': {'time_s': screening_time, 'model_calls': 3, 'memory_mb': 16384}}]})


def test_nodes_get_declared_envelopes_and_aggregate_covers_them():
    value = json.loads(fill_declared_limits(_proposal(), SNAPSHOT, POLICY))
    assert [n['limits']['time_s'] for n in value['nodes']] == [360, 240]
    assert value['limits'] == {'time_s': 600, 'model_calls': 6, 'memory_mb': 16384}


def test_larger_model_aggregate_is_kept_within_policy():
    raw = json.loads(_proposal()); raw['limits']['time_s'] = 5000
    assert json.loads(fill_declared_limits(json.dumps(raw), SNAPSHOT, POLICY))['limits']['time_s'] == 5000


def test_unchanged_when_envelopes_exceed_policy_or_pin_unknown_or_text_invalid():
    tight = {'aggregate_limits': {'time_s': 500, 'model_calls': 80, 'memory_mb': 16384}}
    assert fill_declared_limits(_proposal(), SNAPSHOT, tight) == _proposal()
    unknown = json.loads(_proposal()); unknown['nodes'][0]['cc'] = {**SEARCH, 'cc_version': 'm9-9'}
    assert fill_declared_limits(json.dumps(unknown), SNAPSHOT, POLICY) == json.dumps(unknown)
    assert fill_declared_limits('not json', SNAPSHOT, POLICY) == 'not json'
