from pathlib import Path
from ..assets import prepare as prepare_asset
from .worker import execute as execute
from .checks import check as check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.table_normalize',
        summary='Parse an explicitly selected UTF-8 JSON/CSV file into ordered scalar rows without inference or value conversion')
