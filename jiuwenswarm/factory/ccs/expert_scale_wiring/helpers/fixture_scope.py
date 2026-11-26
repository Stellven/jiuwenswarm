"""Confirm the demo verifier inherited the capped runner's own no-swap scope."""
import os
from pathlib import Path
import re

DEMO_TASK = 'muse-2bit-demo-r8'
SCOPE_ENV = 'FACTORY_WIRING_FIXTURE_SCOPE'


def require_scope():
    prefix = os.environ.get(SCOPE_ENV, '')
    if not re.fullmatch(r'factory-wire-fixture-[a-z0-9]{8}-', prefix):
        raise ValueError('The demo scale-wiring verifier requires its owned capped runner scope')
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::'):
            group = Path(line[3:].lstrip('/'))
            if group.name.startswith(prefix) and group.name.endswith('.scope'):
                directory = Path('/sys/fs/cgroup') / group
                if ((directory / 'memory.max').read_text().strip() == str(96 << 30)
                        and (directory / 'memory.swap.max').read_text().strip() == '0'):
                    return
    raise ValueError('The owned scale-wiring scope does not enforce 96 GiB and zero swap')


def inherited_cap(command, _):
    """Keep each CPU model subprocess in the same gated scope."""
    require_scope()
    return list(command), 'capped runner scope, MemoryMax=96G, MemorySwapMax=0'
