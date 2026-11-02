"""V-X1.2 test-bench part (AC-018, AC-010, AC-011): inside the check group, every phase 1 test bench (F1 TB-01 to
TB-09) and the F5 replay family pass to their frozen specification: the campaign profile of the frozen release,
every variant, three repeats, graded by the independent oracles. The release must match the case files."""
import json

import pytest

from simlab import bench

RELEASE = "pas-m1-phase1-r1"


def test_campaign_on_frozen_release(service, tmp_path):
    chk = bench.verify_release(RELEASE, bench.all_cases())
    assert chk["problems"] == [], chk["problems"]
    out = bench.run_profile(service, profile="campaign", cases=None, family=None, release=RELEASE, output=tmp_path)
    rep = json.loads((next(tmp_path.iterdir()) / "report.json").read_text())
    cells = [r for fam in rep["families"].values() for rows in fam["cases"].values() for r in rows]
    bad = [(r["case_id"], r["variant_id"], r["repeat"], r["outcome"], [c for c in r["checks"] if c["status"] != "pass"][:2])
           for r in cells if r["outcome"] != "PASS"]
    assert not bad, bad
    assert out["families"]["F1"]["PASS"] == 90 and out["families"]["F5"]["PASS"] == 9
    tbs = {r["tb_id"] for r in cells if r["family"] == "F1"}
    assert {f"TB-0{i}" for i in range(1, 10)} <= tbs
    print(json.dumps({"report": out["report_dir"], "families": out["families"],
                      "max_error_by_case": {cid: max((r["metrics"].get("primary_value") for r in rows
                                                      if isinstance(r["metrics"].get("primary_value"), float) and not r["negative_control"]), default=None)
                                            for fam in rep["families"].values() for cid, rows in fam["cases"].items()}}, indent=1))
