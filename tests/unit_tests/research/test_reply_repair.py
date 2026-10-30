"""One bounded re-ask of a reply that fails its own reply schema (live run pl9b).

Screening returned an opportunity_statement of 807 characters against
maxLength 800, and the whole run halted on contract_invalid.
"""
import json

import pytest

from jiuwenswarm.research.capsules._common import ask, object_reply_schema
from jiuwenswarm.research.reply_repair import carrier_reply_schema, repair_prompt, reply_problems

SCHEMA = {'type': 'object', 'properties': {'statement': {'type': 'string', 'maxLength': 10}},
          'required': ['statement'], 'additionalProperties': False}


class Capture:
    def __init__(self):
        self.system = None

    async def model(self, prompt, system=None):
        self.system = system
        return '{"statement": "ok"}'


@pytest.mark.asyncio
async def test_runner_recovers_the_exact_reply_schema_from_an_ask_system_text():
    ctx = Capture()
    await ask(ctx, 'Stage', 'Write.', {'a': 1}, reply_schema=SCHEMA)
    assert carrier_reply_schema(ctx.system) == (True, SCHEMA)
    assert carrier_reply_schema('Plain verifier instructions') == (False, None)
    assert carrier_reply_schema(None) == (False, None)


def test_problems_name_the_rule_and_bound_but_not_the_text():
    assert reply_problems('{"statement": "' + 'x' * 12 + '"}', SCHEMA) == ['statement: maxLength 10, got 12 characters']
    assert reply_problems('```json\n{}\n```', SCHEMA) == ['(root): reply is not one finite JSON object without duplicate members']
    assert reply_problems('{"statement": "ok"}', SCHEMA) == []
    assert reply_problems('{"statement": "ok"}', None) == []


def test_live_pl9b_screening_reply_is_flagged_on_its_one_overlong_field():
    schema = object_reply_schema({'scores': ('screening-result', 'scores'),
                                  'opportunity_statement': ('opportunity-card', 'opportunity_statement')})
    reply = json.dumps({'scores': [], 'opportunity_statement': 's' * 807})
    assert reply_problems(reply, schema) == ['opportunity_statement: maxLength 800, got 807 characters',
                                             'scores: minItems 1, got 0 items']


def test_repair_prompt_keeps_the_original_inputs():
    value = json.loads(repair_prompt('{"a": 1}', '{"statement": "much too long"}', ['statement: maxLength 10, got 13 characters']))
    assert value['inputs'] == {'a': 1}
    assert value['repair']['previous_reply'] == '{"statement": "much too long"}'
    assert value['repair']['validation_errors'] == ['statement: maxLength 10, got 13 characters']


async def _ask_system():
    ctx = Capture()
    await ask(ctx, 'Stage', 'Write.', {'a': 1}, reply_schema=SCHEMA)
    return ctx.system


@pytest.mark.parametrize('owner', [None, object()])
def test_runner_re_asks_an_invalid_carrier_reply_once_on_the_product_path_only(owner):
    import asyncio
    from tests.unit_tests.research.test_transient_model_retry import _context
    from jiuwenswarm.research.runner import transient_retries
    system = asyncio.run(_ask_system())
    ctx, calls, store = _context([('ok', '{"statement": "much too long"}'), ('ok', '{"statement": "short"}')], owner=owner)
    reply = asyncio.run(ctx.model('{"a": 1}', system))
    if owner is None:
        assert reply == '{"statement": "short"}' and calls == [1, 2]
        retry = [r for k, r in store.records if k == 'model-call-retry']
        assert len(retry) == 1 and retry[0]['reason_code'] == 'reply_invalid' and retry[0]['failed_call_ordinal'] == 1
        assert transient_retries(store, 'run:1', subnode_id='screening', attempt_id='screening-a1') == 1
    else:
        assert reply == '{"statement": "much too long"}' and calls == [1] and store.records == []


def test_runner_leaves_valid_and_non_carrier_replies_alone():
    import asyncio
    from tests.unit_tests.research.test_transient_model_retry import _context
    system = asyncio.run(_ask_system())
    ctx, calls, _ = _context([('ok', '{"statement": "ok"}')])
    assert asyncio.run(ctx.model('{}', system)) == '{"statement": "ok"}' and calls == [1]
    ctx, calls, _ = _context([('ok', 'not json at all')])
    assert asyncio.run(ctx.model('{}', 'Verifier instructions')) == 'not json at all' and calls == [1]


def test_only_one_extra_call_even_if_the_repair_is_still_invalid():
    import asyncio
    from tests.unit_tests.research.test_transient_model_retry import _context
    system = asyncio.run(_ask_system())
    ctx, calls, _ = _context([('ok', '{"statement": "much too long"}'), ('ok', '{"statement": "still too long"}')])
    assert asyncio.run(ctx.model('{}', system)) == '{"statement": "still too long"}' and calls == [1, 2]
