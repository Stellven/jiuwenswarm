#!/usr/bin/env python3
"""Compare the assessment's memory-bandwidth upper bound with an engine that exists.

    python tools/so_backtest.py sys/strata --hardware hw/dgx-spark --evidence evidence/strata-on-spark/reported \
        --out runs/strata-backtest-02

tools/so_assess.py gives one figure that is an upper bound that needs no assumption about how the experts are used: memory bandwidth divided by
the bytes one token surely reads, per pass over the weights, for one sequence. This tool computes that figure the same
way (so_assess.model_facts) for an existing engine's model on a machine where its project reports speeds, and checks
it against them: every reported speed per pass must be at or below it. It prints PASS or FAIL and exits 1 on FAIL,
2 when the check cannot be made. It also adds up the memory the engine's description accounts for. The measurements
are the project's; nothing is adjusted to make the figures agree.
"""
import argparse
import json
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import so_check as sc  # noqa: E402
from so_assess import model_facts, fmt, described_notes  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
GB = 1e9
CONDITION_WRITTEN = "2026-11-18"


def num(x, digits=2):
    """A ratio or speed at fixed precision, or at two significant digits when that would print it as zero."""
    return f"{x:.{digits}f}" if abs(x) >= 10 ** -digits or x == 0 else f"{x:.2g}"


