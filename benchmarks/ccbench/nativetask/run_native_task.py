"""Bare native task driver. External work requires explicit --execute.

Every write (attempts, sessions, ledger) goes under --out. Product code comes from AI4R_CODE_ROOT, the codex
binary from --binary / AI4R_CODEX_BIN / PATH."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import roots  # noqa: E402

REPO = roots.code_root()
PYTHON = Path(sys.executable)
RUNTIME = HERE / 'native-runtime-en'    # English overlay of benchmarks.harbor_suite.native_value (copied from the old traps/)
ROOT = None                             # output root; main() sets it from --out
EFFORTS = ('low', 'medium', 'high')
# The portable capsule MCP server (jiuwenswarm/capsule_runtime/README.md) runs as a stdio child of the agent inside the
# container. The image's own jiuwenswarm is older and has no capsule_runtime, so the packages the server imports are staged
# from this checkout and mounted read-only at /capsule-src. Only the MCP child gets PYTHONPATH=/capsule-src; the agent
# process keeps the image's JiuwenSwarm.
CAPSULE_PACKAGES = ('capsule_runtime', 'research', 'research_assets', 'research_contracts', 'research_records',
                    'research_router', 'research_rsi', 'research_sidecar')
CAPSULE_MOUNT = '/capsule-src'
CAPSULE_SERVER = {'name': 'capsules', 'enabled': True, 'transport': 'stdio', 'command': '/opt/venv/bin/python',
                  'args': ['-B', '-m', 'jiuwenswarm.capsule_runtime.mcp'],
                  'env': {'PYTHONPATH': CAPSULE_MOUNT, 'HOME': '/tmp', 'PYTHONDONTWRITEBYTECODE': '1'}}
DEFAULT_IMAGE = 'ai4r:ccbench-native'   # rebuilt opponent; the sweep's ai4r:cc-value-medium-20261026 is gone and had no recipe
REBUILD_HINT = (
    'Image not found. Build it with `scripts/ai4r-bench build-native --yes --out DIR` '
    '(tags ai4r:ccbench-native from deploy/m1/Dockerfile.app, target production) and pass --image ai4r:ccbench-native, '
    'or reuse an existing M1 image such as ai4r:cc-v1-baseline. See benchmarks/ccbench/nativetask/README.md.')


def dump(path, value, exclusive=False):
    with path.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', value):
        raise ValueError('unsafe attempt/session ID')
    return value


def bounded(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise ValueError('linked output path refused')
    path = path.resolve()
    if path == ROOT or not path.is_relative_to(ROOT):
        raise ValueError('all writes, including ledger writes, must stay under the --out directory')
    return path


def snapshot(source, target):
    if any(p.is_symlink() or p.is_junction() for p in (source, *source.parents)):
        raise ValueError('linked input/skill refused')
    source = source.resolve()
    if target.resolve().is_relative_to(source):
        raise ValueError('snapshot destination must not be inside its source')
    if not source.is_dir():
        raise ValueError('snapshot source must be a directory')
    for path in (source, *source.rglob('*')):
        if path.is_symlink() or path.is_junction():
            raise ValueError('linked input/skill refused')
    shutil.copytree(source, target)
    return {str(p.relative_to(target)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(target.rglob('*')) if p.is_file()}


def spec_for(args):
    task = args.task_file.read_text(encoding='utf-8-sig')
    if not task.strip():
        raise ValueError('task text is empty')
    if not args.inputs_dir.is_dir():
        raise ValueError('inputs directory is missing')
    if args.skill_dir and not (args.skill_dir / 'SKILL.md').is_file():
        raise ValueError('skill directory requires SKILL.md')
    spec = dict(variant='native-skills' if args.skill_dir else 'native', task=task,
                inputs_dir='/campaign/inputs', skill_dirs=['/campaign/skill'] if args.skill_dir else [],
                completion_directory='/campaign/broker', model=args.model, reasoning_effort=args.effort,
                mode='agent.work.normal', max_model_calls=args.max_calls, max_tool_calls=80,
                wall_time_s=args.wall_s)
    servers = mcp_servers(args)
    if servers:
        spec['mcp_servers'] = servers      # absent for every other arm, so their specs are unchanged
    return spec


def mcp_servers(args):
    """mcp.servers entries to inject into JiuwenSwarm's config for this run ([] for the plain arms).

    --mcp-config FILE: JSON list of entries, or {"servers": [...]} (the shape of config.yaml mcp.servers; stdio only).
    --capsule-mcp: the portable capsule server (CAPSULE_SERVER), staged and mounted as described above."""
    servers = []
    if getattr(args, 'mcp_config', None):
        data = json.loads(Path(args.mcp_config).read_text(encoding='utf-8-sig'))
        servers += data.get('servers') if isinstance(data, dict) else data
    if getattr(args, 'capsule_mcp', False):
        servers.append(json.loads(json.dumps(CAPSULE_SERVER)))
    if any(not isinstance(s, dict) or not s.get('name') or s.get('transport') != 'stdio' or not s.get('command') for s in servers):
        raise ValueError('mcp entries must be stdio entries with name and command')
    if len({s['name'] for s in servers}) != len(servers):
        raise ValueError('duplicate mcp server name')
    if servers and getattr(args, 'skill_dir', None):
        raise ValueError('MCP servers and --skill-dir are different arms; use one')
    return servers


def stage_capsule_src(target, source=None):
    """Copy the packages the capsule server imports (no bytecode) and return their file hashes."""
    source = Path(source or REPO / 'jiuwenswarm')
    package = target / 'jiuwenswarm'
    package.mkdir(parents=True)
    shutil.copyfile(source / '__init__.py', package / '__init__.py')
    for name in CAPSULE_PACKAGES:
        shutil.copytree(source / name, package / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    return {str(p.relative_to(target)).replace(chr(92), '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(target.rglob('*')) if p.is_file()}


def command_plan(args, attempt):
    session = ROOT / 'sessions' / attempt
    campaign = session / 'native'
    arm = 'native-skills' if args.skill_dir else 'native-capsule-mcp' if getattr(args, 'capsule_mcp', False) else 'native'
    binary = args.binary or roots.codex_bin() or 'codex'
    broker = [str(PYTHON), '-B', str(Path(__file__).resolve()), '_broker',
              '--session-id', attempt, '--out', str(ROOT), '--binary', binary, '--execute']
    worker = ['docker', 'run', '--rm', '--name', 'nativetask-' + attempt, '--network', 'none',
              '--read-only', '--user', '10001:10001', '--cap-drop', 'ALL',
              '--security-opt', 'no-new-privileges:true', '--memory', '2g', '--pids-limit', '256',
              '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001',
              '-e', 'HOME=/tmp', '-e', 'PYTHONDONTWRITEBYTECODE=1',
              '-e', 'PYTHONPATH=/runtime:/opt/ai4r', '--mount',
              f'type=bind,source={args.runtime.resolve()},target=/runtime,readonly', '--mount',
              f'type=bind,source={campaign},target=/campaign', '--mount',
              f'type=bind,source={campaign / "inputs"},target=/campaign/inputs,readonly']
    if args.skill_dir:
        worker += ['--mount', f'type=bind,source={campaign / "skill"},target=/campaign/skill,readonly']
    if getattr(args, 'capsule_mcp', False):
        worker += ['--mount', f'type=bind,source={session / "capsule-src"},target={CAPSULE_MOUNT},readonly']
    worker += ['--entrypoint', '/opt/venv/bin/python', args.image, '-B', '-m',
               'benchmarks.harbor_suite.native_value', 'run', '--spec', '/campaign/spec.json',
               '--output', '/campaign/run']
    return dict(spec=spec_for(args), broker=broker, worker=worker,
                ledger={'path': str(bounded(args.ledger)), 'pair': attempt, 'arm': arm,
                        'call_bound': args.max_calls, 'model': args.model, 'effort': args.effort})


def image_identity(image):
    """Tag, image ID and repo digests from `docker image inspect`; ValueError (with the rebuild note) if absent."""
    try:
        found = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}\t{{json .RepoDigests}}'],
                               capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError('cannot run docker to inspect image %s: %s' % (image, exc))
    if found.returncode != 0 or '\t' not in found.stdout:
        raise ValueError('native image %s is not present locally. %s' % (image, REBUILD_HINT))
    image_id, digests = found.stdout.strip().split('\t', 1)
    return dict(tag=image, id=image_id, repo_digests=json.loads(digests))


def schedule_class():
    # Host harness only; never import or invoke this during planning/tests.
    sys.path.insert(0, str(REPO))
    from benchmarks.harbor_suite.value_schedule import Schedule
    return Schedule


def reserve(plan, session):
    pin = plan['ledger']
    ledger = schedule_class()(pin['path'])
    try:
        ledger.reserve(pin['pair'], hashlib.sha256(plan['spec']['task'].encode()).hexdigest(),
                       {pin['arm']: pin['call_bound']}, requested_model=pin['model'])
        remaining = ledger.claim_envelope(pin['pair'], pin['arm'], pin['pair'] + '-envelope',
                                         pin['call_bound'], model=pin['model'], effort=pin['effort'])
        dump(session / 'envelope.json', dict(pin, deadline=time.time() + remaining), exclusive=True)
        if remaining < plan['spec']['wall_time_s'] + 60:
            raise ValueError('insufficient ledger wall budget; envelope retained for reconciliation')
    finally:
        ledger.close()


class EnvelopeCalls:
    """value_host Schedule interface within one already charged run envelope.

    The upstream broker normally uses Schedule.claim per completion. That cannot
    coexist with a dispatched envelope. Keep those claims durable locally instead;
    never charge both the envelope and its individual calls to the same ledger.
    """
    def __init__(self, session):
        self.session = session
        self.pin = json.loads((session / 'envelope.json').read_text('utf-8'))
        self.calls = session / 'calls'
        self.calls.mkdir(exist_ok=True)

    def claim(self, pair, arm, request_id, *, model, effort):
        identifier(request_id)
        rows = list(self.calls.glob('*.claim.json'))
        if (pair != self.pin['pair'] or arm != self.pin['arm'] or
                model != self.pin['model'] or effort != self.pin.get('effort', 'medium')):
            raise ValueError('envelope identity mismatch')
        if any(not p.with_name(p.name.replace('.claim.', '.finish.')).exists() for p in rows):
            raise ValueError('unresolved completion; reconcile before another dispatch')
        for p in self.calls.glob('*.finish.json'):
            if json.loads(p.read_text('utf-8'))['state'] == 'unknown':
                raise ValueError('unknown completion blocks dispatch')
        if len(rows) >= self.pin['call_bound'] or time.time() >= self.pin['deadline']:
            raise ValueError('envelope budget exhausted')
        dump(self.calls / (request_id + '.claim.json'),
             dict(request_id=request_id, model=model, effort=effort), exclusive=True)
        return self.pin['deadline'] - time.time()

    def finish(self, request_id, state, *, evidence, effective_model=None, effective_effort=None):
        identifier(request_id)
        if not (self.calls / (request_id + '.claim.json')).is_file():
            raise ValueError('unclaimed completion')
        if state not in {'completed', 'failed', 'unknown', 'contained'}:
            raise ValueError('invalid completion state')
        if state == 'completed' and (effective_model != self.pin['model'] or effective_effort != self.pin.get('effort', 'medium')):
            raise ValueError('completion identity mismatch')
        dump(self.calls / (request_id + '.finish.json'), dict(state=state, evidence=evidence,
             effective_model=effective_model, effective_effort=effective_effort), exclusive=True)

    def status(self):
        return {'calls_consumed': len(list(self.calls.glob('*.claim.json')))}

    def close(self):
        pass


def allow_effort(effort):
    """Broker process only: let the host path accept low/high as well as medium.

    The product's governed-Codex path pins medium in literals (local_model_codex._validate,
    value_host.validate_request) and in local_models.CODEX_EFFORTS. This benchmark broker widens
    that to the single effort its ledger is pinned to; the product modules on disk are unchanged.
    The real effort still reaches Codex (thread/start config and app-server -c override)."""
    if effort not in EFFORTS:
        raise ValueError('effort must be one of ' + ', '.join(EFFORTS))
    if effort == 'medium':
        return
    from jiuwenswarm.research import local_model_codex, local_models
    from benchmarks.harbor_suite import value_host
    local_models.CODEX_EFFORTS = frozenset({'medium', effort})
    check_policy, check_request = local_model_codex._validate, value_host.validate_request
    def validate(payload):
        model = payload.get('model') if isinstance(payload, dict) else None
        if isinstance(model, dict) and model.get('reasoning_effort') == effort:
            payload = dict(payload, model=dict(model, reasoning_effort='medium'))
        return check_policy(payload)
    def request(value, filename):
        if isinstance(value, dict) and value.get('reasoning_effort') == effort:
            check_request(dict(value, reasoning_effort='medium'), filename)
            return value
        return check_request(value, filename)
    local_model_codex._validate = validate
    value_host.validate_request = request


def bridge_system():
    """AI4R_BRIDGE_SYSTEM=1 replaces the product's 'Tools are unavailable' developer message with BRIDGE_SYSTEM for
    every model and arm (luna obeys the old message and never calls tools). Off by default, so runs stay comparable
    with earlier sessions; the attempt record says which one ran."""
    return os.environ.get('AI4R_BRIDGE_SYSTEM') == '1'


def broker_main(args):
    session = bounded(ROOT / 'sessions' / identifier(args.session_id))
    # An internal broker invocation is also single-use, including failed starts.
    (session / 'broker-started').open('x', encoding='utf-8').close()
    pin = json.loads((session / 'envelope.json').read_text('utf-8'))
    sys.path.insert(0, str(REPO))
    from benchmarks.harbor_suite import value_host, native_value
    # Reuse exact host protocol, receipt validation and model dispatch. Only the
    # accounting interface changes from per-call charges to this run's envelope.
    value_host.Schedule = lambda _: EnvelopeCalls(session)
    allow_effort(pin['effort'])
    original_complete = value_host.complete
    host_responses = session / 'host-responses'
    host_responses.mkdir(exist_ok=False)
    async def complete(request, **kwargs):
        result = await original_complete(request, **kwargs)
        # Preserve validated broker results outside the worker's writable mount.
        dump(host_responses / (request['request_id'] + '.response.json'), result, exclusive=True)
        return result
    value_host.complete = complete
    record = json.loads((session / 'plan.json').read_text('utf-8'))
    return asyncio.run(value_host.serve(argparse.Namespace(directory=session / 'native/broker',
        private=session / 'private-broker', binary=Path(args.binary), ledger=Path(pin['path']),
        pair=pin['pair'], arm=pin['arm'], seconds=record['spec']['wall_time_s'] + 60,
        system=native_value.BRIDGE_SYSTEM if bridge_system() else None)))


def collect(session):
    """Copy original evidence; missing files are explicit, never fabricate success."""
    session = bounded(session)
    source = session / 'native/run'
    bounded(source)
    missing, skipped = [], []
    # Recollection replaces each prior copied tree as a whole. Keep the earlier
    # snapshot for audit rather than merging stale files into a newer project.
    prior = session / 'collections' / ('prior-' + uuid.uuid4().hex)
    def copy(src, dst):
        if src.is_symlink() or src.is_junction():
            skipped.append(str(src.relative_to(session)))
        elif src.is_dir():
            dst.mkdir(exist_ok=True)
            for child in sorted(src.iterdir()):
                copy(child, dst / child.name)
        elif src.is_file():
            shutil.copyfile(src, dst)
    for name in ('project', 'events.jsonl', 'result.json', 'evidence', 'trajectory',
                 'controller-start.json', 'controller-finished.json', 'controller-timeout.json',
                 'skill-inventory.json', 'assignment.json', 'stdout.log', 'stderr.log'):
        destination = bounded(session / name)
        if destination.exists():
            prior.mkdir(parents=True, exist_ok=True)
            destination.rename(prior / name)
        if (source / name).exists():
            copy(source / name, session / name)
        else:
            missing.append(name)
    finals, malformed = [], 0
    events = source / 'events.jsonl'
    if events.is_file() and not events.is_symlink():
        for line in events.read_text('utf-8').splitlines():
            try:
                payload = json.loads(line).get('payload') or {}
                if payload.get('event_type') == 'chat.final':
                    finals.append(payload)
            except (ValueError, AttributeError):
                malformed += 1
    dump(session / 'final-messages.json', finals)
    (session / 'final-message.txt').write_text('\n\n'.join(str(p.get('content', '')) for p in finals), encoding='utf-8')
    usage = []
    # Prefer host-validated results, inaccessible to the agent. Raw shared broker
    # files remain in native/broker for diagnosing transport failures.
    usage_source = session / 'host-responses'
    if not usage_source.is_dir():
        usage_source = session / 'native/broker'
    for path in sorted(usage_source.glob('*.response.json')):
        if path.is_symlink():
            skipped.append(str(path.relative_to(session)))
            continue
        try:
            row = json.loads(path.read_text('utf-8'))
            usage.append({k: row.get(k) for k in ('request_id', 'status', 'identity', 'reasoning_effort', 'usage', 'elapsed_s')})
        except ValueError:
            missing.append('invalid broker response: ' + path.name)
    dump(session / 'usage.json', usage)
    receipt = dict(missing=missing, skipped_links=skipped, final_messages=len(finals),
                   malformed_event_lines=malformed, usage_records=len(usage),
                   usage_source=str(usage_source.relative_to(session)),
                   oracle_measurement_performed=False)
    dump(session / 'collection.json', receipt)
    return receipt


def reconcile(plan, session, broker_rc, worker_rc):
    """Only clean broker shutdown plus all original terminal receipts releases calls."""
    pin = plan['ledger']
    calls = list((session / 'calls').glob('*.claim.json'))
    known = broker_rc == 0 and worker_rc is not None
    for claim in calls:
        finish = claim.with_name(claim.name.replace('.claim.', '.finish.'))
        if not finish.exists() or json.loads(finish.read_text('utf-8'))['state'] == 'unknown':
            known = False
    ledger = schedule_class()(pin['path'])
    try:
        ledger.finish_envelope(pin['pair'] + '-envelope',
            ('completed' if worker_rc == 0 else 'failed') if known else 'unknown',
            actual_calls=len(calls) if known else None, evidence=str(session / 'collection.json'),
            effective_model=pin['model'] if known else None, effective_effort=pin['effort'] if known else None)
        if known:
            ledger.finish_pair(pin['pair'])
    finally:
        ledger.close()


def execute(plan, session, binary):
    if not Path(binary).is_file():
        raise ValueError('--binary must name an existing qualified Codex executable')
    reserve(plan, session)
    broker = None
    worker_rc = broker_rc = None
    failure = None
    env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    try:
        with (session / 'broker.stdout').open('xb') as bout, (session / 'broker.stderr').open('xb') as berr, \
             (session / 'worker.stdout').open('xb') as wout, (session / 'worker.stderr').open('xb') as werr:
            broker = subprocess.Popen(plan['broker'], cwd=REPO, env=env, stdout=bout, stderr=berr)
            try:
                worker_rc = subprocess.run(plan['worker'], cwd=REPO, env=env, stdout=wout,
                                           stderr=werr, timeout=plan['spec']['wall_time_s'] + 90).returncode
            except Exception as exc:
                failure = type(exc).__name__
                # subprocess.run kills the Docker CLI on timeout, not necessarily
                # the container. Stop this attempt's exact container explicitly.
                try:
                    subprocess.run(['docker', 'stop', '--time', '15',
                                    'nativetask-' + plan['ledger']['pair']],
                                   cwd=REPO, env=env, stdout=wout, stderr=werr, timeout=30)
                except Exception:
                    failure += ':container_stop_unconfirmed'
            finally:
                (session / 'native/broker/STOP').write_text('', encoding='utf-8')
                try:
                    broker_rc = broker.wait(timeout=140)
                except subprocess.TimeoutExpired:
                    broker.terminate()
                    try:
                        broker.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        broker.kill()
                        broker.wait(timeout=15)
                    broker_rc = -1
    except Exception as exc:
        failure = type(exc).__name__
    finally:
        receipt = collect(session)
        dump(session / 'process-outcome.json', dict(worker_returncode=worker_rc,
             broker_returncode=broker_rc, error=failure))
        reconcile(plan, session, broker_rc, worker_rc)
    if broker_rc != 0:
        print(f'FAILURE: completion broker exited {broker_rc}; partial evidence collected; envelope unresolved.', file=sys.stderr)
    if worker_rc != 0 or failure:
        print(f'FAILURE: native worker exited {worker_rc}; evidence retained.', file=sys.stderr)
    # The native result remains independently inspectable even on broker failure.
    return 0 if broker_rc == worker_rc == 0 and not failure and not receipt['skipped_links'] else 1


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    for action in ('plan', 'run'):
        q = sub.add_parser(action)
        q.add_argument('--task-file', type=Path, required=True)
        q.add_argument('--inputs-dir', type=Path, required=True)
        q.add_argument('--skill-dir', type=Path)
        q.add_argument('--model', choices=('gpt-6.1-sol', 'gpt-6-luna'), default='gpt-6.1-sol')
        q.add_argument('--ledger', type=Path, required=True)
        q.add_argument('--wall-s', type=int, choices=range(1, 601), default=600, metavar='1..600')
        q.add_argument('--max-calls', type=int, choices=range(1, 81), default=80, metavar='1..80')
        q.add_argument('--runtime', type=Path, default=RUNTIME)
        q.add_argument('--image', default=DEFAULT_IMAGE)
        q.add_argument('--capsule-mcp', action='store_true', help='register the portable capsule MCP server (python -m jiuwenswarm.capsule_runtime.mcp) with JiuwenSwarm; stages the capsule packages of AI4R_CODE_ROOT read-only')
        q.add_argument('--mcp-config', type=Path, help='JSON file of extra mcp.servers entries (stdio) injected into JiuwenSwarm config for this run')
        q.add_argument('--effort', choices=EFFORTS, default='medium', help='reasoning effort; the ledger must have been created with the same --effort (one ledger per effort)')
        q.add_argument('--binary', default=None, help='qualified signed-in codex executable (default: AI4R_CODEX_BIN, then codex on PATH)')
        q.add_argument('--out', type=Path, required=True, help='all attempts, sessions and the ledger live under this directory')
        q.add_argument('--attempt-id')
        q.add_argument('--execute', action='store_true')
    q = sub.add_parser('collect')
    q.add_argument('--session-id', required=True)
    q.add_argument('--attempt-id')
    q.add_argument('--out', type=Path, required=True)
    q.add_argument('--execute', action='store_true', help='copy local evidence only; no model/Docker/ledger')
    q = sub.add_parser('init-ledger', help='create <out>/ledger.sqlite3 (a value_schedule campaign ledger); refuses to overwrite')
    q.add_argument('--out', type=Path, required=True)
    q.add_argument('--max-calls', type=int, default=256, help='campaign call ceiling (upstream maximum 256)')
    q.add_argument('--wall-s', type=int, default=10800, help='campaign wall-time ceiling in seconds (upstream maximum 10800)')
    q.add_argument('--effort', choices=EFFORTS, default='medium', help='effort this ledger is pinned to; it cannot be mixed later')
    q = sub.add_parser('_broker', help=argparse.SUPPRESS)
    q.add_argument('--session-id', required=True)
    q.add_argument('--binary', required=True)
    q.add_argument('--out', type=Path, required=True)
    q.add_argument('--execute', action='store_true')
    return p


def main(argv=None):
    global ROOT
    args = parser().parse_args(argv)
    ROOT = Path(args.out).resolve()
    if args.action == 'init-ledger':
        path = bounded(ROOT / 'ledger.sqlite3')
        schedule_class().create(path, max_calls=args.max_calls, wall_s=args.wall_s, effort=args.effort).close()
        print(json.dumps(dict(ledger=str(path), max_calls=args.max_calls, wall_s=args.wall_s, effort=args.effort)))
        return 0
    if args.action == '_broker':
        if not args.execute:
            raise ValueError('internal broker requires --execute')
        return broker_main(args)
    attempt = identifier(args.attempt_id or ('PLAN' if args.action == 'plan' else 'native-' + uuid.uuid4().hex))
    if args.action == 'plan':
        print(json.dumps(command_plan(args, attempt), indent=2, sort_keys=True))
        return 0
    image = dict(tag=getattr(args, 'image', None), inspected=False)
    if args.action == 'run' and args.execute:
        # Fail fast, before any file is written or the ledger is touched.
        binary = args.binary or roots.codex_bin()
        if not binary or not Path(binary).is_file():
            print('FAILURE: codex binary not found (%s). Put `codex` on PATH, set AI4R_CODEX_BIN, or pass --binary.' % (binary or 'none'), file=sys.stderr)
            return 1
        args.binary = str(binary)
        try:
            image = dict(image_identity(args.image), inspected=True)
        except ValueError as exc:
            print('FAILURE: ' + str(exc), file=sys.stderr)
            return 1
    ROOT.mkdir(parents=True, exist_ok=True)
    attempts = bounded(ROOT / 'attempts')
    attempts.mkdir(exist_ok=True)
    record_path = bounded(attempts / (attempt + '.json'))
    record = dict(attempt_id=attempt, action=args.action, execute=args.execute, status='started', image=image,
                  effort=getattr(args, 'effort', None),
                  product=roots.product_commit(), bridge_system=bridge_system())    # {'commit', 'dirty'} of AI4R_CODE_ROOT
    dump(record_path, record, exclusive=True)
    try:
        if args.action == 'collect':
            session = bounded(ROOT / 'sessions' / identifier(args.session_id))
            if not session.is_dir():
                raise ValueError('unknown source session')
            record['session_id'] = args.session_id
            print(json.dumps(dict(collect_from=str(session), execute=args.execute), sort_keys=True))
            if args.execute:
                collect(session)
            code = 0
        else:
            plan = command_plan(args, attempt)
            record['plan'] = plan
            dump(record_path, record)
            print(json.dumps(plan, indent=2, sort_keys=True))
            code = 0
            if args.execute:
                session = bounded(ROOT / 'sessions' / attempt)
                session.mkdir(parents=True, exist_ok=False)
                campaign = session / 'native'
                campaign.mkdir()
                hashes = snapshot(args.inputs_dir, campaign / 'inputs')
                skill_hashes = snapshot(args.skill_dir, campaign / 'skill') if args.skill_dir else {}
                capsule_hashes = stage_capsule_src(session / 'capsule-src') if args.capsule_mcp else {}
                (campaign / 'broker').mkdir()
                dump(campaign / 'spec.json', plan['spec'], exclusive=True)
                dump(session / 'plan.json', plan, exclusive=True)
                dump(session / 'staging-receipt.json', dict(inputs_sha256=hashes, skill_sha256=skill_hashes, capsule_src_sha256=capsule_hashes, image=image,
                     task_sha256=hashlib.sha256(plan['spec']['task'].encode()).hexdigest()), exclusive=True)
                code = execute(plan, session, args.binary)
        record['status'] = ('executed' if code == 0 else 'failed') if args.execute else 'dry-run'
        return code
    except Exception as exc:
        record.update(status='failed', error=type(exc).__name__)
        print('FAILURE: ' + str(exc), file=sys.stderr)
        return 1
    finally:
        dump(record_path, record)


if __name__ == '__main__':
    raise SystemExit(main())
