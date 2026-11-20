#!/usr/bin/env python3
"""Run the frozen fair Strata configuration with the same cold and steady-state request sequence."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

from steady_requests import run

ROOT = Path.home() / 'predemo-spark'
HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scope', type=Path)
    args = parser.parse_args()
    scope = args.scope.resolve()
    if scope.parent != ROOT / 'OPS/runs' or scope.exists():
        parser.error('Use a fresh OPS/runs scope')
    config = json.loads((ROOT / 'OPS/configs/p4-s-pass-1.json').read_bytes())
    config['log'] = str(scope / 'engine.log')
    config['env']['STRATA_DS4_SLOT_DIR'] = str(scope / 'ds4-slots')
    assert int(config['env']['DS4_UMA_HEADROOM_GIB']) >= 16 and '--profile-readonly' in config['args']
    config_path = ROOT / 'OPS/configs' / (scope.name + '.json')
    with config_path.open('x') as stream:
        json.dump(config, stream, indent=2)
    preflights = ROOT / 'OPS/p3/early-preflights'
    subprocess.run([sys.executable, str(HERE / 'source_residency.py'), 'cold-start',
                    '--regions', str(ROOT / 'OPS/p4/source-regions.json'),
                    '--out', str(preflights / (scope.name + '-source.json'))], check=True)
    while True:
        q = subprocess.run([str(ROOT / 'bin/quiet')], capture_output=True)
        if q.returncode == 0 and json.loads(q.stdout)['mem_available_gib'] >= 110:
            (preflights / (scope.name + '-quiet.json')).write_bytes(q.stdout)
            break
        time.sleep(5)
    start = json.loads((ROOT / 'OPS/runs/s-first-load/start.json').read_bytes())
    command = list(start['command'])
    command[command.index('--config') + 1] = str(config_path)
    arm = 'S-fair-steady'
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
        hashes = run(scope, arm, port, 'strata')
    finally:
        if (scope / 'scope.json').exists() and server.poll() is None:
            # Signal the Python service only so it can send QUIT to the engine it owns.
            pid = json.loads((scope / 'scope.json').read_bytes())['pid']
            os.kill(pid,signal.SIGTERM)
        server.wait()
    result = json.loads((scope/'result.json').read_bytes())
    if result['reason'] or result['returncode']:
        raise RuntimeError('Strata scope did not exit normally')
    (scope/'probe.json').write_text(json.dumps({'arm':arm,'window':'steady','greedy_hashes':hashes})+'\n')

if __name__ == '__main__':
    main()
