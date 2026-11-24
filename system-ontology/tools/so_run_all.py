#!/usr/bin/env python3
"""Run everything in this directory from start to finish, in the order the steps depend on each other.

    python tools/so_run_all.py                 # every step, then the self-test (about ten minutes)
    python tools/so_run_all.py --no-selftest   # every step, without planting faults (about two minutes)

One command for: checking every description, deriving the Muse design, the node levels, the scorers of the stored
reader answers, the revised document, the back-test, the figures for the Muse model, the generated documents, and the
self-test that plants known faults in a temporary copy.

What the result means. Each step ends in one of these:
  ok            the tool ran and found nothing.
  open          the tool ran and reports something that is known and recorded in `validation/open-findings.yaml`,
                with the same result line as recorded: a target the project has not finished setting, a pass mark
                the stored reader answers do not meet. Not a failure of the run; listed at the end.
  CHANGED       the tool reports something else than what is recorded as open, or reports nothing where something is
                recorded. The record or the description has to be brought in line.
  BROKEN        the tool stopped with an error, or reported a problem that is not recorded as open.
  skipped       the step needs the repository this directory is part of (the factory's design package) and it was
                not found; said, not hidden.
After the steps, every file is compared with what it was before the run. The steps regenerate files; when the inputs
have not changed, nothing may differ. A file that differs was out of date (now it is not), or a tool is not
repeatable. Line endings are not counted as a difference.

Exit 0 only when no step is BROKEN or CHANGED, no file differs, and the self-test, when run, behaves as written.
"""
import hashlib
import os
import pathlib
import subprocess
import sys
import time

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
# The runs that hold the current figures. A new run gets a new number here and in METHOD-assessment.md.
BACKTEST = "runs/strata-backtest-02"
# The target names two candidate memory budgets and has not chosen; the figures are computed for each.
ASSESSMENT = "runs/muse-assessment-08-budget-80"
ASSESSMENT_128 = "runs/muse-assessment-08-budget-128"
# The same figures for the model at the precision it was published in, which the method document works through.
PUBLISHED_MODEL = "model/muse-spark-open"
PUBLISHED_ASSESSMENT = "runs/muse-assessment-07"
# The measurement of the machine the figures use: the latest one taken on the DGX Spark itself.
ENVIRONMENT = "env/dgx-spark-measured-20261119"
OPEN = ROOT / "validation" / "open-findings.yaml"

# (id, what it does, command, needs the repository)
STEPS = [
    ("validate", "every description is well formed and its references exist", "tools/so_check.py validate", False),
    ("derive-muse", "derive the Muse design from Strata", "tools/so_derive.py examples/systems/muse", False),
    ("check-muse", "check the Muse design", "tools/so_check.py system sys/muse-on-spark", False),
    ("check-strata", "check the description of Strata", "tools/so_check.py system sys/strata", False),
    ("check-ds4", "check the description of ds4", "tools/so_check.py system sys/ds4", False),
    ("target-muse", "check the target the Muse engine is judged on", "tools/so_check.py check spec/muse-spark-open-on-dgx-spark/target", False),
    ("words-muse", "word patterns of the source engine in the Muse design", "tools/so_leftovers.py sys/muse-on-spark --count", False),
    ("types-draft", "write the node types draft from its sources", "tools/so_nodetypes.py thin", False),
    ("nodes-strata", "Strata's node level", "tools/so_nodetypes.py example strata", False),
    ("nodes-muse-read", "Muse nodes whose text changed since their type was read", "tools/so_nodetypes.py repin muse-on-spark", False),
    ("nodes-muse", "the Muse design's node level", "tools/so_nodetypes.py example muse-on-spark", False),
    ("nodes-check", "check the node levels against the draft", "tools/so_nodetypes.py check", False),
    ("score-classification-first", "score: readers assign parts to types, first run", "tools/so_nodetypes_experiments.py classify validation/round8/parts.key.yaml round8", False),
    ("score-classification", "score: readers assign parts to types, confirmation", "tools/so_nodetypes_experiments.py classify validation/round9/parts.key.yaml round9", False),
    ("score-selection-first", "score: which types an engine needs, first run", "tools/so_nodetypes_experiments.py selection selection", False),
    ("score-selection", "score: which types an engine needs, confirmation", "tools/so_nodetypes_experiments.py selection selection-final", False),
    ("score-choices", "score: which choices several engines decide", "tools/so_nodetypes_experiments.py recurrence", False),
    ("score-heldout", "score: the engine the types were not drawn from", "tools/so_nodetypes_validate.py heldout", False),
    ("document", "write the revised document", "tools/so_nodetypes.py doc", False),
    ("back-test", "compare the upper bound with an existing engine's reported speeds", f"tools/so_backtest.py sys/strata --hardware hw/dgx-spark --evidence evidence/strata-on-spark/reported --out {BACKTEST} --root .", False),
    ("figures", "figures for the Muse model files on DGX Spark, within 80 GB", f"tools/so_assess.py sys/muse-on-spark --spec spec/muse-spark-open-on-dgx-spark/target --environment {ENVIRONMENT} --budget-gb 80 --backtest {BACKTEST} --out {ASSESSMENT} --root .", False),
    ("figures-128", "the same within the other candidate budget, 128 GB", f"tools/so_assess.py sys/muse-on-spark --spec spec/muse-spark-open-on-dgx-spark/target --environment {ENVIRONMENT} --budget-gb 128 --backtest {BACKTEST} --out {ASSESSMENT_128} --root .", False),
    ("figures-published-precision", "the same for the model at its published precision, the method document's worked example", f"tools/so_assess.py sys/muse-on-spark --spec spec/muse-spark-open-on-dgx-spark/target --environment {ENVIRONMENT} --model {PUBLISHED_MODEL} --budget-gb 80 --backtest {BACKTEST} --out {PUBLISHED_ASSESSMENT} --root .", False),
    ("documents", "the generated reference, dictionary and system documents", "tools/so_docs.py", False),
    ("intake-score", "score: what an Intent pass took up of the ontology", "tools/so_intake_trial.py score", False),
    ("intake-A", "intake trial A: quotes to positions, validated against the factory's schema", "tools/so_intake_trial.py resolve A", True),
    ("intake-B", "intake trial B", "tools/so_intake_trial.py resolve B", True),
    ("intake-C", "intake trial C", "tools/so_intake_trial.py resolve C", True),
]


