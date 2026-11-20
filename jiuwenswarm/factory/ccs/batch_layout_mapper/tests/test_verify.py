import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


CAPSULE = Path(__file__).resolve().parents[1]
FIXTURES = CAPSULE / "tests" / "fixtures"


class VerifyTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(dir=CAPSULE / "tests")
        self.addCleanup(temp.cleanup)
        self.checkout = Path(temp.name)
        for name, contents in (
            ("tools/server/server-context.cpp", "// stock server\n"),
            ("common/sampling.cpp", "// stock sampling\n"),
        ):
            path = self.checkout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        self.git("init")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-m", "Stock fixture")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.checkout), *args], capture_output=True, check=True,
        )

    def invoke(self, fixture=None, *, patch=None, **inputs):
        if fixture:
            inputs["diff_path"] = str(FIXTURES / fixture)
        if patch:
            inputs["diff_path"] = str(patch)
        result = subprocess.run(
            [sys.executable, "-B", str(CAPSULE / "run.py")],
            input=json.dumps({
                "capability": "verify",
                "inputs": {"checkout": str(self.checkout), **inputs},
            }),
            capture_output=True, text=True, check=True,
            env={**os.environ, "TMPDIR": str(self.checkout)},
        )
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["outcome"], "ok")
        output = envelope["outputs"]
        return output["done"], {row["name"]: row for row in output["checks"]}

    def test_verifier_rejects_marker_in_unset_branch(self):
        code = (FIXTURES / "gate-silence-positive.diff").read_text()
        branch = '+    if (!value) {\n+        LLAMA_LOG_INFO("batch_layout_mapper: unexpected");\n+        return;\n+    }\n'
        code = code.replace("+    if (!value) return;\n", branch)
        header, additions = code.split(" @@\n", 1)
        header = header.rsplit(",", 1)[0] + "," + str(len(additions.splitlines()))
        patch = self.checkout / "unset-branch.diff"
        patch.write_text(header + " @@\n" + additions)
        done, checks = self.invoke(patch=patch)
        self.assertFalse(done, checks)
        check = checks["gate_unset_silence"]
        self.assertEqual(check["status"], "fail", checks)
        self.assertIn("recognized unset-", check["detail"])

    def test_gate_silence_fixtures(self):
        for kind, expected in (("positive", "pass"), ("negative", "inconclusive")):
            with self.subTest(kind=kind):
                fixture = f"gate-silence-{kind}.diff"
                done, checks = self.invoke(fixture)
                done, checks = done, checks
                self.assertTrue(done, checks)
                self.assertEqual(checks["gate_unset_silence"]["status"], expected, checks)
                if kind == "negative":
                    self.assertIn("No preceding local", checks["gate_unset_silence"]["detail"])

    def test_good_diff(self):
        done, checks = self.invoke("good.diff")
        self.assertTrue(done, checks)
        self.assertEqual(checks["apply_check"]["stage"], "native CC execution")
        self.assertEqual(checks["activation_markers"]["status"], "pass")
        if shutil.which("g++"):
            self.assertEqual(checks["new_file_syntax:src/llama-batch-layout.h"]["status"], "pass")
        else:
            self.assertEqual(checks["new_file_syntax"]["status"], "skipped")

    def test_missing_marker(self):
        done, checks = self.invoke("missing-marker.diff")
        self.assertFalse(done)
        self.assertEqual(checks["apply_check"]["status"], "pass")
        self.assertEqual(checks["activation_markers"]["status"], "fail")

    def test_forbidden_file(self):
        done, checks = self.invoke("forbidden.diff")
        self.assertFalse(done)
        for name in ("allowed_paths", "router_and_sampling"):
            self.assertEqual(checks[name]["status"], "fail")

    def test_diff_does_not_apply(self):
        done, checks = self.invoke("does-not-apply.diff")
        self.assertFalse(done)
        self.assertEqual(checks["apply_check"]["status"], "fail")

    def test_worktree_with_untracked_helper(self):
        self.git("apply", str(FIXTURES / "good.diff"))
        self.git("add", "tools/server/server-context.cpp")
        done, checks = self.invoke()
        self.assertTrue(done, checks)
        self.assertEqual(checks["apply_check"]["status"], "pass")

    def test_default_on_fails(self):
        patch = self.checkout / "unsafe.diff"
        patch.write_text((FIXTURES / "good.diff").read_text().replace(
            'value != nullptr && std::strcmp(value, "1") == 0', "value == nullptr",
        ))
        done, checks = self.invoke(patch=patch)
        self.assertFalse(done)
        self.assertEqual(checks["default_off_getenv"]["status"], "fail")

    @unittest.skipUnless(shutil.which("g++"), "g++ unavailable")
    def test_syntax_failure(self):
        patch = self.checkout / "bad-syntax.diff"
        patch.write_text((FIXTURES / "good.diff").read_text().replace("inline bool", "inline unknown_type"))
        done, checks = self.invoke(patch=patch)
        self.assertFalse(done)
        self.assertEqual(checks["new_file_syntax:src/llama-batch-layout.h"]["status"], "fail")
