import json

import pytest

from scripts.factory import r8_final_benchmark as bench


def test_calibrated_settings_resolve_exact_required_leg_without_mutation(tmp_path):
    (tmp_path/'1.plan.json').write_text(json.dumps(dict(batch=2048, ubatch=1024, moe_cache_mib=65536)))
    leg = dict(id='3', batch=None, ubatch=None, moe_cache_mib=None,
               settings_from={field: f'1:plan.{field}' for field in ('batch', 'ubatch', 'moe_cache_mib')})
    result = bench.settings(leg, tmp_path)
    assert (result['batch'], result['ubatch'], result['moe_cache_mib']) == (2048, 1024, 65536)
    assert leg['batch'] is None and bench.ORDER == ('1', '3', '4', '2', '5', '6', '7', '8')


def test_consumed_load_cannot_be_repeated(tmp_path):
    leg = dict(id='3', role='P')
    receipt = tmp_path/'3.load.json'
    receipt.write_text('{"status":"stopped"}')
    with pytest.raises(RuntimeError, match='another launch'):
        bench.run_load(tmp_path, {}, leg, None, None, None, None)
    receipt.write_text('{"status":"complete"}')
    assert bench.run_load(tmp_path, {}, leg, None, None, None, None) is None
