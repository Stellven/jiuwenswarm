#!/usr/bin/env python3
"""Plant known faults in a temporary copy and see that each is reported. The real files are never changed.

    python tools/so_selftest.py            # every case
    python tools/so_selftest.py A B        # only the cases whose name starts with A or B
    python tools/so_selftest.py --list

The cases are the faults an audit of these tools found on 2026-11-18, each planted again: a check that passed a
wrong description, a tool that wrote when it should have refused, a conclusion printed whatever the input. A case
passes when the tool reports the fault. Cases marked LIMIT are faults the tools are known not to find; they are run
so that the limit stays stated and a change in it is noticed. Exit 1 when a case does not behave as written here.

Groups: A the derivation and the system check, B the figures for a model on a machine and the back-test, C the node
level and the scorers.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
MUSE = "examples/systems/muse/"
SYS, COMP, MAN, KEPT, NODES, ASSIGN = (MUSE + x for x in ("system.yaml", "components.yaml", "_derive.yaml",
                                                         "_derive.kept.yaml", "nodes.yaml", "node-assignment.yaml"))
TARGET = "examples/specs/muse-spark-open-on-dgx-spark.target.yaml"
import so_run_all as current  # noqa: E402  the measurement and the back-test the figures use now

ENVFILE = "examples/given/env-" + current.ENVIRONMENT.split("/")[-1] + ".yaml"
EVIDENCE = "examples/knowledge/evidence-strata-on-spark-reported.yaml"
W = None                                                         # the temporary copy, set in main
BUDGET = [80.0]                                                  # which of the target's candidate budgets the figures use


def run(*a):
    r = subprocess.run([sys.executable, *a], cwd=W, capture_output=True, text=True, encoding="utf-8", env=ENV)
    return r.returncode, r.stdout + r.stderr


def docs(rel):
    return list(yaml.safe_load_all((W / rel).read_text(encoding="utf-8")))


def save(rel, ds):
    (W / rel).write_text("---\n".join(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=118) for d in ds), encoding="utf-8")


def edit(rel, fn):
    ds = docs(rel)
    fn(ds)
    save(rel, ds)


def text(rel, old, new, count=1):
    p = W / rel
    s = p.read_text(encoding="utf-8")
    assert old in s, f"selftest is out of date: {rel} no longer contains {old[:60]!r}"
    p.write_text(s.replace(old, new, count), encoding="utf-8")


def comp(ds, cid):
    return next(d for d in ds if d["id"] == cid)


def strata_file(needle):
    for p in sorted((W / "examples/systems/strata").glob("components-*.yaml")):
        if needle in p.read_text(encoding="utf-8"):
            return p.relative_to(W).as_posix()
    raise AssertionError(f"selftest is out of date: no Strata component file contains {needle[:60]!r}")


# ---- what a case expects ---------------------------------------------------------------------------------------

def check_blocks(needle=None):
    """The system check of the Muse design must end with blocking issues, and name the fault when `needle` is given."""
    def f():
        c, t = run("tools/so_check.py", "system", "sys/muse-on-spark")
        ok = c == 1 and "has blocking issues" in t and "Traceback" not in t and (needle is None or needle in t)
        return ok, next((x for x in reversed(t.splitlines()) if x.startswith("Conclusion")), t.strip()[-120:])
    return f


def derive_refuses():
    """The derivation must report problems and write nothing."""
    def f():
        before = {r: (W / r).read_bytes() for r in (SYS, COMP)}
        c, t = run("tools/so_derive.py", "examples/systems/muse")
        same = all((W / r).read_bytes() == b for r, b in before.items())
        return c == 1 and same and "nothing was written" in t and "Traceback" not in t, \
            next((x.strip() for x in t.splitlines() if "problems" in x), t.strip()[-120:])
    return f


def validate_fails(needle):
    def f():
        c, t = run("tools/so_check.py", "validate")
        return c == 1 and needle in t, next((x.strip()[:140] for x in t.splitlines() if needle in x), f"exit {c}")
    return f


def assess(*extra):
    c, t = run("tools/so_assess.py", "sys/muse-on-spark", "--spec", "spec/muse-spark-open-on-dgx-spark/target",
               "--environment", current.ENVIRONMENT, "--budget-gb", f"{BUDGET[0]:g}", "--backtest", current.BACKTEST, "--out", "runs/selftest",
               "--root", ".", *extra)
    p = W / "runs/selftest/assessment.md"
    return c, t, (p.read_text(encoding="utf-8") if p.exists() else "")


def assess_says(*needles, not_any=()):
    """The figures' output must contain every needle and none of `not_any`, without a traceback."""
    def f():
        c, t, md = assess()
        ok = "Traceback" not in t and all(n in md for n in needles) and not any(n in md for n in not_any)
        hit = next((x.strip()[:150] for x in md.splitlines() if needles and needles[0] in x), t.strip()[-150:])
        return ok, hit
    return f


