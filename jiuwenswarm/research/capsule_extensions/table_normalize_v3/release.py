from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.table_normalize', version='m1-3',
        output_type='table_packet',
        summary='Parse an explicitly selected UTF-8 JSON/CSV file into ordered scalar rows without inference or value conversion; the result is typed table_packet so only a parsed table can reach a table consumer',
        shared_dependencies=[{'identifier': 'research.utility.table_normalize.v1.worker', 'path': 'table_normalize/worker.py'},
            {'identifier': 'research.utility.table_normalize.v1.checks', 'path': 'table_normalize/checks.py'},
            {'identifier': 'research.utility.table_normalize.v2.checks', 'path': 'table_normalize_v2/checks.py'}])
