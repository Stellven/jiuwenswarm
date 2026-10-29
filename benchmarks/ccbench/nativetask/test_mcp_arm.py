"""Tests for the capsule MCP arm of run_native_task (config injection, staging, container command)."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock

import run_native_task as driver


def overlay():
    path = driver.RUNTIME / 'benchmarks/harbor_suite/native_value.py'
    spec = importlib.util.spec_from_file_location('nv_overlay_mcp', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class McpArmTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='nativetask-mcp-test-')).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'task.txt').write_text('Compute the mean.', encoding='utf-8')
        (self.root / 'inputs').mkdir()

    def argv(self, *extra):
        return ['plan', '--task-file', str(self.root / 'task.txt'), '--inputs-dir', str(self.root / 'inputs'),
                '--ledger', str(self.root / 'l.sqlite3'), '--out', str(self.root), *extra]

    def plan(self, *extra):
        args = driver.parser().parse_args(self.argv(*extra))
        driver.ROOT = self.root
        return driver.command_plan(args, 'a1')

    def test_default_spec_has_no_mcp(self):
        plan = self.plan()
        self.assertNotIn('mcp_servers', plan['spec'])
        self.assertEqual(plan['ledger']['arm'], 'native')
        self.assertFalse(any('capsule-src' in part for part in plan['worker']))

    def test_capsule_mcp_flag_injects_server_and_mounts_source(self):
        plan = self.plan('--capsule-mcp')
        (entry,) = plan['spec']['mcp_servers']
        self.assertEqual((entry['name'], entry['transport'], entry['command']), ('capsules', 'stdio', '/opt/venv/bin/python'))
        self.assertEqual(entry['args'], ['-B', '-m', 'jiuwenswarm.capsule_runtime.mcp'])
        self.assertEqual(entry['env']['PYTHONPATH'], '/capsule-src')
        self.assertEqual(plan['ledger']['arm'], 'native-capsule-mcp')
        self.assertTrue(any(m.endswith('target=/capsule-src,readonly') for m in plan['worker']))
        # the agent process keeps the image's JiuwenSwarm; the staged source is for the MCP child only
        self.assertIn('PYTHONPATH=/runtime:/opt/ai4r', plan['worker'])
        # the task text is identical to the plain arm's: no extra instruction
        self.assertEqual(plan['spec']['task'], self.plan()['spec']['task'])
        # the worker writes exactly that entry into config mcp.servers
        self.assertEqual(overlay().mcp_section(plan['spec']), {'servers': [dict(entry, enabled=True)]})

    def test_mcp_config_file_forms_and_validation(self):
        entry = {'name': 'x', 'transport': 'stdio', 'command': '/bin/true'}
        f = self.root / 'mcp.json'
        for body in ([entry], {'servers': [entry]}):
            f.write_text(json.dumps(body), encoding='utf-8')
            plan = self.plan('--mcp-config', str(f))
            self.assertEqual(plan['spec']['mcp_servers'], [entry])
            self.assertFalse(any('/capsule-src' in m for m in plan['worker']))
        f.write_text(json.dumps([{'name': 'x', 'transport': 'sse', 'command': 'c'}]), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.plan('--mcp-config', str(f))

    def test_worker_spec_validation(self):
        module = overlay()
        base = dict(variant='native', task='t', completion_directory=str(self.root), model='gpt-6.1-sol', reasoning_effort='medium')
        f = self.root / 's.json'
        f.write_text(json.dumps(dict(base, mcp_servers=[{'name': 'c', 'transport': 'stdio', 'command': 'x'}])), encoding='utf-8')
        self.assertEqual(len(module.load_spec(f)['mcp_servers']), 1)
        f.write_text(json.dumps(dict(base, mcp_servers=[{'name': 'c', 'transport': 'sse'}])), encoding='utf-8')
        with self.assertRaises(ValueError):
            module.load_spec(f)

    def test_stage_capsule_src_copies_only_needed_packages(self):
        source = self.root / 'src'
        for name in driver.CAPSULE_PACKAGES + ('server',):
            (source / name / '__pycache__').mkdir(parents=True)
            (source / name / 'm.py').write_text('x = 1', encoding='utf-8')
            (source / name / '__pycache__' / 'm.pyc').write_bytes(b'0')
        (source / '__init__.py').write_text('', encoding='utf-8')
        hashes = driver.stage_capsule_src(self.root / 'staged', source)
        self.assertIn('jiuwenswarm/capsule_runtime/m.py', hashes)
        self.assertNotIn('jiuwenswarm/server/m.py', hashes)
        self.assertFalse(any('pyc' in k for k in hashes))


class ContainerCommandTest(unittest.TestCase):
    """The MCP command, as the worker spawns it, starts inside ai4r:ccbench-native (needs Docker and the image)."""
    def test_mcp_server_lists_the_real_capsules_in_image(self):
        try:
            found = subprocess.run(['docker', 'image', 'inspect', driver.DEFAULT_IMAGE], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            self.skipTest('docker unavailable')
        if found.returncode != 0:
            self.skipTest('image ' + driver.DEFAULT_IMAGE + ' not present')
        root = Path(tempfile.mkdtemp(prefix='nativetask-mcp-')).resolve()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        driver.stage_capsule_src(root / 'capsule-src')
        entry = driver.CAPSULE_SERVER
        command = ['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only', '--user', '10001:10001',
                   '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m,uid=10001,gid=10001',
                   '-e', 'PYTHONPATH=' + entry['env']['PYTHONPATH'], '-e', 'HOME=/tmp', '-e', 'PYTHONDONTWRITEBYTECODE=1',
                   '--mount', 'type=bind,source=%s,target=/capsule-src,readonly' % (root / 'capsule-src'),
                   '--entrypoint', entry['command'], driver.DEFAULT_IMAGE, *entry['args']]
        request = '\n'.join(json.dumps(m) for m in (
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}}},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})) + '\n'
        done = subprocess.run(command, input=request, capture_output=True, text=True, timeout=180,
                              env=dict(os.environ, MSYS_NO_PATHCONV='1'))
        names = [t['name'] for line in done.stdout.splitlines() for t in (json.loads(line).get('result', {}).get('tools') or [])]
        for wanted in ('utility.calculate', 'utility.table_normalize', 'utility.calculate_typed', 'utility.table_normalize_typed'):
            self.assertIn(wanted, names, done.stderr[-500:])


class BridgeSystemTest(unittest.TestCase):
    def test_developer_message_is_the_same_for_models_and_restored_after(self):
        import asyncio
        driver.sys.path.insert(0, str(driver.REPO))
        from benchmarks.harbor_suite import native_value, value_host
        from jiuwenswarm.research import local_model_codex
        seen = []
        async def fake(payload):
            seen.append((payload['model']['model_name'], local_model_codex.SYSTEM))
            return {'outcome': 'failed', 'response_text': 'x'}
        ledger = unittest.mock.Mock()
        ledger.claim.return_value = 100
        root = Path(tempfile.mkdtemp(prefix='nativetask-sys-')).resolve()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        binary = root / 'codex'
        binary.write_bytes(b'x')
        default = local_model_codex.SYSTEM
        with unittest.mock.patch.object(local_model_codex, 'execute_async', fake):
            for model in ('gpt-6.1-sol', 'gpt-6-luna'):
                request = {'request_id': 'a' * 32, 'prompt': 'p', 'timeout_s': 5, 'model': model, 'reasoning_effort': 'medium'}
                (root / ('p-' + model)).mkdir()
                asyncio.run(value_host.complete(request, binary=binary, working=root, fingerprint='f', ledger=ledger, pair='p',
                                                arm='native', private=root / ('p-' + model), system=native_value.BRIDGE_SYSTEM))
        self.assertEqual({text for _, text in seen}, {native_value.BRIDGE_SYSTEM})
        self.assertEqual([m for m, _ in seen], ['gpt-6.1-sol', 'gpt-6-luna'])
        self.assertEqual(local_model_codex.SYSTEM, default)
        self.assertNotIn('unavailable', native_value.BRIDGE_SYSTEM)
        self.assertEqual(native_value.BRIDGE_SYSTEM, overlay().BRIDGE_SYSTEM)


if __name__ == '__main__':
    unittest.main()
