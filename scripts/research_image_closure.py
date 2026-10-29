"""M1-I018 host consumer: independent image closure, never label-based trust."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import tempfile
import zipfile

try:
    from scripts.research_foundation import FoundationBlocked, digest, read_regular, read_pin
    from scripts.research_foundation_host import _absent, _cleanup
    from scripts.research_image_closure_probe import CHECKS
except ModuleNotFoundError:
    from research_foundation import FoundationBlocked, digest, read_regular, read_pin
    from research_foundation_host import _absent, _cleanup
    from research_image_closure_probe import CHECKS


def _linux(path):
    value = str(Path(path).resolve())
    match = re.fullmatch(r'([A-Za-z]):[\\/](.*)', value)
    return '/mnt/' + match[1].lower() + '/' + match[2].replace('\\', '/') if match else value


def inspect_closure(host, profile, source_build_pin, output, *, snapshot=None):
    """Verify exact frozen proof and observe original installed bytes afresh.

    Historical h may have a valid frozen closure while currentness is false.
    Callers must separately enforce current full-candidate/native/source pins.
    """
    # Import after the host driver has initialized, avoiding a module cycle.
    try:
        from scripts.research_build import context_tar, file_sha, regular, validate_manifest, IMAGE, JOB
    except ModuleNotFoundError:
        from research_build import context_tar, file_sha, regular, validate_manifest, IMAGE, JOB
    output = Path(output)
    name = 'ai4r-foundation-closure-' + digest((profile['job_id'] + profile['image_id']).encode())[:24]
    result = {'schema': 'ai4r-source-installed-closure:1', 'qualified': False,
              'current_candidate_qualified': False, 'image_id': profile['image_id'], 'name': name,
              'source_build_pin': source_build_pin, 'target_touched': False}
    issued = False
    try:
        if (not re.fullmatch(r'ai4r-[a-z0-9][a-z0-9-]{1,80}', profile.get('job_id', ''))
                or not re.fullmatch(r'sha256:[a-f0-9]{64}', profile.get('image_id', ''))
                or any(not re.fullmatch(r'[a-f0-9]{64}', profile.get(key, '')) for key in ('candidate_id', 'build_id'))
                or profile.get('platform') not in {'linux/amd64', 'linux/arm64'}):
            raise FoundationBlocked('EXACT_IMAGE_CLOSURE_IDENTITY_REQUIRED')
        if set(source_build_pin) != {'path', 'sha256'} or Path(source_build_pin['path']).name != 'receipt.json':
            raise FoundationBlocked('EXACT_SOURCE_BUILD_RECEIPT_PIN_REQUIRED')
        source_build = read_pin(source_build_pin)
        directory = Path(source_build_pin['path']).resolve().parent
        if (source_build.get('schema') != 'ai4r-source-build:1' or source_build.get('outcome') != 'BUILT'
                or source_build.get('target') != 'app-production' or source_build.get('platform') != profile['platform']
                or source_build.get('image', {}).get('image_id') != profile['image_id']
                or source_build.get('image', {}).get('platform') != profile['platform']
                or source_build.get('context_unchanged') is not True or source_build.get('output_tag_unchanged') is not True
                or source_build.get('producer_completed') is not True
                or source_build.get('build', {}).get('returncode') != 0 or source_build.get('build', {}).get('timed_out') is not False
                or not IMAGE.fullmatch(source_build.get('tag', '')) or not JOB.fullmatch(source_build.get('job_id', ''))):
            raise FoundationBlocked('SOURCE_BUILD_IDENTITY_OR_OUTCOME_MISMATCH')
        command = source_build.get('command', [])
        expected_tail = ['buildx', 'build', '--builder', 'default', '--platform', profile['platform'],
            '--file', 'deploy/m1/Dockerfile.app', '--target', 'production', '--tag', source_build['tag'],
            '--load', '--progress', 'plain', '--metadata-file', _linux(directory / 'build-metadata.json'),
            '--label', 'ai4r.owner=' + source_build['job_id'], '--label', 'ai4r.candidate=' + source_build['candidate_id'],
            '--label', 'ai4r.source-context=' + source_build['context']['sha256'], '-']
        if 'buildx' not in command or command[command.index('buildx'):] != expected_tail:
            raise FoundationBlocked('CLOSED_ORIGINAL_BUILD_COMMAND_REQUIRED')
        artifacts = source_build.get('artifacts', [])
        allowed = {'candidate.json', 'context.tar', 'build.stdout.log', 'build.stderr.log', 'build-metadata.json', 'runtime.stdout.json', 'runtime.stderr.log'}
        names = set()
        for item in artifacts:
            if (set(item) != {'path', 'bytes', 'sha256'} or item['path'] not in allowed or item['path'] in names
                    or file_sha(directory / item['path']) != item['sha256']
                    or (directory / item['path']).stat().st_size != item['bytes']):
                raise FoundationBlocked('ORIGINAL_BUILD_ARTIFACT_CHANGED')
            names.add(item['path'])
        if not {'candidate.json', 'context.tar', 'build.stdout.log', 'build.stderr.log', 'build-metadata.json'} <= names:
            raise FoundationBlocked('ORIGINAL_BUILD_ARTIFACT_MISSING')
        raw_candidate = read_regular(directory / 'candidate.json', maximum=32 * 1024**2)
        candidate = json.loads(raw_candidate)
        validate_manifest(candidate)
        if (digest(raw_candidate) != source_build['candidate_manifest_sha256'] or candidate['candidate_id'] != source_build['candidate_id']
                or candidate['candidate_id'] != profile['candidate_id'] or candidate['snapshot']['sha256'] != source_build['snapshot_sha256']):
            raise FoundationBlocked('ORIGINAL_BUILD_CANDIDATE_MISMATCH')
        source_inventory = {row['path']: row for row in candidate['files']}
        if source_inventory.get('docs/code/Missions/M1/source-baseline.json', {}).get('sha256') != source_build.get('source_baseline_sha256'):
            raise FoundationBlocked('ORIGINAL_SOURCE_BASELINE_MISMATCH')
        result['source_baseline_sha256'] = source_build['source_baseline_sha256']
        snapshot = Path(snapshot or candidate['snapshot']['path'])
        with tempfile.TemporaryDirectory(prefix='ai4r-closure-context-') as temporary:
            actual_context = context_tar(candidate, snapshot, Path(temporary) / 'context.tar')
        if actual_context != source_build['context'] or file_sha(directory / 'context.tar') != actual_context['sha256']:
            raise FoundationBlocked('ORIGINAL_BUILD_CONTEXT_MISMATCH')
        observed = host.json(['image', 'inspect', profile['image_id']])
        if (len(observed) != 1 or observed[0].get('Id') != profile['image_id']
                or observed[0].get('Os', '') + '/' + observed[0].get('Architecture', '') != profile['platform']):
            raise FoundationBlocked('ACTUAL_INSTALLED_IMAGE_MISMATCH')
        if not _absent(host.run(['container', 'inspect', name], check=False)):
            raise FoundationBlocked('FRESH_CLOSURE_PROBE_NAME_REQUIRED')
        payloads = {}
        with regular(snapshot) as stream, zipfile.ZipFile(stream) as archive:
            for path in ('pyproject.toml', 'packages/jiuwenswarm-tui/pyproject.toml'):
                payloads[path] = base64.b64encode(archive.read(path)).decode('ascii')
        value = {'schema': 'ai4r-installed-closure-input:1', 'candidate': candidate,
                 'source_build_receipt_sha256': source_build_pin['sha256'], 'context_sha256': actual_context['sha256'],
                 'snapshot_sha256': candidate['snapshot']['sha256'], 'image_id': profile['image_id'],
                 'platform': profile['platform'], 'build_id': profile['build_id'], 'source_payloads': payloads}
        input_path = output / 'image-closure-input.json'
        with input_path.open('xb') as stream:
            stream.write(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())
        program = read_regular(Path(__file__).with_name('research_image_closure_probe.py')).decode('utf8')
        result.update(candidate_id=candidate['candidate_id'], snapshot_sha256=candidate['snapshot']['sha256'],
                      context_sha256=actual_context['sha256'], source_build_receipt_sha256=source_build_pin['sha256'],
                      program_sha256=digest(program.encode()), input_sha256=file_sha(input_path))
        args = ['run', '--rm', '--name', name, '--label', 'ai4r.foundation-probe=' + profile['job_id'],
            '--network', 'none', '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', '512m', '--pids-limit', '32',
            '--mount', 'type=bind,src=' + _linux(input_path) + ',dst=/run/ai4r-image-closure/input.json,readonly',
            '--entrypoint', '/usr/local/bin/python3', profile['image_id'], '-I', '-S', '-c', program]
        issued = True
        call = host.run(args, timeout=180, check=False)
        result.update(returncode=call.returncode, stdout_sha256=digest(call.stdout), stderr_sha256=digest(call.stderr))
        with (output / 'image-closure.stdout.json').open('xb') as stream: stream.write(call.stdout)
        with (output / 'image-closure.stderr.log').open('xb') as stream: stream.write(call.stderr)
        if len(call.stdout) > 4 * 1024**2:
            raise FoundationBlocked('INDEPENDENT_CLOSURE_OUTPUT_BOUND')
        value = json.loads(call.stdout)
        expected_joins = {key: result[key] for key in ('candidate_id', 'source_build_receipt_sha256', 'context_sha256', 'snapshot_sha256', 'image_id')}
        expected_joins.update(platform=profile['platform'], build_id=profile['build_id'])
        if (call.returncode or value.get('schema') != 'ai4r-installed-closure-observation:1' or value.get('mode') != 'installed'
                or value.get('joins') != expected_joins or value.get('installed_build_id') != profile['build_id']
                or value.get('manifest_sha256') != source_build.get('runtime', {}).get('observation', {}).get('build', {}).get('sha256')):
            raise FoundationBlocked('INDEPENDENT_INSTALLED_CLOSURE_IDENTITY_MISMATCH')
        intact = (file_sha(input_path) == result['input_sha256'] and file_sha(source_build_pin['path']) == source_build_pin['sha256']
                  and file_sha(snapshot) == candidate['snapshot']['sha256']
                  and file_sha(directory / 'context.tar') == actual_context['sha256'])
        result.update(observation=value, frozen_inputs_unchanged=intact,
                      qualified=value.get('qualified') is True and set(value.get('assertions', {})) == set(CHECKS)
                      and all(item is True for item in value['assertions'].values()) and intact)
    except Exception as error:
        result['error'] = str(error) if isinstance(error, FoundationBlocked) else type(error).__name__
    finally:
        result['cleanup'] = _cleanup(host, name, profile['job_id']) if issued else {'attempted': False, 'confirmed': True, 'name': name}
        result['qualified'] = result['qualified'] and result['cleanup']['confirmed']
    return result