def tool_fails(*cmd, needle):
    def f():
        c, t = run(*cmd)
        return c == 1 and needle in t and "Traceback" not in t, next((x.strip()[:150] for x in t.splitlines() if needle in x), f"exit {c}")
    return f


# ---- the faults ------------------------------------------------------------------------------------------------

PLANT = "Compute the router's 512 logits and choose 10 experts in each of 48 layers; the mtp draft head is configured here."
OTHER_WORDS = [
    "The router emits 512 scores per token and keeps the best 10.",
    "Geometry the kernels are built for: layers 48, experts per layer 512, picks per token 10.",
    "A 48-layer stack of 512-expert layers with top_k=10.",
    "Of the 512, the 10 with the highest scores are computed.",
    "All forty-eight layers route among five hundred and twelve experts.",
    "The expert weights are 50.3 GB and the lookup table is 28.8 GB, so both fit in host memory.",
    "There are 24.6 thousand experts (24 576) in all.",
    "Before layer 1, read the rows of the lookup table for the last tokens and keep their history.",
    "Carry the gated delta state and the sparse attention index of each layer from one token to the next.",
    "Tokens proposed ahead by the auxiliary prediction head are checked by the full model and accepted or rolled back.",
    "Counters: accepted_draft_tokens, n_drafts, verify_window_len, vram_free_bytes, gguf_shard_count, strata_engine_restarts, mtp_accept_rate.",
    "Same behaviour as StrataEngine and the strata_control package of the upstream project by Niko1221; ds4_session too.",
    "Started with -ngl 99 -c 4096 -t 8; reads native_experts.txt, engine.toml and run.yaml; calls cudaMemcpyAsync and uploadExpertSlot().",
    "The setting expert_cache_slots and the constant kMaxDraftRows in core::ExpertCache::admit decide the size.",
    "Reads sharded GGUFv3 files; windowed decoding; pinned host memory is copied to the second card's memory (card 0 holds the head); per-card budgets."]


def sampler_says(sentence):
    edit(COMP, lambda ds: comp(ds, "comp/muse/sampler").__setitem__("responsibility", sentence))


def a1a():
    sampler_says(PLANT)
    edit(SYS, lambda ds: ds[0].pop("derived_from"))


def a1b():
    sampler_says(PLANT)
    edit(SYS, lambda ds: [d.__setitem__("main_source", False) for d in ds[0]["derived_from"]])


