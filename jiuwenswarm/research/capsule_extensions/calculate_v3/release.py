from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.calculate', version='m1-3',
        summary='Explicit count/sum/mean/min/max on selected table columns with bounded decimal128 half-even arithmetic, inputs up to 128 digits and a clear packet-shape error; no arbitrary formulas or missing-value inference')
