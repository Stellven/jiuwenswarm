"""Clean-fixture CC run driver: install-tool, prepare, run-cc, collect. Nothing external runs without --execute.

Plan output uses symbolic IDs so it is stable to review; every executed action gets fresh
attempt IDs. A preparation names an immutable session, not a repeatable dispatch: after
prepare, run-cc and collect may each be executed once per preparation.

Roots come from arguments and environment, never from hard-coded paths:
  AI4R_REPO   repository root (default: the checkout that holds this script)
  --out       working directory for attempts/, sessions/ and the ledger
  --fixture   fixture directory that holds cases.json and inputs/

Typical order (see scripts/live/README.md):
  value_schedule init --ledger OUT/ledgers/LEDGER.sqlite3     (once per ledger)
  run_trap.py install-tool ...        copies value_product.py into the results volume
  run_trap.py prepare ...             intake only, no model call
  run_trap.py run-cc --prepared ID    the live run
  run_trap.py collect --prepared ID   copies the campaign records out of the results volume
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

REPO = Path(os.environ.get('AI4R_REPO') or Path(__file__).resolve().parents[2]).resolve()
HERE = Path(__file__).resolve().parent
RUNNER_IMAGE = 'benchmark-runner:local'
RESULTS_VOLUME = 'ai4r-local_results'
CREDENTIAL_VOLUME = 'ai4r-local_runner_credentials'
NETWORK = 'ai4r-local_private'
CALL_CEILING = 80


def dump(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)


def bounded(out, path):
    path, out = Path(path).resolve(), Path(out).resolve()
    if not path.is_relative_to(out) or path == out:
        raise ValueError('writes must stay below --out')
    return path


def identifier(value):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}', value):
        raise ValueError('unsafe identifier')
    return value


def fresh_id():
    return 'trap-' + uuid.uuid4().hex


def local_call(function, *args):
    """Run one helper of this file in a child Python so the command is journalled as argv."""
    code = ('import sys;sys.path.insert(0,' + repr(str(HERE)) + ');'
            'import run_trap;run_trap.' + function + '(*' + repr(list(args)) + ')')
    return [sys.executable, '-B', '-c', code]


def stage(out, source, session):
    """Copy only declared public inputs, never an entire fixture directory."""
    source, session = Path(source), bounded(out, session)
    cases = json.loads((source / 'cases.json').read_text('utf-8-sig'))['cases']
    if len(cases) != 1 or cases[0].get('repeats', 1) != 1:
        raise ValueError('one fixture, one repeat required')
    case = cases[0]
    if any(case.get(k) for k in ('setup', 'steps', 'collection')):
        raise ValueError('public-only preparation required')
    session.mkdir(parents=True, exist_ok=False)
    fixture = session / 'fixture'
    (fixture / 'inputs').mkdir(parents=True)
    shutil.copyfile(source / 'cases.json', fixture / 'cases.json')
    hashes = {}
    for row in case['inputs']:
        rel = Path(row['path'])
        src = source / 'inputs' / rel
        if rel.is_absolute() or '..' in rel.parts or src.is_symlink():
            raise ValueError('unsafe public input')
        if not src.resolve().is_relative_to((source / 'inputs').resolve()):
            raise ValueError('public input escaped root')
        dest = fixture / 'inputs' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        hashes[row['path']] = hashlib.sha256(dest.read_bytes()).hexdigest()
    dump(session / 'staging-receipt.json', {'public_sha256': hashes,
         'case_file_sha256': hashlib.sha256((fixture / 'cases.json').read_bytes()).hexdigest(),
         'task_sha256': hashlib.sha256(case['task'].encode()).hexdigest(),
         'variant': 'cc', 'private_material_copied': False})


def reserve(ledger, session, pair, model='gpt-6.1-sol'):
    """Reserve the CC arm in a fresh ledger before any intake call can lead to inference."""
    sys.path.insert(0, str(REPO))
    from benchmarks.harbor_suite.value_schedule import Schedule
    receipt = json.loads((Path(session) / 'staging-receipt.json').read_text())
    schedule = Schedule(ledger)
    try:
        schedule.reserve(pair, receipt['task_sha256'], {'cc': CALL_CEILING}, requested_model=model)
    finally:
        schedule.close()


def claim_cc(ledger, session, pair, model='gpt-6.1-sol'):
    sys.path.insert(0, str(REPO))
    from benchmarks.harbor_suite.value_schedule import Schedule
    receipt = json.loads((Path(session) / 'prepare.stdout').read_text('utf-8-sig'))
    requests = receipt['requests']
    if len(requests) != 1 or receipt['submitted'] or receipt['model_calls'] != 0:
        raise ValueError('invalid original preparation receipt')
    schedule = Schedule(ledger)
    try:
        remaining = schedule.claim_envelope(pair, 'cc', requests[0]['request_id'], CALL_CEILING,
                                            model=model, effort='medium')
        if remaining < 720:
            raise ValueError('insufficient remaining wall budget; envelope retained')
    finally:
        schedule.close()


def runner_base(fixture, build, name):
    return ['docker', 'run', '--rm', '--name', name, '--network', NETWORK,
            '--read-only', '--user', '11001:11001', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true', '--tmpfs',
            '/tmp:rw,nosuid,nodev,size=128m,uid=11001,gid=11001',
            '--mount', f'type=volume,source={RESULTS_VOLUME},target=/results',
            '--mount', f'type=volume,source={CREDENTIAL_VOLUME},target=/run/benchmark-runner,readonly',
            '--mount', f'type=bind,source={fixture},target=/cases,readonly',
            '--mount', f'type=bind,source={fixture / "inputs"},target=/inputs,readonly',
            '-e', 'AI4R_ENDPOINT=http://ai4r:5173', '-e', 'AI4R_HTTP_AUTHORITY=127.0.0.1:5175',
            '-e', 'AI4R_TOKEN_FILE=/run/benchmark-runner/token', '-e', 'AI4R_EXPECTED_BUILD=' + build]


def command_plan(args, campaign):
    """Pure deterministic argv builder; no reads, writes, subprocesses or UUIDs."""
    out = args.out.resolve()
    session = out / 'sessions' / campaign
    fixture = session / 'fixture'
    ccdir = '/results/value-poc-campaigns/' + campaign
    base = runner_base(fixture, args.expected_build, campaign + '-cc')
    prepare = base + ['--entrypoint', 'python', RUNNER_IMAGE, '/results/value_product.py',
                      '--cases', '/cases/cases.json', '--inputs', '/inputs', '--output',
                      '/results/value-poc-campaigns', '--campaign-id', campaign]
    cc = base + ['--entrypoint', 'benchmark-runner', RUNNER_IMAGE, 'resume', '--campaign-dir', ccdir, '--json']
    collect_code = 'import shutil;shutil.copytree(' + repr(ccdir) + ",'/export/cc',symlinks=False)"
    collect = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--user', '11001:11001',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--mount',
               f'type=volume,source={RESULTS_VOLUME},target=/results,readonly', '--mount',
               f'type=bind,source={session / "collection"},target=/export', '--entrypoint',
               'python', RUNNER_IMAGE, '-B', '-c', collect_code]
    tool = REPO / 'benchmarks/harbor_suite/value_product.py'
    install = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--user', '11001:11001',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
               '--mount', f'type=volume,source={RESULTS_VOLUME},target=/results',
               '--mount', f'type=bind,source={tool},target=/tool/value_product.py,readonly',
               '--entrypoint', 'python', RUNNER_IMAGE, '-B', '-c',
               "import shutil;shutil.copyfile('/tool/value_product.py','/results/value_product.py')"]
    return {'install-tool': [(install, out / ('install-tool-' + campaign))],
            'prepare': [(local_call('stage', str(out), str(args.fixture), str(session)), session / 'stage'),
                        (prepare, session / 'prepare'),
                        (local_call('reserve', str(args.ledger), str(session), campaign, args.model), session / 'reserve')],
            'run-cc': [(local_call('claim_cc', str(args.ledger), str(session), campaign, args.model), session / 'claim'),
                       (cc, session / 'resume')],
            'collect': [(collect, session / 'collect')]}


def run_commands(action, commands, session):
    # Every invocation is journalled before reaching here. No shell interpolation.
    if action == 'collect':
        (session / 'collection').mkdir(exist_ok=False)
    handles = []
    try:
        for index, (argv, prefix) in enumerate(commands):
            # The staging command creates the session; its logs live beside it.
            if action == 'prepare' and index == 0:
                prefix = session.parent / (session.name + '-stage')
            out = Path(str(prefix) + '.stdout').open('xb')
            err = Path(str(prefix) + '.stderr').open('xb')
            handles.extend([out, err])
            subprocess.run(argv, cwd=REPO, stdout=out, stderr=err, check=True,
                           timeout=840 if action == 'run-cc' else 300)
    finally:
        for handle in handles:
            handle.close()


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='action', required=True)
    for name in ('plan', 'install-tool', 'prepare', 'run-cc', 'collect'):
        q = sub.add_parser(name)
        q.add_argument('--out', type=Path, required=True, help='working directory for attempts/, sessions/ and the ledger')
        q.add_argument('--fixture', type=Path, required=True, help='fixture directory with cases.json and inputs/')
        q.add_argument('--ledger', type=Path, required=True, help='fresh ledger below --out (value_schedule init)')
        q.add_argument('--expected-build', required=True, help='build_id from the deploy build receipt')
        q.add_argument('--prepared', help='prepare attempt ID; required for run-cc and collect')
        q.add_argument('--attempt-id', help='optional exclusive ID (normally generated)')
        q.add_argument('--execute', action='store_true')
        q.add_argument('--model', choices=('gpt-6.1-sol', 'gpt-6-luna'), default='gpt-6.1-sol')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    out = args.out.resolve()
    attempt = identifier(args.attempt_id or fresh_id())
    attempts = out / 'attempts'
    attempts.mkdir(parents=True, exist_ok=True)
    record_path = attempts / (attempt + '.json')
    # Exclusive creation also prevents concurrent reuse, including failed attempts.
    with record_path.open('x', encoding='utf-8') as stream:
        record = dict(attempt_id=attempt, request_id='request-' + uuid.uuid4().hex,
                      campaign_id=attempt, action=args.action, execute=args.execute, model=args.model,
                      status='planning', fixture=str(args.fixture.resolve()), ledger=str(args.ledger.resolve()))
        json.dump(record, stream)
    try:
        bounded(out, args.ledger)
        if args.action in ('run-cc', 'collect'):
            if not args.prepared:
                raise ValueError('--prepared is required')
            campaign = identifier(args.prepared)
            prior = json.loads((attempts / (campaign + '.json')).read_text())
            if prior['action'] != 'prepare' or prior['fixture'] != record['fixture'] or prior['ledger'] != record['ledger']:
                raise ValueError('prepared session does not match fixture/ledger')
            if prior.get('model', 'gpt-6.1-sol') != args.model:
                raise ValueError('prepared session model does not match --model')
            if args.execute and prior['status'] != 'executed':
                raise ValueError('cannot execute a dry-run preparation')
            if args.execute:
                for other in attempts.glob('*.json'):
                    if other == record_path:
                        continue
                    old = json.loads(other.read_text())
                    if old.get('prepared') == campaign and old['action'] == args.action and old['execute']:
                        raise ValueError('dispatch/collection already attempted; no silent replay')
        else:
            campaign = attempt
        record['prepared'] = campaign
        # Stable plan templates are distinct from fresh journal identities.
        plans = command_plan(args, 'TRAP_CAMPAIGN' if args.action == 'plan' else campaign)
        chosen = plans if args.action == 'plan' else {args.action: plans[args.action]}
        record['commands'] = {k: [v[0] for v in rows] for k, rows in chosen.items()}
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding='utf-8')
        for action, rows in chosen.items():
            print('# ' + action)
            for command, _ in rows:
                print(subprocess.list2cmdline(command))
        if args.execute and args.action != 'plan':
            (out / 'sessions').mkdir(exist_ok=True)
            run_commands(args.action, plans[args.action], out / 'sessions' / campaign)
        record['status'] = 'executed' if args.execute and args.action != 'plan' else 'dry-run'
        return 0
    except Exception as exc:
        record['status'] = 'failed'
        record['error'] = type(exc).__name__  # no external response or secret echo
        raise
    finally:
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
