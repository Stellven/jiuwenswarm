"""Live-run deployment recipe for the POC pipeline. Printing is the default; only --execute changes state.

Steps: plan | build | override | initialize | doctor. Every step reserves a receipt file
before it mutates anything, so a failed or partial step stays on record and is never
silently retried. Command output is suppressed because it can carry credentials.

Roots come from arguments and environment, never from hard-coded paths:
  AI4R_REPO   repository root (default: the checkout that holds this script)
  --out       directory for receipts and the compose override
  --fixture   clean fixture directory (holds inputs/data.json and inputs/scoring-pins.json)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(os.environ.get('AI4R_REPO') or Path(__file__).resolve().parents[2]).resolve()
STATE_VOLUME = 'ai4r-local_state'
INPUT_VOLUME = 'ai4r-local_inputs'
INPUT_MOUNT = f'type=volume,source={INPUT_VOLUME},target=/workspace/input,readonly'
STATE_MOUNT = f'type=volume,source={STATE_VOLUME},target=/var/lib/ai4r'
DATASET_IN_CONTAINER = '/workspace/input/datasets/local/data.json'
NAME = re.compile(r'[a-z0-9][a-z0-9._-]{0,62}')
TAG = re.compile(r'[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9][A-Za-z0-9._-]{0,127}')

# Release selections of the static template. They are arguments of the capture call,
# so a stale selection fails loudly at initialize instead of running the wrong stage.
SELECTIONS = {'screening_version': 'm1-5', 'requirements_version': 'm1-9'}


def profile_dir(generation):
    return f'/var/lib/ai4r/operator/poc-{generation}-sci'


def receipts_dir(out, generation):
    return Path(out) / f'receipts-{generation}'


def override_path(out, generation):
    return receipts_dir(out, generation) / f'{generation}-active.override.json'


def receipt_path(out, generation, step):
    return receipts_dir(out, generation) / f'{step}.json'


def make_override(build_id, image_tag, generation):
    """Compose override that points the app at the generation image and profile."""
    profile = profile_dir(generation)
    return {'services': {
        'ai4r': {'image': image_tag, 'environment': {
            'JIUWENSWARM_M1_CONFIG': profile + '/config.json',
            'JIUWENSWARM_M1_BOOTSTRAP_BINDINGS': profile + '/bootstrap.json',
            'JIUWENSWARM_M1_ORIGIN': 'http://127.0.0.1:5175',
            'JIUWENSWARM_M1_LOCAL_CHAT': '1', 'FRONTEND_HOST': '0.0.0.0',
            'JIUWENSWARM_DATA_DIR': '/var/lib/ai4r/native', 'JIUWENSWARM_M1_LOCAL_RESEARCH': '1',
            'JIUWENSWARM_AGENT_SDK': 'codex_subscription', 'JIUWENSWARM_M1_REUSABLE_BOOTSTRAP': '1',
            'JIUWENSWARM_M1_BIND_ADDRESS': '127.0.0.1', 'JIUWENSWARM_M1_LOCAL_WORKSPACE': '1',
            'AI4R_EXECUTION_MODE': 'm1_app_process', 'JIUWENSWARM_M1_PROFILE': '1',
            'JIUWENSWARM_M1_ACCOUNTS': '/var/lib/ai4r-accounts', 'FRONTEND_PORT': '5173',
            'JIUWENSWARM_M1_STATE': '/var/lib/ai4r', 'JIUWENSWARM_GOVERNED_REASONING_EFFORT': 'medium'}},
        'benchmark-runner': {'environment': {'AI4R_EXPECTED_BUILD': build_id}}}}


def container(image, code, mounts=()):
    return ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none',
            '--read-only', '--user', '10001:10001', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m,uid=10001,gid=10001',
            *[arg for mount in mounts for arg in ('--mount', mount)],
            '--entrypoint', '/opt/venv/bin/python', image, '-c', code]


def profile_check_code(generation):
    return (f"import os; assert not os.path.lexists({profile_dir(generation)!r}), "
            "'TARGET_PROFILE_ALREADY_EXISTS'; print('fresh')")


IDENTITY = '''import hashlib, json
from pathlib import Path
p = json.loads(Path('/usr/local/share/ai4r-build-identity.json').read_text())
b = p.pop('build_id')
assert hashlib.sha256(json.dumps(p, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == b
print(json.dumps({'build_id': b}))'''

WAIT_PORTS = '''import time
from pathlib import Path
for attempt in range(60):
    if all(Path(p).exists() for p in ('/run/ai4r/model.sock', '/run/ai4r-executor/executor.sock')):
        break
    time.sleep(1)
else:
    raise SystemExit('INITIALIZER_PORTS_UNAVAILABLE')'''


def capture_code(generation, intent_version, pins, requested_model='gpt-6.1-sol', plan_source='static'):
    profile = profile_dir(generation)
    return f'''import json, os
from contextlib import closing
from pathlib import Path
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.local_profile import capture_local_profile
assert os.geteuid() == 10001
assert not os.path.lexists({profile!r}), 'TARGET_PROFILE_ALREADY_EXISTS'
Path({profile!r}).mkdir(mode=0o700, parents=True, exist_ok=False)
with closing(SQLiteRunStore('/var/lib/ai4r', input_root='/workspace/input', recover=False)) as store:
    result = capture_local_profile(store, Path({profile!r}), development_builtin_catalog=True,
        requested_model={requested_model!r}, evidence_aware_review=True,
        screening_version={SELECTIONS['screening_version']!r}, requirements_version={SELECTIONS['requirements_version']!r},
        intent_version={intent_version!r}, public_dataset_path={DATASET_IN_CONTAINER!r}, scoring_pins={pins!r},
        plan_source={plan_source!r})
print(json.dumps(result, sort_keys=True))'''


def science_inputs(fixture):
    """Read the fixture's public dataset hash and scoring pins from host files."""
    inputs = Path(fixture) / 'inputs'
    pins = json.loads((inputs / 'scoring-pins.json').read_text('utf-8'))
    if not isinstance(pins, dict) or any(
            not isinstance(pins.get(key), str) or not re.fullmatch('[0-9a-f]{64}', pins[key])
            for key in ('holdout_sha256', 'scorer_sha256')):
        raise ValueError('INVALID_SCIENCE_PINS')
    return hashlib.sha256((inputs / 'data.json').read_bytes()).hexdigest(), pins


