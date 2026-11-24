#!/usr/bin/env python3
"""Show that the checker catches a mistake, without touching the real files.

    python tools/so_demo.py list
    python tools/so_demo.py two-owners

Each fault is applied to a temporary copy of the descriptions. The checker is run on the copy before and after, and
only the issues that the fault added are printed. The real files are never changed.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent


def edit(root, rel, fn):
    p = root / rel
    docs = list(yaml.safe_load_all(p.read_text(encoding="utf-8")))
    fn(docs)
    p.write_text("---\n".join(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=118) for d in docs), encoding="utf-8")


def budget_candidate(change):
    """A change to the last candidate of the memory budget: the target carries its budget as candidates until the
    project chooses one."""
    def fault(root):
        def f(docs):
            r = next(x for x in docs[0]["contract"]["requirements"] if x["id"] == "c-mem")
            change(r["candidates"][-1] if r.get("candidates") else r)
        edit(root, "examples/specs/muse-spark-open-on-dgx-spark.target.yaml", f)
    return fault


def over_machine(c):
    c["value"] = 600


def gpu_pool(c):
    c["value"], c["pool"] = 12, "gpu_memory"


def forget_component(root):
    def f(docs):
        for dv in docs[0]["derived_from"]:
            dv["not_carried"] = [x for x in dv.get("not_carried", []) if not x["component"].endswith("/ngram-reader")]
    edit(root, "examples/systems/muse/system.yaml", f)


def two_owners(root):
    def f(docs):
        c = next(d for d in docs if d["id"].endswith("/expert-dispatch"))
        c.setdefault("state", {}).setdefault("owns", []).append("residency_table")
    edit(root, "examples/systems/muse/components.yaml", f)


def dangling_flow(root):
    def f(docs):
        docs[0]["flows"][5]["receiver"] = "comp/strata/does-not-exist"
    edit(root, "examples/systems/strata/system.yaml", f)


def unperformed_operation(root):
    def f(docs):
        c = next(d for d in docs if d["id"].endswith("/expert-router"))
        c.pop("performs", None)
    edit(root, "examples/systems/muse/components.yaml", f)


FAULTS = {
    "budget-600": (budget_candidate(over_machine), ["check", "spec/muse-spark-open-on-dgx-spark/target"],
                   "Set a candidate for the Muse memory budget to 600 GB, on a machine with 128 GB."),
    "gpu-memory-pool": (budget_candidate(gpu_pool), ["check", "spec/muse-spark-open-on-dgx-spark/target"],
                        "State a candidate budget as 12 GB of GPU memory, on a machine with one unified pool."),
    "forget-component": (forget_component, ["system", "sys/muse-on-spark"],
                         "Remove the line saying why Strata's n-gram reader was not carried into the Muse design."),
    "two-owners": (two_owners, ["system", "sys/muse-on-spark"],
                   "Let a second Muse component claim to own the cache's residency table."),
    "dangling-flow": (dangling_flow, ["system", "sys/strata"],
                      "Point one of Strata's flows at a component that does not exist."),
    "unperformed-operation": (unperformed_operation, ["system", "sys/muse-on-spark"],
                              "Take the routing operation away from the Muse expert router, so no component performs it."),
}


def issues(root, cmd):
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "so_check.py"), "--root", str(root)] + cmd,
                         capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}).stdout
    found, lines = [], out.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s[:1].isdigit() and ". [" in s[:8]:
            found.append((s.split(". ", 1)[1], lines[i + 1].strip() if i + 1 < len(lines) else ""))
    verdict = next((l for l in reversed(lines) if l.startswith("Conclusion")), "")
    return found, verdict


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    if sys.argv[1] == "list":
        for name, (_, cmd, text) in FAULTS.items():
            print(f"{name:24} {text}")
        return 0
    name = sys.argv[1]
    if name not in FAULTS:
        print(f"unknown fault '{name}'; run `python tools/so_demo.py list`")
        return 2
    fn, cmd, text = FAULTS[name]
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for sub in ("ontology", "examples"):
            shutil.copytree(ROOT / sub, root / sub)
        before, v0 = issues(root, cmd)
        fn(root)
        after, v1 = issues(root, cmd)
    added = [x for x in after if x not in before]
    print(f"Fault: {text}")
    print(f"Check: so_check.py {' '.join(cmd)}   (on a temporary copy; the real files are untouched)\n")
    print(f"Before: {v0}")
    print(f"After:  {v1}\n")
    if not added:
        print("The checker reported nothing new. This fault is NOT caught.")
        return 1
    print(f"New issues the checker reported ({len(added)}):")
    for head, detail in added:
        print(f"  - {head}\n      {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
