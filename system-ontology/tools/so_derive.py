#!/usr/bin/env python3
"""Derive the description of an engine that is being designed from the descriptions of existing engines.

    python tools/so_derive.py examples/systems/muse              # write system.yaml, components.yaml, the report
    python tools/so_derive.py examples/systems/muse --dry-run    # say what would be written and what is wrong
    python tools/so_derive.py examples/systems/muse --unread     # print the source's texts not yet listed as read

The rule the tool keeps. Every text it writes comes from one of two places, and it says which:
  * it was written for this engine in `_derive.yaml` (`set`, `restate`, `new`, `flows.set`, `flows.add`,
    `verification`, the fields of `system`), or
  * it is the source's text, word for word or with a replacement stated under `rewrite`, and `_derive.kept.yaml`
    lists it as read against this engine, pinned to the text that was read.
The tool never changes a text by itself, and a text of the source that is not listed is not written. When anything is
wrong it writes nothing and exits with 1.

`_derive.yaml`:
    system:        every hand-written field of the new system (id, title, summary, product, targets, mechanisms, ...)
    id_prefix:     comp/<name>
    sources:       [{system, main_source, consulted_for}]   existing engines; the first main_source supplies the flows
    declares:      {stages, states, policies}                names that exist in the new engine besides the model's
    carry:         [{from, as: reused|adapted, id?, adaptation?, also_from?, set?, remove?, rewrite?, restate?}]
                     also_from: [{component, took}]          what was taken from a second source component
                     rewrite:   [{old, new}]                 a replacement inside the source's texts
                     restate:   {decisions: {<id>: text}}    one statement said again whole
    not_carried:   [{component, why: does_not_apply|postponed, note}]
    new:           [component documents written by hand, without kind and system]
    flows:         {drop: [ids], set: {<id>: {description, id, timing}}, add: [flows]}
    verification:  {<local id>: [{method, checks, ...}]}
    source_only_terms: [{term, why}]                         words of the source the descriptions cannot tell
    timings:       {<timing of the source>: <timing here>}   a unit of work the source has and this engine has not

`_derive.kept.yaml`:
    read_by:  who read the listed texts, and when
    reused:   {<local id>: {source: <pin of the whole source component>, because}}
    keep:     {<local id>: {responsibility: {pin, text, because},
                            <list field>: [{id or name, pin, text, because}]}}
    flows:    {<flow id of the source>: {pin, text, because}}
    allow:    [{object, found, text, because}]               a true sentence that a word rule finds
A pin is the first 12 hex digits of the sha256 of the item as it would be written. `because` says what in this
engine's model, machine or scope the text rests on. An entry whose pin matches nothing is a problem: the source's text
is no longer the one that was read.

What is carried from a source component:
  reused   the whole component, unchanged. Refused when anything would have to change: a name this engine does not
           have, a timing, a part that is not carried, a value of a decision.
  adapted  its title, role, timings, state and the names of what it performs, with names this engine does not have
           removed (each removal is in the report); its responsibility and each item of its lists (resources,
           decisions, invariants, calls, observation points, boundary notes, capabilities) only when listed as read
           or given by hand. A decision is carried without its value. Its equivalence claim is never carried.
Flows are carried when both ends are carried; a flow's description is the source's text and follows the same rule.
"""
import argparse
import collections
import copy
import hashlib
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import so_leftovers as lo  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

COPIED = ["title", "role", "responsibility", "not_responsible_for", "runs", "implements_stages", "performs", "state",
          "needs_resources", "policies", "decisions", "invariants", "calls", "requires_capabilities",
          "provides_capabilities", "observation_points", "equivalence", "mechanisms"]
ORDER = ["kind", "id", "system", "parent", "title", "role", "responsibility", "not_responsible_for", "parts", "runs",
         "implements_stages", "performs", "state", "needs_resources", "policies", "decisions", "invariants", "calls",
         "verification", "requires_capabilities", "provides_capabilities", "observation_points", "equivalence",
         "mechanisms", "derived_from", "sources"]
