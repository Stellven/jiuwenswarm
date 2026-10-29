"""Build the metadata-only controlled PRD installation alias (M1-I007).

No package code, console replacement, index upload or native metadata mutation.
Uses the installed/candidate native version and standard wheel RECORD hashes.
"""
import argparse
import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import re
import zipfile
from pathlib import Path


def build_compatibility_wheel(output, *, native_version, license_bytes):
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?', native_version):
        raise ValueError('UNSUPPORTED_NATIVE_VERSION')
    root = Path(output); root.mkdir(parents=True, exist_ok=True)
    prefix = 'jiuwenswarm-' + native_version + '.dist-info/'
    files = {
        prefix + 'METADATA': ('Metadata-Version: 2.1\nName: jiuwenswarm\nVersion: ' + native_version +
            '\nSummary: Controlled native WorkSwarm installation compatibility\nLicense: Apache-2.0\n'
            'Requires-Python: >=3.11,<3.14\nRequires-Dist: workswarm[codex,tui]==' + native_version + '\n\n').encode(),
        prefix + 'WHEEL': b'Wheel-Version: 1.0\nGenerator: ai4r-controlled-compat-1\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
        prefix + 'LICENSE': license_bytes,
    }
    records = io.StringIO(newline=''); writer = csv.writer(records, lineterminator='\n')
    for name, data in sorted(files.items()):
        writer.writerow([name, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(), len(data)])
    writer.writerow([prefix + 'RECORD', '', ''])
    files[prefix + 'RECORD'] = records.getvalue().encode()
    target = root / ('jiuwenswarm-' + native_version + '-py3-none-any.whl')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    return {'wheel': str(target), 'name': 'jiuwenswarm', 'version': native_version,
            'native_dependency': 'workswarm[codex,tui]==' + native_version,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'code_files': 0,
            'publication': 'NOT_REQUESTED'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--license', required=True)
    args = parser.parse_args()
    result = build_compatibility_wheel(args.output, native_version=importlib.metadata.version('workswarm'),
                                       license_bytes=Path(args.license).read_bytes())
    Path(args.output, 'compatibility-wheel.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
