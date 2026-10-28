"""Freeze this bench's own inputs (the two tool workers it adapts, the case bank, its code and fixtures) before
measurement; no extraction. Usage: python freeze.py --out DIR  (writes DIR/frozen-manifest.json).
Paths in the manifest are relative to AI4R_CODE_ROOT so the manifest does not depend on where the repo is."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roots  # noqa: E402
from core import TOOLS, declaration, digest, fixtures  # noqa: E402

ROOT = Path(__file__).resolve().parent
REPO = roots.code_root()
ZIP = REPO / 'benchmarks/harbor_suite/assets/AI4Research-Benchmark-Cases-2026-10-26.zip'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args(argv).out
    out.mkdir(parents=True, exist_ok=True)
    sources = {}
    paths = [REPO / 'jiuwenswarm/research/capsule_extensions/calculate/worker.py',
             REPO / 'jiuwenswarm/research/capsule_extensions/calculate_v2/worker.py']
    for path in paths:
        sources[path.relative_to(REPO).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    bank = {}
    with zipfile.ZipFile(ZIP) as archive:
        for name in archive.namelist():
            if '/cases/rsi01-improvement/' in name or '/cases/rsi02-containment/' in name:
                if not name.endswith('/'):
                    data = archive.read(name)
                    bank[name] = hashlib.sha256(data).hexdigest()
    payload = {'sources': sources, 'zip': ZIP.relative_to(REPO).as_posix(),
               'zip_sha256': hashlib.sha256(ZIP.read_bytes()).hexdigest(), 'case_bank_files': bank,
               'local_code': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in ROOT.glob('*.py')},
               'preregistered_seeds': [0, 199],
               'fixtures': {t: {'declaration': declaration(t), 'visible': fixtures(t, 0)[0],
                                 'hidden_sha256': [digest(fixtures(t, s)[1]) for s in range(200)]}
                            for t in TOOLS}}
    (out / 'frozen-manifest.json').write_bytes(json.dumps(payload, indent=2).encode('utf-8'))
    print(f'Frozen {len(bank)} case-bank files, {len(paths)} tool sources, and 400 held-out sets.')


if __name__ == '__main__':
    main()
