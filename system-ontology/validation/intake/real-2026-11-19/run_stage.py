"""Run one stage of the repository's portable capsule runtime (the released Intent m1-8 or Requirements m1-9) on one
query, with the Codex command line as the model for both the worker and the verifier.

    python -B run_stage.py intent A
    python -B run_stage.py requirements A      # needs the delivered Intent of A

The only difference from `python -m jiuwenswarm.capsule_runtime ... invoke` is the time allowed to the model
command: the command-line default is 300 s, here it is the wall time the capsule itself declares (420 s for Intent,
180 s for Requirements), which the runtime enforces in any case.
"""
import json
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, r"<repo>")
from jiuwenswarm.capsule_runtime.engine import Runtime  # noqa: E402
from jiuwenswarm.capsule_runtime.verifier_backends import CommandModel  # noqa: E402

WALL = {"intent": 420, "requirements": 180}


def main():
    stage, v = sys.argv[1], sys.argv[2]
    cid = "research." + stage
    if stage == "intent":
        inputs = json.loads((HERE / f"intent_in_{v}.json").read_text(encoding="utf-8"))
    else:
        inputs = json.loads((HERE / f"intent_in_{v}.json").read_text(encoding="utf-8"))
        res = json.loads((HERE / f"intent_{v}_result.json").read_text(encoding="utf-8"))
        if res["status"] != "delivered":
            print(f"{v}: the Intent was not delivered ({res['status']}); the Requirements stage is not run")
            return 4
        inputs["intent"] = res["outputs"]["intent"]
    t = WALL[stage] - 5
    os.environ["CODEX_TIMEOUT"] = str(t - 5)
    cmd = lambda role: CommandModel([sys.executable, "-B", str(HERE / "codex_call.py"), f"{role}-{stage}-{v}"], timeout=t)
    rt = Runtime([], worker_model=cmd("worker"))
    adm = rt.admit(cid)
    if not adm["passed"]:
        print("not admitted:", adm["failures"])
        return 1
    t0 = time.time()
    result = rt.invoke(cid, inputs, require_admission=True, verifier_model=cmd("verifier"), require_semantic=True)
    (HERE / f"{stage}_{v}_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    rc = result["receipt"]
    print(f"{stage} {v}: {result['status']} in {time.time() - t0:.0f} s | halt {json.dumps(rc.get('halt'), ensure_ascii=False)[:300]} | "
          f"checks {[(c['check_id'], c['outcome']) for c in rc.get('checks', [])]}")
    return 0 if result["status"] == "delivered" else 2


if __name__ == "__main__":
    sys.exit(main())
