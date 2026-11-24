#!/usr/bin/env python3
"""Write a parts inventory from an engine that already has a full two-level description.

    python tools/so_inventory.py sys/strata

The inventory format is the one in `validation/INVENTORY-BRIEF.md`, used as the common evidence base for inducing
and testing node types. For an engine described in full (system plus components), the inventory is derived from
that description and nothing is added: what a part takes and gives comes from the system's flows, its decisions
lose their values, its invariants become `must_never`.
"""
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import so_check as sc  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
RANK = {"bit_exact": 0, "distribution_exact": 1, "numeric": 2, "approximate": 3}
EFFECT = {0: "none", 1: "numeric", 2: "numeric", 3: "changes_output"}


def parts_of(ws, sid):
    """The parts of a system that has a full two-level description, in the inventory format."""
    system = ws.objects[sid]
    comps = {c["id"]: c for c in ws.of_kind("component") if c["system"] == sid}
    leaves = {cid: c for cid, c in comps.items() if not c.get("parts")}
    short = lambda cid: cid.split("/")[-1] if cid in comps else cid

    def leaf_ends(cid):
        """A flow that ends at a subsystem is attributed to it as a whole; keep its id so nothing is invented."""
        return short(cid)

    parts = []
    for cid, c in leaves.items():
        eq = c.get("equivalence")
        cases = eq if isinstance(eq, list) else ([{"level": eq}] if isinstance(eq, str) else ([eq] if eq else []))
        worst = max((RANK.get(x.get("level"), 0) for x in cases), default=0)
        when = "; ".join(f"{x.get('level')} when {x['holds_when']}" for x in cases if x.get("holds_when"))
        part = {
            "id": short(cid),
            "engine_name": c.get("title", ""),
            "does": c["responsibility"],
            "runs": c["runs"],
            "takes": [{"from": leaf_ends(f["sender"]), "what": f.get("description") or f["id"]}
                      for f in system.get("flows", []) if f["receiver"] == cid],
            "gives": [{"to": leaf_ends(f["receiver"]), "what": f.get("description") or f["id"]}
                      for f in system.get("flows", []) if f["sender"] == cid],
            "owns_state": list(c.get("state", {}).get("owns", [])),
            "exists_because": "not recorded in the full description",
            "output_effect": EFFECT[worst],
            "decisions": [d["text"] for d in c.get("decisions", []) if d.get("text")],
            "when_things_go_wrong": [],
            "must_never": [i["text"] for i in c.get("invariants", [])],
            "evidence": [s["ref"] for s in c.get("sources", [])],
            "read": "code" if any(s["basis"] == "code" for s in c.get("sources", [])) else "docs",
        }
        if c.get("not_responsible_for"):
            part["not"] = "; ".join(c["not_responsible_for"])
        if when:
            part["output_effect_when"] = when
        parts.append(part)
    return system, leaves, parts


def main():
    sid = sys.argv[1]
    ws = sc.Workspace(ROOT)
    system, leaves, parts = parts_of(ws, sid)
    name = sid.split("/")[-1]
    out = {
        "engine": system.get("title", name),
        "revision": system.get("product", {}).get("revision", ""),
        "basis": "Derived by tools/so_inventory.py from the full two-level description of this engine. " + system.get("coverage", ""),
        "concurrency": "see parts",
        "models": "; ".join(t["model"] for t in system.get("targets", [])),
        "derived_from_description": True,
        "parts": parts,
        "absent": [],
        "outside_engine": [],
        "surprises": [],
        "not_read": "; ".join(sorted({c["not_read"] for c in leaves.values() if c.get("not_read")}))[:1500],
    }
    dst = ROOT / "validation" / "inventory" / f"{name}.yaml"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("# Derived from the full description; see tools/so_inventory.py.\n" +
                   yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=118), encoding="utf-8")
    n_dec = sum(len(p["decisions"]) for p in parts)
    print(f"wrote {dst.relative_to(ROOT)}: {len(parts)} parts, {n_dec} decisions, "
          f"{sum(1 for p in parts if p['read'] == 'code')} read in code")
    print("  not derivable from the description: exists_because, when_things_go_wrong")
    return 0


if __name__ == "__main__":
    sys.exit(main())
