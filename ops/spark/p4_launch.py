"""Prepare a named P4 launch and submit its requests through the window protocol."""
from argparse import Namespace
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from run_p4_window import run_window


ROOT = Path.home() / 'predemo-spark'
HERE = Path(__file__).resolve().parent
REGIONS = ROOT / 'OPS/p4/source-regions.json'


def add_window_arguments(parser):
    parser.add_argument('--arm', help='Stable P4 arm label shared by the two launches')
    parser.add_argument('--launch-pass', type=int, choices=(1, 2))
    parser.add_argument('--first-window', type=Path, help='Completed pass-1 p4-window/window.json for this arm')
    parser.add_argument('--describe-profile', action='store_true', help='Write the exact frozen P4 profile to stdout and exit')


def validate_window_arguments(parser, args, enabled, view):
    if not enabled:
        if any((args.arm, args.launch_pass, args.first_window, args.describe_profile)):
            parser.error('Arm, pass and first-window receipt are P4 launch options')
        return
    if not args.arm or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*', args.arm) or not args.launch_pass:
        parser.error('P4 requires a stable --arm label and --launch-pass')
    if args.describe_profile:
        return
    if (args.launch_pass == 2) != bool(args.first_window):
        parser.error('Supply --first-window exactly when launching pass 2')
    if args.first_window:
        args.first_window = args.first_window.resolve(strict=True)
        previous = json.loads(args.first_window.read_bytes())
        scope = Path(previous['scope'])
        if (scope.parent != ROOT / 'OPS/runs' or args.first_window != scope / 'p4-window/window.json' or
                previous['status'] != 'complete' or previous['launch_pass'] != 1 or
                previous['arm'] != args.arm or previous['view'] != view):
            parser.error('First-window receipt does not describe a completed pass 1 of this arm')
        cap = json.loads((scope / 'result.json').read_bytes())
        if (cap['returncode'] or cap['reason'] or not cap['scope_verified'] or
                any(int(cap['memory_events'].get(key, 0)) for key in ('oom', 'oom_kill', 'oom_group_kill'))):
            parser.error('First-window cap receipt requires review')


def condition_source_and_check_quiet(scope):
    preflights = ROOT / 'OPS/p3/early-preflights'
    preflights.mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(HERE / 'source_residency.py'), 'cold-start',
                    '--regions', str(REGIONS), '--out', str(preflights / f'{scope.name}-source.json')], check=True)
    quiet_path = preflights / f'{scope.name}-quiet.json'
    # File-specific eviction can briefly elevate load. Validate quiet after conditioning.
    while True:
        quiet = subprocess.run([str(ROOT / 'bin/quiet')], capture_output=True, check=False)
        if quiet.returncode == 0 and json.loads(quiet.stdout)['mem_available_gib'] >= 110:
            quiet_path.write_bytes(quiet.stdout)
            return quiet_path
        time.sleep(5)


def verify_prior_profile(args, profile):
    if args.first_window:
        prior_profile = args.first_window.parents[1] / 'p4-launch-profile.json'
        if json.loads(prior_profile.read_bytes()) != profile:
            raise ValueError('Pass 2 must use the same engine build and runtime profile as pass 1')


def profile_bytes(profile):
    return (json.dumps(profile, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def request_window(args, scope, port, view, quiet_preflight):
    receipt = run_window(Namespace(scope=scope, arm=args.arm, port=port, view=view, regions=REGIONS,
                                   launch_pass=args.launch_pass, first_window=args.first_window,
                                   quiet_preflight=quiet_preflight, pages_per_sample=4096, seed=20261120))
    return json.loads(receipt.read_bytes())['greedy_hashes']
