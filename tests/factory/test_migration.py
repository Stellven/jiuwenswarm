"""Removed M1 configuration must fail before startup side effects."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from jiuwenswarm.factory.migration import LegacyConfigError, check_legacy_config


@pytest.mark.parametrize("key", [
    "JIUWENSWARM_M1_PROFILE", "JIUWENSWARM_M1_ORIGIN",
    "JIUWENSWARM_M1_TOKEN_FILE", "JIUWENSWARM_M1_CLIENT_CONFIG",
    "JIUWENSWARM_M1_FUTURE_KEY", "AI4R_PILOT_BUDGET_DIRECTORY",
])
def test_legacy_key(key):
    with pytest.raises(LegacyConfigError, match=key) as error:
        check_legacy_config({key: "1"}, [])
    assert "M1 pipeline was removed on this branch" in str(error.value)
    assert "docs/architecture/factory/MIGRATION.md" in str(error.value)


def test_clean_environment():
    check_legacy_config({}, [])
    check_legacy_config({"JIUWENSWARM_M1_PROFILE": "", "AI4R_PILOT_BUDGET_DIRECTORY": ""}, [])
    check_legacy_config({"JIUWENSWARM_DATA_DIR": "/tmp/workspace"}, ["chat"])


def test_research_argument():
    with pytest.raises(LegacyConfigError, match="research"):
        check_legacy_config({}, ["research"])


@pytest.mark.parametrize("module,args,key", [
    ("jiuwenswarm.channels.cli.main", ["research"], None),
    ("jiuwenswarm.codex_start", ["--help"], "JIUWENSWARM_M1_PROFILE"),
    ("jiuwenswarm.start_services", ["--help"], "JIUWENSWARM_M1_PROFILE"),
    ("jiuwenswarm.channels.cli.main", ["--help"], "AI4R_PILOT_BUDGET_DIRECTORY"),
])
def test_entrypoint_rejects_before_startup(module, args, key, tmp_path):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("JIUWENSWARM_M1_") and k != "AI4R_PILOT_BUDGET_DIRECTORY"}
    env["JIUWENSWARM_SKIP_DOTENV"] = "1"
    env["JIUWENSWARM_DATA_DIR"] = str(tmp_path / "unused-profile")
    if key:
        env[key] = "1"
    result = subprocess.run([sys.executable, "-m", module, *args],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 2, result.stderr
    assert (key or "research") in result.stderr
    assert "M1 pipeline was removed on this branch" in result.stderr
    assert "docs/architecture/factory/MIGRATION.md" in result.stderr
    assert not Path(env["JIUWENSWARM_DATA_DIR"]).exists()
