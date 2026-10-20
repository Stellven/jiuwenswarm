"""Export actual source-valid private worker custody, beyond minimal history."""
import io
import json
import zipfile

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError, validate
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime


@pytest.mark.asyncio
async def test_actual_worker_export_contains_typed_original_request_journal_assignment_and_measurement(tmp_path):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        runtime = capture_runtime(store, provider, [request])
        owner = provider.resources.bind_runtime(runtime)
        raw = b'\n  ' + json.dumps(request, indent=2).encode() + b'\n'
        result = await provider.single_cc(actor, request, original_body=raw)
        assert result['status'] == 'completed' and len(prompts) == 1
        actor = Principal(actor.account_id, actor.workspace_ids, actor.operations, frozenset({'reviewer'}))
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        request_ref = json.loads(row['request_ref'])
        scope_ref = json.loads(row['scope_ref'])
        terminal_ref = json.loads(row['terminal_ref'])
        grant_refs = [json.loads(x[0]) for x in store.connection.execute('SELECT grant_ref FROM evaluation_assignments')]
        journal = []
        pin = json.loads(row['head_ref'])
        while pin:
            journal.append(pin)
            pin = store.read_record(pin)['previous_event_ref']
        payload = EvaluationReader(store, runtime_ref=runtime).export_bytes(actor, request['request_id'], audience='reviewer')
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            manifest = json.loads(archive.read('evaluation_export.json'))
            delivered = {json_bytes(f['artifact_ref']) for f in manifest['files']}
            assert all(json_bytes(pin) in delivered for pin in [request_ref, scope_ref, terminal_ref, *grant_refs, *journal])
            assert all(archive.read(f['path']) == store.read_blob(f['artifact_ref']) for f in manifest['files'])
            raw_files = [f for f in manifest['files'] if f['kind'] == 'original_request']
            assert len(raw_files) == 1 and archive.read(raw_files[0]['path']) == raw
            kinds = {f['kind'] for f in manifest['files']}
            assert {'model_start', 'model_call', 'prompt', 'measurement', 'observation', 'deterministic_result'} <= kinds
            for f in manifest['files']:
                if f['kind'] == 'source_contract':
                    validate('subnode-execution-contract', store.read_record(f['artifact_ref']))
        # History remains available after executable resource loss, without a
        # caller getting any path back into the private effect owner.
        provider.resources = None
        assert EvaluationReader(store, runtime_ref=runtime).get(actor, request['request_id'])['result'] == result
    finally:
        store.close()


@pytest.mark.asyncio
async def test_actual_worker_history_rejects_schema_valid_foreign_private_context_and_source(tmp_path):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        runtime = capture_runtime(store, provider, [request])
        owner = provider.resources.bind_runtime(runtime)
        result = await provider.single_cc(actor, request)
        assert result['status'] == 'completed'
        actor = Principal(actor.account_id, actor.workspace_ids, actor.operations, frozenset({'reviewer'}))
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        request_ref, scope_ref = json.loads(row['request_ref']), json.loads(row['scope_ref'])
        scope = store.read_record(scope_ref)
        reader = EvaluationReader(store, runtime_ref=runtime)
        for fault in ('actual_contract', 'source_contract'):
            if fault == 'actual_contract':
                node = store.read_record(scope['actual_node_ref'])
                node['id'] += ':forged'
                node['source_template_ref'] = runtime
                validate('urn:ai4r:private:evaluation-node-context:1', node)
                forged = store.append_record('evaluation-node-context', node)
            else:
                node = store.read_record(scope['source_contract_ref'])
                node['id'] += ':forged'
                validate('subnode-execution-contract', node)
                forged = store.append_record('subnode-execution-contract', node)
            owner.event(request_ref, 'captured', capture_kind=fault, capture_ref=forged)
            with pytest.raises(ResearchError): reader.export_bytes(actor, request['request_id'], audience='reviewer')
            # Deliberate corruption fixture restores only the ledger cursor; the
            # forged immutable bytes/events remain retained and unowned.
            with store.transaction() as db:
                db.execute('UPDATE evaluation_requests SET head_ref=?,sequence=? WHERE request_ref=?',
                    (row['head_ref'], row['sequence'], json_bytes(request_ref).decode()))
    finally:
        store.close()
