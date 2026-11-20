import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


CAPSULE = Path(__file__).resolve().parents[1]
FIXTURES = CAPSULE / 'tests' / 'fixtures'
sys.path.insert(0, str(CAPSULE))

import run


class VerifyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=CAPSULE / 'tests')
        self.addCleanup(tmp.cleanup)
        self.scratch = Path(tmp.name)
        self.checkout = self.scratch / 'checkout'
        self.checkout.mkdir()
        for path in ('src/llama-context.cpp', 'src/llama-sampling.cpp'):
            (self.checkout / path).parent.mkdir(exist_ok=True)
            (self.checkout / path).write_text('// stock\n')
        self.git('init', '-q', '--template=')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'Fixture preimage')

    def git(self, *args):
        return run.checked(run.git(self.checkout, *args))

    def verify(self, fixture=None, **kwargs):
        inputs = {'checkout': str(self.checkout), **kwargs}
        if fixture is not None:
            inputs['diff_path'] = str(FIXTURES / fixture)
        return run.verify(inputs, self.scratch)

    def check(self, verdict, name):
        return {check['name']: check for check in verdict['checks']}[name]

    def test_verifier_rejects_marker_in_unset_branch(self):
        code = (FIXTURES / "gate-silence-positive.diff").read_text()
        branch = '+    if (!value) {\n+        LLAMA_LOG_INFO("runtime_event_recorder: unexpected");\n+        return;\n+    }\n'
        code = code.replace("+    if (!value) return;\n", branch)
        header, additions = code.split(" @@\n", 1)
        header = header.rsplit(",", 1)[0] + "," + str(len(additions.splitlines()))
        patch = self.scratch / "unset-branch.diff"
        patch.write_text(header + " @@\n" + additions)
        out = self.verify(str(patch))
        done, checks = out["done"], {row["name"]: row for row in out["checks"]}
        self.assertFalse(done, checks)
        check = checks["gate_unset_silence"]
        self.assertEqual(check["status"], "fail", checks)
        self.assertIn("recognized unset-", check["detail"])

    def test_gate_silence_fixtures(self):
        for kind, expected in (("positive", "pass"), ("negative", "inconclusive")):
            with self.subTest(kind=kind):
                fixture = f"gate-silence-{kind}.diff"
                out = self.verify(fixture)
                done, checks = out["done"], {item["name"]: item for item in out["checks"]}
                self.assertTrue(done, checks)
                self.assertEqual(checks["gate_unset_silence"]["status"], expected, checks)
                if kind == "negative":
                    self.assertIn("No preceding local", checks["gate_unset_silence"]["detail"])


    def test_high_churn_signature_is_informational(self):
        target = self.checkout / "src/llama-moe-cache.cpp"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("bool fixture_copy(int expert,\n                  long bytes);\n")
        candidate = self.checkout / "candidate.diff"
        candidate.write_bytes((FIXTURES / "gate-silence-positive.diff").read_bytes()
                              + (FIXTURES / "high-churn-signature.diff").read_bytes())
        out = self.verify(str(candidate))
        checks = {item["name"]: item for item in out["checks"]}
        finding = checks["high_churn_signatures"]
        self.assertEqual(finding["status"], "info")
        self.assertIn("src/llama-moe-cache.cpp: fixture_copy", finding["detail"])
        self.assertTrue(out["done"], checks)

    def test_good_patch_preserves_checkout(self):
        verdict = self.verify('good.diff')
        self.assertTrue(verdict['done'], verdict)
        self.assertEqual(self.git('status', '--porcelain'), b'')
        syntax = self.check(verdict, 'syntax:src/llama-event-recorder.cpp') if shutil.which('g++') else self.check(verdict, 'syntax')
        self.assertEqual(syntax['stage'], 'compile')
        self.assertEqual(syntax['status'], 'pass' if shutil.which('g++') else 'skipped')

    def test_missing_marker(self):
        verdict = self.verify('missing-marker.diff')
        self.assertFalse(verdict['done'])
        check = self.check(verdict, 'activation_markers')
        self.assertEqual(check['status'], 'fail')
        self.assertIn('inactive (', check['detail'])

    def test_forbidden_path(self):
        verdict = self.verify('forbidden-path.diff')
        self.assertFalse(verdict['done'])
        self.assertEqual(self.check(verdict, 'git_apply_check')['status'], 'pass')
        for name in ('allowed_paths', 'router_and_sampling_paths'):
            self.assertEqual(self.check(verdict, name)['status'], 'fail')

    def test_patch_does_not_apply(self):
        verdict = self.verify('does-not-apply.diff')
        self.assertFalse(verdict['done'])
        self.assertEqual(self.check(verdict, 'git_apply_check')['status'], 'fail')

    def test_worktree_includes_staged_and_untracked_files(self):
        patch = FIXTURES / 'good.diff'
        self.git('apply', str(patch))
        (self.checkout / 'src/llama-context.cpp').write_text('// integration hook\n')
        self.git('add', 'src/llama-context.cpp')
        before = self.git('status', '--porcelain')
        verdict = self.verify()
        self.assertTrue(verdict['done'], verdict)
        self.assertEqual(self.git('status', '--porcelain'), before)

    def test_comment_cannot_supply_gate_or_info_marker(self):
        self.git('apply', str(FIXTURES / 'good.diff'))
        unit = self.checkout / 'src/llama-event-recorder.cpp'
        stats_call = f'LLAMA_LOG_INFO("{run.MARKERS[2]}'
        unit.write_text(unit.read_text()
                        .replace('if (!path) return;', '// if (!path) return;')
                        .replace(stats_call, '// ' + stats_call))
        verdict = self.verify()
        self.assertFalse(verdict['done'])
        for name in ('env_default_off', 'activation_markers'):
            self.assertEqual(self.check(verdict, name)['status'], 'fail')

    def test_existing_gate_can_remain_in_an_unchanged_header(self):
        header = self.checkout / 'src/llama-event-recorder.h'
        header.write_text('#include <cstdlib>\n'
                          'inline const char * configured_path() {\n'
                          '    auto path = std::getenv("LLAMA_EVENT_REC");\n'
                          '    if (!path) return nullptr;\n'
                          '    return path;\n'
                          '}\n')
        original = (FIXTURES / 'good.diff').read_text()
        patch = self.scratch / 'existing-gate.diff'
        patch.write_text(original.replace(
            '+    const char * path = std::getenv("LLAMA_EVENT_REC");',
            '+    const char * path = "fixture";',
        ).replace('+#include <cstdlib>', '+#include "llama-event-recorder.h"'))
        verdict = run.verify({'checkout': str(self.checkout), 'diff_path': str(patch)}, self.scratch)
        self.assertTrue(verdict['done'], verdict)

    @unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
    def test_syntax_failure_makes_done_false(self):
        self.git('apply', str(FIXTURES / 'good.diff'))
        unit = self.checkout / 'src/llama-event-recorder.cpp'
        unit.write_text(unit.read_text() + 'int broken = ;\n')
        verdict = self.verify()
        self.assertFalse(verdict['done'])
        self.assertEqual(self.check(verdict, 'syntax:src/llama-event-recorder.cpp')['status'], 'fail')

    def test_native_packet(self):
        packet = {
            'capability': 'verify',
            'inputs': {'checkout': str(self.checkout), 'diff_path': str(FIXTURES / 'good.diff'),
                       'env_gate': run.ENV_GATE, 'markers': list(run.MARKERS)},
            'output_dir': str(self.scratch),
        }
        process = subprocess.run(
            [sys.executable, str(CAPSULE / 'run.py')], input=json.dumps(packet),
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
            capture_output=True, text=True, check=True,
        )
        output = json.loads(process.stdout)
        self.assertEqual(output['outcome'], 'ok')
        self.assertTrue(output['outputs']['done'], output)
