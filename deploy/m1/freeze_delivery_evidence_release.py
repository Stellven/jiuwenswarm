"""Author/check only the additive Delivery m1-6 (evidence bundle) pins; no admission or activation.

Run with the repository on PYTHONPATH:
    python deploy/m1/freeze_delivery_evidence_release.py
    python deploy/m1/freeze_delivery_evidence_release.py --check
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import tempfile

from jiuwenswarm.research.capsules.assets import build_delivery_evidence_asset, build_research_assets
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'jiuwenswarm/research/resources/capsules/delivery_m1_6_catalog.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify without rewriting pins')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(directory)) as store:
        base = build_research_assets(store)['delivery']
        result = json.loads(json_bytes(build_delivery_evidence_asset(store, base=base, verify_catalog=False)))
    if args.check:
        if result != json.loads(CATALOG.read_text('utf-8')):
            raise SystemExit('Delivery m1-6 differs from frozen release pins')
    else:
        CATALOG.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print('Delivery m1-6 pins verified' if args.check else 'Authored Delivery m1-6 pins; no admission or activation')


if __name__ == '__main__':
    main()
