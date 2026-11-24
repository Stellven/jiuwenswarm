#!/usr/bin/env python3
"""Bounds and estimates for a model on a machine within a target's memory budget, for an engine of one architecture.

    python tools/so_assess.py sys/muse-on-spark --spec spec/muse-spark-open-on-dgx-spark/target \
        --environment env/dgx-spark-measured-20261119 --backtest runs/strata-backtest-02 --out runs/muse-assessment-07

What is assessed. The model, the machine (with what the environment measured on it), the target's memory budget and
context length, and one engine architecture that this program presupposes: the weights every token uses and part of
the selectively used weights (experts) are kept in memory, and the rest are read from storage when routed. Nothing is
built or run; every figure is arithmetic on the descriptions.

What the design contributes. Which node types it has (from `nodes.yaml` beside its system file, which is required),
and the decisions and invariants it records for the parts the arithmetic presupposes. A decision gives a number only
when it settles a quantity this program reads (DESIGN_QUANTITIES) and carries a numeric `value`. Otherwise no figure
changes when the design's decisions change. The output is not an assessment of the design's quality.

`model_facts` is also used by tools/so_backtest.py, so that both use the same definition of the bytes a token reads.
"""
import argparse
import json
import math
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import so_check as sc  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
GB = 1e9

# What the arithmetic presupposes of the engine, section by section: the node types it assumes the engine has, and
# what it assumes each of them does. For every type the output lists the design's nodes of that type, or says the
# design has none, in which case that section describes an engine with such a part and not this design.
PRESUPPOSED = [
    ("storage", "Storage", [
        ("model-conversion", "before the engine starts, writes the files the engine reads, every expert one contiguous "
                             "range, while the checkpoint they are made from is still on the same storage"),
        ("expert-source", "keeps every expert readable from storage for the whole run")]),
    ("memory", "Memory plan", [
        ("memory-planning", "divides the budget among the weights every token uses, the attention state for the context, "
                            "a staging area and a reserve, gives the expert cache the rest, and refuses to start below the "
                            "smallest cache"),
        ("positional-state-store", "holds the attention state of every position up to the context length, in the same budget"),
        ("expert-cache", "holds as many experts in memory as the plan leaves room for")]),
    ("decode", "Decode speed", [
        ("expert-cache", "holds the experts the residency policy keeps"),
        ("residency-policy", "keeps the most used experts of every layer in the cache"),
        ("expert-fetch", "reads a routed expert that is not cached from storage into a staging area before it is computed"),
        ("expert-dispatch", "issues the reads of a layer's missed experts before its cached experts are computed, so that "
                            "reading and computing overlap fully")]),
    ("prefill", "Time to first token", [
        ("prompt-reading", "reads a prompt in chunks, one layer at a time, reading each routed expert that is not cached "
                           "once per chunk"),
        ("expert-fetch", "reads those experts from storage"),
        ("prefix-reuse", "is not used by the figures: they are for a prompt that shares no prefix with stored state. With "
                         "a node of this type a request that continues a stored prefix reads only the rest")]),
    ("unknowns", "What is not known", [
        ("telemetry", "records how often each expert is routed, which measures the unevenness of use on this engine")]),
]

# Quantities a design decision can give a number for: the node type whose choice settles it, and that choice. A
# decision is linked to the quantity when a node of the type `settles` the choice with the decision's text. None: the
# type lists no such choice, so no decision can be linked and the program's own assumption is used.
DESIGN_QUANTITIES = {
    "reserve": ("memory-planning", "the reserve left free"),
    "min_cache": ("memory-planning", "the least a cache may be and still work"),
    "chunk": ("prompt-reading", "chunk size"),
    "staging": ("expert-fetch", None),
}

# Changes that would move the figures: the quantity of the arithmetic each changes and the node types that make it.
LEVERS = [
    ("Fewer bytes per expert: the expert weights stored at a lower precision", "bytes per expert", ["model-conversion"]),
    ("Fewer experts computed per token: low-ranked routed experts that are not cached are omitted",
     "experts read per token", ["expert-dispatch"]),
    ("More than one token per pass over the weights: drafted tokens checked in one pass", "tokens per pass",
     ["draft-proposal", "draft-verification"]),
]

# Model data recognised by id. The model schema has no field saying how much of a table one token reads, so these
# two conventions of the model descriptions are declared here. Any other weight that a token's computation reads,
# other than the experts, is not counted in the bytes a token reads, and the output says so.
ROW_TABLE_IDS = ("token_embedding",)                      # each token reads one row
FULL_READ_IDS = ("shared_weights", "output_head_weights")  # each token reads all of it
VOCAB_TABLE_IDS = ("token_embedding", "output_head_weights")  # vocabulary rows of hidden-size width
PRECISION_BITS = {"BF16": 16, "FP16": 16, "FP32": 32, "FP8": 8, "INT8": 8, "NVFP4": 4, "MXFP4": 4, "INT4": 4}


