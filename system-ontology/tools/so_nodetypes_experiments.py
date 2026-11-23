#!/usr/bin/env python3
"""Inputs and scoring for the checks run on the thin node types (draft 0.9).

    python tools/so_nodetypes_experiments.py packets [DESIGN]  # choices: one packet per engine for the mapping readers;
                                                               # with a name, the packet of that design only
    python tools/so_nodetypes_experiments.py pin-map DESIGN    # choices: key a reader's map of a design by decision id and text
    python tools/so_nodetypes_experiments.py recurrence     # choices: count, per choice, the engines that decide it
    python tools/so_nodetypes_experiments.py anon KEYFILE [ROUND]      # classification: anonymised parts of all six engines
    python tools/so_nodetypes_experiments.py classify KEYFILE [ROUND]  # classification: score the raters in validation/ROUND
    python tools/so_nodetypes_experiments.py selection-inputs DIR  # selection: what the readers of a new run are given
    python tools/so_nodetypes_experiments.py truth          # selection: the node types Strata runs on each machine
    python tools/so_nodetypes_experiments.py selection [DIR]   # selection: score the readers in validation/DIR
    python tools/so_nodetypes_experiments.py instructions DIR FILE [NAME]  # keep the instructions a run's readers were given

ROUND defaults to round8 and DIR to selection, the first run on the thin draft. The confirmation on the final draft 0.9
is in round9 and selection-final.

Pass marks. `validation/criteria.yaml` holds the marks set on its `set_on` date. `classify`, `selection` and
`recurrence` compute their figures against the mark that applies to each, print `met` or `not met`, and exit with 1
when a mark is not met or a reader's file has a problem. A figure no mark applies to is printed with "no mark was
set for this check". A missing answer is never counted as agreement.

  choices         Every decision recorded in the six inventories is matched to at most one choice of its part's node
                  type. A choice is generic when engines decide it independently; one seen in a single engine is an
                  example from that engine.
  classification  Readers who see only the thin types classify the parts of all six engines, names removed.
  selection       Readers who see only the thin types, a model, a machine and a target say which node types the
                  engine needs. For Strata's two machines the answer is compared with its resolved specs.
"""
import collections
import hashlib
import pathlib
import random
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
V = ROOT / "validation"
FROZEN = V / "heldout" / "node-types.draft-0.8.yaml"
DRAFT = ROOT / "ontology" / "node-types.draft.yaml"
AMEND = V / "thin" / "amendments-0.9.yaml"
CRITERIA = V / "criteria.yaml"
INDUCTION = ["strata", "ds4", "hyperqwen", "ninfer", "splash"]
HELD_OUT = "llama-cpp"
ENGINES = INDUCTION + [HELD_OUT]
FITS = ("clean", "partial", "none")
# The runs of the two reader checks on the thin draft, in the order they were made, and the stored files nearest to
# what their readers were given when the run directory does not hold them itself (validation/criteria.yaml,
# `thin_draft_2026_11_17`). A run made with `selection-inputs` holds its own files and needs no entry here.
CLASSIFICATION_RUNS = [("round8", "first run"), ("round9", "confirmation")]
SELECTION_RUNS = [("selection", "first run"), ("selection-final", "confirmation")]
GIVEN = {"round8": {"types": "round8/node-types.thin.yaml"},
         "round9": {"types": "round9/node-types.for-readers.yaml"},
         "selection": {"types": "round8/node-types.thin.yaml", "inputs": "selection/inputs"},
         "selection-final": {"types": "round9/node-types.for-readers.yaml", "inputs": "selection/inputs"}}


def load(p):
    return yaml.safe_load(pathlib.Path(p).read_text(encoding="utf-8"))


def dump(p, data, header=""):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=118), encoding="utf-8")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shown(p):
    p = pathlib.Path(p)
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)


def pct(a, b):
    """A share as text. A share that is not all of `b` is never printed as 100%, and one that is not zero never as 0%."""
    if not b:
        return "n/a"
    if a == b:
        return "100%"
    if a == 0:
        return "0%"
    x = 100 * a / b
    if x == round(x):
        return f"{x:.0f}%"
    return f"{min(max(round(x, 1), 0.1), 99.9):.1f}%"


# ---------------------------------------------------------------- pass marks

def criteria():
    return load(CRITERIA)


def judged(check, path, a, b=None, note="", scoring=True):
    """One figure against the mark at `path` of validation/criteria.yaml (`section.key`; `_min` is a least share or
    count, `_max` a greatest). `b` is the denominator of a share; without it `a` is a count. A share of nothing is
    not met. `scoring` is false for a figure shown beside the one the scorer's result rests on."""
    sec, key = path.split(".")
    limit = criteria()[sec][key]
    least = key.endswith("_min")
    if b is None:
        value, figure = a, str(a)
        lim = f"at {'least' if least else 'most'} {limit}"
    else:
        value, figure = (a / b if b else None), f"{a} of {b} ({pct(a, b)})"
        lim = f"at {'least' if least else 'most'} {limit:.0%}"
    ok = False if value is None else bool(value >= limit if least else value <= limit)
    return {"check": check, "mark": path, "limit": lim, "figure": figure, "met": ok, "note": note, "scoring": scoring}


def unmarked(check, figure, note=""):
    return {"check": check, "mark": None, "limit": "no mark was set for this check", "figure": figure, "met": None,
            "note": note, "scoring": False}


def met_word(row):
    return {True: "met", False: "not met", None: ""}[row["met"]]


def print_marks(rows, problems=()):
    """Print the figures against their marks. Returns 1 when a scoring mark is not met or there is a problem."""
    c = criteria()
    print(f"\nAgainst the pass marks set on {c['set_on']} (validation/criteria.yaml)")
    print("| check | mark | figure | | note |")
    print("|---|---|---|---|---|")
    for r in rows:
        mark = f"{r['limit']} (`{r['mark']}`)" if r["mark"] else r["limit"]
        word = met_word(r) + ("" if r["scoring"] or r["met"] is None else " (shown beside; not the scoring rule)")
        print(f"| {r['check']} | {mark} | {r['figure']} | {word} | {r['note']} |")
    failed = [r for r in rows if r["scoring"] and r["met"] is False]
    for p in problems:
        print("PROBLEM", p)
    if failed or problems:
        print(f"RESULT: FAIL. {len(failed)} of {sum(1 for r in rows if r['scoring'])} marks not met"
              + (f", {len(problems)} problems" if problems else ""))
        return 1
    print(f"RESULT: pass. {sum(1 for r in rows if r['scoring'])} marks met")
    return 0


def instructions_stored(*dirs):
    """The files that hold what the readers of a run were told, in the given directories under validation/."""
    out = []
    for d in dirs:
        d = V / d
        if d.is_dir():
            out += sorted(p for p in d.iterdir() if p.is_file() and re.fullmatch(r"(?i)(instructions.*|.*brief.*)\.md", p.name))
    return out


def store_instructions(where, source, name=""):
    """Copy the instructions given to the readers of a run into its directory. A stored file is a record and is not
    written a second time."""
    src = pathlib.Path(source)
    if not src.is_file():
        print(f"PROBLEM no file {source}")
        return 1
    dst = V / where / (f"INSTRUCTIONS-{name}.md" if name else "INSTRUCTIONS.md")
    if dst.exists():
        print(f"PROBLEM {shown(dst)} exists; the instructions of a run are a record and are not replaced")
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    dst.write_bytes(data)
    print(f"stored {shown(dst)}: {len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()}")
    return 0


# ---------------------------------------------------------------- inventories and the key

def inventory(engine):
    """An engine's parts, and the corrections later readers confirmed against its source."""
    if engine == HELD_OUT:
        return load(V / "held-out" / "llama-cpp.yaml")["parts"], []
    cor = V / "inventory" / f"{engine}.corrections.yaml"
    return load(V / "inventory" / f"{engine}.yaml")["parts"], (load(cor)["corrections"] if cor.exists() else [])


