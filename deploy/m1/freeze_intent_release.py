"""Author/check only additive Intent m1-7 pins; no admission or activation.

Run with the repository on PYTHONPATH:
    python deploy/m1/freeze_intent_release.py
    python deploy/m1/freeze_intent_release.py --check
Select with capture_local_profile(..., intent_version='m1-7') in a fresh profile.
"""
import argparse
import asyncio
from contextlib import closing
import json
from pathlib import Path
import tempfile

from jiuwenswarm.research.intent_release import prepare_intent_release
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'jiuwenswarm/research_assets/compiler/intent_m1_7_catalog.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify without rewriting pins')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(directory)) as store:
        result = json.loads(json_bytes(asyncio.run(prepare_intent_release(store, verify_catalog=False))))
    if args.check:
        if result != json.loads(CATALOG.read_text('utf-8')):
            raise SystemExit('Intent m1-7 differs from frozen release pins')
    else:
        CATALOG.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print('Intent m1-7 pins verified' if args.check else 'Authored Intent m1-7 pins; no admission or activation')


if __name__ == '__main__':
    main()
