from pathlib import Path
from ..assets import prepare as prepare_asset
from .worker import execute as execute
from .checks import check as check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.calculate',
        summary='Explicit count/sum/mean/min/max on selected table columns with bounded decimal128 half-even arithmetic; no arbitrary formulas or missing-value inference')