def read_reference(path):
    """engine -> part -> the node types a stored key accepts for it, first the main one."""
    ref = load(path)
    also = ref.pop("also", {}) or {}
    out = {}
    for e, parts in ref.items():
        out[e] = {}
        for p, t in parts.items():
            extra = also.get(e, {}).get(p) or []
            out[e][p] = [t, *([extra] if isinstance(extra, str) else extra)]
    return out


def assignments():
    """engine -> part -> the node types it is an instance of, first the main one. Empty when it has no type.

    The five induction engines were assigned by the author of the types; the held-out engine by its independent
    checker, after the types were frozen."""
    out = read_reference(V / "reference-assignment.yaml")
    h = load(V / "heldout" / "check-llama-cpp.yaml")
    out[HELD_OUT] = {p: ([] if t == "none" else [t, *h.get("also", {}).get(p, [])]) for p, t in h["assignment"].items()}
    return out


def key_history():
    """How the key of the five induction engines changed from one stored copy to the next.

    Each step compares two stored keys and says, for every part whose accepted types changed, whether the later key
    newly accepts a type that a reader of the earlier round had given for that part."""
    files = sorted(V.glob("round*/reference-assignment-*.yaml"),
                   key=lambda p: [int(x) for x in re.findall(r"\d+", p.stem.split("-")[-1])])
    files.append(V / "reference-assignment.yaml")
    public = load(V / "parts.key.yaml") if (V / "parts.key.yaml").exists() else {}
    steps, prev = [], None
    for f in files:
        cur = read_reference(f)
        entry = {"file": shown(f), "parts": sum(len(v) for v in cur.values()),
                 "with_further_types": sum(1 for v in cur.values() for ts in v.values() if len(ts) > 1)}
        if prev is not None:
            pf, pk = prev
            given = collections.defaultdict(set)
            for rf in sorted(pf.parent.glob("rater-*.yaml")) if pf.parent != V else []:
                for a in load(rf)["assignments"]:
                    if a["item"] in public:
                        given[tuple(public[a["item"]])].add(a.get("node_type") or "none")
            main = further = toward = 0
            for e, parts in cur.items():
                for p, ts in parts.items():
                    old = pk.get(e, {}).get(p)
                    if old is None or (old[0] == ts[0] and set(old) == set(ts)):
                        continue
                    main += old[0] != ts[0]
                    further += old[0] == ts[0]
                    toward += bool((set(ts) - set(old)) & given.get((e, p), set()))
            entry |= {"main_type_changed": main, "further_types_changed": further,
                      "newly_accepts_a_type_a_reader_of_the_round_before_gave": toward}
        steps.append(entry)
        prev = (f, cur)
    return steps


_WS = None


def workspace():
    global _WS
    if _WS is None:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import so_check as sc
        _WS = sc.Workspace(ROOT)
    return _WS


# ---------------------------------------------------------------- designs

def designs():
    """name -> system id, for every described system whose components are derived from other engines' components.

    A design is described with the node types but is not evidence for them: it is left out of `seen_in`, of the count
    of engines per choice and of every check."""
    ws = workspace()
    out = {}
    for c in ws.of_kind("component"):
        if c.get("derived_from") and c["system"].split("/")[-1] not in ENGINES:
            out[c["system"].split("/")[-1]] = c["system"]
    return out


def design_parts(name):
    import so_inventory
    return so_inventory.parts_of(workspace(), designs()[name])[2]


def design_components(name):
    """part -> the description of each leaf component of a design, in the order of its files."""
    ws, sid = workspace(), designs()[name]
    return {c["id"].split("/")[-1]: c for c in ws.of_kind("component") if c["system"] == sid and not c.get("parts")}


def component_decisions(c):
    """(decision id, text) of each decision a component records with a text."""
    return [(d.get("id") or f"text-{sha(d['text'])[:12]}", d["text"]) for d in c.get("decisions") or [] if d.get("text")]


def assignment_path(name):
    return workspace().files[designs()[name]].parent / "node-assignment.yaml"


def squeeze(s):
    return " ".join(str(s).split())


def design_assignment(name):
    """(part -> node types, problems) for a design.

    The type of every node of a design is stated in `node-assignment.yaml` beside the design's files, by whoever
    read the component's own text against the type definitions. An entry holds the type (or none), how well the
    component fits it, the words of the component's responsibility the reading rests on, one sentence of basis, and
    the SHA-256 of the responsibility as it was read. Nothing is inherited from the component a part is derived
    from: `suggest` prints that as a suggestion only. A part with no entry, an entry whose pin is not the SHA-256 of
    the component's current responsibility, a type the draft does not have, or a quote that is not in the
    responsibility is a problem, and the part gets no type."""
    comps, path = design_components(name), assignment_path(name)
    known = {t["id"] for t in load(DRAFT)["types"]}
    if not path.exists():
        return {}, [f"{name}: no {shown(path)}; the node type of every part of a design is stated there"]
    stated = load(path).get("nodes") or {}
    out, problems = {}, []
    for part, c in comps.items():
        e, where = stated.get(part), f"{name}/{part}"
        if not isinstance(e, dict):
            problems.append(f"{where}: no entry in {shown(path)}")
            continue
        bad = []
        types = ([e["type"]] if e.get("type") else []) + list(e.get("also") or [])
        for t in types:
            if t not in known:
                bad.append(f"names the type '{t}', which the draft does not have")
        if len(set(types)) != len(types):
            bad.append("names a type twice")
        if e.get("fit") not in FITS:
            bad.append(f"fit is {e.get('fit')!r}; it is one of {', '.join(FITS)}")
        if e.get("fit") == "none" and types:
            bad.append("fit is none but a type is given; a part no type describes has `type: null`")
        if e.get("fit") in ("clean", "partial") and not e.get("type"):
            bad.append(f"fit is {e['fit']} but no type is given")
        if e.get("fit") in ("partial", "none") and not e.get("reason"):
            bad.append(f"fit is {e['fit']} and no reason is given")
        if not e.get("basis"):
            bad.append("no basis is given")
        if e.get("responsibility_sha256") != sha(c["responsibility"]):
            bad.append("the responsibility has changed since it was read (the pin does not match); read it again, "
                       f"or see `so_nodetypes.py repin {name}`")
        elif not e.get("quote") or squeeze(e["quote"]) not in squeeze(c["responsibility"]):
            bad.append("the quote is not in the component's responsibility word for word")
        if bad:
            problems += [f"{where}: {b}" for b in bad]
        else:
            out[part] = types
    for part in stated:
        if part not in comps:
            problems.append(f"{name}/{part}: {shown(path)} has an entry for it, and the design has no such leaf component")
    return out, problems


def suggestions(name):
    """part -> what the components it is derived from are in the examined engines' key. A suggestion for whoever
    reads the component, never an answer: the component's own text is not looked at here."""
    assign, out = assignments(), {}
    for part, c in design_components(name).items():
        src = c.get("derived_from") or []
        out[part] = []
        for d in (src if isinstance(src, list) else [src]):
            bits = d["component"].split("/")
            out[part].append({"from": d["component"], "carried_as": d.get("carried_as"),
                              "types": assign.get(bits[1], {}).get(bits[-1])})
    return out


def frozen_choices():
    """type -> [(choice id, kind, what)] of the frozen draft. The id is the type and the position in that draft."""
    return {t["id"]: [(f"{t['id']}#{i:02d}", c["kind"], c["what"]) for i, c in enumerate(t.get("choices", []), 1)]
            for t in load(FROZEN)["types"]}


def draft_choice_of():
    """choice id of the frozen draft -> (node type, text) of the choice of the current draft it became, or None when
    the current draft does not keep it. Choices the amendments merged lead to the merged choice."""
    am, draft = load(AMEND), load(DRAFT)
    into, text = {}, {}
    for m in am.get("merge_choices") or []:
        for r in m["ids"][1:]:
            into[r] = m["ids"][0]
        if m.get("what"):
            text[m["ids"][0]] = m["what"]
    frozen = {cid: what for cs in frozen_choices().values() for cid, _, what in cs}
    kept = {t["id"]: {c["what"] for c in t.get("choices", [])} for t in draft["types"]}
    out = {}
    for cid in frozen:
        tgt = into.get(cid, cid)
        t, what = tgt.split("#")[0], text.get(tgt, frozen[tgt])
        out[cid] = (t, what) if what in kept.get(t, ()) else None
    return out


