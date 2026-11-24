#!/usr/bin/env python3
"""Node types: write the thin draft, check it, describe an engine with it, and write the revised node ontology document.

    python tools/so_nodetypes.py thin [--min-engines 2] [--no-choices] [--no-gaps] [--out FILE]
    python tools/so_nodetypes.py example strata            # or a design: example muse-on-spark
    python tools/so_nodetypes.py suggest muse-on-spark     # a design: the types its source components have
    python tools/so_nodetypes.py repin muse-on-spark [NODE ...]
    python tools/so_nodetypes.py check
    python tools/so_nodetypes.py doc

thin      Write `ontology/node-types.draft.yaml` from the frozen draft 0.8 and `validation/thin/amendments-0.9.yaml`.
          A node type keeps what it is, what it takes and gives, what it must keep, and how far it can change the
          output. Of the choices it keeps those that at least `--min-engines` of the engines examined decide
          (`validation/choices/recurrence.yaml`). `--no-choices` leaves choices and `seen_in` out, for readers who
          must judge by the definitions alone. `--no-gaps` leaves `open_gaps` out, for readers who classify parts:
          the gaps describe the parts that have no type.
example   Write `examples/systems/<engine>/nodes.yaml`: the engine's node level under the node types. Each part
          names its type and how it settles that type's choices. Nothing is added that the inventory does not record.
          For a design, the type of every node is the one stated in the design's `node-assignment.yaml` (type, fit,
          basis, and a pin: the SHA-256 of the component's responsibility as it was read). A node with no entry, a
          type the draft does not have, a pin that no longer matches, a decision map that is stale or a packet that
          no longer matches the design is a problem; with any problem nothing is written and the exit status is 1.
suggest   For a design: print the types of the components each node is derived from, beside the stated type. A
          suggestion only; it is never written as the answer.
repin     For a design: list every node whose responsibility changed since it was read, old and new text side by
          side. The pin is updated only for the nodes named on the command line.
check     Check the draft against its own vocabulary and the engines examined, and read every nodes.yaml against
          the descriptions as they are now: `described_in`, `does`, pins, types, decisions and `own_decisions`.
doc       Write `NODE-ONTOLOGY-revised.md`. An opening written by hand is taken from
          `NODE-ONTOLOGY-revised.intro.md` when that file exists.
"""
import argparse
import collections
import datetime
import pathlib
import re
import statistics
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import so_nodetypes_experiments as X  # noqa: E402
import so_nodetypes_validate as VAL  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = X.ROOT
V = X.V
DRAFT = ROOT / "ontology" / "node-types.draft.yaml"
AMEND = V / "thin" / "amendments-0.9.yaml"
RECURRENCE = V / "choices" / "recurrence.yaml"


def latest(*names):
    """The directory of the latest run of a check: the first of `names` that holds results."""
    for n in names:
        if any((V / n).glob("*.yaml")) and ((V / n / "classification.yaml").exists() or (V / n / "selection.yaml").exists()):
            return V / n
    return V / names[-1]
ENGINE_NAMES = {"strata": "Strata", "ds4": "ds4", "hyperqwen": "HyperQwen", "ninfer": "NInfer", "splash": "Splash",
                "llama-cpp": "llama.cpp"}
KEEP = ("summary", "not", "applies_when", "forms", "takes", "gives", "state")


INLINE = ("effect_on_output", "seen_in", "also", "engines_examined", "nearest")


class _Inline(list):
    """A short list of names, written on one line."""


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(_Inline, lambda d, v: d.represent_sequence("tag:yaml.org,2002:seq", v, flow_style=True))


def _inline(x):
    if isinstance(x, dict):
        return {k: (_Inline(v) if k in INLINE and isinstance(v, list) else _inline(v)) for k, v in x.items()}
    if isinstance(x, list):
        return [_inline(v) for v in x]
    return x


def text(data):
    return yaml.dump(_inline(data), Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=118)


def seen_in():
    """type -> the engines examined that have a part of it."""
    out = collections.defaultdict(list)
    for e, parts in X.assignments().items():
        for t in sorted({t for ts in parts.values() for t in ts}):
            out[t].append(e)
    return out


# ---------------------------------------------------------------- thin

def thin(min_engines, with_choices, out, with_gaps=True):
    src, am = X.load(X.FROZEN), X.load(AMEND)
    level_of = {lv["was"]: lv["id"] for lv in am["effect_levels"]}
    new = lambda k: am["rename_fields"].get(k, k)
    engines = {}
    if with_choices:
        if not RECURRENCE.exists():
            raise SystemExit("no validation/choices/recurrence.yaml: run so_nodetypes_experiments.py recurrence, or pass --no-choices")
        rec = X.load(RECURRENCE)
        if len(rec["engines_mapped"]) < len(X.ENGINES):
            raise SystemExit(f"recurrence covers only {rec['engines_mapped']}")
        engines = {r["id"]: set(r["engines"]) for r in rec["choices"]}
    merged_away, merged_text = {}, {}
    for m in am.get("merge_choices") or []:
        into, rest = m["ids"][0], m["ids"][1:]
        for r in rest:
            merged_away[r] = into
            engines[into] = engines.get(into, set()) | engines.get(r, set())
        if m.get("what"):
            merged_text[into] = m["what"]
    seen = seen_in()
    types, kept_n, all_n = [], 0, 0
    for t in src["types"]:
        patch = (am.get("type_patches") or {}).get(t["id"], {}).get("set", {})
        n = {"id": t["id"], new("family"): t["family"]}
        for k in KEEP:
            v = patch.get(new(k), t.get(k))
            if v:
                n[new(k)] = v
        reached = {e["effect"] for e in t["effect_on_output"]}
        n["effect_on_output"] = [level_of[lv] for lv in level_of if lv in reached]
        if t.get("affects_output_through"):
            n["indirect_effect"] = True
        n["rules"] = [{"strength": r["strength"], "rule": r["rule"]} for r in patch.get("rules", t["rules"])]
        if with_choices:
            ch = []
            for cid, kind, what in X.frozen_choices()[t["id"]]:
                if cid in merged_away:
                    continue
                all_n += 1
                k = len(engines.get(cid, ()))
                if k >= min_engines:
                    ch.append({"what": merged_text.get(cid, what), "engines": k})
            kept_n += len(ch)
            if ch:
                n["choices"] = ch
            n["seen_in"] = seen.get(t["id"], [])
        types.append(n)
    doc = {"draft_version": am["draft_version"], "derived_from": "draft 0.8, frozen 2026-11-16",
           "engines_examined": X.ENGINES}
    if with_choices:
        doc["choices_kept_when"] = {"engines": min_engines, "of": len(X.ENGINES)}
    doc |= {"effect_levels": [{"id": lv["id"], "meaning": lv["meaning"]} for lv in am["effect_levels"]],
            "rule_strengths": am["rule_strengths"], "rule_scope": am["rule_scope"],
            "output_principles": am["output_principles"], "groups": src["families"], "types": types}
    if with_gaps:
        doc["open_gaps"] = am["open_gaps"]
    head = "".join(f"# {line}".rstrip() + "\n" for line in am["header"].splitlines())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(head + text(doc), encoding="utf-8")
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    msg = f"wrote {shown}: {len(types)} types, {sum(len(t['rules']) for t in types)} rules"
    if with_choices:
        msg += f", {kept_n} of {all_n} choices kept (decided in {min_engines}+ of {len(X.ENGINES)} engines)"
    print(msg + f", {len(out.read_text(encoding='utf-8').splitlines())} lines")
    return 0


# ---------------------------------------------------------------- example

def kept_choices(draft):
    """type -> text of each choice the thin draft keeps."""
    return {t["id"]: [c["what"] for c in t.get("choices", [])] for t in draft["types"]}


def node_types_of(n):
    return ([n["type"]] if n.get("type") else []) + list(n.get("also") or [])


def build_nodes(engine):
    """(the node level of an engine or a design as `example` writes it, problems). Nothing is written here.

    An examined engine's parts come from its inventory and their types from the key (validation/reference-assignment.yaml,
    or the held-out checker for llama.cpp). A design's parts are its leaf components, and their types are only those
    stated in its `node-assignment.yaml`, each pinned to the responsibility it was read against. How a node settles a
    choice comes from the reader's map of decisions to choices: for a design keyed by decision id and the text that was
    judged, for an examined engine through the packet the map was judged on, which must still match the inventory."""
    draft = X.load(DRAFT)
    order = [t["id"] for t in draft["types"]]
    becomes = X.draft_choice_of()
    design = engine in X.designs()
    problems = []
    ws = X.workspace()
    if design:
        assign, p = X.design_assignment(engine)
        problems += p
        decided, p = X.design_map(engine)
        problems += p
        problems += X.packet_problems(engine)
        entries = X.load(X.assignment_path(engine)).get("nodes") or {} if X.assignment_path(engine).exists() else {}
        parts = [{"id": part, "title": c.get("title") or part, "does": c["responsibility"], "cid": c["id"],
                  "decisions": [t for _, t in X.component_decisions(c)]} for part, c in X.design_components(engine).items()]
    elif engine in X.ENGINES:
        assign = X.assignments()[engine]
        decided, p = X.engine_map(engine)
        problems += p
        entries = {}
        described = {o["id"]: o for o in ws.of_kind("component")}
        prefix = next((c["id"].rsplit("/", 1)[0] for c in described.values() if c["system"].split("/")[-1] == engine), f"comp/{engine}")
        parts = [{"id": q["id"], "title": q.get("engine_name") or q["id"], "does": q["does"],
                  "cid": f"{prefix}/{q['id']}" if f"{prefix}/{q['id']}" in described else None,
                  "decisions": list(q.get("decisions") or [])} for q in X.inventory(engine)[0]]
    else:
        return None, [f"{engine} is neither an engine examined ({', '.join(X.ENGINES)}) nor a design ({', '.join(X.designs())})"]
    nodes = []
    for q in parts:
        if q["id"] not in assign:
            if not design:
                problems.append(f"{engine}/{q['id']}: no entry in the key")
            continue
        types = assign[q["id"]]
        node = {"component": q["id"], "title": q["title"]}
        if q["cid"]:
            node["described_in"] = q["cid"]
            src = ws.objects[q["cid"]].get("derived_from")
            if src:
                node["derived_from"] = [d["component"] for d in (src if isinstance(src, list) else [src])]
        node["type"] = types[0] if types else None
        if len(types) > 1:
            node["also"] = types[1:]
        if design:
            e = entries[q["id"]]
            if e.get("fit") != "clean":
                node["fit"] = e.get("fit")
                node["reason"] = e.get("reason")
            node["responsibility_sha256"] = e["responsibility_sha256"]
        node["does"] = q["does"]
        settles = collections.OrderedDict()
        rows = decided.get(q["id"], [])
        for _, text_, cid, fit in rows:
            to = becomes.get(cid) if fit == "covered" and cid else None
            if to and to[0] in types:
                settles.setdefault(to, []).append(text_)
        if settles:
            node["settles"] = [({"type": t} if len(types) > 1 else {}) | {"choice": w, "how": hows}
                               for (t, w), hows in settles.items()]
        own = len(q["decisions"]) - sum(len(h) for h in settles.values())
        if own:
            node["own_decisions"] = own
        nodes.append(node)
    nodes.sort(key=lambda n: order.index(n["type"]) if n["type"] in order else len(order))
    used = {t for n in nodes for t in node_types_of(n)}
    by_id = {t["id"]: t for t in draft["types"]}
    out = {"engine": engine, "node_types": f"ontology/node-types.draft.yaml, draft {draft['draft_version']}", "nodes": nodes,
           "types_without_a_part": [{"type": t} | ({"needed_when": by_id[t]["needed_when"]} if by_id[t].get("needed_when") else {})
                                    for t in order if t not in used]}
    return out, list(dict.fromkeys(problems))


def nodes_path(engine):
    if engine in X.designs():
        return X.workspace().files[X.designs()[engine]].parent / "nodes.yaml"
    return ROOT / "examples" / "systems" / engine / "nodes.yaml"


def assignment_reader(engine):
    """Who stated the node types of a design, as its node-assignment.yaml records it."""
    path = X.assignment_path(engine)
    return (X.load(path).get("read_by") if path.exists() else None) or None