def a1d():
    p = W / "examples/given/model-qwen3.8-flash-125b-a6b.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "\noperations: [unclosed\n", encoding="utf-8")


def a1e():
    m = W / MAN
    t = m.read_text(encoding="utf-8")
    i, j = t.index("source_only_terms:"), t.index("\ntimings:")
    m.write_text(t[:i] + t[j:], encoding="utf-8")
    edit(COMP, lambda ds: comp(ds, "comp/muse/sampler").setdefault("not_responsible_for", []).append(
        "GGUF shards of each pack in VRAM, page-locked, one verify window per card."))


def a2a():
    text(MAN, 'responsibility: "Turn the logits of the position being generated',
         'responsibility: "As in Strata, with --temp and the mtp draft head, for 10 of 512 experts. Turn the logits')


def a3():
    f = strata_file("id: comp/strata/launch-argument-resolver")
    ds = docs(f)
    comp(ds, "comp/strata/launch-argument-resolver")["responsibility"] += " Each token picks 10 of 512 experts (not if --evict)."
    save(f, ds)


def a5():
    edit(COMP, lambda ds: comp(ds, "comp/muse/sampler").setdefault("not_responsible_for", []).extend(OTHER_WORDS))


def a5_words():
    c, t = run("tools/so_leftovers.py", "sys/muse-on-spark")
    hit = sorted({int(x.split("[")[1].split("]")[0]) for x in t.splitlines() if x.startswith("- comp/muse/sampler  not_responsible_for[")})
    missed = [i + 1 for i in range(len(OTHER_WORDS)) if i not in hit]
    return len(hit) >= 12, f"the word patterns find {len(hit)} of {len(OTHER_WORDS)} source facts said in other words; not found: sentences {missed}"


def a8():
    f = strata_file("A slot is reported as holding an expert only after that expert's bytes have fully arrived.")
    text(f, "A slot is reported as holding an expert only after that expert's bytes have fully arrived.",
         "A slot may be reported as holding an expert before that expert's bytes have arrived.")


def a13a():
    p = W / COMP
    p.write_text(p.read_text(encoding="utf-8") + "---\nkind: component\nid: comp/muse/sampler\nsystem: sys/muse-on-spark\ntitle: x\n"
                 "role: drafter\nresponsibility: A second sampler.\nruns: [per_step]\nsources: [{ref: x, basis: proposal}]\n", encoding="utf-8")


def a14a():
    def f(ds):
        a, b = comp(ds, "comp/muse/setup"), comp(ds, "comp/muse/run-config-generator")
        a["parent"] = b["id"]
        b.setdefault("parts", []).append(a["id"])
    edit(COMP, f)
    edit(SYS, lambda ds: ds[0]["components"].remove("comp/muse/setup"))


def a14d():
    p = W / COMP
    p.write_text(p.read_text(encoding="utf-8") + "---\nkind: component\nid: comp/muse/orphan\nsystem: sys/muse-on-sparkk\ntitle: x\n"
                 "role: drafter\nresponsibility: A part of no system.\nruns: [per_step]\nsources: [{ref: x, basis: proposal}]\n", encoding="utf-8")


def a15a():
    def f(ds):
        fl = next(x for x in ds[0]["flows"] if x["carries"]["content"] == "weights" and x["carries"].get("refs"))
        fl["carries"]["refs"] = ["attention_kv"]
    edit(SYS, f)


def all_needs_slow(ds):
    for d in ds:
        for n in d.get("needs_resources", []) or []:
            n["resource"] = "slow_memory"


def empty_design(ds):
    for d in ds:
        d["responsibility"] = "Does nothing."
        d.pop("decisions", None)


def b_design():
    c, t, base = assess()
    edit(COMP, empty_design)
    c2, t2, md = assess()
    rows = lambda x: [r for r in x.splitlines() if r.startswith("|") and any(ch.isdigit() for ch in r) and "comp/muse" not in r
                      and "decision" not in r.lower()]
    said = "typed from text the design no longer has" in md
    return rows(base) == rows(md) and said and "not an assessment of the design" in md.replace("\n", " "), \
        "every figure is unchanged, and the output says the node level was typed from text the design no longer has"


def storage_too_small():
    p = W / ENVFILE
    t = p.read_text(encoding="utf-8")
    d = json.loads(t[t.index("{"):])
    for s in d.get("statements", []):
        if s.get("property") == "capacity_reported_by_os" and s.get("unit") == "GB" and s["value"] > 1000:
            s["value"] = 100                              # less than the model files themselves
    p.write_text(t[:t.index("{")] + json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def budget(gb):
    def f():
        def g(ds):
            r = next(x for x in ds[0]["contract"]["requirements"] if x.get("quantity") == "memory_budget")
            r["candidates"][-1]["value"] = gb                    # the candidate the figures are computed for
        edit(TARGET, g)
        BUDGET[0] = float(gb)
    return f


def no_cache_node():
    p = W / NODES
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    d["nodes"] = [n for n in d["nodes"] if n.get("type") != "expert-cache"]
    p.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=118), encoding="utf-8")


def speeds_times_ten():
    def scale(x):
        if isinstance(x, dict):
            for k, v in list(x.items()):
                if isinstance(v, (int, float)) and not isinstance(v, bool) and 20 < v < 100:
                    x[k] = v * 10
                else:
                    scale(v)
        elif isinstance(x, list):
            for v in x:
                scale(v)
    edit(EVIDENCE, scale)


def cache_is_a_sampler():
    edit(COMP, lambda ds: comp(ds, "comp/muse/expert-cache").__setitem__(
        "responsibility", "Draw the next token from the output distribution with a seeded random generator. Holds no weights."))


def example_refuses(needle):
    def f():
        before = (W / NODES).read_bytes()
        c, t = run("tools/so_nodetypes.py", "example", "muse-on-spark")
        return c == 1 and (W / NODES).read_bytes() == before and needle in t and "nothing written" in t, \
            next((x.strip()[:150] for x in t.splitlines() if "PROBLEM" in x), f"exit {c}")
    return f


def all_readers_wrong():
    for r in ("rater-a", "rater-b"):
        p = W / f"validation/round9/{r}.yaml"
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        for a in d["assignments"]:
            a["node_type"] = "scoring"
        p.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")


