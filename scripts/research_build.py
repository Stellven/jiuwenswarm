"""Finite local builds from an exclusive, fully verified source snapshot.

This host-only producer supplies build-input evidence. BUILT never means that
the image, its models, its isolation or a platform has passed qualification.
It does not accept Dockerfile names, build arguments, commands or credentials.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import tarfile
import zipfile

try:
    from scripts.research_candidate import (DEFAULT_SCOPE, PRODUCT_WORKSPACE_ROOTS, PUBLIC_TEMPLATE_FILES,
                                            excluded, verify_candidate)
    from scripts.research_system import DockerHost, linux_path
    from scripts.research_reports import source_identity
except ModuleNotFoundError:
    from research_candidate import (DEFAULT_SCOPE, PRODUCT_WORKSPACE_ROOTS, PUBLIC_TEMPLATE_FILES,
                                    excluded, verify_candidate)
    from research_system import DockerHost, linux_path
    from research_reports import source_identity


TARGETS = {
    'app-production': ('deploy/m1/Dockerfile.app', 'production', False),
    'app-verify': ('deploy/m1/Dockerfile.app', 'verify', False),
    'sidecar-production': ('deploy/m1/Dockerfile.sidecar', 'production', False),
    'rsi-production': ('deploy/m1/Dockerfile.rsi', 'production', True),
    'rsi-worker': ('deploy/m1/Dockerfile.rsi', 'worker-broker', True),
}
PLATFORMS = frozenset({'linux/amd64', 'linux/arm64'})
HEX = re.compile(r'[a-f0-9]{64}\Z')
IMAGE = re.compile(r'ai4r-[a-z0-9][a-z0-9_.-]{0,100}:[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,100}\Z')
JOB = re.compile(r'ai4r-build-[a-z0-9][a-z0-9-]{0,64}\Z')
# Host-parser resource bounds, not product or experimental thresholds.
MAX_FILES, MAX_FILE, MAX_ARCHIVE = 50000, 128 * 1024**2, 1024**3


class BuildBlocked(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, value):
    with Path(path).open('xb') as handle:
        handle.write(value if isinstance(value, bytes) else encoded(value) + b'\n')


def regular(path, maximum=MAX_ARCHIVE):
    """Open one non-aliased regular input; the caller retains the descriptor."""
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise BuildBlocked('INPUT_ALIAS_DENIED')
    handle = path.open('rb')
    info = os.fstat(handle.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 <= info.st_size <= maximum:
        handle.close()
        raise BuildBlocked('REGULAR_BOUNDED_SINGLE_LINK_INPUT_REQUIRED')
    return handle


def file_sha(path):
    digest = hashlib.sha256()
    with regular(path) as handle:
        for chunk in iter(lambda: handle.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def logical_name(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or any(ord(char) < 32 for char in name)):
        raise BuildBlocked('NONCANONICAL_MEMBER_PATH')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '.' in path.parts or path.as_posix() != name:
        raise BuildBlocked('NONCANONICAL_MEMBER_PATH')
    if not any(path == PurePosixPath(scope) or path.is_relative_to(PurePosixPath(scope)) for scope in DEFAULT_SCOPE):
        raise BuildBlocked('MEMBER_OUTSIDE_PUBLIC_SCOPE')
    product_workspace = any(path.is_relative_to(PurePosixPath(prefix)) for prefix in PRODUCT_WORKSPACE_ROOTS)
    if excluded(Path(name), tracked_product_workspaces={name} if product_workspace else frozenset(),
                tracked_public_templates=PUBLIC_TEMPLATE_FILES):
        raise BuildBlocked('PRIVATE_MEMBER_DENIED')
    return name


def validate_manifest(value):
    if not isinstance(value, dict) or value.get('schema_version') != '1.0.0' or value.get('scope') != list(DEFAULT_SCOPE):
        raise BuildBlocked('FULL_DEFAULT_CANDIDATE_REQUIRED')
    rows = value.get('files')
    if not isinstance(rows, list) or not 0 < len(rows) <= MAX_FILES:
        raise BuildBlocked('BOUNDED_CANDIDATE_INVENTORY_REQUIRED')
    names, total = [], 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'path', 'bytes', 'sha256'}:
            raise BuildBlocked('CANDIDATE_ROW_INVALID')
        names.append(logical_name(row['path']))
        if (type(row['bytes']) is not int or not 0 <= row['bytes'] <= MAX_FILE
                or not isinstance(row['sha256'], str) or not HEX.fullmatch(row['sha256'])):
            raise BuildBlocked('CANDIDATE_ROW_INVALID')
        total += row['bytes']
    if total > MAX_ARCHIVE or names != sorted(set(names)) or len(set(x.casefold() for x in names)) != len(names):
        raise BuildBlocked('CANDIDATE_INVENTORY_ORDER_OR_SIZE')
    head = value.get('base_head')
    if head is not None and (not isinstance(head, str) or not re.fullmatch(r'[a-f0-9]{40,64}', head)):
        raise BuildBlocked('CANDIDATE_HEAD_INVALID')
    identity = {key: value[key] for key in ('schema_version', 'base_head', 'scope', 'files')}
    if value.get('candidate_id') != sha(encoded(identity)):
        raise BuildBlocked('CANDIDATE_IDENTITY_MISMATCH')
    snapshot = value.get('snapshot')
    if (not isinstance(snapshot, dict) or set(snapshot) != {'path', 'sha256'}
            or not isinstance(snapshot['sha256'], str) or not HEX.fullmatch(snapshot['sha256'])):
        raise BuildBlocked('EXCLUSIVE_SNAPSHOT_PIN_REQUIRED')
    return {row['path']: row for row in rows}


def context_tar(manifest, snapshot, destination):
    """Never extract: validate the complete ZIP, then stream its bytes into tar."""
    expected = validate_manifest(manifest)
    with regular(snapshot) as source:
        before = os.fstat(source.fileno())
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024**2), b''):
            digest.update(chunk)
        if digest.hexdigest() != manifest['snapshot']['sha256']:
            raise BuildBlocked('SNAPSHOT_HASH_MISMATCH')
        source.seek(0)
        try:
            with zipfile.ZipFile(source) as archive:
                members = archive.infolist()
                names = [logical_name(member.filename) for member in members]
                if len(names) != len(set(names)) or set(names) != set(expected):
                    raise BuildBlocked('SNAPSHOT_INVENTORY_MISMATCH')
                for member in members:
                    mode = member.external_attr >> 16
                    if (member.is_dir() or not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o644
                            or member.flag_bits & 1 or member.file_size != expected[member.filename]['bytes']):
                        raise BuildBlocked('SNAPSHOT_MEMBER_TYPE_OR_SIZE')
                # The capture writer emits a single bounded archive without
                # comments, descriptors, hidden local members or prepended/
                # appended payloads. Do not silently ignore such extra bytes.
                if archive.comment:
                    raise BuildBlocked('SNAPSHOT_EXTRA_ARCHIVE_BYTES')
                offset = 0
                for member in sorted(members, key=lambda item: item.header_offset):
                    source.seek(member.header_offset)
                    header = source.read(30)
                    if len(header) != 30:
                        raise BuildBlocked('SNAPSHOT_LOCAL_HEADER_INVALID')
                    fields = struct.unpack('<4s5H3I2H', header)
                    signature, _, flags, compression, _, _, crc, compressed_size, size, name_length, extra_length = fields
                    if (member.header_offset != offset or signature != b'PK\x03\x04' or flags & 8
                            or member.extra or member.comment or extra_length
                            or (flags, compression, crc, compressed_size, size)
                            != (member.flag_bits, member.compress_type, member.CRC, member.compress_size, member.file_size)):
                        raise BuildBlocked('SNAPSHOT_EXTRA_ARCHIVE_BYTES')
                    offset = member.header_offset + 30 + name_length + extra_length + compressed_size
                source.seek(-22, 2)
                end = source.read(22)
                if offset != archive.start_dir or end[:4] != b'PK\x05\x06' or end[-2:] != b'\0\0':
                    raise BuildBlocked('SNAPSHOT_EXTRA_ARCHIVE_BYTES')
                # Verify ALL bytes before creating a context or starting Docker.
                for name in sorted(expected):
                    member_digest, size = hashlib.sha256(), 0
                    with archive.open(name) as stream:
                        for chunk in iter(lambda: stream.read(1024**2), b''):
                            member_digest.update(chunk); size += len(chunk)
                    if member_digest.hexdigest() != expected[name]['sha256'] or size != expected[name]['bytes']:
                        raise BuildBlocked('SNAPSHOT_MEMBER_DIGEST')
                with Path(destination).open('xb') as output:
                    with tarfile.open(fileobj=output, mode='w', format=tarfile.PAX_FORMAT) as tar:
                        for name in sorted(expected):
                            item = tarfile.TarInfo(name)
                            item.size, item.mode, item.uid, item.gid, item.mtime = expected[name]['bytes'], 0o644, 0, 0, 0
                            item.uname = item.gname = ''
                            with archive.open(name) as stream:
                                tar.addfile(item, stream)
        except (zipfile.BadZipFile, RuntimeError, EOFError) as error:
            raise BuildBlocked('SNAPSHOT_FORMAT_INVALID') from error
        after = os.fstat(source.fileno())
        source.seek(0); digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024**2), b''):
            digest.update(chunk)
        if ((before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns)
                or digest.hexdigest() != manifest['snapshot']['sha256']):
            raise BuildBlocked('SNAPSHOT_CHANGED_DURING_CAPTURE')
    return {'sha256': file_sha(destination), 'bytes': Path(destination).stat().st_size,
            'members': len(expected), 'inventory_sha256': sha(encoded(manifest['files']))}


class FrozenDockerHost(DockerHost):
    def __init__(self, root, config):
        super().__init__(root)
        # A new empty Docker client configuration never inherits registry auth.
        config = linux_path(config)
        if os.name == 'nt':
            index = self.prefix.index('docker')
            self.prefix[index:index] = ['env', 'DOCKER_CONFIG=' + config]
        else:
            self.prefix = ['env', 'DOCKER_CONFIG=' + config, *self.prefix]

    def build(self, arguments, context, output, timeout):
        command = self.prefix + list(arguments)
        self.commands.append(command)
        with regular(context) as source, (output / 'build.stdout.log').open('xb') as stdout, (output / 'build.stderr.log').open('xb') as stderr:
            try:
                result = subprocess.run(command, cwd=self.root, stdin=source, stdout=stdout, stderr=stderr,
                                        timeout=timeout, check=False)
                return {'returncode': result.returncode, 'timed_out': False}
            except subprocess.TimeoutExpired:
                # Docker's server may still be finishing: retain unknown truth.
                return {'returncode': None, 'timed_out': True}
            except OSError:
                return {'returncode': None, 'timed_out': False, 'error': 'LOCAL_BUILD_CLIENT_UNAVAILABLE'}


INSPECTOR = r'''
import hashlib,json,os,pathlib,subprocess
def capture(path,maximum=32*1024*1024):
 p=pathlib.Path(path)
 if not p.exists():return {"available":False}
 if p.is_symlink() or not p.is_file() or p.stat().st_size>maximum:return {"available":False,"error":"UNQUALIFIED_FILE"}
 raw=p.read_bytes();return {"available":True,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
result={"schema":"ai4r-image-runtime-observation:1"}
for key,path in [("build","/usr/local/share/ai4r-build-identity.json"),("codex_manifest","/usr/local/share/ai4r-codex-runtime.json"),("os_packages","/usr/local/share/ai4r-os-packages.txt")]:
 result[key]=capture(path)
 if result[key]["available"] and path.endswith(".json"):
  try:result[key]["value"]=json.loads(pathlib.Path(path).read_bytes())
  except Exception:result[key]["error"]="INVALID_JSON"
result["codex_binary"]=capture("/usr/local/bin/codex",256*1024*1024)
if result["codex_binary"]["available"]:
 try:
  call=subprocess.run(["/usr/local/bin/codex","--version"],capture_output=True,timeout=15,env={"PATH":"/usr/local/bin:/usr/bin:/bin","HOME":"/nonexistent","CODEX_HOME":"/nonexistent"})
  result["codex_binary"].update(returncode=call.returncode,version=call.stdout[:4096].decode("utf-8",errors="replace"),stderr_sha256=hashlib.sha256(call.stderr).hexdigest())
 except Exception:result["codex_binary"]["error"]="VERSION_UNAVAILABLE"
try:
 call=subprocess.run(["/usr/bin/dpkg-query","-W"],capture_output=True,timeout=15)
 result["installed_os_packages"]={"returncode":call.returncode,"sha256":hashlib.sha256(call.stdout).hexdigest(),"inventory":call.stdout.decode("utf-8",errors="replace") if len(call.stdout)<=1024*1024 else None}
except Exception:result["installed_os_packages"]={"available":False}
print(json.dumps(result,sort_keys=True,separators=(",",":")))
'''


def image(host, reference, *, required=True):
    call = host.run(['image', 'inspect', reference], check=False)
    if call.returncode:
        absent = b'No such image:' in call.stderr or b'No such object:' in call.stderr
        if not required and absent:
            return None
        raise BuildBlocked('LOCAL_IMAGE_REQUIRED' if absent else 'LOCAL_IMAGE_LOOKUP_FAILED')
    try:
        rows = json.loads(call.stdout)
        row = rows[0]
        if len(rows) != 1 or not re.fullmatch(r'sha256:[a-f0-9]{64}', row['Id']):
            raise ValueError()
        return {'image_id': row['Id'], 'platform': row['Os'] + '/' + row['Architecture'],
                'labels': row.get('Config', {}).get('Labels', {}), 'repo_digests': row.get('RepoDigests', [])}
    except (ValueError, KeyError, TypeError, IndexError):
        raise BuildBlocked('LOCAL_IMAGE_OBSERVATION_INVALID') from None


def runtime_observation(host, image_id, job, output):
    name = job + '-inspect'
    initial = host.run(['container', 'inspect', name], check=False)
    if initial.returncode == 0:
        raise BuildBlocked('INSPECTION_NAME_ALREADY_EXISTS')
    if b'No such object:' not in initial.stderr and b'No such container:' not in initial.stderr:
        raise BuildBlocked('INSPECTION_NAME_LOOKUP_FAILED')
    arguments = ['run', '--rm', '--name', name, '--label', 'ai4r.owner=' + job, '--network', 'none', '--read-only',
                 '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                 '--memory', '256m', '--pids-limit', '32', '--tmpfs', '/tmp:rw,nosuid,nodev,size=16m',
                 '--entrypoint', '/usr/local/bin/python3', image_id, '-I', '-S', '-c', INSPECTOR]
    observed = {'available': False, 'cleanup': {'name': name, 'attempted': False, 'confirmed': False}}
    try:
        result = host.run(arguments, timeout=60, check=False)
        write_new(output / 'runtime.stdout.json', result.stdout)
        write_new(output / 'runtime.stderr.log', result.stderr)
        if result.returncode or len(result.stdout) > 32 * 1024**2:
            observed.update(error='FIXED_INSPECTION_FAILED', returncode=result.returncode)
            return observed
        value = json.loads(result.stdout)
        if value.get('schema') != 'ai4r-image-runtime-observation:1':
            raise ValueError()
        observed.update(available=True, observation=value, sha256=sha(result.stdout))
        return observed
    except (OSError, ValueError) as error:
        observed.update(error=type(error).__name__)
        return observed
    finally:
        # A timed-out CLI can leave a running container. Remove only this job's
        # exact fresh name after independently checking its ownership label.
        cleanup = observed['cleanup']
        try:
            call = host.run(['container', 'inspect', name], check=False)
            if call.returncode == 0:
                rows = json.loads(call.stdout)
                if len(rows) != 1 or rows[0].get('Config', {}).get('Labels', {}).get('ai4r.owner') != job:
                    raise BuildBlocked('INSPECTION_CLEANUP_OWNERSHIP_CHANGED')
                cleanup['attempted'] = True
                cleanup['remove_returncode'] = host.run(['container', 'rm', '--force', name], check=False).returncode
                call = host.run(['container', 'inspect', name], check=False)
            cleanup['confirmed'] = bool(call.returncode and (b'No such object:' in call.stderr or b'No such container:' in call.stderr))
            if not cleanup['confirmed']:
                cleanup['error'] = 'INSPECTION_CLEANUP_UNCONFIRMED'
        except Exception as error:
            cleanup['error'] = str(error) if isinstance(error, BuildBlocked) else type(error).__name__


def produce(*, root, candidate, snapshot, target, platform, tag, job_id, output, parent_image=None,
            timeout_s=3600, host_factory=FrozenDockerHost):
    root, output = Path(root).resolve(), Path(output).absolute()
    if target not in TARGETS or platform not in PLATFORMS or not IMAGE.fullmatch(tag) or not JOB.fullmatch(job_id):
        raise BuildBlocked('CLOSED_LOCAL_BUILD_IDENTITY_REQUIRED')
    if type(timeout_s) is not int or not 1 <= timeout_s <= 21600:
        raise BuildBlocked('BOUNDED_BUILD_TIMEOUT_REQUIRED')
    dockerfile, stage, needs_parent = TARGETS[target]
    if needs_parent != bool(parent_image) or (parent_image and not IMAGE.fullmatch(parent_image)):
        raise BuildBlocked('FINITE_LOCAL_PARENT_REQUIRED_FOR_RSI_ONLY')
    # Evidence cannot add execution inputs to the very candidate it measures.
    for ancestor in (output, *output.parents):
        if ancestor.is_symlink():
            raise BuildBlocked('OUTPUT_ALIAS_DENIED')
    if output.is_relative_to(root) and any(output.is_relative_to(root / scope) for scope in DEFAULT_SCOPE):
        raise BuildBlocked('OUTPUT_INSIDE_EXECUTION_SCOPE')
    output.mkdir(exist_ok=False)
    record = {'schema': 'ai4r-source-build:1', 'job_id': job_id, 'target': target, 'platform': platform,
              'tag': tag, 'started_at': now(), 'outcome': 'BLOCKED', 'qualification': 'NOT_ASSESSED',
              'limitations': ['BUILT is build-input evidence only; model, isolation, scientific, native hardware and platform qualification are not established.'],
              'image': None, 'parent': None, 'runtime': None, 'checkout_current': None}
    host, context = None, output / 'context.tar'
    try:
        with regular(candidate, 32 * 1024**2) as stream:
            raw = stream.read()
        value = json.loads(raw)
        inventory = validate_manifest(value)
        record.update(candidate_id=value['candidate_id'], candidate_manifest_sha256=sha(raw),
                      snapshot_sha256=value['snapshot']['sha256'])
        write_new(output / 'candidate.json', raw)
        changed = verify_candidate(root, value)
        if changed:
            raise BuildBlocked('CHECKOUT_DIFFERS_FROM_FROZEN_CANDIDATE')
        baseline, changed_source = source_identity(root, root / 'docs/code/Missions/M1')
        if changed_source:
            raise BuildBlocked('AUTHORITATIVE_SOURCE_CHANGED')
        record['source_baseline_sha256'] = baseline
        required = {dockerfile, dockerfile + '.dockerignore', 'uv.lock'}
        if not required <= set(inventory):
            raise BuildBlocked('TARGET_PUBLIC_BUILD_INPUT_MISSING')
        record['context'] = context_tar(value, snapshot, context)
        config = output / 'docker-client'
        config.mkdir(mode=0o700)
        host = host_factory(root, config)
        contexts = host.json(['context', 'inspect', 'default'])
        if len(contexts) != 1 or contexts[0].get('Endpoints', {}).get('docker', {}).get('Host') != 'unix:///var/run/docker.sock':
            raise BuildBlocked('LOCAL_UNIX_DOCKER_REQUIRED')
        if image(host, tag, required=False):
            raise BuildBlocked('OUTPUT_IMAGE_TAG_ALREADY_EXISTS')
        if needs_parent:
            before = image(host, parent_image)
            if before['platform'] != platform:
                raise BuildBlocked('PARENT_PLATFORM_MISMATCH')
            alias = 'ai4r-m1-parent:' + job_id
            if image(host, alias, required=False):
                raise BuildBlocked('OWNED_PARENT_ALIAS_ALREADY_EXISTS')
            host.run(['image', 'tag', before['image_id'], alias])
            aliased = image(host, alias)
            if aliased['image_id'] != before['image_id']:
                raise BuildBlocked('PARENT_ALIAS_IDENTITY_CHANGED')
            record['parent'] = {'reference': parent_image, 'alias': alias, 'before': before, 'alias_before': aliased}
        arguments = ['buildx', 'build', '--builder', 'default', '--platform', platform, '--file', dockerfile,
                     '--target', stage, '--tag', tag, '--load', '--progress', 'plain',
                     '--metadata-file', linux_path(output / 'build-metadata.json'),
                     '--label', 'ai4r.owner=' + job_id, '--label', 'ai4r.candidate=' + value['candidate_id'],
                     '--label', 'ai4r.source-context=' + record['context']['sha256']]
        if needs_parent:
            arguments += ['--build-arg', 'APP_IMAGE=' + record['parent']['alias']]
        arguments.append('-')
        record['command'] = host.prefix + arguments
        record['build_dispatch'] = {'issued_at': now(), 'status': 'ISSUED'}
        record['build'] = host.build(arguments, context, output, timeout_s)
        record['image'] = image(host, tag, required=False)
        if needs_parent:
            record['parent']['after'] = image(host, parent_image, required=False)
            record['parent']['alias_after'] = image(host, record['parent']['alias'], required=False)
            record['parent']['unchanged'] = all(item and item['image_id'] == record['parent']['before']['image_id']
                                               for item in (record['parent']['after'], record['parent']['alias_after']))
        labels = (record['image'] or {}).get('labels', {})
        matched = (record['image'] and record['image']['platform'] == platform and labels.get('ai4r.owner') == job_id
                   and labels.get('ai4r.candidate') == value['candidate_id']
                   and labels.get('ai4r.source-context') == record['context']['sha256'])
        context_intact = file_sha(context) == record['context']['sha256'] and file_sha(snapshot) == value['snapshot']['sha256']
        record['context_unchanged'] = context_intact
        if record['build'].get('timed_out'):
            record['outcome'] = 'OUTCOME_UNKNOWN'
        elif record['build'].get('returncode') != 0 or not matched or not context_intact or (needs_parent and not record['parent']['unchanged']):
            record['outcome'] = 'FAILED'
        else:
            record['outcome'] = 'BUILT'
        if record['image']:
            record['runtime'] = runtime_observation(host, record['image']['image_id'], job_id, output)
            if not record['runtime']['cleanup']['confirmed']:
                record['outcome'] = 'OUTCOME_UNKNOWN'
                record['limitations'].append('The fixed inspection container cleanup could not be confirmed; its exact owned identity is retained.')
            observation = (record['runtime'].get('observation') or {})
            installed = observation.get('build', {}).get('value')
            if isinstance(installed, dict):
                build_id = installed.get('build_id')
                identity = {key: item for key, item in installed.items() if key != 'build_id'}
                record['installed_build'] = {'build_id': build_id, 'identity_valid': build_id == sha(encoded(identity)),
                    'lock_matches_candidate': installed.get('uv_lock_sha256') == inventory.get('uv.lock', {}).get('sha256'),
                    'project_matches_candidate': installed.get('pyproject_sha256') == inventory.get('pyproject.toml', {}).get('sha256')}
            final_image = image(host, tag, required=False)
            record['output_tag_unchanged'] = bool(final_image and final_image['image_id'] == record['image']['image_id'])
            if not record['output_tag_unchanged']:
                record['outcome'] = 'FAILED'
        record['changed_execution_inputs'] = verify_candidate(root, value)
        after_baseline, record['changed_authoritative_sources'] = source_identity(root, root / 'docs/code/Missions/M1')
        record['checkout_current'] = (not record['changed_execution_inputs'] and not record['changed_authoritative_sources']
                                      and after_baseline == baseline)
        if not record['checkout_current']:
            record['limitations'].append('The checkout changed during this build; this image retains the frozen input identity and is stale relative to the current checkout.')
        record['producer_completed'] = True
    except Exception as error:
        record['error'] = {'code': str(error) if isinstance(error, BuildBlocked) else type(error).__name__}
        # A client/control failure after dispatch cannot establish no build.
        if 'build_dispatch' in record and record['outcome'] != 'FAILED':
            record['outcome'] = 'OUTCOME_UNKNOWN'
    finally:
        if 'build_dispatch' in record and not record.get('producer_completed') and record['outcome'] != 'FAILED':
            record['outcome'] = 'OUTCOME_UNKNOWN'
        record['finished_at'] = now()
        record['commands'] = host.commands if host else []
        record['artifacts'] = []
        for name in ('candidate.json', 'context.tar', 'build.stdout.log', 'build.stderr.log', 'build-metadata.json',
                     'runtime.stdout.json', 'runtime.stderr.log'):
            item = output / name
            if item.exists() or item.is_symlink():
                try:
                    record['artifacts'].append({'path': name, 'bytes': item.stat().st_size, 'sha256': file_sha(item)})
                except (OSError, BuildBlocked):
                    record['artifacts'].append({'path': name, 'error': 'ARTIFACT_INTEGRITY_UNAVAILABLE'})
        write_new(output / 'receipt.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--target', choices=sorted(TARGETS), required=True)
    parser.add_argument('--platform', choices=sorted(PLATFORMS), required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--parent-image')
    parser.add_argument('--timeout-s', type=int, default=3600)
    args = vars(parser.parse_args())
    result = produce(**args)
    print(json.dumps({key: result.get(key) for key in ('job_id', 'outcome', 'candidate_id', 'checkout_current', 'image', 'error')}, sort_keys=True))
    return 0 if result['outcome'] == 'BUILT' else 1


if __name__ == '__main__':
    raise SystemExit(main())
