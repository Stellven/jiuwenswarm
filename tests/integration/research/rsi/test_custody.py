"""Inspect the actual controller identity/mount boundary without oracle reads."""
import os
from pathlib import Path

import pytest


def test_actual_controller_has_no_custodian_or_main_private_mount():
    assert os.geteuid() == 12001, "BLOCKED: execute in the RSI controller observer service"
    forbidden = {"/var/lib/ai4r/native", "/var/lib/ai4r-accounts", "/hidden-fixtures",
                 "/var/lib/ai4r-rsi/custodian", "/var/lib/ai4r-rsi-inputs/hidden"}
    mounts = {line.split()[4] for line in Path("/proc/self/mountinfo").read_text().splitlines()}
    assert not forbidden & mounts, "A private custody/main root was mounted into the controller"
    for name in forbidden:
        path = Path(name)
        if not path.exists(): continue
        with pytest.raises(PermissionError):
            if path.is_dir(): list(path.iterdir())
            else: path.read_bytes()
    assert not Path("/var/run/docker.sock").exists()


def test_actual_controller_does_not_hold_worker_or_custodian_identity():
    assert os.geteuid() == os.getegid() == 12001, "BLOCKED: execute under the installed controller UID/GID"
    assert 12003 not in os.getgroups()
    assert Path("/proc/self/status").read_text().split("CapEff:\t", 1)[1].splitlines()[0] == "0000000000000000"
    # Group12002 may grant only the custodian-owned socket. Its presence is
    # never treated as authority to read a private oracle root.