def all_open():
    for r in ("reader-a", "reader-b"):
        p = W / f"validation/selection-final/{r}.yaml"
        t = p.read_text(encoding="utf-8")
        for word in ("not_needed", "needed"):
            t = t.replace(f"answer: {word}", "answer: open")
        p.write_text(t, encoding="utf-8")


def wrong_own_number():
    sampler_says("Turn the logits of the position being generated into one token id; the model has 60 layers of 128 experts.")
    text(MAN, 'responsibility: "Turn the logits of the position being generated into one token id by a fixed chain: logit bias, penalties, top-k, top-p, min-p, temperature, pick."',
         'responsibility: "Turn the logits of the position being generated into one token id; the model has 60 layers of 128 experts."')


def own_number_passes():
    c, t = run("tools/so_check.py", "system", "sys/muse-on-spark")
    return c == 0, "a number of this engine's own model written wrongly (60 layers, 128 experts) is not found: no rule compares the design's numbers with its model"


CASES = [
    # name, what is planted, how, what must happen
    ("A01", "a source sentence in a component, and the system no longer says it is derived", a1a, check_blocks("cannot be checked against the source")),
    ("A02", "a source sentence, and no source marked as the main one", a1b, check_blocks("cannot be checked against the source")),
    ("A03", "the source model's description cannot be read", a1d, check_blocks("YAML could not be parsed")),
    ("A04", "the same, for the derivation", a1d, derive_refuses()),
    ("A05", "the hand-listed terms deleted, and a sentence that uses them", a1e, check_blocks()),
    ("A06", "a source sentence written by hand into the derivation list", a2a, derive_refuses()),
    ("A07", "a source text changed after it was read and kept", a3, derive_refuses()),
    ("A08", "the same, for the system check", a3, check_blocks("deriving again from the derivation list gives a problem")),
    ("A09", "a generated component edited by hand", lambda: edit(COMP, lambda ds: comp(ds, "comp/muse/telemetry").__setitem__(
        "responsibility", "Decide which experts are computed.")), check_blocks("the file differs from what the derivation list writes now")),
    ("A10", "fifteen source facts said in other words", a5, check_blocks()),
    ("A11", "source words in a component's title", lambda: edit(COMP, lambda ds: comp(ds, "comp/muse/sampler").__setitem__(
        "title", "Strata's MTP drafter reads GGUF shards into VRAM")), check_blocks("title")),
    ("A12", "a kept invariant reversed in the source", a8, check_blocks("no item of the source has that text now")),
    ("A13", "`as: Adapted` in the derivation list", lambda: text(MAN, "  - from: comp/strata/sampler\n    as: adapted",
                                                               "  - from: comp/strata/sampler\n    as: Adapted"), derive_refuses()),
    ("A14", "the target machine changed to another one", lambda: edit(SYS, lambda ds: ds[0]["targets"][0].__setitem__(
        "hardware", "hw/pc-12g-64g")), check_blocks()),
    ("A15", "every component asks for a kind of memory this machine does not have", lambda: edit(COMP, all_needs_slow),
     check_blocks("has no such resource")),
    ("A16", "the system declares no state names", lambda: edit(SYS, lambda ds: ds[0]["declares"].pop("states")),
     check_blocks("these names cannot be checked")),
    ("A17", "a component derived from itself", lambda: edit(COMP, lambda ds: comp(ds, "comp/muse/sampler")["derived_from"].append(
        {"component": "comp/muse/sampler", "carried_as": "adapted", "adaptation": "from itself, changed in nothing at all"})),
     check_blocks("a component of this same system")),
    ("A18", "every reason for not carrying a component emptied", lambda: edit(SYS, lambda ds: [x.__setitem__("note", "")
     for d in ds[0]["derived_from"] for x in d.get("not_carried", [])]), check_blocks("the reason is not written in words")),
    ("A19", "two components with one id", a13a, check_blocks("duplicate id")),
    ("A20", "a description whose `kind` is misspelled", lambda: text(ENVFILE, '"kind": "environment"', '"kindd": "environment"'),
     validate_fails("it was not read in")),
    ("A21", "two components each other's parent, off the top list", a14a, check_blocks("it cannot be reached")),
    ("A22", "a component whose `system` is misspelled", a14d, check_blocks("there is no such system")),
    ("A23", "a flow of weights that carries a model state", a15a, check_blocks("is model_state in the model description")),
    ("A24", "all flows removed", lambda: edit(SYS, lambda ds: ds[0].__setitem__("flows", [])), check_blocks("no flow is written at all")),
    ("A25", "a component uses a mechanism the system does not list", lambda: edit(COMP, lambda ds: comp(
        ds, "comp/muse/expert-dispatch").__setitem__("mechanisms", ["mech/route-tail-skip"])), check_blocks("which the system's mechanisms does not list")),
    ("A26", "the target's hardware names a model", lambda: edit(SYS, lambda ds: ds[0]["targets"][0].__setitem__(
        "hardware", "model/muse-spark-open")), check_blocks("is not a hardware description")),
    ("A27", "a model selects an operation that does not exist", lambda: text(
        "examples/given/model-muse-spark-open.yaml", "selects: {operation: expert_ffn,", "selects: {operation: no_such_operation,"),
     validate_fails("no_such_operation")),
    ("B01", "the design emptied: every responsibility 'Does nothing.', all decisions removed", lambda: None, b_design),
    ("B02", "storage reported as 100 GB, less than the model files", storage_too_small,
     assess_says("**No**: the prepared files do not fit on storage", not_any=["**Yes** on memory and storage"])),
    ("B03", "a memory budget of 600 GB, above what the machine can give", budget(600), assess_says("**No**: the budget")),
    ("B04", "a memory budget of 22 GB, too small for anything", budget(22), assess_says("**No**: no row of the memory plan fits")),
    ("B05", "the design has no node of type expert-cache", no_cache_node, assess_says("has no node of type `expert-cache`")),
    ("B06", "the speeds the existing engine reports, multiplied by ten", speeds_times_ten, tool_fails(
        "tools/so_backtest.py", "sys/strata", "--hardware", "hw/dgx-spark", "--evidence", "evidence/strata-on-spark/reported",
        "--out", "runs/selftest-bt", "--root", ".", needle="FAIL")),
    ("C01", "a component's responsibility changed to something its node type cannot be", cache_is_a_sampler,
     example_refuses("the responsibility has changed since it was read")),
    ("C02", "the same, for the check of the node levels", cache_is_a_sampler, tool_fails("tools/so_nodetypes.py", "check", needle="problems")),
    ("C03", "a node type that does not exist", lambda: text(ASSIGN, "type: expert-cache", "type: expert-warehouse"),
     example_refuses("which the draft does not have")),
    ("C04", "both readers give one wrong type for every part", all_readers_wrong, tool_fails(
        "tools/so_nodetypes_experiments.py", "classify", "validation/round9/parts.key.yaml", "round9", needle="RESULT: FAIL. 4 of 6")),
    ("C05", "every selection answer set to open", all_open, tool_fails(
        "tools/so_nodetypes_experiments.py", "selection", "selection-final", needle="RESULT: FAIL. 4 of 4")),
    ("LIMIT1", "fifteen source facts said in other words: how many the word patterns alone find", a5, a5_words),
    ("LIMIT2", "a number of this engine's own model written wrongly", wrong_own_number, own_number_passes),
]


