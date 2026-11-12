from copy import deepcopy
import os
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import urllib.request

from jiuwenswarm.ccv2.ccv2 import CCError, Host, normalize, service_entries, callable_entries


EXAMPLE = Path(__file__).parent/'examples/http_product'


def draft(declaration):
    """Create a test-only mutable service view."""
    result = deepcopy(declaration)
    result['applications'] = service_entries(result)
    result['capabilities'] = callable_entries(result)
    return result


def undraft(declaration):
    declaration = deepcopy(declaration)
    declaration.setdefault('capabilities', {})
    for name, app in declaration.pop('applications', {}).items():
        cap = {k:v for k,v in app.items() if k not in {'interfaces','ready'}}
        cap['serves'] = {k:v for k,v in app.items() if k in {'interfaces','ready'}}
        declaration['capabilities'][name] = cap
    return declaration


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.host = Host(Path(self.temp.name)/'store', session_grants=['process.exec', 'network.listen', 'workspace.write'])
        self.release = self.host.prepare(EXAMPLE)
        self.started = []

    def tearDown(self):
        for instance in self.started:
            self.host.stop(instance)
        self.temp.cleanup()

    def start(self, **options):
        result = self.host.start(self.release, 'api', **options)
        if result['identity']:
            self.started.append(result['id'])
        return result

    def test_hybrid_package_tool_and_application(self):
        description = self.host.describe(self.release)
        self.assertEqual(set(description['capabilities']), {'inspect', 'api'})
        self.assertEqual(set(service_entries(description)), {'api'})
        tool = self.host.call(self.release, 'inspect', {})
        self.assertEqual(tool['state'], 'succeeded')
        self.assertEqual(tool['effects']['granted'], [])
        app = self.start()
        self.assertEqual((app['state'], app['readiness']), ('running', 'ready'), app)
        self.assertEqual(app['effects']['granted'], ['network.listen', 'process.exec'])
        with urllib.request.urlopen(app['endpoints']['api']+'compute?x=3', timeout=2) as response:
            self.assertEqual(json.load(response)['value'], 3)
        self.assertEqual(self.host.inspect_instance(app['id'])['state'], 'running')
        self.assertEqual(self.host.stop(app['id'])['state'], 'stopped')

    def test_application_is_not_implicitly_an_agent_tool(self):
        result = self.host.call(self.release, 'api', {})
        self.assertEqual(result['reason'], 'SERVICE_REQUIRES_START')

    def test_product_only_and_no_empty_package(self):
        declaration = draft(self.host.release(self.release)[0])
        declaration.pop('capabilities')
        product = normalize(undraft(declaration))
        self.assertEqual(set(service_entries(product)), {'api'})
        product.pop('capabilities')
        with self.assertRaises(CCError): normalize(product)

    def test_no_implicit_deployment_authority(self):
        host = Host(Path(self.temp.name)/'limited')
        release = host.prepare(EXAMPLE)
        with self.assertRaises(CCError) as error:
            host.start(release, 'api')
        self.assertEqual(error.exception.code, 'DENIED')

    def test_instance_replay_and_conflict(self):
        first = self.start(key='start-once')
        self.assertEqual(first['id'], self.host.start(self.release, 'api', key='start-once')['id'])
        with self.assertRaises(CCError):
            self.host.start(self.release, 'api', key='start-once', timeout=3)

    def test_unknown_protocol_and_reference_rejected(self):
        declaration = draft(self.host.release(self.release)[0])
        wrong = deepcopy(declaration)
        wrong['applications']['api']['interfaces']['api']['protocol'] = 'invented'
        with self.assertRaises(CCError): normalize(undraft(wrong))
        wrong = deepcopy(declaration)
        wrong['applications']['api']['ready']['interface'] = 'missing'
        with self.assertRaises(CCError): normalize(undraft(wrong))

    def test_generation_mismatch_never_stops_another_process(self):
        app = self.start()
        manager = self.host._applications()
        original = manager.get(app['id'])
        wrong = deepcopy(original); wrong['identity']['created'] += 100
        manager.save(wrong)
        try:
            with self.assertRaises(CCError) as error:
                self.host.stop(app['id'])
            self.assertEqual(error.exception.code, 'INSTANCE_REPLACED')
        finally:
            manager.save(original)

    def test_lab_optional_telemetry_does_not_block_benchmark(self):
        app=self.start()
        self.host.resources['engine']={'kind':'environment','url':app['endpoints']['api'],'instance':app['id']}
        self.host.session_grants.append('network.request')
        bundle=Path(__file__).resolve().parent/'protocol_examples/lab'
        observation=self.host.run(bundle,'observe',{'engine':'engine'})
        self.assertEqual((observation['state'],observation['completeness']),('succeeded','partial'))
        self.assertEqual(observation['effects']['granted'],[])
        result=self.host.run(bundle,'benchmark',{'engine':'engine','workload':{'points':[1,2,3]}})
        self.assertEqual(result['state'],'succeeded')
        self.assertEqual(result['outputs']['metrics']['values'],[1,2,3])
        self.assertEqual(result['assessment']['verdict'],'not_requested')

    def test_image_listen_does_not_silently_grant_egress(self):
        declaration = draft(self.host.release(self.release)[0])
        declaration['bindings']['default'] = {'kind': 'image', 'image': 'sha256:'+'a'*64, 'command': ['app']}
        import yaml
        folder = Path(self.temp.name)/'image'; folder.mkdir()
        (folder/'cc.yaml').write_text(yaml.safe_dump(undraft(declaration)), encoding='utf-8')
        (folder/'api.json').write_bytes((EXAMPLE/'api.json').read_bytes())
        (folder/'inspect.py').write_bytes((EXAMPLE/'inspect.py').read_bytes())
        release = self.host.prepare(folder)
        with self.assertRaises(CCError) as error:
            self.host.start(release, 'api')
        self.assertEqual(error.exception.code, 'UNSUPPORTED_NETWORK_POLICY')

    def variant(self, change):
        import yaml
        folder = Path(self.temp.name)/'variant'
        shutil.copytree(EXAMPLE, folder)
        declaration = draft(self.host.release(self.release)[0])
        change(declaration)
        (folder/'cc.yaml').write_text(yaml.safe_dump(undraft(declaration)), encoding='utf-8')
        return self.host.prepare(folder)

    def test_application_inputs_are_strict_ports_with_open_json(self):
        release = self.variant(lambda d: d['applications']['api'].update(takes={'options': 'json'}))
        with self.assertRaises(CCError) as error: self.host.start(release, 'api')
        self.assertEqual(error.exception.code, 'INVALID_INPUT')
        inputs = {'options': {'arbitrary': {'new_fields': [1, True, None]}}}
        app = self.host.start(release, 'api', inputs)
        self.started.append(app['id'])
        self.assertEqual((app['state'], app['inputs']), ('running', inputs))

    def test_readiness_failure_preserves_logs_and_stops(self):
        release = self.variant(lambda d: d['applications']['api']['ready'].update(path='/unavailable'))
        app = self.host.start(release, 'api', timeout=0.15)
        self.started.append(app['id'])
        self.assertEqual(app['state'], 'failed', app)
        self.assertTrue(any(d['code'] == 'READINESS_TIMEOUT' for d in app['diagnostics']))
        self.assertTrue(Path(app['logs']['stderr']).is_file())
        self.assertEqual(self.host.stop(app['id'])['state'], 'failed')
        self.assertIn('stopped', app['provenance'])

    def test_restart_host_looks_up_original_instance(self):
        app = self.start(key='durable-start')
        other = Host(Path(self.temp.name)/'store', session_grants=['process.exec', 'network.listen'])
        replay = other.start(self.release, 'api', key='durable-start')
        self.assertEqual(replay['id'], app['id'])
        self.assertEqual(other.inspect_instance(app['id'])['state'], 'running')

    def test_cli_start_and_stop_use_same_ledger(self):
        command = [sys.executable, '-m', 'jiuwenswarm.ccv2']
        def cli(*arguments):
            result = subprocess.run(command + list(arguments) + ['--store', str(self.host.store)], capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)
        session = Path(self.temp.name)/'session.json'
        session.write_text(json.dumps({'grants': ['process.exec', 'network.listen']}), encoding='utf-8')
        app = cli('start', self.release, 'api', '--session', str(session), '--trusted-local')
        self.started.append(app['id'])
        self.assertEqual(cli('instance', app['id'])['state'], 'running')
        self.assertEqual(cli('stop', app['id'])['state'], 'stopped')

    def test_replay_does_not_need_original_artifact(self):
        release = self.variant(lambda d: d['applications']['api'].update(takes={'config': 'artifact'}))
        source = Path(self.temp.name)/'config.json'; source.write_text('{}')
        artifact = self.host.put_artifact(source)
        app = self.host.start(release, 'api', {'config': artifact}, key='artifact-start')
        self.started.append(app['id'])
        self.host.artifact_path(artifact).unlink()
        self.assertEqual(self.host.start(release, 'api', {'config': artifact}, key='artifact-start')['id'], app['id'])
        self.assertEqual(self.host.lookup_instance('artifact-start')['id'], app['id'])

    def test_literal_input_is_not_launch_syntax(self):
        def change(d):
            app = d['applications']['api']; app.update(takes={'task': 'text'}, interfaces={}); app.pop('ready')
            d['bindings']['default']['command'] = ['{python}', '-c', 'import time; time.sleep(30)', '{input.task}']
        release = self.variant(change)
        task = 'Explain {input.NAME} and {port.api} literally'
        app = self.host.start(release, 'api', {'task': task})
        self.started.append(app['id'])
        self.assertEqual(app['state'], 'running', app)
        self.assertEqual(app['provenance']['command'][-1], task)

    def test_exited_launcher_does_not_confirm_children_stopped(self):
        import psutil
        def change(d):
            app = d['applications']['api']; app.update(interfaces={}); app.pop('ready')
            d['bindings']['default']['command'] = ['{python}', '-c', "import subprocess,sys,time; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); Path('child.pid').write_text(str(p.pid)); time.sleep(.25)"]
        release = self.variant(change)
        app = self.host.start(release, 'api')
        pidfile = self.host.store/'instances'/app['id']/'child.pid'
        deadline = time.monotonic()+4
        while not pidfile.exists() and time.monotonic() < deadline: time.sleep(.03)
        child = psutil.Process(int(pidfile.read_text()))
        try:
            # Reap the foreground launcher before checking orphan semantics. A
            # fixed sleep leaves a zombie on POSIX, which still has a PID.
            self.host._applications().processes[app['id']].wait(timeout=4)
            with self.assertRaises(CCError) as error: self.host.stop(app['id'])
            self.assertEqual(error.exception.code, 'STOP_UNCONFIRMED')
            self.assertEqual(self.host.lookup_instance(app['key'])['state'], 'unknown')
            self.assertTrue(child.is_running())
        finally:
            child.kill()
            try:
                child.wait(timeout=3)
            except psutil.TimeoutExpired:
                # Minimal container PID 1 may not reap an orphaned zombie.
                self.assertEqual(child.status(), psutil.STATUS_ZOMBIE)
            self.host.reconcile_instance(app['id'], stopped=True, note='Test operator terminated observed orphan child')


if __name__ == '__main__':
    unittest.main()
