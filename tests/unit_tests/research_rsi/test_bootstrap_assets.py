"""Actual shipped source capture stays separate from execution and authority."""
import importlib.util
import hashlib
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_bootstrap_assets.py'
spec = importlib.util.spec_from_file_location('rsi_bootstrap_assets_under_test', SOURCE)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


@pytest.fixture
def capture_root(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, 'ROOT', tmp_path)
    # Test actual authoring APIs without claiming native filesystem custody.
    monkeypatch.setattr(bootstrap, '_custody', lambda root: None)
    monkeypatch.delenv('JIUWENSWARM_M1_EXTERNAL_DATASET', raising=False)
    monkeypatch.delenv('JIUWENSWARM_M1_EXTERNAL_SCORING_PINS', raising=False)
    return tmp_path


def test_actual_source_capture_is_idempotent_and_grants_no_authority(capture_root, monkeypatch):
    from jiuwenswarm.research.calibration_authority import CalibrationAuthority
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research_rsi.signing import Signer
    from jiuwenswarm.research_rsi.targets import ranking_preparation
    from jiuwenswarm.research.state import SQLiteRunStore
    import jiuwenswarm.research as research

    def forbidden(*args, **kwargs):
        raise AssertionError('Source capture attempted an authority or execution effect')
    for owner, methods in ((CalibrationAuthority, ('start', 'execute')),
                           (LibraryService, ('admit', 'admit_rsi', 'set_standing')),
                           (Signer, ('sign',)),
                           (ranking_preparation, ('prepare_ranking', 'prepare_helper'))):
        for method in methods:
            monkeypatch.setattr(owner, method, forbidden)
    result = bootstrap.capture()
    marker_before = (capture_root / bootstrap.MARKER).read_bytes()
    assert result == bootstrap.capture()
    assert (capture_root / bootstrap.MARKER).read_bytes() == marker_before
    assert result['status'] == 'SOURCE_CAPTURED_NOT_READY'
    assert result['requested_model']=='gpt-6-luna'
    assert result['screening_declaration_ref']['sha256'] == '1f8f0e2f036d7b8d629ec8241e7279e71b60f43c66ab95ce04be37d6af8602e5'
    store = SQLiteRunStore(capture_root / 'core', recover=False, input_root=capture_root / 'input')
    try:
        assert store.read_blob(result['screening_helper_ref']) == (Path(research.__file__).parent / 'capsules/ranking.py').read_bytes()
        binding = store.read_record(result['bootstrap_binding_ref'])
        operator = store.read_record(result['configuration_ref'])
        assert store.read_record(result['deployment_ref'])['requested_model']=='gpt-6-luna'
        assert operator['rsi'] == {'custodian_key_id': None, 'custodian_public_key': None}
        assert binding['protected_options']['development_builtin_catalog'] is False
        kinds = {row[0] for row in store.connection.execute('SELECT DISTINCT kind FROM records')}
        assert not kinds.intersection({'library-admission', 'activation-record', 'model-call',
            'invocation-observation', 'calibration-measurement', 'rsi-session-result'})
        assert 'calibration-runtime' in kinds
    finally:
        store.close()


def test_changed_installation_is_refused_before_store_open(capture_root, monkeypatch):
    bootstrap.capture()
    monkeypatch.setattr(bootstrap, '_source_digest', lambda: '0' * 64)
    from jiuwenswarm.research.state import SQLiteRunStore
    monkeypatch.setattr(SQLiteRunStore, '__init__', lambda *a, **k: pytest.fail('Changed installation opened store'))
    with pytest.raises(ValueError):
        bootstrap.capture()


def test_partial_or_foreign_volume_is_not_adopted(capture_root):
    (capture_root / 'unreviewed').write_text('retained')
    with pytest.raises(ValueError):
        bootstrap.capture()
    assert (capture_root / 'unreviewed').read_text() == 'retained'
    assert not (capture_root / 'core').exists()


def test_external_scientific_import_is_refused(capture_root, monkeypatch):
    monkeypatch.setenv('JIUWENSWARM_M1_EXTERNAL_DATASET', '/outside/data')
    with pytest.raises(ValueError):
        bootstrap.capture()
    assert not list(capture_root.iterdir())


def test_native_owner_gate_precedes_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap.sys, 'platform', 'win32')
    with pytest.raises(ValueError):
        bootstrap._custody(tmp_path)
    assert not list(tmp_path.iterdir())


def test_all_authored_corpus_bytes_match_original_manifest():
    from importlib.resources import files
    root = files('jiuwenswarm.research').joinpath('resources/calibration')
    manifest = json.loads(root.joinpath('manifest.json').read_bytes())
    assert len(manifest['files']) == 87
    mismatches = [name for name, digest in manifest['files'].items()
                  if hashlib.sha256(root.joinpath(name).read_bytes()).hexdigest() != digest]
    assert not mismatches, mismatches