def main():
    global W
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if "--list" in args:
        for name, what, _, _ in CASES:
            print(f"{name:7} {what}")
        return 0
    chosen = [c for c in CASES if not args or any(c[0].startswith(a) for a in args)]
    with tempfile.TemporaryDirectory() as tmp:
        W = pathlib.Path(tmp) / "system-ontology"
        shutil.copytree(ROOT, W, ignore=shutil.ignore_patterns("__pycache__", ".git*", "muse-assessment-0[1-4]"))
        keep = pathlib.Path(tmp) / "keep"
        for sub in ("examples", "validation"):
            shutil.copytree(W / sub, keep / sub)
        c, t = run("tools/so_check.py", "system", "sys/muse-on-spark")
        if c != 0:
            print("the Muse design does not pass its check before any fault is planted; the cases would show nothing:")
            print(t.strip()[-300:])
            return 1
        wrong = 0
        for name, what, plant, expect in chosen:
            try:
                plant()
                ok, seen = expect()
            except AssertionError as e:
                ok, seen = False, str(e)
            except Exception as e:                               # a broken case is a failure of the self-test, said as such
                ok, seen = False, f"the case itself failed: {type(e).__name__}: {e}"
            for sub in ("examples", "validation"):
                shutil.rmtree(W / sub)
                shutil.copytree(keep / sub, W / sub)
            BUDGET[0] = 80.0
            limit = name.startswith("LIMIT")
            mark = ("known limit" if ok else "LIMIT CHANGED") if limit else ("reported" if ok else "NOT REPORTED")
            wrong += not ok
            print(f"{name:7} {mark:13} {what}\n        {str(seen)[:170]}")
        n_lim = sum(1 for c in chosen if c[0].startswith("LIMIT"))
        print(f"\n{len(chosen) - n_lim} faults planted, {n_lim} known limits shown; {wrong} did not behave as written")
        return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
