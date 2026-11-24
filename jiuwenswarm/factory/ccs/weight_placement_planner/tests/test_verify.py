import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from run import verify


CAPSULE = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name("fixtures")


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=CAPSULE, prefix=".verify-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.scratch = Path(self.temp.name)
        env = patch.dict("os.environ", {"TMPDIR": self.temp.name})
        env.start()
        self.addCleanup(env.stop)
        tempdir = patch.object(tempfile, "tempdir", self.temp.name)
        tempdir.start()
        self.addCleanup(tempdir.stop)
        self.root = self.scratch / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        for name, content in {
            "common/arg.cpp": "// stock arguments\n",
            "src/llama-sampler.cpp": "// stock sampling\n",
        }.items():
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(content)
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "fixture base")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def check(self, fixture=None, **inputs):
        if fixture:
            inputs["diff_path"] = str(FIXTURES / f"{fixture}.diff")
        result = verify({"checkout": str(self.root), **inputs})
        return result["done"], {item["name"]: item["status"] for item in result["checks"]}

    def altered(self, old, new):
        path = self.scratch / "variant.diff"
        path.write_text((FIXTURES / "good.diff").read_text().replace(old, new))
        return str(path)

    def test_verifier_rejects_marker_in_unset_branch(self):
        code = (FIXTURES / "gate-silence-positive.diff").read_text()
        branch = '+    if (!value) LLAMA_LOG_INFO("weight_placement_planner: unexpected");\n'
        code = code.replace("+}\n", branch + "+}\n")
        header, additions = code.split(" @@\n", 1)
        header = header.rsplit(",", 1)[0] + "," + str(len(additions.splitlines()))
        patch = self.scratch / "unset-branch.diff"
        patch.write_text(header + " @@\n" + additions)
        out = verify({"checkout": str(self.root), "diff_path": str(patch)})
        done, checks = out["done"], {row["name"]: row for row in out["checks"]}
        self.assertFalse(done, checks)
        check = checks["gate_unset_silence"]
        self.assertEqual(check["status"], "fail", checks)
        self.assertIn("recognized unset-", check["detail"])

    def test_gate_silence_fixtures(self):
        for kind, expected in (("positive", "pass"), ("negative", "inconclusive")):
            with self.subTest(kind=kind):
                fixture = f"gate-silence-{kind}.diff"
                out = verify({"checkout": str(self.root), "diff_path": str(FIXTURES / fixture)})
                done, checks = out["done"], {item["name"]: item for item in out["checks"]}
                self.assertTrue(done, checks)
                self.assertEqual(checks["gate_unset_silence"]["status"], expected, checks)
                if kind == "negative":
                    self.assertIn("No preceding local", checks["gate_unset_silence"]["detail"])


    def test_high_churn_signature_is_informational(self):
        target = self.root / "ggml/include/ggml-backend.h"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("bool fixture_copy(int expert,\n                  long bytes);\n")
        candidate = self.root / "candidate.diff"
        candidate.write_bytes((FIXTURES / "gate-silence-positive.diff").read_bytes()
                              + (FIXTURES / "high-churn-signature.diff").read_bytes())
        out = verify({"checkout": str(self.root), "diff_path": str(candidate)})
        checks = {item["name"]: item for item in out["checks"]}
        finding = checks["high_churn_signatures"]
        self.assertEqual(finding["status"], "info")
        self.assertIn("ggml/include/ggml-backend.h: fixture_copy", finding["detail"])
        self.assertFalse(out["done"])
        self.assertEqual(checks["allowed_paths"]["status"], "fail")

    def test_good(self):
        done, checks = self.check("good")
        self.assertTrue(done, checks)
        self.assertEqual(checks["git_apply_check"], "pass")
        expected = "pass" if shutil.which("g++") else "skipped"
        self.assertEqual(checks["new_cpp_syntax:src/llama-placement-plan.cpp"], expected)

    def test_missing_marker(self):
        done, checks = self.check("missing_marker")
        self.assertFalse(done, checks)
        self.assertEqual(checks["activation_marker:weight_placement_planner: stats"], "fail")

    def test_forbidden_file(self):
        done, checks = self.check("forbidden_file")
        self.assertFalse(done, checks)
        self.assertEqual(checks["allowed_paths"], "fail")
        self.assertEqual(checks["router_sampling_untouched"], "fail")

    def test_does_not_apply(self):
        done, checks = self.check("does_not_apply")
        self.assertFalse(done, checks)
        self.assertEqual(checks["git_apply_check"], "fail")

    def test_working_tree_combines_staged_and_untracked_changes(self):
        self.git("apply", str(FIXTURES / "good.diff"))
        self.git("add", "common/arg.cpp")
        before = self.git("status", "--porcelain").stdout
        done, checks = self.check()
        self.assertTrue(done, checks)
        self.assertEqual(self.git("status", "--porcelain").stdout, before)

    def test_commented_marker_and_extra_marker(self):
        diff = self.altered('+    LOG_INF("weight_placement_planner: stats");',
                            '+    /* LOG_INF("weight_placement_planner: stats"); */')
        done, checks = self.check(diff_path=diff, markers=["custom"])
        self.assertFalse(done, checks)
        self.assertEqual(checks["activation_marker:weight_placement_planner: stats"], "fail")
        self.assertEqual(checks["activation_marker:custom"], "fail")

    def test_default_on_guard_fails(self):
        diff = self.altered("gate &&", "!gate ||")
        done, checks = self.check(diff_path=diff)
        self.assertFalse(done, checks)
        self.assertEqual(checks["getenv_default_off"], "fail")

    @unittest.skipUnless(shutil.which("g++"), "requires g++")
    def test_syntax_error_fails(self):
        diff = self.altered("(void) message;", "invalid_identifier;")
        done, checks = self.check(diff_path=diff)
        self.assertFalse(done, checks)
        self.assertEqual(checks["new_cpp_syntax:src/llama-placement-plan.cpp"], "fail")

    @unittest.skipUnless(shutil.which("g++"), "requires g++")
    def test_missing_header_skips(self):
        diff = self.altered("#include <cstdlib>", "#include <generated-placement-example.h>")
        done, checks = self.check(diff_path=diff)
        self.assertTrue(done, checks)
        self.assertEqual(checks["new_cpp_syntax:src/llama-placement-plan.cpp"], "skipped")

    def test_native_packet(self):
        packet = {"capability": "verify", "inputs": {
            "checkout": str(self.root), "diff_path": str(FIXTURES / "good.diff"),
        }}
        result = subprocess.run(
            [sys.executable, str(CAPSULE / "run.py")], capture_output=True,
            text=True, input=json.dumps(packet), check=True,
        )
        response = json.loads(result.stdout)
        self.assertEqual(response["outcome"], "ok")
        self.assertTrue(response["outputs"]["done"], response)
