"""Bounded local engine inspection; no build, pull, or evaluation scheduling."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import time
import uuid

from .store import FactoryError

from .config import PROBE, DOCKER_PREFIX, INSPECT_TIMEOUT
PATCHES = Path(__file__).parent / 'ccs' / 'engine_component'
FLAG = re.compile(r'(?<![\w-])(--?[A-Za-z][A-Za-z0-9_-]*)(?![\w-])')
from .effective_config import ENV_KEYS, parse_effective


class InspectionError(FactoryError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Inspector:
    def __init__(self, home):
        self.home = Path(home)
        self.deadline = time.monotonic() + INSPECT_TIMEOUT
        self.stderr = ''

    def run(self, argv, *, timeout=3, cwd=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise InspectionError('TIMEOUT', 'Inspector deadline exceeded')
        try:
            result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                    errors='replace', timeout=min(timeout, remaining),
                                    env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'))
        except subprocess.TimeoutExpired as exc:
            tail = exc.stderr or b''
            self.stderr += tail.decode(errors='replace') if isinstance(tail, bytes) else tail
            raise InspectionError('TIMEOUT', 'Inspector subprocess timed out') from exc
        self.stderr += result.stderr[-65536:]
        self.stderr = self.stderr[-65536:]
        return result

    def docker(self, args, timeout=3):
        command = shlex.split(os.environ.get('FACTORY_DOCKER', 'docker')) + args
        # The fake seam replaces Docker entirely, including the group wrapper.
        prefix = shlex.split(os.environ.get('DOCKER_CMD_PREFIX', DOCKER_PREFIX))
        if prefix and not os.environ.get('FACTORY_DOCKER'):
            command = prefix + [shlex.join(command)]
        return self.run(command, timeout=timeout)

    def image(self, image):
        # Accept a plain reference string ("repo:tag" or "sha256:<64hex>") or {"tag"|"id"|"ref": str}.
        if isinstance(image, str):
            value = image
        elif isinstance(image, dict) and len(image) == 1 and set(image) <= {'tag', 'id', 'ref'}:
            value = next(iter(image.values()))
        else:
            raise ValueError('image must be a reference string ("repo:tag" or "sha256:<hex>") '
                             'or an object with exactly one of "tag", "id", "ref"; got %s'
                             % (type(image).__name__ if not isinstance(image, dict) else sorted(image)))
        if not isinstance(value, str) or not value or value.startswith('-'):
            raise ValueError('Invalid image reference')
        result = self.docker(['image', 'inspect', value], timeout=2)
        if result.returncode:
            raise InspectionError('IMAGE_NOT_FOUND', 'Cannot inspect local image')
        rows = json.loads(result.stdout)
        row = rows[0]
        image_id = row['Id']
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', image_id):
            raise ValueError('Docker did not return an immutable image Id')
        return {'id': image_id, 'labels': row.get('Config', {}).get('Labels') or {},
                'arch': row.get('Architecture')}

    def container(self, image_id, tool, args, *, extra=(), timeout=40):
        name = 'factory-inspector-' + uuid.uuid4().hex
        try:
            return self.docker(['run', '--rm', '--pull', 'never', '--name', name, '--label', 'factory=1',
                                '--runtime', 'nvidia', *extra, '--entrypoint', '/app/' + tool,
                                image_id, *args], timeout=timeout)
        finally:
            # Target only the owned container. Cleanup gets its own bounded second
            # even when the probe exhausted its execution deadline.
            self.deadline = max(self.deadline, time.monotonic() + 1)
            cleanup = self.docker(['rm', '-f', name], timeout=1)
            if cleanup.returncode and 'No such container' not in cleanup.stderr:
                raise InspectionError('CLEANUP_FAILED', 'Owned inspector container removal failed')

    def inspect(self, inputs, packet):
        if set(inputs) - {'source', 'subpath', 'image'}:
            raise ValueError('Unknown inspect input')
        handle = inputs['source']
        resource = packet.get('resources', {}).get(handle) if isinstance(handle, str) else None
        if not resource or resource.get('kind') != 'workspace':
            raise ValueError('source must be a workspace handle')
        root = Path(resource['path']).resolve()
        subpath = inputs.get('subpath', '.')
        if not isinstance(subpath, str) or Path(subpath).is_absolute():
            raise ValueError('subpath must be relative')
        source = (root / subpath).resolve()
        if not source.is_relative_to(root) or not source.is_dir():
            raise ValueError('source must remain in workspace')
        def git(*args):
            result = self.run(['git', '-C', str(source), *args])
            if result.returncode:
                raise InspectionError('SOURCE_INVALID', 'Git source inspection failed')
            return result.stdout.strip()
        # Prevent Git from discovering a repository outside the granted handle.
        top = Path(git('rev-parse', '--show-toplevel')).resolve()
        if top != source:
            raise ValueError('subpath must name the repository root')
        patches = []
        for patch in sorted(PATCHES.glob('*.patch')):
            result = self.run(['git', '-C', str(source), 'apply', '--reverse', '--check', str(patch)])
            if result.returncode == 0:
                patches.append({'name': patch.name, 'sha256': hashlib.sha256(patch.read_bytes()).hexdigest()})
        l4t = Path('/etc/nv_tegra_release')
        try:
            docker_available = self.docker(['version', '--format', '{{json .Server}}']).returncode == 0
        except OSError:
            docker_available = False
        output = {'source': {'commit': git('rev-parse', 'HEAD'),
                             'dirty': bool(git('status', '--porcelain', '--untracked-files=normal')),
                             'branch': git('branch', '--show-current'), 'applied_patches': patches},
                  'host': {'arch': platform.machine(), 'l4t': l4t.read_text().strip() if l4t.exists() else None,
                           'nvcc_on_path': shutil.which('nvcc') is not None,
                           'docker': docker_available}}
        if 'image' in inputs:
            output['image'] = self.image(inputs['image'])
        return output

    def preflight(self, inputs):
        if set(inputs) != {'image', 'tool', 'argv'}:
            raise ValueError('preflight requires image, tool, argv')
        tool, argv = inputs['tool'], inputs['argv']
        if not isinstance(tool, str) or not re.fullmatch(r'llama-[a-z0-9-]+', tool):
            raise ValueError('Invalid tool basename')
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            raise ValueError('argv must be strings')
        image = self.image(inputs['image'])
        cache = self.home / 'preflight'
        key = hashlib.sha256((image['id'] + '\0' + tool).encode()).hexdigest()
        path = cache / (key + '.txt')
        if path.is_file():
            help_text = path.read_text()
        else:
            result = self.container(image['id'], tool, ['--help'])
            help_text = result.stdout + '\n' + result.stderr
            if result.returncode or not help_text.strip():
                raise InspectionError('HELP_FAILED', 'Image tool help failed')
            cache.mkdir(parents=True, exist_ok=True)
            temporary = cache / (key + '.' + uuid.uuid4().hex + '.tmp')
            temporary.write_text(help_text)
            temporary.replace(path)
        supported = set(FLAG.findall(help_text))
        unsupported = []
        for arg in argv:
            if arg == '--':
                break
            flag = arg.split('=', 1)[0]
            if re.match(r'^--?[A-Za-z]', flag) and flag not in supported and flag not in unsupported:
                unsupported.append(flag)
        return {'ok': not unsupported, 'unsupported_flags': unsupported,
                'help_sha256': hashlib.sha256(help_text.encode()).hexdigest(), 'image': image}, help_text

    def verify(self, inputs):
        if set(inputs) != {'image', 'env'}:
            raise ValueError('verify requires image and env')
        env = inputs['env']
        if not isinstance(env, dict) or not all(isinstance(k, str) and k.startswith('LLAMA_EXPERT_')
                                               and isinstance(v, str) and '\0' not in v for k, v in env.items()):
            raise ValueError('env must contain string LLAMA_EXPERT_* settings')
        image = self.image(inputs['image'])
        extra = ['--mount', f'type=bind,src={PROBE.parent},dst=/probe,readonly']
        for key, value in sorted(env.items()):
            extra += ['--env', f'{key}={value}']
        result = self.container(image['id'], 'llama-completion',
                                ['-m', '/probe/' + PROBE.name, '-p', 'x', '-n', '1', '-ngl', '0',
                                 '-c', '256', '--temp', '0', '-no-cnv'], extra=extra, timeout=45)
        output = {'requested': env, 'effective': {}, 'mismatches': {}, 'image': image,
                  'exit_status': result.returncode, 'aborted': result.returncode < 0 or
                  result.returncode > 128 or bool(getattr(result, 'signal', None))}
        invalid = re.search(r'^expert_config: invalid .*$', result.stderr, re.MULTILINE)
        if invalid:
            output['invalid_line'] = invalid.group(0)
            return output, ('CONFIG_REJECTED', invalid.group(0))
        lines, effective = parse_effective(result.stderr)
        # Patch 08 prints once per llama_context; llama-completion creates more than one
        # (observed live on om11: two identical lines). All must agree.
        if not lines:
            return output, ('CONFIG_MISSING', 'No expert_config effective line in stderr')
        if len(set(lines)) != 1:
            return output, ('CONFIG_MISMATCH', 'Effective config lines disagree across contexts')
        output['effective'] = effective
        if set(effective) != set(ENV_KEYS.values()):
            return output, ('CONFIG_MISSING', 'Effective config line is incomplete or unrecognized')
        for key, value in env.items():
            actual = effective.get(ENV_KEYS.get(key))
            # Engine integers accept leading zeros and print decimal values.
            expected = str(int(value)) if key in ENV_KEYS and ENV_KEYS[key] not in {'random', 'order', 'diag_csv'} and value.isascii() and value.isdigit() else value
            if actual != expected:
                output['mismatches'][key] = {'requested': value, 'effective': actual}
        if output['mismatches']:
            return output, ('CONFIG_MISMATCH', 'Effective config differs from request')
        if result.returncode:
            return output, ('PROBE_FAILED', 'Config probe exited unsuccessfully')
        return output, None


def dispatch(store, task_id, capability, packet):
    """Return a native result envelope, retaining evidence on errors too."""
    inspector = Inspector(store._store.home if hasattr(store, '_store') else store.home)
    output, error = {}, None
    try:
        inputs = packet.get('inputs', {})
        if capability == 'inspector.inspect':
            output = inspector.inspect(inputs, packet)
        elif capability == 'inspector.preflight':
            output, help_text = inspector.preflight(inputs)
            inspector.stderr += '\n' + help_text
            if not output['ok']:
                error = ('UNSUPPORTED_FLAG', 'Unsupported flags: ' + ', '.join(output['unsupported_flags']))
        elif capability == 'inspector.verify_effective_config':
            output, error = inspector.verify(inputs)
        else:
            raise ValueError('Unknown inspector capability')
    except InspectionError as exc:
        error = (exc.code, str(exc))
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        # Say why: an agent can only repair a call it can diagnose.
        error = ('INVALID_INPUT', (f'{type(exc).__name__}: {exc}')[:300])
    except OSError:
        error = ('PROCESS_FAILED', 'Inspector executable or local file unavailable')
    artifact = store.put_artifact(task_id, None,
        (json.dumps(output, sort_keys=True) + '\n--- stderr tail ---\n' + inspector.stderr[-65536:]).encode(),
        'text/plain', packet.get('call'))
    observation = store.append_observation(task_id, {
        'kind': capability, 'source_artifacts': [artifact['artifact_id']], 'values': output,
        'error': {'code': error[0], 'message': error[1]} if error else {},
        'limitations': 'Local inspection/config probe only; no activation or correctness claim.'})
    output['evidence'] = {'observation_id': observation['obs_id'], 'artifact_id': artifact['artifact_id']}
    result = {'outcome': 'error' if error else 'ok', 'outputs': output}
    if error:
        result['error'] = {'code': error[0], 'message': error[1]}
    return result
