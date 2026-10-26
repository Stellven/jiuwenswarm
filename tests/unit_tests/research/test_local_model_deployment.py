"""Offline operator fixtures: no Docker, SSH, models, or service starts."""
import copy
from contextlib import nullcontext
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[3]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy/m1' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


lm = module('unit_local_model_operator', 'local_model_operator.py')
host = module('unit_local_model_host', 'operator_host.py')
with patch.dict('sys.modules', {'operator_host': host}):
    cli = module('unit_local_model_cli', 'ai4r.py')


def selected():
    return dict(schema=lm.PROFILE_SCHEMA, catalog='/operator/catalog.json',
        session_file='/operator/private/session.json', socket_directory='/operator/model-export',
        catalog_sha256='a' * 64, session_sha256='b' * 64)


def deployment():
    return dict(project='ai4r-fixture', deployment_id='fixture-deployment',
        app_image='sha256:' + '1' * 64, local_model=selected())


def catalog():
    return dict(schema='ai4r-local-model-catalog:1', gateway_id='fixture-gateway',
        backend=dict(kind='ssh-loopback-openai', target='fixture-user@fixture-host', base_url='http://127.0.0.1:8000/v1'),
        transport=dict(socket_path=lm.SOCKET_ROOT + '/model.sock', session_file=lm.CONFIG_ROOT + '/session.json',
                       peer_uid=1000, socket_mode=0o660),
        models=[dict(id='local-fixture', name='Fixture', model_name='fixture-model', revision='fixture-r1',
                     enabled=True, context_window=4096, max_output_tokens=512, max_prompt_bytes=2048,
                     timeout_s=30, temperature=0, enable_thinking=False)])


