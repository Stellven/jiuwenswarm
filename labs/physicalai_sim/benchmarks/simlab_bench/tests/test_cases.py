"""SIMLAB-Bench case format and oracle checks (benchmark group; AC-020, AC-021 manifest part).

Every case declares objective, inputs, grading and primary metric (B01); has at least three
regular variants; keeps expected values only in referee/ (B12); freezes each tolerance with its
reason; cites its adopted reference (AC-021); records the engine version; ships a stdlib-only
oracle whose own unit tests pass on correct, defective and missing evidence.
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1]
CASES = sorted(p for p in (BENCH / "cases").iterdir() if (p / "case.json").is_file())


def test_families_present():
    fams = {json.loads((c / "case.json").read_text())["family"] for c in CASES}
    tbs = {json.loads((c / "case.json").read_text())["tb_id"] for c in CASES}
    assert fams == {"F1", "F5"}
    assert {f"TB-0{i}" for i in range(1, 10)} <= tbs


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_case_format(case):
    c = json.loads((case / "case.json").read_text())
    for k in ("objective", "inputs", "grading", "primary_metric", "variants", "references", "engine", "model_assumptions"):
        assert c.get(k), k
    import mujoco
    assert c["engine"]["mujoco"] == mujoco.__version__, "a MuJoCo upgrade forces re-freezing and rerunning the cases"
    regular = [v for v in c["variants"] if not v.get("negative_control")]
    assert len(regular) >= 3 and all(v["split"] == "development" for v in c["variants"])
    crit = json.loads((case / "referee" / "criteria.json").read_text())
    assert set(crit["variants"]) == {v["id"] for v in c["variants"]}
    for vid, v in crit["variants"].items():
        assert v.get("tolerance_reason"), vid
    def keys(x):
        if isinstance(x, dict):
            for k, v in x.items():
                yield k, v
                yield from keys(v)
        elif isinstance(x, list):
            for v in x:
                yield from keys(v)
    for p in (case / "public").glob("*.json"):
        tpl = json.loads(p.read_text())
        assert not any(c.get("check_kind") == "known_answer" for c in tpl["header"].get("checks", [])), p
        found = {k for k, _v in keys(tpl)}
        assert not found & {"expected", "reference", "tolerance_rel", "tolerance_e", "tolerance_angle_rad"}, (p, "expected values stay in referee/ (B12)")
    for need in ("oracle.py", "test_oracle.py", "README.md"):
        assert (case / need).is_file()


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_oracle_is_stdlib_only_and_independent(case):
    tree = ast.parse((case / "oracle.py").read_text())
    mods = {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert mods <= set(sys.stdlib_module_names) | {""}, mods
    assert "simlab" not in mods


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_oracle_unit_tests(case):
    r = subprocess.run([sys.executable, "-I", str(case / "test_oracle.py")], capture_output=True, text=True, cwd="/tmp", timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]


def test_frozen_release_matches_case_files():
    from simlab import bench

    releases = sorted((BENCH / "releases").glob("*.json"))
    if not releases:
        pytest.skip("no frozen release yet (freeze with `simlab bench freeze` before a campaign)")
    rel = releases[-1].stem
    chk = bench.verify_release(rel, bench.all_cases())
    assert chk["problems"] == [], chk["problems"]
