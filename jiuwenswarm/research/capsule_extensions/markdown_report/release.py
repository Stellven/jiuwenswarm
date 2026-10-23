from pathlib import Path
from ..assets import prepare as prepare_asset
from .worker import execute as execute
from .checks import check as check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.markdown_report',
        summary='Render explicit supplied sections and selected JSON data into an escaped Markdown artifact and digest manifest without adding research claims')