# ---------------------------------------------------------------- choices

def _packet_pairs(pk):
    """What a map that names decisions by number depends on: the part, its types, the number and the text."""
    return [(p["part"], tuple(p.get("types") or []), d["d"], d["text"]) for p in pk.get("parts", []) for d in p["decisions"]]


def packet_problems(name):
    """How the stored packet of a design differs from the design as it is now: a decision removed, added or reworded,
    or a part whose node types have changed. Each is a problem, because a reader's map was judged on the packet."""
    pkp = V / "choices" / f"packet-{name}.yaml"
    if not pkp.exists():
        return [f"{name}: no {shown(pkp)}"]
    pk = load(pkp)
    types_of, _ = design_assignment(name)
    current = {f"{part}/{did}": (part, sha(text)) for part, c in design_components(name).items()
               for did, text in component_decisions(c)}
    out, seen = [], set()
    for p in pk.get("parts", []):
        if p["part"] in types_of and list(p.get("types") or []) != types_of[p["part"]]:
            out.append(f"{name}: packet part {p['part']} has types {p.get('types')}; node-assignment.yaml now says {types_of[p['part']]}")
        for d in p["decisions"]:
            key = d.get("decision")
            if not key:
                out.append(f"{name}: packet {d['d']} has no decision id; the packet was written before decisions were keyed")
                continue
            seen.add(key)
            if key not in current:
                out.append(f"{name}: packet {d['d']} ({key}) is a decision the component no longer has")
            elif current[key][1] != sha(d["text"]):
                out.append(f"{name}: packet {d['d']} ({key}): the text has changed since the packet was written")
    out += [f"{name}: decision {k} is not in the packet" for k in current if k not in seen]
    return out


def packets(only=None):
    """Write the packet a mapping reader is given. A packet numbers the decisions by position (D001, ...), so a
    stored map that names decisions only by that number is tied to the packet it was judged on: such a packet is
    not written again once its decisions have changed."""
    choices, assign = frozen_choices(), assignments()
    status = 0
    for e in ([only] if only else ENGINES):
        design = e in designs()
        if design:
            types_of, problems = design_assignment(e)
            if problems:
                for p in problems:
                    print("PROBLEM", p)
                print(f"packet-{e}.yaml not written: {len(problems)} problems in the design's node types")
                status = 1
                continue
            parts = [{"id": part, "does": c["responsibility"], "decisions": component_decisions(c)}
                     for part, c in design_components(e).items()]
            corrections = []
        else:
            if e not in assign:
                print(f"PROBLEM {e}: not an examined engine and not a design")
                status = 1
                continue
            types_of = assign[e]
            inv, corrections = inventory(e)
            parts = [{"id": p["id"], "does": p["does"], "decisions": [(None, t) for t in p.get("decisions") or []]} for p in inv]
        by_part = collections.defaultdict(list)
        for c in corrections:
            if c.get("field") in ("decisions", "parts", "does"):
                by_part[c.get("part")].append({k: c[k] for k in ("field", "recorded", "source_shows") if k in c})
        out_parts, used, n = [], [], 0
        for p in parts:
            types = types_of.get(p["id"])
            if types is None:
                raise SystemExit(f"{e}: part {p['id']} has no entry in the assignment")
            decisions = []
            for did, text in p["decisions"]:
                n += 1
                row = {"d": f"D{n:03d}"}
                if design:
                    row |= {"decision": f"{p['id']}/{did}", "text_sha256": sha(text)}
                decisions.append(row | {"text": text})
            if not decisions:
                continue
            item = {"part": p["id"], "does": p["does"], "types": types, "decisions": decisions}
            if by_part.get(p["id"]):
                item["corrections"] = by_part[p["id"]]
            out_parts.append(item)
            used += [t for t in types if t not in used]
        new = {"engine": e, "decisions": n, "parts": out_parts,
               "candidates": {t: [{"id": i, "kind": k, "what": w} for i, k, w in choices[t]] for t in used}}
        dst, mp = V / "choices" / f"packet-{e}.yaml", V / "choices" / f"map-{e}.yaml"
        if dst.exists() and mp.exists():
            by_number = [r for r in load(mp)["map"] if not r.get("decision")]
            if by_number and _packet_pairs(load(dst)) != _packet_pairs(new):
                print(f"PROBLEM {e}: the decisions have changed since packet-{e}.yaml was written, and {len(by_number)} rows of "
                      f"map-{e}.yaml name decisions by their number in that packet. The packet is not written again: the map "
                      "would point at other decisions. Have the changed decisions judged again, or remove the map.")
                status = 1
                continue
        dump(dst, new, "# Written by tools/so_nodetypes_experiments.py packets. Read validation/choices/BRIEF.md first.\n")
        print(f"packet-{e}.yaml: {n} decisions in {len(out_parts)} parts, {len(used)} node types")
        if design and mp.exists():
            stale = design_map(e)[1]
            for p in stale:
                print("PROBLEM", p)
            if stale:
                print(f"map-{e}.yaml does not match the design as it is now: {len(stale)} problems; the decisions named "
                      "must be judged again against the new packet")
                status = 1
    return status


def _row_problems(e, name, c, fit, known, allowed):
    out = []
    if fit not in ("covered", "loosely", "none", "engine_specific"):
        out.append(f"{e} {name}: fit {fit!r}")
    if fit in ("covered", "loosely") and (c not in known or c not in allowed):
        out.append(f"{e} {name}: choice {c!r} is not a candidate of this part")
    return out


def read_maps(names=None):
    """engine -> decision number -> (choice id or None, fit), for the examined engines. Engines whose map is missing
    are left out.

    A map names decisions by their number in the packet its reader was given. The packet is therefore compared with
    the inventory and the key as they are now; a part whose decisions or types differ is a problem, because the
    rows of the map may then stand for other decisions."""
    choices, assign = frozen_choices(), assignments()
    known = {i for cs in choices.values() for i, _, _ in cs}
    maps, problems = {}, []
    for e in (names or ENGINES):
        mp, pkp = V / "choices" / f"map-{e}.yaml", V / "choices" / f"packet-{e}.yaml"
        if not mp.exists():
            continue
        if not pkp.exists():
            problems.append(f"{e}: map-{e}.yaml has no packet-{e}.yaml to read its decision numbers from")
            continue
        pk = load(pkp)
        current = {p["id"]: list(p.get("decisions") or []) for p in inventory(e)[0]}
        in_packet = {p["part"]: p for p in pk["parts"]}
        stale = []
        for part, texts in current.items():
            p = in_packet.get(part)
            if texts and p is None:
                stale.append(f"part {part} has decisions and is not in the packet")
            elif p is not None and [d["text"] for d in p["decisions"]] != texts:
                stale.append(f"the decisions of part {part} are not those of the inventory now")
            elif p is not None and p["types"] != assign[e].get(part):
                stale.append(f"the types of part {part} are not those of the key now")
        stale += [f"part {part} is in the packet and not in the inventory" for part in in_packet if part not in current]
        problems += [f"{e}: packet-{e}.yaml is stale, so map-{e}.yaml cannot be relied on: {s}" for s in stale]
        allowed = {}
        for p in pk["parts"]:
            cand = {c["id"] for t in p["types"] for c in pk["candidates"][t]}
            for d in p["decisions"]:
                allowed[d["d"]] = cand
        got = {}
        for row in load(mp)["map"]:
            d, c, fit = row["d"], row.get("choice"), row["fit"]
            if d not in allowed:
                problems.append(f"{e} {d}: no such decision")
                continue
            if d in got:
                problems.append(f"{e} {d}: judged twice")
            problems += _row_problems(e, d, c, fit, known, allowed[d])
            got[d] = (c if fit in ("covered", "loosely") else None, fit)
        for d in allowed:
            if d not in got:
                problems.append(f"{e} {d}: not judged")
        maps[e] = got
    return maps, problems


