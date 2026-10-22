"""Replace only the idle CLI container using a fresh immutable Compose file."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import uuid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image')
    parser.add_argument('--http-authority')
    parser.add_argument('--refresh-credential', action='store_true', help='Issue a fresh finite grant through the running app operator and replace only the idle runner')
    args = parser.parse_args(argv)
    if not args.image and not args.http_authority and not args.refresh_credential:
        parser.error('choose --image, --http-authority or --refresh-credential')
    runtime = Path(os.environ['LOCALAPPDATA']) / 'AI4Research/runtime'
    spec = importlib.util.spec_from_file_location('existing_ai4r_operator', runtime / 'poc-clean-isolation.py')
    operator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operator)
    profile = json.loads(operator.ACTIVE.read_bytes())
    ops, project = operator.ops, profile['project']
    if profile['migration'] != 'existing-project-two-images':
        raise ValueError('EXACT_EXISTING_TWO_SERVICE_PROJECT_REQUIRED')
    compose = json.loads(ops.wsl('cat', '--', profile['compose']))
    idle = """import psutil
for process in psutil.process_iter(['cmdline']):
 args=process.info['cmdline'] or []
 assert not ('benchmark-runner' in ' '.join(args) and any(value in args for value in ('run','resume'))),'RUNNER_CAMPAIGN_ACTIVE'
print('idle')
"""
    ops.docker('exec', project + '-benchmark-runner-1', 'python', '-c', idle)
    image = json.loads(ops.docker('image', 'inspect', args.image or profile['runner_image_id']))[0]['Id']
    compose['services']['benchmark-runner']['image'] = image
    if args.http_authority:
        compose['services']['benchmark-runner']['environment']['AI4R_HTTP_AUTHORITY'] = args.http_authority
    if args.refresh_credential:
        # Native startup revokes old grant families. The existing root-owned
        # account/workspace binding selects a finite replacement, never a broad
        # browser credential. Output names are exclusive and never reused.
        name = 'runner-token-' + uuid.uuid4().hex
        container_path = '/run/benchmark-runner-operator/' + name
        grant = json.loads(ops.docker('exec', '--user', '0:0', project + '-ai4r-1',
            '/opt/venv/bin/python', '-m', 'jiuwenswarm.research.runner_grants', 'issue',
            '--binding-file', '/run/benchmark-runner-operator/binding.json', '--output', container_path))
        if grant.get('status') != 'issued':
            raise ValueError('SCOPED_RUNNER_GRANT_UNAVAILABLE')
        new_source = str(Path(profile['runner_credential']).parent).replace('\\', '/') + '/' + name
        for mount in compose['services']['benchmark-runner']['volumes']:
            if mount.get('target') == '/run/benchmark-runner/token':
                mount['source'] = new_source
        profile['runner_credential'] = new_source
        profile['runner_grant'] = grant
    new_path = profile['patch_root'] + '/compose-runner-' + uuid.uuid4().hex + '.json'
    raw = json.dumps(compose, separators=(',', ':')).encode()
    ops.write_new(new_path, raw)
    ops.docker('compose', '-p', project, '-f', new_path, 'up', '-d', '--no-deps', '--no-build', '--pull', 'never', 'benchmark-runner')
    profile.update(compose=new_path, runner_image_id=image, compose_sha256=hashlib.sha256(raw).hexdigest())
    from migrate_benchmark_runner import _publish_active
    _publish_active(operator, profile)
    print(json.dumps({'status': 'runner_configured', 'image_id': image,
                      'app_restarted': False, 'build_id': profile['build_id']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
