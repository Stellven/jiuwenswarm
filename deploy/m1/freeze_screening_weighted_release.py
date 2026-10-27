"""Author/check only the additive Screening m1-6 (weighted) pins; no admission or activation.

Run with the repository on PYTHONPATH:
    python deploy/m1/freeze_screening_weighted_release.py
    python deploy/m1/freeze_screening_weighted_release.py --check
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import tempfile

from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'jiuwenswarm/research/resources/capsules/screening_m1_6_catalog.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify without rewriting pins')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(directory)) as store:
        base = build_research_assets(store)['screening']
        from jiuwenswarm.research.capsules.assets import build_weighted_screening_asset
        result = json.loads(json_bytes(build_weighted_screening_asset(store, base=base, verify_catalog=False)))
    if args.check:
        if result != json.loads(CATALOG.read_text('utf-8')):
            raise SystemExit('Screening m1-6 differs from frozen release pins')
    else:
        CATALOG.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print('Screening m1-6 pins verified' if args.check else 'Authored Screening m1-6 pins; no admission or activation')


if __name__ == '__main__':
    main()