def engine_map(name):
    """(part -> [(decision number, text, choice id or None, fit)], problems) for an examined engine, through its packet."""
    maps, problems = read_maps([name])
    if name not in maps:
        return {}, problems + [f"no validation/choices/map-{name}.yaml"]
    out = collections.defaultdict(list)
    for p in load(V / "choices" / f"packet-{name}.yaml")["parts"]:
        for d in p["decisions"]:
            if d["d"] in maps[name]:
                out[p["part"]].append((d["d"], d["text"], *maps[name][d["d"]]))
    return out, problems


def design_map(name):
    """(part -> [(decision id, text, choice id or None, fit)], problems) for a design.

    A row of the design's map names a decision by the component's own decision id and holds the SHA-256 of the text
    it was judged on. A row whose decision the component no longer has, or whose text has changed, is a problem and
    matches nothing; so is a decision with no row. The position of a decision plays no part."""
    comps = design_components(name)
    types_of, problems = design_assignment(name)
    choices = frozen_choices()
    known = {i for cs in choices.values() for i, _, _ in cs}
    mp = V / "choices" / f"map-{name}.yaml"
    if not mp.exists():
        return {}, problems + [f"{name}: no validation/choices/map-{name}.yaml"]
    current = {f"{part}/{did}": (part, text) for part, c in comps.items() for did, text in component_decisions(c)}
    out, seen = collections.defaultdict(list), set()
    for row in load(mp)["map"]:
        key, c, fit = row.get("decision"), row.get("choice"), row.get("fit")
        if not key:
            problems.append(f"{name} {row.get('d')}: the row names its decision only by a packet number; key the map with "
                            f"`so_nodetypes_experiments.py pin-map {name}` while the packet it was judged on is unchanged")
            continue
        if key in seen:
            problems.append(f"{name} {key}: judged twice")
            continue
        seen.add(key)
        if key not in current:
            problems.append(f"{name} {key}: map-{name}.yaml has a row for this decision, and the component no longer has it")
            continue
        part, text = current[key]
        if row.get("text_sha256") != sha(text):
            problems.append(f"{name} {key}: the text of the decision has changed since it was judged; judge it again")
            continue
        if part in types_of and list(row.get("types") or []) != types_of[part]:
            problems.append(f"{name} {key}: judged against the choices of {row.get('types')}; the part's types are now "
                            f"{types_of[part]}; judge it again")
            continue
        allowed = {i for t in types_of.get(part, []) for i, _, _ in choices.get(t, [])}
        bad = _row_problems(name, key, c, fit, known, allowed) if part in types_of else []
        problems += bad
        if not bad:
            out[part].append((key.split("/", 1)[1], text, c if fit in ("covered", "loosely") else None, fit))
    problems += [f"{name} {key}: not judged in map-{name}.yaml" for key in current if key not in seen]
    return out, problems


def pin_map(name):
    """Key a reader's map of a design by decision id and text. The reader wrote rows by packet number; each is given
    the decision id and the SHA-256 of the text the packet holds under that number. Done only while every decision of
    the packet is a decision the component has now, with the same text."""
    if name not in designs():
        print(f"PROBLEM {name} is not a design")
        return 1
    mp, pkp = V / "choices" / f"map-{name}.yaml", V / "choices" / f"packet-{name}.yaml"
    pk, rows = load(pkp), load(mp)["map"]
    in_order = [(part, did, text) for part, c in design_components(name).items() for did, text in component_decisions(c)]
    current = {f"{part}/{did}": sha(text) for part, did, text in in_order}
    # A packet written before decisions were keyed holds only numbers. Its numbers can be given ids only when its
    # decisions are, part by part and in order, the decisions the design has now, word for word.
    unkeyed = [(p["part"], d) for p in pk["parts"] for d in p["decisions"] if not d.get("decision")]
    if unkeyed:
        if [(part, squeeze(d["text"])) for part, d in ((p["part"], d) for p in pk["parts"] for d in p["decisions"])] \
                == [(part, squeeze(text)) for part, _, text in in_order]:
            ids = iter(f"{part}/{did}" for part, did, _ in in_order)
            for p in pk["parts"]:
                for d in p["decisions"]:
                    d["decision"] = next(ids)
            print(f"packet-{name}.yaml holds numbers only; its {len(in_order)} decisions are word for word those of the "
                  "design now, in the same order, so each number is given the id of the decision at its place")
        else:
            print(f"PROBLEM packet-{name}.yaml holds numbers only and its decisions are not those of the design now; the "
                  "map cannot be keyed and must be judged again")
            return 1
    by_d, problems = {}, []
    for p in pk["parts"]:
        for d in p["decisions"]:
            if not d.get("decision"):
                problems.append(f"packet-{name}.yaml {d['d']} has no decision id; write the packet again with `packets {name}`")
            elif current.get(d["decision"]) != sha(d["text"]):
                problems.append(f"packet-{name}.yaml {d['d']} ({d['decision']}) is not a decision of the design as it is now")
            by_d[d["d"]] = d | {"types": list(p.get("types") or [])}
    out = []
    for r in rows:
        if r.get("decision"):
            out.append(r)
            continue
        d = by_d.get(r.get("d"))
        if d is None:
            problems.append(f"map-{name}.yaml {r.get('d')}: no such decision in the packet")
            continue
        out.append({"decision": d.get("decision"), "text_sha256": sha(d["text"]), "types": d["types"],
                    "choice": r.get("choice"), "fit": r["fit"]})
    if problems:
        for p in problems:
            print("PROBLEM", p)
        print(f"map-{name}.yaml not changed: {len(problems)} problems")
        return 1
    dump(mp, {"engine": name, "map": out},
         f"# The match of each decision of {name} to a choice of its part's node type, judged by a reader against\n"
         f"# validation/choices/packet-{name}.yaml. Each row names the decision by the component's own decision id and\n"
         "# holds the SHA-256 of the text that was judged and the node types whose choices it was judged against\n"
         "# (tools/so_nodetypes_experiments.py pin-map), so that a row cannot come to stand for another decision when\n"
         "# decisions are added, removed or reworded, or keep a match when the part's types change.\n"
         "# A row with `judged_by` was judged again by the reader it names, after the part's types changed.\n")
    print(f"map-{name}.yaml: {len(out)} rows keyed by decision id and text")
    return 0


def coverage(totals):
    """(real decisions, plainly covered, not covered, left out) from the totals of one engine's map. Decisions the
    reader called engine-specific are left out of the denominator (validation/criteria.yaml, decision_coverage)."""
    dropped = totals.get("engine_specific", 0)
    return sum(totals.values()) - dropped, totals.get("covered", 0), totals.get("none", 0), dropped


def recurrence_marks(totals, maps):
    """The coverage of recorded decisions against the decision_coverage marks: by the choices of the full-detail draft
    the maps were judged against, and by the choices the current draft keeps of them."""
    kept = draft_choice_of()
    rows = []
    for name, engines in (("the first five engines", INDUCTION), (HELD_OUT, [HELD_OUT])):
        real, cov, none, dropped = (sum(coverage(totals[e])[i] for e in engines) for i in range(4))
        in_draft = sum(1 for e in engines for c, fit in maps[e].values() if fit == "covered" and kept.get(c))
        note = f"{dropped} decisions the reader called engine-specific are left out of the denominator"
        rows.append(judged(f"{name}: decisions plainly a choice of the full-detail draft", "decision_coverage.covered_min", cov, real, note))
        rows.append(judged(f"{name}: decisions no choice of the full-detail draft names", "decision_coverage.not_covered_max", none, real))
        rows.append(judged(f"{name}: decisions plainly a choice the current draft keeps", "decision_coverage.covered_min", in_draft, real,
                           "computed from the same maps; no reader judged the decisions against the current draft"))
    return rows


def shared_counts(rows):
    """How many choices count as shared under each of three rules, from the rows of recurrence.yaml."""
    return {"covered_2": sum(1 for r in rows if len(r["engines"]) >= 2),
            "covered_3": sum(1 for r in rows if len(r["engines"]) >= 3),
            "covered_or_loosely_2": sum(1 for r in rows if len(r["engines"]) + len(r["loosely_only"]) >= 2),
            "exactly_2": sum(1 for r in rows if len(r["engines"]) == 2)}


