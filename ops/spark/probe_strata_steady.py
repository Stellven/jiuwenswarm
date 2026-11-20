#!/usr/bin/env python3
"""Run the frozen fair Strata configuration with the same cold and steady-state request sequence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

from p4_launch import (add_window_arguments, condition_source_and_check_quiet, request_window,
                       validate_window_arguments, verify_prior_profile)
from steady_requests import run

ROOT = Path.home() / 'predemo-spark'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scope', type=Path)
    add_window_arguments(parser)
    args = parser.parse_args()
    p4 = any((args.arm, args.launch_pass, args.first_window))
    validate_window_arguments(parser, args, p4, 'strata')
    scope = args.scope.resolve()
    if scope.parent != ROOT / 'OPS/runs' or scope.exists():
        parser.error('Use a fresh OPS/runs scope')
    config_bytes = (ROOT / 'OPS/configs/p4-s-pass-1.json').read_bytes()
    config = json.loads(config_bytes)
    start = json.loads((ROOT / 'OPS/runs/s-first-load/start.json').read_bytes())
    if p4:
        with Path(config['exe']).open('rb') as engine:
            engine_sha = hashlib.file_digest(engine, 'sha256').hexdigest()
        if engine_sha != start['binary_sha256']:
            raise RuntimeError('Fair Strata engine digest differs from the measured reference')
        launch_profile = dict(engine_binary=config['exe'], binary_sha256=engine_sha, command=start['command'],
                              fair_config_sha256=hashlib.sha256(config_bytes).hexdigest())
        verify_prior_profile(args, launch_profile)
    config['log'] = str(scope / 'engine.log')
    config['env']['STRATA_DS4_SLOT_DIR'] = str(scope / 'ds4-slots')
    assert int(config['env']['DS4_UMA_HEADROOM_GIB']) >= 16 and '--profile-readonly' in config['args']
    config_path = ROOT / 'OPS/configs' / (scope.name + '.json')
    with config_path.open('x') as stream:
        json.dump(config, stream, indent=2)
    quiet_preflight = condition_source_and_check_quiet(scope)
    command = list(start['command'])
    command[command.index('--config') + 1] = str(config_path)
    arm = args.arm if p4 else 'S-fair-steady'
    port = config['port']
    now = time.monotonic()
    server = subprocess.Popen([str(ROOT / 'bin/capped'), '--arm', arm, '--engine-binary', config['exe'],
                               '--result-dir', str(scope), '--', *command], env=os.environ | config['env'])
    try:
        while time.monotonic() - now < 1200:
            if server.poll() is not None:
                raise RuntimeError('Strata stopped during load')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as response:
                    health = json.load(response)
                if health.get('loaded') and health.get('service') == 'strata':
                    break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        else:
            raise TimeoutError('Strata readiness deadline exceeded')
        (scope / 'load-ready.json').write_text(json.dumps({'ready_at':datetime.now(timezone.utc).isoformat(),
                    'health_elapsed_s':time.monotonic()-now, 'config':str(config_path)})+'\n')
        if p4:
            (scope / 'p4-launch-profile.json').write_text(json.dumps(launch_profile, indent=2) + '\n')
        hashes = (request_window(args, scope, port, 'strata', quiet_preflight) if p4 else
                  run(scope, arm, port, 'strata'))
    finally:
        if server.poll() is None:
            if (scope / 'scope.json').exists():
                # Signal the Python service only so it can send QUIT to the engine it owns.
                pid = json.loads((scope / 'scope.json').read_bytes())['pid']
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                server.terminate()
        try:
            server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            server.terminate()
            server.wait()
    result = json.loads((scope/'result.json').read_bytes())
    if result['reason'] or result['returncode'] or not result['scope_verified']:
        raise RuntimeError('Strata scope did not exit normally')
    (scope/'probe.json').write_text(json.dumps({'arm':arm,'window':'p4' if p4 else 'steady','greedy_hashes':hashes})+'\n')

if __name__ == '__main__':
    main()
