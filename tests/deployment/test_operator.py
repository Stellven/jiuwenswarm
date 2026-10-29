"""Host/operator integration without app imports, credentials, models or Docker."""
import argparse
import base64
from contextlib import redirect_stdout, redirect_stderr
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'deploy/m1'))
import ai4r
import operator_host as h


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.p = h.setup({'profile': {'project': 'ai4r-test', 'root': str(self.base / 'host'),
            'output': str(self.base / 'results'), 'platform': 'linux/amd64', 'ttl_days': 7,
            'docker_context': None}, 'seccomp': '{}'})
        self.config = {'schema': 'ai4r-operator:1', 'deployment': self.p, 'builds': {}}
        self.real_docker = h.docker
        mocked_docker = patch.object(h, 'docker', side_effect=ValueError('Docker deliberately unavailable in host-only tests'))
        mocked_docker.start(); self.addCleanup(mocked_docker.stop)

    def request(self, action, **kwargs):
        return h.dispatch({'profile': self.p, 'action': action, **kwargs})

    def make_campaign(self, state='complete'):
        directory = Path(self.p['output']) / 'example'; directory.mkdir()
        h.publish(directory / '.runner-owner.json', h.canonical({'owner': 'ai4r-sequential-runner:1', 'campaign_id': 'example'}))
        h.publish(directory / 'campaign_state.json', h.canonical({'state': state}))
        h.publish(directory / 'answer.txt', b'real artifact bytes')
        return directory

    def transfer(self, data, expected=None):
        ident = self.request('begin-transfer', size=len(data))['id']
        self.request('put', id=ident, data=base64.b64encode(data).decode(), offset=0)
        info = {'size': len(data), 'sha256': __import__('hashlib').sha256(data).hexdigest()}
        result = self.request('publish-transfer', id=ident, kind='inputs', path='stage/data.txt', info=expected or info)
        return ident, info, result

    def test_repeat_setup_preserves_bytes_and_state(self):
        marker = Path(self.p['root']) / 'config.json'; marker.write_bytes(b'preserve')
        result = h.setup({'profile': copy.deepcopy(self.p), 'seccomp': 'changed'})
        self.assertEqual(result, self.p)
        self.assertEqual(marker.read_bytes(), b'preserve')
        self.assertEqual((Path(self.p['root']) / 'seccomp.json').read_bytes(), b'{}')

    def test_foreign_root_and_overlapping_output_refused(self):
        p = copy.deepcopy(self.p); p['root'] = str(self.base / 'foreign')
        Path(p['root']).mkdir()
        with self.assertRaises(FileNotFoundError): h.setup({'profile': p, 'seccomp': '{}'})
        p['root'] = str(self.base / 'new'); p['output'] = p['root']
        with self.assertRaises(ValueError): h.setup({'profile': p, 'seccomp': '{}'})

    def test_existing_output_files_and_mode_preserved(self):
        output = self.base / 'existing'; output.mkdir(); output.chmod(0o750)
        (output / 'sentinel').write_bytes(b'user')
        mode = output.stat().st_mode
        p = copy.deepcopy(self.p); p.update(root=str(self.base / 'another'), output=str(output))
        h.setup({'profile': p, 'seccomp': '{}'})
        self.assertEqual(output.stat().st_mode, mode)
        self.assertEqual((output / 'sentinel').read_bytes(), b'user')

    def test_transfer_integrity_skip_and_no_overwrite(self):
        ident, info, result = self.transfer(b'first')
        self.assertTrue(result['verified'])
        self.assertTrue(self.request('file-check', kind='inputs', path='stage/data.txt', info=info)['matches'])
        with self.assertRaises(ValueError): self.transfer(b'other')
        self.assertEqual((Path(self.p['root']) / 'inputs/stage/data.txt').read_bytes(), b'first')
        with self.assertRaises(ValueError): self.transfer(b'wrong', {'size': 5, 'sha256': '0' * 64})

    def test_paths_offsets_and_chunk_bounds(self):
        for name in ('../outside', '/absolute', 'a\\b', 'a:b', './alias'):
            with self.assertRaises(ValueError): h.relative(name)
        ident = self.request('begin-transfer', size=3)['id']
        with self.assertRaises(ValueError): self.request('put', id=ident, offset=1, data='YQ==')
        with self.assertRaises(ValueError): self.request('publish-transfer', id='../../bad', kind='inputs', path='a', info={})

    def test_capacity_preserves_twenty_percent(self):
        usage = argparse.Namespace(total=1000, free=250)
        with patch.object(h.shutil, 'disk_usage', return_value=usage):
            self.assertEqual(h.capacity(self.base, 50)['additional_bytes'], 50)
            with self.assertRaises(ValueError): h.capacity(self.base, 51)

    def test_ttl_dry_run_protects_retained_and_incomplete(self):
        campaign = self.make_campaign()
        expired = h.temporary(self.p, 'transfer'); (expired / 'old').write_bytes(b'temp'); h.finish_temporary(expired)
        current = h.temporary(self.p, 'transfer'); h.finish_temporary(current)
        incomplete = h.temporary(self.p, 'transfer')
        marker = expired / 'temporary.json'; record = json.loads(marker.read_bytes())
        record['completed_at'] = time.time() - 8 * 86400; h.publish(marker, h.canonical(record), replace=True)
        dry = self.request('gc', dry_run=True)
        self.assertIn(expired.name, dry['eligible']); self.assertTrue(expired.exists())
        self.request('gc')
        self.assertFalse(expired.exists()); self.assertTrue(current.exists()); self.assertTrue(incomplete.exists())
        self.assertEqual((campaign / 'answer.txt').read_bytes(), b'real artifact bytes')

    def test_gc_and_stop_refuse_unknown_campaign(self):
        self.make_campaign('paused')
        with self.assertRaises(ValueError): self.request('gc')
        with self.assertRaises(ValueError): self.request('stop')

    def test_gc_refuses_hardlinks_in_expired_tree(self):
        folder = h.temporary(self.p, 'transfer'); h.finish_temporary(folder)
        sentinel = self.base / 'sentinel'; sentinel.write_bytes(b'keep')
        os.link(sentinel, folder / 'link')
        with self.assertRaises(ValueError): h.gc(self.p, now=time.time() + 8 * 86400)
        self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_snapshot_and_fetch_are_verified_and_survive_source_removal(self):
        campaign = self.make_campaign()
        output = self.base / 'retrieved'
        result = ai4r.fetch(self.config, argparse.Namespace(campaign='example', output=output))
        self.assertTrue(result['source_retained'])
        self.assertEqual((output / 'answer.txt').read_bytes(), b'real artifact bytes')
        __import__('shutil').rmtree(campaign)
        self.assertEqual((output / 'answer.txt').read_bytes(), b'real artifact bytes')
        with self.assertRaises(ValueError): ai4r.fetch(self.config, argparse.Namespace(campaign='example', output=output))

    def test_fetch_resume_uses_same_snapshot_and_skips_verified_files(self):
        self.make_campaign()
        output = self.base / 'retrieved'
        original = ai4r.Transport.request
        failed = [False]
        def unreliable(transport, action, **values):
            if action == 'read-chunk' and not failed[0]:
                failed[0] = True; raise ValueError('connection lost')
            return original(transport, action, **values)
        args = argparse.Namespace(campaign='example', output=output)
        with patch.object(ai4r.Transport, 'request', unreliable):
            with self.assertRaises(ValueError): ai4r.fetch(self.config, args)
        self.assertFalse(output.exists())
        def no_new_snapshot(transport, action, **values):
            self.assertNotEqual(action, 'snapshot')
            return original(transport, action, **values)
        with patch.object(ai4r.Transport, 'request', no_new_snapshot): ai4r.fetch(self.config, args)
        self.assertEqual((output / 'answer.txt').read_bytes(), b'real artifact bytes')

    def test_snapshot_refuses_foreign_campaign(self):
        directory = self.make_campaign(); (directory / '.runner-owner.json').write_text('{}')
        with self.assertRaises(ValueError): self.request('snapshot', campaign='example')

    def test_rpc_executes_shipped_source_not_private_imports(self):
        source = (ai4r.HERE / 'operator_host.py').read_text()
        request = {'action': 'gc', 'dry_run': True, 'profile': self.p}
        result = subprocess.run([sys.executable, '-c', ai4r.REMOTE],
            input=h.canonical({'source': source, 'request': request}), capture_output=True, check=True)
        self.assertTrue(json.loads(result.stdout)['ok'])

    def test_selected_docker_and_explicit_wsl_are_preserved(self):
        self.assertEqual(ai4r.docker_prefix({'docker_context': 'chosen'}), ['docker', '--context', 'chosen'])
        self.assertEqual(ai4r.docker_prefix({'wsl_distro': 'Ubuntu-24.04'}), ['wsl.exe', '-d', 'Ubuntu-24.04', '--exec', 'docker'])

    def test_existing_image_pair_is_pinned_without_build_or_source_claim(self):
        def inspect(args, **kwargs):
            self.assertEqual(args[:3], ['docker', 'image', 'inspect'])
            return h.canonical([{'Id': 'sha256:' + ('1' if args[-1] == 'ai4r:local' else '2') * 64,
                'Architecture': 'amd64', 'Os': 'linux', 'Size': 100, 'Config': {'Labels': None}}])
        with patch.object(h, 'run', inspect):
            ai4r.select_images(self.config, 'ai4r:local', 'benchmark-runner:local')
        self.assertEqual(self.config['deployment']['app_image'], 'sha256:' + '1' * 64)
        self.assertIn('not performed', self.config['builds']['provenance'])
        self.assertIsNone(self.config['builds']['images']['ai4r']['source_revision'])
        before = copy.deepcopy(self.config)
        with patch.object(h, 'run', return_value=h.canonical([{'Architecture': 'arm64'}])):
            with self.assertRaises(ValueError): ai4r.select_images(self.config, 'app', 'runner')
        self.assertEqual(self.config, before)

    def test_stage_receipt_selects_images_and_rejects_partial_image_flags(self):
        receipt = self.base / 'receipt.json'
        images = {role: {'image_id': 'sha256:' + digit * 64} for role, digit in [('ai4r', '1'), ('benchmark-runner', '2')]}
        receipt.write_text(json.dumps({'schema': 'ai4r-build:1', 'platform': 'linux/amd64', 'images': images}))
        args = argparse.Namespace(receipt=receipt, app_image=None, runner_image=None)
        with patch.object(ai4r, 'stage', return_value={'staged': True}):
            self.assertTrue(ai4r.stage_selection(self.config, args)['staged'])
        self.assertEqual(self.config['deployment']['runner_image'], images['benchmark-runner']['image_id'])
        args.receipt = None; args.app_image = 'only-app'
        with self.assertRaises(ValueError): ai4r.stage_selection(self.config, args)

    def test_up_stages_existing_images_preserves_inputs_and_repeats_without_build(self):
        cases_root = self.base / 'selected'; cases_root.mkdir()
        inputs = self.base / 'user-inputs'; inputs.mkdir()
        cases = cases_root / 'cases.json'; cases.write_text('{"supplied":"cases"}')
        sentinel = inputs / 'user.txt'; sentinel.write_bytes(b'original user bytes')
        profile = self.base / 'operator.json'
        original = ai4r.Transport.request
        starts = []
        def request(transport, action, **kwargs):
            if action == 'image-check': return {'matches': True}
            if action == 'start':
                self.assertNotIn('cgroup_script', kwargs)
                self.assertNotIn('cgroup_root', transport.config['deployment'])
                starts.append(copy.deepcopy(transport.config['deployment']))
                return {'deployment': transport.config['deployment'], 'app_started': True,
                    'next': 'Complete authentication before starting a campaign'}
            return original(transport, action, **kwargs)
        def inspect(args, **kwargs):
            self.assertEqual(args[:3], ['docker', 'image', 'inspect'])
            return h.canonical([{'Id': 'sha256:' + ('1' if args[-1] == 'ai4r:local' else '2') * 64,
                'Architecture': 'amd64', 'Os': 'linux', 'Size': 100, 'Config': {'Labels': None}}])
        args = ['--profile', str(profile), 'up', '--cases', str(cases), '--inputs', str(inputs),
            '--root', self.p['root'], '--output', self.p['output'], '--project', self.p['project'], '--platform', 'linux/amd64']
        with patch.object(ai4r.Transport, 'request', request), patch.object(h, 'run', inspect), redirect_stdout(io.StringIO()):
            self.assertEqual(ai4r.main(args), 0)
            self.assertEqual(ai4r.main(args), 0)
        self.assertEqual(len(starts), 2)
        self.assertEqual(starts[0]['deployment_id'], starts[1]['deployment_id'])
        self.assertEqual(sentinel.read_bytes(), b'original user bytes')
        self.assertEqual(ai4r.load(profile)['deployment']['app_image'], 'sha256:' + '1' * 64)

    def test_local_relative_output_is_resolved_but_remote_path_is_not(self):
        profile = self.base / 'relative-profile.json'
        args = ai4r.parser().parse_args(['--profile', str(profile), 'setup',
            '--project', 'ai4r-relative', '--root', str(self.base / 'another-host'), '--output', './results'])
        with patch('os.getcwd', return_value=str(self.base)):
            ai4r.setup(args)
        self.assertEqual(ai4r.load(profile)['deployment']['output'], str(self.base / 'results'))
        remote = ai4r.parser().parse_args(['--profile', str(self.base / 'remote.json'), 'setup',
            '--ssh', 'spark', '--output', '/home/researcher/results'])
        def request(transport, action, **values):
            self.assertEqual(transport.config['deployment']['output'], '/home/researcher/results')
            return transport.config['deployment']
        with patch.object(ai4r.Transport, 'request', request): ai4r.setup(remote)

    def test_wsl_transport_uses_default_user_without_forced_root(self):
        reply = argparse.Namespace(returncode=0, stdout=b'{"ok":true,"result":{}}')
        with patch.object(ai4r.subprocess, 'run', return_value=reply) as call:
            ai4r.Transport({**self.config, 'wsl_distro': 'chosen-distro'}).request('doctor')
        command = call.call_args.args[0]
        self.assertEqual(command[:4], ['wsl.exe', '-d', 'chosen-distro', '--exec'])
        self.assertNotIn('root', command)
        self.assertEqual(ai4r.docker_prefix({}, build=True), ['docker'])

    def test_ssh_arguments_are_not_shell_interpolated(self):
        config = {**self.config, 'ssh': 'spark'}
        response = argparse.Namespace(returncode=0, stdout=b'{"ok":true,"result":{"ready":true}}')
        with patch.object(ai4r.subprocess, 'run', return_value=response) as call:
            self.assertTrue(ai4r.Transport(config).request('doctor')['ready'])
        args = call.call_args.args[0]
        self.assertEqual(args[:3], ['ssh', '-o', 'BatchMode=yes'])
        self.assertEqual(args[-2], 'spark')
        self.assertIn('ConnectTimeout=10', args)
        self.assertNotIn(self.p['root'], args[-1])

    def test_failed_ssh_never_publishes_success(self):
        response = argparse.Namespace(returncode=255, stdout=b'')
        with patch.object(ai4r.subprocess, 'run', return_value=response):
            with self.assertRaises(ValueError): ai4r.Transport({**self.config, 'ssh': 'spark'}).request('doctor')

    def test_freeze_context_excludes_credentials_and_runner_from_app(self):
        repo = self.base / 'source'; repo.mkdir()
        for name in ('pyproject.toml', 'uv.lock', 'LICENSE', 'OPEN_SOURCE_SOFTWARE_NOTICE.md'):
            (repo / name).write_text('public')
        for rel in ('jiuwenswarm/core.py', 'jiuwenswarm/research_sidecar/secret.py', 'jiuwenswarm/.env',
                    'jiuwenswarm/auth.json', 'jiuwenswarm/private/hidden.txt'):
            path = repo / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('bytes')
        with patch.object(ai4r, 'REPO', repo):
            inventory = ai4r.freeze_context('ai4r', self.base / 'source.tar')
        paths = [row['path'] for row in inventory]
        self.assertIn('jiuwenswarm/core.py', paths)
        self.assertNotIn('jiuwenswarm/research_sidecar/secret.py', paths)
        self.assertNotIn('jiuwenswarm/.env', paths)
        self.assertNotIn('jiuwenswarm/auth.json', paths)
        self.assertNotIn('jiuwenswarm/private/hidden.txt', paths)

    @unittest.skipUnless(__import__('shutil').which('docker'), 'Docker Compose CLI unavailable')
    def test_real_compose_render_needs_no_daemon(self):
        available = subprocess.run(['docker', 'compose', 'version'], capture_output=True)
        if available.returncode: self.skipTest('Compose plugin unavailable')
        self.p['input_stage'] = 'a' * 64
        with patch.object(h, 'docker', self.real_docker):
            h.render(self.p, (ai4r.HERE / 'compose.benchmark-runner.yaml').read_text())
        rendered = json.loads((Path(self.p['root']) / 'compose.json').read_bytes())
        self.assertEqual(set(rendered['services']), {'ai4r', 'benchmark-runner'})
        app = rendered['services']['ai4r']; runner = rendered['services']['benchmark-runner']
        self.assertNotIn('build', app)
        self.assertEqual(app['ports'][0]['published'], '5175')
        self.assertEqual(app['ports'][0]['host_ip'], '127.0.0.1')
        self.assertEqual(app['environment']['AI4R_EXECUTION_MODE'], 'm1_app_process')
        self.assertEqual(app['environment']['JIUWENSWARM_M1_LOCAL_RESEARCH'], '1')
        self.assertEqual(int(app['mem_limit']), 4 * 1024 ** 3)
        self.assertEqual(app['pids_limit'], 256)
        self.assertFalse(any(m.get('target') == '/etc/ai4r/config.yaml' for m in app['volumes']))
        self.assertFalse(any(m.get('target') == '/run/benchmark-runner' for m in app['volumes']))
        self.assertTrue(any('/resources:rw,nosuid,nodev,size=128m,mode=0711,uid=0,gid=0' in v for v in app['tmpfs']))
        self.assertEqual(runner['labels']['ai4r.deployment'], self.p['deployment_id'])
        mounts = {m['target']: m for m in runner['volumes']}
        self.assertTrue(mounts['/inputs']['read_only']); self.assertTrue(mounts['/cases']['read_only'])
        self.assertNotIn('docker.sock', json.dumps(rendered))
        self.assertNotIn('/var/lib/ai4r-accounts', json.dumps(runner))
        self.assertEqual(mounts['/run/benchmark-runner']['type'], 'volume')
        self.assertEqual(mounts['/results']['type'], 'bind')
        self.assertEqual(runner['logging']['options']['max-size'], '10m')

    def test_cli_setup_is_repeatable_without_any_private_runtime(self):
        profile = self.base / 'operator.json'; root = self.base / 'cli-root'
        args = ['--profile', str(profile), 'setup', '--root', str(root)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(ai4r.main(args), 0)
            config = json.loads(profile.read_bytes())
            sentinel = root / 'results' / 'sentinel'; sentinel.write_bytes(b'user')
            self.assertEqual(ai4r.main(args), 0)
        self.assertEqual(sentinel.read_bytes(), b'user')
        self.assertEqual(json.loads(profile.read_bytes())['deployment']['deployment_id'], config['deployment']['deployment_id'])

    def test_start_initializes_once_then_reuses_state_and_refreshes_scope(self):
        self.p.update(app_image='sha256:' + '1' * 64, runner_image='sha256:' + '2' * 64)
        events = []
        def docker(profile, *args, **kwargs):
            if args[:2] == ('ps', '-aq'): return b''
            if args[0] in {'volume', 'network'}: raise ValueError('missing')
            if args[:2] == ('image', 'inspect'):
                return h.canonical([{'Architecture': 'amd64', 'Id': args[2]}])
            if args[0] == 'inspect': return h.canonical([{'State': {'StartedAt': 'instance-1'}}])
            raise AssertionError(args)
        def compose(profile, *args, **kwargs):
            events.append(args)
            if args[:2] == ('ps', '-q'): return b'container-id'
            if 'jiuwenswarm.research.initialize' in args: return b'{"status":"initialized"}'
            return b''
        def grant(profile):
            profile.update(credential_ready=True, grant={'expires_at': time.time() + 1000}, build_id='build')
        request = {'template': '', 'cgroup_script': '', 'refresh_credential': False}
        with patch.object(h, 'run', side_effect=AssertionError('No host commands or elevation expected')), patch.object(h, 'docker', docker), patch.object(h, 'compose', compose), patch.object(h, 'render'), patch.object(h, 'issue_credential', grant), patch.object(h, 'mount_probe'):
            first = h.start(self.p, request)
            second = h.start(self.p, request)
            self.assertTrue(first['app_started']); self.assertTrue(second['runner_started'])
        self.assertEqual(sum('jiuwenswarm.research.initialize' in args for args in events), 1)
        self.assertEqual(json.loads((Path(self.p['root']) / 'initialized.json').read_bytes())['app_image'], self.p['app_image'])

    def test_start_refuses_existing_foreign_volume_before_app_changes(self):
        self.p.update(app_image='sha256:' + '1' * 64, runner_image='sha256:' + '2' * 64)
        def docker(profile, *args, **kwargs):
            if args[0] == 'ps': return b''
            if args[0] == 'volume': return b'[{"Labels":{"ai4r.deployment":"someone-else"}}]'
            raise AssertionError(args)
        with patch.object(h, 'docker', docker), patch.object(h, 'compose') as compose:
            with self.assertRaises(ValueError): h.start(self.p, {'template': '', 'cgroup_script': ''})
        compose.assert_not_called()

    def test_credential_never_appears_in_profile_or_command_arguments(self):
        secret = 'private-fixture-token'
        def compose(profile, *args, **kwargs):
            if args[-2] == '-c': return h.canonical({'token': secret, 'grant': {'expires_at': time.time() + 100}})
            return b'{"build_id":"build-fixture"}'
        self.p['app_image'] = 'sha256:' + '1' * 64
        (Path(self.p['root']) / 'compose.source.yaml').write_text('fixture')
        with patch.object(h, 'compose', compose), patch.object(h, 'render'), patch.object(h, 'docker', return_value=b'') as docker:
            h.issue_credential(self.p)
        self.assertNotIn(secret, json.dumps(self.p))
        for call in docker.call_args_list:
            self.assertNotIn(secret, str(call.args))
        self.assertEqual(self.p['credential_reference']['path'], '/run/benchmark-runner/token')

    def test_image_expiry_requires_ownership_age_no_references_and_no_pin(self):
        ident = 'sha256:' + 'd' * 64
        calls = []
        def docker(profile, *args, **kwargs):
            calls.append(args)
            if args[:2] == ('image', 'ls'): return ident.encode()
            if args[:2] == ('image', 'inspect'):
                return h.canonical([{'Created': '2000-01-01T00:00:00Z', 'Config': {'Labels': {
                    'ai4r.owner': self.p['project'], 'ai4r.deployment': self.p['deployment_id']}}}])
            return b''
        with patch.object(h, 'docker', docker):
            self.assertEqual(h.gc_images(self.p, True)['eligible'], [ident])
            self.assertFalse(any(args[:2] == ('image', 'rm') for args in calls))
            self.assertEqual(h.gc_images(self.p)['removed'], [ident])
            self.p['image_pins'] = [ident]
            self.assertEqual(h.gc_images(self.p)['eligible'], [])
        self.assertFalse(any('prune' in args or '--force' in args for args in calls))

    def test_timer_installs_exact_repo_code_and_reports_unavailable_manager(self):
        source = (ai4r.HERE / 'operator_host.py').read_text()
        with patch.object(h.Path, 'home', return_value=self.base), patch.object(h, 'run', side_effect=ValueError('no user manager')):
            result = h.install_timer(self.p, source)
        self.assertFalse(result['installed'])
        installed = self.base / '.local/lib/ai4r' / result['source_sha256'] / 'operator_host.py'
        self.assertEqual(installed.read_text(), source)

    def test_app_idle_probe_is_read_only_and_rejects_ordinary_active_runs(self):
        import sqlite3
        state = self.base / 'app'; executor = self.base / 'executor'
        fixtures = [(state / 'state/research.sqlite3', 'runs'),
                    (executor / 'ledger/claims.sqlite3', 'claims'),
                    (executor / 'attempts/attempts.sqlite3', 'leases')]
        for path, table in fixtures:
            path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(path); db.execute('CREATE TABLE ' + table + '(state TEXT)'); db.commit(); db.close()
        before = {str(path): path.read_bytes() for path, table in fixtures}
        command = [sys.executable, '-c', h.IDLE_PROBE, str(state), str(executor)]
        result = subprocess.run(command, capture_output=True, check=True)
        self.assertTrue(json.loads(result.stdout)['idle'])
        self.assertEqual(before, {str(path): path.read_bytes() for path, table in fixtures})
        db = sqlite3.connect(fixtures[0][0]); db.execute("INSERT INTO runs VALUES ('running')"); db.commit(); db.close()
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_stop_refuses_live_app_work_even_without_benchmark_campaign(self):
        (Path(self.p['root']) / 'compose.json').write_text('{}')
        def compose(profile, *args, **kwargs):
            if args[:2] == ('ps', '-aq'): return b'container'
            if args[0] == 'exec': raise ValueError('ordinary research job is active')
            raise AssertionError('Stop must not be reached')
        observed = [{'State': {'Running': True}, 'Config': {'Labels': {'ai4r.deployment': self.p['deployment_id']}}}]
        with patch.object(h, 'compose', compose), patch.object(h, 'docker', return_value=h.canonical(observed)):
            with self.assertRaises(ValueError): self.request('stop')


if __name__ == '__main__':
    unittest.main()