def preflight_code(dataset_sha256):
    return f'''import hashlib
from pathlib import Path
p = Path({DATASET_IN_CONTAINER!r})
if not p.is_file():
    raise ValueError('SCIENCE_DATASET_MISSING')
if hashlib.sha256(p.read_bytes()).hexdigest() != {dataset_sha256!r}:
    raise ValueError('SCIENCE_DATASET_SHA256_MISMATCH')
print('science dataset verified')'''


def compose_base(args):
    return ['docker', 'compose', '-p', 'ai4r-local', '-f', str(REPO / 'deploy/m1/compose.benchmark-runner.yaml'),
            '-f', str(override_path(args.out, args.generation))]


def commands(step, args, build_id='<verified build_id from the build receipt>'):
    """Structured argv lists with complete Python code; no shell interpolation."""
    image = args.image_tag
    fresh = profile_check_code(args.generation)
    state_ro = [STATE_MOUNT + ',readonly']
    if step == 'build':
        return [
            ['git', '-C', str(REPO), 'branch', '--show-current'],
            ['docker', 'info', '--format', '{{.OSType}}'],
            ['docker', 'image', 'ls', '--quiet', '--filter', 'reference=' + image],
            ['docker', 'volume', 'inspect', STATE_VOLUME, '--format', '{{.Name}}'],
            container(args.check_image or '<--check-image>', fresh, state_ro),
            ['docker', 'build', '--file', 'deploy/m1/Dockerfile.app', '--target', 'production',
             '--tag', image, '--progress', 'plain', '.'],
            ['docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
            container(image, IDENTITY)]
    if step == 'initialize':
        dataset_sha, pins = science_inputs(args.fixture)
        base = compose_base(args)
        python = '/opt/venv/bin/python'
        return [
            container(image, fresh, state_ro),
            ['docker', 'volume', 'inspect', INPUT_VOLUME, '--format', '{{.Name}}'],
            container(image, preflight_code(dataset_sha), [INPUT_MOUNT]),
            container(image, capture_code(args.generation, args.intent_version, pins, plan_source=args.plan_source),
                      [STATE_MOUNT, INPUT_MOUNT]),
            base + ['up', '-d', '--no-build', '--pull', 'never', 'ai4r'],
            base + ['exec', '-T', '--user', '10001:10001', 'ai4r', python, '-c', WAIT_PORTS],
            base + ['exec', '-T', '--user', '10001:10001', 'ai4r', python, '-m', 'jiuwenswarm.research.initialize', '--json'],
            base + ['up', '-d', '--force-recreate', '--no-build', '--pull', 'never', 'ai4r']]
    if step == 'doctor':
        base = compose_base(args)
        return [base + ['--profile', 'benchmark', 'up', '-d', '--no-build', '--pull', 'never', 'benchmark-runner'],
                base + ['exec', '-T', 'benchmark-runner', 'benchmark-runner', 'doctor', '--cases', '/cases/cases.json',
                        '--inputs', '/inputs', '--output', '/results', '--json']]
    return [{'write_exclusive': str(override_path(args.out, args.generation)),
             'json': make_override(build_id, image, args.generation)}]


def run(argv):
    # Never forward Docker logs, inherited environment, tokens or raw errors.
    print(json.dumps({'running_argv': argv}, indent=2), flush=True)
    result = subprocess.run(argv, cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError('COMMAND_FAILED (output suppressed to protect credentials)')
    return result.stdout.strip()


def verified_build(args):
    value = json.loads(receipt_path(args.out, args.generation, 'build').read_text('utf-8'))
    if value.get('status') != 'complete' or value.get('image') != args.image_tag:
        raise ValueError('SUCCESSFUL_OWNED_BUILD_REQUIRED')
    if run(['docker', 'image', 'inspect', args.image_tag, '--format', '{{.Id}}']) != value['image_id']:
        raise ValueError('TARGET_IMAGE_CHANGED')
    observed = json.loads(run(container(args.image_tag, IDENTITY)))['build_id']
    if observed != value['build_id'] or not re.fullmatch('[0-9a-f]{64}', observed):
        raise ValueError('BUILD_ID_CHANGED')
    return value


def execute(step, args):
    receipts_dir(args.out, args.generation).mkdir(parents=True, exist_ok=True)
    path = receipt_path(args.out, args.generation, step)
    with path.open('x', encoding='utf-8') as stream:  # reserve before any mutation
        json.dump({'step': step, 'status': 'started', 'image': args.image_tag}, stream)
    receipt = {'step': step, 'image': args.image_tag, 'profile_directory': profile_dir(args.generation),
               'status': 'failed', 'model_calls': 0}
    try:
        if step == 'build':
            recipe = commands(step, args)
            branch = run(recipe[0])
            if args.expected_branch and branch != args.expected_branch:
                raise ValueError('WRONG_SOURCE_BRANCH')
            receipt['source_branch'] = branch
            run(recipe[1])
            if run(recipe[2]):
                raise ValueError('TARGET_IMAGE_ALREADY_EXISTS')
            for cmd in recipe[3:6]:
                run(cmd)
            receipt['image_id'] = run(recipe[6])
            receipt['build_id'] = json.loads(run(recipe[7]))['build_id']
            if not re.fullmatch('[0-9a-f]{64}', receipt['build_id']):
                raise ValueError('INVALID_BUILD_ID')
        else:
            build = verified_build(args)
            receipt.update(build_id=build['build_id'], image_id=build['image_id'])
            recipe = commands(step, args, build['build_id'])
            print(json.dumps({'resolved': recipe}, indent=2))
            expected = make_override(build['build_id'], args.image_tag, args.generation)
            if step == 'override':
                run(container(args.image_tag, profile_check_code(args.generation), [STATE_MOUNT + ',readonly']))
                with override_path(args.out, args.generation).open('x', encoding='utf-8') as stream:
                    json.dump(expected, stream, indent=2)
                    stream.write('\n')
            else:
                if json.loads(override_path(args.out, args.generation).read_text('utf-8')) != expected:
                    raise ValueError('OVERRIDE_CHANGED_OR_MISSING')
                if step == 'doctor':
                    prior = json.loads(receipt_path(args.out, args.generation, 'initialize').read_text('utf-8'))
                    if prior.get('status') != 'complete':
                        raise ValueError('SUCCESSFUL_INITIALIZATION_REQUIRED')
                else:
                    run(['docker', 'volume', 'inspect', STATE_VOLUME, '--format', '{{.Name}}'])
                for index, cmd in enumerate(recipe):
                    output = run(cmd)
                    if step == 'initialize' and cmd[-2:] == ['jiuwenswarm.research.initialize', '--json']:
                        result = json.loads(output)
                        if (result.get('status') != 'initialized' or result.get('diagnostics')
                                or result.get('calibration_results')
                                or result.get('actor', {}).get('os_uid') != 10001
                                or result.get('qualification_status') != 'not_run'):
                            raise ValueError('INITIALIZATION_BLOCKED')
                        receipt['initialization'] = {key: result[key] for key in (
                            'status', 'diagnostics', 'qualification_status', 'runtime_ready',
                            'configuration_ref', 'binding_ref', 'static_template_ref')}
                    if step == 'doctor' and index == 1:
                        result = json.loads(output)
                        if result.get('ready') is not True or result.get('build_id') != build['build_id']:
                            raise ValueError('DOCTOR_NOT_READY_OR_BUILD_MISMATCH')
                        receipt['doctor'] = {key: result[key] for key in ('ready', 'build_id')}
        receipt['status'] = 'complete'
    finally:
        path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('step', choices=('plan', 'build', 'override', 'initialize', 'doctor'))
    p.add_argument('--generation', required=True, help='name of this build generation, for example r5h')
    p.add_argument('--image-tag', required=True, help='image tag to build and run, for example ai4r:live-r5h')
    p.add_argument('--out', type=Path, required=True, help='receipts directory root')
    p.add_argument('--fixture', type=Path, required=True, help='clean fixture directory with inputs/')
    p.add_argument('--check-image', help='existing image used for the pre-build profile freshness check (build step)')
    p.add_argument('--intent-version', default='m1-8')
    p.add_argument('--plan-source', choices=('static', 'planned'), default='static',
                   help='static reproduces the recorded r5 runs; planned lets the Planner compose the pipeline')
    p.add_argument('--expected-branch', help='refuse to build unless the checkout is on this branch')
    p.add_argument('--execute', action='store_true')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if not NAME.fullmatch(args.generation) or not TAG.fullmatch(args.image_tag):
        parser().error('unsafe --generation or --image-tag')
    args.out = args.out.resolve()
    if args.step == 'build' and args.execute and not args.check_image:
        parser().error('--check-image is required to execute the build step')
    steps = ('build', 'override', 'initialize', 'doctor') if args.step == 'plan' else (args.step,)
    print(json.dumps({'mode': 'execute' if args.execute and args.step != 'plan' else 'dry-run', 'cwd': str(REPO),
                      'steps': [{'step': s, 'commands': commands(s, args),
                                 'receipt': str(receipt_path(args.out, args.generation, s))} for s in steps]}, indent=2))
    if args.execute and args.step != 'plan':
        try:
            execute(args.step, args)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            print('Deployment refused or failed; no raw process output is disclosed. Check the step receipt and prerequisites.',
                  file=sys.stderr)
            return 0 if args.step == 'doctor' else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
