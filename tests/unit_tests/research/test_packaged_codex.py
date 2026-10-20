"""Build-time native binary execution, independent of model authentication."""
import hashlib
import importlib.util
from pathlib import Path
import stat
import tempfile

import pytest


def installer():
    spec = importlib.util.spec_from_file_location('m1_install_codex', Path('/workspace/deploy/m1/install_codex.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pinned_elf_is_copied_executed_and_not_a_console_wrapper():
    from codex_cli_bin import bundled_codex_path
    scratch=Path('/var/lib/ai4r-install-probe')
    assert scratch.is_dir(), 'Use the explicit trusted native-install probe mount from compose.verify.yaml'
    with tempfile.TemporaryDirectory(prefix='codex-install-',dir=scratch) as directory:
        target,receipt=Path(directory)/'codex',Path(directory)/'receipt.json'
        value = installer().install_packaged_codex(target, receipt)
        assert not target.is_symlink() and target.read_bytes().startswith(b'\x7fELF')
        assert target.read_bytes() == Path(bundled_codex_path()).read_bytes()
        assert stat.S_IMODE(target.stat().st_mode) == 0o555
        assert hashlib.sha256(target.read_bytes()).hexdigest() == value['sha256']
        assert value['version'] == 'codex-cli 0.144.4'
        assert value['model_access'] == value['tool_confinement'] == 'NOT_RUN'


def test_existing_or_linked_binary_is_never_replaced(tmp_path):
    target, receipt = tmp_path/'codex', tmp_path/'receipt.json'
    target.write_bytes(b'existing-operator-file')
    with pytest.raises(ValueError, match='NEW_IMMUTABLE'):
        installer().install_packaged_codex(target, receipt)
    assert target.read_bytes() == b'existing-operator-file' and not receipt.exists()
