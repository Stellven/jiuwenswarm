"""The canary: do independent derivations from the vault agree? (PROCESS.md, "The canary")

Two modes, each over capsule Declarations (cc.declaration.v1 JSON):

  --compare A.json B.json
      Two agents derived the SAME module blind. They must agree on every interface fact: kind, every port's
      name, type and required flag, needs.external refs, effect_class, effect resource keys, failure codes,
      and check ids with their anchor, over and applies_at.

  --producer A.json --consumer B.json --wire OUT=IN [--wire OUT=IN ...]
      Two agents derived the two sides of a seam. Every wire must join an existing output of A to an existing
      input of B of the same port type, and no `json` port may be wired. Every required input of B must be
      wired or listed with --external NAME (fed by something other than A).

A mismatch means the vault is under-specified: fix the docs, never one of the derivations. Exit 1 on any mismatch.
"""
import json
import sys


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ports(decl, side):
    return {p["name"]: p for p in decl.get("ports", {}).get(side, [])}


def facts(decl):
    ins, outs = _ports(decl, "inputs"), _ports(decl, "outputs")
    needs, changes, guar = decl.get("needs", {}), decl.get("changes", {}), decl.get("guarantees", {})
    return {
        "identity.kind": decl.get("identity", {}).get("kind"),
        "inputs": {n: (p.get("type"), p.get("required", True)) for n, p in ins.items()},
        "outputs": {n: p.get("type") for n, p in outs.items()},
        "needs.external": sorted(e.get("ref") for e in needs.get("external", [])),
        "changes.effect_class": changes.get("effect_class"),
        "changes.effects": sorted(e.get("resource_key") for e in changes.get("effects", [])),
        "failure_modes": sorted(m.get("reason_code") for m in guar.get("failure_modes", [])),
        "checks": {c["id"]: (c.get("anchor"), c.get("over"), c.get("applies_at")) for c in guar.get("checks", [])},
    }


def compare(a, b):
    fa, fb = facts(a), facts(b)
    out = []
    for k in fa:
        if fa[k] != fb[k]:
            out.append(f"{k}: A={fa[k]!r} B={fb[k]!r}")
    return out


def seam(prod, cons, wires, external):
    outs, ins = _ports(prod, "outputs"), _ports(cons, "inputs")
    out, wired = [], set()
    for w in wires:
        o, i = w.split("=", 1)
        if o not in outs:
            out.append(f"wire {w}: producer has no output port {o!r}")
            continue
        if i not in ins:
            out.append(f"wire {w}: consumer has no input port {i!r}")
            continue
        to, ti = outs[o].get("type"), ins[i].get("type")
        if to != ti:
            out.append(f"wire {w}: type {to!r} does not match {ti!r}")
        if "json" in (to, ti):
            out.append(f"wire {w}: a json port is wired (rule wired_ports_named)")
        wired.add(i)
    for name, p in ins.items():
        if p.get("required", True) and name not in wired and name not in external:
            out.append(f"consumer input {name!r} is required but neither wired nor --external")
    return out


def main(argv):
    args, wires, external = list(argv), [], set()
    def take(flag):
        i = args.index(flag)
        v = args[i + 1]
        del args[i:i + 2]
        return v
    while "--wire" in args:
        wires.append(take("--wire"))
    while "--external" in args:
        external.add(take("--external"))
    if args[:1] == ["--compare"] and len(args) == 3:
        problems = compare(_load(args[1]), _load(args[2]))
    elif "--producer" in args and "--consumer" in args:
        problems = seam(_load(take("--producer")), _load(take("--consumer")), wires, external)
    else:
        print(__doc__)
        return 2
    for p in problems:
        print("mismatch:", p)
    print("agree" if not problems else f"{len(problems)} mismatch(es)")
    return 1 if problems else 0