def recurrence_data():
    """(totals per engine, maps, problems) from the stored maps, as `recurrence` reads them."""
    maps, problems = read_maps()
    totals = {e: dict(collections.Counter(fit for _, fit in got.values())) for e, got in maps.items()}
    return totals, maps, problems


def recurrence():
    choices, assign = frozen_choices(), assignments()
    maps, problems = read_maps()
    missing = [e for e in ENGINES if e not in maps]
    if missing:
        print("no map yet for:", ", ".join(missing))
    seen = collections.defaultdict(lambda: {"covered": set(), "loosely": set()})
    totals = {}
    for e, got in maps.items():
        totals[e] = dict(collections.Counter(fit for _, fit in got.values()))
        for c, fit in got.values():
            if c:
                seen[c][fit].add(e)
    has_type = {e: {t for ts in assign[e].values() for t in ts} for e in ENGINES}
    rows = []
    for t, cs in choices.items():
        for cid, kind, what in cs:
            cov = seen[cid]["covered"]
            rows.append({"id": cid, "kind": kind, "what": what,
                         "engines": sorted(cov, key=ENGINES.index),
                         "loosely_only": sorted(seen[cid]["loosely"] - cov, key=ENGINES.index),
                         "induction": len(cov & set(INDUCTION)), "held_out": HELD_OUT in cov,
                         "type_in_held_out": t in has_type[HELD_OUT]})
    out = {"engines_mapped": [e for e in ENGINES if e in maps], "decisions": totals, "choices": rows}
    if problems:
        for p in problems:
            print("PROBLEM", p)
        print(f"RESULT: FAIL. validation/choices/recurrence.yaml not written: {len(problems)} problems")
        return 1
    dump(V / "choices" / "recurrence.yaml", out,
         "# Written by tools/so_nodetypes_experiments.py recurrence from validation/choices/map-*.yaml.\n"
         "# engines: the engines with a decision that plainly is this choice. induction: how many of the five the\n"
         "# types were drawn from. held_out: whether llama.cpp has one.\n")
    if missing:
        print(f"RESULT: FAIL. {len(missing)} engines have no map; nothing is scored")
        return 1

    print("\nDecisions, by engine")
    print("| engine | decisions | plainly a choice | loosely | no choice | engine-specific |")
    print("|---|---|---|---|---|---|")
    for e in ENGINES:
        t = totals[e]
        n = sum(t.values())
        print(f"| {e} | {n} | {t.get('covered', 0)} ({pct(t.get('covered', 0), n)}) | {t.get('loosely', 0)} | "
              f"{t.get('none', 0)} | {t.get('engine_specific', 0)} |")

    print("\nChoices of the frozen draft, by the number of induction engines that decide them")
    print("| seen in k of the 5 | choices | of those, in a type llama.cpp has | also decided in llama.cpp |")
    print("|---|---|---|---|")
    for k in range(len(INDUCTION) + 1):
        grp = [r for r in rows if r["induction"] == k]
        inh = [r for r in grp if r["type_in_held_out"]]
        hit = [r for r in inh if r["held_out"]]
        print(f"| {k} | {len(grp)} | {len(inh)} | {len(hit)}" + (f" ({pct(len(hit), len(inh))})" if inh else "") + " |")
    for lo, name in ((2, "2 or more"), (3, "3 or more")):
        grp = [r for r in rows if r["induction"] >= lo and r["type_in_held_out"]]
        rest = [r for r in rows if r["induction"] < lo and r["type_in_held_out"]]
        a, b = sum(r["held_out"] for r in grp), sum(r["held_out"] for r in rest)
        print(f"\nSeen in {name} of the 5: {a} of {len(grp)} also decided in llama.cpp ({pct(a, len(grp))}); "
              f"the rest: {b} of {len(rest)} ({pct(b, len(rest))}).")
    lm = maps[HELD_OUT]
    n = len(lm)
    by = {r["id"]: r for r in rows}
    for lo in (1, 2, 3):
        kept = sum(1 for c, fit in lm.values() if fit == "covered" and by[c]["induction"] >= lo)
        print(f"llama.cpp decisions that plainly are a choice seen in {lo}+ of the 5: {kept} of {n} ({pct(kept, n)})")
    counts = shared_counts(rows)
    print(f"\nChoices counted as shared, by the rule: plainly decided in 2+ engines {counts['covered_2']}; plainly decided in "
          f"3+ engines {counts['covered_3']}; plainly or loosely decided in 2+ engines {counts['covered_or_loosely_2']}. "
          f"Of the {counts['covered_2']}, {counts['exactly_2']} rest on exactly two engines.")
    marks = recurrence_marks(totals, maps)
    marks.append(unmarked("choices plainly decided in two or more of the six engines", str(counts["covered_2"])))
    return print_marks(marks)


# ---------------------------------------------------------------- classification

def anon(keyfile, rnd="round8"):
    """All parts of the six engines in one shuffled list, with the fields the earlier rounds showed and no names.

    Each round has its own order and its own item ids, so that nothing carries over from one round to the next.
    The list of a round that has readers' answers is a record and is not written again."""
    seed, prefix = {"round8": (20261117, "Q")}.get(rnd, (sum(map(ord, rnd)) + 20261117, rnd[0].upper() + rnd[-1]))
    if any((V / rnd).glob("rater-*.yaml")):
        print(f"PROBLEM validation/{rnd} holds readers' answers; its parts list is a record and is not written again")
        return 1
    items = []
    for e in ENGINES:
        for p in inventory(e)[0]:
            items.append((e, p))
    random.Random(seed).shuffle(items)
    out, key = [], {}
    for i, (e, p) in enumerate(items, 1):
        item = {"item": f"{prefix}{i:03d}", "does": p["does"], "runs": p.get("runs") or [], "owns_state": p.get("owns_state") or []}
        out.append(item)
        key[item["item"]] = [e, p["id"]]
    dump(V / rnd / "parts.anon.yaml", out)
    dump(keyfile, key)
    print(f"{len(out)} parts written to validation/{rnd}/parts.anon.yaml; key in {keyfile}")
    return 0