def pass_range(v):
    """Tokens per pass as (fewest, most) from a number or a text such as '2.4 to 3.2'."""
    if isinstance(v, (int, float)):
        return float(v), float(v)
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(v))]
    return (min(nums), max(nums)) if nums else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system")
    ap.add_argument("--hardware", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--root", type=pathlib.Path, default=ROOT)
    args = ap.parse_args()
    root = args.root.resolve()
    ws = sc.Workspace(root)
    system, ev = ws.objects[args.system], ws.objects[args.evidence]
    target = next((t for t in system["targets"] if t["hardware"] == args.hardware), None)
    if target is None:
        raise SystemExit(f"`{args.system}` has no target on `{args.hardware}`")
    model, hw, spec = ws.objects[target["model"]], ws.objects[args.hardware], ws.objects[target["spec"]]
    if ev["measured_under"]["model"] != model["id"]:
        raise SystemExit(f"the evidence is for `{ev['measured_under']['model']}`, the description's target for `{model['id']}`")
    env = ws.objects[ev["measured_under"]["environment"]]
    entries = {e["component_ref"]: e for e in spec["composition"]["components"] if e.get("component_ref")}
    interface = spec.get("interface") if isinstance(spec.get("interface"), dict) else {}
    modality = (interface.get("input") or {}).get("modality") if isinstance(interface.get("input"), dict) else None
    modality = None if sc.is_unset(modality) else modality

    nodes_path = ws.files[system["id"]].parent / "nodes.yaml"
    nodes = yaml.safe_load(nodes_path.read_text(encoding="utf-8")).get("nodes", []) if nodes_path.exists() else None

    pool = next(p for p in hw["memory_pools"] if p["kind"] in ("unified_ram", "vram"))
    bw = pool["properties"]["bandwidth"]["value"]
    mem_rate = bw * GB
    alloc = next((sc.to_bytes(a) for a in env.get("allocatable", []) if a["pool"] == pool["id"]), None)

    drafting = ev["results"].get("drafting") or {}
    tpp = pass_range(drafting.get("tokens_per_pass")) if drafting.get("tokens_per_pass") is not None else None
    if tpp:
        tpp_text = (f"{drafting['tokens_per_pass']} tokens per pass, from the evidence ({drafting.get('source', 'no source')}"
                    + (f"; {drafting['note'].rstrip('.')}" if drafting.get("note") else "") + ")")
    elif nodes is not None and not any(n.get("type") == "draft-verification" or "draft-verification" in (n.get("also") or [])
                                       for n in nodes):
        tpp = (1.0, 1.0)
        tpp_text = "one token per pass: the evidence gives no figure and the description has no node of type `draft-verification`"
    else:
        tpp_text = "not known: the evidence gives no tokens per pass and the description may check drafted tokens"

    L, rows_json = [], []
    add = L.append
    add(f"# Back-test of the memory-bandwidth upper bound: {system.get('title', system['id'])} on `{hw['id']}`\n")
    own = ev["measured_under"].get("status") == "measured"       # measured here, or taken from the project's documents
    said = "measured" if own else "reported"
    add(f"Description `{system['id']}`, its spec `{spec['id']}`, model `{model['id']}`, against "
        + (f"what I measured (`{ev['id']}`, {ev['measured_under'].get('source', '')}). I ran the engine. "
           f"{ev['measured_under'].get('note', '')}\n" if own else
           f"what the project itself reports (`{ev['id']}`, {ev['measured_under'].get('source', '')}). The measurements are "
           f"the project's; I did not run the engine.\n"))
    add("**What is compared.** The one figure of tools/so_assess.py that is an upper bound that needs no assumption about how the experts are used: "
        "memory bandwidth divided by the bytes one token surely reads, per pass over the weights, for one sequence. It is "
        "computed by the same function as in the assessment (`so_assess.model_facts`), so the bytes a token reads are "
        "defined the same way: the routed experts, every weight the description says each token reads in full, one row of "
        "the embedding table, and nothing whose per-token amount the description does not give. The engine reports tokens "
        "per second; its speed per pass over the weights is its speed divided by the tokens it produces per pass"
        + (", which the evidence gives as more than one, so the two differ." if tpp and tpp[1] > 1 else
           ", which is one here, so the two are the same." if tpp else ", which is not known here.") + "\n")
    add(f"**Pass condition** (added to this program on {CONDITION_WRITTEN}, after the result of its first run, Strata on "
        f"`hw/dgx-spark` in `runs/strata-backtest-01`, was known; that run had no condition and could not fail): every "
        f"{said} speed divided by the fewest tokens per pass the evidence gives is at or below the bound of its weight "
        f"pack. PASS if so, FAIL otherwise. A speed below the bound does not count against it: an upper bound says nothing "
        f"about how much slower an engine is.\n")
    add(f"Tokens per pass: {tpp_text}.\n")

    # ---- 1. speed
    add(f"## 1. Upper bound and {said} speeds\n")
    mf0 = model_facts(model, modality)
    add("Bytes one token reads, as the assessment defines them:\n")
    add("| Weight | Size | Read by one token | Counted |\n|---|---|---|---|")
    add(f"| `{mf0['expert_id']}` | per weight pack, below | {mf0['pick']} of {mf0['n_exp']} experts in each of {mf0['layers']} layers | yes |")
    use_text = {"full": "all of it", "row": "one row", "draft": "only when drafting", "other_modality": "not for this input",
                "modality_unknown": "only for some input modalities", "unknown_amount": "an amount the description does not give",
                "unread": "nothing"}
    for t in mf0["terms"]:
        if t["use"] == "row":
            counted = f"one row, {t['row'] / 1e3:.1f} kB" if t["row"] else "no: the size of one row cannot be derived"
        elif t["use"] == "full":
            counted = ("only the part not attributed to other items" if t["id"] == mf0["aggregate"] and mf0["aggregate_uncertain"]
                       else ("yes" if t["size"] is not None else "no: no size given"))
        else:
            counted = "no"
        add(f"| `{t['id']}` | {fmt(t['size'], 2) if t['size'] is not None else 'not given'} | {use_text[t['use']]} | {counted} |")
    add("")
    for n in mf0["notes"]:
        add(f"- {n}")
    add("")
    for line in described_notes(mf0):
        add(line)
    add("| Weight pack | One expert | Bytes read per token, at least | Upper bound per pass | Reported | Reported per pass | "
        "Reported / bound (tokens) | Reported per pass / bound |\n|---|---|---|---|---|---|---|---|")
    for p in ev["results"]["packs"]:
        mf = model_facts(model, modality, expert_bytes=sc.to_bytes(p["expert_bytes"]))
        bound = mem_rate / mf["bytes_strict"]
        vals = [v for k in ("decode_tok_per_s", "decode_tok_per_s_table_off") for v in (p.get(k) or {}).values()]
        lo, hi = min(vals), max(vals)
        row = {"pack": p["pack"], "bytes_per_token": mf["bytes_strict"], "bound": bound, "reported": [lo, hi],
               "token_ratio": [lo / bound, hi / bound]}
        if tpp:
            row["per_pass"] = [lo / tpp[1], hi / tpp[0]]
            row["per_pass_ratio"] = [lo / tpp[1] / bound, hi / tpp[0] / bound]
        rows_json.append(row)
        add(f"| {p['pack']} | {mf['per_expert'] / 1e6:.2f} MB | {fmt(mf['bytes_strict'], 2)} | {bound:.1f} tok/s | "
            f"{lo:g} to {hi:g} tok/s | " + (f"{num(row['per_pass'][0], 1)} to {num(row['per_pass'][1], 1)}" if tpp else "not known") +
            f" | {num(row['token_ratio'][0])} to {num(row['token_ratio'][1])} | " +
            (f"{num(row['per_pass_ratio'][0])} to {num(row['per_pass_ratio'][1])}" if tpp else "not known") + " |")
    token_ratio = [min(r["token_ratio"][0] for r in rows_json), max(r["token_ratio"][1] for r in rows_json)]
    if tpp:
        per_pass_ratio = [min(r["per_pass_ratio"][0] for r in rows_json), max(r["per_pass_ratio"][1] for r in rows_json)]
        verdict = "PASS" if per_pass_ratio[1] <= 1.0 else "FAIL"
        over = [r["pack"] for r in rows_json if r["per_pass_ratio"][1] > 1.0]
    else:
        per_pass_ratio, verdict, over = None, "NOT CHECKED", []
    add(f"\n**Result: {verdict}.** " + (
        f"Per pass the {said} speeds are {num(per_pass_ratio[0])} to {num(per_pass_ratio[1])} times the bound. "
        if per_pass_ratio else "The speed per pass is not known, so the condition cannot be applied. ") +
        f"In tokens per second they are {num(token_ratio[0])} to {num(token_ratio[1])} times it." +
        (f" Above the bound per pass: {', '.join(over)}; the bound, the weight sizes or the tokens per pass are wrong there."
         if over else "") + "\n")
    add("What each ratio can show:\n")
    add("- **Per pass** compares like with like. A value above 1 would refute the bound, or the sizes or tokens per pass it "
        "rests on. A value at or below 1 is consistent with it and does not show how close it is: computation and the "
        "attention state read per token are not in the bound.")
    add("- **Tokens per second** compares a speed in tokens with a bound per pass. With drafting a value above 1 is possible "
        "and contradicts nothing; this ratio cannot show whether the bound holds.")
    caches = [p.get("expert_cache") for p in ev["results"]["packs"]]
    known = all(c and "slots" in c and "of" in c for c in caches)
    all_in = known and all(c["slots"] >= c["of"] for c in caches)
    add("- " + ("The evidence reports every expert in the cache for every pack, so the engine read no expert from storage "
                "here: the storage part of the assessment's arithmetic, its cache and hit-rate estimates and its first-token "
                "estimates are not tested by this back-test." if all_in else
                ("The evidence reports fewer experts in the cache than the model has for at least one pack, so the engine "
                 "reads some from storage there" if known else "The evidence does not say how many experts the engine "
                 "holds in memory") + "; the bound still applies, as every expert in memory is the fastest case. Only the "
                "bound is compared: the assessment's cache, hit-rate and first-token estimates are not tested."))

    # ---- 2. memory
    add("\n## 2. Memory accounting\n")
    alloc_text = (fmt(alloc) + ", the memory figure of `" + env["id"] + "`") if alloc else "no memory figure"
    add(f"Everything the description says the engine holds in `{pool['id']}`, added up, against what the machine has "
        f"({alloc_text}) and what {'I measured' if own else 'the project reports'} as left free after start.\n")
    data = {d["id"]: d for d in model["data"]}
    add("| Held | Amount | From |\n|---|---|---|")
    total, unknown, seen = 0.0, [], set()
    for r in spec["binding"]["residency"]:
        if r["pool"] != pool["id"] or r["data"] in seen:
            continue
        seen.add(r["data"])
        size = sc.to_bytes(data.get(r["data"], {}).get("size")) or sc.to_bytes(r.get("capacity"))
        if size is None:
            unknown.append(f"`{r['data']}` (binding)")
            continue
        total += size
        add(f"| `{r['data']}` | {size / GB:.2f} GB | binding, {r.get('allocation', 'pinned')} |")
    for e in spec["composition"]["components"]:
        if e.get("active") is False:
            continue
        for u in e.get("uses", []):
            if u["where"] != pool["id"]:
                continue
            amt = u.get("amount")
            size = sc.to_bytes(amt) if isinstance(amt, dict) and isinstance(amt.get("value"), (int, float)) else None
            if size is None:
                unknown.append(f"{e['id']}: {u['purpose']}")
                continue
            if u.get("allocation") == "transient":
                continue
            total += size
            add(f"| {e['id']}: {u['purpose']} | {size / GB:.2f} GB | composition |")
    add(f"| **Total the description gives an amount for** | **{total / GB:.1f} GB** | |")
    mem_rows = []
    add("\n| Weight pack | Reported free after start | So the engine and the system hold | The description gives amounts for | "
        "Difference |\n|---|---|---|---|---|")
    base_expert = sc.to_bytes(data[mf0["expert_id"]]["size"])
    # A pack's lookup table, as the evidence reports it, replaces the description's item of the same size held in the pool.
    # The item is found by size, against any pack's table; if none matches, nothing is replaced and the output says so.
    held_sizes = {d: sc.to_bytes(data[d]["size"]) for d in seen if sc.to_bytes(data.get(d, {}).get("size"))}
    table_item = None
    for p in ev["results"]["packs"]:
        tb = sc.to_bytes((p.get("lookup_table") or {}).get("size"))
        hit = [d for d, b in held_sizes.items() if tb and d != mf0["expert_id"] and abs(b - tb) <= 0.005 * tb]
        if len(hit) == 1:
            table_item = hit[0]
            break
    table_notes = []
    for p in ev["results"]["packs"] if alloc else []:
        free = sc.to_bytes(p["free_memory_at_start"])
        held = alloc - free
        ours = total - base_expert + sc.to_bytes(p["expert_bytes"])
        table = p.get("lookup_table") or {}
        if table and table_item:
            in_memory = "storage" not in str(table.get("held", ""))
            ours += (sc.to_bytes(table["size"]) if in_memory else 0.0) - held_sizes[table_item]
            table_notes.append(f"{p['pack']}: `{table_item}` counted as {fmt(sc.to_bytes(table['size'])) if in_memory else 'not held'}"
                               f" (the evidence: {table.get('held', 'held where not stated')})")
        elif table:
            table_notes.append(f"{p['pack']}: the evidence reports a lookup table of {fmt(sc.to_bytes(table['size']))}, which "
                               f"matches no item of the description by size; the description's amounts are used unchanged")
        gap = held - ours
        mem_rows.append({"pack": p["pack"], "held": held, "accounted": ours, "gap": gap, "share": ours / held})
        add(f"| {p['pack']} | {free / GB:.1f} GB | {held / GB:.1f} GB | {ours / GB:.1f} GB ({ours / held:.0%} of it) | "
            f"{gap / GB:+.1f} GB |")
    if table_notes:
        add("\nLookup table per pack: " + "; ".join(table_notes) + ".")
    under = [m for m in mem_rows if m["share"] <= 1]
    beyond = [m for m in mem_rows if m["share"] > 1]
    res = []
    if under:
        res.append(f"for {', '.join(m['pack'] for m in under)} the amounts the description gives come to "
                   f"{min(m['share'] for m in under):.0%} to {max(m['share'] for m in under):.0%} of the memory in use; "
                   f"{min(m['gap'] for m in under) / GB:.1f} to {max(m['gap'] for m in under) / GB:.1f} GB is held by "
                   f"the {len(unknown)} items below, for which it gives no amount, or by the system")
    if beyond:
        res.append(f"for {', '.join(m['pack'] for m in beyond)} the amounts the description gives exceed the memory in use "
                   f"by {min(-m['gap'] for m in beyond) / GB:.1f} to {max(-m['gap'] for m in beyond) / GB:.1f} GB: the "
                   f"description or the reported figure is wrong there")
    if not alloc:
        res.append("the environment reports no allocatable memory, so the memory in use cannot be derived from the free memory")
    add(f"\n**Result:** " + "; ".join(res) + ".\n")
    if unknown:
        add("Held, with no amount in the description:\n")
        for u in unknown:
            add(f"- {u}")
        add("")

    # ---- 3. inactive parts
    add("## 3. What the description says about this machine, to be checked on it\n")
    add("These statements come from the engine's log of the measured run.\n" if own else
        "These statements come from the project's document, not from a run.\n")
    add("| Component | The description says | How to check on the machine |\n|---|---|---|")
    for cid, e in entries.items():
        if e.get("active") is False:
            add(f"| `{cid}` | inactive: {e.get('inactive_reason', '')} | its counters stay at zero during a run |")
    for p in ev["results"]["packs"]:
        c = p.get("expert_cache")
        if c:
            add(f"| expert cache, {p['pack']} | holds {c['slots']:,} of {c['of']:,} experts (the evidence) | the engine's "
                f"start-up line reports the slot count |")

    out = args.out if args.out.is_absolute() else root / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "backtest.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "backtest.json").write_text(json.dumps({
        "system": system["id"], "model": model["id"], "hardware": hw["id"], "evidence": ev["id"],
        "compared": "memory-bandwidth upper bound per pass, bytes per token as in so_assess.model_facts",
        "condition": "every reported speed / fewest tokens per pass <= bound", "condition_written": CONDITION_WRITTEN,
        "condition_written_after_first_result": True, "tokens_per_pass": list(tpp) if tpp else None,
        "verdict": verdict, "token_ratio": token_ratio, "per_pass_ratio": per_pass_ratio,
        "all_experts_in_memory": all_in, "speed": rows_json, "memory": mem_rows, "unaccounted_items": unknown},
        indent=2), encoding="utf-8")
    try:
        shown = (out / "backtest.md").resolve().relative_to(root).as_posix()
    except ValueError:
        shown = out / "backtest.md"
    print(f"wrote {shown}")
    for r in rows_json:
        print(f"  {r['pack']}: bound {r['bound']:.1f} tok/s per pass, {said} {r['reported'][0]:g} to {r['reported'][1]:g} tok/s"
              + (f", per pass {num(r['per_pass'][0], 1)} to {num(r['per_pass'][1], 1)}" if tpp else ""))
    print(f"  {verdict}: per pass / bound " + (f"{num(per_pass_ratio[0])} to {num(per_pass_ratio[1])}" if per_pass_ratio else "not known")
          + f"; tokens / bound {num(token_ratio[0])} to {num(token_ratio[1])} (condition written {CONDITION_WRITTEN}, after the first result)")
    return {"PASS": 0, "FAIL": 1}.get(verdict, 2)


if __name__ == "__main__":
    sys.exit(main())
