"""Completed exact request history survives loss of executable resources."""
import copy
import json

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime, product_state
from tests.unit_tests.research.test_evaluation_private_replay import replay_runtime
from tests.unit_tests.research.test_evaluation_replay import replay_fixture


async def bound_fixture(root, entry_point):
    if entry_point == 'E3':
        store, provider, actor, request, prompts = await source_fixture(root)
        second = request | {'request_id': request['request_id'] + ':unused'}
        owner = provider.resources.bind_runtime(capture_runtime(store, provider, [request, second]))
    else:
        store, provider, actor, request, prompts, _ = await replay_fixture(root,
            bad_span=False, record_gate=True)
        second = request | {'request_id': request['request_id'] + ':unused'}
        owner = provider.resources.bind_runtime(replay_runtime(store, provider, [request, second]))
        owner.runner.model.persist = owner.runner.capture_record
    return store, provider, actor, request, second, prompts, owner


def private_snapshot(store):
    return {name: [tuple(row) for row in store.connection.execute('SELECT * FROM ' + name)]
        for name in ('evaluation_requests', 'evaluation_assignments', 'evaluation_calls', 'evaluation_tools',
            'artifacts', 'records')}


@pytest.mark.asyncio
async def test_bound_runtime_unknown_request_never_falls_back_to_legacy_metadata(tmp_path):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        # This explicitly retired record is readable by the historical unbound
        # provider. Its old identity omits runtime/assets and grants no execution.
        historical = {'historical_fixture': True}
        key = provider._key(request['request_id'])
        result_ref = store.append_record('evaluation-result', {'id': key + ':result',
            'result': historical, 'invalid_for_product': True})
        record = {'fingerprint': 'retired-history-only', 'status': 'completed',
            'result_ref': result_ref, 'failure_ref': None}
        with store.transaction() as db:
            db.execute('INSERT INTO metadata(key,value) VALUES(?,?)', (key, json_bytes(record).decode()))
        assert provider.get(actor, request['request_id'])['result'] == historical
        provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
        before = private_snapshot(store)
        metadata_before = [tuple(row) for row in store.connection.execute('SELECT * FROM metadata')]
        product_before = product_state(store)
        with pytest.raises(ResearchError) as missing:
            provider.get(actor, request['request_id'])
        assert missing.value.code == 'not_found'
        assert not prompts and private_snapshot(store) == before and product_state(store) == product_before
        assert [tuple(row) for row in store.connection.execute('SELECT * FROM metadata')] == metadata_before
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('entry_point', ['E2', 'E3'])
async def test_completed_original_get_and_duplicate_post_survive_resource_loss_without_effects(tmp_path, entry_point):
    store, provider, actor, request, second, prompts, owner = await bound_fixture(tmp_path, entry_point)
    try:
        method = provider.single_cc if entry_point == 'E3' else provider.node_replay
        raw = b' \n' + json.dumps(request, indent=2).encode() + b'\n'
        first = await method(actor, request, original_body=raw)
        assert (first['status'] == 'completed') if entry_point == 'E3' else (first['tier2_verdict'] == 'PASS')
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        captured = store.read_record(json.loads(row['request_ref']))
        assert store.read_blob(captured['original_request_ref']) == raw
        before = private_snapshot(store); product_before = product_state(store); count = len(prompts)
        provider.resources = None
        owner.runner._evaluation_owners.clear(); owner.runner.model = None; owner.runner.executor = None
        # GET uses actual stored scope/terminal; POST reconciles exact normalized
        # identity before looking for current Library/model/executor resources.
        observed = {}; got = repeated = None
        try: got = provider.get(actor, request['request_id'])
        except ResearchError as error: observed['get'] = error.code
        duplicate = copy.deepcopy(request)
        if entry_point == 'E2' and duplicate.get('host_records') == []: duplicate.pop('host_records')
        try: repeated = await method(actor, duplicate, original_body=json_bytes(duplicate))
        except ResearchError as error: observed['post'] = error.code
        assert not observed, observed
        assert got == {'request_id': request['request_id'], 'status': 'completed', 'result': first,
            'failure_ref': None, 'invalid_for_product': True}
        assert repeated == first
        with pytest.raises(ResearchError) as conflict:
            await method(actor, request | {'case_id': request['case_id'] + ':changed'})
        assert conflict.value.code == 'identity_conflict'
        for bad_body in [b'\xff', b'{"request_id":' + json.dumps(request['request_id']).encode() + b',' + json_bytes(request)[1:]]:
            with pytest.raises(ResearchError): await method(actor, request, original_body=bad_body)
        with pytest.raises(ResearchError): await method(actor, second)
        foreign = Principal('foreign', actor.workspace_ids, actor.operations, actor.audiences)
        with pytest.raises(ResearchError): provider.get(foreign, request['request_id'])
        with pytest.raises(ResearchError): await method(foreign, request)
        assert len(prompts) == count and private_snapshot(store) == before and product_state(store) == product_before
        assert store.read_blob(captured['original_request_ref']) == raw
    finally:
        store.close()


@pytest.mark.asyncio
async def test_resource_loss_never_upgrades_orphan_terminal_to_historical_success(tmp_path):
    store, provider, actor, request, second, prompts, owner = await bound_fixture(tmp_path, 'E3')
    try:
        await provider.single_cc(actor, request)
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        terminal = store.read_record(json.loads(row['terminal_ref']))
        with store.transaction() as db:
            db.execute('UPDATE evaluation_requests SET head_ref=?,sequence=? WHERE request_ref=?',
                (json_bytes(terminal['through_event_ref']).decode(), row['sequence'] - 1, row['request_ref']))
        before = private_snapshot(store)
        provider.resources = None
        owner.runner._evaluation_owners.clear(); owner.runner.model = None; owner.runner.executor = None
        observed = {}
        try: provider.get(actor, request['request_id'])
        except ResearchError as error: observed['get'] = error.code
        try: await provider.single_cc(actor, request)
        except ResearchError as error: observed['post'] = error.code
        assert observed == {'get': 'integrity_fault', 'post': 'integrity_fault'}, observed
        assert len(prompts) == 1 and private_snapshot(store) == before
    finally:
        store.close()
