from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.local_profile import capture_local_profile
from jiuwenswarm.research.state import SQLiteRunStore


def test_requirements_selection_rejects_unknown_and_checking_only_refresh():
    for version in ('latest', 'm1-10', None, []):
        with pytest.raises(ResearchError, match='Unsupported explicit Requirements'):
            capture_local_profile(None, 'unused', requirements_version=version)
    with pytest.raises(ResearchError, match='Checking-only refresh'):
        capture_local_profile(None, 'unused', requirements_version='m1-9', legacy_checking_refresh=True)


def test_actual_profile_freezes_requirements_release_and_rejects_drift():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        inputs = root / 'input'
        inputs.mkdir()
        store = SQLiteRunStore(root / 'state', input_root=inputs)
        try:
            with patch('jiuwenswarm.research.local_profile.os.geteuid', return_value=inputs.stat().st_uid, create=True), patch('jiuwenswarm.research.local_profile.stat.S_IMODE', return_value=0o700), patch('jiuwenswarm.research.bootstrap_gateway._protected_file', side_effect=lambda p: Path(p).read_bytes()):
                profile = root / 'operator' / 'requirements9'
                result = capture_local_profile(store, profile, input_root=inputs, requirements_version='m1-9', screening_version='m1-5', allow_missing_science=True)
                binding = store.read_record(result['binding_ref'])
                assert binding['protected_options']['requirements_version'] == 'm1-9'
                assert binding['protected_options']['screening_version'] == 'm1-5'
                assert capture_local_profile(store, profile, input_root=inputs, requirements_version='m1-9', screening_version='m1-5', allow_missing_science=True) == result
                with pytest.raises(ResearchError, match='Frozen Requirements release changed'):
                    capture_local_profile(store, profile, input_root=inputs, screening_version='m1-5', allow_missing_science=True)
        finally:
            store.close()
