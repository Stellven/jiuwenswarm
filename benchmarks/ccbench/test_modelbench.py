import sys
sys.dont_write_bytecode = True
import json
import tempfile
import unittest
from pathlib import Path

import modelbench as mb


class ModelBenchTests(unittest.TestCase):
    def test_parse_tokens(self):
        self.assertEqual(mb.parse_tokens('x\ntokens used\n12,345\nbye'), 12345)
        self.assertEqual(mb.parse_tokens('tokens used: 7\n...\ntokens used: 9'), 9)
        self.assertIsNone(mb.parse_tokens('nothing'))
        self.assertIsNone(mb.parse_tokens(None))

    def test_manifest_round_trip_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'a.json').write_bytes(b'{"x":1}\n')
            mb.write_manifest(d, ['a.json'])
            self.assertEqual(mb.verify_manifest(d), [])
            (d / 'a.json').write_bytes(b'{"x":2}\n')
            self.assertIn('differs', mb.verify_manifest(d)[0])
            (d / 'MANIFEST.sha256').unlink()
            self.assertIn('missing', mb.verify_manifest(d)[0])

    def test_call_codex_records_prompt_reply_tokens_and_wall(self):
        def invoke(command, prompt, timeout):
            self.assertEqual(command[1:3], ['exec', '--skip-git-repo-check'])
            self.assertEqual(command[command.index('-s') + 1], 'read-only')
            self.assertIn('--ephemeral', command)
            self.assertEqual(command[-1], '-')
            Path(command[command.index('-o') + 1]).write_bytes('hello'.encode('utf-8'))
            return dict(elapsed_s=2.0, returncode=0, timed_out=False, stdout_tail='', stderr_tail='', tokens=42)
        with tempfile.TemporaryDirectory() as d:
            res = mb.call_codex('PROMPT', Path(d) / 'c1', cli='codex', invoke=invoke, meta=dict(case='x'))
            self.assertEqual((res['reply'], res['tokens'], res['elapsed_s'], res['ok']), ('hello', 42, 2.0, True))
            run = json.loads((Path(d) / 'c1' / 'run.json').read_text('utf-8'))
            self.assertEqual(run['case'], 'x')
            self.assertEqual(run['prompt_chars'], 6)
            self.assertEqual((Path(d) / 'c1' / 'prompt.txt').read_text('utf-8'), 'PROMPT')
            self.assertEqual([p.name for p in (Path(d) / 'c1').iterdir() if p.name.startswith('empty-')], [])
            with self.assertRaises(FileExistsError):
                mb.call_codex('P', Path(d) / 'c1', cli='codex', invoke=invoke)

    def test_call_codex_failure_is_recorded_not_raised(self):
        def invoke(command, prompt, timeout):
            raise OSError('boom')
        with tempfile.TemporaryDirectory() as d:
            res = mb.call_codex('P', Path(d) / 'c', cli='codex', invoke=invoke)
            self.assertFalse(res['ok'])
            self.assertEqual(res['reply'], '')

    def test_cost_and_rotation_and_blocks(self):
        self.assertEqual(mb.call_cost([dict(tokens=5, elapsed_s=1.0), dict(tokens=None, elapsed_s=2.0)]),
                         dict(calls=2, tokens=5, calls_without_token_count=1, wall_s=3.0))
        self.assertEqual(mb.call_cost([dict(tokens=None, elapsed_s=1)])['tokens'], None)
        self.assertEqual(mb.rotate(['a', 'b', 'c'], 1), ['a', 'b', 'c'])
        self.assertEqual(mb.rotate(['a', 'b', 'c'], 2), ['b', 'c', 'a'])
        text = 'x\n```python\nA\n```\ny\n```json\n{}\n```\n'
        self.assertEqual(mb.extract_blocks(text, 'python'), ['A\n'])
        self.assertEqual(len(mb.extract_blocks(text)), 2)


if __name__ == '__main__':
    unittest.main()