def nodes_header(engine):
    if engine in X.designs():
        title = X.workspace().objects[X.designs()[engine]].get("title", engine)
        return (f"# The node level of {title} under the generic node types. Written by\n"
                f"# `tools/so_nodetypes.py example {engine}`. The type of each node is the one stated in node-assignment.yaml\n"
                "# beside this file, read from the component's own text and pinned to its responsibility\n"
                "# (`responsibility_sha256`); `fit` and `reason` appear where that reading found the type does not fit plainly.\n"
                + (f"# Who read: {assignment_reader(engine)}.\n" if assignment_reader(engine) else "") +
                "# `settles` names the choices of the type this design decides, with its decisions word for word, from\n"
                "# validation/choices/map-" + engine + ".yaml, keyed by decision id and text. `own_decisions` counts the\n"
                "# decisions of the component that are not a kept choice of its types. The full description of each\n"
                "# component is at `described_in`.\n")
    title = ENGINE_NAMES.get(engine, engine)
    return (f"# The node level of {title} under the generic node types. Written by\n"
            f"# `tools/so_nodetypes.py example {engine}` from validation/ (the parts inventory, the assignment of parts to\n"
            "# types, and the match of each recorded decision to a choice). Each node names its type and how this engine\n"
            "# settles the choices that type leaves open, in the words of the engine's inventory. `own_decisions` counts\n"
            "# the decisions recorded for the part that are not a choice of the type. Call interfaces, source lines and\n"
            "# the full list of parameters stay in the full description (`described_in`).\n")


def example(engine):
    out, problems = build_nodes(engine)
    if problems:
        for pr in problems:
            print("PROBLEM", pr)
        print(f"nothing written: {len(problems)} problems")
        return 1
    dst = nodes_path(engine)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(nodes_header(engine) + text(out), encoding="utf-8")
    nodes = out["nodes"]
    used = {t for n in nodes for t in node_types_of(n)}
    print(f"wrote {dst.relative_to(ROOT)}: {len(nodes)} nodes of {len(used)} types, "
          f"{sum(len(n.get('settles', [])) for n in nodes)} choices settled, "
          f"{sum(n.get('own_decisions', 0) for n in nodes)} decisions of its own")
    return 0


def suggest(design):
    """Print, beside the type stated for each node of a design, what the components it is derived from are in the
    key of the engines examined. A suggestion for whoever reads the component; nothing is written."""
    if design not in X.designs():
        print(f"PROBLEM {design} is not a design ({', '.join(X.designs())})")
        return 1
    path = X.assignment_path(design)
    stated = (X.load(path).get("nodes") or {}) if path.exists() else {}
    differ = 0
    for part, sug in X.suggestions(design).items():
        first = next((s["types"] for s in sug if s["types"]), None)
        e = stated.get(part)
        now = node_types_of(e) if isinstance(e, dict) else None
        mark = "" if now is None or first is None or now == first else "   <- the reading differs"
        differ += bool(mark)
        print(f"{part}: suggested {first or 'nothing (no source component has a type in the key)'}"
              + (f" from {', '.join(s['from'] for s in sug)}" if sug else "")
              + f"; stated {now if now is not None else 'nothing yet'}{mark}")
    print(f"\nThese suggestions come from what the components are derived from, not from their text. They are never "
          f"written as the answer: the type of each node is stated in {X.shown(path)}. {differ} readings differ from "
          "the suggestion.")
    return 0


def repin(design, names):
    """List every node of a design whose responsibility has changed since it was read, old and new text side by side.
    The pin of a node is updated only when the node is named, which says its entry has been read again against the
    new text and still holds."""
    if design not in X.designs():
        print(f"PROBLEM {design} is not a design ({', '.join(X.designs())})")
        return 1
    path = X.assignment_path(design)
    if not path.exists():
        print(f"PROBLEM no {X.shown(path)}")
        return 1
    raw = path.read_text(encoding="utf-8")
    head = "".join(ln for ln in raw.splitlines(keepends=True) if ln.startswith("#"))
    data = X.load(path)
    nodes = data.get("nodes") or {}
    comps = X.design_components(design)
    changed, status = [], 0
    for part, c in comps.items():
        e = nodes.get(part)
        if not isinstance(e, dict):
            print(f"{part}: no entry; read the component and write one")
            status = 1
            continue
        if e.get("responsibility_sha256") == X.sha(c["responsibility"]):
            continue
        changed.append(part)
        print(f"\n{part}: the responsibility has changed since it was read (type {node_types_of(e) or 'none'}, fit {e.get('fit')})")
        print(f"  read:  {X.squeeze(e.get('responsibility_read', '(the text read was not kept)'))}")
        print(f"  now:   {X.squeeze(c['responsibility'])}")
    for part in names:
        if part not in comps:
            print(f"PROBLEM {part} is not a node of {design}")
            status = 1
        elif part not in changed:
            print(f"{part}: its pin already matches; nothing to do")
    done = []
    for part in changed:
        if part not in names:
            status = 1
            continue
        e, c = nodes[part], comps[part]
        if not e.get("quote") or X.squeeze(e["quote"]) not in X.squeeze(c["responsibility"]):
            print(f"PROBLEM {part}: its quote is not in the new text; edit the entry (quote, basis, type) before repinning")
            status = 1
            continue
        e["responsibility_sha256"] = X.sha(c["responsibility"])
        e["responsibility_read"] = c["responsibility"]
        e["repinned_on"] = datetime.date.today().isoformat()
        done.append(part)
    if done:
        path.write_text(head + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=118), encoding="utf-8")
    left = [p for p in changed if p not in done]
    print(f"\n{len(changed)} nodes changed since they were read; repinned: {', '.join(done) or 'none'}; "
          f"still to read again: {', '.join(left) or 'none'}")
    return status


# ---------------------------------------------------------------- check

def check():
    d = X.load(DRAFT)
    problems, notes = [], []
    levels = [lv["id"] for lv in d["effect_levels"]]
    strengths = {s["id"] for s in d["rule_strengths"]}
    fams = {f["id"] for f in d["groups"]}
    ids = [t["id"] for t in d["types"]]
    if len(set(ids)) != len(ids):
        problems.append("two node types share an id")
    allowed = {"id", "group", "summary", "not", "needed_when", "forms", "takes", "gives", "owns_state", "effect_on_output",
               "indirect_effect", "rules", "choices", "seen_in"}
    for t in d["types"]:
        tid = t["id"]
        for k in set(t) - allowed:
            problems.append(f"{tid}: field {k} is not part of a node type")
        for k in ("summary", "takes", "gives", "effect_on_output", "rules"):
            if not t.get(k):
                problems.append(f"{tid}: {k} is missing")
        if t["group"] not in fams:
            problems.append(f"{tid}: group {t['group']} is not declared")
        for lv in t.get("effect_on_output", []):
            if lv not in levels:
                problems.append(f"{tid}: effect level {lv} is not declared")
        if t.get("effect_on_output") != [lv for lv in levels if lv in t.get("effect_on_output", [])]:
            problems.append(f"{tid}: effect levels are not in the declared order")
        for r in t.get("rules", []):
            if r.get("strength") not in strengths or not r.get("rule"):
                problems.append(f"{tid}: a rule needs a declared strength and a text")
        for c in t.get("choices", []):
            if c.get("engines", 0) < d.get("choices_kept_when", {}).get("engines", 0):
                problems.append(f"{tid}: choice '{c['what']}' is below the number of engines required")
    for f in fams - {t["group"] for t in d["types"]}:
        problems.append(f"group {f} has no type")
    for g in d.get("open_gaps", []):
        for t in g.get("nearest", []):
            if t not in ids:
                problems.append(f"open gap names an unknown type {t}")

    # against the dictionary: a name that is already a term there is used in the same meaning, or not at all
    terms = {t["term"] for t in X.load(ROOT / "ontology" / "dictionary.yaml")["terms"]}
    shared = X.load(AMEND).get("shared_terms") or {}
    used = (allowed | {"groups", "types", "effect_levels", "rule_strengths", "rule_scope", "output_principles", "open_gaps",
                       "strength", "rule", "what", "engines", "meaning", "nearest", "title", "about"}
            | set(levels) | strengths | fams | set(ids))
    for name in sorted(n for n in used if n.replace("-", "_") in terms and n not in shared):
        problems.append(f"'{name}' is a dictionary term with another meaning, or is not listed under shared_terms")
    for name in sorted(set(levels) | strengths):
        if name not in terms:
            problems.append(f"'{name}' is an enumerated value and has no dictionary entry")

    # against the engines examined
    seen = seen_in()
    for e, parts in X.assignments().items():
        inv = {p["id"] for p in X.inventory(e)[0]}
        for p, ts in parts.items():
            for t in ts:
                if t not in ids:
                    problems.append(f"{e}/{p} is assigned to an unknown type {t}")
        if inv - set(parts):
            problems.append(f"{e}: parts with no assignment: {sorted(inv - set(parts))}")
        none = [p for p, ts in parts.items() if not ts]
        if none:
            notes.append(f"{ENGINE_NAMES[e]}: {len(none)} of {len(parts)} parts have no type ({', '.join(none)})")
    for t in d["types"]:
        if "seen_in" in t and t["seen_in"] != seen.get(t["id"], []):
            problems.append(f"{t['id']}: seen_in does not match the assignments")
        if not seen.get(t["id"]):
            problems.append(f"{t['id']}: no engine examined has a part of this type")
        elif len(seen[t["id"]]) == 1:
            notes.append(f"{t['id']}: seen in one engine only ({ENGINE_NAMES[seen[t['id']][0]]})")

    # the node levels written with the types: each file is read against the descriptions as they are now
    kept = kept_choices(d)
    ws = X.workspace()
    for path in sorted((ROOT / "examples" / "systems").glob("*/nodes.yaml")):
        where = f"{path.parent.name}/nodes.yaml"
        before = len(problems)
        ex = X.load(path)
        e = ex.get("engine")
        design = e in X.designs()
        if design:
            assign, p = X.design_assignment(e)
            problems += [f"{where}: {x}" for x in p]
            entries = X.load(X.assignment_path(e)).get("nodes") or {} if X.assignment_path(e).exists() else {}
            parts = list(X.design_components(e))
            source = f"{X.shown(X.assignment_path(e))}, read from each component's own text"
        elif e in X.ENGINES:
            assign, entries = X.assignments()[e], {}
            parts = [p["id"] for p in X.inventory(e)[0]]
            source = ("validation/heldout/check-llama-cpp.yaml" if e == X.HELD_OUT else "validation/reference-assignment.yaml")
            notes.append(f"{where}: generated from {source}; comparing its types with that key detects only staleness, "
                         "not whether the types are right")
        else:
            problems.append(f"{where}: engine {e!r} is neither an engine examined nor a design")
            continue
        got = [n["component"] for n in ex["nodes"]]
        if sorted(got) != sorted(parts):
            problems.append(f"{where}: its nodes are not the parts of {e} (missing {sorted(set(parts) - set(got))}, "
                            f"extra {sorted(set(got) - set(parts))})")
        for n in ex["nodes"]:
            at = f"{where} {n['component']}"
            ts = node_types_of(n)
            for t in ts:
                if t not in ids:
                    problems.append(f"{at}: names the type '{t}', which the draft does not have")
            if n["component"] in assign and ts != assign[n["component"]]:
                problems.append(f"{at}: type {ts} differs from {source} ({assign[n['component']]})")
            comp = ws.objects.get(n.get("described_in")) if n.get("described_in") else None
            if comp is None or comp.get("kind") != "component":
                problems.append(f"{at}: described_in {n.get('described_in')!r} is not a component of the descriptions")
                continue
            if X.squeeze(n.get("does")) != X.squeeze(comp.get("responsibility")):
                problems.append(f"{at}: `does` is not the component's responsibility as it is now")
            if design:
                pin, now = n.get("responsibility_sha256"), X.sha(comp["responsibility"])
                stated = (entries.get(n["component"]) or {}).get("responsibility_sha256")
                if pin != now:
                    problems.append(f"{at}: its pin does not match the component's responsibility as it is now")
                if stated != pin:
                    problems.append(f"{at}: its pin is not the one in node-assignment.yaml")
            current = [X.squeeze(dd["text"]) for dd in comp.get("decisions") or [] if dd.get("text")]
            hows = [h for s in n.get("settles", []) for h in s.get("how", [])]
            for h in hows:
                if X.squeeze(h) not in current:
                    problems.append(f"{at}: settles a choice with a decision the component no longer has: {h[:80]!r}")
            if n.get("own_decisions", 0) != len(current) - len(hows):
                problems.append(f"{at}: own_decisions is {n.get('own_decisions', 0)}; the component has {len(current)} "
                                f"decisions, {len(hows)} of them settle a choice")
            for s in n.get("settles", []):
                if not any(s["choice"] in kept.get(t, []) for t in ([s["type"]] if s.get("type") else ts)):
                    problems.append(f"{at}: settles '{s['choice']}', which its type does not list")
        rebuilt, why = build_nodes(e)
        if why:
            problems += [f"{where}: {x}" for x in why]
        elif text(rebuilt) != text({k: ex.get(k) for k in rebuilt}):
            problems.append(f"{where}: is not what `so_nodetypes.py example {e}` writes from the files as they are now")
        found = list(dict.fromkeys(problems[before:]))
        problems[before:] = found
        notes.append(f"{where}: {len(got)} nodes, {len(found)} problems")

    sizes = [len(text(t)) for t in d["types"]]
    print(f"draft {d['draft_version']}: {len(ids)} types in {len(fams)} groups, {sum(len(t['rules']) for t in d['types'])} rules, "
          f"{sum(len(t.get('choices', [])) for t in d['types'])} choices; one type is {statistics.median(sizes):.0f} characters "
          f"(median), {sum(sizes)} in all")
    problems = list(dict.fromkeys(problems))
    for n in notes:
        print("  note:", n)
    for p in problems:
        print("  PROBLEM:", p)
    print(f"{len(problems)} problems")
    return 1 if problems else 0