def number(v):
    """A statement's value as a number; YAML reads a bare 816e9 as text."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def stmt(obj, prop):
    return next((s for s in obj.get("statements", []) if s.get("property") == prop), None)


def zipf_probs(n, s):
    w = [1.0 / (i ** s) for i in range(1, n + 1)]
    t = sum(w)
    return [x / t for x in w]


def max_skew(n, pick):
    """Largest Zipf exponent at which the most used of n experts is chosen at most once per token, when each token
    chooses `pick` different experts: pick * p1 <= 1, i.e. sum of i^-s over 1..n >= pick. None when there is no limit."""
    if pick <= 1:
        return None
    lo, hi = 0.0, 1.0
    while sum(i ** -hi for i in range(1, n + 1)) >= pick:
        hi *= 2
    for _ in range(60):
        mid = (lo + hi) / 2
        if sum(i ** -mid for i in range(1, n + 1)) >= pick:
            lo = mid
        else:
            hi = mid
    return lo


def hit_rate(n, cached, s):
    """Share of selections that fall on the cached experts, when use follows a Zipf law with exponent s, the choices of
    successive tokens are independent, and the cache holds exactly the `cached` most used (the best a fixed set does).
    A fractional `cached` holds that fraction of the next expert."""
    if cached >= n:
        return 1.0
    p = zipf_probs(n, s)
    k = int(cached)
    return sum(p[:k]) + (cached - k) * p[k]


def distinct_uncached(n, cached, s, pick, tokens):
    """Expected number of experts outside the cache that `tokens` tokens touch, each token choosing `pick` different
    experts with marginal probability pick * p_i, tokens independent. Same cut of a fractional cache as hit_rate."""
    if cached >= n:
        return 0.0
    p = zipf_probs(n, s)
    k = int(cached)
    touched = [1.0 - max(0.0, 1.0 - pick * pi) ** tokens for pi in p]
    return (1 - (cached - k)) * touched[k] + sum(touched[k + 1:])


def fmt(x, digits=1):
    return f"{x / GB:.{digits}f} GB"


def probe_object_text(env, per_expert):
    """The size of the ranges the storage probe read, as the environment records it, beside the size of one expert of
    the model assessed: the rate was measured for that size and is used for this one."""
    found = set()

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("object_mb"), (int, float)):
                found.add(float(x["object_mb"]))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(env)
    if not found:
        return " of a size the environment does not record"
    sizes = " and ".join(f"{v:g} MB" for v in sorted(found))
    same = all(abs(v * 1e6 - per_expert) / per_expert < 0.05 for v in found)
    return (f" of {sizes} each, the size of one expert here" if same else
            f" of {sizes} each (one expert here is {per_expert / 1e6:.2f} MB; the rate for ranges of that size was not measured)")


def model_facts(model, modality=None, expert_bytes=None):
    """Sizes of a model and the bytes one token reads. `expert_bytes` replaces the described size of all experts (a
    back-test uses the size of a weight pack). Returns the figures and the reasons for every term counted or not."""
    sel_op = next((o for o in model["operations"] if o["kind"] == "selection"), None)
    if sel_op is None:
        raise SystemExit(f"model `{model['id']}` has no selection operation. This program is for models that choose a few "
                         f"of many weight blocks per token.")
    sel = sel_op["selects"]
    n_exp, pick = sel["out_of"], sel["pick"]
    ops = {o["id"]: o for o in model["operations"]}
    data = {d["id"]: d for d in model["data"]}
    eids = [sel["data"]] if sel.get("data") else [r for r in ops[sel["operation"]].get("reads", [])
                                                  if data.get(r, {}).get("kind") == "weight"]
    if len(eids) != 1:
        raise SystemExit(f"model `{model['id']}`: the selection chooses among {eids}; this program needs exactly one weight")
    eid = eids[0]
    ls = stmt(model, "layers")
    if ls is None:
        raise SystemExit(f"model `{model['id']}` states no `layers`; the size of one expert cannot be derived")
    layers = ls["value"]
    hidden = (stmt(model, "hidden_dim") or {}).get("value")
    vocab = (stmt(model, "vocab_size") or {}).get("value")
    ex = data[eid]
    bits = ex.get("encoded_bits")
    described_expert = sc.to_bytes(ex.get("size"))
    expert_total = expert_bytes if expert_bytes is not None else described_expert
    if expert_total is None:
        raise SystemExit(f"model `{model['id']}` gives no size for `{eid}`")
    per_expert = expert_total / (layers * n_exp)
    per_token_expert = pick * layers * per_expert

    readers = {d: [o for o in model["operations"] if d in o.get("reads", [])] for d in data}
    # an item whose size, with the experts, makes up every parameter at the stated bits holds every other weight
    aggregate, total_s = None, stmt(model, "params_total")
    total_params = number((total_s or {}).get("value"))
    if total_params and bits and described_expert:
        whole = total_params * bits / 8
        for d in data.values():
            size = sc.to_bytes(d.get("size"))
            others = [x for x in data.values() if x["kind"] == "weight" and x["id"] not in (eid, d["id"])
                      and any(not o.get("serves_modality") for o in readers[x["id"]])]
            # only when the other weights a text token reads have no size of their own: with sizes of their own they
            # are plainly not inside this item
            if d["kind"] == "weight" and d["id"] != eid and size and abs(described_expert + size - whole) <= 0.01 * whole \
                    and all(sc.to_bytes(x.get("size")) is None for x in others):
                aggregate = d["id"]
    terms, notes = [], []
    for d in data.values():
        if d["kind"] != "weight" or d["id"] == eid:
            continue
        rd = readers[d["id"]]
        own = sc.to_bytes(d.get("size"))
        if rd and all(o["kind"] == "draft" for o in rd):
            use = "draft"
        elif rd and all(o.get("serves_modality") for o in rd):
            use = "other_modality" if modality and all(modality not in o["serves_modality"] for o in rd) else (
                "full" if modality else "modality_unknown")
        elif d["id"] in ROW_TABLE_IDS:
            use = "row"
        elif d["id"] in FULL_READ_IDS or d["id"] == aggregate:
            use = "full"
        elif not rd:
            use = "unread"
        else:
            use = "unknown_amount"
        size, size_how = own, ("stated" if own is not None else None)
        if own is None and d["id"] in VOCAB_TABLE_IDS and vocab and hidden:
            b = d.get("encoded_bits") or bits
            if b:
                size = vocab * hidden * b / 8
                size_how = (f"{vocab:,} x {hidden:,} values at {b:g} bits" +
                            ("" if d.get("encoded_bits") else ", the bits of the expert weights: the model gives none for this table"))
        row = None
        if use == "row":
            if size is not None and vocab:
                row = size / vocab
            elif hidden and (d.get("encoded_bits") or bits):
                row = hidden * (d.get("encoded_bits") or bits) / 8
        cell = d.get("size") if isinstance(d.get("size"), dict) else {}
        terms.append({"id": d["id"], "use": use, "size": size, "size_how": size_how,
                      "bits_assumed": size_how is not None and size_how != "stated" and not d.get("encoded_bits"),
                      "inside": aggregate is not None and d["id"] != aggregate and own is None, "row": row,
                      "described": [x for x in (cell.get("note"), d.get("note")) if x]})

    strict = central = per_token_expert
    resident = 0.0
    agg_uncertain = False
    unpriced = []
    if aggregate:
        agg = next(t for t in terms if t["id"] == aggregate)
        inside = [t for t in terms if t["inside"]]
        rest = agg["size"] - sum(t["size"] for t in inside if t["size"] is not None)
        unsure = [t for t in inside if t["size"] is None and t["use"] not in ("full",)]
        for t in inside:
            if t["size"] is None:
                continue
            if t["use"] == "full":
                strict += t["size"]
                central += t["size"]
            elif t["use"] == "row" and t["row"]:
                strict += t["row"]
                central += t["row"]
        central += rest
        if unsure:
            agg_uncertain = True
            notes.append(f"`{aggregate}` ({fmt(agg['size'])}) holds every weight other than the experts: with the experts it "
                         f"makes up the model's {total_params:.4g} parameters at {bits:g} bits. Inside it, "
                         + ", ".join(f"`{t['id']}`" for t in unsure) + " has no size in the description and is not read by "
                         "every token of this target. The remainder of it after the parts with a size, "
                         f"{fmt(rest, 2)}, is therefore counted in the estimate but not in the upper bound: the bytes a token "
                         f"reads may be higher than the bound's figure by up to that much, so the bound holds but may be loose by that much.")
        else:
            strict += rest
        resident = agg["size"]
        for t in inside:
            if t["use"] in ("other_modality", "modality_unknown"):
                notes.append(f"`{t['id']}` is held in memory with `{aggregate}` because the description gives it no size of its "
                             f"own; an engine for this target need not hold it, which would leave more memory for the cache.")
    for t in terms:
        if t["inside"] or t["id"] == aggregate:
            continue
        if t["use"] == "full" and t["size"] is not None:
            strict += t["size"]
            central += t["size"]
            resident += t["size"]
        elif t["use"] == "row":
            if t["row"]:
                strict += t["row"]
                central += t["row"]
            if t["size"] is not None:
                resident += t["size"]
        elif t["use"] == "full":
            notes.append(f"`{t['id']}` is read by every token but has no size in the description; it is not counted, so the "
                         f"true bytes per token are higher and the true upper bound lower than shown by its size.")
        elif t["use"] == "unknown_amount":
            unpriced.append(t)
            notes.append(f"`{t['id']}`" + (f" ({fmt(t['size'])})" if t["size"] is not None else "") +
                         " is read while generating, but the description does not say how much of it one token reads. It is "
                         "not counted in the bytes a token reads (counting it would lower the upper bound) and not priced "
                         "in the memory plan (holding it in memory would shrink the cache).")
    for t in terms:
        if t["use"] == "row" and not t["row"]:
            notes.append(f"`{t['id']}`: one row is read per token, of a size the description does not allow to compute; it is "
                         f"not counted, so the true bytes per token are higher by one row.")
    return {"n_exp": n_exp, "pick": pick, "layers": layers, "hidden": hidden, "vocab": vocab, "bits": bits,
            "expert_id": eid, "expert_cell": ex.get("size"),
            "expert_described": [x for x in ((ex.get("size") or {}).get("note") if isinstance(ex.get("size"), dict) else None,
                                             ex.get("note")) if x], "expert_total": expert_total, "per_expert": per_expert,
            "per_token_expert": per_token_expert, "aggregate": aggregate, "terms": terms,
            "aggregate_uncertain": agg_uncertain, "bytes_strict": strict, "bytes_central": central, "resident": resident, "unpriced": unpriced, "notes": notes}


def described_notes(mf):
    """The model description's own notes on the weights counted in the bytes a token reads, quoted: the program does not
    read them, and they may say that the sizes or what a token reads differ from what is counted."""
    counted = [(mf["expert_id"], mf["expert_described"])] + [
        (t["id"], t["described"]) for t in mf["terms"]
        if t["described"] and (t["use"] in ("full", "row") or t["id"] == mf["aggregate"])]
    counted = [(i, d) for i, d in counted if d]
    if not counted:
        return []
    return (["The model description's own notes on the weights counted above. The program does not interpret them; "
             "where one says a size or the amount a token reads differs, the figures above do not reflect it:\n"]
            + [f"- `{i}`: " + " ".join(str(x).strip() for x in d) for i, d in counted] + [""])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--environment", required=True)
    ap.add_argument("--model", default=None,
                    help="a model description to use in place of the target's, for example the same model in another "
                         "storage precision. The output says so")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--contexts", default=None, help="context lengths to tabulate when the target sets none")
    ap.add_argument("--read-rates", default=None,
                    help="storage read rates in GB/s to assume instead of the environment's measured ones")
    ap.add_argument("--skews", default=None,
                    help="Zipf exponents of expert use to tabulate. Default: 0, half the largest possible, the largest possible")
    ap.add_argument("--reserve-gb", type=float, default=None)
    ap.add_argument("--budget-gb", type=float, default=None,
                    help="which of the target's candidate memory budgets to compute for, when it names several")
    ap.add_argument("--prompts", default=None, help="prompt lengths to tabulate when the target's workload gives none")
    ap.add_argument("--backtest", type=pathlib.Path, default=None,
                    help="a run directory of tools/so_backtest.py; its result is quoted in the limits")
    ap.add_argument("--root", type=pathlib.Path, default=ROOT)
    args = ap.parse_args()
    root = args.root.resolve()
    ws = sc.Workspace(root)
    for oid in (args.system, args.spec, args.environment):
        if oid not in ws.objects:
            raise SystemExit(f"`{oid}` is not among the descriptions under {root}")
    system, spec, env = ws.objects[args.system], ws.objects[args.spec], ws.objects[args.environment]
    model, hw = ws.objects[args.model or spec["given"]["model"]], ws.objects[spec["given"]["hardware"]]
    if model.get("kind") != "model":
        raise SystemExit(f"{args.model} is not a model description")
    other_model = args.model and args.model != spec["given"]["model"]
    if env.get("hardware") != hw["id"]:
        raise SystemExit(f"the environment `{env['id']}` is of `{env.get('hardware')}`, the target's machine is `{hw['id']}`")
    comps = {c["id"]: c for c in ws.of_kind("component") if c.get("system") == system["id"]}

    # ---- the design's node level: required
    nodes_path = ws.files[system["id"]].parent / "nodes.yaml"
    types_path = root / "ontology" / "node-types.draft.yaml"
    needed = sorted({t for _, _, ts in PRESUPPOSED for t, _ in ts})
    for path, what in ((nodes_path, "the design's node level"), (types_path, "the node types")):
        if not path.exists():
            raise SystemExit(f"{path.relative_to(root).as_posix()} is missing ({what}). The figures presuppose an engine with "
                             f"parts of the node types {', '.join(needed)}, and the program finds the design's parts by "
                             f"node type in that file. Without it, it cannot say whether the design has those parts, so it stops.")
    nodes = yaml.safe_load(nodes_path.read_text(encoding="utf-8")).get("nodes") or []
    draft = yaml.safe_load(types_path.read_text(encoding="utf-8"))
    node_types, types_version = {t["id"]: t for t in draft["types"]}, draft["draft_version"]
    for tid in needed + [t for _, _, ts in LEVERS for t in ts] + [v[0] for v in DESIGN_QUANTITIES.values()]:
        if tid not in node_types:
            raise SystemExit(f"the program presupposes node type '{tid}', which node types draft {types_version} does not have")

    def nodes_of(tid):
        return [n for n in nodes if n.get("type") == tid or tid in (n.get("also") or [])]

    def node_label(n):
        return f"`{n.get('described_in') or n.get('component')}`"

    def norm(s):
        return " ".join(str(s).split())

    stale = [n for n in nodes if n.get("described_in") in comps and n.get("does")
             and norm(n["does"]) != norm(comps[n["described_in"]].get("responsibility", ""))]
    orphan = [n for n in nodes if n.get("described_in") and n["described_in"] not in comps]

    def design_number(key):
        """(number, unit, node, decision) of a decision linked to the quantity and carrying a numeric value, else None;
        and the texts by which the design settles the choice without a number."""
        tid, choice = DESIGN_QUANTITIES[key]
        if choice is None or not any(c["what"] == choice for c in node_types[tid].get("choices", [])):
            return None, []
        words = []
        for n in nodes_of(tid):
            hows = [h for x in n.get("settles", []) or [] if x.get("choice") == choice for h in x.get("how", [])]
            comp = comps.get(n.get("described_in"), {})
            for d in comp.get("decisions", []) or []:
                if norm(d.get("text", "")) not in map(norm, hows):
                    continue
                v = d.get("value")
                num = v.get("value") if isinstance(v, dict) else v
                if isinstance(num, (int, float)) and not isinstance(num, bool):
                    return (num, v.get("unit") if isinstance(v, dict) else None, n, d), hows
            texts = [norm(d.get("text", "")) for d in comp.get("decisions", []) or []]
            words += [(n, h, norm(h) in texts) for h in hows]
        return None, words

    # ---- model
    modality = (spec.get("interface", {}).get("input") or {}).get("modality") if isinstance(spec.get("interface"), dict) else None
    modality = None if sc.is_unset(modality) else modality
    mf = model_facts(model, modality)
    n_exp, pick, layers, hidden = mf["n_exp"], mf["pick"], mf["layers"], mf["hidden"]
    expert_total, per_expert, per_token_expert = mf["expert_total"], mf["per_expert"], mf["per_token_expert"]
    resident = mf["resident"]
    n_all = layers * n_exp
    ex = mf["expert_cell"]

    # ---- budget, memory, storage
    req = next((r for r in spec["contract"]["requirements"] if r.get("quantity") == "memory_budget"), None)
    cands = (req or {}).get("candidates") or []
    if cands:
        # the target names several budgets and has not chosen: the figures are for the one given on the command line
        listed = "; ".join(f"{c['value']:g} {c.get('unit', req.get('unit', ''))} ({c.get('source', 'no source')})" for c in cands)
        if args.budget_gb is None:
            raise SystemExit(f"the target `{spec['id']}` names {len(cands)} candidate memory budgets and has not chosen one: "
                             f"{listed}. Give the one to compute for with --budget-gb.")
        pick_c = next((c for c in cands if abs(float(c["value"]) - args.budget_gb) < 1e-9), None)
        if pick_c is None:
            raise SystemExit(f"--budget-gb {args.budget_gb:g} is not one of the target's candidates: {listed}")
        req = {**{k: v for k, v in req.items() if k != "candidates"}, **pick_c,
               "status": f"one of {len(cands)} candidates the target names and has not chosen among: {listed}"}
    elif args.budget_gb is not None:
        raise SystemExit(f"the target `{spec['id']}` sets its memory budget itself; --budget-gb is for a target that names candidates")
    if req is None or sc.is_unset(req.get("value")):
        raise SystemExit(f"the target `{spec['id']}` sets no memory budget; every figure of the memory plan depends on it")
    budget = sc.to_bytes({"value": req["value"], "unit": req["unit"], "unit_basis": req.get("unit_basis", "decimal")})
    pool = req["pool"]
    alloc_cell = next((a for a in env.get("allocatable", []) if a["pool"] == pool), None)
    alloc = sc.to_bytes(alloc_cell) if alloc_cell else None
    mem_pool = next((p for p in hw["memory_pools"] if p["id"] == pool), None)
    if mem_pool is None or "bandwidth" not in (mem_pool.get("properties") or {}):
        raise SystemExit(f"the machine `{hw['id']}` gives no bandwidth for the budget's pool `{pool}`; the bound and every "
                         f"estimate divide by it")
    nominal = sc.to_bytes(mem_pool.get("capacity_nominal"))
    bw = mem_pool["properties"]["bandwidth"]
    mem_rate = bw["value"] * GB
    storage = next((p for p in hw["memory_pools"] if p["kind"] == "nvme"), None)
    if storage is None:
        raise SystemExit(f"the machine `{hw['id']}` has no storage pool; this program presupposes experts read from storage")
    if any(p["kind"] in ("host_ram",) for p in hw["memory_pools"]) and pool != next(
            (p["id"] for p in hw["memory_pools"] if p["kind"] == "host_ram"), pool):
        raise SystemExit(f"the machine `{hw['id']}` has a second memory pool between storage and `{pool}`; this program "
                         f"presupposes one pool that holds the cache, with the rest read from storage, and does not cover it")
    disk = next((s for s in env.get("statements", []) if s.get("property") == "capacity_reported_by_os"
                 and s.get("subject") == storage["id"]), None)
    if disk:
        storage_cap = sc.to_bytes({"value": disk["value"], "unit": disk["unit"], "unit_basis": disk.get("unit_basis", "decimal")})
        cap_text = f"{fmt(storage_cap, 0)}, the total size of the file system as the environment reports it, not its free space"
        cap_from = "environment"
    else:
        storage_cap = sc.to_bytes({**storage["capacity_nominal"], "unit_basis": storage["capacity_nominal"].get("unit_basis", "decimal")})
        cap_text = f"{fmt(storage_cap, 0)}, the nominal capacity in the hardware description ({storage['capacity_nominal'].get('note', 'no note')}), not free space"
        cap_from = "machine"
    paths = {p["id"] for p in hw.get("access_paths", []) if p.get("kind") == "page_in"}
    measured_read = next((s for s in env.get("statements", []) if s.get("property") == "read_bandwidth"
                          and s.get("subject") in paths and s.get("status") == "measured"), None)
    scattered = sorted(((s["conditions"]["concurrency"], s["value"] * GB) for s in env.get("statements", [])
                        if s.get("property") == "scattered_read_bandwidth" and s.get("subject") in paths
                        and s.get("status") == "measured" and "concurrency" in s.get("conditions", {})))
    rate_measured = False
    if args.read_rates:
        read_rates = sorted(float(x) * GB for x in args.read_rates.split(","))
        rate_text, rate_from = f"{args.read_rates} GB/s, given on the command line", "assumed by this program (command line)"
    elif scattered:
        at_pick = min(scattered, key=lambda x: abs(x[0] - pick))
        best = max(scattered, key=lambda x: x[1])
        cmax = max(c for c, _ in scattered)
        read_rates = sorted({at_pick[1], best[1]})
        rate_measured = True
        rate_text = (f"{at_pick[1] / GB:.2f} GB/s with {at_pick[0]} reads in flight (one token routes {pick} experts in a layer) "
                     f"and {best[1] / GB:.2f} GB/s, the best of the {len(scattered)} rates measured, at {best[0]} in flight"
                     + (", the largest concurrency tried" if best[0] == cmax else f" (the largest tried was {cmax})")
                     + "; scattered ranges" + probe_object_text(env, per_expert)
                     + ", measured with a test file and no engine running")
        rate_from = "environment (measured)"
    elif measured_read:
        m = measured_read["value"] * GB
        read_rates = [m / 2, m]
        rate_text = (f"{measured_read['value']:g} GB/s measured for one large sequential read, and half of it, because experts "
                     f"are separate ranges of about {per_expert / 1e6:.0f} MB")
        rate_from = "environment (sequential read measured), half of it assumed by this program"
    else:
        read_rates = [1.5 * GB, 3 * GB, 6 * GB]
        rate_text, rate_from = "1.5, 3 and 6 GB/s", "assumed by this program: nothing measured"
    r_best = max(read_rates)

    # ---- context, attention state, unevenness, prompts
    model_max = (stmt(model, "context_length") or {}).get("value")
    ctx_req = next((r for r in spec["contract"]["requirements"] if r.get("quantity") == "context_length"), None)
    target_ctx = None if ctx_req is None or sc.is_unset(ctx_req.get("value")) else int(sc.raw(ctx_req["value"]))
    dropped_ctx = []
    if target_ctx:
        contexts = [target_ctx]
        ctx_from = "target"
    else:
        contexts = [int(x) for x in (args.contexts or "8192,32768,131072").split(",")]
        ctx_from = "assumed by this program (the target sets none)" + (", given on the command line" if args.contexts else "")
        dropped_ctx = [c for c in contexts if model_max and c > model_max]
        contexts = [c for c in contexts if c not in dropped_ctx] or ([int(model_max)] if model_max else contexts)
    kv_stated = stmt(model, "attention_state_per_token")
    kv_bytes = sc.to_bytes(kv_stated) if kv_stated else None
    # A model may state that some layers attend only to the most recent tokens. Such a layer needs the state of that
    # many tokens and no more; whether an engine drops the older state is its choice, so both cases are shown.
    kv_window = {}
    win, win_layers = (stmt(model, "attention_window_tokens") or {}).get("value"), (stmt(model, "attention_windowed_layers") or {}).get("value")
    if kv_bytes:
        kv_cases = [("as the model states it", kv_bytes)]
        kv_text, kv_from = f"{kv_bytes / 1e6:.3f} MB with every layer keeping every token", "model"
        if win and win_layers:
            label = f"the {win_layers} windowed layers keep their last {win:,} tokens only"
            kv_cases = [("every layer keeps every token", kv_bytes), (label, kv_bytes)]
            kv_window[label] = (win_layers, win)
            kv_text += (f"; {win_layers} of the {layers} layers attend only to the last {win:,} tokens and need the state "
                        f"of no more than those")
    elif hidden:
        kv_wide = 2 * hidden * 2 * layers
        kv_cases = [("as wide as the hidden size", kv_wide), ("one eighth of that", kv_wide / 8)]
        kv_text = (f"{kv_wide / 8 / 1e6:.2f} MB and {kv_wide / 1e6:.2f} MB: keys and values as wide as the hidden size "
                   f"({hidden:,}) at 16 bits over {layers} layers, and one eighth of that")
        kv_from = "assumed by this program: the model does not state it"
    else:
        raise SystemExit(f"model `{model['id']}` states neither the attention state per token nor the hidden size; the "
                         f"memory plan cannot price the attention state")
    s_max = max_skew(n_exp, pick)
    if args.skews:
        asked = sorted(float(x) for x in args.skews.split(","))
        skews = [s for s in asked if s_max is None or s <= s_max + 1e-9]
        skews_dropped = [s for s in asked if s not in skews]
        skew_from = "given on the command line"
    else:
        skews = [0.0] + ([round(s_max / 2, 3), round(s_max, 3)] if s_max else [0.8, 1.2])
        skews_dropped = []
        skew_from = "assumed by this program"
    if not skews:
        raise SystemExit(f"none of the exponents {args.skews} is possible for this model: the largest at which the most used "
                         f"expert is chosen at most once per token is {s_max:.3f}")
    workload = spec["contract"].get("workload")
    prompts = [int(x) for x in (args.prompts or "100,1000,10000").split(",")]
    prompt_from = ("assumed by this program: the target's workload is not set" if workload is None or sc.is_unset(workload)
                   else "assumed by this program: it does not read prompt lengths from the target's workload")
    if args.prompts:
        prompt_from = "given on the command line"

    # ---- quantities a design decision can give
    param_rows, design_numbers = [], []

    def from_design(key, label, default_value, default_text, convert):
        tid, choice = DESIGN_QUANTITIES[key]
        hit, words = design_number(key)
        if hit:
            num, unit, n, d = hit
            v = convert(num, unit)
            if v is not None:
                design_numbers.append(f"{label}: `{d['id']}` of {node_label(n)}")
                return v, f"a decision of the design: `{d['id']}` of {node_label(n)}, {num:g} {unit or ''}".strip()
            words = [(n, f"`{d['id']}` gives {num:g} {unit or ''}, a unit this program cannot read for this quantity", True)]
        if choice is None:
            why = f"no choice of `{tid}` names this quantity, so no decision of the design can give it"
        elif not nodes_of(tid):
            why = f"the design has no node of type `{tid}`"
        elif words:
            why = "the design settles it in words only: " + "; ".join(
                f"{node_label(n)}: \"{h}\"" + ("" if backed else " (in nodes.yaml only: no decision of the component has this text now)")
                for n, h, backed in words)
        else:
            why = f"no node of type `{tid}` settles the choice \"{choice}\""
        return default_value, f"the design leaves this open ({why}); assumed here: {default_text}"

    if args.reserve_gb is not None:
        reserve, reserve_from = args.reserve_gb * GB, "assumed by this program (command line)"
    else:
        reserve, reserve_from = from_design("reserve", "reserve", 2 * GB, "2 GB",
                                            lambda v, u: sc.to_bytes({"value": v, "unit": u}) if u else None)
    min_cache, min_cache_from = from_design(
        "min_cache", "smallest cache", pick * layers * per_expert,
        f"the experts one step can route, {pick} x {layers} = {pick * layers}, {fmt(pick * layers * per_expert)}",
        lambda v, u: v * per_expert if u in ("experts",) else (sc.to_bytes({"value": v, "unit": u}) if u else None))
    staging, staging_from = from_design("staging", "staging area", 2 * pick * per_expert,
                                        f"{2 * pick} experts, twice what one token routes in a layer, {fmt(2 * pick * per_expert, 2)}",
                                        lambda v, u: v * per_expert if u in ("experts",) else (sc.to_bytes({"value": v, "unit": u}) if u else None))
    chunk, chunk_from = from_design("chunk", "chunk size", None, "the whole prompt as one chunk",
                                    lambda v, u: int(v) if u in (None, "tokens") else None)

    # ---- 1. sizes and storage
    prepared = expert_total + resident
    prec_listed = [p.strip() for p in str((stmt(model, "weight_precisions") or {}).get("value", "")).split(",") if p.strip()]
    total_params = number((stmt(model, "params_total") or {}).get("value"))
    chosen_ckpt = (spec.get("delivery") or {}).get("model_checkpoint")
    chosen_ckpt = None if sc.is_unset(chosen_ckpt) else str(sc.raw(chosen_ckpt))
    ckpts = []      # (precision, bytes or None, how known)
    named = ws.objects.get(spec["given"]["model"])
    named_mf = model_facts(named, modality) if named and named.get("kind") == "model" else None
    for p in ([chosen_ckpt] if chosen_ckpt else prec_listed):
        b = PRECISION_BITS.get(p.upper()) if p else None
        if b and total_params:
            ckpts.append((p, total_params * b / 8, f"{total_params:.4g} parameters at {b} bits"))
        elif chosen_ckpt and named_mf and named_mf["expert_total"] and named_mf["resident"]:
            ckpts.append((p, named_mf["expert_total"] + named_mf["resident"],
                          f"taken as the weights of the target's model, `{named['id']}`, as its description sizes them; "
                          "no field of the target gives the checkpoint a size"))
        else:
            ckpts.append((p, None, "size not derivable"))
    assumed_ckpt = not ckpts
    if assumed_ckpt:
        ckpts = [("as published", prepared, "assumed by this program: the same size as the prepared files, since neither "
                                            "the target nor the model names a precision")]
    storage_rows = []
    for p, size, how in ckpts:
        if size is None:
            storage_rows.append({"checkpoint": p, "bytes": None, "both_fit": None, "how": how})
        else:
            storage_rows.append({"checkpoint": p, "bytes": size, "both_fit": size + prepared <= storage_cap, "how": how})
    prepared_fits = prepared <= storage_cap
    # the checkpoint at the experts' own precision decides the verdict when the target names none
    match = [r for r in storage_rows if r["bytes"] and mf["bits"] and PRECISION_BITS.get(str(r["checkpoint"]).upper()) == mf["bits"]]
    decisive = (storage_rows[0] if chosen_ckpt or assumed_ckpt else (match[0] if match else None))

    # ---- memory plan
    plans = []
    for ctx in contexts:
        for label, per_tok in kv_cases:
            kv = ctx * per_tok
            if label in kv_window:                           # windowed layers hold at most the window
                wl, wt = kv_window[label]
                kv = per_tok / layers * ((layers - wl) * ctx + wl * min(ctx, wt))
            cache = budget - resident - kv - staging - reserve
            ok = cache >= min_cache
            n_cached = min(max(cache, 0) / per_expert, n_all)
            plans.append({"context": ctx, "kv_case": label, "kv_bytes": kv, "cache_bytes": cache, "feasible": ok,
                          "experts_cached": n_cached, "share": n_cached / n_all, "shortfall": max(min_cache - cache, 0)})
    feasible = [p for p in plans if p["feasible"]]
    best_plan = max(feasible, key=lambda p: p["share"]) if feasible else None
    worst_plan = min(feasible, key=lambda p: p["share"]) if feasible else None
    whole_fits = feasible and best_plan["share"] >= 1.0

    # ---- speed bound, reference, estimates
    bound = mem_rate / mf["bytes_strict"]
    central = mem_rate / mf["bytes_central"]
    t_mem = mf["bytes_central"] / mem_rate
    all_storage = 1.0 / max(per_token_expert / r_best, t_mem)
    decode, plan_cases = [], []
    if feasible:
        plan_cases = [("largest cache", best_plan)] + ([("smallest cache", worst_plan)] if worst_plan is not best_plan else [])
    for plan_label, plan in plan_cases:
        for s in skews:
            h = hit_rate(n_exp, plan["share"] * n_exp, s)
            miss = (1 - h) * per_token_expert
            decode.append({"plan": plan_label, "context": plan["context"], "kv_case": plan["kv_case"], "share": plan["share"],
                           "skew": s, "hit": h, "miss_bytes": miss, "tok_per_s": [1.0 / max(miss / r, t_mem) for r in read_rates]})
    lo = min(min(d["tok_per_s"]) for d in decode) if decode else None
    hi = max(max(d["tok_per_s"]) for d in decode) if decode else None

    def spread(key_fixed):
        """Largest ratio max/min of the estimate when only one factor varies, the others held."""
        groups = {}
        for d in decode:
            for i, r in enumerate(d["tok_per_s"]):
                k = {"skew": (d["plan"], i), "rate": (d["plan"], d["skew"]), "plan": (d["skew"], i)}[key_fixed]
                v = {"skew": d["skew"], "rate": i, "plan": d["plan"]}[key_fixed]
                groups.setdefault(k, {})[v] = r
        ratios = [max(g.values()) / min(g.values()) for g in groups.values() if len(g) > 1]
        return max(ratios) if ratios else None
    spreads = {k: spread(k) for k in ("skew", "rate", "plan")} if decode else {}
    spread_names = {"skew": "how unevenly the experts are used", "rate": "the storage read rate",
                    "plan": "the size of the cache, which the context length and the attention state set"}

    targets = [0.5, 1, 2, 5]
    needs = {}
    for tgt in targets:
        needs[tgt] = [None if 1 / tgt < t_mem else max(1 - r / (per_token_expert * tgt), 0.0) for r in read_rates]

    prefill = []
    if best_plan:
        for n in prompts:
            c = chunk or n
            sizes = [c] * (n // c) + ([n % c] if n % c else [])
            for s in (skews[0], skews[-1]):
                d = sum(distinct_uncached(n_exp, best_plan["share"] * n_exp, s, pick, t) for t in sizes)
                b = d * layers * per_expert
                uncached_layer = n_exp * (1 - best_plan["share"])
                prefill.append({"prompt": n, "chunks": len(sizes), "skew": s, "bytes": b,
                                "share_of_uncached_read": (d / len(sizes)) / uncached_layer if uncached_layer > 0 else 0.0,
                                "seconds": [b / r for r in read_rates]})
    pre_lo = min(min(p["seconds"]) for p in prefill) if prefill else None
    pre_hi = max(max(p["seconds"]) for p in prefill) if prefill else None

    # ---- unknowns
    unknowns = []
    if not rate_measured:
        unknowns.append(("Storage read rate for scattered expert reads", rate_text,
                         "run `tools/spark_kit/probe.py` on the machine", "expert-fetch"))
    unknowns.append(("How unevenly the model uses its experts", f"Zipf exponents {', '.join(f'{s:g}' for s in skews)}",
                     "record routing over the benchmark's prompts on any machine that can run the model", "telemetry"))
    if not kv_bytes:
        unknowns.append(("Attention state per token", kv_text, "read the model's config.json", "positional-state-store"))
    if not target_ctx:
        unknowns.append(("Context length the engine must offer", f"tabulated for {', '.join(f'{c:,}' for c in contexts)} tokens",
                         "a decision of the project, written into the target", "memory-planning"))
    not_measured = [f"the size of `{mf['expert_id']}` ({ex.get('status')})"] if isinstance(ex, dict) and ex.get("status") != "measured" else []
    for t in mf["terms"]:
        if t["id"] == mf["aggregate"] or (t["use"] in ("full",) and not t["inside"]):
            cell = next(d for d in model["data"] if d["id"] == t["id"]).get("size")
            if isinstance(cell, dict) and cell.get("status") != "measured":
                not_measured.append(f"the size of `{t['id']}` ({cell.get('status')})")

    # ================================================================ output
    L = []
    add = L.append
    add(f"# Bounds and estimates for `{model['id']}` on `{hw['id']}` within the target's {fmt(budget, 0)} budget, for an "
        f"engine that keeps part of the experts in memory\n")
    add(f"Model `{model['id']}` · machine `{hw['id']}` · environment `{env['id']}` · target `{spec['id']}` · "
        f"design `{system['id']}` (node types only) · node types draft {types_version}.\n")
    if other_model:
        add(f"**The model is not the one the target names.** The target names `{spec['given']['model']}`; these figures are "
            f"for `{model['id']}`, given on the command line. " + (f"{model.get('note')} " if model.get("note") else "") +
            "Whether the target allows this model in place of its own is the target's to say; this program does not "
            "judge it.\n")
    what = (f"**What is assessed.** The figures are bounds and estimates for the model `{model['id']}` on the machine "
            f"`{hw['id']}` within the target's memory budget of {fmt(budget, 0)}, for an engine of one architecture: the "
            f"weights every token uses and part of the experts kept in memory, the rest read from storage when routed. "
            f"The design `{system['id']}` contributes which node types it has and nothing else numeric: no figure changes "
            f"when the design's decisions change, unless a decision gives a number this program reads ("
            + ", ".join(f"{node_types[t]['id']}: {c}" for t, c in DESIGN_QUANTITIES.values() if c) + "; Section 2). "
            + (f"In this run {len(design_numbers)} decision(s) gave a number: {'; '.join(design_numbers)}."
               if design_numbers else "In this run no decision of the design gave a number.")
            + " This is not an assessment of the design's quality.\n")
    add(what)
    limits_at = len(L)

    def absent_note(key):
        if key in absent:
            add(f"**This design has no node of type {', '.join(f'`{t}`' for t in absent[key])}.** The figures of this section "
                f"describe an engine with such a part, which this design does not have.\n")

    # ---- 1. presupposed parts
    add("## 1. What the arithmetic presupposes of the engine, and which parts of the design have those node types\n")
    add("| Section | Node type | What the arithmetic assumes of it | Nodes of this design of that type |\n|---|---|---|---|")
    absent = {}
    for key, title, ts in PRESUPPOSED:
        for tid, assumes in ts:
            mine = nodes_of(tid)
            if not mine:
                absent.setdefault(key, []).append(tid)
            add(f"| {title} | `{tid}` | {assumes} | " + (", ".join(node_label(n) for n in mine) or "**none**") + " |")
    if absent:
        add("")
        for key, title, _ in PRESUPPOSED:
            if key in absent:
                add(f"- **{title}:** this design has no node of type {', '.join(f'`{t}`' for t in absent[key])}. The figures of "
                    f"that section describe an engine with such a part, which this design does not have.")
    add(f"\nThe nodes and their types are read from `{nodes_path.relative_to(root).as_posix()}`; a node's type is taken as "
        f"that file states it. " + (f"For {len(stale)} node(s) the job written there differs from the component's "
                                    f"responsibility in the design ({', '.join(node_label(n) for n in stale)}): the file was "
                                    f"written from an earlier text, and their types have not been read again from the "
                                    f"current one." if stale else "Every node's job there is the component's responsibility "
                                    "as the design now states it.")
        + (f" Nodes naming a component the design does not have: {', '.join(node_label(n) for n in orphan)}." if orphan else "") + "\n")

    # ---- 2. parameters
    add("## 2. Quantities the arithmetic uses, and where each comes from\n")
    add("| Quantity | Value used | Comes from |\n|---|---|---|")
    rows = [
        ("Experts", f"{layers} layers x {n_exp} = {n_all:,}; each token uses {pick} per layer", "model"),
        ("All expert weights", f"{fmt(expert_total)} at {mf['bits']} bits" if mf["bits"] else fmt(expert_total),
         f"model ({ex.get('status', 'stated') if isinstance(ex, dict) else 'stated'})"),
        ("Weights held in memory besides the experts", fmt(resident), "model (Section 3)"),
        ("Memory budget", f"{fmt(budget, 0)} of `{pool}`", f"target ({req.get('status', 'stated')})"),
        ("Allocatable memory", (f"{fmt(alloc)} of `{pool}`" if alloc else "not reported") +
         (f"; nominal {fmt(nominal, 0)}" if nominal else ""), "environment" + (f" ({alloc_cell.get('status')})" if alloc_cell else "")),
        ("Memory bandwidth", f"{bw['value']} GB/s", f"machine ({bw.get('status', '')})"),
        ("Storage read rate", rate_text, rate_from),
        ("Storage capacity", cap_text, cap_from),
        ("Context length", ", ".join(f"{c:,}" for c in contexts) + " tokens" +
         (f" (dropped as above the model's maximum: {', '.join(f'{c:,}' for c in dropped_ctx)})" if dropped_ctx else ""), ctx_from),
        ("Model's maximum context", f"{model_max:,} tokens" if model_max else "not stated", "model" if model_max else "-"),
        ("Attention state per token", kv_text, kv_from),
        ("Reserve left free", fmt(reserve), reserve_from),
        ("Smallest cache", fmt(min_cache), min_cache_from),
        ("Staging area", fmt(staging, 2), staging_from),
        ("Chunk of a prompt read at once", f"{chunk:,} tokens" if chunk else "the whole prompt", chunk_from),
        ("Prompt lengths tabulated", ", ".join(f"{p:,}" for p in prompts) + " tokens", prompt_from),
        ("Range of unevenness of expert use (Zipf exponent)", ", ".join(f"{s:g}" for s in skews) +
         (f" (dropped as impossible: {', '.join(f'{s:g}' for s in skews_dropped)})" if skews_dropped else ""),
         skew_from + ". A choice, not a property of the model"),
        ("Largest possible exponent", f"{s_max:.3f}: above it the most used expert would be chosen more than once per "
                                      f"token ({pick} different experts of {n_exp} per token)" if s_max else "no limit",
         "model (derived)"),
        ("Speeds tabulated in Section 6", ", ".join(f"{t:g}" for t in targets) + " tokens per second", "assumed by this program"),
    ]
    for r in rows:
        add("| " + " | ".join(r) + " |")
    add("")

    # ---- 3. sizes
    add("## 3. What the model asks of the machine\n")
    add(f"One expert is {fmt(expert_total)} / ({layers} x {n_exp}) = {per_expert / 1e6:.2f} MB. The expert weights one token "
        f"reads: {pick} x {layers} x {per_expert / 1e6:.2f} MB = {fmt(per_token_expert, 2)}.\n")
    use_text = {"full": "all of it", "row": "one row", "draft": "only when drafting", "other_modality":
                f"not for {modality} input", "modality_unknown": "only for some input modalities; the target sets none",
                "unknown_amount": "an amount the description does not give", "unread": "nothing"}
    add("| Other weight | Size | Read by one token | Counted in the upper bound | Counted in the estimate |\n|---|---|---|---|---|")
    for t in mf["terms"]:
        if t["id"] == mf["aggregate"]:
            add(f"| `{t['id']}` (every weight other than the experts) | {fmt(t['size'], 2)} | the part after those listed "
                f"inside it | {'only the parts listed with a size' if mf['aggregate_uncertain'] else 'yes'} | yes |")
            continue
        size = (fmt(t["size"], 2) + ("" if t["size_how"] == "stated" else f" ({t['size_how']})")) if t["size"] is not None else "not given"
        counted = (t["use"] == "full" and t["size"] is not None) or (t["use"] == "row" and bool(t["row"]))
        add(f"| `{t['id']}`" + (f" (inside `{mf['aggregate']}`)" if t["inside"] else "") + f" | {size} | {use_text[t['use']]} | "
            f"{'yes' if counted else 'no'} | {'yes' if counted else ('inside the remainder' if t['inside'] else 'no')} |")
    add(f"\nBytes one token reads at least, for one sequence and one token per pass: **{fmt(mf['bytes_strict'], 2)}**. "
        f"As an estimate: {fmt(mf['bytes_central'], 2)}. Attention state read per token is not counted in either; it "
        f"lowers the true speed, so leaving it out keeps the upper bound an upper bound.\n")
    for n in mf["notes"]:
        add(f"- {n}")
    if mf["notes"]:
        add("")
    for line in described_notes(mf):
        add(line)

    # ---- 4. storage
    add("## 4. Storage\n")
    absent_note("storage")
    add(f"The prepared files take {fmt(prepared, 0)} (all expert weights and the weights held besides them). The storage is "
        f"{cap_text}.\n")
    add("| Checkpoint | Size | How the size is known | Checkpoint and prepared files together | Fits |\n|---|---|---|---|---|")
    for r in storage_rows:
        if r["bytes"] is None:
            add(f"| {r['checkpoint']} | not known | {r['how']} | - | not known |")
        else:
            add(f"| {r['checkpoint']} | {fmt(r['bytes'], 0)} | {r['how']} | {fmt(r['bytes'] + prepared, 0)} | "
                f"{'yes' if r['both_fit'] else '**no**'} |")
    if assumed_ckpt:
        ck_note = "Neither the target nor the model names the checkpoint's precision; its size is assumed equal to the prepared files."
    elif chosen_ckpt:
        ck_note = f"The target names the checkpoint: {chosen_ckpt}."
    elif decisive:
        ck_note = (f"The target names no checkpoint; the row at the experts' own precision ({decisive['checkpoint']}) decides "
                   f"the result. The other rows show what another checkpoint would need.")
    else:
        ck_note = "The target names no checkpoint, and no listed precision matches the experts' bits; the result is not known."
    if decisive is None or decisive["bytes"] is None:
        storage_verdict = "not known" if prepared_fits else "no"
    elif decisive["both_fit"]:
        storage_verdict = "yes"
    elif prepared_fits:
        storage_verdict = "only if prepared elsewhere"
    else:
        storage_verdict = "no"
    st_text = {"yes": "the checkpoint and the prepared files fit together",
               "only if prepared elsewhere": "the prepared files fit, but not together with the checkpoint: the checkpoint "
                                             "must be prepared on another machine",
               "no": "the prepared files alone do not fit", "not known": "the prepared files fit; whether the checkpoint fits "
                                                                         "beside them is not known"}[storage_verdict]
    add(f"\n{ck_note} Free space is not reported, so files already on the device are not counted.\n")
    add(f"**Result:** {st_text}.\n")

    # ---- 5. memory plan
    add("## 5. Memory plan: how large the expert cache can be\n")
    absent_note("memory")
    add(f"The budget, {fmt(budget, 0)}, minus the weights held besides the experts ({fmt(resident)}), the attention state, the "
        f"staging area ({fmt(staging, 2)}) and the reserve ({fmt(reserve)}) is the cache. A row fits when the cache is at least "
        f"the smallest cache, {fmt(min_cache)}. " +
        (f"The environment reports {fmt(alloc)} allocatable in `{pool}`; " + (
            "the budget is within it." if budget <= alloc else
            f"**the budget is above it** by {fmt(budget - alloc)}: as reported, this machine cannot give it. The rows below "
            "are what the arithmetic gives for the budget as written.")
         if alloc else "The environment reports no allocatable figure.") + "\n")
    add("| Context (tokens) | Attention state per token | Attention state | Expert cache | Experts cached | Share of all experts |\n|---|---|---|---|---|---|")
    for p in plans:
        per_tok = next(v for k, v in kv_cases if k == p["kv_case"])
        add(f"| {p['context']:,} | {p['kv_case']}, {per_tok / 1e6:.2f} MB | {fmt(p['kv_bytes'])} | " +
            (f"{fmt(p['cache_bytes'])} | {p['experts_cached']:,.0f} | {p['share']:.0%} |" if p["feasible"]
             else f"**does not fit**: {fmt(p['shortfall'])} short | — | — |"))
    if not feasible:
        mem_result = (f"no row fits. The budget is short of the smallest cache by {fmt(min(p['shortfall'] for p in plans))} "
                      f"in the most favourable row. No estimate of speed or first-token time follows.")
    elif whole_fits:
        mem_result = (f"every expert fits in the cache in at least one row ({best_plan['context']:,} tokens, attention state "
                      f"{best_plan['kv_case']}): storage is not read while generating there.")
    else:
        held = (f"{best_plan['share']:.0%}" if len(feasible) == 1 else f"{worst_plan['share']:.0%} to {best_plan['share']:.0%}")
        mem_result = (f"{len(feasible)} of {len(plans)} rows fit; the cache holds {held} of the experts in them, and the experts are {expert_total / budget:.1f} times "
                      f"the budget. Across the rows the attention state takes {fmt(min(p['kv_bytes'] for p in plans))} to "
                      f"{fmt(max(p['kv_bytes'] for p in plans))} from the same budget.")
    add(f"\n**Result:** {mem_result}\n")

    # ---- 6. decode
    add("## 6. Decode speed\n")
    absent_note("decode")
    add(f"**Upper bound, with no assumption about how the experts are used:** {bound:.1f} tokens per second. Memory bandwidth ({bw['value']} GB/s) "
        f"divided by the bytes one token reads at least ({fmt(mf['bytes_strict'], 2)}, Section 3), with every routed expert "
        f"already in memory. It holds for one sequence and one token per pass over the weights; an engine that checks "
        f"several drafted tokens in one pass can produce more tokens per second than this. It rests on the sizes of the "
        f"weights as the model states them.\n")
    add(f"**Estimate with every weight in memory:** {central:.1f} tokens per second, with the bytes of the estimate "
        f"({fmt(mf['bytes_central'], 2)}).\n")
    add(f"**Reference point, no expert in memory:** {all_storage:.2f} tokens per second, every routed expert read from storage "
        f"at {r_best / GB:.2f} GB/s. Not a bound: a real engine with a cache is faster, and computation makes it slower.\n")
    add("**Estimates under stated assumptions.** Between these, the share of a token's experts found in the cache decides "
        "the speed. The estimates assume: (1) each token's choice of experts is independent of the previous token's; (2) the "
        "cache holds exactly the most used experts of every layer, which is the best a fixed set can do under (1); (3) reads "
        "overlap fully with computation, and computation itself takes no time beyond reading memory. Under (1) no "
        "cache can do better than (2). If successive tokens repeat experts, a cache that follows recent use finds more, "
        "so these estimates are **not** upper bounds on speed; (3) makes them optimistic. They are estimates, not bounds.\n")
    if not decode:
        add("No estimate: no row of the memory plan fits.\n")
    for plan_label, plan in plan_cases:
        add(f"**{plan_label.capitalize()}: {plan['share']:.0%} of experts cached** (context {plan['context']:,}, attention state "
            f"{plan['kv_case']}).\n")
        add("| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | " +
            " | ".join(f"Estimate at {r / GB:.2f} GB/s" for r in read_rates) + " |\n|---|---|---|" + "---|" * len(read_rates))
        for d in [d for d in decode if d["plan"] == plan_label]:
            add(f"| {d['skew']:g}{' (even)' if d['skew'] == 0 else ''} | {d['hit']:.0%} | {fmt(d['miss_bytes'], 2)} | " +
                " | ".join(f"{x:.2f} tok/s" for x in d["tok_per_s"]) + " |")
        add("")
    if decode:
        ordered = sorted(((v, k) for k, v in spreads.items() if v), reverse=True)
        fixed = [spread_names[k] for k, v in spreads.items() if not v]
        add(f"**Result:** {lo:.2f} to {hi:.2f} tokens per second as estimates under the assumptions above. " +
            ("Holding the other factors, the estimate moves most with " +
             ", then ".join(f"{spread_names[k]} (up to {v:.2f} times)" for v, k in ordered) + "." if ordered else "")
            + (f" Fixed in this run: {', '.join(fixed)}." if fixed else "")
            + f" Across the tabulated exponents, {skews[0]:g} to {skews[-1]:g}, the estimate for the largest cache at "
              f"{r_best / GB:.2f} GB/s goes from "
            f"{next(d['tok_per_s'][-1] for d in decode if d['plan'] == 'largest cache' and d['skew'] == skews[0]):.2f} to "
            f"{next(d['tok_per_s'][-1] for d in decode if d['plan'] == 'largest cache' and d['skew'] == skews[-1]):.2f} "
            f"tokens per second.\n")
    add("What a given speed requires, under the same assumptions:\n")
    add("| Speed | " + " | ".join(f"Share that must be found in cache at {r / GB:.2f} GB/s" for r in read_rates) + " |\n|---|" + "---|" * len(read_rates))
    for tgt in targets:
        add(f"| {tgt:g} tok/s | " + " | ".join("above the estimate with every weight in memory" if x is None else
                                              ("any" if x <= 0 else f"{x:.0%}") for x in needs[tgt]) + " |")
    if decode:
        reach = {tgt: sorted({(d["plan"], d["skew"]) for d in decode if max(d["tok_per_s"]) >= tgt}) for tgt in targets}
        lines = []
        for tgt in targets:
            if reach[tgt]:
                lines.append(f"{tgt:g} tok/s is reached in {len(reach[tgt])} of {len({(d['plan'], d['skew']) for d in decode})} "
                             f"rows above at the best rate (lowest exponent among them: {min(s for _, s in reach[tgt]):g})")
            else:
                lines.append(f"{tgt:g} tok/s is reached in no row above")
        add("\n" + "; ".join(lines) + ".\n")
    else:
        add("")

    # ---- 7. prefill
    add("## 7. Time to first token\n")
    absent_note("prefill")
    if not prefill:
        add("No estimate: no row of the memory plan fits.\n")
    else:
        add(f"A prompt is read {'in chunks of ' + format(chunk, ',') + ' tokens' if chunk else 'as one chunk'}, one layer at a "
            f"time, so an expert routed by several tokens of a chunk is read once. The table gives the bytes read from storage "
            f"for a prompt that shares nothing with stored state, for the largest cache ({best_plan['share']:.0%}), and the "
            f"time that reading alone takes. Same assumptions as Section 6: tokens choose independently, so a prompt whose "
            f"tokens repeat experts reads fewer; these are estimates, **not** lower bounds on time.\n")
        add("| Prompt (tokens) | Use of experts | Read from storage | Share of uncached experts read per chunk | " +
            " | ".join(f"Estimate at {r / GB:.2f} GB/s" for r in read_rates) + " |\n|---|---|---|---|" + "---|" * len(read_rates))
        for p in prefill:
            add(f"| {p['prompt']:,} | {p['skew']:g}{' (even)' if p['skew'] == 0 else ''} | {fmt(p['bytes'], 0)} | "
                f"{p['share_of_uncached_read']:.0%} | " + " | ".join(f"{t:.0f} s" for t in p["seconds"]) + " |")
        cap_read = (1 - best_plan["share"]) * expert_total
        add(f"\n**Result:** {pre_lo:.0f} to {pre_hi:.0f} seconds of storage reading before the first token, as estimates. "
            f"Whatever the use of experts, one chunk reads each uncached expert at most once: at most "
            f"{fmt(cap_read, 0)}, {cap_read / r_best:.0f} s at {r_best / GB:.2f} GB/s per chunk. "
            + ("Nodes of type `prefix-reuse` in this design: " + ", ".join(node_label(n) for n in nodes_of("prefix-reuse"))
               + "; a request that continues a stored prefix reads only what follows it."
               if nodes_of("prefix-reuse") else "This design has no node of type `prefix-reuse`: every prompt is read in full.")
            + "\n")

    # ---- 8. unknowns
    add("## 8. What is not known, and how to find out\n")
    absent_note("unknowns")
    add("| Unknown | Treated here as | How to settle it | Node type that would settle it in the engine | Nodes of this design |\n|---|---|---|---|---|")
    for u in unknowns:
        add("| " + " | ".join(u[:3]) + f" | `{u[3]}` | " + (", ".join(node_label(n) for n in nodes_of(u[3])) or "none") + " |")
    add("")

    # ---- 9. what the design records
    add("## 9. What the design records for the parts the arithmetic presupposes\n")
    add("Read from each node's component in the design: its decisions (with a value where one is given) and invariants, "
        "and the choices of the node type the node settles. None of these changes a figure unless Section 2 says so.\n")
    seen = set()
    for _, _, ts in PRESUPPOSED:
        for tid, _ in ts:
            if tid in seen:
                continue
            seen.add(tid)
            mine = nodes_of(tid)
            if not mine:
                add(f"- `{tid}`: the design has no node of this type.")
                continue
            for n in mine:
                comp = comps.get(n.get("described_in"), {})
                decs = [f"`{d['id']}`: {d.get('text', '').rstrip('.')}" + (
                    f" (value: {sc.raw(d['value'])} {d['value'].get('unit', '') if isinstance(d['value'], dict) else ''}".rstrip() + ")"
                    if "value" in d else "") for d in comp.get("decisions", []) or []]
                invs = [f"`{i['id']}`: {i.get('text', '').rstrip('.')}" for i in comp.get("invariants", []) or []]
                dec_texts = {norm(d.get("text", "")) for d in comp.get("decisions", []) or []}
                sets = [f"{x.get('choice')}: {' '.join(x.get('how', [])).rstrip('.')}" + (
                    "" if all(norm(h) in dec_texts for h in x.get("how", [])) else
                    " (in nodes.yaml only: no decision of the component has this text now)")
                        for x in n.get("settles", []) or []]
                add(f"- `{tid}`, {node_label(n)}: " + (
                    "; ".join(filter(None, [("decisions: " + " | ".join(decs)) if decs else "",
                                            ("invariants: " + " | ".join(invs)) if invs else "",
                                            ("settles: " + " | ".join(sets)) if sets else ""]))
                    or "the design records no decision, invariant or settled choice for this node") + ".")
    add("")

    # ---- 10. levers
    allowed = spec["contract"].get("allowed_transformations")
    allowed = None if allowed is None or sc.is_unset(allowed) else set(allowed["value"] if isinstance(allowed, dict) else allowed)
    levers = []
    add("## 10. Changes that would move the figures\n")
    add("Each change alters one quantity of the arithmetic. The levels are every level the node type lists for its own work "
        "(how far it can move the output); which one a given change reaches depends on how it is made.\n")
    add("| Change | Quantity it alters | Node type | Nodes of this design | Levels the type lists | Allowed by the target |\n|---|---|---|---|---|---|")
    for lever, qty, tids in LEVERS:
        for tid in tids:
            lv = node_types[tid]["effect_on_output"]
            mine = nodes_of(tid)
            ok = ("not decided: the target's `allowed_transformations` is not set" if allowed is None
                  else ", ".join(f"{l}: {'yes' if l in allowed else 'no'}" for l in lv))
            levers.append({"lever": lever, "quantity": qty, "node_type": tid, "levels": lv,
                           "in_design": [n.get("described_in") for n in mine],
                           "allowed": None if allowed is None else {l: l in allowed for l in lv}})
            add(f"| {lever} | {qty} | `{tid}` | {', '.join(node_label(n) for n in mine) or 'none'} | "
                f"{', '.join(f'`{l}`' for l in lv)} | {ok} |")
    add("")

    # ---- 11. summary
    add("## 11. Summary\n")
    reasons_no, reasons_if, reasons_open = [], [], []
    if alloc and budget > alloc:
        reasons_no.append(f"the budget, {fmt(budget, 0)}, is above the {fmt(alloc)} the environment reports allocatable")
    elif not alloc and nominal and budget > nominal:
        reasons_no.append(f"the budget, {fmt(budget, 0)}, is above the machine's nominal {fmt(nominal, 0)}")
    if storage_verdict == "no":
        reasons_no.append("the prepared files do not fit on storage")
    elif storage_verdict == "only if prepared elsewhere":
        reasons_if.append("the checkpoint is prepared on another machine")
    elif storage_verdict == "not known":
        reasons_open.append("whether the checkpoint fits beside the prepared files")
    if target_ctx and model_max and target_ctx > model_max:
        reasons_no.append(f"the target's context, {target_ctx:,}, is above the model's maximum, {model_max:,}")
    if not feasible:
        reasons_no.append("no row of the memory plan fits" + (f" the target's context of {target_ctx:,} tokens" if target_ctx else ""))
    elif target_ctx and len(feasible) < len(plans):
        reasons_if.append(f"the attention state for the target's {target_ctx:,} tokens is held as in the rows of Section 5 "
                          "that fit (" + "; ".join(sorted({p["kv_case"] for p in feasible})) + ")")
    elif not target_ctx:
        reasons_open.append("the target sets no context length; the contexts that fit here are "
                            + ", ".join(sorted({f"{p['context']:,}" for p in feasible}, key=lambda x: int(x.replace(',', ''))))
                            + (" (not every attention-state case)" if len(feasible) < len(plans) else ""))
    if reasons_no:
        verdict = "**No**: " + "; ".join(reasons_no) + "."
    elif reasons_if:
        verdict = "**Only if** " + "; and ".join(reasons_if) + "."
    else:
        verdict = "**Yes** on memory and storage" + (" for the rows of Section 5 that fit" if not target_ctx else "") + "."
    if reasons_open and not reasons_no:
        verdict += " Open: " + "; ".join(reasons_open) + "."
    add(f"- **Can it run?** {verdict}")
    if whole_fits:
        add(f"- **Can the model be held in memory?** Yes, within the {fmt(budget, 0)} budget in at least one row of Section 5; "
            f"there the speed is bounded by memory bandwidth alone." +
            (f" The machine cannot give that budget ({fmt(alloc)} allocatable)." if alloc and budget > alloc else ""))
    else:
        add(f"- **Can the model be held in memory?** No: the experts are {fmt(expert_total, 0)}, " +
            (f"and the cache holds at most {best_plan['share']:.0%} of them." if feasible else "and no cache fits."))
    add(f"- **Upper bound on decode speed:** {bound:.1f} tokens per second (one sequence, one token per pass). Estimate with "
        f"every weight in memory: {central:.1f}. Reference with no expert in memory: {all_storage:.2f}.")
    if decode:
        add(f"- **Estimated decode speed** under the assumptions of Section 6: {lo:.2f} to {hi:.2f} tokens per second.")
        add(f"- **Estimated storage time before the first token** for prompts of {', '.join(f'{p:,}' for p in prompts)} tokens: "
            f"{pre_lo:.0f} to {pre_hi:.0f} seconds.")
        if ordered:
            add(f"- **Largest spread in this run:** {spread_names[ordered[0][1]]}, up to {ordered[0][0]:.2f} times.")
    blocking = [i for i in sc.check_spec(ws, spec)[0] if i.blocking]
    add(f"- **What the project still has to decide:** the target has {len(blocking)} blocking gaps; run "
        f"`python tools/so_check.py check {spec['id']}` for the list.")

    # ---- read this first
    K = ["## Read this first: what these figures can and cannot say",
         f"0. **What they are about:** the model, the machine and the target's budget, for an engine that keeps the weights "
         f"every token uses and part of the experts in memory and reads the rest from storage when routed. The design "
         f"gives only which node types it has" + (f", and these numbers: {'; '.join(design_numbers)}" if design_numbers else
                                                   ", and no number") +
         ". No figure changes when its decisions change unless a decision gives a number this program reads. This is not "
         "an assessment of the design's quality."]
    K.append(f"1. **One figure is an upper bound that needs no assumption about how the experts are used:** {bound:.1f} tokens per second, memory bandwidth "
             f"over the bytes a token surely reads, for one sequence and one token per pass, with the weight sizes as the "
             f"model states them (Section 2 says how each is known)."
             + (f" Inside `{mf['aggregate']}` the description gives no size to a part a token of this target does not "
                f"read, so {fmt(mf['bytes_central'] - mf['bytes_strict'], 2)} of possibly read weights is left out of the "
                f"bound: it is a true upper bound but may be loose by that much (the estimate counts it: {central:.1f} "
                f"tokens per second)." if mf["aggregate_uncertain"] else "")
             + ((lambda ids: f" {', '.join(ids)} {'is' if len(ids) == 1 else 'are'} sized at the bits of the expert weights "
                             f"because the model gives no bits for {'it' if len(ids) == 1 else 'them'}: stored at more bits, "
                             f"the true bound is lower than this figure; at fewer, higher." if ids else "")(
                 [f"`{t['id']}`" for t in mf["terms"] if t["bits_assumed"] and
                  ((t["use"] == "full") or (t["use"] == "row" and t["row"]))]))
             + f" With no expert in memory a token takes {1 / all_storage:.1f} s ({all_storage:.2f} tokens per "
             f"second), a reference point, not a bound.")
    K.append("2. **Every other speed and time is an estimate under stated assumptions** (Section 6): each token's choice of "
             "experts independent of the previous token's, the cache holding the most used experts, reading fully "
             "overlapped and computation not counted. If successive tokens repeat experts, a cache that follows recent use "
             "finds more: the speed estimates are then not upper bounds and the first-token estimates not lower bounds.")
    K.append(f"3. **The figures are for the target's budget of {fmt(budget, 0)}** ({req.get('status', 'stated')}); the "
             f"environment reports {fmt(alloc) + ' allocatable' if alloc else 'no allocatable figure'}. They change with the "
             f"budget, the reserve, the context lengths and the range of unevenness, each listed with its source in Section 2.")
    bt = None
    if args.backtest is not None:
        bt_dir = args.backtest if args.backtest.is_absolute() else root / args.backtest
        bt_path = bt_dir / "backtest.json"
        if not bt_path.exists():
            raise SystemExit(f"{bt_path} does not exist")
        bt = json.loads(bt_path.read_text(encoding="utf-8"))
    if bt and "verdict" in bt:
        same = "the same machine description as here" if bt.get("hardware") == hw["id"] else f"`{bt.get('hardware')}`, not this machine"
        ppr, tr = bt.get("per_pass_ratio"), bt.get("token_ratio")
        K.append(f"4. **Back-test** (`{args.backtest.as_posix()}`): the memory-bandwidth upper bound, computed the same way, was "
                 f"compared with the speeds the project of `{bt.get('system')}` reports for model `{bt.get('model')}` on "
                 f"{same}. Condition: {bt.get('condition', 'not stated')} (written {bt.get('condition_written', 'on an unstated date')}"
                 + (", after the first result was known" if bt.get("condition_written_after_first_result") else "") + "). "
                 + (f"Per pass the reported speeds are {ppr[0]:.2f} to {ppr[1]:.2f} times the bound: **{bt['verdict']}**. "
                    if ppr else f"The speed per pass is not known there: **{bt['verdict']}**. ")
                 + (f"In tokens per second they are {tr[0]:.2f} to {tr[1]:.2f} times it. " if tr else "")
                 + ("That engine holds every expert in memory there, so the storage part of the arithmetic, the cache and "
                    "hit-rate estimates and the first-token estimates were not compared with it. "
                    if bt.get("all_experts_in_memory") else
                    "That engine reads some experts from storage there, but the back-test compares only the upper bound, so "
                    "the cache and hit-rate estimates and the first-token estimates were not compared with it. ")
                 + "This program was given no measurement of an engine built to this design.")
    elif bt:
        K.append(f"4. **Back-test** `{args.backtest.as_posix()}` was written by an earlier version of so_backtest.py and states no "
                 f"pass condition; it is not quoted.")
    else:
        K.append("4. **Nothing here has been compared with a real engine:** no back-test was named (`--backtest`).")
    K.append(f"5. **{len(unknowns)} quantities are not known and {len(not_measured)} are derived, not read from the model's "
             f"files.** Not known: {'; '.join(u[0][0].lower() + u[0][1:] for u in unknowns)}. Derived: "
             f"{'; '.join(not_measured) or 'none'}. Section 8 says how each can be settled.")
    if absent or stale:
        K.append("6. **The design and these figures:** " + "; ".join(
            ([f"the design has no node of type {', '.join(f'`{t}`' for t in dict.fromkeys(t for ts in absent.values() for t in ts))}, which the "
              f"arithmetic presupposes (Section 1)"] if absent else []) +
            ([f"{len(stale)} node(s) of `nodes.yaml` were typed from text the design no longer has (Section 1)"] if stale else [])) + ".")
    K.append("")
    L.insert(limits_at, "\n\n".join(K))

    out = args.out if args.out.is_absolute() else root / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "assessment.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "assessment.json").write_text(json.dumps({
        "system": system["id"], "spec": spec["id"], "environment": env["id"], "model": model["id"], "hardware": hw["id"],
        "assessed": "bounds and estimates for the model on the machine within the target's budget, for an engine keeping "
                    "part of the experts in memory; the design contributes its node types only",
        "design_numbers_used": design_numbers, "nodes_absent": absent, "nodes_stale": [n.get("described_in") for n in stale],
        "per_expert_bytes": per_expert, "per_token_expert_bytes": per_token_expert,
        "bytes_per_token_lower_bound": mf["bytes_strict"], "bytes_per_token_estimate": mf["bytes_central"],
        "memory_bound_tok_per_s": bound, "memory_estimate_tok_per_s": central, "all_from_storage_tok_per_s": all_storage,
        "budget_bytes": budget, "allocatable_bytes": alloc, "max_skew": s_max, "skews": skews, "contexts": contexts,
        "storage": {"prepared_bytes": prepared, "capacity_bytes": storage_cap, "rows": storage_rows, "verdict": storage_verdict},
        "plans": plans, "decode": decode, "prefill": prefill, "required_hit_rate": needs,
        "decode_estimate_range": [lo, hi] if decode else None, "ttft_estimate_range_s": [pre_lo, pre_hi] if prefill else None,
        "spreads": spreads, "can_run": verdict, "target_spec_blocking_gaps": len(blocking),
        "backtest": {k: bt.get(k) for k in ("verdict", "per_pass_ratio", "token_ratio", "hardware")} if bt else None,
        "node_types_draft": types_version, "changes_to_output": levers}, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        shown = (out / "assessment.md").resolve().relative_to(root).as_posix()
    except ValueError:
        shown = out / "assessment.md"
    print(f"wrote {shown}")
    print(f"  upper bound {bound:.1f} tok/s (estimate with all in memory {central:.1f}); reference with nothing cached "
          f"{all_storage:.2f} tok/s")
    if decode:
        print(f"  estimates: decode {lo:.2f} to {hi:.2f} tok/s; first token {pre_lo:.0f} to {pre_hi:.0f} s; cache "
              + (f"{best_plan['share']:.0%}" if len(feasible) == 1 else f"{worst_plan['share']:.0%} to {best_plan['share']:.0%}") + " of experts")
    print(f"  can it run: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
