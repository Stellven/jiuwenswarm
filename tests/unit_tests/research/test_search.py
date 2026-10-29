import hashlib
import unittest
from jiuwenswarm.research.checks.research import CheckError, validate_search


class SearchChecks(unittest.TestCase):
    def test_unicode_slices_and_exact_connector_accounting(self):
        raw = 'café 😀 bounded lookup'.encode()
        ref = {'id': 'doc', 'sha256': hashlib.sha256(raw).hexdigest()}
        scope = {'connectors': ['local_documents'], 'max_queries': 1, 'max_hits_per_query': 1, 'local_document_refs': [ref]}
        citation = {'id': 'citation:one', 'source_ref': ref, 'connector': 'local_documents', 'query': 'bounded lookup',
                    'char_start': 5, 'char_end': 6, 'excerpt': '😀', 'excerpt_sha256': hashlib.sha256('😀'.encode()).hexdigest()}
        output = {'queries': ['bounded lookup'], 'connector_outcomes': [{'connector': 'local_documents', 'status': 'used', 'reason': 'Captured', 'citations_captured': 1}],
                  'citations': [citation], 'ideas': [{'idea_id': 'idea:one', 'citation_ids': ['citation:one']}]}
        validate_search(scope, output, lambda _: raw)
        citation['char_start'] = 6
        with self.assertRaises(CheckError):
            validate_search(scope, output, lambda _: raw)

    def test_no_evidence_is_not_a_candidate(self):
        scope = {'connectors': ['arxiv'], 'max_queries': 1, 'max_hits_per_query': 1, 'local_document_refs': []}
        with self.assertRaises(CheckError):
            validate_search(scope, {'queries': ['no evidence'], 'citations': [], 'ideas': [], 'connector_outcomes': []}, lambda _: b'')
