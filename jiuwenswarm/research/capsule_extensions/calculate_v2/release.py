from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.calculate', version='m1-2',
        summary='Explicit count/sum/mean/min/max on selected table columns with bounded decimal128 half-even arithmetic; no arbitrary formulas or missing-value inference',
        shared_dependencies=[{'identifier': 'research.utility.calculate.v1.worker', 'path': 'calculate/worker.py'},
            {'identifier': 'research.utility.calculate.v1.checks', 'path': 'calculate/checks.py'}])
