#!/usr/bin/env python3
"""Assemble a system description from per-area fragments.

A large engine is written area by area. Each area has a component file (`components-<area>.yaml`) and a fragment
(`_parts/<area>.yaml`, a plain mapping without `kind`). `_parts/_system.yaml` holds what belongs to the system as a
whole. This tool merges them into `system.yaml` and writes the per-target parts into the engine specs named there.

    python tools/so_assemble.py examples/systems/strata [--dry-run]

Fragment keys: flows, declares, policies, states, invariants, composition_<key>, policy_target_<key>,
residency_<key>, optional_policies, model_additions, uncatalogued_mechanisms, notes.

A policy is written once, without anything that depends on the machine. What it needs on one target (the pool it
controls, its budget) goes in `policy_target_<key>` as entries with the policy's id; they are merged into the policy
when it is written to that target's spec. `optional_policies` are policies of features that are off by default; they
stay in the fragment as a record and are not written to any spec. `residency_<key>` entries are added to that
target's `binding.residency`; an entry with the same data, pool, allocation and policy replaces the one there.
`_system.yaml` keys: every `system` field written by hand, plus
    assemble:
      area_order: [loading, ...]            # optional; default alphabetical
      specs: {<key>: <engine_spec id>}      # composition_<key> goes to this spec
      model: <model id>                     # where model_additions are reported against
      prefer: {<state, policy or invariant id>: <area>}   # whose wording stands when two areas write one id
"""
import argparse
import pathlib
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent


class Problem(Exception):
    pass


def load_docs(path):
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]


def find_file(kind, ident):
    for p in sorted((ROOT / "examples").rglob("*.yaml")):
        if "_parts" in p.parts:
            continue
        try:
            docs = load_docs(p)
        except yaml.YAMLError:
            continue
        for d in docs:
            if d.get("kind") == kind and d.get("id") == ident:
                return p, docs
    raise Problem(f"no {kind} with id {ident}")


def merge_by_id(existing, incoming, what, problems, key="id", prefer=None):
    """Incoming entries replace existing ones with the same id. Two areas writing one id differently is a problem
    unless `prefer` names the area whose wording stands for that id."""
    seen = {}
    prefer = prefer or {}
    for area, item in incoming:
        k = item.get(key)
        if k in seen and seen[k][1] != item:
            if prefer.get(k) == area:
                seen[k] = (area, item)
            elif prefer.get(k) != seen[k][0]:
                problems.append(f"{what} `{k}` is written differently by {seen[k][0]} and {area}; "
                                f"name the one that stands under assemble.prefer in _system.yaml")
            continue
        seen[k] = (area, item)
    out, used = [], set()
    for item in existing:
        k = item.get(key)
        if k in seen:
            out.append(seen[k][1])
            used.add(k)
        else:
            out.append(item)
    out += [item for k, (_, item) in seen.items() if k not in used]
    return out


def deep_merge(base, extra):
    out = dict(base)
    for k, v in extra.items():
        # a budget is one value: the target's budget replaces the policy's, it is not mixed into it
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "budget" else v
    return out


