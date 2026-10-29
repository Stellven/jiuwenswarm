from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.calculate', version='m1-4',
        input_type='table_packet',
        summary='Explicit count/sum/mean/min/max on selected table columns with bounded decimal128 half-even arithmetic and a clear packet-shape error; accepts only a table_packet from table normalization, never an unparsed file; no arbitrary formulas or missing-value inference',
        shared_dependencies=[{'identifier': 'research.utility.calculate.v3.worker', 'path': 'calculate_v3/worker.py'},
            {'identifier': 'research.utility.calculate.v3.checks', 'path': 'calculate_v3/checks.py'}])
