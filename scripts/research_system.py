"""Bounded host controller for identified M1 foundation procedures.

Native plans own procedures. This driver owns only task-scoped Docker controller
jobs, refreshes finite observations, retains raw evidence, and never grants a
pass for missing resources, development targets, zero cases or required skips.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

try:
    from scripts.research_candidate import DEFAULT_SCOPE, capture_candidate, verify_candidate
    from scripts.research_foundation import (CHECKS, HOST_KINDS, JOIN_KEYS, FoundationBlocked, digest,
                                             json_bytes, manifests, read_pin, read_regular, validate_profile)
    from scripts.research_reports import parse_native, source_identity, validate_receipt
    from scripts.research_foundation_host import enrich_observations
    from scripts.research_image_closure import inspect_closure
except ModuleNotFoundError:
    from research_candidate import DEFAULT_SCOPE, capture_candidate, verify_candidate
    from research_foundation import (CHECKS, HOST_KINDS, JOIN_KEYS, FoundationBlocked, digest,
                                     json_bytes, manifests, read_pin, read_regular, validate_profile)
    from research_reports import parse_native, source_identity, validate_receipt
    from research_foundation_host import enrich_observations
    from research_image_closure import inspect_closure


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, value):
    with Path(path).open('xb') as handle:
        handle.write(value if isinstance(value, bytes) else json_bytes(value))


def linux_path(path):
    if os.name == 'nt' and str(path).startswith('/') and '\\' not in str(path):
        from pathlib import PurePosixPath
        if '..' in PurePosixPath(path).parts:
            raise FoundationBlocked('LOCAL_WSL_PATH_REQUIRED')
        return str(path)
    path = str(Path(path).resolve())
    if os.name == 'nt':
        match = re.fullmatch(r'([A-Za-z]):[\\/](.*)', path)
        if not match:
            raise FoundationBlocked('LOCAL_WSL_PATH_REQUIRED')
        return '/mnt/' + match[1].lower() + '/' + match[2].replace('\\', '/')
    return path


class DockerHost:
    """Only this process sees local Docker; evaluated/controller code never does."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.prefix = (['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', linux_path(root), '--exec', 'docker']
                       if os.name == 'nt' else ['docker']) + ['--context', 'default']
        self.commands = []

    def run(self, arguments, *, timeout=30, check=True, env=None):
        command = self.prefix + list(arguments)
        # Arguments come exclusively from fixed procedures and validated local
        # identities. Profiles never supply programs, shell syntax or selectors.
        self.commands.append(command)
        try:
            result = subprocess.run(command, cwd=self.root, capture_output=True, timeout=timeout,
                                    env={**os.environ, **(env or {})}, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise FoundationBlocked('LOCAL_DOCKER_UNAVAILABLE_OR_TIMEOUT') from None
        if check and result.returncode:
            raise FoundationBlocked('LOCAL_DOCKER_OPERATION_FAILED')
        return result

    def json(self, arguments):
        try:
            return json.loads(self.run(arguments).stdout)
        except (ValueError, TypeError):
            raise FoundationBlocked('LOCAL_DOCKER_OBSERVATION_INVALID') from None


def controller_secret(host, path, job_id):
    """Read only the named controller grant, never application/provider auth.

    Windows drives do not establish Linux mode custody. The Windows host driver
    can consume a root-owned Linux tmp grant through fixed WSL stat/dd programs;
    secret bytes stay in process memory and are never emitted by the driver.
    """
    if os.name != 'nt' or not str(path).startswith('/'):
        return read_regular(path, private=True, maximum=4096)
    from pathlib import PurePosixPath
    supplied = PurePosixPath(path)
    expected_parent = PurePosixPath('/tmp/ai4r-foundation-private') / job_id
    if supplied.parent != expected_parent or supplied.name not in {'token', 'bootstrap-challenge'}:
        raise FoundationBlocked('FIXED_LINUX_CONTROLLER_SECRET_PATH_REQUIRED')
    prefix = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--exec']
    for item in (supplied, expected_parent, expected_parent.parent):
        command = prefix + ['/usr/bin/stat', '--format=%a:%u:%h:%s:%F', '--', str(item)]
        host.commands.append(command)
        result = subprocess.run(command, capture_output=True, timeout=10, check=False)
        fields = result.stdout.decode('ascii', errors='strict').strip().split(':')
        if result.returncode or len(fields) != 5:
            raise FoundationBlocked('LINUX_CONTROLLER_SECRET_CUSTODY')
        mode, uid, links, size, kind = fields
        if uid != '0' or (item == supplied and (mode != '600' or links != '1' or not 0 < int(size) <= 4096 or kind != 'regular file')):
            raise FoundationBlocked('LINUX_CONTROLLER_SECRET_CUSTODY')
        if item != supplied and (mode != '700' or kind != 'directory'):
            raise FoundationBlocked('LINUX_CONTROLLER_SECRET_CUSTODY')
    command = prefix + ['/bin/dd', 'if=' + str(supplied), 'iflag=nofollow', 'bs=4097', 'count=1', 'status=none']
    # Do not put this command's output in any diagnostic or command transcript.
    host.commands.append(command)
    result = subprocess.run(command, capture_output=True, timeout=10, check=False)
    if result.returncode or not 0 < len(result.stdout) <= 4096:
        raise FoundationBlocked('LINUX_CONTROLLER_SECRET_READ')
    return result.stdout


def fresh_observations(host, profile):
    joins = {key: profile[key] for key in JOIN_KEYS}
    receipts = {kind: {'schema': 'ai4r-foundation-host-receipt:1', 'kind': kind, **joins, 'observed_at': now(),
                       'qualified': False, 'observations': {}, 'limitations': ['Full required actual procedure has not been observed.']}
                for kind in HOST_KINDS}
    context = host.json(['context', 'inspect', 'default'])
    if len(context) != 1 or context[0].get('Endpoints', {}).get('docker', {}).get('Host') != 'unix:///var/run/docker.sock':
        raise FoundationBlocked('LOCAL_UNIX_DOCKER_REQUIRED')
    ids = host.run(['ps', '--all', '--filter', 'label=com.docker.compose.project=' + profile['project'],
                    '--filter', 'label=com.docker.compose.service=app', '--format', '{{.ID}}']).stdout.decode().split()
    if len(ids) != 1 or not re.fullmatch(r'[a-f0-9]{12,64}', ids[0]):
        raise FoundationBlocked('ONE_IDENTIFIED_APP_REQUIRED')
    container_id = ids[0]
    rows = host.json(['inspect', container_id])
    if len(rows) != 1:
        raise FoundationBlocked('ONE_IDENTIFIED_APP_REQUIRED')
    container = rows[0]
    labels = container.get('Config', {}).get('Labels', {})
    if labels.get('com.docker.compose.project') != profile['project'] or labels.get('com.docker.compose.service') != 'app':
        raise FoundationBlocked('APP_OWNERSHIP_CHANGED')
    image_id = container.get('Image')
    images = host.json(['image', 'inspect', image_id])
    if len(images) != 1:
        raise FoundationBlocked('APP_IMAGE_UNAVAILABLE')
    image = images[0]
    actual_platform = image.get('Os', '') + '/' + image.get('Architecture', '')
    image_match = image_id == profile['image_id'] and actual_platform == profile['platform'] and container['Config'].get('Image') == profile['image_ref']
    running = container.get('State', {}).get('Running') is True
    mounts = container.get('Mounts', [])
    # Development source mounts invalidate an installed-image closure claim.
    code_mounts = [m.get('Destination') for m in mounts if m.get('Destination', '').startswith(('/opt/ai4r', '/opt/venv', '/usr/local'))]
    actual_config, image_config = container.get('Config', {}), image.get('Config', {})
    frozen_entrypoint = (actual_config.get('Entrypoint') == image_config.get('Entrypoint')
                         and actual_config.get('Cmd') == image_config.get('Cmd'))
    receipts['image'].update(qualified=bool(image_match and running and not code_mounts and frozen_entrypoint), observations={
        'actual_image_id': image_id, 'actual_platform': actual_platform, 'running': running,
        'installed_image_only': not code_mounts and frozen_entrypoint, 'frozen_entrypoint': frozen_entrypoint, 'same_candidate_closure': False,
        'both_architectures': False, 'locked_closure': False}, limitations=[
        'Single running image inspection does not establish both architecture builds or source-to-installed candidate equality.'])
    bindings = container.get('NetworkSettings', {}).get('Ports', {})
    published = []
    for internal, values in bindings.items():
        for item in values or []:
            published.append({'container_port': internal, 'host_ip': item.get('HostIp'), 'host_port': item.get('HostPort')})
    from urllib.parse import urlsplit
    origin = urlsplit(profile['origin'])
    private_only = len(published) == 1 and published[0] == {'container_port': '5173/tcp', 'host_ip': origin.hostname, 'host_port': str(origin.port)}
    forbidden_mounts = any(m.get('Destination', '').startswith(('/var/run/docker.sock', '/hidden-fixtures', '/var/lib/ai4r-referee', '/var/lib/ai4r-rsi/custodian')) for m in mounts)
    broad_home = any(m.get('Destination') in {'/', '/root', '/home', '/opt', '/usr', '/var', '/var/lib'}
                     or (m.get('Type') == 'bind' and re.fullmatch(r'/(?:root|home/[^/]+|mnt/[a-z]/Users/[^/]+)/?', m.get('Source', '')))
                     for m in mounts)
    receipts['ports'].update(qualified=True, observations={'published': published, 'approved_private_only': private_only,
                                                          'no_internal_ports': private_only and not forbidden_mounts,
                                                          'no_broad_home': not broad_home and not forbidden_mounts}, limitations=[])
    if running:
        boot_result = host.run(['exec', '--user', '10001:10001', container_id, '/bin/cat', '/run/ai4r/instance.json'])
        try:
            boot_record = json.loads(boot_result.stdout)
        except ValueError:
            raise FoundationBlocked('ACTUAL_BOOT_IDENTITY_UNAVAILABLE') from None
        build_result = host.run(['exec', '--user', '10001:10001', container_id, '/opt/venv/bin/python', '-c',
            "import json;from pathlib import Path;print(json.loads(Path('/usr/local/share/ai4r-build-identity.json').read_bytes())['build_id'])"])
        actual_build = build_result.stdout.decode('ascii').strip()
        if boot_record.get('boot_id') != profile['instance_id'] or actual_build != profile['build_id']:
            raise FoundationBlocked('ACTUAL_BOOT_OR_BUILD_IDENTITY_MISMATCH')
        receipts['image']['observations'].update(actual_build_id=actual_build, actual_instance_id=boot_record['boot_id'])
        result = host.run(['exec', '--user', '10001:10001', container_id, '/opt/venv/bin/jiuwenswarm-start', '--status'], check=False)
        try:
            status = json.loads(result.stdout) if result.returncode == 0 else {}
        except ValueError:
            status = {}
        panes = status.get('panes', [])
        fixed = (status.get('running') is True and len(panes) == 3 and {p.get('role') for p in panes} == {'agentserver', 'gateway', 'frontend'}
                 and all(p.get('running') is True and re.fullmatch(r'%\d+', p.get('pane', '')) for p in panes))
        receipts['tmux'].update(qualified=True, observations={'fixed_owned_panes': fixed, 'panes': panes,
                                                            'attach_detach_preserves': False, 'fault_logs_no_replay': False, 'authority_unchanged': False},
                                limitations=['Status inspection is not an actual PTY attach/detach or deliberate owned service fault.'])
        receipts['startup']['observations'] = {'running': fixed, 'native_surfaces': False, 'invalid_config_cases': False,
            'planted_fixture_denied': False, 'fixed_route_without_optional': False, 'blocked_execution_observed': False,
            'websocket_auth_matrix': False, 'revoked_http_ws': False}
    # Counts cannot be inferred from filtered configuration or absence of ports.
    receipts['channels']['limitations'] = ['Actual startup constructor and outbound-attempt trace is required; configuration filtering alone is insufficient.']
    receipts['operations']['limitations'] = ['This inspection run did not build/start/export/cleanup the target or exercise sentinel/redaction fixtures.']
    receipts['native_platform']['limitations'] = ['No physical GB10 or independent arm64 build/emulation qualification was executed.']
    receipts['child_checks']['limitations'] = ['No current exact-candidate full child SYSTEM population was supplied and independently reconciled.']
    return receipts, container_id


def native_context(root, check_id):
    program = Path(root) / 'docs/code/Missions/M1'
    feature = program / check_id.split('/')[0]
    native = parse_native(feature)
    if check_id not in native['checks'] or native['diagnostics']:
        raise FoundationBlocked('NATIVE_PROCEDURE_OR_COVERAGE_UNAVAILABLE')
    source_sha, changed = source_identity(root, program)
    if changed:
        raise FoundationBlocked('SUPPLIED_SOURCE_CHANGED')
    interfaces, owners = {}, {}
    for line in (program / 'TASKS.md').read_text(encoding='utf-8-sig').splitlines():
        match = re.match(r'^\|\s*(M1-IF-\d{3})\s*/\s*(r\d+)\s*\|', line)
        if match:
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            interfaces[match[1]], owners[match[1]] = match[2], cells[2]
    pins = dict(native['native_pins'])
    check = native['checks'][check_id]
    for interface in set(re.findall(r'M1-IF-\d{3}', check['source_row'])):
        owner = owners[interface]
        pins[owner + '/TASK.md'] = digest((program / owner / 'TASK.md').read_bytes())
    return check, source_sha, interfaces, pins


def junit_result(raw, required_cases):
    try:
        document = ET.fromstring(raw)
        cases = list(document.iter('testcase'))
        observed = [c.get('classname', '') + '::' + c.get('name', '') for c in cases]
        return (bool(cases) and len(observed) == len(set(observed)) and set(required_cases) <= set(observed)
                and not any(c.find(k) is not None for c in cases for k in ('failure', 'error', 'skipped'))
                and not any(int(s.get(k, '0')) for s in document.iter() if s.tag in {'testsuite', 'testsuites'} for k in ('failures', 'errors', 'skipped')))
    except (ValueError, ET.ParseError):
        return False


def validate_candidate(root, candidate, profile):
    identity = {key: candidate[key] for key in ('schema_version', 'base_head', 'scope', 'files')}
    recomputed = digest(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode())
    if recomputed != candidate['candidate_id'] or candidate['candidate_id'] != profile['candidate_id'] or verify_candidate(root, candidate):
        raise FoundationBlocked('CURRENT_TARGET_CANDIDATE_REQUIRED')
    if profile['mode'] == 'qualified_foundation' and tuple(candidate['scope']) != tuple(DEFAULT_SCOPE):
        raise FoundationBlocked('QUALIFIED_FOUNDATION_REQUIRES_FULL_PRODUCT_AND_HARNESS_CLOSURE')


def run(arguments):
    root = Path(arguments.root).resolve()
    output = Path(arguments.evidence_dir).resolve()
    if output.exists():
        raise FoundationBlocked('EVIDENCE_IDENTITY_ALREADY_EXISTS')
    output.mkdir(parents=True)
    started = now()
    receipt = {'schema': 'm1-verification-result:1', 'check_id': arguments.check, 'outcome': 'BLOCKED',
               'reason': 'Required controlled target resources are unavailable.', 'started_at': started}
    host = DockerHost(root)
    controller_name = None
    controller_issued = False
    try:
        if arguments.check not in CHECKS:
            raise FoundationBlocked('CHECK_REQUIRES_ITS_REGISTERED_REAL_STUDY_CONTROLLER; no foundation substitution is permitted')
        if not re.fullmatch(r'ai4r-verify-[a-z0-9][a-z0-9-]{1,70}', arguments.project):
            raise FoundationBlocked('OWNED_CONTROLLER_PROJECT_REQUIRED')
        for path, expected in [(arguments.compose, 'deploy/m1/compose.yaml'), (arguments.verify_override, 'deploy/m1/compose.verify.yaml')]:
            if Path(path).resolve() != root / expected:
                raise FoundationBlocked('FIXED_COMPOSE_BINDING_REQUIRED')
        if not arguments.verify_image or not re.fullmatch(r'ai4r-[a-z0-9-]+(?::[A-Za-z0-9_.-]+|@sha256:[a-f0-9]{64})', arguments.verify_image):
            raise FoundationBlocked('EXPLICIT_QUALIFIED_CONTROLLER_IMAGE_REQUIRED')
        raw_profile = read_regular(arguments.profile_file)
        profile = validate_profile(json.loads(raw_profile))
        redacted_profile = {key: value for key, value in profile.items() if key not in {'auth', 'host_receipts', 'fixture_manifest', 'assertion_manifest'}}
        redacted_profile['auth'] = {key: bool(value) for key, value in profile['auth'].items()}
        redacted_profile['original_profile_sha256'] = digest(raw_profile)
        write_new(output / 'target-profile.redacted.json', redacted_profile)
        if arguments.check not in profile['check_ids'] or arguments.project == profile['project']:
            raise FoundationBlocked('TARGET_CHECK_OR_CONTROLLER_SCOPE')
        controller_name = arguments.project + '-controller'
        occupied = host.run(['ps', '--all', '--filter', 'name=^/' + controller_name + '$', '--format', '{{.ID}}']).stdout.strip()
        if occupied:
            raise FoundationBlocked('CONTROLLER_NAME_ALREADY_EXISTS')
        check, source_sha, interfaces, pins = native_context(root, arguments.check)
        expected_fixture, expected_assertion = manifests(arguments.check, check['procedure_sha256'], source_sha)
        if read_pin(profile['fixture_manifest']) != expected_fixture or read_pin(profile['assertion_manifest']) != expected_assertion:
            raise FoundationBlocked('FROZEN_ASSERTION_OR_FIXTURE_POPULATION_MISMATCH')
        candidate = json.loads(read_regular(arguments.candidate)) if arguments.candidate else capture_candidate(root)
        validate_candidate(root, candidate, profile)
        write_new(output / 'candidate-manifest.json', candidate)
        observations, container_id = fresh_observations(host, profile)
        image_input = read_pin(profile['host_receipts']['image'])
        source_build_pin = image_input.get('observations', {}).get('source_build_receipt')
        if source_build_pin:
            if (image_input.get('schema') != 'ai4r-foundation-host-receipt:1' or image_input.get('kind') != 'image'
                    or any(image_input.get(key) != profile[key] for key in JOIN_KEYS)):
                raise FoundationBlocked('FROZEN_IMAGE_INPUT_JOIN_MISMATCH')
            closure = inspect_closure(host, profile, source_build_pin, output)
            valid = bool(closure['qualified'] and closure.get('source_baseline_sha256') == source_sha
                         and observations['image']['qualified'] and observations['image']['observations'].get('installed_image_only'))
            closure['current_candidate_qualified'] = valid
            write_new(output / 'image-closure.json', closure)
            observations['image']['observations'].update(same_candidate_closure=valid, locked_closure=valid)
        if profile['mode'] == 'qualified_foundation' and not observations['image']['observations'].get('same_candidate_closure'):
            raise FoundationBlocked('INDEPENDENT_SOURCE_TO_INSTALLED_IMAGE_CLOSURE_REQUIRED; image ID alone is insufficient')
        observations = enrich_observations(host, profile, arguments.check, observations, container_id, output,
                                          source_build_pin=source_build_pin)
        controller_image = host.json(['image', 'inspect', arguments.verify_image])[0]
        controller_digest = controller_image.get('Id')
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', controller_digest or ''):
            raise FoundationBlocked('CONTROLLER_IMAGE_IDENTITY')
        write_new(output / 'assertion-manifest.json', expected_assertion)
        write_new(output / 'fixture-manifest.json', expected_fixture)
        with tempfile.TemporaryDirectory(prefix='ai4r-foundation-') as temporary:
            public = Path(temporary)
            derived = copy.deepcopy(profile)
            derived['host_receipts'] = {}
            for kind, value in observations.items():
                name = kind + '.json'
                raw = json_bytes(value)
                write_new(public / name, raw)
                write_new(output / name, raw)
                derived['host_receipts'][kind] = {'path': '/run/ai4r-foundation-public/' + name, 'sha256': digest(raw)}
            for key, value in [('fixture_manifest', expected_fixture), ('assertion_manifest', expected_assertion)]:
                name = key + '.json'
                raw = json_bytes(value)
                write_new(public / name, raw)
                derived[key] = {'path': '/run/ai4r-foundation-public/' + name, 'sha256': digest(raw)}
            private_mounts = []
            for key, name in [('token_file', 'token'), ('bootstrap_challenge_file', 'bootstrap-challenge')]:
                supplied = profile['auth'][key]
                derived['auth'][key] = None
                if supplied:
                    linux_private = os.name == 'nt' and str(supplied).startswith('/')
                    secret_path = str(supplied) if linux_private else Path(supplied).resolve()
                    if not linux_private and (secret_path.is_relative_to(root) or secret_path.is_relative_to(output)):
                        raise FoundationBlocked('CONTROLLER_SECRET_MUST_BE_OUTSIDE_CODE_AND_EVIDENCE')
                    controller_secret(host, secret_path, profile['job_id'])
                    destination = '/run/ai4r-foundation-private/' + name
                    private_mounts.append({'type': 'bind', 'source': linux_path(secret_path), 'target': destination, 'read_only': True,
                                           'bind': {'create_host_path': False}})
                    derived['auth'][key] = destination
            write_new(public / 'target.json', derived)
            override = {'services': {'app': {'image': arguments.verify_image, 'network_mode': 'host',
                'environment': {'AI4R_FOUNDATION_TARGET': '/run/ai4r-foundation-public/target.json',
                                'AI4R_FOUNDATION_OBSERVATIONS': '/evidence/controller-observations.json'},
                'volumes': [{'type': 'bind', 'source': linux_path(public), 'target': '/run/ai4r-foundation-public', 'read_only': True}, *private_mounts]}}}
            # Compose merge retains readonly code/evidence bindings; network list
            # is already reset by the fixed verification override.
            write_new(public / 'controller.compose.json', override)
            command = ['compose', '-p', arguments.project, '-f', linux_path(arguments.compose), '-f', linux_path(arguments.verify_override),
                       '-f', linux_path(public / 'controller.compose.json'), 'run', '--rm', '--no-deps', '--pull', 'never',
                       '--name', controller_name, '--label', 'ai4r.foundation-controller=' + arguments.project,
                       '-e', 'AI4R_EVIDENCE_DIR=' + linux_path(output), '-v', linux_path(output) + ':/evidence',
                       'app', '-m', 'pytest', CHECKS[arguments.check][0], '-o', 'addopts=', '-q', '--junitxml=/evidence/junit.xml']
            controller_issued = True
            result = host.run(command, timeout=300, check=False)
            # Never export arbitrary credential values echoed by a broken target.
            logs = result.stdout + b'\n' + result.stderr
            for key in ('token_file', 'bootstrap_challenge_file'):
                if profile['auth'][key]:
                    secret = controller_secret(host, profile['auth'][key], profile['job_id']).strip()
                    if secret:
                        logs = logs.replace(secret, b'[REDACTED]')
            write_new(output / 'command-output.log', logs)
        unchanged = not verify_candidate(root, candidate)
        current_check, current_source, current_interfaces, current_pins = native_context(root, arguments.check)
        native_unchanged = (current_check['procedure_sha256'], current_source, current_interfaces, current_pins) == (check['procedure_sha256'], source_sha, interfaces, pins)
        ledger_path = output / 'controller-observations.json'
        ledger = json.loads(read_regular(ledger_path)) if ledger_path.is_file() else {}
        required = expected_assertion['required_assertion_ids']
        rows = ledger.get('assertions', [])
        passed = [r['id'] for r in rows if r.get('passed') is True]
        assertion_pass = (ledger.get('check_id') == arguments.check and ledger.get('joins') == {k: profile[k] for k in JOIN_KEYS}
                          and ledger.get('complete') is True and len(rows) == len(required) and set(passed) == set(required))
        junit_ok = (output / 'junit.xml').is_file() and junit_result((output / 'junit.xml').read_bytes(), expected_assertion['required_case_ids'])
        outcome = ('STALE' if not unchanged or not native_unchanged else 'BLOCKED' if profile['mode'] == 'blocked_development'
                   else 'PASS' if result.returncode == 0 and assertion_pass and junit_ok else 'FAIL')
        receipt.update(outcome=outcome, reason=('Development mode cannot establish acceptance.' if profile['mode'] == 'blocked_development'
            else 'Current required assertions and raw cases passed.' if outcome == 'PASS' else 'Required actual observations failed, were unavailable, or changed.'),
            candidate_id=candidate['candidate_id'], source_baseline_sha256=source_sha, procedure_sha256=check['procedure_sha256'],
            interface_revisions=interfaces, native_pins=pins, command=host.commands[-1], cwd=linux_path(root), ended_at=now(),
            environment={'platform': controller_image['Os'] + '/' + controller_image['Architecture'], 'image_digest': controller_digest,
                         'target_image_id': profile['image_id'], 'target_container_id': container_id},
            dependency_mode=expected_assertion['required_dependency_mode'], profile_pins={'original_target_profile': digest(raw_profile)},
            fixture_pins={expected_fixture['id']: digest(json_bytes(expected_fixture)), expected_assertion['id']: digest(json_bytes(expected_assertion))},
            assertions={'required_ids': required, 'passed_ids': passed, 'expected': len(required), 'observed': len(rows)})
        kinds = {'junit.xml': 'junit', 'command-output.log': 'stdout', 'assertion-manifest.json': 'assertion_manifest',
                 'controller-observations.json': 'raw', 'fixture-manifest.json': 'fixture_manifest'}
        receipt['artifacts'] = [{'kind': kinds.get(p.name, 'raw'), 'path': p.relative_to(output).as_posix(), 'sha256': digest(p.read_bytes())}
                                for p in sorted(output.rglob('*')) if p.is_file() and not p.is_symlink()]
        if outcome == 'PASS':
            assessment = validate_receipt(receipt, check=check, root=output, candidate_id=candidate['candidate_id'], source_sha=source_sha, interfaces=interfaces, native_pins=pins)
            if assessment['status'] != 'PASS':
                receipt.update(outcome='BLOCKED', reason='Receipt failed independent raw-evidence reconciliation.')
    except (FoundationBlocked, ValueError, KeyError, OSError, TypeError) as error:
        receipt.update(outcome='BLOCKED', reason=str(error) if isinstance(error, FoundationBlocked) else 'Controlled binding unavailable: ' + type(error).__name__)
    finally:
        cleanup = {'schema': 'ai4r-foundation-controller-cleanup:1', 'controller': controller_name,
                   'target_touched': False, 'resources_removed': [], 'qualified': False}
        if controller_issued:
            try:
                found = host.run(['inspect', controller_name], check=False)
                if found.returncode == 0:
                    owned = json.loads(found.stdout)
                    if len(owned) != 1 or owned[0].get('Config', {}).get('Labels', {}).get('ai4r.foundation-controller') != arguments.project:
                        raise FoundationBlocked('CONTROLLER_CLEANUP_OWNERSHIP_MISMATCH')
                    host.run(['rm', '--force', controller_name])
                    cleanup['resources_removed'] = [controller_name]
                cleanup['qualified'] = True
            except (FoundationBlocked, ValueError, OSError):
                receipt.update(outcome='BLOCKED', reason='Owned controller containment or cleanup could not be established.')
        write_new(output / 'controller-cleanup.json', cleanup)
        receipt['ended_at'] = now()
        write_new(output / 'commands.json', host.commands)
        write_new(output / 'result.json', receipt)
    print(json.dumps({'check_id': arguments.check, 'outcome': receipt['outcome'], 'reason': receipt['reason'], 'evidence': str(output)}))
    return 0 if receipt['outcome'] == 'PASS' else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    invoke = sub.add_parser('run')
    invoke.add_argument('--root', default='.')
    invoke.add_argument('--compose', default='deploy/m1/compose.yaml')
    invoke.add_argument('--verify-override', default='deploy/m1/compose.verify.yaml')
    invoke.add_argument('--project', required=True)
    invoke.add_argument('--profile-file', required=True)
    invoke.add_argument('--check', required=True)
    invoke.add_argument('--evidence-dir', required=True)
    invoke.add_argument('--verify-image', required=True)
    invoke.add_argument('--candidate')
    freeze = sub.add_parser('freeze-foundation-manifests', help='Explicit authoring before a run; never regenerates expected inputs during execution')
    freeze.add_argument('--root', default='.')
    freeze.add_argument('--check', required=True, choices=sorted(CHECKS))
    freeze.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == 'run':
            return run(args)
        check, source_sha, _, _ = native_context(args.root, args.check)
        output = Path(args.output_dir)
        output.mkdir(exist_ok=False, parents=True)
        fixture, assertion = manifests(args.check, check['procedure_sha256'], source_sha)
        write_new(output / 'fixture-manifest.json', fixture)
        write_new(output / 'assertion-manifest.json', assertion)
        print(json.dumps({'check_id': args.check, 'output': str(output), 'acceptance': 'NOT_ASSESSED'}))
        return 0
    except (FoundationBlocked, ValueError, OSError, KeyError) as error:
        print('Foundation driver blocked: ' + (str(error) if isinstance(error, FoundationBlocked) else type(error).__name__), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