def score_classification(keyfile, rnd="round8"):
    """Score the readers of one classification run against the key. Returns None when the run has no reader files.

    A part counts for a reader only when the reader answered it; a part some reader did not answer is agreed by
    nobody and is left out of the reader-to-reader count, which says how many parts it covers."""
    key, assign = load(keyfile), assignments()
    known = {t["id"] for t in load(DRAFT)["types"]} | {"none"}
    raters, problems = {}, []
    for p in sorted((V / rnd).glob("rater-*.yaml")):
        raters[p.stem] = {}
        for a in load(p)["assignments"]:
            if a["item"] not in key:
                problems.append(f"{p.stem}: answers {a['item']}, which is not an item of this round")
            elif a["item"] in raters[p.stem]:
                problems.append(f"{p.stem}: answers {a['item']} twice")
            else:
                raters[p.stem][a["item"]] = a
                if (a.get("node_type") or "none") not in known:
                    problems.append(f"{p.stem} {a['item']}: '{a['node_type']}' is not a node type of the draft")
    if not raters:
        return None
    group = lambda: {"parts": 0, "agree": 0, "agree_main": 0, "none_ref": 0, "further_types": 0,
                     "per": {r: 0 for r in raters}, "per_main": {r: 0 for r in raters},
                     "answered": {r: 0 for r in raters}, "all_answered": 0, "same_type": 0,
                     "fits": {r: collections.Counter() for r in raters}}
    res = {g: group() for g in ("induction", "held_out")}
    disagreements = []
    for item, (e, part) in sorted(key.items()):
        x = res["held_out" if e == HELD_OUT else "induction"]
        accepted = set(assign[e][part]) or {"none"}
        main = assign[e][part][0] if assign[e][part] else "none"
        x["parts"] += 1
        x["none_ref"] += accepted == {"none"}
        x["further_types"] += len(accepted) > 1
        given = {r: (a[item].get("node_type") or "none") for r, a in raters.items() if item in a}
        for r in given:
            x["answered"][r] += 1
            x["per"][r] += given[r] in accepted
            x["per_main"][r] += given[r] == main
            x["fits"][r][str(raters[r][item].get("fit"))] += 1
        everyone = len(given) == len(raters)
        x["all_answered"] += everyone
        x["same_type"] += everyone and len(set(given.values())) == 1
        x["agree_main"] += everyone and all(v == main for v in given.values())
        if everyone and all(v in accepted for v in given.values()):
            x["agree"] += 1
        else:
            disagreements.append({"engine": e, "part": part, "accepted": sorted(accepted), "given": given,
                                  "notes": {r: raters[r][item].get("note") for r in given if raters[r][item].get("note")}})
    total = sum(x["parts"] for x in res.values())
    for r, a in raters.items():
        if len(a) < total:
            problems.append(f"{r}: no answer for {total - len(a)} of {total} parts; a part without an answer is agreed by nobody")
    marks = []
    names = {"induction": "the first five engines", "held_out": "llama.cpp"}
    for g, name in names.items():
        x = res[g]
        marks.append(judged(f"{name}: every reader gives a type the key accepts", "agreement.same_type_min", x["agree"], x["parts"]))
        marks.append(judged(f"{name}: every reader gives the main type of the key", "agreement.same_type_min", x["agree_main"], x["parts"],
                            f"{x['further_types']} parts have further accepted types", scoring=False))
        marks.append(unmarked(f"{name}: the readers give each other the same type",
                              f"{x['same_type']} of the {x['all_answered']} parts every reader answered"))
    for r in raters:
        f, n = res["held_out"]["fits"][r], res["held_out"]["parts"]
        note = (f"the reader's own fit marks; no part is dropped; {n - res['held_out']['answered'][r]} parts without an answer "
                "count as not plainly one type")
        marks.append(judged(f"llama.cpp, {r}: parts the reader calls plainly an instance of one type", "generalisation.clean_fit_min", f["clean"], n, note))
        marks.append(judged(f"llama.cpp, {r}: parts the reader gives no type", "generalisation.no_type_max", f["none"], n))
    out = {g: {k: ({r: dict(c) for r, c in v.items()} if k == "fits" else v) for k, v in x.items()} for g, x in res.items()}
    same, answered = sum(x["same_type"] for x in res.values()), sum(x["all_answered"] for x in res.values())
    out |= {"raters": list(raters), "raters_same_type": same, "parts_every_rater_answered": answered,
            "generalisation_applies_to": criteria()["generalisation"].get("applies_to"),
            "marks": marks, "problems": problems, "disagreements": disagreements}
    return out


def classify(keyfile, rnd="round8"):
    c = score_classification(keyfile, rnd)
    if c is None:
        print(f"no rater files in validation/{rnd}")
        return 1
    raters = c["raters"]
    print("| parts | every reader gives a type the key accepts | "
          + " | ".join(f"{r} matches the key" for r in raters) + " | every reader gives the main type | the readers give each other the same type |")
    print("|---|---|" + "---|" * len(raters) + "---|---|")
    for g, name in (("induction", "first five engines"), ("held_out", "llama.cpp")):
        x = c[g]
        print(f"| {name}: {x['parts']} | {x['agree']} ({pct(x['agree'], x['parts'])}) | "
              + " | ".join(f"{x['per'][r]} ({pct(x['per'][r], x['parts'])})" for r in raters)
              + f" | {x['agree_main']} ({pct(x['agree_main'], x['parts'])}) | {x['same_type']} of {x['all_answered']} answered by all |")
    for g in ("induction", "held_out"):
        for r in raters:
            print(f"  {g} {r}: answered {c[g]['answered'][r]} of {c[g]['parts']}; own judgement of fit: {c[g]['fits'][r]}")
    total = c["induction"]["parts"] + c["held_out"]["parts"]
    print(f"  the raters give each other the same type for {c['raters_same_type']} of the {c['parts_every_rater_answered']} parts "
          f"every rater answered ({total} parts in all)")
    print(f"  instructions given to the readers: {', '.join(shown(p) for p in instructions_stored(rnd)) or 'not stored'}")
    if c["generalisation_applies_to"] == "every_fold":
        print("  the generalisation marks ask for every engine to be held out in turn; only llama.cpp was")
    dump(V / rnd / "classification.yaml", {k: v for k, v in c.items() if k != "raters"},
         "# Written by tools/so_nodetypes_experiments.py classify.\n")
    return print_marks(c["marks"], c["problems"])


# ---------------------------------------------------------------- selection

SPECS = {"qwen-on-pc": "qwen-flash-on-pc.resolved.yaml", "qwen-on-spark": "qwen-flash-on-dgx-spark.resolved.yaml"}


def strata_truth():
    """The node types Strata runs on each of its two machines, from its resolved specs."""
    assign = assignments()["strata"]
    out = {}
    for name, spec in SPECS.items():
        comps = load(ROOT / "examples" / "specs" / spec)["composition"]["components"]
        active, off = set(), {}
        for c in comps:
            part = c["component_ref"].split("/")[-1]
            if part not in assign:
                continue                                  # a subsystem, not a leaf part
            if c.get("active") is False:
                off[part] = c.get("inactive_reason", "")
            else:
                active.add(part)
        out[name] = {"runs": sorted({t for p in active for t in assign[p]}),
                     "main": sorted({assign[p][0] for p in active}),
                     "off_parts": {p: {"types": assign[p], "reason": r} for p, r in off.items()}}
    return out


TARGETS = {
    "qwen-on-pc": ("model-qwen3.8-flash-125b-a6b.yaml", "hw-pc-12g-64g.yaml", "qwen-flash-on-pc.target.yaml"),
    "qwen-on-spark": ("model-qwen3.8-flash-125b-a6b.yaml", "hw-dgx-spark.yaml", "qwen-flash-on-dgx-spark.resolved.yaml"),
    "muse-on-spark": ("model-muse-spark-open.yaml", "hw-dgx-spark.yaml", "muse-spark-open-on-dgx-spark.target.yaml"),
}
DESIGN_SECTIONS = ("execution", "state", "composition", "policy", "binding", "mechanisms", "target_spec")
# Words by which a `note` speaks of how an engine is built. Such a note is a remark about an engine's design, not a
# fact about the model or the machine, and is left out of what a reader is given.
DESIGN_WORDS = r"(?i)\b(engine|engines|engine's|pack|packs)\b"
# What an earlier replacement of a name left behind, and other wordings that say an engine for the case exists.
TRACES = ("existing engine", "an existing", "engine-like", "engine-reported", "reference engine")
NEUTRAL = "item"


def hidden_names():
    """Every name that must not reach a selection reader: the engines examined and the designs, as they are written."""
    return sorted({n.lower() for n in [*ENGINES, *designs(), "llama.cpp", "llamacpp", "dwarfstar"]})


def scrub(x, names=None, renamed=None):
    """Remove what would tell a reader which existing engine a description was taken from, or that one exists.

    A string made of one word (an id or a reference) that holds a hidden name is replaced whole by a neutral token,
    the same token for the same string, so that no part of the old string remains. A longer text loses every
    sentence that holds a hidden name. `source` and `title` are dropped, and so is a `note` that speaks of an engine."""
    names = hidden_names() if names is None else names
    renamed = {} if renamed is None else renamed
    has = lambda s: any(n in s.lower() for n in names)
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if k in ("source", "title"):
                continue
            if k == "note" and isinstance(v, str) and (has(v) or re.search(DESIGN_WORDS, v)):
                continue
            out[k] = scrub(v, names, renamed)
        return out
    if isinstance(x, list):
        return [scrub(v, names, renamed) for v in x]
    if isinstance(x, str) and has(x):
        if not re.search(r"\s", x):
            return renamed.setdefault(x, f"{NEUTRAL}-{len(renamed) + 1}")
        return " ".join(s for s in re.split(r"(?<=[.!?。；;])\s+", x) if not has(s))
    return x


def leftovers(text, names=None):
    """What a text given to a reader still tells about an existing engine: a hidden name, a trace of a name that
    was replaced, or a field that lists engines."""
    names = hidden_names() if names is None else names
    low = text.lower()
    found = [n for n in names if n in low]
    found += [t for t in TRACES if t in low]
    found += [f"`{k}`" for k in ("seen_in", "engines_examined") if re.search(rf"(?m)^\s*-?\s*{k}:", text)]
    return found


