import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


CAPSULE = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
sys.path.insert(0, str(CAPSULE))
from run import verify


class VerifyTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(tmp.cleanup)
        self.checkout = Path(tmp.name)
        (self.checkout / "src").mkdir()
        (self.checkout / "src/llama-sampler.cpp").write_text("int stock_sampler;\n")
        (self.checkout / "src/llama-context.cpp").write_text("int stock_context;\n")
        self.git("init", "-q", "--template=")
        self.git("add", "src")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "Fixture base")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.checkout), *args],
                              check=True, capture_output=True, text=True).stdout

    def inputs(self, filename=None):
        inputs = {"checkout": str(self.checkout)}
        if filename is not None:
            inputs["diff_path"] = str(FIXTURES / filename)
        return inputs

    def get_check(self, output, name):
        return next(check for check in output["checks"] if check["name"] == name)

    def assert_status(self, output, name, status):
        self.assertEqual(self.get_check(output, name)["status"], status, output)

    def test_verifier_rejects_marker_in_unset_branch(self):
        code = (FIXTURES / "gate-silence-positive.diff").read_text()
        branch = '+    if (!value) {\n+        LLAMA_LOG_INFO("expert_weight_cache: unexpected");\n+        return;\n+    }\n'
        code = code.replace("+    if (!value) return;\n", branch)
        header, additions = code.split(" @@\n", 1)
        header = header.rsplit(",", 1)[0] + "," + str(len(additions.splitlines()))
        patch = self.checkout / "unset-branch.diff"
        patch.write_text(header + " @@\n" + additions)
        out = verify(self.inputs(str(patch)))
        done, checks = out["done"], {row["name"]: row for row in out["checks"]}
        self.assertFalse(done, checks)
        check = checks["gate_unset_silence"]
        self.assertEqual(check["status"], "fail", checks)
        self.assertIn("recognized unset-", check["detail"])

    def test_gate_silence_fixtures(self):
        for kind, expected in (("positive", "pass"), ("negative", "inconclusive")):
            with self.subTest(kind=kind):
                fixture = f"gate-silence-{kind}.diff"
                out = verify(self.inputs(fixture))
                done, checks = out["done"], {item["name"]: item for item in out["checks"]}
                self.assertTrue(done, checks)
                self.assertEqual(checks["gate_unset_silence"]["status"], expected, checks)
                if kind == "negative":
                    self.assertIn("No preceding local", checks["gate_unset_silence"]["detail"])


    def test_high_churn_signature_is_informational(self):
        target = self.checkout / "src/llama-context.cpp"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("bool fixture_copy(int expert,\n                  long bytes);\n")
        candidate = self.checkout / "candidate.diff"
        candidate.write_bytes((FIXTURES / "gate-silence-positive.diff").read_bytes()
                              + (FIXTURES / "high-churn-signature.diff").read_bytes())
        out = verify(self.inputs(str(candidate)))
        checks = {item["name"]: item for item in out["checks"]}
        finding = checks["high_churn_signatures"]
        self.assertEqual(finding["status"], "info")
        self.assertIn("src/llama-context.cpp: fixture_copy", finding["detail"])
        self.assertTrue(out["done"], checks)

    def test_good_diff_native_packet(self):
        packet = {"capability": "verify", "inputs": self.inputs("good.diff")}
        child = subprocess.run([sys.executable, "-B", str(CAPSULE / "run.py")],
                               input=json.dumps(packet), capture_output=True, text=True, check=True)
        result = json.loads(child.stdout)
        self.assertEqual(result["outcome"], "ok")
        output = result["outputs"]
        self.assertTrue(output["done"], output)
        self.assert_status(output, "git_apply_check", "pass")
        if shutil.which("g++"):
            self.assert_status(output, "new_files_syntax", "pass")
            self.assertEqual(self.get_check(output, "new_files_syntax")["stage"], "compile")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_missing_marker(self):
        output = verify(self.inputs("missing-marker.diff"))
        self.assertFalse(output["done"])
        self.assert_status(output, "activation_markers", "fail")
        self.assert_status(output, "git_apply_check", "pass")

    def test_forbidden_file(self):
        output = verify(self.inputs("forbidden-file.diff"))
        self.assertFalse(output["done"])
        self.assert_status(output, "allowed_paths", "fail")
        self.assert_status(output, "router_sampling_scope", "fail")
        self.assert_status(output, "git_apply_check", "pass")

    def test_inapplicable_diff(self):
        output = verify(self.inputs("inapplicable.diff"))
        self.assertFalse(output["done"])
        self.assert_status(output, "git_apply_check", "fail")
        self.assert_status(output, "new_files_syntax", "skipped")

    def test_working_tree_with_untracked_addition(self):
        self.git("apply", str(FIXTURES / "good.diff"))
        (self.checkout / "src/llama-context.cpp").write_text("int changed_context;\n")
        self.git("add", "src/llama-context.cpp")
        before = self.git("status", "--porcelain")
        output = verify(self.inputs())
        self.assertTrue(output["done"], output)
        self.assert_status(output, "git_apply_check", "pass")
        self.assertEqual(self.git("status", "--porcelain"), before)

    def test_working_tree_reports_syntax_error(self):
        if not shutil.which("g++"):
            self.skipTest("g++ unavailable")
        self.git("apply", str(FIXTURES / "good.diff"))
        source = self.checkout / "src/llama-expert-weight-cache.cpp"
        source.write_text(source.read_text() + '\nint broken = ;\n')
        output = verify(self.inputs())
        self.assertFalse(output["done"])
        self.assert_status(output, "new_files_syntax", "fail")

    def test_working_tree_rejects_gate_without_default_off(self):
        self.git("apply", str(FIXTURES / "good.diff"))
        source = self.checkout / "src/llama-expert-weight-cache.cpp"
        source.write_text(source.read_text().replace(
            'gate != nullptr && std::strcmp(gate, "1") == 0', 'gate == nullptr',
        ))
        output = verify(self.inputs())
        self.assertFalse(output["done"])
        self.assert_status(output, "env_gate_default_off", "fail")

    def test_missing_header_skips_syntax_without_compile_evidence(self):
        self.git("apply", str(FIXTURES / "good.diff"))
        source = self.checkout / "src/llama-expert-weight-cache.cpp"
        source.write_text('#include "expert_weight_cache_fixture_missing.h"\n' + source.read_text())
        output = verify(self.inputs())
        self.assertTrue(output["done"], output)
        self.assert_status(output, "new_files_syntax", "skipped")
        self.assertEqual(self.get_check(output, "new_files_syntax")["stage"], "native CC execution")

    def test_block_comment_cannot_supply_markers(self):
        self.git("apply", str(FIXTURES / "good.diff"))
        source = self.checkout / "src/llama-expert-weight-cache.cpp"
        source.write_text("/*\n" + source.read_text() + "*/\n")
        output = verify(self.inputs())
        self.assertFalse(output["done"])
        self.assert_status(output, "activation_markers", "fail")
        self.assert_status(output, "env_gate_default_off", "fail")


if __name__ == "__main__":
    unittest.main()
