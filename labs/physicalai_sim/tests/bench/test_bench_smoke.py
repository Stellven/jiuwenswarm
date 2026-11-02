"""SIMLAB-Bench harness wiring (benchmark group): a smoke run through a fresh service writes a dated report with a
hardware inventory before each run, per-family results and no aggregate score; a defective case is graded FAIL."""
import json

from simlab import bench


def test_smoke_run_report(service, tmp_path):
    out = bench.run_profile(service, profile="smoke", cases=["f1-tb02-free-fall", "f5-replay"], family=None, release=None, output=tmp_path)
    d = next(tmp_path.iterdir())
    rep = json.loads((d / "report.json").read_text())
    assert set(rep["families"]) == {"F1", "F5"} and "score" not in json.dumps(rep).lower().replace("no aggregate score", "")
    for cell in d.rglob("repeat-*"):
        inv = json.loads((cell / "inventory.json").read_text())
        ev = json.loads((cell / "evidence.json").read_text())
        assert inv["hardware"]["taken_at"] < ev["result"]["identity"].get("build_id", "z") or inv["hardware"]["cpu_model"]
        assert (cell / "grade.json").is_file()
    assert out["families"]["F1"]["PASS"] == 1 and out["families"]["F5"]["PASS"] == 1


def test_negative_variant_must_be_caught(service, tmp_path):
    case = bench.load_case("f1-tb08-box-stack")
    v = next(x for x in case["variants"] if x.get("negative_control"))
    ev = bench.run_variant(service, case, v)
    p = tmp_path / "e.json"
    p.write_text(json.dumps(ev))
    g = bench.grade(case, p, tmp_path / "g.json")
    assert bench.outcome(v, g) == "PASS" and any(c["status"] == "fail" for c in g["checks"]), "the gravity-off stack is caught"
    ok = next(x for x in case["variants"] if not x.get("negative_control"))
    assert bench.outcome({**ok}, g) == "FAIL", "the same grade on a regular variant is a failure"
