import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from benchmarks.harbor_suite import value_product_evidence as subject


def fixture(path, *, tamper=False):
    files = {}
    inventory = []
    def put(name, value, identity):
        raw = json.dumps(value, sort_keys=True).encode() if not isinstance(value, bytes) else value
        ref = {"id": identity, "sha256": hashlib.sha256(raw).hexdigest()}
        files[name] = raw
        inventory.append({"path": name, "artifact_ref": ref})
        return ref
    output = put("paper_summary.json", b'original answer', 'blob:answer')
    call_refs = []
    for index, function in enumerate(("worker", "verifier")):
        call_refs.append(put("evidence/model-call-" + str(index) * 64 + ".json", {
            "id": "call:" + str(index), "call_function": function, "outcome": "completed",
            "usage": {"input_tokens": 10, "output_tokens": 2, "cost_amount": None}}, "call:" + str(index)))
    # A start record must not be counted as another executed model call.
    put("evidence/model-call-start-" + "5" * 64 + ".json", {"id": "start:0"}, "start:0")
    for index, call in enumerate(call_refs):
        put("evidence/invocation-observation-" + str(index) * 64 + ".json", {
            "run_id": "run:one", "node_id": "summary", "subnode_id": str(index),
            "cc_name": "worker" if index == 0 else "verifier", "outcome": "success",
            "model_calls": 100, "trace_refs": [call], "output_refs": [output]}, "observation:" + str(index))
    if tamper:
        files["paper_summary.json"] = b'altered answer'
    files["client_retrieval.json"] = json.dumps({"run_id": "run:one", "files": inventory}).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)


class ProductEvidenceTests(unittest.TestCase):
    def test_full_pipeline_counts_worker_and_verifier_without_observation_double_counting(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "originals.zip"
            fixture(path)
            result = subject.audit_archive(path, expected_run_id="run:one")
            self.assertEqual(result["model_calls"], 2)
            self.assertEqual(result["call_functions"], {"worker": 1, "verifier": 1})
            self.assertEqual(result["usage"]["input_tokens"]["total"], 20)
            self.assertIsNone(result["usage"]["cost_amount"]["total"])
            self.assertTrue(result["all_model_calls_joined"])
            self.assertEqual(result["missing_output_refs"], [])
            self.assertEqual(result["invocations"][0]["output_refs"][0]["archive_paths"], ["paper_summary.json"])

    def test_tampered_original_bytes_and_foreign_run_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "originals.zip"
            fixture(path, tamper=True)
            with self.assertRaisesRegex(ValueError, "bytes differ"):
                subject.audit_archive(path)
            fixture(path)
            with self.assertRaisesRegex(ValueError, "another run"):
                subject.audit_archive(path, expected_run_id="run:foreign")


if __name__ == "__main__":
    unittest.main()
