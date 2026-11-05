"""Application lifecycle adapter. Uses the same host/store/material identities as calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid


class Applications:
    def __init__(self, host, core):
        self.host, self.core = host, core
        self.processes = {}
        with host.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS instances (id TEXT PRIMARY KEY, key TEXT UNIQUE, fingerprint TEXT, record TEXT)')

    def process_api(self):
        try:
            import psutil
            return psutil
        except ImportError as error:
            raise self.core.CCError('UNSUPPORTED_BINDING', 'Process inspection unavailable; install requirements-services.txt for service execution') from error

    def get(self, instance):
        with self.host.db() as db:
            row = db.execute('SELECT record FROM instances WHERE id=?', (instance,)).fetchone()
        self.core.require(row is not None, 'UNKNOWN_INSTANCE', instance)
        return json.loads(row[0])

    def lookup(self, key):
        with self.host.db() as db:
            row = db.execute('SELECT record FROM instances WHERE key=?', (key,)).fetchone()
        self.core.require(row is not None, 'UNKNOWN_INSTANCE', key)
        return json.loads(row[0])

    def save(self, record):
        with self.host.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT record FROM instances WHERE id=?', (record['id'],)).fetchone()
            current = json.loads(current[0]) if current else None
            if current and current['state'] in {'stopped', 'failed'} and record['state'] not in {current['state']}:
                current.setdefault('late_observations', []).append({'state': record['state'], 'readiness': record['readiness'], 'recorded': time.time()})
                current['diagnostics'].extend(d for d in record['diagnostics'] if d not in current['diagnostics'])
                record = current
            db.execute('UPDATE instances SET record=? WHERE id=?', (json.dumps(record), record['id']))
        return record

    def launch(self, record, callback):
        # Serialize spawn/identity persistence with stop/reconciliation, so a
        # canceled preparing instance cannot launch after it was reconciled.
        with self.host.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current = json.loads(db.execute('SELECT record FROM instances WHERE id=?', (record['id'],)).fetchone()[0])
            self.core.require(current['state'] == 'preparing', 'INSTANCE_NOT_STARTABLE', 'Instance was stopped/reconciled before spawn')
            callback()
            record['state'] = 'running'
            db.execute('UPDATE instances SET record=? WHERE id=?', (json.dumps(record), record['id']))

    def reconcile(self, instance, *, stopped, note):
        self.core.require(stopped is True and isinstance(note, str) and note.strip(), 'RECONCILIATION_REQUIRED', 'Confirm stop and describe observed effects')
        with self.host.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT record FROM instances WHERE id=?', (instance,)).fetchone()
            self.core.require(row is not None, 'UNKNOWN_INSTANCE', instance)
            record = json.loads(row[0])
            self.core.require(record['state'] in {'unknown', 'preparing', 'exited'}, 'INVALID_STATE', 'Inspect or stop known running instances normally')
            record.setdefault('reconciliations', []).append({'previous_state': record['state'], 'stopped': True, 'note': note, 'recorded': time.time()})
            record.update(state='stopped', readiness='not_ready')
            db.execute('UPDATE instances SET record=? WHERE id=?', (json.dumps(record), instance))
        return record

    @staticmethod
    def free_port():
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            return listener.getsockname()[1]

    @staticmethod
    def docker(*arguments):
        try:
            return subprocess.run(['docker', *arguments], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as error:
            return subprocess.CompletedProcess(['docker', *arguments], 1, '', str(error))

    def start(self, release, name, inputs, key=None, grants=None, timeout=15):
        psutil = self.process_api()
        c, host = self.core, self.host
        declaration, bundle = host.release(release)
        c.require(name in c.service_entries(declaration), 'NOT_SERVED_CAPABILITY', name)
        c.require(isinstance(inputs, dict), 'INVALID_INPUT', 'Service setup inputs must be a port map')
        c.require(isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and 0 < timeout <= 3600, 'INVALID_LIMIT', 'Startup timeout must be 0..3600 seconds')
        app = c.service_entries(declaration)[name]
        binding = declaration['bindings'][app['using']]
        grants = host.grant_list((set(app['changes']) & set(host.session_grants or [])) if grants is None else grants)
        c.require(set(grants) <= set(app['changes']), 'UNDECLARED_EFFECT', 'Grant exceeds selected application')
        c.require(host.session_grants is None or set(grants) <= set(host.session_grants), 'DENIED', 'Grant exceeds session')
        c.require(set(app['changes']) <= set(grants), 'DENIED', 'Application effects need authorization')
        c.require('process.exec' in grants, 'DENIED', 'Starting a persistent application requires process.exec')
        c.require(not app['interfaces'] or 'network.listen' in grants, 'DENIED', 'Interfaces require network.listen')
        c.require(not set(app['needs']) - {'python'}, 'UNSUPPORTED_REQUIREMENT', 'Reference applications support the Python host; qualify other providers explicitly')
        if binding['kind'] == 'image' and app['interfaces']:
            c.require('network.request' in grants, 'UNSUPPORTED_NETWORK_POLICY', 'Basic Docker bridge exposes egress; authorize network.request or use an enforcing network provider')
        key = key or str(uuid.uuid4())
        c.require(isinstance(key, str) and key and len(key) <= 256, 'INVALID_KEY', 'A bounded host key is required')
        fingerprint = c.sha(c.encoded({'release': release, 'capability': name, 'inputs': inputs, 'grants': grants, 'timeout': timeout}))
        with host.db() as db:
            previous = db.execute('SELECT fingerprint,record FROM instances WHERE key=?', (key,)).fetchone()
        if previous:
            c.require(previous[0] == fingerprint, 'KEY_CONFLICT', 'An instance key cannot change its deployment')
            return json.loads(previous[1])
        c.require(set(inputs) <= set(app['takes']), 'INVALID_INPUT', 'Unknown application input')
        for port, definition in app['takes'].items():
            spec = c.port(definition, declaration['defs'])
            c.require(spec['optional'] or port in inputs, 'INVALID_INPUT', 'Missing application input: ' + port)
            if port in inputs:
                c.require(spec['kind'] != 'handle', 'UNSUPPORTED_RESOURCE', 'Live/device handles require a qualified deployment provider')
                host.validate_value(spec, inputs[port])
        record = {'format': 'cc-instance/2', 'id': str(uuid.uuid4()), 'key': key, 'release': release, 'capability': name,
                  'state': 'preparing', 'readiness': 'not_checked', 'endpoints': {}, 'identity': {}, 'inputs': deepcopy(inputs),
                  'effects': {'declared': app['changes'], 'granted': grants, 'assurance': 'trusted_local' if binding['kind'] == 'native' else 'container',
                              'limits': 'Native process-tree observation is not OS isolation; readiness is not semantic correctness'},
                  'provenance': {'binding': binding, 'started': time.time()}, 'diagnostics': []}
        record['provenance']['owner'] = {'pid': os.getpid(), 'created': psutil.Process(os.getpid()).create_time()}
        with host.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT fingerprint,record FROM instances WHERE key=?', (key,)).fetchone()
            if previous:
                c.require(previous[0] == fingerprint, 'KEY_CONFLICT', 'An instance key cannot change its deployment')
                return json.loads(previous[1])
            db.execute('INSERT INTO instances VALUES (?,?,?,?)', (record['id'], key, fingerprint, json.dumps(record)))
        directory = host.store / 'instances' / record['id']
        indir = directory / 'in'
        record['logs'] = {'stdout': str(directory/'stdout.log'), 'stderr': str(directory/'stderr.log')}
        values = {}
        try:
            directory.mkdir(parents=True)
            indir.mkdir()
            for port, value in inputs.items():
                spec = c.port(app['takes'][port], declaration['defs'])
                if spec['kind'] == 'text':
                    values[port] = value
                else:
                    target = indir / port
                    if spec['kind'] == 'artifact':
                        import shutil
                        shutil.copyfile(host.artifact_path(value), target)
                        c.require(c.file_sha(target) == value['sha256'], 'DIGEST_MISMATCH', port)
                    else:
                        target.write_bytes(c.encoded(value))
                    values[port] = str(target) if binding['kind'] == 'native' else '/cc/in/' + port
            command = list(binding['command'])
            ports = {}
            for interface, definition in app['interfaces'].items():
                dynamic = any('{port.' + interface + '}' in arg for arg in command)
                ports[interface] = self.free_port() if binding['kind'] == 'native' and dynamic else definition['port']
            import re
            substitutions = {'python': host.python, 'bundle': str(bundle) if binding['kind'] == 'native' else '/cc/bundle'}
            substitutions.update({'input.' + key: value for key, value in values.items()})
            substitutions.update({'port.' + key: str(value) for key, value in ports.items()})
            def substitute(match):
                c.require(match[1] in substitutions, 'UNRESOLVED_REFERENCE', 'Unknown launch placeholder: ' + match[1])
                return substitutions[match[1]]
            # Parse the authored command once; inserted input text is never reparsed.
            command = [re.sub(r'\{(python|bundle|input\.[^}]+|port\.[^}]+)\}', substitute, arg) for arg in command]
            if 'provenance' in declaration:
                record['provenance']['build_record'] = host.put_artifact(c.contained(bundle, declaration['provenance']))
            def spawn():
                nonlocal ports
                if binding['kind'] == 'native':
                    self.spawn_native(record, binding, bundle, app, command, directory)
                else:
                    self.spawn_image(record, binding, app, command, bundle, indir, grants, ports)
                record['provenance']['command'] = command
                record['endpoints'] = {name: 'http://127.0.0.1:' + str(ports[name]) + definition['path'] for name, definition in app['interfaces'].items()}
            self.launch(record, spawn)
            self.save(record)
            if 'ready' in app:
                interface = app['ready']['interface']
                url = 'http://127.0.0.1:' + str(ports[interface]) + app['ready']['path']
                deadline = time.monotonic() + timeout
                class NoRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, *args, **kwargs): return None
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
                while time.monotonic() < deadline:
                    current = self.inspect(record['id'])
                    c.require(current['state'] == 'running', 'START_FAILED', 'Application exited or was stopped before readiness')
                    try:
                        with opener.open(url, timeout=min(0.5, max(0.05, deadline-time.monotonic()))) as response:
                            if 200 <= response.status < 300:
                                record['readiness'] = 'ready'
                                break
                    except (urllib.error.URLError, TimeoutError, OSError):
                        time.sleep(0.03)
                c.require(record['readiness'] == 'ready', 'READINESS_TIMEOUT', 'Startup health endpoint did not become ready')
            return self.save(record)
        except Exception as error:
            record['diagnostics'].append({'code': getattr(error, 'code', 'START_FAILED'), 'message': str(error)})
            self.save(record)
            if record['identity']:
                try:
                    return self.stop(record['id'], _failed=True)
                except Exception:
                    record['state'] = 'unknown'
            else:
                owned = self.processes.pop(record['id'], None)
                if owned is not None:
                    owned.terminate(); owned.wait(timeout=3)
                record['state'] = 'failed'
            record['readiness'] = 'failed'
            return self.save(record)

    def spawn_native(self, record, binding, bundle, app, command, directory):
        psutil = self.process_api()
        host, c = self.host, self.core
        manifest = json.loads((bundle.parent/'manifest.json').read_bytes())
        executable = host.bound_executables(record['release'], app['using'])[app['using']]
        if '{bundle}' not in binding['command'][0]:
            command[0] = executable['path']
        record['provenance']['executable_sha256'] = c.file_sha(command[0])
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        with Path(record['logs']['stdout']).open('wb') as out, Path(record['logs']['stderr']).open('wb') as err:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err, cwd=directory,
                                       env=dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1'), **flags)
        self.processes[record['id']] = process
        record['identity'] = {'kind': 'native', 'pid': process.pid, 'created': psutil.Process(process.pid).create_time()}

    def spawn_image(self, record, binding, app, command, bundle, indir, grants, ports):
        c = self.core
        cname = 'cc-app-' + record['id']
        record['identity'] = {'kind': 'image', 'container': cname}
        docker = ['run', '--detach', '--pull=never', '--name', cname, '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                  '--tmpfs', '/tmp', '--mount', f'type=bind,src={bundle},dst=/cc/bundle,readonly',
                  '--mount', f'type=bind,src={indir},dst=/cc/in,readonly']
        if 'network.request' not in grants:
            docker += ['--network', 'none']
        for interface, definition in app['interfaces'].items():
            docker += ['--publish', f'127.0.0.1::{definition["port"]}']
        result = self.docker(*docker, binding['image'], *command)
        c.require(result.returncode == 0, 'START_FAILED', result.stderr)
        record['identity']['container_id'] = result.stdout.strip()
        state = self.docker('inspect', cname)
        c.require(state.returncode == 0, 'EXECUTION_UNKNOWN', 'Cannot identify started container')
        inspected = json.loads(state.stdout)[0]
        for interface, definition in app['interfaces'].items():
            mapping = inspected['NetworkSettings']['Ports'][str(definition['port']) + '/tcp']
            ports[interface] = int(mapping[0]['HostPort'])
        record['provenance']['image_id'] = inspected['Image']

    def inspect(self, instance):
        record = self.get(instance)
        if record['state'] == 'preparing':
            psutil = self.process_api()
            owner = record['provenance']['owner']
            try:
                alive = abs(psutil.Process(owner['pid']).create_time()-owner['created']) < 0.001
            except psutil.NoSuchProcess:
                alive = False
            except psutil.AccessDenied:
                record['state'] = 'unknown'
                record['diagnostics'].append({'code': 'EXECUTION_UNKNOWN', 'message': 'Cannot inspect startup owner'})
                return self.save(record)
            if not alive:
                record['state'] = 'unknown'
                record['diagnostics'].append({'code': 'EXECUTION_UNKNOWN', 'message': 'Preparing host exited before execution identity was committed'})
                return self.save(record)
        if record['state'] != 'running':
            return record
        identity = record['identity']
        if identity['kind'] == 'native':
            psutil = self.process_api()
            try:
                process = psutil.Process(identity['pid'])
                alive = abs(process.create_time()-identity['created']) < 0.001 and process.is_running() and process.status() != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                alive = False
            except psutil.AccessDenied:
                record['state'] = 'unknown'
                record['diagnostics'].append({'code': 'EXECUTION_UNKNOWN', 'message': 'Cannot inspect application process'})
                return self.save(record)
        else:
            result = self.docker('inspect', identity.get('container_id', identity['container']))
            if result.returncode != 0:
                record['state'] = 'unknown'
                record['diagnostics'].append({'code': 'EXECUTION_UNKNOWN', 'message': 'Container state unavailable'})
                return self.save(record)
            alive = json.loads(result.stdout)[0]['State']['Running']
            self.image_logs(record)
        if not alive:
            owned = self.processes.get(instance)
            if owned is not None and owned.poll() is not None:
                self.processes.pop(instance)
            record.update(state='exited', readiness='not_ready')
            return self.save(record)
        return record

    def image_logs(self, record):
        result = self.docker('logs', record['identity'].get('container_id', record['identity']['container']))
        if result.returncode == 0:
            for stream in ('stdout', 'stderr'):
                Path(record['logs'][stream]).write_text(getattr(result, stream), encoding='utf-8')
        else:
            record['diagnostics'].append({'code': 'LOGS_UNAVAILABLE', 'message': 'Container logs could not be collected'})

    def stop(self, instance, _failed=False):
        record = self.get(instance)
        if record['state'] == 'stopped' or (record['state'] == 'failed' and 'stopped' in record['provenance']):
            return record
        identity = record['identity']
        self.core.require(bool(identity), 'STOP_UNCONFIRMED', 'No execution identity; reconcile before retry')
        if identity['kind'] == 'native':
            psutil = self.process_api()
            try:
                process = psutil.Process(identity['pid'])
                self.core.require(abs(process.create_time()-identity['created']) < 0.001, 'INSTANCE_REPLACED', 'PID generation differs; refusing to stop another process')
                observed = process.children(recursive=True) + [process]
                for child in observed:
                    try: child.terminate()
                    except psutil.NoSuchProcess: pass
                _, alive = psutil.wait_procs(observed, timeout=3)
                for child in alive:
                    try: child.kill()
                    except psutil.NoSuchProcess: pass
                _, alive = psutil.wait_procs(alive, timeout=3)
                self.core.require(not alive, 'STOP_UNCONFIRMED', 'Observed processes remain alive')
            except psutil.NoSuchProcess:
                owned = self.processes.get(instance)
                if owned is not None and owned.poll() is not None:
                    self.processes.pop(instance)
                record['state'] = 'unknown'
                record['diagnostics'].append({'code': 'STOP_UNCONFIRMED', 'message': 'Foreground leader exited; child cessation is not established. Inspect and reconcile.'})
                self.save(record)
                raise self.core.CCError('STOP_UNCONFIRMED', 'Foreground leader exited; inspect descendants and reconcile before confirming stop')
            if instance in self.processes:
                self.processes.pop(instance).wait(timeout=1)
        else:
            self.image_logs(record)
            result = self.docker('rm', '--force', identity.get('container_id', identity['container']))
            self.core.require(result.returncode == 0, 'STOP_UNCONFIRMED', result.stderr)
        record.update(state='failed' if _failed else 'stopped', readiness='not_ready')
        record['provenance']['stopped'] = time.time()
        return self.save(record)
