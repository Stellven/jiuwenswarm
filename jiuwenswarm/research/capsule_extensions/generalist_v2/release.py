from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='research.generalist', version='m1-2', agent=True,
        summary='Low-trust fallback for a frozen task: permitted packet files, generated artifacts and bounded pure expressions; no ambient tools or host execution',
        extra_criteria=[('frozen_task_alignment', 'Does the output address its host-checked data.generalist_task objective and disclose gaps, uncertainty and low trust without claiming unobserved execution?')],
        shared_dependencies=[{'identifier': 'research.generalist.v1.worker', 'path': 'generalist/worker.py'},
            {'identifier': 'research.generalist.v1.checks', 'path': 'generalist/checks.py'},
            {'identifier': 'research.generalist.v1.expression', 'path': 'generalist/expression.py'}])