def types_for_selection():
    """The draft as a selection reader is given it: without the engines each type was seen in, the list of engines
    examined, the number of engines behind each choice, and the gaps found in the held-out engine."""
    d = load(DRAFT)
    out = {k: v for k, v in d.items() if k not in ("engines_examined", "open_gaps", "choices_kept_when", "derived_from")}
    out["types"] = []
    for t in d["types"]:
        n = {k: v for k, v in t.items() if k != "seen_in"}
        if "choices" in n:
            n["choices"] = [{"what": c["what"]} for c in n["choices"]]
        out["types"].append(n)
    return out


def selection_inputs(where):
    """Write what the readers of a new selection run are given: the node types, and a model, a machine and a target
    for each case, with no trace of any engine's design. The files of a run are the record of what its readers saw:
    a directory that already holds inputs or answers is not written to. Exits with 1 when a trace is left."""
    dst = pathlib.Path(where)
    dst = dst if dst.is_absolute() else V / where
    if (dst / "inputs").exists() or any(dst.glob("reader-*.yaml")):
        print(f"PROBLEM {shown(dst)} already holds the inputs or the answers of a run; they are a record and are not written again")
        return 1
    names, left = hidden_names(), {}
    files = {dst / "node-types.for-readers.yaml": types_for_selection()}
    for name, (model, hw, spec) in TARGETS.items():
        renamed = {}
        files[dst / "inputs" / name / "model.yaml"] = scrub(load(ROOT / "examples" / "given" / model), names, renamed)
        files[dst / "inputs" / name / "machine.yaml"] = scrub(load(ROOT / "examples" / "given" / hw), names, renamed)
        target = {k: v for k, v in load(ROOT / "examples" / "specs" / spec).items() if k not in DESIGN_SECTIONS}
        target["spec_level"] = "target"
        files[dst / "inputs" / name / "target.yaml"] = scrub(target, names, renamed)
    for path, data in files.items():
        dump(path, data)
        found = leftovers(path.read_text(encoding="utf-8"), names)
        if found:
            left[shown(path)] = found
        print(shown(path), "written" + (f"; STILL TELLS OF AN ENGINE: {found}" if found else ""))
    print(f"store what the readers are told with `so_nodetypes_experiments.py instructions {where} FILE` before they run")
    return 1 if left else 0


def given_to(run):
    """(types file, inputs directory, whether each is the run's own) for the readers of a run: the run's own files
    when it holds them, otherwise the stored files nearest to what they were given. Either may be None."""
    d, rec = V / run, GIVEN.get(run, {})
    types = d / "node-types.for-readers.yaml"
    if not types.exists():
        types = V / rec["types"] if rec.get("types") and (V / rec["types"]).exists() else None
    inputs = d / "inputs"
    if not inputs.is_dir():
        inputs = V / rec["inputs"] if rec.get("inputs") and (V / rec["inputs"]).is_dir() else None
    own = lambda p: p is not None and d in p.parents
    return types, inputs, own(types), own(inputs)


def what_readers_were_given(run):
    """What the stored files of a selection run tell a reader about existing engines, read from the files."""
    types, inputs, own_types, own_inputs = given_to(run)
    names = hidden_names()
    out = {"types_file": shown(types) if types else None, "types_file_is_the_runs_own": own_types,
           "inputs": shown(inputs) if inputs else None, "inputs_are_the_runs_own": own_inputs,
           "traces": [], "engine_notes": [], "seen_in_types": 0, "seen_in_names": [], "types": 0,
           "engines_examined": [], "open_gaps": 0}
    if inputs:
        for f in sorted(inputs.rglob("*.yaml")):
            lines = f.read_text(encoding="utf-8").splitlines()
            for i, ln in enumerate(lines):
                low = ln.lower()
                if any(t in low for t in [*TRACES, *names]):
                    out["traces"].append({"file": f.relative_to(inputs).as_posix(), "line": ln.strip()})
                elif re.match(r"\s*note:", ln) and f.stem != "target":
                    # a target speaks of the engine to be built; a model or a machine should not speak of any engine
                    j, block = i + 1, ln                     # a note runs on over the indented lines that follow it
                    while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > len(ln) - len(ln.lstrip()):
                        block += " " + lines[j].strip()
                        j += 1
                    if re.search(r"(?i)\bthe engine\b|\bengine's\b", block):
                        out["engine_notes"].append({"file": f.relative_to(inputs).as_posix(),
                                                    "line": squeeze(block.split("note:", 1)[1]).strip(" '\"")})
    if types:
        d = load(types)
        out["types"] = len(d["types"])
        out["seen_in_types"] = sum(1 for t in d["types"] if "seen_in" in t)
        out["seen_in_names"] = sorted({e for t in d["types"] for e in t.get("seen_in", [])},
                                      key=lambda e: ENGINES.index(e) if e in ENGINES else len(ENGINES))
        out["engines_examined"] = list(d.get("engines_examined") or [])
        out["open_gaps"] = len(d.get("open_gaps") or [])
    return out


def conditions(types_file):
    """type -> the condition under which an engine needs it, in a types file; None when the type has none."""
    return {t["id"]: t.get("needed_when") or t.get("applies_when") for t in load(types_file)["types"]}


NORM = {True: "yes", False: "no", "needed": "yes", "not_needed": "no", "yes": "yes", "no": "no", "open": "open"}


def selection_answers(where):
    """(node types, target -> reader -> node type -> answer, problems). An answer has `needed` (yes, no or open),
    `because` and `asks`. A type a reader did not answer has no entry."""
    types = [t["id"] for t in load(FROZEN)["types"]]
    ans, problems = collections.defaultdict(dict), []
    for p in sorted((V / where).glob("reader-*.yaml")):
        d = load(p)
        for tg in TARGETS:
            got = {}
            for a in (d.get("targets") or {}).get(tg) or []:
                if a.get("node_type") not in types:
                    problems.append(f"{p.stem} {tg}: '{a.get('node_type')}' is not a node type")
                elif not isinstance(a.get("needed"), (str, bool)) or a.get("needed") not in NORM:
                    problems.append(f"{p.stem} {tg} {a['node_type']}: answer {a.get('needed')!r} is not needed, not_needed or open")
                elif a["node_type"] in got:
                    problems.append(f"{p.stem} {tg} {a['node_type']}: answered twice")
                else:
                    got[a["node_type"]] = a | {"needed": NORM[a["needed"]]}
            miss = [t for t in types if t not in got]
            if miss:
                problems.append(f"{p.stem} {tg}: no answer for {len(miss)} of {len(types)} types "
                                f"({', '.join(miss[:6])}{', ...' if len(miss) > 6 else ''})")
            ans[tg][p.stem] = got
    return types, dict(ans), problems


def against_truth(answers, types, present):
    """One reader's answers on one case against the set of types the known engine has: the matches, and the strict
    agreement in which an open or missing answer agrees with nothing."""
    yes = {t for t, a in answers.items() if a["needed"] == "yes"}
    no = {t for t, a in answers.items() if a["needed"] == "no"}
    opn = {t for t, a in answers.items() if a["needed"] == "open"}
    return {"needed_and_present": len(yes & present), "not_needed_and_absent": len(no - present),
            "agree": len(yes & present) + len(no - present), "of": len(types),
            "answered_needed_or_not": len(yes | no), "open": len(opn), "no_answer": len(types) - len(answers),
            "needed_but_absent": sorted(yes - present), "not_needed_but_present": sorted(no & present),
            "open_and_present": sorted(opn & present), "open_and_absent": sorted(opn - present)}


def names_types(text, types, own=None):
    """The node types a reader's reason names, by id with or without its hyphens, other than `own`."""
    found = []
    for t in types:
        if t != own and re.search(r"(?i)(?<![\w-])" + r"[- ]".join(map(re.escape, t.split("-"))) + r"(?![\w-])", text or ""):
            found.append(t)
    return found