# ---------------------------------------------------------------- doc

ENGINE_ABOUT = {
    "strata": "An engine written for one mixture-of-experts model, Qwen3.8-Flash-Next, on a PC with a 12 GB GPU and on "
              "DGX Spark. Described in full in this repository; the engine the analysis started from",
    "ds4": "DwarfStar. One engine for several large mixture-of-experts model families (DeepSeek V4, GLM 5, Qwen3.8 Flash Next)",
    "hyperqwen": "An engine for Qwen3.8-27B, a dense model that mixes recurrent and attention layers",
    "ninfer": "An engine for dense and mixture-of-experts Qwen models and GLM-5.3-Flash; one model per instance, several "
              "requests at once",
    "splash": "An engine for five model families on one Apple-Silicon GPU",
    "llama-cpp": "The general-purpose open-source engine, about 176 model architectures",
}
SHOW_TYPE, SHOW_NODE = "draft-proposal", "mtp-drafter"


def weight_size(model_file, data_id):
    """The stated size of one kind of data of a model description, as text."""
    for x in X.load(ROOT / "examples" / "given" / model_file).get("data", []):
        if x["id"] == data_id:
            return f"{x['size']['value']:.0f} {x['size']['unit']}"
    return "an unstated size"


def count_items(text_):
    """The items of a list written as one text, separated by semicolons."""
    return len([x for x in str(text_ or "").split(";") if x.strip()])


def listing(xs, last="and"):
    xs = list(xs)
    if len(xs) <= 1:
        return "".join(xs)
    return ", ".join(xs[:-1]) + f" {last} " + xs[-1]


def quoted(s, n=160):
    s = X.squeeze(s)
    return f"“{s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + ' …'}”"


def number_word(n):
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(n, str(n))


def truth_sources():
    """case -> what the resolved spec behind a known answer says of itself: its title, its environment, and the parts
    it marks inactive with their reasons."""
    out = {}
    for case, spec in X.SPECS.items():
        s = X.load(ROOT / "examples" / "specs" / spec)
        title = str(s.get("title", ""))
        env = (s.get("given") or {}).get("environment")
        off = [(c["component_ref"].split("/")[-1], c.get("inactive_reason", ""))
               for c in s.get("composition", {}).get("components", []) if c.get("active") is False]
        out[case] = {"file": f"examples/specs/{spec}", "title": title, "environment": env,
                     "reconstruction": "重构" in title or "reconstruct" in title.lower(),
                     "from_documents": "文档" in title or "document" in title.lower() or "reported" in str(env),
                     "off": off}
    return out


CASES = {"qwen-on-pc": "Strata's model on the PC", "qwen-on-spark": "Strata's model on DGX Spark",
         "muse-on-spark": "Muse Spark Open on DGX Spark", "llama-cpp": "llama.cpp"}


def memory_text(hw_file):
    """The memory pools of a machine description, as text: size and kind of each pool that is not storage."""
    kinds = {"device_ram": "GPU memory", "host_ram": "host memory", "unified_ram": "memory shared by CPU and GPU"}
    pools = [p for p in X.load(ROOT / "examples" / "given" / hw_file).get("memory_pools", []) if p.get("kind") in kinds]
    return listing(f"{p['capacity_nominal']['value']} {p['capacity_nominal']['unit']} of {kinds[p['kind']]}" for p in pools) or "no memory stated"


def mark_row(r):
    """A row of the pass-mark table from a figure judged by so_nodetypes_experiments."""
    word = {True: "met", False: "**not met**", None: "no mark"}[r["met"]]
    if r["met"] is not None and not r["scoring"]:
        word += " (shown beside)"
    check = r["check"]
    for k, v in CASES.items():
        check = re.sub(rf"(?<![\w-]){re.escape(k)}(?![\w-])", v, check)
    return f"| {check} | {r['limit']} | {r['figure']} | {word} |"


