from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.table_normalize_typed', version='m1-1',
        summary='table normalize with independent exact JSON type preservation in addition to original value checks',
        shared_dependencies=[{'identifier': 'research.utility.table_normalize.worker', 'path': 'table_normalize/worker.py'},
            {'identifier': 'research.utility.table_normalize.checks', 'path': 'table_normalize/checks.py'},
            {'identifier': 'research.utility.typed_values', 'path': 'typed_values.py'}])