# Fields of a component whose items are statements in words. An adapted component keeps an item only when read.
LISTS = ("not_responsible_for", "needs_resources", "decisions", "invariants", "calls", "observation_points",
         "requires_capabilities", "provides_capabilities")
SHORT = 15                                                       # a reason shorter than this says nothing


def pin(item):
    return hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def label_of(x):
    return (x.get("id") or x.get("name")) if isinstance(x, dict) else None


def main_text(x):
    """The sentence of an item, for a person who reads the list of kept texts."""
    if isinstance(x, str):
        return x
    for k in ("text", "purpose", "when", "what", "description", "summary"):
        if isinstance(x.get(k), str):
            return x[k]
    return next((v for v in x.values() if isinstance(v, str)), "")


def other_texts(x):
    """What an item says besides its sentence (a note, a second field), so that a reader of the list sees all of it."""
    if not isinstance(x, dict):
        return []
    main = main_text(x)
    return [f"{k}: {v}" for k, v in x.items() if isinstance(v, str) and v != main and k not in ("id", "name", "resource", "resolved_at")]


def shown(x, p):
    """One entry of the list of kept texts for an item, without its reason."""
    return {**({"id": label_of(x)} if label_of(x) else {}), "pin": p, "text": main_text(x),
            **({"also": other_texts(x)} if other_texts(x) else {}), "because": ""}


def load_all(root):
    """Every description under examples/, and the files that could not be read."""
    objs, errors = {}, []
    for p in sorted((root / "examples").rglob("*.yaml")):
        if "_parts" in p.parts or p.name.startswith("_"):
            continue
        try:
            for d in yaml.safe_load_all(p.read_text(encoding="utf-8")):
                if isinstance(d, dict) and "id" in d and "kind" in d:
                    objs.setdefault(d["id"], d)
        except yaml.YAMLError as e:
            errors.append(f"{p.relative_to(root).as_posix()} could not be read: {str(e).splitlines()[0]}")
    return objs, errors


def reword(x, old, new):
    if isinstance(x, str):
        return x.replace(old, new)
    if isinstance(x, list):
        return [reword(v, old, new) for v in x]
    if isinstance(x, dict):
        return {k: reword(v, old, new) for k, v in x.items()}
    return x


