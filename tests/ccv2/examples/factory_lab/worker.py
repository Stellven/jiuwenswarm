"""Native Strata product inspection only; fixture bytes are never executed."""
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

PIN = 'c62d5e3a15b40ea51c96aae9e8d36928965f53ab'


def run(packet):
    source = Path(packet['inputs']['data']['strata_source'])
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('Strata source commit does not match the tested exact pin')
    sys.path.insert(0, str(source))
    from strata_control import engine_component
    product_path = Path(packet['inputs']['product']['path'])
    with tempfile.TemporaryDirectory(prefix='cc-strata-inspect-') as temp:
        root = Path(temp)
        with zipfile.ZipFile(product_path) as archive:
            for member in archive.infolist():
                path = Path(member.filename)
                if path.is_absolute() or '..' in path.parts or ':' in member.filename or '\\' in member.filename:
                    raise ValueError('Unsafe product archive path')
            archive.extractall(root)
        if list(root.rglob('cc.yaml')):
            raise ValueError('Fixture must be a native product without a reusable CC declaration')
        native = engine_component.read_manifest(root)
        engine_component.verify(native, full=True)
        return {'outcome': 'ok', 'outputs': {'inspection': {
            'fixture_only': True, 'entrypoint_executed': False, 'inference_measured': False,
            'product_sha256': hashlib.sha256(product_path.read_bytes()).hexdigest(),
            'manifest_sha256': hashlib.sha256((root / engine_component.MANIFEST).read_bytes()).hexdigest(),
            'component': native.to_dict(),
            'payloads': [{'path': name, 'sha256': sha, 'bytes': size} for name, sha, size in native.files],
            'strata_commit': head, 'loader_sha256': hashlib.sha256(Path(inspect.getfile(engine_component)).read_bytes()).hexdigest(),
            'loader_calls': ['read_manifest', 'verify(full=True)'], 'reusable_cc_count_in_product': 0}}}


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin))))
    except Exception as error:
        print(json.dumps({'outcome': 'error', 'outputs': {}, 'error': {'code': 'PRODUCT_INVALID', 'message': str(error)}}))
        sys.exit(1)