def reasons_against_truth(where, case, which):
    """For each reader and each type in `which` the reader called not needed in `case`: the other types the stated
    reason names, and of those, the ones the reader also called not needed while the known engine has them. A reason
    that rests on such a type agrees with the truth file in its answer and not in its ground."""
    types, ans, _ = selection_answers(where)
    present = set(strata_truth()[case]["runs"])
    out = []
    for r, got in ans.get(case, {}).items():
        for t in which:
            a = got.get(t)
            if not a or a["needed"] != "no":
                continue
            named = names_types(a.get("because"), types, own=t)
            wrong = [u for u in named if got.get(u, {}).get("needed") == "no" and u in present]
            out.append({"reader": r, "type": t, "because": a.get("because"), "names": named, "rests_on_absent_but_present": wrong})
    return out


def score_selection(where="selection"):
    """Score the readers of one selection run. Returns None when the run has no reader files."""
    if not any((V / where).glob("reader-*.yaml")):
        return None
    types, ans, problems = selection_answers(where)
    truth_ = strata_truth()
    types_file = given_to(where)[0]
    cond = conditions(types_file) if types_file else {}
    report, marks = {}, []
    for tg in TARGETS:
        rs = list(ans[tg])
        got = lambda r, t: ans[tg][r].get(t, {}).get("needed")
        everyone = [t for t in types if all(got(r, t) for r in rs)]
        same = [t for t in everyone if len({got(r, t) for r in rs}) == 1]
        split = {t: {r: got(r, t) for r in rs} for t in types if t not in same}
        rep = {"types": len(types), "types_every_reader_answered": len(everyone), "readers_agree": len(same), "readers_differ": split,
               "counts": {r: dict(collections.Counter(a["needed"] for a in ans[tg][r].values())) for r in rs}}
        marks.append(judged(f"{tg}: the readers give each other the same answer (another reading of the mark: "
                            "agreement between readers, not with a known answer)", "sufficiency.selection_agrees_min",
                            len(same), len(types), f"{len(types) - len(everyone)} types not answered by every reader count as not agreed",
                            scoring=False))
        if tg in truth_:
            runs, main = set(truth_[tg]["runs"]), set(truth_[tg]["main"])
            for r in rs:
                x = against_truth(ans[tg][r], types, runs)
                m = against_truth(ans[tg][r], types, main)
                rep[f"{r}_against_strata"] = {
                    "said_needed_and_strata_runs_it": x["needed_and_present"], "said_needed_but_strata_does_not_run_it": x["needed_but_absent"],
                    "said_not_needed_and_strata_does_not_run_it": x["not_needed_and_absent"], "said_not_needed_but_strata_runs_it": x["not_needed_but_present"],
                    "left_open_and_strata_runs_it": x["open_and_present"], "left_open_and_strata_does_not": x["open_and_absent"],
                    "answer_is_strata": x["agree"], "answer_is_strata_main_types_only": m["agree"],
                    "answered_needed_or_not_needed": x["answered_needed_or_not"], "open": x["open"], "no_answer": x["no_answer"]}
                marks.append(judged(f"{tg}, {r}: the answer is what Strata has (an open or missing answer agrees with nothing)",
                                    "sufficiency.selection_agrees_min", x["agree"], x["of"],
                                    f"{x['open']} open, {x['no_answer']} without an answer; among the {x['answered_needed_or_not']} answered needed or "
                                    f"not needed: {pct(x['agree'], x['answered_needed_or_not'])}"))
                marks.append(judged(f"{tg}, {r}: the same, counting only the main type of each part of Strata",
                                    "sufficiency.selection_agrees_min", m["agree"], m["of"], scoring=False))
        else:
            marks.append(unmarked(f"{tg}: agreement with a known answer", "no engine exists for this case"))
        report[tg] = rep
    unconditional = sorted(t for t in types if not cond.get(t)) if cond else None
    return {"report": report, "marks": marks, "problems": problems, "answers": ans, "types": types,
            "types_file": shown(types_file) if types_file else None, "conditions": cond, "unconditional": unconditional}


def selection(where="selection"):
    s = score_selection(where)
    if s is None:
        print(f"no reader files in validation/{where}")
        return 1
    truth_, report = strata_truth(), s["report"]
    for tg, rep in report.items():
        print(f"\n{tg}: readers give the same answer for {rep['readers_agree']} of the {rep['types_every_reader_answered']} types "
              f"every reader answered ({rep['types']} types)")
        for r in rep["counts"]:
            print(f"  {r}: {rep['counts'][r]}")
            if tg in truth_:
                x = rep[f"{r}_against_strata"]
                print(f"    needed and Strata runs it: {x['said_needed_and_strata_runs_it']}; needed but Strata does not: "
                      f"{x['said_needed_but_strata_does_not_run_it']}; not needed but Strata runs it: "
                      f"{x['said_not_needed_but_strata_runs_it']}; open and Strata runs it: {x['left_open_and_strata_runs_it']}")
        if rep["readers_differ"]:
            print("  differ on:", ", ".join(f"{t} ({'/'.join(str(v) for v in sp.values())})" for t, sp in rep["readers_differ"].items()))
    if {"qwen-on-pc", "qwen-on-spark"} <= set(truth_):
        dropped = sorted(set(truth_["qwen-on-pc"]["runs"]) - set(truth_["qwen-on-spark"]["runs"]))
        rs = reasons_against_truth(where, "qwen-on-spark", dropped)
        print(f"\nTypes Strata stops running on qwen-on-spark: {', '.join(dropped) or 'none'}. Answers `not needed` for them: "
              f"{len(rs)}; of these, the reason rests on another type the reader called not needed and Strata runs: "
              f"{sum(1 for x in rs if x['rests_on_absent_but_present'])}")
        for x in rs:
            if x["rests_on_absent_but_present"]:
                print(f"  {x['reader']} {x['type']}: \"{x['because']}\" names {', '.join(x['rests_on_absent_but_present'])}")
    if s["unconditional"] is not None:
        print(f"\n{len(s['unconditional'])} of {len(s['types'])} types have no condition in {s['types_file']}: every engine has them "
              "by definition, so `needed` for them does not depend on the case")
    print("`open` agrees with nothing here: it cannot be scored wrong, and it is not counted as right")
    print(f"instructions given to the readers: {', '.join(shown(p) for p in instructions_stored(where)) or 'not stored'}")
    c = criteria().get("sufficiency") or {}
    print("the mark `sufficiency.selection_agrees_min` does not say what the selection must agree with; it is read here as "
          "the types Strata has an active part for. That reading was fixed on 2026-11-18, after the results.")
    if "choices_without_guidance_max" in c:
        print("the mark `sufficiency.choices_without_guidance_max` is not tested: no reader was asked to settle choices")
    dump(V / where / "selection.yaml", report | {"marks": s["marks"], "problems": s["problems"]},
         "# Written by tools/so_nodetypes_experiments.py selection.\n")
    return print_marks(s["marks"], s["problems"])


def truth():
    t = strata_truth()
    dump(V / "selection" / "strata-truth.yaml", t,
         "# Written by tools/so_nodetypes_experiments.py truth. The node types Strata's working parts are instances of,\n"
         "# on each machine, from examples/specs/*.resolved.yaml and validation/reference-assignment.yaml.\n"
         "# `main` counts only the first type of a part that does two jobs.\n")
    for k, v in t.items():
        print(k, len(v["runs"]), "types;", "parts not working:", ", ".join(v["off_parts"]))
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "packets":
        return packets(*sys.argv[2:3])
    if cmd == "pin-map" and len(sys.argv) > 2:
        return pin_map(sys.argv[2])
    if cmd == "recurrence":
        return recurrence()
    if cmd == "anon" and len(sys.argv) > 2:
        return anon(*sys.argv[2:4])
    if cmd == "classify" and len(sys.argv) > 2:
        return classify(*sys.argv[2:4])
    if cmd == "truth":
        return truth()
    if cmd == "selection-inputs" and len(sys.argv) > 2:
        return selection_inputs(sys.argv[2])
    if cmd == "selection":
        return selection(*sys.argv[2:3])
    if cmd == "instructions" and len(sys.argv) > 3:
        return store_instructions(*sys.argv[2:5])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
