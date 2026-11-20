import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CAPSULE = Path(__file__).resolve().parents[1]
FIXTURES = CAPSULE / "tests/fixtures"
sys.path.insert(0, str(CAPSULE))
from run import verify


class VerifyTests(unittest.TestCase):
    def setUp(self):
        scratch = CAPSULE / "tests/.cc-state"
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.checkout = self.root / "checkout"
        (self.checkout / "src").mkdir(parents=True)
        (self.checkout / "src/llama-context.cpp").write_text("int context = 1;\n")
        (self.checkout / "src/llama-sampling.cpp").write_text("int sampling = 1;\n")
        self.git("init", "--quiet")
        self.git("add", ".")
        self.git("-c", "user.email=fixture@example.invalid", "-c", "user.name=Fixture",
                 "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                 "commit", "--quiet", "-m", "Fixture base")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.checkout), *args], check=True,
                              capture_output=True, text=True).stdout

    def check_fixture(self, name=None):
        inputs = {"checkout": str(self.checkout)}
        if name:
            inputs["diff_path"] = str(FIXTURES / name)
        result = verify(inputs)
        return result["done"], {check["name"]: check for check in result["checks"]}

    def test_verifier_rejects_marker_in_unset_branch(self):
        code = (FIXTURES / "gate-silence-positive.diff").read_text()
        branch = '+    if (!value) {\n+        LLAMA_LOG_INFO("expert_demand_predictor: unexpected");\n+        return;\n+    }\n'
        code = code.replace("+    if (!value) return;\n", branch)
        header, additions = code.split(" @@\n", 1)
        header = header.rsplit(",", 1)[0] + "," + str(len(additions.splitlines()))
        patch = self.root / "unset-branch.diff"
        patch.write_text(header + " @@\n" + additions)
        out = verify({"checkout": str(self.checkout), "diff_path": str(patch)})
        done, checks = out["done"], {row["name"]: row for row in out["checks"]}
        self.assertFalse(done, checks)
        check = checks["gate_unset_silence"]
        self.assertEqual(check["status"], "fail", checks)
        self.assertIn("recognized unset-", check["detail"])

    def test_gate_silence_fixtures(self):
        for kind, expected in (("positive", "pass"), ("negative", "inconclusive")):
            with self.subTest(kind=kind):
                fixture = f"gate-silence-{kind}.diff"
                done, checks = self.check_fixture(fixture)
                done, checks = done, checks
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
        out = verify({"checkout": str(self.checkout), "diff_path": str(candidate)})
        checks = {item["name"]: item for item in out["checks"]}
        finding = checks["high_churn_signatures"]
        self.assertEqual(finding["status"], "info")
        self.assertIn("src/llama-context.cpp: fixture_copy", finding["detail"])
        self.assertTrue(out["done"], checks)

    def test_good_diff_and_syntax(self):
        done, checks = self.check_fixture("good.diff")
        self.assertTrue(done, checks)
        self.assertEqual(checks["apply_check"]["stage"], "native CC execution")
        syntax = checks["cxx_syntax:src/llama-expert-predict.cpp"]
        self.assertEqual(syntax["status"], "pass" if shutil.which("g++") else "skipped")
        self.assertEqual(syntax["stage"], "compile")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_missing_marker(self):
        done, checks = self.check_fixture("missing-marker.diff")
        self.assertFalse(done)
        self.assertEqual(checks["activation_markers"]["status"], "fail")

    def test_forbidden_path(self):
        done, checks = self.check_fixture("forbidden-path.diff")
        self.assertFalse(done)
        self.assertEqual(checks["allowed_paths"]["status"], "fail")
        self.assertEqual(checks["router_sampling_untouched"]["status"], "fail")

    def test_non_applying_diff(self):
        done, checks = self.check_fixture("non-applying.diff")
        self.assertFalse(done)
        self.assertEqual(checks["apply_check"]["status"], "fail")

    def test_worktree_includes_staged_and_untracked_files(self):
        self.git("apply", str(FIXTURES / "good.diff"))
        path = self.checkout / "src/llama-context.cpp"
        path.write_text("int context = 2;\n")
        self.git("add", str(path))
        before = self.git("status", "--porcelain")
        done, checks = self.check_fixture()
        self.assertTrue(done, checks)
        self.assertEqual(checks["apply_check"]["status"], "pass")
        self.assertEqual(self.git("status", "--porcelain"), before)

    def test_default_on_is_rejected_through_native_packet(self):
        patch = self.root / "default-on.diff"
        patch.write_text((FIXTURES / "good.diff").read_text().replace(
            'value != nullptr && std::strcmp(value, "1") == 0',
            'value == nullptr || std::strcmp(value, "1") == 0',
        ))
        packet = {"capability": "verify", "inputs": {
            "checkout": str(self.checkout), "diff_path": str(patch),
        }}
        run = subprocess.run([sys.executable, str(CAPSULE / "run.py")], input=json.dumps(packet),
                             text=True, capture_output=True, check=True, env=os.environ.copy())
        result = json.loads(run.stdout)
        self.assertEqual(result["outcome"], "ok")
        self.assertFalse(result["outputs"]["done"])
        self.assertIn(("default_off_env_gate", "fail"), {
            (check["name"], check["status"]) for check in result["outputs"]["checks"]
        })


if __name__ == "__main__":
    unittest.main()