def real_stages_section(add):
    """What the factory's released Intent and Requirements stages did with the ontology files, from the stored results
    of the runs (validation/intake/real-*). Every figure is counted from those files."""
    import hashlib
    import json
    runs = sorted((ROOT / "validation" / "intake").glob("real-*"))
    if not runs:
        return
    rd = runs[-1]
    load = lambda n: json.loads((rd / n).read_text(encoding="utf-8")) if (rd / n).exists() else None

    def spans(x, out=None):
        out = [] if out is None else out
        if isinstance(x, dict):
            if "source_ref" in x and "start" in x:
                out.append((x["source_ref"].get("sha256"), x["start"], x["end"]))
            for v in x.values():
                spans(v, out)
        elif isinstance(x, list):
            for v in x:
                spans(v, out)
        return out

    rows, all_spans, facts, requests, verdicts = [], [], {}, [], set()
    for q in "ABCD":
        inp, res = load(f"intent_in_{q}.json"), load(f"intent_{q}_result.json")
        if not inp or not res:
            continue
        names = {hashlib.sha256(d["text"].encode("utf-8")).hexdigest(): d["name"] for d in inp["documents"]}
        ir = (res.get("outputs") or {}).get("intent")
        requests.append(inp.get("request", ""))
        req = load(f"requirements_{q}_result.json")
        for one in (res, req):
            for review in ((((one or {}).get("receipt") or {}).get("semantic_verifier") or {}).get("reviews") or {}).values():
                if (one or {}).get("status") == "delivered" and review.get("verdict"):
                    verdicts.add(review["verdict"])
        brief = ((req or {}).get("outputs") or {}).get("brief")
        row = {"q": q, "files": [d["name"] for d in inp["documents"]], "intent": res["status"],
               "halt": ((res["receipt"].get("halt") or {}).get("reason") or "").split(";")[0],
               "req": req["status"] if req else None,
               "req_halt": (((req or {}).get("receipt") or {}).get("halt") or {}).get("reason", "").split(";")[0] if req else ""}
        if ir:
            u = ir["uncertainties"]
            row |= {"readiness": ir["readiness"]["status"], "unc": len(u), "blocking": sum(1 for x in u if x.get("blocking"))}
            cited = {}
            for field in ("context", "in_scope", "out_of_scope", "constraints", "preferences", "user_targets"):
                for e in ir.get(field) or []:
                    for sha, a, b in spans(e):
                        cited.setdefault(names.get(sha, "request"), set()).add(field)
            for sha, a, b in spans(ir):                      # every position of the Intent, whatever entry carries it
                all_spans.append((q, names.get(sha), a, b))
            row["cited"] = cited
            facts[q] = {"ir": ir, "brief": brief}
        if brief:
            un = brief.get("unresolved_items") or []
            row |= {"mand": len(brief.get("mandatory_requirements") or []), "cons": len(brief.get("constraints") or []),
                    "unres": len(un)}
        rows.append(row)
    if not rows:
        return
    add("### 6.6 What the factory's own Intent and Requirements stages did with these files\n")
    add(f"The checks above used stand-in readers. On {rd.name.replace('real-', '')} I ran the factory's released Intent and "
        "Requirements stages themselves, through the repository's portable capsule runtime, with the product's fixed model "
        f"and reasoning effort (`validation/intake/{rd.name}/README.md` says exactly what was run and what it is not: it is "
        "not the whole product, each stage makes one model call, and the worker and the verifier are the same model). "
        "Each query is a request of a few sentences with ontology files attached."
        + (" Every request ends “Take them as the statement of what is wanted”, and those with an engine description say that "
           "the files describe “the engine itself at two levels”. What the stage did with the files may follow from that "
           "wording; no other wording was tried."
           if requests and all("Take them as the statement of what is wanted" in r for r in requests) else "") + "\n")
    add("| Query | Files attached | Intent | Readiness | Uncertainties, blocking | Requirements |")
    add("|---|---|---|---|---|---|")
    for r in rows:
        intent = "delivered: checks passed, verifier accepted" if r["intent"] == "delivered" else f"**rejected by a check**: {r['halt'][:90]}"
        reqs = ("not run" if r["req"] is None else
                f"delivered: {r.get('mand')} mandatory requirements, {r.get('cons')} constraints, {r.get('unres')} unresolved"
                if r["req"] == "delivered" else f"**rejected by a check**: {r['req_halt'][:80]}")
        add(f"| {r['q']} | {', '.join(f'`{x}`' for x in r['files'])} | {intent} | {r.get('readiness', '').replace('_', ' ')} | "
            + (f"{r['blocking']} of {r['unc']}" if "unc" in r else "") + f" | {reqs} |")
    add("")
    delivered = [r for r in rows if "readiness" in r]
    if delivered and all(r["readiness"] == "needs_clarification" for r in delivered):
        add(f"Every delivered Intent says the request needs clarification ({len(delivered)} of {len(delivered)}), and "
            f"{sum(r['blocking'] for r in delivered)} of the {sum(r['unc'] for r in delivered)} uncertainties are blocking. "
            "By my reading of them, those of query A are all items the target file marks `UNSET` or `status: proposed`: "
            "the stage turns each into a question for the user. "
            + (f"That did not stop the next stage in this runtime: I ran the Requirements stage on these Intents and it "
               f"delivered a Brief for {' and '.join(r['q'] for r in rows if r['req'] == 'delivered')}, with the questions "
               "carried as unresolved items. " if any(r["req"] == "delivered" for r in rows) else "")
            + "The stand-in readers of my earlier trial had called queries A and B ready.\n")
    if verdicts:
        add("The verifier's verdict on every delivered output is "
            + ", ".join(f"`{v}`" for v in sorted(verdicts))
            + (": in this runtime it is given the output and not the contents of the files the output refers to, and it "
               "says so as its known limitation." if any("LIMITATION" in v for v in verdicts) else ".") + "\n")
    for r in rows:
        nt = (r.get("cited") or {}).get("node-types.yaml")
        if "node-types.yaml" in r["files"] and "cited" in r:
            add(f"**The generic node types (query {r['q']}).** "
                + (f"The Intent cites the file in one kind of entry only: `{'`, `'.join(sorted(nt))}`. "
                   if nt and len(nt) == 1 else f"The Intent cites the file in `{'`, `'.join(sorted(nt))}`. " if nt
                   else "No entry of the Intent cites the file. ")
                + ("No constraint, target or scope entry cites it: in this run the file is taken as a piece of context.\n"
                   if not nt or nt <= {"context"} else "\n"))
    c = facts.get("C")
    if c:
        ir, brief = c["ir"], c["brief"]
        conflict = next((u for u in ir["uncertainties"] if u.get("kind") == "conflicting" and "512" in u.get("description", "")), None)
        kinds = collections.Counter(u.get("kind") for u in ir["uncertainties"])
        fields = sorted({f for n, fs in (next(r for r in rows if r["q"] == "C")["cited"]).items() if n in ("system.yaml", "nodes.yaml") for f in fs})
        add("**One engine's two-level description (query C, the Muse design in the version of my earlier trial, before it "
            "was derived again on 2026-11-18).** "
            f"The Intent cites the system level and the node level in `{'`, `'.join(fields)}` and in no constraint or target. "
            f"Of its {len(ir['uncertainties'])} uncertainties, {kinds.get('conflicting', 0)} are conflicts and "
            f"{kinds.get('ambiguous', 0)} ambiguities. "
            + (f"One conflict is between the model and a node of the description: “{conflict['description'][:230].strip()}…”. " if conflict else ""))
        if brief:
            hit = next((x for x in brief.get("mandatory_requirements") or []
                        if "conversation" in json.dumps(x)), None)
            if hit:
                text = hit.get("text") or hit.get("statement") or ""
                add(f"The Brief turns the system level's sentence on what the first version leaves out into a mandatory "
                    f"requirement: “{text[:200].strip()}…”. That sentence was partly wrong in that version (it said the first "
                    "version leaves out keeping more than one conversation in memory, while the design has a part that keeps "
                    "the state of earlier conversations; corrected since), so a wrong sentence of a description became a "
                    "requirement.")
        add("")
    d = next((r for r in rows if r["q"] == "D"), None)
    if d and d["intent"] != "delivered":
        d_replies = list(rd.glob("rejected_intent_D*.json")) + list((rd / "round2").glob("rejected_intent_D*.json"))
        with_512 = sum(1 for p in d_replies if "512" in p.read_text(encoding="utf-8"))
        add(f"**The same request with the files of {rd.name.replace('real-', '')} (query D).** These are the files as they "
            "stood on the morning of the run; a few sentences of the design were corrected afterwards, one of them because "
            "a rejected reply pointed at it. The stage's check of quotation positions rejected the "
            f"reply in each of {len(d_replies)} runs: a quotation ended beyond the end of a file. Nothing was delivered, so D "
            "adds no accepted output. The rejected replies are stored; "
            + ("none of them names the conflict of C between 8 of 256 and 10 of 512 experts.\n" if not with_512 else
               f"{with_512} of them still name a conflict over 512 experts.\n"))
    if all_spans:
        in_files = [x for x in all_spans if x[1]]
        zero = [x for x in in_files if x[2] == 0]
        round_ = sum(1 for x in in_files if x[3] % 10 == 0)
        inside = collections.Counter(f"{x[0]}, `{x[1]}`" for x in in_files if x[2] != 0)
        add(f"**What the quotations show.** Each entry of an Intent carries positions in the request or in an attached "
            f"file. Of the {len(all_spans)} positions in the delivered Intents, {len(in_files)} are in attached files; of "
            f"these, {len(zero)} start at character 0 and {round_} end at a multiple of ten: such a position points at a "
            "file from its beginning, not at a sentence. "
            + (f"The other {len(in_files) - len(zero)} start inside a file ("
               + "; ".join(f"{n} in query {k}" for k, n in sorted(inside.items())) + "). " if inside else "")
            + "The stage's check accepts any position inside the file and does not compare the quoted text with the entry. "
              "So for most entries these runs show whether a file was used, not which sentence of it.\n")
    # a second run of the same queries, when its results are stored: does the outcome repeat?
    again = rd / "round2"
    if again.is_dir():
        def outcome_file(path):
            ir = json.loads(path.read_text(encoding="utf-8"))
            u = ir["uncertainties"]
            return (f"**rejected by a check**; the reply says {ir['readiness']['status'].replace('_', ' ')}, "
                    f"{sum(1 for x in u if x.get('blocking'))} of {len(u)} blocking")

        def outcome(folder, q):
            p = folder / f"intent_{q}_result.json"
            if not p.exists():
                return None
            r = json.loads(p.read_text(encoding="utf-8"))
            ir = (r.get("outputs") or {}).get("intent")
            said = ""
            if not ir:                                       # rejected: what the reply said is kept beside the result
                rej = folder / f"rejected_intent_{q}.json"
                if not rej.exists():
                    return "**rejected by a check**"
                ir, said = json.loads(rej.read_text(encoding="utf-8")), "**rejected by a check**; the reply says "
            u = ir["uncertainties"]
            cites = set()
            inp = json.loads((rd / f"intent_in_{q}.json").read_text(encoding="utf-8"))
            names = {hashlib.sha256(d["text"].encode("utf-8")).hexdigest(): d["name"] for d in inp["documents"]}
            for field in ("context", "in_scope", "out_of_scope", "constraints", "preferences", "user_targets"):
                for e in ir.get(field) or []:
                    for sha, a, b in spans(e):
                        if names.get(sha) in ("node-types.yaml", "nodes.yaml", "system.yaml"):
                            cites.add(field)
            return (said + f"{ir['readiness']['status'].replace('_', ' ')}, {sum(1 for x in u if x.get('blocking'))} of {len(u)} "
                    f"blocking" + (f"; node-type or engine files cited in `{'`, `'.join(sorted(cites))}`" if cites else
                                   "; no node-type or engine file cited" if any(n in names.values() for n in ("node-types.yaml", "nodes.yaml")) else ""))
        pairs = [(q, outcome(rd, q), outcome(again, q)) for q in "ABCD"]
        pairs = [x for x in pairs if x[2] is not None]
        if pairs:
            add("**Run a second time.** One model call can come out differently the next time, so each Intent was run again "
                "on the same inputs.\n")
            add("| Query | First run | Second run |")
            add("|---|---|---|")
            for q, a, b in pairs:
                add(f"| {q} | {a} | {b} |")
            add("")
            every = [x for _, a, b in pairs for x in (a, b) if x] + \
                    [outcome_file(p) for p in sorted(rd.glob("rejected_intent_*_repeat.json"))]
            n_rej = sum(1 for x in every if "rejected" in x)
            add(f"Of the {len(every)} replies of the Intent stage in all, {n_rej} were rejected by the stage's check of "
                f"quotation positions, each time because a quotation ended beyond the end of a file, and "
                f"{len(every) - n_rej} were delivered. Which query is delivered is not stable from one run to the next. "
                + ("Every reply, delivered or rejected, says the request needs clarification. "
                   if all("needs clarification" in x for x in every) else "")
                + "What a rejected reply says is not an output of the stage; it is shown because it is the same model on "
                  "the same input.\n")
    add("My reading of these runs for the node level, and no more than these runs: where an Intent was delivered with "
        "the description of an engine attached (C, once), the stage drew questions and scope from it; where one was "
        "delivered with the generic types attached (B, twice), it cited the file once, as context. On the files of the day "
        "(D) nothing was delivered. This is one model with one call per stage, outside the product, on requests worded as "
        "above. Beyond Requirements no later stage was run, so nothing here shows what a later stage would do with either "
        "file.\n")


