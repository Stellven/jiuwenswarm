from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.table_normalize', version='m1-2',
        summary='Parse an explicitly selected UTF-8 JSON/CSV file into ordered scalar rows without inference or value conversion',
        shared_dependencies=[{'identifier': 'research.utility.table_normalize.v1.worker', 'path': 'table_normalize/worker.py'},
            {'identifier': 'research.utility.table_normalize.v1.checks', 'path': 'table_normalize/checks.py'}])