def in_repository():
    return any((b / "docs" / "architecture" / "design-package" / "reference" / "schemas").is_dir() for b in [ROOT, *ROOT.parents])


def snapshot():
    """A checksum of every file, line endings left out of the comparison."""
    out = {}
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT).as_posix()
        if p.is_file() and "__pycache__" not in rel and not rel.startswith(".git"):
            out[rel] = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return out


def result_line(text):
    lines = [x.strip() for x in text.strip().splitlines() if x.strip()]
    for key in ("Conclusion", "RESULT", "PASS:", "FAIL:"):
        hit = [x for x in lines if x.startswith(key) or f" {key}" in x[:12]]
        if hit:
            return hit[-1]
    return lines[-1] if lines else ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    selftest = "--no-selftest" not in sys.argv
    recorded = (yaml.safe_load(OPEN.read_text(encoding="utf-8")) or {}) if OPEN.exists() else {}
    repo = in_repository()
    before = snapshot()
    rows, bad, used = [], 0, set()
    for sid, what, cmd, needs_repo in STEPS:
        if needs_repo and not repo:
            rows.append((sid, "skipped", what, "needs the repository's design package, which was not found from this directory"))
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable] + cmd.split(), cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=ENV)
        out = r.stdout + r.stderr
        line = result_line(out)
        entry = recorded.get(sid)
        if "Traceback (most recent call last)" in out or r.returncode not in (0, 1):
            state, line = "BROKEN", (out.strip().splitlines() or ["no output"])[-1]
        elif r.returncode == 0:
            state = "CHANGED" if entry else "ok"
            if entry:
                line = f"recorded as open ({entry['result']}), and the tool now reports nothing: remove the entry from validation/open-findings.yaml"
        elif entry and entry["result"] == line:
            state = "open"
            used.add(sid)
        elif entry:
            state, line = "CHANGED", f"now: {line} | recorded: {entry['result']}"
        else:
            state = "BROKEN"
        bad += state in ("BROKEN", "CHANGED")
        rows.append((sid, state, what, line))
        print(f"{state:8} {sid:28} {time.time() - t0:4.0f}s  {line[:150]}", flush=True)
    for sid, state, what, line in rows:
        if state == "skipped":
            print(f"{state:8} {sid:28}        {line}")
    for sid in sorted(set(recorded) - {s[0] for s in STEPS}):
        bad += 1
        print(f"CHANGED  {sid:28}        validation/open-findings.yaml records a finding for a step that does not exist")

    after = snapshot()
    differ = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    print(f"\nfiles that differ from before the run: {len(differ)}")
    for k in differ:
        print(f"  {'new ' if k not in before else 'gone' if k not in after else 'changed'}  {k}")
    if differ:
        print("  The steps regenerate files and the inputs did not change, so nothing should differ. These files were out of\n"
              "  date before the run and are current now, or a tool does not give the same output twice. Run again: a\n"
              "  second run that still lists files means a tool is not repeatable.")

    st = None
    if selftest:
        print("\nself-test: known faults planted in a temporary copy (tools/so_selftest.py)", flush=True)
        r = subprocess.run([sys.executable, "tools/so_selftest.py"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=ENV)
        st = r.returncode
        text = (r.stdout + r.stderr).strip().splitlines()
        for x in text[:-1]:
            if "NOT REPORTED" in x or "LIMIT CHANGED" in x or "known limit" in x:
                print("  " + x[:170])
        print("  " + (text[-1] if text else "no output"))

    print("\nopen and recorded (not failures of this run):")
    for sid, state, what, line in rows:
        if state == "open":
            e = recorded[sid]
            print(f"  {sid}: {line}\n      {e['why']}  [{e['whose']}]")
    if not any(s == "open" for _, s, _, _ in rows):
        print("  none")
    n = {s: sum(1 for r in rows if r[1] == s) for s in ("ok", "open", "CHANGED", "BROKEN", "skipped")}
    ok = not bad and not differ and st in (None, 0)
    print(f"\nRESULT: {'RAN THROUGH' if ok else 'NOT CLEAN'}. {n['ok']} steps ok, {n['open']} open as recorded, {n['CHANGED']} changed, "
          f"{n['BROKEN']} broken, {n['skipped']} skipped; {len(differ)} files differ; self-test "
          + ("not run" if st is None else "as written" if st == 0 else "NOT as written"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
