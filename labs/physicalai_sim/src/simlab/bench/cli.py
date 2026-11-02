"""simlab bench: run, freeze, speed, admit (PAS-M1-001 B12)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simlab bench")
    sub = ap.add_subparsers(dest="op", required=True)
    r = sub.add_parser("run")
    r.add_argument("--case", action="append")
    r.add_argument("--family")
    r.add_argument("--profile", default="smoke", choices=["smoke", "development", "campaign"])
    r.add_argument("--release")
    r.add_argument("--output", type=Path, required=True)
    r.add_argument("--data-dir", default=os.environ.get("SIMLAB_DATA_DIR"))
    r.add_argument("--compute-log", type=Path)
    r.add_argument("--task", default="PAS-M1-001")
    f = sub.add_parser("freeze")
    f.add_argument("--release", required=True)
    s = sub.add_parser("speed")
    s.add_argument("--output", type=Path)
    s.add_argument("--steps", type=int, default=20000)
    ad = sub.add_parser("admit")
    ad.add_argument("--report", type=Path, required=True)
    ad.add_argument("--data-dir", default=os.environ.get("SIMLAB_DATA_DIR"))
    a = ap.parse_args(argv)
    from simlab import bench
    if a.op == "run":
        from simlab.interface.client import Client
        out = bench.run_profile(Client(a.data_dir), profile=a.profile, cases=a.case, family=a.family, release=a.release, output=a.output,
                                compute_log=a.compute_log, task=a.task)
        print(json.dumps(out, indent=1))
        return 0
    if a.op == "freeze":
        print(json.dumps({k: v for k, v in bench.freeze(a.release).items() if k != "files"}, indent=1))
        return 0
    if a.op == "speed":
        rec = bench.speed(a.steps)
        if a.output:
            a.output.parent.mkdir(parents=True, exist_ok=True)
            a.output.write_text(json.dumps(rec, indent=1, default=str))
        print(json.dumps({k: rec[k] for k in ("steps_per_s", "realtime_factor", "wall_s", "cpu_s", "peak_rss_mb", "mean_contacts")}))
        return 0
    if a.op == "admit":
        from simlab.registry import admit
        from simlab.store import Store
        rep = json.loads((a.report / "report.json").read_text())
        f1 = rep["families"].get("F1")
        tbs = sorted({r["tb_id"] for rows in (f1 or {}).get("cases", {}).values() for r in rows})
        need = [f"TB-0{i}" for i in range(1, 10)]
        cells = [r for rows in (f1 or {}).get("cases", {}).values() for r in rows]
        ok = bool(cells) and all(r["outcome"] == "PASS" for r in cells) and set(need) <= set(tbs) and rep["profile"] == "campaign" \
            and not rep.get("release_problems")
        reason = (f"F1 campaign {rep['run_id']} release {rep['release']}: {len(cells)} cells, all PASS (TB-01..TB-09)" if ok else
                  f"F1 campaign {rep['run_id']}: not admitted ({sum(1 for r in cells if r['outcome'] != 'PASS')} cells not PASS; "
                  f"TB present {tbs}; release problems {rep.get('release_problems')})")
        pending = sorted({r["case_id"] for r in cells if (bench.CASES / r["case_id"] / "referee" / "criteria.json").is_file()
                          and any(v.get("confirm") for v in json.loads((bench.CASES / r["case_id"] / "referee" / "criteria.json").read_text())["variants"].values())})
        if ok and pending:
            reason += f"; frozen tolerances marked [confirm] await the owner's confirmation in {len(pending)} cases ({', '.join(pending)})"
        print(json.dumps(admit(Store(a.data_dir), "engine:mujoco", str(a.report), ok, reason), indent=1))
        return 0 if ok else 1
    return 2