def dump(doc):
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=118)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sysdir = args.directory if args.directory.is_absolute() else (pathlib.Path.cwd() / args.directory)
    parts_dir = sysdir / "_parts"
    header = yaml.safe_load((parts_dir / "_system.yaml").read_text(encoding="utf-8"))
    asm = header.pop("assemble", {})
    sys_id = header["id"]

    areas = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) or {}
             for p in sorted(parts_dir.glob("*.yaml")) if p.stem != "_system"}
    order = [a for a in asm.get("area_order", []) if a in areas] + \
            [a for a in areas if a not in asm.get("area_order", [])]
    problems, notes = [], []

    # components of this system
    comps = {}
    for p in sorted(sysdir.glob("*.yaml")):
        for d in load_docs(p):
            if d.get("kind") == "component" and d.get("system") == sys_id:
                if d["id"] in comps:
                    problems.append(f"component {d['id']} is defined in {comps[d['id']][0]} and {p.name}")
                comps[d["id"]] = (p.name, d)
    top = [cid for cid, (_, d) in comps.items() if not d.get("parent")]
    want = header.pop("components", None) or []
    top_sorted = [c for c in want if c in top] + [c for c in top if c not in want]
    for c in want:
        if c not in top:
            problems.append(f"_system.yaml lists {c} as top-level, but no such top-level component is written")
    for cid, (fname, d) in comps.items():
        par = d.get("parent")
        if par and par not in comps:
            problems.append(f"{cid} ({fname}) has parent {par}, which is not written")
        elif par and cid not in (comps[par][1].get("parts") or []):
            problems.append(f"{cid} names parent {par}, but that component's `parts` does not list it")
        for part in d.get("parts") or []:
            if part not in comps:
                problems.append(f"{cid} lists part {part}, which is not written")
            elif comps[part][1].get("parent") != cid:
                problems.append(f"{cid} lists part {part}, whose `parent` is {comps[part][1].get('parent')}")

    # flows
    flows, flow_owner = [], {}
    ends = set(comps) | {"external", "model_files"}
    for a in order:
        for f in areas[a].get("flows") or []:
            fid = f.get("id")
            if fid in flow_owner:
                problems.append(f"flow `{fid}` is declared by both {flow_owner[fid]} and {a}")
                continue
            flow_owner[fid] = a
            for end in ("sender", "receiver"):
                if f.get(end) not in ends:
                    problems.append(f"flow `{fid}` ({a}): {end} {f.get(end)} is not a written component")
            flows.append(f)

    # declares
    declares = {k: list(v) for k, v in (header.pop("declares", None) or {}).items()}
    for a in order:
        for k, names in (areas[a].get("declares") or {}).items():
            for n in names or []:
                if n not in declares.setdefault(k, []):
                    declares[k].append(n)

    uncat = list(header.pop("uncatalogued_mechanisms", None) or [])
    for a in order:
        uncat += areas[a].get("uncatalogued_mechanisms") or []
        for n in areas[a].get("notes") or []:
            notes.append((a, n))

    system = {"kind": "system", **header}
    system["components"] = top_sorted
    system["declares"] = declares
    system["flows"] = flows
    if uncat:
        system["uncatalogued_mechanisms"] = uncat
    # keep hand-written order: put coverage last
    if "coverage" in system:
        system["coverage"] = system.pop("coverage")

    writes = [(sysdir / "system.yaml",
               f"# Assembled by tools/so_assemble.py from _parts/. Edit the fragments, not this file.\n" + dump(system))]

    # per-target parts into the engine specs
    policies = [(a, p) for a in order for p in areas[a].get("policies") or []]
    states = [(a, s) for a in order for s in areas[a].get("states") or []]
    invs = [(a, i) for a in order for i in areas[a].get("invariants") or []]
    for key, spec_id in (asm.get("specs") or {}).items():
        path, docs = find_file("engine_spec", spec_id)
        if len(docs) != 1:
            raise Problem(f"{path} holds more than one document")
        spec = docs[0]
        entries = [(a, e) for a in order for e in areas[a].get(f"composition_{key}") or []]
        refs = {}
        for a, e in entries:
            r = e.get("component_ref")
            if r not in comps:
                problems.append(f"composition_{key} ({a}): {r} is not a written component")
            if r in refs:
                problems.append(f"composition_{key}: {r} has an entry from both {refs[r]} and {a}")
            refs[r] = a
        for cid, (_, cd) in comps.items():
            if cid not in refs and not cd.get("parts"):
                problems.append(f"composition_{key}: no entry for {cid}")
        spec["composition"] = {"components": merge_by_id([], entries, f"composition_{key} entry", problems)}
        declared_states = set(declares.get("states") or [])
        pol = spec.get("policy") if isinstance(spec.get("policy"), dict) else {}
        active = {r for _, e in entries if e.get("active", True) for r in [e.get("component_ref")]}
        run_here = {p for cid in active if cid in comps for p in comps[cid][1].get("policies") or []}
        extra = {}
        for a in order:
            for e in areas[a].get(f"policy_target_{key}") or []:
                extra[e["id"]] = deep_merge(extra.get(e["id"], {}), e)
        here = [(a, deep_merge(p, extra.get(p.get("id"), {}))) for a, p in policies if p.get("id") in run_here]
        # policies come from the fragments alone, so one removed from a fragment also leaves the spec
        pol["policies"] = merge_by_id([],
                                      here, "policy", problems, prefer=asm.get("prefer"))
        spec["policy"] = pol
        bind = spec.get("binding") if isinstance(spec.get("binding"), dict) else {}
        res = list(bind.get("residency") or [])
        rkey = lambda r: (r.get("data"), r.get("pool"), r.get("allocation", "pinned"), r.get("by_policy"))
        for a in order:
            for r in areas[a].get(f"residency_{key}") or []:
                res = [x for x in res if rkey(x) != rkey(r)] + [r]
        if res:
            bind["residency"] = res
            spec["binding"] = bind
        st = spec.get("state") if isinstance(spec.get("state"), dict) else {}
        st["states"] = merge_by_id(st.get("states") or [], states, "state", problems, prefer=asm.get("prefer"))
        st["invariants"] = merge_by_id(st.get("invariants") or [], invs, "invariant", problems, prefer=asm.get("prefer"))
        spec["state"] = st
        for s in st["states"]:
            if s["id"] not in declared_states:
                problems.append(f"{spec_id}: state `{s['id']}` is not declared by the system")
        writes.append((path, dump(spec)))

    # model additions are reported, not written: the model description is a Given and is edited by hand
    additions = [(a, m) for a in order for m in areas[a].get("model_additions") or []]

    print(f"{sys_id}: {len(comps)} components ({len(top_sorted)} top-level), {len(flows)} flows, "
          f"{len(policies)} policies, {len(states)} states, {len(uncat)} uncatalogued mechanisms")
    if additions:
        print(f"\nModel additions asked for ({asm.get('model', 'model not named')}):")
        for a, m in additions:
            print(f"  [{a}] {yaml.safe_dump(m, allow_unicode=True, default_flow_style=True, width=1000).strip()}")
    if problems:
        print(f"\n{len(problems)} problems:")
        for p in problems:
            print("  - " + p)
    if not args.dry_run:
        for path, text in writes:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
        (parts_dir / "NOTES.md").write_text(
            "# Notes collected from the area fragments\n\n" +
            "\n".join(f"- **{a}**: {n}" for a, n in notes) + "\n", encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Problem as e:
        print(f"error: {e}")
        sys.exit(2)