def derive(directory, root=ROOT):
    """What the derivation list of `directory` gives. Returns {system, components, report, problems, counts, unread}.
    Nothing is written here."""
    d = pathlib.Path(directory)
    spec = yaml.safe_load((d / "_derive.yaml").read_text(encoding="utf-8"))
    kept_path = d / "_derive.kept.yaml"
    kept = (yaml.safe_load(kept_path.read_text(encoding="utf-8")) or {}) if kept_path.exists() else {}
    objs, problems = load_all(root)
    report, unread = [], {"keep": {}, "flows": {}}
    counts = collections.Counter()
    sysdoc = dict(spec["system"])
    sid, prefix = sysdoc["id"], spec["id_prefix"]
    objs = {k: v for k, v in objs.items() if k != sid and v.get("system") != sid}   # never a source of itself

    # names that exist in the new engine
    model_ops, model_data = set(), set()
    for t in sysdoc.get("targets", []):
        m = objs.get(t["model"])
        if m is None or m.get("kind") != "model":
            problems.append(f"model {t['model']} not found")
            continue
        model_ops |= {o["id"] for o in m.get("operations", [])}
        model_data |= {x["id"] for x in m.get("data", [])}
    dec = spec.get("declares", {})
    stages, states, policies = set(dec.get("stages", [])), set(dec.get("states", [])) | model_data, set(dec.get("policies", []))

    source_ids = [s["system"] for s in spec.get("sources", [])]
    for s in source_ids:
        if objs.get(s, {}).get("kind") != "system":
            problems.append(f"sources: {s} is not a system that could be read")

    idmap = {}
    for c in spec.get("carry", []):
        if c.get("as") not in ("reused", "adapted"):
            problems.append(f"carry: {c.get('from')} has as: {c.get('as')!r}; it must be reused or adapted")
        src = objs.get(c["from"])
        if src is None or src.get("kind") != "component":
            problems.append(f"carry: {c['from']} not found")
            continue
        if src.get("system") not in source_ids:
            problems.append(f"carry: {c['from']} belongs to {src.get('system')}, which is not listed under sources")
        local = c.get("id") or c["from"].split("/")[-1]
        if c["from"] in idmap:
            problems.append(f"carry: {c['from']} is carried twice")
        idmap[c["from"]] = f"{prefix}/{local}"

    cmp = lo.compare(objs, sysdoc, spec.get("sources", []), spec.get("source_only_terms"))
    problems += [f"cannot compare with the source: {x}" for x in cmp["cannot"]]
    rules = cmp["rules"]
    timing_map = spec.get("timings") or {}
    carried_locals = {(c.get("id") or c["from"].split("/")[-1]) for c in spec.get("carry", [])}
    for section in ("keep", "reused"):
        for name in (kept.get(section) or {}):
            if name not in carried_locals:
                problems.append(f"_derive.kept.yaml: {section} names {name}, which is not carried")

    def reason_ok(entry, where):
        if len(str((entry or {}).get("because", "")).strip()) < SHORT:
            problems.append(f"_derive.kept.yaml: {where} gives no reason (`because`) for being kept")

    def prune(cid, field, values, known, what):
        for v in values:
            if v not in known:
                report.append(f"{cid}: removed {what} `{v}` from {field} (it does not exist in this engine)")
        return [v for v in values if v in known]

    comps = []
    for c in spec.get("carry", []):
        src = objs.get(c["from"])
        if src is None or src.get("kind") != "component":
            continue
        cid = idmap[c["from"]]
        local = cid.split("/")[-1]
        as_ = c.get("as")
        out = {"kind": "component", "id": cid, "system": sid}
        for k in COPIED:
            if k in src:
                out[k] = copy.deepcopy(src[k])
        whole = copy.deepcopy({k: out[k] for k in COPIED if k in out})
        if src.get("parent") in idmap:
            out["parent"] = idmap[src["parent"]]
        elif src.get("parent"):
            report.append(f"{cid}: its parent in the source, {src['parent'].split('/')[-1]}, is not carried; unless `set` gives "
                          f"a parent it stands at the top level here")
        if as_ != "reused":
            for dcs in out.get("decisions", []):
                dcs.pop("value", None)
                dcs.pop("source", None)
        before_names = len(report)
        if timing_map and "runs" in out:                         # a unit of work of the source that this engine lacks
            mapped = list(dict.fromkeys(timing_map.get(t, t) for t in out["runs"]))
            if mapped != out["runs"]:
                report.append(f"{cid}: timings {', '.join(out['runs'])} written as {', '.join(mapped)}")
                out["runs"] = mapped
        if "implements_stages" in out:
            out["implements_stages"] = prune(cid, "implements_stages", out["implements_stages"], stages, "stage")
        if "performs" in out:
            out["performs"] = prune(cid, "performs", out["performs"], model_ops, "operation")
        if "policies" in out:
            out["policies"] = prune(cid, "policies", out["policies"], policies, "policy")
        if "state" in out:
            for rel in ("owns", "reads", "writes"):
                if rel in out["state"]:
                    out["state"][rel] = prune(cid, f"state.{rel}", out["state"][rel], states, "state")
            out["state"] = {k: v for k, v in out["state"].items() if v}
        if "mechanisms" in out:
            out["mechanisms"] = prune(cid, "mechanisms", out["mechanisms"], set(sysdoc.get("mechanisms", [])), "mechanism")
        names_changed = len(report) - before_names

        if as_ == "reused":
            # Carried whole and unchanged, and read as a whole: the pin is of the source component.
            entry = (kept.get("reused") or {}).get(local)
            missing = [p for p in src.get("parts", []) if p not in idmap]
            hand = [k for k in ("set", "remove", "rewrite", "restate") if c.get(k)]
            if names_changed or missing or hand:
                why = ([f"{names_changed} names or timings had to change"] if names_changed else []) + \
                      ([f"its parts {', '.join(p.split('/')[-1] for p in missing)} are not carried"] if missing else []) + \
                      ([f"the list gives {', '.join(hand)} for it"] if hand else [])
                problems.append(f"carry: {c['from']} is marked reused, but {'; '.join(why)}. Mark it adapted and say what changed.")
            if entry is None:
                problems.append(f"carry: {c['from']} is reused, and _derive.kept.yaml does not list it under `reused` as read")
            else:
                reason_ok(entry, f"reused {local}")
                if entry.get("source") != pin(whole):
                    problems.append(f"_derive.kept.yaml: reused {local} was read as {entry.get('source')}; the source "
                                    f"component is now {pin(whole)}")
            counts["components carried whole"] += 1
        else:
            overridden = set(c.get("set") or {}) | set(c.get("remove") or [])
            restated = {(f, i) for f, by in (c.get("restate") or {}).items() for i in by}
            for field, by_id in (c.get("restate") or {}).items():
                ids = {x.get("id") for x in out.get(field, []) if isinstance(x, dict)}
                for iid, new_text in by_id.items():
                    if iid not in ids:
                        problems.append(f"carry: {c['from']} restates {field} `{iid}`, which the source does not have")
                for x in out.get(field, []):
                    if isinstance(x, dict) and x.get("id") in by_id:
                        x["text"] = by_id[x["id"]]
            plain = {f: [pin(x) for x in out.get(f, [])] for f in LISTS}
            plain_resp = pin(out.get("responsibility"))
            for rw in c.get("rewrite") or []:
                before = copy.deepcopy(out)
                for k in list(out):
                    if k not in ("kind", "id", "system", "parent"):
                        out[k] = reword(out[k], rw["old"], rw["new"])
                if out == before:
                    problems.append(f"carry: {c['from']} rewrites {rw['old']!r}, which its text does not contain")
            mine = (kept.get("keep") or {}).get(local) or {}
            for f in mine:
                if f != "responsibility" and f not in LISTS:
                    problems.append(f"_derive.kept.yaml: keep {local} names the field {f}, which is not one that is kept by list")
            # the responsibility: given by hand, or the source's and read
            if "responsibility" in out and "responsibility" not in overridden:
                e = mine.get("responsibility")
                if e is None:
                    problems.append(f"carry: {c['from']}: its responsibility is the source's text and is neither given under "
                                    f"`set` nor listed as read")
                    unread["keep"].setdefault(local, {})["responsibility"] = {
                        "pin": pin(out["responsibility"]), "text": out["responsibility"], "because": ""}
                else:
                    reason_ok(e, f"keep {local} responsibility")
                    if e.get("pin") != pin(out["responsibility"]):
                        problems.append(f"_derive.kept.yaml: keep {local} responsibility was read as {e.get('pin')}; the text "
                                        f"is now {pin(out['responsibility'])}: {out['responsibility'][:90]}")
                    counts["source texts kept with a stated replacement" if pin(out["responsibility"]) != plain_resp
                           else "source texts kept word for word"] += 1
            for field in LISTS:
                if field not in out or field in overridden:
                    if field in mine and field in overridden:
                        problems.append(f"_derive.kept.yaml: keep {local} lists {field}, which the derivation list gives by hand")
                    continue
                listed_here = mine.get(field) or []
                if any(not isinstance(e, dict) or "pin" not in e for e in listed_here):
                    problems.append(f"_derive.kept.yaml: keep {local} {field} has entries without a pin; each kept text is "
                                    f"listed as {{pin, text, because}}")
                    listed_here = [e for e in listed_here if isinstance(e, dict) and "pin" in e]
                wanted = {e.get("pin"): e for e in listed_here}
                left, used = [], set()
                for i, x in enumerate(out[field]):
                    p = pin(x)
                    if (field, label_of(x)) in restated:
                        left.append(x)                           # said again whole for this engine
                    elif p in wanted:
                        left.append(x)
                        used.add(p)
                        reason_ok(wanted[p], f"keep {local} {field} {label_of(x) or main_text(x)[:40]!r}")
                        counts["source texts kept with a stated replacement" if p != plain[field][i]
                               else "source texts kept word for word"] += 1
                    else:
                        unread["keep"].setdefault(local, {}).setdefault(field, []).append(shown(x, p))
                for p, e in wanted.items():
                    if p not in used:
                        problems.append(f"_derive.kept.yaml: keep {local} {field} lists {e.get('id') or str(e.get('text'))[:60]!r} "
                                        f"as read with pin {p}; no item of the source has that text now")
                if len(left) < len(out[field]):
                    report.append(f"{cid}: {len(out[field]) - len(left)} of the source's {len(out[field])} {field} not carried "
                                  f"(not listed as read)")
                out[field] = left
            if "equivalence" in out and "equivalence" not in overridden:
                del out["equivalence"]
                report.append(f"{cid}: the source's equivalence claim not carried")
            for k, v in (c.get("set") or {}).items():
                out[k] = v
            for k in c.get("remove") or []:
                out.pop(k, None)
            if len(str(c.get("adaptation", "")).strip()) < SHORT:
                problems.append(f"carry: {c['from']} is adapted but does not say what was changed (adaptation)")
        out = {k: v for k, v in out.items() if v not in ([], {}, None)}
        entries = [{"component": c["from"], "carried_as": as_, **({"adaptation": c["adaptation"]} if c.get("adaptation") else {})}]
        for a in c.get("also_from") or []:
            if not isinstance(a, dict) or len(str(a.get("took", "")).strip()) < SHORT:
                problems.append(f"carry: {c['from']}: also_from must say what was taken from each other component "
                                f"({{component, took}}); got {a!r}")
                continue
            other = objs.get(a["component"])
            if other is None or other.get("kind") != "component":
                problems.append(f"carry: {c['from']}: also_from names {a['component']}, which was not found")
            elif other.get("system") not in source_ids:
                problems.append(f"carry: {c['from']}: also_from names {a['component']} of {other.get('system')}, which is not "
                                f"listed under sources")
            entries.append({"component": a["component"], "carried_as": "adapted", "adaptation": a["took"]})
        out["derived_from"] = entries
        out["sources"] = [{"ref": e["component"], "basis": "proposal"} for e in entries]
        comps.append(out)
    for n in spec.get("new", []):
        out = {"kind": "component", "system": sid, **copy.deepcopy(n)}
        if "/" not in out["id"]:
            out["id"] = f"{prefix}/{out['id']}"
        out.setdefault("sources", [{"ref": "designed for this engine; no existing component was taken", "basis": "proposal"}])
        comps.append(out)
    for cid, n in collections.Counter(c["id"] for c in comps).items():
        if n > 1:
            problems.append(f"{cid} is the id of {n} components")

    by_id = {c["id"]: c for c in comps}
    for local, entries in (spec.get("verification") or {}).items():
        cid = f"{prefix}/{local}"
        if cid not in by_id:
            problems.append(f"verification: {cid} is not in the new engine")
        else:
            by_id[cid]["verification"] = entries
    for c in comps:
        par = c.get("parent")
        if par and "/" not in par:
            c["parent"] = par = f"{prefix}/{par}"
        if par and par not in by_id:
            problems.append(f"{c['id']}: parent {par} is not in the new engine")
    for c in comps:
        kids = [k["id"] for k in comps if k.get("parent") == c["id"]]
        if kids:
            c["parts"] = kids
            if c.get("role") != "subsystem":
                problems.append(f"{c['id']}: it has parts and its role is {c.get('role')}, not subsystem")
        elif c.get("role") == "subsystem":
            problems.append(f"{c['id']}: a subsystem with no parts")

    # A subsystem runs when its parts run. Its parts here are not the source's, so its timings come from them.
    schema = yaml.safe_load((root / "ontology" / "schema.yaml").read_text(encoding="utf-8"))
    timing_order = schema["defs"]["timing"]["enum"]

    def runs_of(c, seen=()):
        if not c.get("parts") or c["id"] in seen:
            return set(c.get("runs", []))
        return set().union(*[runs_of(by_id[k], seen + (c["id"],)) for k in c["parts"] if k in by_id])

    reused_ids = {idmap[c["from"]] for c in spec.get("carry", []) if c.get("as") == "reused" and c["from"] in idmap}
    for c in comps:
        if c.get("parts"):
            mine = [t for t in timing_order if t in runs_of(c)]
            if mine and mine != c.get("runs"):
                if c["id"] in reused_ids:
                    problems.append(f"{c['id']} is marked reused, but its timings would change to those of its parts here "
                                    f"({', '.join(mine)}). Mark it adapted.")
                report.append(f"{c['id']}: timings set from its parts: {', '.join(mine)}")
                c["runs"] = mine

    # every leaf of a main source is carried or listed with a reason
    carried_from = {dv["component"] for c in comps for dv in c.get("derived_from", [])}
    listed = {x["component"]: x for x in spec.get("not_carried", [])}
    derived = []
    for s in spec.get("sources", []):
        entry = {"system": s["system"], **({"consulted_for": s["consulted_for"]} if s.get("consulted_for") else {}),
                 "main_source": bool(s.get("main_source"))}
        src_comps = [o for o in objs.values() if o.get("kind") == "component" and o.get("system") == s["system"]]
        mine = [listed[o["id"]] for o in src_comps if o["id"] in listed]
        if mine:
            entry["not_carried"] = mine
        if s.get("main_source"):
            for o in src_comps:
                if o.get("parts"):
                    continue
                if o["id"] not in carried_from and o["id"] not in listed:
                    problems.append(f"{o['id']} is neither carried nor listed under not_carried")
                if o["id"] in carried_from and o["id"] in listed:
                    problems.append(f"{o['id']} is both carried and listed under not_carried")
        derived.append(entry)
    for cid, x in listed.items():
        o = objs.get(cid)
        if o is None:
            problems.append(f"not_carried: {cid} not found")
        elif o.get("system") not in source_ids:
            problems.append(f"not_carried: {cid} belongs to {o.get('system')}, which is not listed under sources")
        if len(str(x.get("note", "")).strip()) < SHORT:
            problems.append(f"not_carried: {cid} gives no reason in words (note)")

    # flows from the first main source
    flows, fspec = [], spec.get("flows", {})
    main = next((s["system"] for s in spec.get("sources", []) if s.get("main_source")), None)
    main_flows = objs.get(main, {}).get("flows", []) if main else []
    known_flows = {f["id"] for f in main_flows}
    known_refs = states | model_data | model_ops
    for fid in (fspec.get("drop") or []):
        if fid not in known_flows:
            problems.append(f"flows.drop: {fid} is not a flow of the main source")
    for fid in (fspec.get("set") or {}):
        if fid not in known_flows:
            problems.append(f"flows.set: {fid} is not a flow of the main source")
    kept_flows = kept.get("flows") or {}
    for fid in kept_flows:
        if fid not in known_flows:
            problems.append(f"_derive.kept.yaml: flows names {fid}, which is not a flow of the main source")
    for f in main_flows:
        if f["id"] in (fspec.get("drop") or []):
            report.append(f"flow {f['id']}: dropped by hand")
            continue
        ends = {}
        for end in ("sender", "receiver"):
            e = f[end]
            ends[end] = e if e in ("external", "model_files") else idmap.get(e)
        if None in ends.values():
            gone = [f[e].split("/")[-1] for e in ("sender", "receiver") if ends[e] is None]
            report.append(f"flow {f['id']}: not carried ({', '.join(gone)} is not in this engine)")
            continue
        g = copy.deepcopy(f)
        g.update(ends)
        g["timing"] = timing_map.get(g["timing"], g["timing"])
        given = (fspec.get("set") or {}).get(f["id"]) or {}
        if "description" in g and "description" not in given:
            e = kept_flows.get(f["id"])
            if e is None:
                problems.append(f"flow {f['id']}: its description is the source's text and is neither given under flows.set "
                                f"nor listed as read")
                unread["flows"][f["id"]] = {"pin": pin(g["description"]), "text": g["description"], "because": ""}
            else:
                reason_ok(e, f"flows {f['id']}")
                if e.get("pin") != pin(g["description"]):
                    problems.append(f"_derive.kept.yaml: flows {f['id']} was read as {e.get('pin')}; the text is now "
                                    f"{pin(g['description'])}")
                counts["source texts kept word for word"] += 1
        elif f["id"] in kept_flows:
            problems.append(f"_derive.kept.yaml: flows lists {f['id']}, whose description the derivation list gives by hand")
        for k, v in given.items():
            g[k] = v
        refs = g["carries"].get("refs")
        if refs:
            kept_refs = [r for r in refs if r in known_refs]
            if len(kept_refs) != len(refs):
                report.append(f"flow {f['id']}: removed {', '.join(r for r in refs if r not in kept_refs)} from refs")
            if kept_refs:
                g["carries"]["refs"] = kept_refs
            elif g["carries"]["content"] in ("weights", "model_state", "engine_state"):
                report.append(f"flow {f['id']}: not carried (nothing it carried exists in this engine)")
                continue
            else:
                g["carries"].pop("refs")
        flows.append(g)
    for f in fspec.get("add") or []:
        g = copy.deepcopy(f)
        for end in ("sender", "receiver"):
            if g[end] not in ("external", "model_files") and "/" not in g[end]:
                g[end] = f"{prefix}/{g[end]}"
            if g[end] not in ("external", "model_files") and g[end] not in by_id:
                problems.append(f"added flow {g['id']}: {end} {g[end]} is not in the new engine")
        flows.append(g)
    for fid, n in collections.Counter(f["id"] for f in flows).items():
        if n > 1:
            problems.append(f"{fid} is the id of {n} flows")

    top = [c["id"] for c in comps if not c.get("parent")]
    want = [f"{prefix}/{x}" if "/" not in x else x for x in spec.get("top_level_order", [])]
    sysdoc_out = {"kind": "system", **sysdoc}
    sysdoc_out["components"] = [x for x in want if x in top] + [x for x in top if x not in want]
    sysdoc_out["declares"] = {k: list(v) for k, v in dec.items()}
    sysdoc_out["flows"] = flows
    sysdoc_out["derived_from"] = derived
    if "coverage" in sysdoc_out:
        sysdoc_out["coverage"] = sysdoc_out.pop("coverage")

    ordered = lambda c: {k: c[k] for k in ORDER if k in c} | {k: v for k, v in c.items() if k not in ORDER}
    comps = [ordered(c) for c in comps]

    # the word rules, over everything that would be written; a true sentence they find is listed under `allow`
    names, _ = lo.own_names([sysdoc_out] + comps)
    own = (cmp["own"][0] | names, cmp["own"][1])
    allowed = collections.defaultdict(set)
    for a in kept.get("allow") or []:
        reason_ok(a, f"allow {a.get('object')} {a.get('found')!r}")
        allowed[(a.get("object"), a.get("text"))].add(str(a.get("found")).lower())
    used_allow = set()
    for x in lo.scan([sysdoc_out] + comps, rules, own):
        if x["found"].lower() in allowed.get((x["object"], x["text"]), ()):
            used_allow.add((x["object"], x["text"], x["found"].lower()))
            continue
        problems.append(f"{x['object']} {x['field']}: {x['found']!r} ({x['why']}). Text: {x['context']}")
    for (obj, text), founds in allowed.items():
        for f in founds:
            if (obj, text, f) not in used_allow:
                problems.append(f"_derive.kept.yaml: allow lists {f!r} in a text of {obj} that is not written, or in which no "
                                f"rule finds it")

    # the result must be a valid description
    import so_check as sc
    ws = sc.Workspace(root)
    for doc in [sysdoc_out] + comps:
        for i in ws.validate(doc):
            problems.append(f"not valid: {i.about}: {i.message}")

    total = sum(1 for doc in [sysdoc_out] + comps for _ in lo.prose(doc))
    hand_titles = {idmap[c["from"]] for c in spec.get("carry", []) if c["from"] in idmap and "title" in (c.get("set") or {})}
    counts["titles taken from the source as names"] = sum(1 for c in comps if c.get("derived_from") and c["id"] not in hand_titles
                                                           and c["id"] not in reused_ids and "title" in c)
    kept_n = counts["source texts kept word for word"] + counts["source texts kept with a stated replacement"]
    whole_texts = sum(1 for c in comps if c["id"] in reused_ids for _ in lo.prose(c))
    counts["texts in all"] = total
    counts["texts of components carried whole"] = whole_texts
    counts["texts written for this engine in the derivation list"] = total - kept_n - whole_texts - counts["titles taken from the source as names"]
    counts["components"] = len(comps)
    counts["reused"] = sum(1 for c in spec.get("carry", []) if c.get("as") == "reused")
    counts["adapted"] = sum(1 for c in spec.get("carry", []) if c.get("as") == "adapted")
    counts["new"] = len(spec.get("new", []))
    counts["not carried"] = len(listed)
    counts["flows"] = len(flows)
    counts["word patterns"] = len(rules)
    return {"system": sysdoc_out, "components": comps, "report": report, "problems": problems, "counts": dict(counts),
            "unread": unread, "read_by": kept.get("read_by")}


