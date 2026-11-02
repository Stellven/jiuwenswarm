"""X1.6 fresh-checkout reproduction (PAS-M1-001 B14, V-X1.6, AC-017; ARCH X1.6).

    python tools/fresh_checkout.py --commit SHA --run RUN --output DIR       # the check (needs an owner commit)
    python tools/fresh_checkout.py --rehearsal  --run RUN --output DIR       # a rehearsal from a clean export, never PASS

1. Source: a clean clone at SHA (only committed files), or for the rehearsal an export of
   the lab's tracked and untracked, non-ignored files.
2. Rebuild the image with --no-cache from that source alone (the Docker build context is
   the clone; uv sync --frozen from its uv.lock).
3. Declared inputs: the recorded run's experiment, manifest and artifacts, exported from the
   original store. Nothing else enters the fresh container: an empty data directory, the
   inputs mounted read-only, no network.
4. Re-author the experiment through the tools (identical content gives identical IDs), run it,
   and compare with the recorded result: bitwise-equal per-step state digests and measurements.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[1]


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--commit")
    g.add_argument("--rehearsal", action="store_true")
    ap.add_argument("--run", required=True, help="recorded run ID in the original data directory")
    ap.add_argument("--data-dir", default=os.environ.get("SIMLAB_DATA_DIR", os.path.expanduser("~/simlab-data")))
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args(argv)
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tag = f"simlab-runner:fresh-{uuid.uuid4().hex[:8]}"
    work = Path(tempfile.mkdtemp(prefix="simlab-fresh-"))
    rec = {"record": "simlab-fresh-checkout", "v_id": "V-X1.6", "ac": "PAS-M1-001/AC-017", "mode": "commit" if a.commit else "rehearsal",
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "recorded_run": a.run, "work_dir": str(work)}
    t0 = time.monotonic()
    # 1. source
    src = work / "checkout"
    if a.commit:
        r = sh(["git", "clone", "--quiet", "--no-local", "--no-hardlinks", str(REPO), str(src)])
        r2 = sh(["git", "-C", str(src), "checkout", "--quiet", a.commit]) if r.returncode == 0 else r
        rec["source"] = {"kind": "clean clone", "commit": a.commit, "clone_exit": r.returncode, "checkout_exit": r2.returncode,
                         "error": (r.stderr + r2.stderr)[-1500:]}
        lab = src / "labs" / "physicalai_sim"
    else:
        files = sh(["git", "-C", str(REPO), "ls-files", "-co", "--exclude-standard", "labs/physicalai_sim"]).stdout.split()
        files = [f for f in files if not f.startswith("labs/physicalai_sim/missions/")]
        for f in files:
            dst = src / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / f, dst)
        rec["source"] = {"kind": "clean export of the working tree (tracked + untracked, not ignored, missions/ excluded)", "files": len(files),
                         "head": sh(["git", "-C", str(REPO), "rev-parse", "HEAD"]).stdout.strip()}
        lab = src / "labs" / "physicalai_sim"
    if not (lab / "uv.lock").is_file():
        rec.update(result="FAIL" if a.commit else "REHEARSAL_FAILED", reason="the checkout has no labs/physicalai_sim/uv.lock (SIMLAB not committed?)")
        (out / "fresh-checkout.json").write_text(json.dumps(rec, indent=1))
        print(json.dumps({k: rec[k] for k in ("mode", "result", "reason")}))
        return 1
    # 2. rebuild
    b0 = time.monotonic()
    with (out / "docker-build.log").open("w") as log:
        b = subprocess.run(["docker", "build", "--no-cache", "-f", str(lab / "docker" / "Dockerfile"), "-t", tag, str(lab)], stdout=log, stderr=subprocess.STDOUT)
    rec["build"] = {"exit_code": b.returncode, "wall_s": round(time.monotonic() - b0, 1), "tag": tag, "context": str(lab), "no_cache": True,
                    "image_id": sh(["docker", "image", "inspect", "--format", "{{.Id}}", tag]).stdout.strip(),
                    "build_identity": json.loads(sh(["docker", "run", "--rm", "--network", "none", tag, "build-identity"]).stdout or "{}")}
    if b.returncode != 0:
        rec.update(result="FAIL" if a.commit else "REHEARSAL_FAILED", reason="image rebuild failed")
        (out / "fresh-checkout.json").write_text(json.dumps(rec, indent=1))
        return 1
    # 3. declared inputs from the original store (exported by the original build)
    inputs = work / "inputs"
    inputs.mkdir()
    os.chmod(inputs, 0o777)
    ex = sh(["docker", "exec", "simlab-runner", "python", "-m", "simlab.interface.portable", "export", "--data-dir", "/data", "--run", a.run,
             "--out", f"/data/export-{uuid.uuid4().hex[:6]}"])
    rec["export"] = {"exit_code": ex.returncode, "stdout": ex.stdout[-800:], "stderr": ex.stderr[-800:]}
    exported = None
    for p in Path(a.data_dir).glob("export-*"):
        if (p / "experiment.json").exists() and json.loads((p / "recorded-result.json").read_text())["run_id"] == a.run:
            exported = p
    if exported is None:
        rec.update(result="FAIL" if a.commit else "REHEARSAL_FAILED", reason="could not export the recorded run (is simlab-runner up on the original data?)")
        (out / "fresh-checkout.json").write_text(json.dumps(rec, indent=1))
        return 1
    shutil.copytree(exported, inputs, dirs_exist_ok=True)
    shutil.rmtree(exported, ignore_errors=True)
    rec["declared_inputs"] = sorted(str(p.relative_to(inputs)) for p in inputs.rglob("*") if p.is_file())
    # 4. fresh run: empty data directory, inputs read-only, no network
    fresh = work / "data"
    fresh.mkdir()
    name = f"simlab-fresh-{uuid.uuid4().hex[:6]}"
    uid, gid = os.getuid(), os.getgid()
    run = ["docker", "run", "-d", "--name", name, "--network", "none", "--read-only", "--tmpfs", "/tmp:size=256m", "--user", f"{uid}:{gid}",
           "-e", "HOME=/tmp", "-e", "SIMLAB_IN_CONTAINER=1", "-e", f"SIMLAB_IMAGE_ID={rec['build']['image_id']}",
           "-e", f"SIMLAB_HOST_ID={os.uname().nodename}", "-v", f"{fresh}:/data", "-v", f"{inputs}:/inputs:ro", tag, "serve"]
    rec["fresh_container"] = {"command": run, "mounts": {"/data": "empty", "/inputs": "declared inputs, read-only"}, "network": "none"}
    sh(run)
    for _ in range(100):
        if (fresh / "runner.sock").exists():
            break
        time.sleep(0.1)
    imp = sh(["docker", "exec", name, "python", "-m", "simlab.interface.portable", "import", "--data-dir", "/data", "--dir", "/inputs"])
    sh(["docker", "rm", "-f", name])
    try:
        rec["reproduction"] = json.loads(imp.stdout)
    except json.JSONDecodeError:
        rec["reproduction"] = {"error": imp.stderr[-2000:]}
    comp = rec["reproduction"].get("comparison", {})
    same = all((rec["reproduction"].get("identical_content") or {"x": False}).values())
    ok = comp.get("equal") is True and same
    rec["wall_s"] = round(time.monotonic() - t0, 1)
    rec["result"] = ("PASS" if ok else "FAIL") if a.commit else ("REHEARSAL_REPRODUCED" if ok else "REHEARSAL_FAILED")
    rec["note"] = None if a.commit else "A rehearsal from an export of uncommitted work is not X1.6 evidence; X1.6 needs a clean clone of an owner commit."
    sh(["docker", "image", "rm", tag])
    (out / "fresh-checkout.json").write_text(json.dumps(rec, indent=1, default=str))
    shutil.rmtree(work, ignore_errors=True)
    print(json.dumps({k: rec.get(k) for k in ("mode", "result", "wall_s")} | {"comparison": comp, "identical_content": rec["reproduction"].get("identical_content")}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
