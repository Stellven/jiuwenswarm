from pathlib import Path

from ..assets import prepare as prepare_asset
from .worker import execute as execute
from .checks import check as check


def prepare(store):
    value = prepare_asset(store, Path(__file__).parent, name='research.generalist', agent=True,
        summary='Low-trust fallback for a frozen task: permitted packet files, generated artifacts and bounded pure expressions; no ambient tools or host execution',
        extra_criteria=[('frozen_task_alignment', 'Does the output address its host-checked data.generalist_task objective and disclose gaps, uncertainty and low trust without claiming unobserved execution?')])
    return value