def summary(res):
    c = res["counts"]
    return [f"{c['components']} components ({c['reused']} reused, {c['adapted']} adapted, {c['new']} new), "
            f"{c['not carried']} not carried, {c['flows']} flows",
            f"{c['texts in all']} texts: {c['texts written for this engine in the derivation list']} written for this engine in "
            f"the derivation list; {c.get('source texts kept word for word', 0)} the source's word for word and "
            f"{c.get('source texts kept with a stated replacement', 0)} the source's with a stated replacement, each listed "
            f"as read; {c['titles taken from the source as names']} titles taken from the source as names; "
            f"{c['texts of components carried whole']} in components carried whole",
            f"read by: {res['read_by'] or 'not stated'}",
            f"{c['word patterns']} word patterns looked for in every text"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument("--unread", action="store_true",
                    help="print, in the form of _derive.kept.yaml, the source's texts that are not listed as read; "
                         "writes nothing")
    args = ap.parse_args()
    d = args.directory if args.directory.is_absolute() else pathlib.Path.cwd() / args.directory
    res = derive(d)
    if args.unread:
        n = sum(1 if f == "responsibility" else len(v) for c in res["unread"]["keep"].values() for f, v in c.items()) + len(res["unread"]["flows"])
        print(f"# {n} texts of the source that are not listed as read. Each is left out (an item of a list) or stops the\n"
              f"# derivation (a responsibility, a flow's description) until it is given by hand or listed with a reason.")
        print(yaml.safe_dump(res["unread"], allow_unicode=True, sort_keys=False, width=118))
        return 0
    print(f"{res['system']['id']}: " + "\n  ".join(summary(res)))
    for r in res["report"]:
        print("  . " + r)
    if res["problems"]:
        print(f"\n{len(res['problems'])} problems; nothing was written:")
        for p in res["problems"]:
            print("  - " + p)
        return 1
    if not args.dry_run:
        note = "# Generated by tools/so_derive.py from _derive.yaml. Edit that file, not this one.\n"
        dump = lambda x: yaml.safe_dump(x, allow_unicode=True, sort_keys=False, width=118)
        (d / "system.yaml").write_text(note + dump(res["system"]), encoding="utf-8")
        (d / "components.yaml").write_text(note + "---\n".join(dump(c) for c in res["components"]), encoding="utf-8")
        (d / "derivation-report.txt").write_text("\n".join(summary(res) + [""] + res["report"]) + "\n", encoding="utf-8")
        print(f"wrote {(d / 'system.yaml').relative_to(ROOT)}, components.yaml, derivation-report.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