def doc():
    d = X.load(DRAFT)
    crit = X.criteria()
    types = {t["id"]: t for t in d["types"]}
    fams = d["groups"]
    L = []
    add = L.append
    n_eng = len(d["engines_examined"])
    n_rules = sum(len(t["rules"]) for t in d["types"])
    n_choices = sum(len(t.get("choices", [])) for t in d["types"])
    sizes = [len(text(t)) for t in d["types"]]
    assign = X.assignments()
    names = lambda ts: ", ".join(f"`{t}`" for t in ts) or "none"
    ex_path = ROOT / "examples" / "systems" / "strata" / "nodes.yaml"
    nodes = X.load(ex_path)["nodes"] if ex_path.exists() else []
    node_chars = sum(len(text(n)) for n in nodes)
    ho = V / "heldout"
    checker, mismatches = VAL.checks(ho)
    hc = checker.get(X.HELD_OUT)
    checked_drafts = sorted({X.load(next(p.parent.glob("node-types.draft-*.yaml")))["draft_version"]
                             for p in V.glob("*/check-*.yaml") if any(p.parent.glob("node-types.draft-*.yaml"))}, key=VAL.version)
    claims_checked_now = d["draft_version"] in checked_drafts

    add(f"# Node ontology: revised version (draft {d['draft_version']})\n")
    add("Generated by `tools/so_nodetypes.py doc` from `ontology/node-types.draft.yaml`.\n")
    intro = ROOT / "NODE-ONTOLOGY-revised.intro.md"
    if intro.exists():
        add(intro.read_text(encoding="utf-8").strip() + "\n")

    # 1
    strata_sizes, ws = [], None
    try:
        ws = X.workspace()
        strata_sizes = [len(text(c)) for c in ws.of_kind("component") if c["system"] == "sys/strata" and not c.get("parts")]
    except Exception as e:
        print("note: full descriptions not loaded:", e)
    add("## 1. What changed\n")
    add("Three versions are named in this document.\n")
    add("- **The reviewed version**: the node level you reviewed, one description per component of Strata.")
    add(f"- **The full-detail draft**: a first draft of generic node types, not sent. It has the same {len(types)} types as "
        "now and much more written about each.")
    add(f"- **This draft** ({d['draft_version']}): the full-detail draft with the detail removed. The stored records and "
        "some sentences below call it the thin draft.\n")
    add("| | The reviewed version | This draft |")
    add("|---|---|---|")
    add("| What is described | each component of one engine | a kind of component, for any engine |")
    if strata_sizes:
        add(f"| How many | {len(strata_sizes)} components for Strata alone | {len(types)} node types in {len(fams)} groups |")
        add(f"| Size of one description | about {statistics.median(strata_sizes):,.0f} characters (median) | about {statistics.median(sizes):,.0f} characters (median) |")
        if nodes:
            add(f"| Strata's node level in all | about {sum(strata_sizes) / 1000:.0f} thousand characters | about {node_chars / 1000:.0f} thousand "
                f"characters for Strata's {len(nodes)} nodes, plus about {sum(sizes) / 1000:.0f} thousand for the {len(types)} types, which all engines share |")
    add("| Parameter values, call interfaces, source lines | in the node description | not in a node type. Nothing was deleted: "
        "they remain in the full description of the engine, which each node points to |")
    add(f"| Drawn from | Strata | {n_eng} engines |")
    add("")
    add(f"The {number_word(n_eng)} engines. Each was read from its source code; none was built or run.\n")
    add("| Engine | What it is | Parts I listed |")
    add("|---|---|---|")
    for e in d["engines_examined"]:
        add(f"| {ENGINE_NAMES[e]} | {ENGINE_ABOUT[e]} | {len(assign[e])} |")
    add("")
    add("One way of reading the node types that I tried: given the description of a model, a machine and a target (what "
        "the engine is for), say for each type whether the engine needs it and which decisions are left to whoever builds "
        "it. Section 6.4 reports that try and what it does and does not show. The factory's first reader, the Intent "
        "stage, did not read them that way when I ran it on them: section 6.6.\n")

    # 2
    strength = {s["id"]: s["meaning"] for s in d["rule_strengths"]}
    add("## 2. What a node type contains\n")
    add("**What I borrowed from the CC declaration.** A Capability Capsule (CC) declaration in this repository "
        "(`docs/architecture/design-package/reference/declaration.md`) describes a unit by what it promises, not by how "
        "it is built. I took that as the reference for how deep a node type should go: it answers the same kind of "
        "questions about an engine part. A node type is not a CC. It is an input that CCs read, and its format and "
        "field names are the ontology's own.\n")
    add("| Node type field | The question it answers |")
    add("|---|---|")
    claims_word = ("" if claims_checked_now else
                   f" Draft {d['draft_version']} itself was not checked against the engines for its rules or its effect on output"
                   + (f"; the last such check, of draft {checked_drafts[-1]}"
                      + (f" on {ENGINE_NAMES[X.HELD_OUT]}, found {len(hc['contradictions'])} claims the engine contradicts"
                         if hc and checked_drafts[-1] == X.load(ho / 'node-types.draft-0.8.yaml')['draft_version'] else "")
                      if checked_drafts else "") + ".")
    for f, q in [
        ("`id`, `group`, `summary`, `not`", "What is its one job, and what is easily mistaken for it?"),
        ("`needed_when`", "Which property of the model, the machine or the service makes this node necessary? Absent when the job has to be done in every engine."),
        ("`forms`", "In which distinct ways do engines realise it?"),
        ("`takes`, `gives`", "What does it consume and produce? Which node it connects to differs between engines and is stated at system level, the description of one engine as a whole."),
        ("`owns_state`", "What does it alone keep consistent?"),
        ("`rules`", f"What must it guarantee? `must`: {strength.get('must', '')} `should`: {strength.get('should', '')} "
                    f"`rule_scope`: {d.get('rule_scope', '')}{claims_word}"),
        ("`effect_on_output`", "How far can its own work change the returned output? One or more of the five levels below. Several levels mean that which one applies depends on how an engine builds the node and on its settings."),
        ("`indirect_effect`", "Does it also change the output through other nodes, by deciding something their effect depends on, such as how wide a step is or what is kept in memory? Present and `true` when it does."),
        ("`choices`", f"What is left for whoever builds the engine to decide? Names only, no values. Listed only when at least {d['choices_kept_when']['engines']} of the {n_eng} engines decide it; `engines` says how many."),
        ("`seen_in`", "Which of the engines examined have a part of this type?"),
    ]:
        add(f"| {f} | {q} |")
    add("")
    add("The levels of `effect_on_output`. The first four are the equivalence levels the format already uses, so a node "
        "type can be compared with what a target allows to change.\n")
    add("| Level | Meaning |")
    add("|---|---|")
    for lv in d["effect_levels"]:
        add(f"| `{lv['id']}` | {lv['meaning']} |")
    add("")
    add("Not in a node type: parameter values, call interfaces, source file and line references, measured costs, test "
        "status, and choices only one engine makes. These are facts about one engine and stay in its description.\n")
    add(f"In all: {len(types)} node types, {n_rules} rules, {n_choices} choices.\n")

    # 3
    add("## 3. The node types\n")
    add("Two columns need a word. **Needed when**: `always` means the job has to be done in every engine; otherwise the "
        f"condition is given. **Seen in**: the number of the {number_word(n_eng)} engines in which I listed a part of this type. The two "
        "can differ. An engine can do an `always` job inside a part that is mainly of another type, and a conditional "
        f"type is seen in all {number_word(n_eng)} when all {number_word(n_eng)} meet its condition.\n")
    for f in fams:
        add(f"### {f['title']} (`{f['id']}`)\n")
        add(f"{f['about']}\n")
        add("| Node type | Its job | Needed when | Seen in |")
        add("|---|---|---|---|")
        for t in d["types"]:
            if t["group"] != f["id"]:
                continue
            sn = t["seen_in"]
            where = f"{len(sn)} of {n_eng}" + (f" ({', '.join(ENGINE_NAMES[e] for e in sn)})" if len(sn) <= 2 else "")
            add(f"| `{t['id']}` | {t['summary']} | {t.get('needed_when', 'always')} | {where} |")
        add("")

    # 4
    add("## 4. One node type in full\n")
    add("```yaml")
    add(text(types[SHOW_TYPE]).rstrip())
    add("```\n")
    absent = [k for k in ("not", "needed_when", "forms", "owns_state", "indirect_effect", "choices") if k not in types[SHOW_TYPE]]
    if absent:
        add(f"A field that does not apply is left out; this type has no {' and no '.join(f'`{k}`' for k in absent)}.\n")

    # 5
    add("## 5. Strata as the worked example\n")
    if nodes:
        by_type = collections.defaultdict(list)
        for n in nodes:
            by_type[n["type"]].append(n["title"])
        add("Strata is described at two levels. The system level (`examples/systems/strata/system.yaml`) says what the "
            "engine is for and how its parts are connected. The node level (`examples/systems/strata/nodes.yaml`) is now "
            "a list of nodes, each naming its node type and how Strata settles the choices that type leaves open.\n")
        add("### 5.1 Which node types Strata has\n")
        with_second = {t for n in nodes for t in [n["type"], *n.get("also", [])]}
        add(f"Strata's {len(nodes)} parts are instances of {len(by_type)} of the {len(types)} node types"
            + (f", or {len(with_second)} when the further jobs of some parts are counted" if len(with_second) > len(by_type) else "") + ".\n")
        add("| Group | Node type | Strata's parts |")
        add("|---|---|---|")
        for f in fams:
            for t in d["types"]:
                if t["group"] == f["id"] and t["id"] in by_type:
                    add(f"| {f['title']} | `{t['id']}` | {'; '.join(by_type[t['id']])} |")
        two = [n for n in nodes if n.get("also")]
        if two:
            add("")
            add(f"{len(two)} parts do more than one job and are also instances of other types: "
                + "; ".join(f"{n['title']} (also {names(n['also'])})" for n in two) + ".")
        add("")
        add("Node types Strata has no part for, with the condition under which an engine needs them:\n")
        add("| Node type | Needed when |")
        add("|---|---|")
        for x in X.load(ex_path)["types_without_a_part"]:
            add(f"| `{x['type']}` | {x.get('needed_when', 'always')} |")
        add("")
        pick = next((n for n in nodes if n["component"] == SHOW_NODE), nodes[0])
        add("### 5.2 One node of Strata in full\n")
        add("This is Strata's instance of the type shown in section 4. `settles` lists the choices of the type that "
            "Strata decides, with the decision as recorded in Strata's inventory. `own_decisions` counts the further "
            "decisions recorded for this part that are not a choice of the type. `described_in` points to the full "
            "description of the component.\n")
        add("```yaml")
        add(text(pick).rstrip())
        add("```\n")
        if ws is not None and pick.get("described_in") in ws.objects:
            add(f"The full description of the same component is about {len(text(ws.objects[pick['described_in']])):,} "
                f"characters and also holds the parameter values, the call interfaces and the source lines. This node is "
                f"{len(text(pick)):,} characters.\n")
    add("### 5.3 The same types in the other engines\n")
    add("| Engine | Parts | Node types it has | Parts with no type |")
    add("|---|---|---|---|")
    for e in d["engines_examined"]:
        parts = assign[e]
        add(f"| {ENGINE_NAMES[e]} | {len(parts)} | {len({t for ts in parts.values() for t in ts})} | "
            f"{sum(1 for ts in parts.values() if not ts)} |")
    add("")

    section6(d, crit, add, assign, names, checker, mismatches, hc, checked_drafts, claims_checked_now)

    # 7
    add("## 7. Not covered yet\n")
    add("Work a general-purpose engine does that no node type describes. All were seen in llama.cpp, after the types "
        "were fixed, and are recorded and not added:\n")
    for g in d["open_gaps"]:
        near = f" Nearest: {names(g['nearest'])}." if g.get("nearest") else " No type is near."
        add(f"- {g['what']}{near}")
    add("")
    one = [t["id"] for t in d["types"] if len(t["seen_in"]) == 1]
    if one:
        add(f"Seen in one engine only, and kept because no other type does the job: {names(one)}.\n")
    add("The format that the checking program reads (`ontology/schema.yaml`) still holds the component descriptions of "
        "the reviewed version. The node types are a separate file until the list of types is agreed.\n")
    add("Questions for the team on scope, granularity and depth are sent with this document as a separate message.\n")

    (ROOT / "NODE-ONTOLOGY-revised.md").write_text("\n".join(L), encoding="utf-8")
    print(f"wrote NODE-ONTOLOGY-revised.md, {len(L)} lines")
    return 0


