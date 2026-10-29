from pathlib import Path

from ..assets_v2 import prepare as prepare_asset
from .worker import execute
from .checks import check


def prepare(store):
    return prepare_asset(store, Path(__file__).parent, name='utility.markdown_report', version='m1-2',
        summary='Render explicit supplied sections and selected JSON data into an escaped Markdown artifact and digest manifest without adding research claims',
        shared_dependencies=[{'identifier': 'research.utility.markdown_report.v1.worker', 'path': 'markdown_report/worker.py'},
            {'identifier': 'research.utility.markdown_report.v1.checks', 'path': 'markdown_report/checks.py'}])
