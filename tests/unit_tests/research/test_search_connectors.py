import hashlib
import unittest
from unittest.mock import Mock

from jiuwenswarm.research.connectors import AcademicConnectors
from jiuwenswarm.research.contracts.types import ResearchError


class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_bound_search_has_fresh_claims_frozen_scope_and_no_external_egress(self):
        data = b'bounded lookup evidence'
        ref = {'id': 'local', 'sha256': hashlib.sha256(data).hexdigest()}
        scope = {'connectors': ['local_documents', 'arxiv'], 'max_queries': 1, 'max_hits_per_query': 1, 'local_document_refs': [ref]}
        store = Mock(); store.read_record.return_value = scope; store.read_blob.return_value = data
        claims = []
        def before_tool(operation):
            claims.append(operation)
            return {'id': 'claim:' + str(len(claims)), 'sha256': 'a' * 64}
        contract = {'run_id': 'run:unit', 'inputs': [{'name': 'search_scope', 'artifact_refs': [{'id': 'scope', 'sha256': 'b' * 64}]}],
            'subnode_limits': {'tool_calls': 1}, 'bindings': [{'limits': {'tool_calls': 1},
                'effective_authority': {'tools': ['deepsearch'], 'network': 'none', 'network_allowlist': []}}]}
        operator = AcademicConnectors(store, approved={'local_documents', 'arxiv'}, timeout_s=5)
        for invocation in ['invocation:one', 'invocation:two']:
            bound = operator.bind_invocation({'id': 'contract', 'sha256': 'c' * 64}, invocation, contract, before_tool=before_tool)
            with self.assertRaises(ResearchError): await bound.retrieve(dict(scope, max_queries=2), ['bounded lookup'])
            citations, outcomes = await bound.retrieve(scope, ['bounded lookup'])
            self.assertEqual(citations[0]['source_ref'], ref)
            self.assertEqual(outcomes[1]['status'], 'unavailable')
            with self.assertRaises(ResearchError): await bound.retrieve(scope, ['bounded lookup'])
        self.assertEqual(claims, ['deepsearch', 'deepsearch'])
        self.assertEqual(operator.tool_calls, 0)

    async def test_scope_only_local_capture_and_unavailable(self):
        data = 'café 😀 bounded lookup evidence'.encode()
        ref = {'id': 'local', 'sha256': hashlib.sha256(data).hexdigest()}
        store = Mock(); store.read_blob.return_value = data
        connector = AcademicConnectors(store, approved={'local_documents'}, timeout_s=5)
        scope = {'connectors': ['local_documents', 'arxiv'], 'local_document_refs': [ref], 'max_hits_per_query': 1}
        citations, outcomes = await connector.retrieve(scope, ['bounded lookup'])
        self.assertEqual(citations[0]['source_ref'], ref)
        self.assertEqual(outcomes[1]['status'], 'unavailable')
        self.assertEqual(outcomes[1]['citations_captured'], 0)
        self.assertEqual(connector.tool_calls, 1)

    async def test_no_tool_after_hard_ceiling(self):
        store = Mock(); store.read_blob.return_value = b'bounded lookup'
        connector = AcademicConnectors(store, approved={'local_documents'}, timeout_s=5, tool_limit=1)
        scope = {'connectors': ['local_documents'], 'local_document_refs': [{'id': 'a', 'sha256': 'a' * 64}], 'max_hits_per_query': 1}
        with self.assertRaises(ResearchError):
            await connector.retrieve(scope, ['bounded lookup', 'another query'])
        self.assertEqual(connector.tool_calls, 1)
