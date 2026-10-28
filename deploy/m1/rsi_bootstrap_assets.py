"""Capture installed source metadata in a fresh isolated bootstrap volume.

No model, admission, standing, signing, generated RSI fixtures or execution API
is called. Captured catalog guards are authored package resources, not measured
checking eligibility. This operator template precedes fresh custody provisioning.
"""
from __future__ import annotations

import fnmatch
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path('/var/lib/ai4r-rsi-bootstrap')
SCHEMA = 'ai4r-rsi-bootstrap-source-capture:1'
MARKER = 'source-capture.json'


def _need(condition):
    if not condition:
        raise ValueError('Fresh private installed-source bootstrap prerequisites differ')


def _source_digest():
    import jiuwenswarm.research as research
    package = Path(research.__file__).resolve().parent.parent
    rows = []
    for name in ('research', 'research_assets', 'research_contracts'):
        for path in sorted((package / name).rglob('*')):
            if path.is_file() and path.suffix in {'.py', '.json', '.txt', '.md'}:
                _need(not path.is_symlink())
                rows.append([path.relative_to(package).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()])
    _need(bool(rows))
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()


def _custody(root):
    _need(sys.platform == 'linux' and os.geteuid() == 12001 and os.getegid() == 12001)
    _need(root == ROOT and root.is_absolute())
    _need(not any(path.is_symlink() for path in (root, *root.parents)))
    metadata = root.stat()
    _need(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == metadata.st_gid == 12001
          and stat.S_IMODE(metadata.st_mode) == 0o700)
    from jiuwenswarm.research_rsi.preparation_runtime import _native_fs
    _native_fs(root)
    for path in root.rglob('*'):
        metadata = path.lstat()
        _need(not path.is_symlink() and metadata.st_uid == metadata.st_gid == 12001
              and not metadata.st_mode & 0o077
              and (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)))
        if path.is_file():
            _need(metadata.st_nlink == 1)


@contextmanager
def _private_creation():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


def capture():
    with _private_creation():
        return _capture()


def _capture():
    root = ROOT
    _custody(root)
    # Local-profile capture supports optional scientific imports in other flows.
    # This finite owner accepts only installed metadata and no external inputs.
    _need(not os.environ.get('JIUWENSWARM_M1_EXTERNAL_DATASET')
          and not os.environ.get('JIUWENSWARM_M1_EXTERNAL_SCORING_PINS'))
    source_sha = _source_digest()
    marker = root / MARKER
    previous = None
    if marker.exists():
        previous = json.loads(marker.read_bytes())
        _need(previous.get('schema') == SCHEMA and previous.get('installed_source_sha256') == source_sha)
        _need({path.name for path in root.iterdir()} == {'core', 'input', 'operator-template', MARKER})
    else:
        # Interrupted captures require explicit inspection, never implicit replay.
        _need(not any(root.iterdir()))
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.capsules.assets import build_research_assets
    from jiuwenswarm.research.local_profile import capture_local_profile, _write_once
    store = SQLiteRunStore(root / 'core', recover=False, input_root=root / 'input')
    try:
        assets = build_research_assets(store)
        screening = assets['screening']
        declaration = store.read_record(screening['declaration_ref'], contract_id='capsule-declaration')
        evolution = declaration['evolution']
        _need(evolution['rsi'] == 'propose' and any(
            fnmatch.fnmatchcase('ranking_parent.txt', value.removeprefix('files:'))
            for value in evolution['may_change'] if value.startswith('files:')))
        import jiuwenswarm.research as research
        helper = Path(research.__file__).parent / 'capsules/ranking.py'
        _need(store.read_blob(screening['body_refs']['ranking_parent.txt']) == helper.read_bytes())
        captured = capture_local_profile(store, root / 'operator-template',
            input_root=root / 'input', development_builtin_catalog=False,
            requested_model='gpt-6-luna')
        binding = store.read_record(captured['binding_ref'])
        _need(binding['protected_options']['development_builtin_catalog'] is False)
        _need(binding['protected_options'].get('calibration_runtime_ref') is not None)
        result = {'schema': SCHEMA, 'status': 'SOURCE_CAPTURED_NOT_READY',
            'installed_source_sha256': source_sha,
            'operator_template_path': captured['configuration_path'],
            'bootstrap_binding_ref': captured['binding_ref'],
            'configuration_ref': binding['configuration_ref'],
            'model_selection_profile_ref': binding['model_selection_profile_ref'],
            'deployment_ref': binding['deployment_ref'],
            'requested_model': 'gpt-6-luna',
            'screening_declaration_ref': screening['declaration_ref'],
            'screening_helper_ref': screening['body_refs']['ranking_parent.txt'],
            'requirements': ['fresh_custodian_public_pin_and_final_configuration_capture',
                'real_catalog_guard_calibration_and_admitted_active_exact_capsules',
                'dedicated_model_authentication', 'independent_RSI_fixture_review',
                'draft_scope_security_qualification_and_real_calibration',
                'final_scope_security_qualification_and_session_authorization']}
        if previous is not None:
            _need(previous == result)
        _write_once(marker, result)
        return result
    finally:
        store.close()


def main():
    from jiuwenswarm.research.contracts import ResearchError
    try:
        result = capture()
    except (ResearchError, ValueError, OSError, KeyError, TypeError):
        print(json.dumps({'schema': SCHEMA, 'status': 'BLOCKED',
                          'reason': 'Installed source capture or private native custody is unavailable'}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