class LocalModelDeploymentTests(unittest.TestCase):
    def test_disabled_compose_is_unchanged_and_enabled_is_app_only(self):
        value = {'services': {'ai4r': {'environment': {}, 'volumes': []},
                              'benchmark-runner': {'environment': {}, 'volumes': []},
                              'sandbox': {'environment': {}, 'volumes': []}}, 'volumes': {}}
        original = copy.deepcopy(value)
        lm.apply_compose({}, value)
        self.assertEqual(value, original)
        lm.apply_compose(deployment(), value)
        self.assertEqual(value['services']['benchmark-runner'], original['services']['benchmark-runner'])
        self.assertEqual(value['services']['sandbox'], original['services']['sandbox'])
        app = value['services']['ai4r']
        self.assertEqual(app['environment']['AI4R_LOCAL_MODEL_CATALOG'], lm.CONFIG_ROOT + '/catalog.json')
        self.assertEqual(len(app['volumes']), 2)
        self.assertTrue(all(m['read_only'] for m in app['volumes']))
        self.assertFalse(app['volumes'][1]['bind']['create_host_path'])
        self.assertEqual(value['volumes']['local_model_config']['labels']['ai4r.role'], lm.ROLE)

    def test_catalog_is_closed_and_transport_mounts_cannot_be_redirected(self):
        self.assertEqual(lm.validate_catalog(catalog()), catalog())
        for mutate in (lambda c: c.update(extra=True),
                       lambda c: c['transport'].update(socket_path='/run/docker.sock'),
                       lambda c: c['transport'].update(socket_mode=0o666),
                       lambda c: c['backend'].update(target='fixture; arbitrary-command'),
                       lambda c: c['backend'].update(base_url='http://localhost:8000/v1'),
                       lambda c: c['models'][0].update(timeout_s=float('nan')),
                       lambda c: c['models'][0].update(command='anything')):
            value = catalog()
            mutate(value)
            with self.assertRaises(ValueError):
                lm.validate_catalog(value)
        with self.assertRaises(ValueError):
            lm.json_value(b'{"capability":"one","capability":"two"}')

    def test_profile_rejects_arbitrary_bind_fields_and_paths(self):
        for mutate in (lambda p: p.update(extra='anything'),
                       lambda p: p.update(socket_directory='/operator/export,source=/'),
                       lambda p: p.update(socket_directory='/operator/../etc'),
                       lambda p: p.update(catalog='relative.json'),
                       lambda p: p.update(session_sha256='wrong')):
            value = selected()
            mutate(value)
            with self.assertRaises(ValueError):
                lm.validate_profile(value)

    def test_export_directory_is_separate_setgid_and_contains_only_socket(self):
        directory, source = Mock(), Mock()
        source.is_relative_to.return_value = False
        socket = Mock()
        socket.exists.return_value = False
        socket.is_symlink.return_value = False
        directory.__truediv__ = Mock(return_value=socket)
        directory.iterdir.return_value = []
        metadata = SimpleNamespace(st_mode=0o042710, st_uid=1000, st_gid=10001)
        directory.lstat.return_value = metadata
        session = json.dumps({'session_id': 's' * 43, 'capability': 'private-fixture-' * 4}).encode()
        def fake_path(value):
            return directory if value == '/operator/export' else source
        with patch.object(lm.os, 'name', 'posix'), \
             patch.object(lm, 'path', side_effect=fake_path), \
             patch.object(lm, 'read_file', side_effect=lambda value, **kw: json.dumps(catalog()).encode() if value.endswith('catalog') else session):
            profile, _, _ = lm.inspect_sources('/operator/catalog', '/operator/session', '/operator/export')
            self.assertEqual(profile['socket_directory'], '/operator/export')
            metadata.st_mode = 0o040710
            with self.assertRaises(ValueError):
                lm.inspect_sources('/operator/catalog', '/operator/session', '/operator/export')
            metadata.st_mode = 0o042710
            directory.iterdir.return_value = [SimpleNamespace(name='requests.sqlite3')]
            with self.assertRaises(ValueError):
                lm.inspect_sources('/operator/catalog', '/operator/session', '/operator/export')
            directory.iterdir.return_value = []
            source.is_relative_to.return_value = True
            with self.assertRaises(ValueError):
                lm.inspect_sources('/operator/catalog', '/operator/session', '/operator/export')

    def fake_docker(self, *, foreign=False, running=False):
        p = deployment()
        volume = p['project'] + '_local_model_config'
        label = lm.labels(p)
        if foreign:
            label['ai4r.deployment'] = 'foreign'
        calls = []
        def docker(profile, *args, **kwargs):
            calls.append((args, kwargs))
            if args[:2] == ('context', 'inspect'):
                return json.dumps([{'Endpoints': {'docker': {'Host': 'unix:///var/run/docker.sock'}}}]).encode()
            if args[0] == 'info':
                return b'[]'
            if args[:2] == ('volume', 'ls'):
                return (volume + '\n').encode()
            if args[:2] == ('volume', 'inspect'):
                return json.dumps([{'Name': volume, 'Labels': label, 'Driver': 'local', 'Options': {}}]).encode()
            if args[0] == 'ps':
                return b'running-fixture' if running else b''
            if args[0] == 'run':
                return b''
            raise AssertionError(args)
        return docker, calls

    def test_provision_is_no_network_and_secrets_only_travel_on_stdin(self):
        docker, calls = self.fake_docker()
        with patch.object(lm, 'read_pinned', return_value=(b'{"fixture":"catalog"}', b'private-fixture-capability')):
            lm.provision(deployment(), docker)
        args, kwargs = calls[-1]
        self.assertEqual(args[0], 'run')
        self.assertEqual(args[args.index('--network') + 1], 'none')
        self.assertEqual(args[args.index('--pull') + 1], 'never')
        self.assertIn('--read-only', args)
        self.assertNotIn('private-fixture-capability', str(args))
        self.assertIn('data', kwargs)
        self.assertNotIn('type=bind', str(args))
        self.assertIn('fchown', args[-1])
        self.assertIn('0o444', args[-1])
        self.assertIn('0o400', args[-1])

    def test_foreign_volume_is_refused_before_helper(self):
        docker, calls = self.fake_docker(foreign=True)
        with patch.object(lm, 'read_pinned', return_value=(b'catalog', b'session')):
            with self.assertRaises(ValueError):
                lm.provision(deployment(), docker)
        self.assertFalse(any(args[0] == 'run' for args, kwargs in calls))

    def test_remote_docker_host_is_refused_for_host_socket_binds(self):
        docker = Mock()
        with patch.dict(os.environ, {'DOCKER_HOST': 'ssh://fixture-remote'}):
            with self.assertRaises(ValueError):
                lm.provision(deployment(), docker)
        docker.assert_not_called()
        docker.return_value = json.dumps([{'Endpoints': {'docker': {'Host': 'tcp://fixture:2376'}}}]).encode()
        with patch.dict(os.environ, {'DOCKER_HOST': ''}):
            with self.assertRaises(ValueError):
                lm.provision(deployment(), docker)
        self.assertEqual(docker.call_count, 1)

    def test_rootless_remapping_and_conflicting_context_are_refused(self):
        docker = Mock()
        p = deployment()
        p['docker_context'] = 'fixture-local'
        with patch.dict(os.environ, {'DOCKER_HOST': '', 'DOCKER_CONTEXT': 'fixture-other'}):
            with self.assertRaises(ValueError):
                lm.provision(p, docker)
        docker.assert_not_called()
        for option in ('name=rootless', 'name=userns'):
            docker.reset_mock()
            docker.side_effect = [json.dumps([{'Endpoints': {'docker': {'Host': 'unix:///var/run/docker.sock'}}}]).encode(),
                                  json.dumps([option]).encode()]
            with patch.dict(os.environ, {'DOCKER_HOST': '', 'DOCKER_CONTEXT': ''}):
                with self.assertRaises(ValueError):
                    lm.provision(p, docker)
            self.assertEqual(docker.call_count, 2)

    def test_running_volume_is_verified_readonly_without_rewrite(self):
        docker, calls = self.fake_docker(running=True)
        with patch.object(lm, 'read_pinned', return_value=(b'catalog', b'session')):
            lm.provision(deployment(), docker)
        args, kwargs = calls[-1]
        self.assertIn(',readonly', args[args.index('--mount') + 1])
        self.assertEqual(args[-1], lm.VOLUME_VERIFY)
        self.assertEqual(set(json.loads(kwargs['data'])), {'catalog_sha256', 'session_sha256'})

    def test_configure_checks_idle_records_only_pins_and_does_not_activate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            p = deployment()
            p.pop('local_model')
            (root / 'deployment.json').write_text(json.dumps(p))
            inspect = Mock(return_value=(selected(), b'catalog', b'private-secret'))
            with patch.object(host, 'owned', return_value=root), \
                 patch.object(host, 'lock', side_effect=lambda _: nullcontext()), \
                 patch.object(host, 'assert_idle') as idle, \
                 patch.object(host, 'assert_app_idle') as app_idle, \
                 patch.object(host, 'local_model_operator', return_value={'inspect_sources': inspect}), \
                 patch.object(host, 'docker', side_effect=AssertionError('Docker activation forbidden')):
                result = host.dispatch(dict(action='local-model-configure', profile=p,
                    catalog=selected()['catalog'], session_file=selected()['session_file'],
                    socket_directory=selected()['socket_directory']))
            idle.assert_called_once()
            app_idle.assert_called_once()
            self.assertFalse(result['activated'])
            saved = (root / 'deployment.json').read_text()
            self.assertNotIn('private-secret', saved)
            self.assertEqual(json.loads(saved)['local_model'], selected())

    def test_cli_and_remote_source_bundle_are_static_and_import_safe(self):
        args = cli.parser().parse_args(['local-model', 'configure', '--catalog', '/operator/catalog.json',
            '--session-file', '/operator/session.json', '--socket-directory', '/operator/export'])
        self.assertEqual(args.command, 'local-model')
        namespace = {'__name__': 'offline_fixture'}
        with patch('subprocess.run', side_effect=AssertionError('No external process permitted')):
            exec(compile(cli.host_source(), '<offline-host-source>', 'exec'), namespace)
            helper = namespace['local_model_operator']()
        self.assertEqual(helper['PROFILE_SCHEMA'], lm.PROFILE_SCHEMA)

    @unittest.skipUnless(os.name == 'posix', 'Unix custody semantics')
    def test_real_source_file_rejects_mode_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'session.json'
            source.write_bytes(b'fixture')
            source.chmod(0o600)
            kwargs = dict(owner=os.geteuid(), modes={0o600}, maximum=32)
            self.assertEqual(lm.read_file(str(source), **kwargs), b'fixture')
            source.chmod(0o644)
            with self.assertRaises(ValueError):
                lm.read_file(str(source), **kwargs)
            source.chmod(0o600)
            alias = source.with_name('alias')
            alias.symlink_to(source)
            with self.assertRaises(ValueError):
                lm.read_file(str(alias), **kwargs)
            alias.unlink()
            os.link(source, alias)
            with self.assertRaises(ValueError):
                lm.read_file(str(source), **kwargs)


if __name__ == '__main__':
    unittest.main()
