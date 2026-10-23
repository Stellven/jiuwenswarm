"""Run the CLI inside the single configured benchmark-runner container."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

from build_two_images import docker_prefix


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments == ['--help']:
        print('Usage: python deploy/m1/runner.py doctor|run [--cases /cases/smoke.json] [--campaign-id ID] [--json]')
        print('       python deploy/m1/runner.py status|resume|cancel|export|cleanup --campaign-dir /results/ID [--json]')
        print('Uses the active 5175 installation; all runner commands execute inside benchmark-runner.')
        return 0
    active = Path(os.environ.get('AI4R_ACTIVE_PROFILE', str(Path(os.environ.get('LOCALAPPDATA', '')) / 'AI4Research/runtime/poc-clean-active.json')))
    profile = json.loads(active.read_bytes())
    if profile.get('migration') != 'existing-project-two-images':
        raise ValueError('THE_ACTIVE_INSTALLATION_HAS_NO_CONFIGURED_RUNNER')
    if arguments[0] in {'doctor', 'run'}:
        for name, value in [('--cases', '/cases/smoke.json'), ('--inputs', '/inputs'), ('--output', '/results')]:
            if name not in arguments:
                arguments += [name, value]
    command = docker_prefix() + ['compose', '-p', profile['project'], '-f', profile['compose'],
        'exec', '-T', '--user', '11001:11001', 'benchmark-runner', 'benchmark-runner', *arguments]
    return subprocess.run(command).returncode


if __name__ == '__main__':
    raise SystemExit(main())
