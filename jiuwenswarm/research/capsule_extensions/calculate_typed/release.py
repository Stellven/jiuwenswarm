from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.calculate_typed', version='m1-1',
        summary='calculate with independent exact JSON type preservation in addition to original value checks',
        shared_dependencies=[{'identifier': 'research.utility.calculate.worker', 'path': 'calculate/worker.py'},
            {'identifier': 'research.utility.calculate.checks', 'path': 'calculate/checks.py'},
            {'identifier': 'research.utility.typed_values', 'path': 'typed_values.py'}])

