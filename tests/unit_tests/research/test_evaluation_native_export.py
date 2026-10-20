"""Actual trace writer and late claim-linked original packet custody."""
import io
import json
import zipfile

import pytest

from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime


@pytest.mark.asyncio
async def test_late_original_native_trace_packets_follow_only_typed_call_owned_edges(tmp_path):
    from jiuwenswarm.research.evaluation_authority import capture_evaluation_native
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    from jiuwenswarm.server.runtime.codex_subscription.governed_trace import GovernedTrace
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        runtime = capture_runtime(store, provider, [request])
        owner = provider.resources.bind_runtime(runtime)
        result = await provider.single_cc(actor, request)
        assert result['status'] == 'completed'
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        request_ref = json.loads(row['request_ref'])
        start_event = owner.captures(request_ref, 'model_start')[0]
        start_ref = start_event['capture_ref']
        start = store.read_record(start_ref)
        claim_ref = start['call_claim_ref']
        claim = store.read_record(claim_ref)
        context = {k: claim[k] for k in ('execution_id', 'invocation_id', 'call_id', 'contract_ref')}
        context['call_claim_ref'] = claim_ref
        child = store.read_record(claim['contract_ref'])
        scope = {k: child[k] for k in ('run_id', 'node_id', 'subnode_id', 'attempt_id')}
        scope.update({k: claim[k] for k in ('execution_id', 'invocation_id', 'call_id', 'contract_ref')})
        scope['model_call_start_ref'] = start_ref
        trace = GovernedTrace(scope,
            lambda kind, record: capture_evaluation_native(store, kind, record, context=context), store.put_blob)
        raw = b' {"id":3,"result":{"thread":{"id":"owned-thread"}}}\n'
        trace.request_observer('thread/start')('in', raw, json.loads(raw))
        # Actual trace writer excludes interleaved unrelated account packets.
        secret = b'{"method":"account/login","params":{"secret":"unrelated"}}\n'
        trace.notification('in', secret, json.loads(secret))
        summary_ref = trace.finish('completed')
        summary = store.read_record(summary_ref)
        event_ref = summary['event_refs'][0]
        raw_ref = store.read_record(event_ref)['raw_ref']
        actor = Principal(actor.account_id, actor.workspace_ids, actor.operations, frozenset({'reviewer'}))
        payload = EvaluationReader(store, runtime_ref=runtime).export_bytes(actor, request['request_id'], audience='reviewer')
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            manifest = json.loads(archive.read('evaluation_export.json'))
            delivered = {json_bytes(f['artifact_ref']): f['path'] for f in manifest['files']}
            assert all(json_bytes(ref) in delivered for ref in (start_ref, summary_ref, event_ref, raw_ref))
            assert archive.read(delivered[json_bytes(raw_ref)]) == raw
            assert all(secret not in archive.read(f['path']) for f in manifest['files'])
        assert len(prompts) == 1 and owner.inspect(request_ref)['state'] == 'completed'
    finally:
        store.close()