def section6(d, crit, add, assign, names, checker, mismatches, hc, checked_drafts, claims_checked_now):
    types = [t["id"] for t in d["types"]]
    n_eng = len(d["engines_examined"])
    limits = []                                       # the items of 6.6, gathered where their figures are computed

    add("## 6. How this draft was checked\n")
    n_first = sum(len(assign[e]) for e in X.INDUCTION)
    n_last = len(assign[X.HELD_OUT])
    n_corr = sum(len(X.inventory(e)[1]) for e in X.INDUCTION)
    add(f"The types rest on parts inventories of the {number_word(n_eng)} engines: for each engine, a list of its parts with what each does "
        f"and which design decisions it makes. The first {number_word(len(X.INDUCTION))} engines ({n_first} parts) were used to write the types. "
        f"llama.cpp ({n_last} parts) was held out, to see how the types fit an engine they were not drawn from "
        "(section 6.2 says what I knew of it before the types were fixed).\n")
    add("Who did what. I wrote the types and the assignment of each part to a type, working with Claude. "
        "**Every reader named below is a Claude subagent**, not a person: a separate run that sees only the "
        "files it is given. The inventories were also written by subagents from the source code, and later readers "
        f"corrected {n_corr} of their entries against the source.\n")
    places = [("the first classification run", ["round8"]), ("the classification confirmation", ["round9"]),
              ("the first selection run", ["selection"]), ("the selection confirmation", ["selection-final"]),
              ("matching decisions to choices", ["choices"]), ("the held-out classification on draft 0.8", ["heldout"])]
    stored = {name: X.instructions_stored(*dirs) for name, dirs in places}
    # The checkers of rounds 2 to 7 and of the held-out engine were given one brief kept at the top of validation/,
    # not a copy per run: it is the brief as it stands now, and which version each run saw is not recorded.
    shared_brief = V / "CHECK-BRIEF.md"
    if any(V.glob("*/check-*.yaml")):
        places.append(("the checkers of the types (rounds 2 to 7 and the held-out checker)", None))
        stored["the checkers of the types (rounds 2 to 7 and the held-out checker)"] = [shared_brief] if shared_brief.exists() else []
    have = [f"{n} (`{X.shown(ps[0])}`" + (", one file for every run, as it stands now; which version each run saw is not "
                                           "recorded" if ps[0].parent == V else "") + ")"
            for n, ps in stored.items() if ps]
    lack = [n for n, ps in stored.items() if not ps]
    add("What the readers were told. " + (f"The instructions are stored for: {listing(have)}. " if have else "")
        + (f"No instructions are stored for: {listing(lack)}; what those readers were told cannot be checked now. "
           if lack else "") + "Each future run can store its readers' instructions beside its results "
        "(`so_nodetypes_experiments.py instructions DIR FILE`).\n")
    if lack:
        limits.append(f"The readers' instructions are not stored for {len(lack)} of the {len(places)} checks ({listing(lack)}).")

    # ---- pass marks
    c9 = X.score_classification(V / "round9" / "parts.key.yaml", "round9")
    c8 = X.score_classification(V / "round8" / "parts.key.yaml", "round8")
    runs_c = [(c8, "first run"), (c9, "confirmation")]
    sel = [(X.score_selection(r), lbl, r) for r, lbl in X.SELECTION_RUNS]
    totals, maps, map_problems = X.recurrence_data()
    rec_marks = X.recurrence_marks(totals, maps) if len(maps) == len(X.ENGINES) else []
    ho_fits = VAL.heldout(V / "heldout", crit["generalisation"])
    thin_key = next((k for k in crit if k.startswith("thin_draft")), None)
    thin = crit.get(thin_key) or {}
    thin_date = "-".join(thin_key.split("_")[-3:]) if thin_key else None
    rows = []
    for c, lbl in runs_c:
        if c:
            rows += [r | {"check": f"Classification, {lbl}: {r['check']}"} for r in c["marks"] if r["mark"]]
    for rname, n, c, ok, dropped, total in ho_fits:
        rows.append(X.judged(f"Held-out classification on draft 0.8, {rname}: plainly an instance of one type",
                             "generalisation.clean_fit_min", c["clean"], n))
        rows.append(X.judged(f"Held-out classification on draft 0.8, {rname}: no type", "generalisation.no_type_max", c["none"], n))
    if hc:
        rows.append(X.judged("Held-out checker on draft 0.8, llama.cpp: decisions plainly covered by a choice",
                             "decision_coverage.covered_min", hc["totals"]["covered"], hc["real"]))
        rows.append(X.judged("Held-out checker on draft 0.8, llama.cpp: decisions not covered",
                             "decision_coverage.not_covered_max", hc["totals"]["not_covered"], hc["real"]))
        rows.append(X.judged("Held-out checker on draft 0.8, llama.cpp: claims the engine contradicts",
                             "claims.contradicted_max", len(hc["contradictions"])))
    rows += [r | {"check": f"Matching decisions to choices: {r['check']}"} for r in rec_marks]
    for s, lbl, r in sel:
        if s:
            rows += [x | {"check": f"Selection, {lbl}: {x['check']}"} for x in s["marks"] if x["mark"]]
    not_tested = [("Leave one engine out, for each engine in turn", "generalisation",
                   f"one engine was held out ({ENGINE_NAMES[X.HELD_OUT]}), once"),
                  ("Claims of draft " + d["draft_version"] + " against the engines", "claims",
                   "not run" if not claims_checked_now else "run"),
                  ("Selection: a reader settles the choices of the types it selects", "sufficiency",
                   "no reader was asked to settle choices")]
    scoring = [r for r in rows if r["scoring"] and r["met"] is not None]
    failed = [r for r in scoring if r["met"] is False]
    add("### Pass marks\n")
    add(f"On {crit['set_on']} I set pass marks for these checks in `validation/criteria.yaml`."
        + (f" On {thin_date} I recorded there that no pass mark is set for the thin draft (`{thin_key}`)" if thin_key else "")
        + ((", after earlier results were known: its own reason quotes one of them ("
            + quoted(re.search(r"\(([^()]*\d+%[^()]*)\)", thin.get("why", "")).group(1)) + ")")
           if thin_key and re.search(r"\(([^()]*\d+%[^()]*)\)", thin.get("why", "")) else "")
        + ". Section 6 did not mention the marks when this document was first sent. Here every figure is set against "
        f"the mark of {crit['set_on']} that applies to it; the marks were not changed for this. In the table, the key "
        "is the assignment of each part to a type that a reader's answer is compared with (6.1 says who made it); "
        "readers appear under the names of their stored files (`rater-a`, `reader-a`, `heldout-a`); a confirmation is the "
        "same check run again on the final wording of this draft.\n")
    add(f"| Check | Mark of {crit['set_on']} | Figure | |")
    add("|---|---|---|---|")
    for r in rows:
        add(mark_row(r))
    for what, sec, why in not_tested:
        if sec in crit:
            add(f"| {what} | `{sec}` | {why} | not tested |")
    add("")
    add(f"Of the {len(scoring)} figures the marks apply to, {len(scoring) - len(failed)} meet their mark and {len(failed)} do not. "
        f"{sum(1 for w, s, _ in not_tested if s in crit)} parts of the marks were never tested. "
        "“Shown beside” rows are the same data counted another way (the key's main type only, or the two readers against "
        "each other); the result does not rest on them. In the selection rows an answer `open` agrees with nothing, so "
        "it never counts as right there; in the tables of 6.4 open answers are counted apart and never count as wrong.\n")
    met_rows = [r for r in scoring if r["met"]]
    older = [r for r in met_rows if re.search(r"full-detail draft|draft 0\.\d", r["check"])
             and str(d["draft_version"]) not in r["check"]]
    if older:
        add(f"{len(older)} of the {len(met_rows)} figures that meet their mark are figures of the full-detail draft, not of "
            "this one: the rows that name it or its number.\n")
    agree_rows = [r for r in rows if not r["scoring"] and "give each other the same answer" in r["check"]]
    fixed_after = next((v["reading_fixed_after_the_results"] for v in X.criteria().values()
                        if isinstance(v, dict) and v.get("reading_fixed_after_the_results")), None)
    if agree_rows and fixed_after:
        add("The mark for selection does not say what an answer must agree with. I fixed its reading after the results were "
            "known (`validation/criteria.yaml`, `reading_fixed_after_the_results`): agreement with what Strata has scores, "
            f"and agreement between the two readers is shown beside it. Under the other reading the {len(agree_rows)} rows "
            f"shown beside would score instead, and {sum(1 for r in agree_rows if r['met'])} of them meet the mark.\n")
    limits.insert(0, f"Against the pass marks set on {crit['set_on']}, {len(failed)} of {len(scoring)} figures do not meet their "
                  f"mark, and {sum(1 for w, s, _ in not_tested if s in crit)} parts of the marks were never tested"
                  + (f". The marks were withdrawn for the thin draft on {thin_date}, after earlier results were known" if thin_key else "") + ".")

    # ---- 6.1
    add("### 6.1 Do two readers put each part where the key puts it?\n")
    c = c9
    if c:
        add(f"Two readers were given this draft and the {c['induction']['parts'] + c['held_out']['parts']} parts of all "
            f"{number_word(n_eng)} engines, with names and engines removed, and assigned each part to a type. They did not see the "
            "key: the assignment I made when the types were written for the first five engines, and the one a third "
            "reader made for llama.cpp. The two readers are runs of the same model reading the same files; what is "
            "measured is how far each matches the key, not whether people would tell the types apart.\n")
        add("| Parts | Every reader gives a type the key accepts | The first reader matches the key | The second reader matches the key | Every reader gives the key's main type |")
        add("|---|---|---|---|---|")
        for g, name in (("induction", "The first five engines"), ("held_out", "llama.cpp")):
            x = c[g]
            per = list(x["per"].values())
            add(f"| {name}: {x['parts']} | {x['agree']} | {per[0]} | {per[1]} | {x['agree_main']} |")
        add("")
        add(f"A part that does more than one job is accepted with any of its types ({c['induction']['further_types']} parts of "
            f"the first five engines, {c['held_out']['further_types']} of llama.cpp); the last column accepts only its main "
            f"type. The two readers gave each other the same type for {c['raters_same_type']} of the "
            f"{c['parts_every_rater_answered']} parts both answered.")
        total_parts = c["induction"]["parts"] + c["held_out"]["parts"]
        for r in c["raters"]:
            got_n = c["induction"]["answered"][r] + c["held_out"]["answered"][r]
            if got_n < total_parts:
                add(f"Reader {r} answered {got_n} of the {total_parts} parts; a part without an answer counts as not agreed.")
        for p_ in c["problems"]:
            add(f"The scorer reports a problem in the stored answers: {p_}.")
        if c8:
            add(f"In the first run on the thin draft (round 8, without choices) every reader gave an accepted type for "
                f"{c8['induction']['agree']} of {c8['induction']['parts']} and {c8['held_out']['agree']} of {c8['held_out']['parts']}, "
                f"the main type for {c8['induction']['agree_main']} and {c8['held_out']['agree_main']}.")
        # the last round of the full-detail drafts that has readers' answers on the five induction engines
        full_rounds = sorted((p.parent for p in V.glob("round*/rater-*.yaml")
                              if not (p.parent / "parts.key.yaml").exists() and any(p.parent.glob("reference-assignment-*.yaml"))),
                             key=lambda q: VAL.version(q.name))
        r7 = None
        if full_rounds:
            rd7 = full_rounds[-1]
            ref7 = X.load(sorted(rd7.glob("reference-assignment-*.yaml"))[0])
            also7 = ref7.pop("also", {}) or {}
            r7 = VAL.agreement(rd7, ref7, also7, X.load(V / "parts.key.yaml"))
            d7 = next((X.load(p)["draft_version"] for p in rd7.glob("node-types.draft-*.yaml")), "?")
        if r7:
            fv = X.load(X.FROZEN)["draft_version"]
            frozen_rated = any(X.load(p)["draft_version"] == fv for q in full_rounds for p in q.glob("node-types.draft-*.yaml"))
            add(f"The same check in {re.sub(r'(\D)(\d)', r'\1 \2', rd7.name, count=1)}, on draft {d7}"
                + (f" (the full-detail draft {fv} itself was not given to classification readers of these engines)"
                   if d7 != fv and not frozen_rated else "")
                + f", for the first five engines only, gave {r7['agree']} of {r7['parts']} with every reader agreeing, each "
                f"against its own key of that round, against {c['induction']['agree']} here.")
        no_type = [x for x in c.get("disagreements", []) if x["accepted"] == ["none"]]
        if no_type and all(v != "none" for x in no_type for v in x["given"].values()):
            add(f"Neither reader said of any part that it has no type: the {len(no_type)} parts of llama.cpp that no type "
                f"describes (section 7) were each put in the nearest type, which accounts for {len(no_type)} of the "
                f"{c['held_out']['parts'] - c['held_out']['agree']} llama.cpp parts not agreed.")
        add("")
        hist = X.key_history()
        steps = [h for h in hist if "main_type_changed" in h]
        if steps:
            changed = sum(h["main_type_changed"] + h["further_types_changed"] for h in steps)
            toward = sum(h["newly_accepts_a_type_a_reader_of_the_round_before_gave"] for h in steps)
            rounds = sorted({p.parent.name for p in V.glob("round*/rater-*.yaml") if not (p.parent / "parts.key.yaml").exists()})
            drafts = [X.load(next((V / r).glob("node-types.draft-*.yaml")))["draft_version"] for r in rounds
                      if any((V / r).glob("node-types.draft-*.yaml"))]
            add(f"The key of the first five engines is not independent of the readers. It is stored as it stood in each "
                f"round ({len(hist)} copies); between one copy and the next, {changed} entries changed "
                f"({sum(h['main_type_changed'] for h in steps)} main types, {sum(h['further_types_changed'] for h in steps)} "
                f"further types), and in {toward} of them the later key accepts a type a reader of the round before had "
                f"given. The {n_first} parts are also the parts the definitions were revised against: readers classified "
                f"the same parts in {len(rounds)} earlier rounds ({rounds[0]} to {rounds[-1]}"
                + (f", drafts {drafts[0]} to {drafts[-1]}" if drafts else "") + "), and the types were reworded after each.\n")
            limits.append(f"The key of the first five engines was revised between rounds, {toward} times toward a type a "
                          f"reader had given ({changed} entries changed in all), and its {n_first} parts are the ones the "
                          "definitions were revised against. Agreement on them is not agreement on unseen parts.")
        n_two = {e: sum(1 for ts in assign[e].values() if len(ts) > 1) for e in assign}
        limits.append(f"{sum(n_two[e] for e in X.INDUCTION)} parts of the first five engines and {n_two[X.HELD_OUT]} of "
                      f"llama.cpp do more than one job and are allowed any of their types; with the main type only, every "
                      f"reader agrees on {c['induction']['agree_main']} of {c['induction']['parts']} and "
                      f"{c['held_out']['agree_main']} of {c['held_out']['parts']}.")

    # ---- 6.2
    add("### 6.2 How well do the types fit an engine they were not drawn from?\n")
    fr = crit.get("frozen") or {}
    ho_types = X.load(V / "heldout" / "node-types.draft-0.8.yaml")
    inv = X.load(V / "held-out" / "llama-cpp.yaml")
    held = crit.get("held_out") or {}
    add(f"`validation/criteria.yaml` records the rule that the held-out inventory is not opened by whoever writes the types "
        f"until they are frozen, the full-detail draft (draft {fr.get('draft', ho_types['draft_version'])}) frozen on "
        f"{fr.get('on', fr.get(True, '?'))}"
        + (", and this disclosure: " + quoted(fr["disclosure"], 600) if fr.get("disclosure") else "") + "\n")
    add(f"This check rests on {number_word(len([held.get('engine', X.HELD_OUT)]))} engine, held out once"
        + (f"; the mark of {crit['set_on']} asks for each engine to be held out in turn"
           if crit["generalisation"].get("applies_to") == "every_fold" else "") + ". Of llama.cpp, the inventory's reader lists "
        f"{count_items(inv.get('not_read'))} things not read and {len(inv.get('outside_engine') or [])} things in the "
        f"repository that are outside the engine; its {len(inv['parts'])} parts are what was read.\n")
    limits.append(f"The held-out check rests on one engine, read in part ({count_items(inv.get('not_read'))} things not read), and "
                  "llama.cpp can no longer serve as an engine the types were not drawn from. A further check of that kind "
                  "needs another engine.")
    cols = [(f"draft {ho_types['draft_version']}, {r}", n, cnt, dropped, n_last - total) for r, n, cnt, ok, dropped, total in ho_fits]
    for cc, lbl in runs_c:
        if cc:
            for r in cc["raters"]:
                f = cc["held_out"]["fits"][r]
                cols.append((f"draft {d['draft_version']}, {lbl}, {r}", cc["held_out"]["parts"], collections.Counter(f), 0,
                             cc["held_out"]["parts"] - cc["held_out"]["answered"][r]))
    add(f"Readers assigned the {n_last} parts of llama.cpp and judged how well each fits its type. The first "
        f"{number_word(len(ho_fits))} columns are the held-out readers of draft {ho_types['draft_version']}; the others are the "
        "classification readers of this draft, who marked the fit of every part they assigned.\n")
    add("| Reader's judgement | " + " | ".join(c_[0] for c_ in cols) + " |")
    add("|---|" + "---|" * len(cols))
    for k, word in (("clean", "plainly an instance of one type"),
                    ("partial", "the nearest type, but the part does more or less than the type says"), ("none", "no type")):
        add(f"| {word} | " + " | ".join(str(c_[2].get(k, 0)) for c_ in cols) + " |")
    add("| parts left out as outside an engine | " + " | ".join(str(c_[3]) for c_ in cols) + " |")
    if any(c_[4] for c_ in cols):
        add("| parts the reader gave no answer for (counted as not plainly one type) | " + " | ".join(str(c_[4]) for c_ in cols) + " |")
    add("")
    g = crit["generalisation"]
    old_ok = [ok for _, _, _, ok, _, _ in ho_fits]
    new = [(cc["held_out"]["fits"][r].get("clean", 0), cc["held_out"]["parts"]) for cc, _ in runs_c if cc for r in cc["raters"]]
    add(f"Against the mark (at least {g['clean_fit_min']:.0%} plainly one type, at most {g['no_type_max']:.0%} with none): on "
        f"draft {ho_types['draft_version']} {sum(old_ok)} of {len(old_ok)} readers meet it; on this draft "
        f"{sum(1 for a, b in new if b and a / b >= g['clean_fit_min'])} of {len(new)} readers reach the share of plainly one type.\n")
    if ho_fits and new:
        limits.append(f"The fit figures first reported in 6.2 ({' and '.join(str(c_[2]['clean']) for c_ in cols[:len(ho_fits)])} of "
                      f"{n_last} plainly one type) were given on draft {ho_types['draft_version']}; on this draft the readers "
                      f"gave {', '.join(str(a) for a, _ in new)}.")
    none_ref = sum(1 for ts in assign[X.HELD_OUT].values() if not ts)
    if hc:
        t_ = hc["totals"]
        add(f"A third reader checked llama.cpp against draft {ho_types['draft_version']} in full "
            "(`validation/heldout/check-llama-cpp.yaml`). Of its {0} recorded decisions, {1} are engine-specific; of the "
            "other {2}, {3} ({4}) are plainly a choice of the part's type, {5} loosely and {6} ({7}) not at all. It found "
            "{8} claims of the types that the engine contradicts, {9} causes of an effect on output that the types do not "
            "name, and {10} jobs no type describes, of which {11} are whole parts with no type (section 7)."
            .format(t_["decisions"], t_["engine_specific"], hc["real"], t_["covered"], X.pct(t_["covered"], hc["real"]),
                    t_["loosely"], t_["not_covered"], X.pct(t_["not_covered"], hc["real"]), len(hc["contradictions"]),
                    len(hc["new_causes"]), len(hc["missing_from_the_types"]), none_ref)
            + (" Where its typed totals and its listed entries differ: " + "; ".join(mismatches) + "." if mismatches else "") + "\n")
    else:
        add(f"A third reader, who checked llama.cpp against the types in full, found {none_ref} parts that no type describes.\n")

    # ---- 6.3
    rec = X.load(RECURRENCE) if RECURRENCE.exists() else None
    if rec and len(rec["engines_mapped"]) == n_eng:
        rows_ = rec["choices"]
        inh = [r for r in rows_ if r["type_in_held_out"]]
        grp = [r for r in inh if r["induction"] >= 2]
        rest = [r for r in inh if r["induction"] < 2]
        a, b = sum(r["held_out"] for r in grp), sum(r["held_out"] for r in rest)
        sc = X.shared_counts(rows_)
        one_ = sum(1 for r in rows_ if len(r["engines"]) == 1)
        add("### 6.3 Which choices do several engines decide?\n")
        add(f"The full-detail draft listed {len(rows_)} choices. To see which of them engines share, every design "
            f"decision recorded in the {number_word(n_eng)} inventories ({sum(sum(v.values()) for v in rec['decisions'].values())} in all) "
            "was matched by one reader per engine to at most one choice of its part's type.\n")
        add("| A choice is decided by | Choices |")
        add("|---|---|")
        add(f"| two or more of the {number_word(n_eng)} engines | {sc['covered_2']} |")
        add(f"| one engine | {one_} |")
        add(f"| no engine plainly | {sum(1 for r in rows_ if not r['engines'])} |")
        add("")
        add(("Most choices came from a single engine. " if one_ > len(rows_) / 2 else "")
            + f"This draft keeps the {sc['covered_2']}, which are {sum(len(t.get('choices', [])) for t in d['types'])} after "
            "choices that said nearly the same thing were merged.\n")
        add(f"The {sc['covered_2']} depend on where the line is drawn. Counting a choice when three or more engines plainly "
            f"decide it gives {sc['covered_3']}; counting it when two or more decide it plainly or loosely gives "
            f"{sc['covered_or_loosely_2']}. Of the {sc['covered_2']}, {sc['exactly_2']} rest on exactly two engines.\n")
        limits.append(f"The {sc['covered_2']} shared choices depend on the rule: {sc['covered_3']} with three or more engines, "
                      f"{sc['covered_or_loosely_2']} counting loose matches; {sc['exactly_2']} rest on exactly two engines.")
        add("Does this rule carry over to an engine it was not made from? For this question only, llama.cpp is left "
            f"out of the rule: a choice counts as shared when two or more of the first five engines decide it. Of the "
            f"{len(rows_)} choices, {len(inh)} belong to types llama.cpp has a part for. Among these, llama.cpp decides "
            f"{a} of the {len(grp)} shared choices ({X.pct(a, len(grp))}) and {b} of the other {len(rest)} ({X.pct(b, len(rest))}).\n")
        lm = rec["decisions"].get(X.HELD_OUT, {})
        brief = V / "choices" / "BRIEF.md"
        btext = brief.read_text(encoding="utf-8") if brief.exists() else ""
        # the rules of the mapping brief on how many choices a decision gets and how doubt is counted, word for word
        told_rules = [X.squeeze(m.group(1)) for m in re.finditer(r"(?ms)^- ((?:One decision gets at most one choice|Be strict)[^\n]*(?:\n  [^\n]*)*)", btext)]
        told_rules = [re.split(r"(?<=\.) The purpose", x)[0] for x in told_rules]
        if hc:
            same_n = sum(lm.values()) == hc["totals"]["decisions"]
            add(f"Each engine's decisions were matched by one reader. For llama.cpp two readers judged "
                + ("the same " if same_n else "") + f"decisions against the same draft: the mapping reader called "
                f"{lm.get('covered', 0)} of {sum(lm.values())} plainly a choice, the held-out checker {hc['totals']['covered']} "
                f"of {hc['totals']['decisions']}."
                + (" The mapping readers' stored instructions (`validation/choices/BRIEF.md`) say "
                   + " and ".join(quoted(x, 200) for x in told_rules) if told_rules else "") + "\n")
            limits.append(f"Each decision was matched to a choice by one reader only. Where two readers judged the same "
                          f"engine's decisions (llama.cpp), one found {lm.get('covered', 0)} plainly a choice and the other "
                          f"{hc['totals']['covered']}.")

    # ---- 6.4
    truth = X.strata_truth()
    srcs = truth_sources()
    label = {"qwen-on-pc": "the PC", "qwen-on-spark": "DGX Spark"}
    add("### 6.4 Which types did readers call needed for a model, a machine and a target, against Strata?\n")
    q_exp = weight_size("model-qwen3.8-flash-125b-a6b.yaml", "expert_weights")
    add("Two readers were given this draft and the descriptions of a model, a machine and a target. For each type they "
        "answered: needed, not needed, or open, with the fact or decision that would settle it. Two of the cases are "
        "compared with Strata:\n")
    add(f"- Strata's model on **the PC**. The model has about {q_exp} of expert weights; the PC has "
        + memory_text("hw-pc-12g-64g.yaml") + ".")
    add("- The same model on **DGX Spark**, which has " + memory_text("hw-dgx-spark.yaml") + ".\n")
    for case, s in srcs.items():
        add(f"The answer for {label[case]} is read from `{s['file']}`, whose title is “{s['title']}”"
            + (", a reference reconstruction" if s["reconstruction"] else "")
            + (" from what Strata's documents report" if s["from_documents"] else "")
            + (f"; its environment is `{s['environment']}`" if s["environment"] not in (None, "UNSET") else "")
            + f". It marks {len(s['off'])} of Strata's parts inactive"
            + (": " + "; ".join(f"`{p}`, {quoted(r, 140)}" for p, r in s["off"]) if s["off"] else "") + ".\n")
    recon = [label[c_] for c_, s in srcs.items() if s["reconstruction"]]
    if recon:
        limits.append(f"The answers compared with in 6.4 are reconstructions from my description of Strata ({listing(recon)}"
                      + (", the DGX Spark one from what Strata's documents report" if srcs["qwen-on-spark"]["from_documents"] else "")
                      + "), not observed runs of an engine.")
    leaks = []
    for (s, lbl, run) in sel:
        if not s:
            continue
        w = X.what_readers_were_given(run)
        bits = []
        if w["traces"]:
            bits.append(f"{len(w['traces'])} lines that name an engine or carry what a removed name left behind, such as "
                        + quoted(w["traces"][0]["line"], 90) + f" (`{w['traces'][0]['file']}`)")
        if w["engine_notes"]:
            bits.append(f"{len(w['engine_notes'])} notes on how an engine places or reads the data, such as "
                        + quoted(min(w["engine_notes"], key=lambda n: len(n["line"]))["line"], 120)
                        + f" (`{min(w['engine_notes'], key=lambda n: len(n['line']))['file']}`)")
        if w["seen_in_types"]:
            bits.append(f"`seen_in` on {w['seen_in_types']} of {w['types']} types, naming the engines examined")
        if w["engines_examined"]:
            bits.append("the list of engines examined")
        if w["open_gaps"]:
            bits.append(f"{w['open_gaps']} open gaps, which describe parts of llama.cpp")
        where = f"`{w['types_file']}`" + (f" and `{w['inputs']}`" if w["inputs"] else "")
        nearest = [k for k, own in (("the types file", w["types_file_is_the_runs_own"]),
                                     ("the inputs", w["inputs_are_the_runs_own"] or not w["inputs"])) if not own]
        add(f"What the readers of the {lbl} were given, as far as the stored files show ({where}"
            + (f"; {listing(nearest)} {'is' if len(nearest) == 1 else 'are'} the stored "
               f"{'file' if len(nearest) == 1 and nearest[0] == 'the types file' else 'files'} nearest to what they were "
               "given, not a copy kept with the run" if nearest else "") + "): "
            + (listing(bits) + ". These files were meant to say nothing of an existing engine; they do say it."
               if bits else "nothing that names an engine or says one exists.") + "\n")
        if bits:
            leaks.append((lbl, bits))
    if leaks:
        limits.append("The files given to the selection readers tell of an existing engine, against the method: "
                      + "; ".join(f"{lbl}: {listing(b_.split(',')[0].split(' such as')[0] for b_ in bits)}" for lbl, bits in leaks) + ".")
    told = ((crit.get(thin_key) or {}).get("confirmation_2026_11_17") or {}).get("what_the_readers_saw", "") if thin_key else ""
    if "seen_in" in told and not X.instructions_stored("selection-final"):
        add(f"`validation/criteria.yaml` records that the readers of the confirmation were told not to use `seen_in`; their "
            "instructions are not stored, so this cannot be checked.\n")

    am = X.load(AMEND)
    patched = am.get("type_patches") or {}
    say = {"yes": "needed", "no": "not needed", "open": "open", "no answer": "no answer"}
    for (s, lbl, run) in sel:
        if not s:
            continue
        cond = s["conditions"]
        uncond = set(s["unconditional"] or [])
        ans = s["answers"]
        rd = sorted(next(iter(ans.values())).keys())
        both = lambda tg, v: {t for t in types if all(ans[tg].get(r, {}).get(t, {}).get("needed") == v for r in rd)}
        differ = lambda tg: [t for t in types if len({ans[tg].get(r, {}).get(t, {}).get("needed") for r in rd}) > 1]
        add(f"**{lbl[0].upper() + lbl[1:]}** (`validation/{run}/`, types as in `{s['types_file']}`: {len(uncond)} of "
            f"{len(types)} types have no `needed_when`, so every engine has them by definition).\n")
        add("| Case | Both readers said | Types | Of these, with no `needed_when` | Strata has an active part | The same, main types only |")
        add("|---|---|---|---|---|---|")
        for tg in ("qwen-on-pc", "qwen-on-spark"):
            runs_, main = set(truth[tg]["runs"]), set(truth[tg]["main"])
            for v, word in (("yes", "needed"), ("no", "not needed"), ("open", "open")):
                ts = both(tg, v)
                add(f"| {label[tg]} | {word} | {len(ts)} | {len(ts & uncond)} | {len(ts & runs_)} | {len(ts & main)} |")
            add(f"| {label[tg]} | the readers differed | {len(differ(tg))} | | | |")
        add("")
        for tg in ("qwen-on-pc", "qwen-on-spark"):
            runs_ = set(truth[tg]["runs"])
            yes = both(tg, "yes")
            add(f"{label[tg][0].upper() + label[tg][1:]}: of the {len(yes)} types both called needed, {len(yes & uncond)} have no "
                f"`needed_when`; on the {len(yes - uncond)} conditional ones Strata has an active part for "
                f"{len((yes - uncond) & runs_)}. `open` answers: "
                + ", ".join(f"{r} {sum(1 for a in ans[tg][r].values() if a['needed'] == 'open')}" for r in rd)
                + f" of {len(types)}; an open answer cannot be scored wrong." + chr(10))
        only_also = {tg: sorted(set(truth[tg]["runs"]) - set(truth[tg]["main"])) for tg in ("qwen-on-pc", "qwen-on-spark")}
        add(f"Types Strata has only as a further type of a part (`also`): on the PC {names(only_also['qwen-on-pc'])}; "
            f"on DGX Spark {names(only_also['qwen-on-spark'])}. The last column counts without them.\n")
        yes_pc, no_pc = both("qwen-on-pc", "yes"), both("qwen-on-pc", "no")
        add(f"On the PC, types both readers called needed for which Strata has no separate part: "
            f"{names(sorted(yes_pc - set(truth['qwen-on-pc']['runs'])))}. Types both called not needed for which Strata has an "
            f"active part: {names(sorted(no_pc & set(truth['qwen-on-pc']['runs'])))}.\n")
        dropped = set(truth["qwen-on-pc"]["runs"]) - set(truth["qwen-on-spark"]["runs"])
        said = both("qwen-on-spark", "no") - no_pc
        extra = (both("qwen-on-spark", "no") - dropped) & set(truth["qwen-on-spark"]["runs"])
        why = X.reasons_against_truth(run, "qwen-on-spark", sorted(dropped & said))
        resting = [x for x in why if x["rests_on_absent_but_present"]]
        add(f"On DGX Spark Strata no longer runs {names(sorted(dropped))}. Both readers called {len(dropped & said)} of these "
            f"{len(dropped)} not needed there"
            + (f". They also called {names(sorted(extra))} not needed there, which Strata still runs" if extra else "")
            + ((f". Of the {len(why)} answers `not needed` on the {len(dropped & said)} types Strata no longer runs, "
                f"{len(resting)} give as their reason "
                "that another type is absent which Strata still runs there"
                + (f" ({names(sorted({u for x in resting for u in x['rests_on_absent_but_present']}))}; for example "
                   + quoted(resting[0]["because"], 120) + "): the answer matches the known one, its ground does not"
                   if resting else ""))
               if why else "") + ".\n")
        cases_ = [tg for tg in X.TARGETS if tg in ans]
        per_case = {tg: collections.Counter(tuple(sorted({ans[tg].get(r, {}).get(t, {}).get("needed") or "no answer" for r in rd}))
                                            for t in differ(tg)) for tg in cases_}
        n_diff = sum(sum(c_.values()) for c_ in per_case.values())
        if not n_diff:
            add(f"The two readers gave the same answer on every type in all {number_word(len(cases_))} cases.\n")
        else:
            add("Where the two readers differed, by case: " + "; ".join(
                f"{label.get(tg, CASES.get(tg, tg))}, " + ", ".join(f"{n} {'type' if n == 1 else 'types'} {' against '.join(say[v] for v in p)}"
                                                                 for p, n in cnt.most_common())
                for tg, cnt in per_case.items() if cnt)
                + (f" (none on {listing(label.get(tg, CASES.get(tg, tg)) for tg, cnt in per_case.items() if not cnt)})"
                   if any(not cnt for cnt in per_case.values()) else "") + ".\n")
    if len([s for s, _, _ in sel if s]) == 2:
        (s1, l1, r1), (s2, l2, r2) = sel
        c1, c2 = s1["conditions"], s2["conditions"]
        reworded = [t for t in types if c1.get(t) != c2.get(t)]
        noted = [t for t in reworded if t in patched]
        add(f"Between the two runs the conditions of {len(reworded)} types were reworded"
            + (f" (recorded in `validation/thin/amendments-0.9.yaml`, `type_patches`)" if noted else "") + ": "
            + "; ".join(f"`{t}` from {quoted(c1.get(t) or 'none (always needed)', 120)} to {quoted(c2.get(t) or 'none', 120)}"
                        for t in reworded) + ". How the answers on them changed: "
            + "; ".join(f"`{t}` on {label.get(tg, CASES.get(tg, tg))}: " + ", ".join(
                f"{r} {say[s1['answers'][tg].get(r, {}).get(t, {}).get('needed') or 'no answer']} → "
                f"{say[s2['answers'][tg].get(r, {}).get(t, {}).get('needed') or 'no answer']}" for r in sorted(s1['answers'][tg]))
                for t in reworded for tg in ("qwen-on-pc", "qwen-on-spark", "muse-on-spark")) + ".\n")
        if reworded:
            limits.append(f"After the first selection run the conditions of {len(reworded)} types ({names(reworded)}) were "
                          "reworded on what its readers reported, and the check was run again. Both runs are reported in 6.4.")
        uncond2 = len(s2["unconditional"] or [])
        limits.append(f"{uncond2} of the {len(types)} types have no `needed_when`: every engine has them by definition, so a "
                      "reader who calls them needed is not tested by the case.")

    # ---- 6.5
    s_last = next((s for s, _, _ in reversed(sel) if s), None)
    if s_last:
        ans = s_last["answers"]
        rd = sorted(next(iter(ans.values())).keys())
        both = lambda tg, v: [t for t in types if all(ans[tg].get(r, {}).get(t, {}).get("needed") == v for r in rd)]
        differ = lambda tg: [t for t in types if len({ans[tg].get(r, {}).get(t, {}).get("needed") for r in rd}) > 1]
        tg_dir = "muse-on-spark"
        m_exp = weight_size("model-muse-spark-open.yaml", "expert_weights")
        hw = X.load(ROOT / "examples" / "given" / "hw-dgx-spark.yaml")
        pool = next((p for p in hw.get("memory_pools", []) if p.get("kind") == "unified_ram"), None)
        cap = pool["capacity_nominal"] if pool else None
        exp = next((x for x in X.load(ROOT / "examples" / "given" / "model-muse-spark-open.yaml").get("data", [])
                    if x["id"] == "expert_weights"), None)
        ratio = (exp["size"]["value"] / cap["value"]) if exp and cap and exp["size"]["unit"] == cap["unit"] else None
        r_last = next(r for s, _, r in reversed(sel) if s)
        given_dir = X.given_to(r_last)[1]
        given_target = (given_dir / tg_dir / "target.yaml") if given_dir else None
        readers_own = bool(given_target and given_target.exists())
        target = X.load(given_target if readers_own else ROOT / "examples" / "specs" / "muse-spark-open-on-dgx-spark.target.yaml")
        io = target.get("interface") or {}
        def unset_paths(x, at=""):
            if isinstance(x, dict):
                if "id" in x and at:
                    at = at.rsplit(".", 1)[0] + "." + str(x["id"])
                return [q for k, v in x.items() for q in unset_paths(v, f"{at}.{k}" if at else k)]
            if isinstance(x, list):
                return [q for v in x for q in unset_paths(v, at)]
            return [at] if x == "UNSET" else []
        unset = [q.replace("contract.requirements.", "") for q in unset_paths(target) if not q.startswith("given.")]
        tg = "muse-on-spark"
        sw = [t["id"] for t in d["types"] if t["group"] == "selective-weights"]
        add("### 6.5 The same question for Muse Spark Open on DGX Spark\n")
        add(f"No engine exists for this case, so there is no answer to compare with. Muse Spark Open is a mixture-of-experts "
            f"model with about {m_exp} of expert weights (at the 4 bits of the weights as published)"
            + (f", about {ratio:.1f} times the {cap['value']} {cap['unit']} of DGX Spark's memory" if ratio else "") + ". "
            f"Of the types for selectively used weights, both readers called {names([t for t in sw if t in both(tg, 'yes')])} "
            f"needed here; for Strata's smaller model on the same machine they called "
            f"{names([t for t in sw if t in both('qwen-on-spark', 'no')])} not needed. "
            + ("The target the readers were given (the file as it stood then, stored with the run) is "
               if readers_own else "The target is ")
            + f"{(io.get('input') or {}).get('modality', '?')} in and {(io.get('output') or {}).get('modality', '?')} out"
            + (f"; it left {len(unset)} items not set: {names(unset)}" if unset else "") + ".\n")
        add("| Both readers said | Node types |")
        add("|---|---|")
        add(f"| needed | {names(both(tg, 'yes'))} |")
        add(f"| not needed | {names(both(tg, 'no'))} |")
        add(f"| open: a fact the target does not state yet, or a decision left to the builder | {names(both(tg, 'open'))} |")
        add(f"| the readers differed | {names(differ(tg))} |")
        add("")

    # ---- 6.6
    real_stages_section(add)

    # ---- 6.7
    add("### 6.7 Limits\n")
    readers = (crit.get(thin_key) or {}).get("readers") if thin_key else None
    add("- The readers are Claude subagents" + (f" (`validation/criteria.yaml`: {quoted(readers, 140)})" if readers else "")
        + ". Two readers of one check are runs of the same model reading the same files, so their agreement with each "
        "other says less than their agreement with the key or with Strata.")
    add(f"- The key of 6.1 for the first {number_word(len(X.INDUCTION))} engines is my own assignment of parts, and the key for "
        f"{ENGINE_NAMES[X.HELD_OUT]} is its held-out checker's (`validation/heldout/check-{X.HELD_OUT}.yaml`); the answers compared "
        "with in 6.4 come from my own description of Strata. All were written from source code.")
    if not claims_checked_now:
        add(f"- Draft {d['draft_version']} was not checked against the engines for its rules or its effect on output"
            + (f"; the last such check was of draft {checked_drafts[-1]}" if checked_drafts else "") + ".")
    for x in limits:
        add(f"- {x}")
    add("")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    th = sub.add_parser("thin")
    th.add_argument("--min-engines", type=int, default=2)
    th.add_argument("--no-choices", action="store_true")
    th.add_argument("--no-gaps", action="store_true")
    th.add_argument("--out", type=pathlib.Path, default=DRAFT)
    sub.add_parser("example").add_argument("engine")
    sub.add_parser("suggest").add_argument("design")
    rp = sub.add_parser("repin")
    rp.add_argument("design")
    rp.add_argument("nodes", nargs="*")
    sub.add_parser("check")
    sub.add_parser("doc")
    a = ap.parse_args()
    if a.cmd == "thin":
        return thin(a.min_engines, not a.no_choices, a.out.resolve(), not a.no_gaps)
    if a.cmd == "example":
        return example(a.engine)
    if a.cmd == "suggest":
        return suggest(a.design)
    if a.cmd == "repin":
        return repin(a.design, a.nodes)
    if a.cmd == "check":
        return check()
    return doc()


if __name__ == "__main__":
    sys.exit(main())
