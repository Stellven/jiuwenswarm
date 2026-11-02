"""Move one experiment between SIMLAB stores as plain files (PAS-M1-001 B14, used by tools/fresh_checkout.py).

    python -m simlab.interface.portable export --data-dir D --run RUN --out DIR   # experiment, manifest, artifacts, recorded result
    python -m simlab.interface.portable import --data-dir D --dir DIR             # re-author through the tools, bind, submit

Import goes through the authoring operations, so the identical content gives the
identical experiment and manifest IDs (the manifest binds that one experiment).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

PUT = {"geometry": "geometry_put", "collision": "collision_put", "model_file": "model_file_put"}


def export(data_dir: str, run_id: str, out: Path) -> dict:
    from simlab.runner.results import build_result  # noqa: PLC0415
    from simlab.store import Store  # noqa: PLC0415

    st = Store(data_dir)
    res = build_result(st, run_id)
    exp = st.get_experiment(res["experiment_id"])
    man = st.get_manifest(exp["assets"]["manifest_id"])
    (out / "artifacts").mkdir(parents=True, exist_ok=True)
    for a in man["artifacts"]:
        p = out / "artifacts" / a["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(st.get_blob(a["sha256"]))
    (out / "experiment.json").write_text(json.dumps(exp, indent=1, sort_keys=True))
    (out / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    (out / "recorded-result.json").write_text(json.dumps(res, indent=1, sort_keys=True))
    return {"experiment_id": exp["experiment_id"], "manifest_sha256": man["manifest_sha256"], "run_id": run_id,
            "artifacts": len(man["artifacts"])}


def import_and_submit(client, d: Path) -> dict:
    exp = json.loads((d / "experiment.json").read_text())
    man = json.loads((d / "manifest.json").read_text())
    from simlab.authoring import HEADER_FIELDS  # noqa: PLC0415

    head = {k: v for k, v in exp.items() if k in HEADER_FIELDS and v is not None}
    draft = client.draft_create(header=head)["draft_id"]
    for a in man["artifacts"]:
        data = (d / "artifacts" / a["path"]).read_bytes()
        k = a["kind"]
        if k in PUT:
            if k == "model_file":
                client.model_file_put(draft_id=draft, path=a["path"], content=data.decode())
            else:
                client.call(PUT[k], draft_id=draft, path=a["path"], content_b64=base64.b64encode(data).decode())
        elif k == "procedure":
            client.procedure_put(draft_id=draft, procedure=json.loads(data))
        elif k == "intervention":
            client.intervention_put(draft_id=draft, intervention=json.loads(data))
        elif k == "measurement":
            client.measurement_put(draft_id=draft, measurement=json.loads(data))
        elif k == "observation":
            client.observation_put(draft_id=draft, observation=json.loads(data), probe=a["path"].startswith("probes/"))
        elif k == "component":
            client.component_put(draft_id=draft, path=a["path"], extension_point=a["extension_point"], code=data.decode())
    b = client.bind(draft_id=draft)
    same = {"experiment_id": b["experiment"]["experiment_id"] == exp["experiment_id"],
            "manifest_sha256": b["manifest"]["manifest_sha256"] == man["manifest_sha256"]}
    sub = client.submit(experiment=b["experiment"])
    if "run_id" not in sub:
        return {"identical_content": same, "findings": sub.get("findings")}
    client.wait(run_id=sub["run_id"], timeout_s=1800)
    return {"identical_content": same, "run_id": sub["run_id"], "result": client.result(run_id=sub["run_id"])}


def compare(recorded: dict, fresh: dict) -> dict:
    """Declared rule: bitwise-equal per-step state digests and equal measurement values, trial by trial."""
    diffs = []
    for a, b in zip(recorded["trials"], fresh["trials"]):
        da, db = [x["state_digest"] for x in a["attempts"]], [x["state_digest"] for x in b["attempts"]]
        if da != db:
            diffs.append({"trial": a["trial_id"], "difference": "state digests", "recorded": da, "fresh": db})
        ma = {m["measurement_id"]: m["value"] for m in a["measurements"]}
        mb = {m["measurement_id"]: m["value"] for m in b["measurements"]}
        if ma != mb:
            diffs.append({"trial": a["trial_id"], "difference": "measurements", "recorded": ma, "fresh": mb})
    if len(recorded["trials"]) != len(fresh["trials"]):
        diffs.append({"difference": "trial count", "recorded": len(recorded["trials"]), "fresh": len(fresh["trials"])})
    return {"rule": "bitwise-equal per-step state digests and equal measurement values, trial by trial", "equal": not diffs,
            "differences": diffs[:20], "trials": len(fresh["trials"])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="op", required=True)
    e = sub.add_parser("export")
    e.add_argument("--data-dir", required=True)
    e.add_argument("--run", required=True)
    e.add_argument("--out", type=Path, required=True)
    i = sub.add_parser("import")
    i.add_argument("--data-dir", required=True)
    i.add_argument("--dir", type=Path, required=True)
    i.add_argument("--report", type=Path)
    a = ap.parse_args(argv)
    if a.op == "export":
        print(json.dumps(export(a.data_dir, a.run, a.out)))
        return 0
    from simlab.interface.client import Client  # noqa: PLC0415

    out = import_and_submit(Client(a.data_dir), a.dir)
    if "result" in out:
        out["comparison"] = compare(json.loads((a.dir / "recorded-result.json").read_text()), out["result"])
        out["result_identity"] = out["result"]["identity"]
        del out["result"]
    text = json.dumps(out, indent=1, sort_keys=True, default=str)
    if a.report:
        a.report.write_text(text)
    print(text)
    return 0 if out.get("comparison", {}).get("equal") and all(out["identical_content"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
