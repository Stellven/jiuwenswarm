import json
from copy import deepcopy
from pathlib import Path
import tempfile
import os
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

import yaml
from jiuwenswarm.ccv2.ccv2 import CCError, Host, load, normalize, resolve_request, snapshot
from jiuwenswarm.ccv2.mcp_server import tool_schema, invoke_tool


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        self.decl = {'cc': '2', 'id': 'test.example', 'version': '1.0.0',
                     'bindings': {'default': {'kind': 'native', 'command': ['{python}', '{bundle}/tool.py']}},
                     'capabilities': {'echo': {'does': 'Echo JSON', 'takes': {'value': 'json'}, 'gives': {'value': 'json'}}}}
        (self.bundle / 'tool.py').write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'outcome':'ok','outputs':{'value':p['inputs']['value']}}))\n")
        self.host = Host(self.root / 'store')

    def tearDown(self):
        self.temp.cleanup()

    def seal(self):
        (self.bundle / 'cc.yaml').write_text(yaml.safe_dump(self.decl))
        return self.host.seal(self.bundle)

    def test_broad_json_and_duplicate_conflict(self):
        release = self.seal()
        value = {'never_declared_before': [1, True, None, {'more': 'fields'}]}
        first = self.host.call(release, 'echo', {'value': value}, key='repeat')
        self.assertEqual(first['outputs']['value'], value)
        self.assertEqual(first['state'], 'succeeded')
        self.assertEqual(first, self.host.call(release, 'echo', {'value': value}, key='repeat'))
        with self.assertRaises(CCError):
            self.host.call(release, 'echo', {'value': 2}, key='repeat')

    def test_invalid_input_and_missing_output(self):
        release = self.seal()
        self.assertEqual(self.host.call(release, 'echo', {})['reason'], 'INVALID_INPUT')
        (self.bundle / 'tool.py').write_text("print('{\"outcome\":\"ok\",\"outputs\":{}}')")
        result = self.host.call(self.seal(), 'echo', {'value': 0})
        self.assertEqual(result['reason'], 'INVALID_OUTPUT')

    def test_empty_and_partial_are_distinct(self):
        self.decl['capabilities']['echo']['gives'] = {}
        (self.bundle / 'tool.py').write_text("print('{\"outcome\":\"ok\",\"outputs\":{}}')")
        result = self.host.call(self.seal(), 'echo', {'value': 0})
        self.assertEqual((result['state'], result['completeness']), ('succeeded', 'complete'))
        (self.bundle / 'tool.py').write_text("print('{\"outcome\":\"partial\",\"reason\":\"capture interrupted\",\"outputs\":{}}')")
        result = self.host.call(self.seal(), 'echo', {'value': 0})
        self.assertEqual((result['state'], result['completeness']), ('succeeded', 'partial'))
        self.assertEqual(result['diagnostics'][0]['message'], 'capture interrupted')

    def test_schema_optional_but_observed_if_supplied(self):
        self.decl['capabilities']['echo']['takes']['value'] = {'kind': 'json', 'schema': {'type': 'integer'}}
        result = self.host.call(self.seal(), 'echo', {'value': 'wrong'})
        self.assertEqual(result['reason'], 'INVALID_INPUT')

    def test_sealed_source_is_immutable(self):
        release = self.seal()
        (self.bundle / 'tool.py').write_text('raise Exception("edited source")')
        self.assertEqual(self.host.call(release, 'echo', {'value': 1})['state'], 'succeeded')
        sealed = self.host.store / 'releases' / release / 'bundle' / 'tool.py'
        sealed.write_text('raise Exception("tamper")')
        self.assertEqual(self.host.call(release, 'echo', {'value': 1})['reason'], 'DIGEST_MISMATCH')

    def test_artifact_staleness_and_output_traversal(self):
        file = self.root / 'input.txt'; file.write_text('first')
        ref = self.host.put_artifact(file)
        self.decl['capabilities']['echo']['takes']['value'] = 'artifact'
        Path(self.host.artifact_path(ref)).write_text('stale')
        self.assertEqual(self.host.call(self.seal(), 'echo', {'value': ref})['reason'], 'DIGEST_MISMATCH')
        self.decl['capabilities']['echo']['takes']['value'] = 'json'
        self.decl['capabilities']['echo']['gives']['value'] = 'artifact'
        (self.bundle / 'tool.py').write_text("print('{\"outcome\":\"ok\",\"outputs\":{\"value\":{\"path\":\"../../escape\"}}}')")
        self.assertEqual(self.host.call(self.seal(), 'echo', {'value': 1})['reason'], 'INVALID_PATH')

    def test_independent_negative_assessment(self):
        self.decl['capabilities']['echo']['guarantees'] = ['coverage.target']
        release = self.seal()
        self.assertEqual(self.host.call(release, 'echo', {'value': 1}, checks=['coverage.target'], require_checks=True)['reason'], 'CHECKER_UNAVAILABLE')
        self.host.checkers['coverage.target'] = lambda receipt, packet: 'FAIL'
        result = self.host.call(release, 'echo', {'value': 1}, checks=['coverage.target'])
        self.assertEqual((result['state'], result['assessment']['verdict']), ('succeeded', 'failed'))
        self.assertTrue(result['assessment']['checks'][0]['checker']['code_sha256'])

    def test_selected_capability_permissions(self):
        self.decl['capabilities']['inspect'] = {'does': 'Read-only action', 'gives': {}}
        self.decl['capabilities']['echo']['changes'] = ['workspace.write']
        release = self.seal()
        self.assertEqual(self.host.call(release, 'echo', {'value': 1})['reason'], 'DENIED')
        self.assertEqual(self.host.call(release, 'inspect', {}, grants=['workspace.write'])['reason'], 'UNDECLARED_EFFECT')

    def test_native_agent_edits_are_observed(self):
        workspace = self.root / 'workspace'; workspace.mkdir()
        (workspace / 'existing.txt').write_text('dirty content')
        self.host.resources['work'] = {'kind': 'workspace', 'path': str(workspace)}
        self.decl['bindings']['default'] = {'kind': 'delegate', 'agent': 'coder'}
        cap = self.decl['capabilities']['echo']
        cap.update(takes={'workspace': 'handle'}, gives={'value': 'json'}, needs=['workspace'], changes=['workspace.read', 'workspace.write'])

        def delegate(packet, context):
            (workspace / 'new.bin').write_bytes(b'\x00\xff')
            return {'outcome': 'ok', 'outputs': {'value': {'tests_run': False}}}
        self.host.delegates['coder'] = delegate
        result = self.host.call(self.seal(), 'echo', {'workspace': 'work'}, grants=cap['changes'])
        self.assertEqual(result['state'], 'succeeded')
        self.assertTrue(result['provenance']['delegate']['code_sha256'])
        self.assertEqual(result['effects']['observed'][0]['changes'][0]['path'], 'new.bin')
        self.assertEqual((workspace / 'existing.txt').read_text(), 'dirty content')

    def test_request_resolution(self):
        desired = dict(self.decl); desired.pop('bindings')
        req = {'format': 'cc-request/2', 'id': 'test.request', 'desired': desired,
               'open': {'/bindings': {'owner': 'implementer', 'question': 'Provide implementation'}}}
        resolved = resolve_request(req, {'/bindings': self.decl['bindings']})
        self.assertEqual(resolved['id'], self.decl['id'])
        req['open']['/id'] = {'owner': 'implementer', 'question': 'Overwrite?'}
        with self.assertRaises(CCError):
            resolve_request(req, {'/bindings': self.decl['bindings'], '/id': 'changed'})
    def test_duplicate_unsupported_and_unresolved(self):
        path = self.bundle / 'bad.yaml'; path.write_text("cc: '2'\nid: one\nid: two")
        with self.assertRaises(CCError): load(path)
        for field, value in [('bindings', {'default': {'kind': 'unknown'}}), ('cc', '1')]:
            raw = dict(self.decl); raw[field] = value
            with self.assertRaises(CCError): normalize(raw)
        self.decl['capabilities']['echo']['takes']['value'] = '$missing'
        with self.assertRaises(CCError): self.seal()

    def test_boolean_schema_discovery(self):
        for value in (True, False):
            cap = {'takes': {'data': {'kind': 'json', 'schema': value}}}
            self.assertIn('data', tool_schema(cap, {})['properties'])

    def test_external_script_and_missing_entrypoint_rejected(self):
        outside = self.root / 'outside.py'; outside.write_text('print(1)')
        self.decl['bindings']['default']['command'][1] = str(outside)
        with self.assertRaises(CCError) as e: self.seal()
        self.assertEqual(e.exception.code, 'UNSEALED_IMPLEMENTATION')
        self.decl['bindings']['default']['command'][1] = '{bundle}/missing.py'
        with self.assertRaises(CCError) as e: self.seal()
        self.assertEqual(e.exception.code, 'MISSING_IMPLEMENTATION')

    def agent_workspace(self):
        workspace = self.root / 'workspace'; workspace.mkdir(exist_ok=True)
        self.host.resources['work'] = {'kind': 'workspace', 'path': str(workspace)}
        self.decl['bindings']['default'] = {'kind': 'delegate', 'agent': 'coder'}
        self.decl['capabilities']['echo'].update(takes={'workspace': 'handle'}, needs=['workspace'], changes=['workspace.read', 'workspace.write'])
        return workspace

    def test_overlapping_workspace_calls_serialize(self):
        workspace = self.agent_workspace(); (workspace / 'src').mkdir()
        started, finish = threading.Event(), threading.Event()
        def delegate(packet, context):
            started.set(); finish.wait(5)
            return {'outcome': 'ok', 'outputs': {'value': 1}}
        self.host.delegates['coder'] = delegate
        release = self.seal()
        grants = ['workspace.read', 'workspace.write']
        thread = threading.Thread(target=lambda: self.host.call(release, 'echo', {'workspace': 'work'}, grants=grants))
        thread.start(); self.assertTrue(started.wait(5))
        other = Host(self.host.store, resources={'child': {'kind': 'workspace', 'path': str(workspace / 'src')}}, delegates={'coder': delegate})
        second = other.call(release, 'echo', {'workspace': 'child'}, grants=grants)
        self.assertEqual(second['reason'], 'RESOURCE_BUSY')
        finish.set(); thread.join(5); self.assertFalse(thread.is_alive())

    def test_observation_failure_persists_unknown_and_reconciles(self):
        workspace = self.agent_workspace()
        self.host.delegates['coder'] = lambda packet, context: {'outcome': 'ok', 'outputs': {'value': 1}}
        release = self.seal()
        before = snapshot(workspace)
        with patch('jiuwenswarm.ccv2.ccv2.snapshot', side_effect=[before, PermissionError('exclusive lock')]):
            result = self.host.call(release, 'echo', {'workspace': 'work'}, grants=['workspace.read', 'workspace.write'], key='locked')
        self.assertEqual(self.host.status('locked')['state'], 'unknown')
        self.assertEqual(result['reason'], 'EFFECT_UNKNOWN')
        resolved = self.host.reconcile('locked', stopped=True, note='Native session stopped; workspace inspected manually')
        self.assertEqual(resolved['reason'], 'RECONCILED_STOP')
        self.assertTrue((Path(result['provenance']['attempt_dir']) / 'receipt.json').is_file())
        self.assertEqual(json.loads((Path(result['provenance']['attempt_dir']) / 'receipt.json').read_text())['state'], 'unknown')

    def test_model_effect_does_not_grant_image_network(self):
        self.decl['bindings']['default'] = {'kind': 'image', 'image': 'sha256:' + 'b'*64, 'command': ['python', '{bundle}/tool.py']}
        self.decl['capabilities']['echo']['changes'] = ['model.invoke']
        release = self.seal()
        class Process:
            returncode=0; stdout=b'{"outcome":"ok","outputs":{"value":1}}'; stderr=b''
        with patch('jiuwenswarm.ccv2.ccv2.subprocess.run', return_value=Process()) as run:
            receipt = self.host.call(release, 'echo', {'value': 1}, grants=['model.invoke'])
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('--network')+1], 'none')
        self.assertEqual(receipt['state'], 'succeeded')

    def test_host_key_is_not_model_argument(self):
        import asyncio
        class Client:
            async def call_tool(self, name, arguments):
                return name, arguments
        name, args = asyncio.run(invoke_tool(Client(), 'echo', {'value': 2}, 'host.id'))
        self.assertEqual(args['_cc_key'], 'host.id')
        with self.assertRaises(CCError):
            asyncio.run(invoke_tool(Client(), 'echo', {'_cc_key': 'forged', 'value': 2}, 'host.id'))

    def test_dispatch_uses_pinned_executable_not_current_path(self):
        import shutil
        self.decl['bindings']['default']['command'][0] = 'python'
        expected = str(Path(shutil.which('python')).resolve())
        release = self.seal()
        class Process:
            returncode=0; stdout=b'{"outcome":"ok","outputs":{"value":1}}'; stderr=b''
        with patch('jiuwenswarm.ccv2.ccv2.subprocess.run', return_value=Process()) as run:
            self.host.call(release, 'echo', {'value': 1})
        self.assertEqual(run.call_args.args[0][0], expected)

    def test_reconciliation_wins_late_buffered_result(self):
        self.agent_workspace()
        stopped, deliver = threading.Event(), threading.Event()
        def delegate(packet, context):
            stopped.set(); deliver.wait(5)
            return {'outcome': 'ok', 'outputs': {'value': 1}}
        self.host.delegates['coder'] = delegate
        release = self.seal(); results = []
        thread = threading.Thread(target=lambda: results.append(self.host.call(release, 'echo', {'workspace': 'work'}, key='buffered', grants=['workspace.read', 'workspace.write'])))
        thread.start(); self.assertTrue(stopped.wait(5))
        self.host.reconcile('buffered', stopped=True, note='Execution owner stopped; reply buffered')
        deliver.set(); thread.join(5)
        self.assertFalse(thread.is_alive())
        final = self.host.status('buffered')
        self.assertEqual(final['reason'], 'RECONCILED_STOP')
        self.assertEqual(final['state'], 'failed')
        self.assertEqual(len(final['reconciliations']), 1)
        self.assertEqual(len(final['late_observations']), 1)
        self.assertEqual(results[0], final)

    def test_nonfinite_json_has_a_protocol_diagnostic(self):
        release = self.seal()
        with self.assertRaises(CCError) as e:
            self.host.call(release, 'echo', {'value': float('nan')})
        self.assertEqual(e.exception.code, 'INVALID_INPUT')

    def test_advertised_guarantees_do_not_run_or_require_checkers(self):
        self.decl['capabilities']['echo']['guarantees'] = ['missing', 'expensive']
        callback = unittest.mock.Mock(side_effect=AssertionError('No automatic verifier'))
        self.host.checkers['expensive'] = callback
        result = self.host.call(self.seal(), 'echo', {'value': {'new': {'nested': ['anything', 2]}}})
        self.assertEqual(result['state'], 'succeeded')
        self.assertEqual(result['assessment'], {'verdict': 'not_requested', 'checks': []})
        callback.assert_not_called()

    def test_advisory_missing_crashing_and_invalid_checkers_preserve_result(self):
        self.host.checkers['crashes'] = lambda receipt, packet: 1 / 0
        self.host.checkers['invalid'] = lambda receipt, packet: 'looks okay'
        def exits(receipt, packet):
            raise SystemExit(7)
        self.host.checkers['exits'] = exits
        result = self.host.call(self.seal(), 'echo', {'value': 7}, checks=['missing', 'crashes', 'invalid', 'exits'])
        self.assertEqual((result['state'], result['outputs']['value']), ('succeeded', 7))
        self.assertEqual(result['assessment']['verdict'], 'inconclusive')
        self.assertEqual(len(result['assessment']['checks']), 4)
        self.assertEqual({d['code'] for d in result['diagnostics']}, {'CHECKER_ERROR', 'CHECKER_UNAVAILABLE'})

    def test_required_failure_retains_execution_success(self):
        self.host.checkers['reject'] = lambda receipt, packet: 'FAIL'
        result = self.host.call(self.seal(), 'echo', {'value': 8}, checks=['reject'], require_checks=True)
        self.assertEqual((result['state'], result['assessment']['verdict']), ('succeeded', 'failed'))
        self.assertEqual(result['outputs']['value'], 8)
        self.assertTrue(result['provenance']['verification']['required'])

    def test_required_missing_checker_does_not_dispatch(self):
        self.host.checkers['absent'] = None
        result = self.host.call(self.seal(), 'echo', {'value': 1}, checks=['absent'], require_checks=True)
        self.assertEqual((result['state'], result['reason']), ('blocked', 'CHECKER_UNAVAILABLE'))
        self.assertEqual(result['assessment']['verdict'], 'not_run')
        self.assertFalse((Path(result['provenance']['attempt_dir']) / 'stdout.log').exists())

    def test_check_policy_is_part_of_invocation_identity(self):
        release = self.seal()
        self.host.call(release, 'echo', {'value': 1}, key='policy')
        with self.assertRaises(CCError) as e:
            self.host.call(release, 'echo', {'value': 1}, key='policy', checks=['core.complete'])
        self.assertEqual(e.exception.code, 'KEY_CONFLICT')
        self.host.call(release, 'echo', {'value': 1}, key='policy2', checks=['core.complete'])
        with self.assertRaises(CCError):
            self.host.call(release, 'echo', {'value': 1}, key='policy2', checks=['core.complete'], require_checks=True)

    def test_session_authorization_is_inherited_only_by_selected_capability(self):
        self.decl['capabilities']['echo']['changes'] = ['workspace.write']
        self.decl['capabilities']['inspect'] = deepcopy(dict(self.decl['capabilities']['echo'], changes=[]))
        host = Host(self.host.store, session_grants=['workspace.write', 'network.request'])
        release = self.seal()
        edited = host.call(release, 'echo', {'value': 1})
        inspected = host.call(release, 'inspect', {'value': 1})
        self.assertEqual(edited['effects']['granted'], ['workspace.write'])
        self.assertEqual((inspected['state'], inspected['effects']['granted']), ('succeeded', []))
        self.assertEqual(host.call(release, 'echo', {'value': 1}, grants=[])['reason'], 'DENIED')
        limited = Host(self.host.store, session_grants=[])
        self.assertEqual(limited.call(release, 'echo', {'value': 1}, grants=['workspace.write'])['reason'], 'DENIED')

    def test_run_automatically_seals_current_source(self):
        self.seal()
        first = self.host.run(self.bundle, 'echo', {'value': 1})
        (self.bundle / 'tool.py').write_text("print('{\"outcome\":\"ok\",\"outputs\":{\"value\":2}}')")
        second = self.host.run(self.bundle, 'echo', {'value': 1})
        self.assertEqual((first['outputs']['value'], second['outputs']['value']), (1, 2))
        self.assertNotEqual(first['release'], second['release'])
        self.assertEqual(self.host.call(first['release'], 'echo', {'value': 1})['outputs']['value'], 1)

    def test_advisory_checker_cannot_mutate_inline_result(self):
        def mutate(receipt, packet):
            receipt['outputs']['value']['changed'] = True
            return 'FAIL'
        self.host.checkers['mutate'] = mutate
        result = self.host.call(self.seal(), 'echo', {'value': {'original': True}}, checks=['mutate'])
        self.assertEqual(result['outputs']['value'], {'original': True})

    def test_artifact_and_logs_survive_checker_exception(self):
        self.decl['capabilities']['echo']['gives'] = {'value': 'artifact'}
        (self.bundle / 'tool.py').write_text("import json,sys\nfrom pathlib import Path\np=json.load(sys.stdin)\n(Path(p['output_dir'])/'value.txt').write_bytes(b'usable')\nprint('worker log',file=sys.stderr)\nprint(json.dumps({'outcome':'ok','outputs':{'value':{'path':'value.txt'}}}))\n")
        self.host.checkers['crash'] = lambda receipt, packet: 1 / 0
        result = self.host.call(self.seal(), 'echo', {'value': 1}, checks=['crash'])
        self.assertEqual(result['state'], 'succeeded')
        self.assertEqual(self.host.artifact_path(result['outputs']['value']).read_bytes(), b'usable')
        attempt = Path(result['provenance']['attempt_dir'])
        self.assertIn('worker log', (attempt/'stderr.log').read_text())
        self.assertTrue((attempt/'stdout.log').is_file())

    def cli(self, *arguments):
        return subprocess.run([sys.executable, '-m', 'jiuwenswarm.ccv2', *map(str, arguments)],
                              capture_output=True, text=True, cwd=self.root,
                              env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])})

    def test_cli_run_advisory_strict_and_execution_exit_codes(self):
        self.seal()
        inputs = self.root / 'inputs.json'; inputs.write_text('{"value":1}')
        common = ['run', self.bundle, 'echo', '--inputs', inputs, '--store', self.host.store, '--trusted-local']
        advisory = self.cli(*common, '--check', 'missing')
        self.assertEqual(advisory.returncode, 0, advisory.stdout + advisory.stderr)
        self.assertEqual(json.loads(advisory.stdout)['assessment']['verdict'], 'inconclusive')
        strict = self.cli(*common, '--check', 'missing', '--require-checks')
        self.assertEqual(strict.returncode, 1, strict.stdout + strict.stderr)
        complete = self.cli(*common, '--check', 'core.complete', '--require-checks')
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
        (self.bundle / 'tool.py').write_text("print('{\"outcome\":\"partial\",\"reason\":\"partial evidence\",\"outputs\":{\"value\":1}}')")
        partial = self.cli(*common, '--check', 'core.complete', '--require-checks')
        self.assertEqual(partial.returncode, 1)
        self.assertEqual(json.loads(partial.stdout)['state'], 'succeeded')
        (self.bundle / 'tool.py').write_text('raise SystemExit(3)')
        failed = self.cli(*common)
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(json.loads(failed.stdout)['state'], 'failed')

    def test_cli_session_reuses_authorization_and_default_store(self):
        self.decl['capabilities']['echo']['changes'] = ['process.exec']
        self.seal()
        inputs = self.root/'inputs.json'; inputs.write_text('{"value":1}')
        session = self.root/'session.json'; session.write_text('{"grants":["process.exec"]}')
        result = self.cli('run', self.bundle, 'echo', '--inputs', inputs, '--session', session, '--trusted-local')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['effects']['granted'], ['process.exec'])
        self.assertTrue((self.root/'.cc-state/calls.sqlite').is_file())

    def test_failed_execution_retains_valid_partial_outputs(self):
        (self.bundle / 'tool.py').write_text("print('{\"outcome\":\"error\",\"error\":{\"code\":\"CAPTURE_STOPPED\",\"message\":\"Stopped after partial work\"},\"outputs\":{\"value\":{\"usable\":true}}}')\nraise SystemExit(1)")
        result = self.host.call(self.seal(), 'echo', {'value': 1})
        self.assertEqual((result['state'], result['completeness'], result['reason']), ('failed', 'partial', 'CAPTURE_STOPPED'))
        self.assertEqual(result['outputs']['value'], {'usable': True})

    def test_missing_required_output_retains_other_valid_outputs(self):
        self.decl['capabilities']['echo']['gives']['extra'] = 'text'
        result = self.host.call(self.seal(), 'echo', {'value': 'keep this'})
        self.assertEqual((result['state'], result['reason'], result['completeness']), ('failed', 'INVALID_OUTPUT', 'partial'))
        self.assertEqual(result['outputs']['value'], 'keep this')


if __name__ == '__main__':
    unittest.main()
