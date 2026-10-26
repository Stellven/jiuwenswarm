"""Optional private asset release for authored benchmark integration checks."""
import os

import pytest


@pytest.fixture(scope="module")
def benchmark_case_assets():
    from benchmarks.harbor_suite.contracts import resolve_cases_root
    root = resolve_cases_root()
    if not root.is_dir():
        if "AI4R_BENCHMARK_CASES_DIR" in os.environ:
            pytest.fail("Configured benchmark asset directory is missing: " + str(root))
        pytest.skip("External benchmark cases required; set AI4R_BENCHMARK_CASES_DIR")
    return root
