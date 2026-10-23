"""Validate explicit bind paths on the selected Docker daemon, never run cases.

Run this on the Docker host (including WSL), or select an explicit remote Docker
context. Remote source paths must already be absolute canonical daemon paths;
they are never converted from client-local paths or created automatically.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import uuid


PROBE = r'''
import json,os,pathlib,re,stat,uuid
checks={}; roots={}
role_names=('cases','inputs','results')+(() if os.environ.get('AI4R_PROBE_DATA_ONLY')=='1' else ('credential',))
mounts={}
for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines():
 fields=line.split()
 decode=lambda text:re.sub(r'\\([0-7]{3})',lambda match:chr(int(match[1],8)),text)
 mounts[decode(fields[4])]=decode(fields[3])
for name in role_names:
 p=pathlib.Path('/mnt')/name
 info=p.lstat()
 expected=stat.S_ISDIR(info.st_mode) if name in ('cases','inputs','results') else stat.S_ISREG(info.st_mode)
 if p.is_symlink() or not expected:raise ValueError('MOUNT_TYPE_INVALID:'+name)
 if not os.access(p,os.R_OK) or (p.is_dir() and not os.access(p,os.X_OK)):
  raise ValueError('RUNNER_UID_CANNOT_READ:'+name)
 checks[name]={'uid':info.st_uid,'gid':info.st_gid,'mode':oct(stat.S_IMODE(info.st_mode)),
   'device':info.st_dev,'inode':info.st_ino,'readable':True}
 roots[name]=(info.st_dev,info.st_ino)
 if str(p) not in mounts:raise ValueError('ACTUAL_BIND_MOUNT_REQUIRED:'+name)
 checks[name]['mount_root']=mounts[str(p)]
if len({roots[n] for n in ('cases','inputs','results')})!=3:
 raise ValueError('CONFLICTING_MOUNT_ROOTS')
names=('cases','inputs','results')
for index,first in enumerate(names):
 for second in names[index+1:]:
  a=pathlib.PurePosixPath(checks[first]['mount_root']);b=pathlib.PurePosixPath(checks[second]['mount_root'])
  if roots[first][0]==roots[second][0] and (a.is_relative_to(b) or b.is_relative_to(a)):
   raise ValueError('DAEMON_RESOLVED_MOUNT_ROOTS_OVERLAP')
base=pathlib.Path('/mnt/results'); probe=base/('.ai4r-mount-probe-'+uuid.uuid4().hex)
try:
 fd=os.open(probe,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:os.write(fd,b'ai4r-owned-mount-probe\n');os.fsync(fd)
 finally:os.close(fd)
 if probe.read_bytes()!=b'ai4r-owned-mount-probe\n':raise ValueError('OUTPUT_MOUNT_VERIFY_FAILED')
 checks['results']['writable']=True
finally:
 if probe.exists():probe.unlink()
for name in ('cases','inputs')+(() if os.environ.get('AI4R_PROBE_DATA_ONLY')=='1' else ('credential',)):
 target=pathlib.Path('/mnt')/name
 # Kernel mount flags, rather than a DAC check, establish read-only custody.
 if not os.statvfs(target).f_flag & getattr(os,'ST_RDONLY',1):
  raise ValueError('READ_ONLY_MOUNT_REQUIRED:'+name)
print(json.dumps({'schema':'ai4r-runner-mount-check:1','uid':os.geteuid(),'checks':checks}))
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Built benchmark-runner image ID or immutable tag')
    parser.add_argument('--docker-context', help='Explicit Docker context; paths refer to that daemon host')
    for name in ('cases', 'inputs', 'output', 'credential'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    command = ['docker']
    wsl_host = bool(os.environ.get('AI4R_WSL_DISTRO')) and not args.docker_context
    if wsl_host:
        from build_two_images import docker_prefix
        command = docker_prefix()
    if args.docker_context:
        command += ['--context', args.docker_context]
    sources = {name: getattr(args, name) for name in ('cases', 'inputs', 'output', 'credential')}
    try:
        context = subprocess.run(command + ['context', 'inspect'], check=True, capture_output=True, text=True)
        details = json.loads(context.stdout)[0]
        endpoint = details['Endpoints']['docker']['Host']
        remote = not endpoint.startswith(('unix://', 'npipe://'))
        # DOCKER_HOST is authoritative when explicitly set, including WSL usage.
        if not args.docker_context and os.environ.get('DOCKER_HOST'):
            endpoint = os.environ['DOCKER_HOST']
            remote = not endpoint.startswith(('unix://', 'npipe://'))
        for name, value in sources.items():
            path = PurePosixPath(value)
            if (not path.is_absolute() or path.as_posix() != value or '..' in path.parts
                    or ',' in value or any(ord(c) < 32 for c in value)):
                raise ValueError('ABSOLUTE_CANONICAL_DOCKER_HOST_PATH_REQUIRED:' + name)
            if wsl_host:
                canonical = subprocess.check_output(['wsl', '-d', os.environ['AI4R_WSL_DISTRO'], '-u', 'root', '--exec',
                    'readlink', '-e', '--', value], text=True).strip()
                if canonical != value:
                    raise ValueError('EXISTING_CANONICAL_DOCKER_HOST_PATH_REQUIRED:' + name)
            elif not remote:
                local = Path(value)
                if not local.exists() or str(local.resolve(strict=True)) != value:
                    raise ValueError('EXISTING_CANONICAL_DOCKER_HOST_PATH_REQUIRED:' + name)
        roots = [PurePosixPath(sources[name]) for name in ('cases', 'inputs', 'output')]
        for index, first in enumerate(roots):
            for second in roots[index + 1:]:
                if first.is_relative_to(second) or second.is_relative_to(first):
                    raise ValueError('CONFLICTING_CASE_INPUT_OUTPUT_ROOTS')
        for name in ('credential',):
            path = PurePosixPath(sources[name])
            if any(path.is_relative_to(root) for root in roots):
                raise ValueError('PRIVATE_CONFIG_OR_CREDENTIAL_INSIDE_DATA_ROOT:' + name)
        image = subprocess.run(command + ['image', 'inspect', args.image, '--format', '{{.Id}}'],
                               capture_output=True, text=True, check=True).stdout.strip()
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
            raise ValueError('EXACT_RUNNER_IMAGE_UNAVAILABLE')
        probe_name = 'ai4r-runner-mount-check-' + uuid.uuid4().hex
        run = command + ['run', '--rm', '--name', probe_name, '--network', 'none', '--read-only',
                         '--user', '11001:11001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                         '--memory', '128m', '--pids-limit', '16', '--entrypoint', 'python']
        for name, source in sources.items():
            destination = 'results' if name == 'output' else name
            mount = 'type=bind,src=' + source + ',dst=/mnt/' + destination
            if name != 'output':
                mount += ',readonly'
            run += ['--mount', mount]
        result = subprocess.run(run + [image, '-c', PROBE], capture_output=True, text=True, timeout=60)
        if result.returncode:
            # Probe traces only mention fixed mount roles; never print secrets.
            error = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'MOUNT_PROBE_FAILED'
            raise ValueError(error[:500])
        value = json.loads(result.stdout)
        value.update(image_id=image, remote=remote, paths=sources)
        print(json.dumps(value, indent=2) if args.json else 'Runner UID11001 can read the mounted inputs and durably write output; read-only mounts verified.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, KeyError, IndexError) as exc:
        if args.json:
            print(json.dumps({'ok': False, 'error': str(exc)[:500]}))
        else:
            print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
