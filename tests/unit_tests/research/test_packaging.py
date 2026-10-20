"""The PRD install name resolves to the unchanged native distribution."""
import base64
import csv
import hashlib
import importlib.util
import io
import zipfile
from pathlib import Path


def test_controlled_compatibility_wheel_has_only_valid_metadata_and_exact_native_dependency(tmp_path):
    path = Path('/workspace/scripts/research_compat_wheel.py')
    if not path.exists(): path = Path(__file__).resolve().parents[3] / 'scripts/research_compat_wheel.py'
    spec = importlib.util.spec_from_file_location('compat_builder', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result = module.build_compatibility_wheel(tmp_path, native_version='0.2.5b1', license_bytes=b'Apache-2.0 test fixture')
    with zipfile.ZipFile(result['wheel']) as wheel:
        names = wheel.namelist()
        assert all(name.startswith('jiuwenswarm-0.2.5b1.dist-info/') for name in names)
        metadata = wheel.read('jiuwenswarm-0.2.5b1.dist-info/METADATA').decode()
        assert 'Requires-Dist: workswarm[codex,tui]==0.2.5b1\n' in metadata
        assert 'Name: jiuwenswarm\n' in metadata
        for name, digest, size in csv.reader(io.StringIO(wheel.read('jiuwenswarm-0.2.5b1.dist-info/RECORD').decode())):
            if name.endswith('/RECORD'): continue
            data = wheel.read(name)
            assert digest == 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            assert len(data) == int(size)
    assert result['sha256'] == hashlib.sha256(Path(result['wheel']).read_bytes()).hexdigest()
