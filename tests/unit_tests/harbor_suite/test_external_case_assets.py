"""An external asset release must be used consistently, without repo fallback."""
import shutil
from pathlib import Path

import pytest

from benchmarks.harbor_suite import prepare
from benchmarks.harbor_suite.comparison_harbor import _source_content_oracle
from benchmarks.harbor_suite.contracts import load_cases, resolve_cases_root, validate_bundle


def test_external_release_is_frozen_and_missing_release_does_not_fallback(tmp_path, monkeypatch):
    source = resolve_cases_root()
    external = tmp_path / "external-cases"
    shutil.copytree(source, external, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    marker = b"\n# External-release provenance marker.\n"
    oracle = external / "cc01-transfer/oracle.py"
    oracle.write_bytes(oracle.read_bytes() + marker)
    monkeypatch.setenv("AI4R_BENCHMARK_CASES_DIR", str(external))
    assert len(load_cases()) == 10
    assert _source_content_oracle() == oracle
    bundle = tmp_path / "bundle"
    prepare.main(["--destination", str(bundle), "--python-image",
                  "python:3.12-slim-bookworm@sha256:" + "1" * 64,
                  "--case", "cc01-transfer", "--variant", "evaluate-boundary"])
    index = validate_bundle(bundle)
    assert len(index["tasks"]) == 1
    frozen = bundle / "tasks" / index["tasks"][0]["task_key"] / "tests/oracle.py"
    assert frozen.read_bytes() == oracle.read_bytes()
    # Explicit root overrides the environment, including invalid paths: no fallback.
    missing = tmp_path / "missing"
    assert resolve_cases_root(missing) == missing
    with pytest.raises((OSError, ValueError)):
        load_cases(missing)
    monkeypatch.setenv("AI4R_BENCHMARK_CASES_DIR", str(missing))
    with pytest.raises((OSError, ValueError)):
        load_cases()
    # Already frozen bundles are independent of subsequent operator configuration.
    assert validate_bundle(bundle) == index


pytestmark = pytest.mark.usefixtures("benchmark_case_assets")
