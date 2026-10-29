import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import run_native_task as driver


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='nativetask-test-')).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.task = self.root / 'task.txt'
        self.task.write_text('Implement the requested transformation and report checks.', encoding='utf-8')
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        (self.inputs / 'sample.txt').write_text('example', encoding='utf-8')
        self.skill = self.root / 'ordinary-skill'
        self.skill.mkdir()
        (self.skill / 'SKILL.md').write_text('Inspect the task and verify your work.', encoding='utf-8')
        self.root_patch = patch.object(driver, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        # Every process and real ledger entry point is disabled in every test.
        self.popen = patch.object(driver.subprocess, 'Popen').start()
        self.run = patch.object(driver.subprocess, 'run').start()
        self.schedule = patch.object(driver, 'schedule_class').start()
        # The attempt record's product commit is a git call; give it a fixed value instead.
        patch.object(driver.roots, 'product_commit', return_value={'commit': 'test', 'dirty': False}).start()
        self.addCleanup(patch.stopall)
        self.output = io.StringIO()
        self.out = contextlib.redirect_stdout(self.output)
        self.err = contextlib.redirect_stderr(self.output)
        self.out.__enter__()
        self.err.__enter__()
        self.addCleanup(self.out.__exit__, None, None, None)
        self.addCleanup(self.err.__exit__, None, None, None)

    def argv(self, action='run', ident='attempt-1'):
        return [action, '--task-file', str(self.task), '--inputs-dir', str(self.inputs),
                '--ledger', str(self.root / 'ledger.sqlite3'), '--attempt-id', ident, '--out', str(self.root)]

    def plan(self, **overrides):
        args = driver.parser().parse_args(self.argv())
        for name, value in overrides.items():
            setattr(args, name, value)
        return driver.command_plan(args, 'attempt-1')

    def session(self):
        session = self.root / 'sessions/attempt-1'
        (session / 'native/broker').mkdir(parents=True)
        return session

    def test_plan_deterministic_and_pure(self):
        argv = self.argv('plan')
        self.assertEqual(driver.main(argv), 0)
        first = self.output.getvalue()
        self.output.seek(0)
        self.output.truncate()
        self.assertEqual(driver.main(argv), 0)
        self.assertEqual(first, self.output.getvalue())
        self.assertFalse((self.root / 'attempts').exists())
        self.popen.assert_not_called()
        self.run.assert_not_called()
        self.schedule.assert_not_called()

    def test_execute_required_and_fresh_ids(self):
        self.assertEqual(driver.main(self.argv()), 0)
        self.assertFalse((self.root / 'sessions').exists())
        with self.assertRaises(FileExistsError):
            driver.main(self.argv())
        self.popen.assert_not_called()
        self.run.assert_not_called()
        self.schedule.assert_not_called()
        with self.assertRaisesRegex(ValueError, '--execute'):
            driver.main(['_broker', '--session-id', 'attempt-1', '--binary', 'unused', '--out', str(self.root)])

    def test_model_skill_and_limits_propagate(self):
        plan = self.plan(model='gpt-6-luna', skill_dir=self.skill, wall_s=123, max_calls=7)
        spec = plan['spec']
        self.assertEqual(spec['model'], 'gpt-6-luna')
        self.assertEqual(spec['skill_dirs'], ['/campaign/skill'])
        self.assertEqual(spec['variant'], 'native-skills')
        self.assertEqual(spec['reasoning_effort'], 'medium')
        self.assertEqual(spec['wall_time_s'], 123)
        self.assertEqual(spec['max_model_calls'], 7)
        self.assertEqual(plan['ledger']['arm'], 'native-skills')
        self.assertEqual(spec['task'], self.task.read_text('utf-8'))

    def test_mounts_no_credentials_measurement_or_private_holdout(self):
        plan = self.plan(skill_dir=self.skill)
        argv = plan['worker']
        self.assertEqual(argv[argv.index('--network') + 1], 'none')
        mounts = [argv[i + 1] for i, value in enumerate(argv) if value == '--mount']
        self.assertTrue(any('target=/campaign/inputs,readonly' in m for m in mounts))
        self.assertTrue(any('target=/campaign/skill,readonly' in m for m in mounts))
        self.assertTrue(any(m.endswith('target=/campaign') for m in mounts))
        commands = json.dumps([plan['worker'], plan['broker']]).lower()
        for forbidden in ('credentials', 'api_key', 'token', 'auth.json', 'measurement', 'holdout', 'http:'):
            self.assertNotIn(forbidden, commands)
        self.assertIn('--execute', plan['broker'])

    def test_outside_ledger_and_unsafe_ids_refused(self):
        with self.assertRaisesRegex(ValueError, 'all writes'):
            self.plan(ledger=self.root.parent / 'outside.sqlite3')
        with self.assertRaises(ValueError):
            driver.identifier('../escape')

    def test_one_envelope_no_real_ledger(self):
        plan = self.plan(max_calls=9)
        session = self.session()
        ledger = self.schedule.return_value.return_value
        ledger.claim_envelope.return_value = 999
        driver.reserve(plan, session)
        ledger.reserve.assert_called_once()
        ledger.claim_envelope.assert_called_once_with('attempt-1', 'native', 'attempt-1-envelope',
                                                     9, model='gpt-6.1-sol', effort='medium')
        ledger.claim.assert_not_called()
        ledger.close.assert_called_once()

    def test_envelope_adapter_limits_identity_and_pending(self):
        session = self.session()
        driver.dump(session / 'envelope.json', dict(pair='attempt-1', arm='native',
            model='gpt-6.1-sol', call_bound=1, deadline=driver.time.time() + 100))
        calls = driver.EnvelopeCalls(session)
        with self.assertRaisesRegex(ValueError, 'identity'):
            calls.claim('attempt-1', 'native', 'a', model='gpt-6-luna', effort='medium')
        calls.claim('attempt-1', 'native', 'a', model='gpt-6.1-sol', effort='medium')
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            calls.claim('attempt-1', 'native', 'b', model='gpt-6.1-sol', effort='medium')
        calls.finish('a', 'completed', evidence='receipt', effective_model='gpt-6.1-sol', effective_effort='medium')
        with self.assertRaisesRegex(ValueError, 'budget'):
            calls.claim('attempt-1', 'native', 'b', model='gpt-6.1-sol', effort='medium')

    def test_collection_partial_and_recollection_no_stale_files(self):
        session = self.session()
        run = session / 'native/run'
        (run / 'project').mkdir(parents=True)
        (run / 'project/answer.py').write_text('pass', encoding='utf-8')
        driver.dump(run / 'result.json', dict(status='completed'))
        (run / 'events.jsonl').write_text(json.dumps(dict(payload=dict(event_type='chat.final', content='Done.'))) + '\n{', encoding='utf-8')
        driver.dump(session / 'native/broker/a.response.json', dict(request_id='a', usage={'input_tokens': 12}))
        receipt = driver.collect(session)
        self.assertEqual((session / 'final-message.txt').read_text('utf-8'), 'Done.')
        self.assertEqual(receipt['malformed_event_lines'], 1)
        self.assertEqual(json.loads((session / 'usage.json').read_text())[0]['usage'], {'input_tokens': 12})
        (run / 'project/answer.py').rename(run / 'project/renamed.py')
        driver.collect(session)
        self.assertFalse((session / 'project/answer.py').exists())
        self.assertTrue((session / 'project/renamed.py').exists())

    def test_broker_failure_still_collects_completed_native_outcome(self):
        session = self.session()
        (session / 'native/run').mkdir()
        driver.dump(session / 'native/run/result.json', dict(status='completed'))
        self.popen.return_value.wait.return_value = 2
        self.run.return_value.returncode = 0
        with patch.object(driver, 'reserve'), patch.object(driver, 'reconcile') as reconcile:
            self.assertEqual(driver.execute(self.plan(), session, str(self.task)), 1)
        self.assertEqual(json.loads((session / 'result.json').read_text())['status'], 'completed')
        self.assertIn('completion broker exited 2', self.output.getvalue())
        self.assertEqual(reconcile.call_args.args[2:], (2, 0))

    def test_worker_timeout_stops_exact_container_and_collects(self):
        session = self.session()
        self.popen.return_value.wait.return_value = 0
        self.run.side_effect = [subprocess.TimeoutExpired('docker', 1), Mock(returncode=0)]
        with patch.object(driver, 'reserve'), patch.object(driver, 'reconcile'):
            self.assertEqual(driver.execute(self.plan(), session, str(self.task)), 1)
        self.assertEqual(self.run.call_args_list[1].args[0],
                         ['docker', 'stop', '--time', '15', 'nativetask-attempt-1'])
        self.assertTrue((session / 'collection.json').exists())

    def test_unknown_keeps_envelope_charged(self):
        session = self.session()
        driver.reconcile(self.plan(), session, 2, 0)
        ledger = self.schedule.return_value.return_value
        self.assertEqual(ledger.finish_envelope.call_args.args[1], 'unknown')
        self.assertIsNone(ledger.finish_envelope.call_args.kwargs['actual_calls'])
        ledger.finish_pair.assert_not_called()

    def test_collect_dry_run_no_copy_or_dispatch(self):
        self.session()
        with patch.object(driver, 'collect') as collect:
            self.assertEqual(driver.main(['collect', '--session-id', 'attempt-1', '--attempt-id', 'collect-1', '--out', str(self.root)]), 0)
        collect.assert_not_called()
        self.run.assert_not_called()
        self.popen.assert_not_called()
        self.schedule.assert_not_called()

    def test_execute_stages_selected_spec_with_all_processes_mocked(self):
        self.schedule.return_value.return_value.claim_envelope.return_value = 999
        self.popen.return_value.wait.return_value = 0
        self.run.return_value.returncode = 0
        identity = dict(tag='ai4r:test', id='sha256:abc', repo_digests=['ai4r@sha256:def'])
        patch.object(driver, 'image_identity', return_value=identity).start()
        argv = self.argv() + ['--execute', '--binary', str(self.task), '--skill-dir', str(self.skill),
                              '--model', 'gpt-6-luna', '--max-calls', '3']
        self.assertEqual(driver.main(argv), 0)
        session = self.root / 'sessions/attempt-1'
        spec = json.loads((session / 'native/spec.json').read_text('utf-8'))
        self.assertEqual(spec['model'], 'gpt-6-luna')
        self.assertEqual(spec['skill_dirs'], ['/campaign/skill'])
        self.assertEqual(spec['max_model_calls'], 3)
        self.assertTrue((session / 'native/skill/SKILL.md').is_file())
        self.assertTrue((session / 'native/inputs/sample.txt').is_file())
        record = json.loads((self.root / 'attempts/attempt-1.json').read_text())
        self.assertEqual(record['status'], 'executed')
        self.assertEqual(record['image'], dict(identity, inspected=True))
        self.assertEqual(json.loads((session / 'staging-receipt.json').read_text())['image'], dict(identity, inspected=True))
        with self.assertRaises(FileExistsError):
            driver.main(argv)
        self.popen.assert_called_once()
        self.run.assert_called_once()

    def test_init_ledger_creates_only_under_out(self):
        self.assertEqual(driver.main(['init-ledger', '--out', str(self.root), '--max-calls', '9']), 0)
        create = self.schedule.return_value.create
        create.assert_called_once_with(self.root / 'ledger.sqlite3', max_calls=9, wall_s=10800)
        create.return_value.close.assert_called_once()

    def test_missing_codex_binary_fails_before_any_write(self):
        argv = self.argv() + ['--execute', '--binary', str(self.root / 'no-such-codex')]
        self.assertEqual(driver.main(argv), 1)
        self.assertIn('codex binary not found', self.output.getvalue())
        self.assertFalse((self.root / 'attempts').exists())
        self.assertFalse((self.root / 'sessions').exists())
        self.run.assert_not_called()
        self.popen.assert_not_called()
        self.schedule.assert_not_called()

    def test_missing_image_fails_before_any_write_with_rebuild_note(self):
        self.run.return_value = Mock(returncode=1, stdout='', stderr='No such image')
        argv = self.argv() + ['--execute', '--binary', str(self.task)]
        self.assertEqual(driver.main(argv), 1)
        self.assertIn('not present locally', self.output.getvalue())
        self.assertIn('Dockerfile.app', self.output.getvalue())
        self.assertFalse((self.root / 'attempts').exists())
        self.popen.assert_not_called()
        self.schedule.assert_not_called()

    def test_image_identity_parses_inspect_output(self):
        self.run.return_value = Mock(returncode=0, stdout='sha256:abc\t["ai4r@sha256:def"]\n', stderr='')
        self.assertEqual(driver.image_identity('ai4r:x'), dict(tag='ai4r:x', id='sha256:abc', repo_digests=['ai4r@sha256:def']))
        self.assertEqual(self.run.call_args.args[0][:4], ['docker', 'image', 'inspect', 'ai4r:x'])

    def test_usage_prefers_host_validated_responses(self):
        session = self.session()
        (session / 'host-responses').mkdir()
        driver.dump(session / 'native/broker/a.response.json', dict(request_id='a', usage={'input_tokens': 1}))
        driver.dump(session / 'host-responses/a.response.json', dict(request_id='a', usage={'input_tokens': 42}))
        receipt = driver.collect(session)
        self.assertEqual(receipt['usage_source'], 'host-responses')
        self.assertEqual(json.loads((session / 'usage.json').read_text())[0]['usage']['input_tokens'], 42)


if __name__ == '__main__':
    unittest.main()
