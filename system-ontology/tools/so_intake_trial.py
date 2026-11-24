#!/usr/bin/env python3
"""Trial: the System Ontology as part of a query that enters the factory through the Intention Compiler.

    python tools/so_intake_trial.py assemble           # write the queries of both variants
    python tools/so_intake_trial.py resolve A          # quotes of a reader's draft -> spans; validate against the schema
    python tools/so_intake_trial.py score              # what of the ontology each Intent IR takes up
    python tools/so_intake_trial.py brief A            # validate a reader's Research Brief against the schema

The method and what is reported are stated in validation/criteria.yaml (`intake_trial_2026_11_17`). The readers who
play the Intent CC and the Requirements CC work in folders of their own; their files are copied into
validation/intake/<variant>/ before `resolve`.

A query is a request (`request.txt`) and context sources, each a file of the ontology copied byte for byte.
`sources.json` gives every source its id and SHA-256, which is what the factory's `Ref` holds. Where the Intent IR
schema asks for `source_spans`, a reader writes `quotes: [{"source": "<id>", "text": "<exact text>"}]`; `resolve`
finds each quote in its source and writes the offsets, counted in Unicode code points with the end excluded.
"""
import hashlib
import json
import pathlib
import re
import sys

import jsonschema
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = ROOT.parent
OUT = ROOT / "validation" / "intake"
SCHEMAS = REPO / "docs" / "architecture" / "design-package" / "reference" / "schemas"
REQUEST = ("Build a custom inference engine for Meta Muse Spark Open that runs on NVIDIA DGX Spark. "
           "The attached System Ontology files describe the model, the machine and the target the engine is judged on. "
           "Take them as the statement of what is wanted.\n")
VARIANTS = {
    "A": {"target": "examples/specs/muse-spark-open-on-dgx-spark.target.yaml",
          "model": "examples/given/model-muse-spark-open.yaml",
          "machine": "examples/given/hw-dgx-spark.yaml"},
}
VARIANTS["B"] = VARIANTS["A"] | {"node-types": "ontology/node-types.draft.yaml"}
# Second run (2026-11-18): the engine's own description at two levels, without the generic node types.
VARIANTS["C"] = VARIANTS["A"] | {"system": "examples/systems/muse/system.yaml", "nodes": "examples/systems/muse/nodes.yaml"}
REQUESTS = {
    "C": ("Build a custom inference engine for Meta Muse Spark Open that runs on NVIDIA DGX Spark. "
          "The attached System Ontology files describe the model, the machine, the target the engine is judged on, "
          "and the engine itself at two levels: the system as a whole and its nodes. "
          "Take them as the statement of what is wanted.\n"),
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sources(variant):
    """The files of a query as they were run. Quotes are recorded as character positions in these files, so the bytes
    must be the ones the reader saw: each is checked against the checksum recorded when the query was assembled."""
    d = OUT / variant / "query"
    out = {}
    for s in json.loads((d / "sources.json").read_text(encoding="utf-8")):
        b = (d / s["file"]).read_bytes()
        if sha(b) != s["sha256"]:
            raise SystemExit(f"validation/intake/{variant}/query/{s['file']} is not the file that was run: its checksum is "
                             f"{sha(b)[:12]}, the recorded one {s['sha256'][:12]} ({len(b)} bytes against {s['bytes']}). "
                             f"Line endings were probably converted on checkout; the file must be stored unconverted "
                             f"(see .gitattributes).")
        out[s["id"]] = s | {"text": b.decode("utf-8")}
    return out


def need_schemas():
    if not SCHEMAS.is_dir():
        raise SystemExit(f"this command validates against the factory's schemas, which are in the repository at "
                         f"docs/architecture/design-package/reference/schemas and were not found at {SCHEMAS}. "
                         f"`score` does not need them.")


def assemble(only=None):
    for v, files in VARIANTS.items():
        d = OUT / v / "query"
        if only and v != only:
            continue
        if (d / "sources.json").exists():       # a query that was run is a record; it is never written again
            print(f"variant {v}: query kept as it was run")
            continue
        d.mkdir(parents=True, exist_ok=True)
        request = REQUESTS.get(v, REQUEST)
        (d / "request.txt").write_bytes(request.encode("utf-8"))
        listing = [{"id": "request", "file": "request.txt", "sha256": sha(request.encode("utf-8")), "bytes": len(request.encode("utf-8"))}]
        for sid, rel in files.items():
            b = (ROOT / rel).read_bytes()
            name = f"{sid}{pathlib.Path(rel).suffix}"
            (d / name).write_bytes(b)
            listing.append({"id": sid, "file": name, "from": rel, "sha256": sha(b), "bytes": len(b)})
        (d / "sources.json").write_text(json.dumps(listing, indent=2), encoding="utf-8")
        total = sum(s["bytes"] for s in listing)
        print(f"variant {v}: {len(listing)} sources, {total:,} bytes ({total / 1024:.0f} KB): "
              + ", ".join(f"{s['id']} {s['bytes']:,}" for s in listing))


def validator(name):
    common = json.loads((SCHEMAS / "common.schema.json").read_text(encoding="utf-8"))
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    from referencing import Registry, Resource
    reg = Registry().with_resources([(common["$id"], Resource.from_contents(common)), (schema["$id"], Resource.from_contents(schema))])
    return jsonschema.Draft202012Validator(schema, registry=reg)


def resolve(variant):
    need_schemas()
    src = sources(variant)
    draft = json.loads((OUT / variant / "intent_ir.draft.json").read_text(encoding="utf-8"))
    ref = lambda sid: {"id": sid, "sha256": src[sid]["sha256"]}
    stats = {"quotes": 0, "not_found": []}

    def spans(quotes, where):
        out = []
        for q in quotes or []:
            stats["quotes"] += 1
            text = src.get(q.get("source"), {}).get("text")
            at = -1 if text is None else text.find(q["text"])
            if at < 0 and text is not None:                       # tolerate differences in white space only
                m = re.search(r"\s+".join(re.escape(w) for w in q["text"].split()), text)
                at, q = (m.start(), q | {"text": m.group(0)}) if m else (-1, q)
            if at < 0:
                stats["not_found"].append({"in": where, "source": q.get("source"), "text": q["text"][:120]})
                continue
            out.append({"source_ref": ref(q["source"]), "start": at, "end": at + len(q["text"])})
        return out

    def convert(x, where):
        if isinstance(x, dict):
            y = {k: convert(v, f"{where}.{k}") for k, v in x.items() if k != "quotes"}
            if "quotes" in x:
                y["source_spans"] = spans(x["quotes"], f"{where}[{x.get('id', '')}]")
            return y
        if isinstance(x, list):
            return [convert(v, where) for v in x]
        return x

    unc_quotes = {u["id"]: spans(u.get("quotes"), f"uncertainties[{u['id']}]") for u in draft.get("uncertainties", [])}
    ir = convert({k: v for k, v in draft.items() if k != "uncertainties"}, "")
    ir["uncertainties"] = [{k: v for k, v in u.items() if k != "quotes"} for u in draft.get("uncertainties", [])]
    ir["schema_version"] = "1.0.0"
    ir["request_ref"] = ref("request")
    ir["context_refs"] = [ref(s) for s in src if s != "request"]
    # the schema gives an uncertainty no span; what it was read from is kept under `ext`, which the schema leaves open
    # (the schema wants every key of `ext` to be a qualified name)
    ir["ext"] = {"so-trial.tool": "so_intake_trial", "uncertainty_sources": {k: v for k, v in unc_quotes.items() if v}}
    order = ["schema_version", "request_ref", "interpretation", "context", "in_scope", "out_of_scope", "constraints",
             "preferences", "user_targets", "context_refs", "uncertainties", "readiness", "ext"]
    ir = {k: ir[k] for k in order if k in ir} | {k: v for k, v in ir.items() if k not in order}
    errors = sorted(validator("intent-ir.schema.json").iter_errors(ir), key=lambda e: list(e.absolute_path))
    (OUT / variant / "intent_ir.json").write_text(json.dumps(ir, indent=2, ensure_ascii=False), encoding="utf-8")
    report = {"variant": variant, "schema_valid": not errors,
              "schema_errors": [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:160]}" for e in errors][:20],
              "quotes": stats["quotes"], "quotes_not_found": stats["not_found"]}
    (OUT / variant / "resolve.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"variant {variant}: schema {'valid' if not errors else 'INVALID (' + str(len(errors)) + ' errors)'}; "
          f"{stats['quotes']} quotes, {len(stats['not_found'])} not found word for word")
    for e in report["schema_errors"][:8]:
        print("   ", e)
    for q in stats["not_found"][:8]:
        print("    not found:", q)
    return 0 if not errors else 1


def target_items(text):
    """The parts of a target spec a reader can cite: each requirement, each stated field, each line that is not set."""
    lines = text.splitlines(keepends=True)
    at, offs = 0, []
    for ln in lines:
        offs.append(at)
        at += len(ln)
    items, i = [], 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"\s*- id: (c-[\w-]+)", ln)
        if m:
            j = i + 1
            ind = len(ln) - len(ln.lstrip())
            while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > ind):
                j += 1
            block = "".join(lines[i:j])
            items.append({"item": m.group(1), "kind": "requirement", "start": offs[i], "end": offs[i] + len(block),
                          "unset": "UNSET" in block})
            for k in range(i, j):
                if "UNSET" in lines[k].split("#")[0]:
                    items.append({"item": f"{m.group(1)}.{lines[k].split(':')[0].strip()}", "kind": "not_set",
                                  "start": offs[k], "end": offs[k] + len(lines[k])})
            i = j
            continue
        body = ln.split("#")[0]
        key = body.split(":")[0].strip().lstrip("- ")
        deliverable = re.match(r"\s*- \{item: ([\w-]+)", ln)
        if deliverable:
            key = f"deliverable {deliverable.group(1)}"
        if key and not ln.lstrip().startswith("#") and ":" in body and body.split(":", 1)[1].strip():
            kind = "not_set" if "UNSET" in body else ("left_open" if body.split(":", 1)[1].strip() == "open" else "stated")
            if key not in ("kind", "id", "title", "spec_level", "ontology_version"):
                items.append({"item": key, "kind": kind, "start": offs[i], "end": offs[i] + len(ln)})
        i += 1
    return items


def type_ranges(text):
    out = []
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"(?m)^- id: ([\w-]+)\r?\n  group:", text)]
    for n, (s, tid) in enumerate(starts):
        e = starts[n + 1][0] if n + 1 < len(starts) else (text.find("\nopen_gaps:", s) if "\nopen_gaps:" in text[s:] else len(text))
        out.append((s, e, tid))
    return out


def blocks(text, start_pattern, within=None):
    """(start, end, name) of each list item of a YAML text that opens with `start_pattern`, optionally only inside
    the top-level section `within`."""
    lo, hi = 0, len(text)
    if within:
        m = re.search(rf"(?m)^{within}:", text)
        if not m:
            return []
        lo = m.end()
        nxt = re.search(r"(?m)^[A-Za-z_]+:", text[lo:])
        hi = lo + nxt.start() if nxt else len(text)
    starts = [(lo + m.start(), m.group(1)) for m in re.finditer(start_pattern, text[lo:hi])]
    return [(s, starts[n + 1][0] if n + 1 < len(starts) else hi, name) for n, (s, name) in enumerate(starts)]


def top_sections(text):
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"(?m)^([A-Za-z_]+):", text)]
    return [(s, starts[n + 1][0] if n + 1 < len(starts) else len(text), name) for n, (s, name) in enumerate(starts)]


def score():
    report = {}
    for v in VARIANTS:
        p = OUT / v / "intent_ir.json"
        if not p.exists():
            print(f"variant {v}: no intent_ir.json")
            continue
        ir, src = json.loads(p.read_text(encoding="utf-8")), sources(v)
        res = json.loads((OUT / v / "resolve.json").read_text(encoding="utf-8"))
        cites = []                                             # (field, entry id, source, start, end)
        for field in ("context", "in_scope", "out_of_scope", "constraints", "preferences", "user_targets"):
            for e in ir.get(field, []):
                for s in e["source_spans"]:
                    cites.append((field, e["id"], s["source_ref"]["id"], s["start"], s["end"]))
        for uid, sp in ir["ext"]["uncertainty_sources"].items():
            for s in sp:
                cites.append(("uncertainties", uid, s["source_ref"]["id"], s["start"], s["end"]))
        hit = lambda sid, a, b, fields=None: sorted({(f, i) for f, i, s, x, y in cites
                                                     if s == sid and x < b and y > a and (fields is None or f in fields)})
        items = target_items(src["target"]["text"])
        target_cites = [(f, i, a, b) for f, i, s, a, b in cites if s == "target"]

        def reach(a, b, kind):
            """How many items of one kind a quoted span touches."""
            return sum(1 for it in items if it["kind"] == kind and a < it["end"] and b > it["start"])

        rows = []
        for it in items:
            touching = [(f, i, a, b) for f, i, a, b in target_cites if a < it["end"] and b > it["start"]]
            # A quote is specific to an item when, of the items of the same kind, it touches this one only. A quote
            # that spans several items of the kind (a whole list) touches each of them without singling any out.
            specific = [(f, i) for f, i, a, b in touching if reach(a, b, it["kind"]) == 1]
            rows.append(it | {"cited_by": [f"{f}:{i}" for f, i in hit("target", it["start"], it["end"])],
                              "by_uncertainty": bool(hit("target", it["start"], it["end"], {"uncertainties"})),
                              "cited_specifically_by": sorted({f"{f}:{i}" for f, i in specific}),
                              "widest_quote_touches": max((reach(a, b, it["kind"]) for _, _, a, b in touching), default=0),
                              "quote_characters": sorted({b - a for _, _, a, b in touching})})
        by_kind = {}
        for k in ("requirement", "stated", "left_open", "not_set"):
            grp = [r for r in rows if r["kind"] == k]
            by_kind[k] = {"items": len(grp), "cited": sum(1 for r in grp if r["cited_by"]),
                          "cited_specifically": sum(1 for r in grp if r["cited_specifically_by"]),
                          "touched_only_by_quotes_spanning_several": [r["item"] for r in grp if r["cited_by"] and not r["cited_specifically_by"]],
                          "cited_by_an_uncertainty": sum(1 for r in grp if r["by_uncertainty"]),
                          "not_cited": [r["item"] for r in grp if not r["cited_by"]]}
        per_source = {}
        for sid, s in src.items():
            covered = set()
            for f, i, s2, a, b in cites:
                if s2 == sid:
                    covered.update(range(a, b))
            per_source[sid] = {"characters": len(s["text"]), "cited": len(covered), "entries": len({(f, i) for f, i, s2, a, b in cites if s2 == sid})}
        types = {}
        if "node-types" in src:
            for a, b, tid in type_ranges(src["node-types"]["text"]):
                h = hit("node-types", a, b)
                if h:
                    types[tid] = [f"{f}:{i}" for f, i in h]
        engine = {}
        if "nodes" in src:                                    # the engine's own node level and system level
            nb = blocks(src["nodes"]["text"], r"(?m)^- component: ([\w-]+)", within="nodes")
            cited = {name: [f"{f}:{i}" for f, i in hit("nodes", a, b)] for a, b, name in nb}
            fields = sorted({c.split(":")[0] for cs in cited.values() for c in cs})
            engine["nodes"] = {"items": len(nb), "cited": sum(1 for c in cited.values() if c), "in_fields": fields,
                               "cited_by": {k: v2 for k, v2 in cited.items() if v2}}
        if "system" in src:
            fb = blocks(src["system"]["text"], r"(?m)^- id: ([\w-]+)", within="flows")
            fc = {name: [f"{f}:{i}" for f, i in hit("system", a, b)] for a, b, name in fb}
            sec = {name: [f"{f}:{i}" for f, i in hit("system", a, b)] for a, b, name in top_sections(src["system"]["text"])}
            engine["system_flows"] = {"items": len(fb), "cited": sum(1 for c in fc.values() if c)}
            engine["system_sections"] = {"items": len(sec), "cited": sum(1 for c in sec.values() if c),
                                         "cited_by": {k: v2 for k, v2 in sec.items() if v2}}
        unc = ir["uncertainties"]
        report[v] = {
            "engine_description": engine,
            "query_bytes": sum(s["bytes"] for s in src.values()),
            "schema_valid": res["schema_valid"], "quotes": res["quotes"], "quotes_not_found": len(res["quotes_not_found"]),
            "readiness": ir["readiness"]["status"], "readiness_reason": ir["readiness"]["reason"],
            "entries": {f: len(ir.get(f, [])) for f in ("context", "in_scope", "out_of_scope", "constraints", "preferences", "user_targets", "uncertainties")},
            "uncertainties_blocking": sum(1 for u in unc if u["blocking"]),
            "uncertainties": [{"id": u["id"], "kind": u["kind"], "blocking": u["blocking"], "description": u["description"]} for u in unc],
            "interpretation": ir["interpretation"],
            "target_spec": by_kind, "target_items": rows, "per_source": per_source,
            "node_types_cited": types,
        }
        r = report[v]
        print(f"\nvariant {v}: query {r['query_bytes'] / 1024:.0f} KB; schema {'valid' if r['schema_valid'] else 'INVALID'}; "
              f"{r['quotes_not_found']} of {r['quotes']} quotes not found; readiness {r['readiness']}")
        print("  entries:", r["entries"], "| blocking uncertainties:", r["uncertainties_blocking"])
        for k, x in by_kind.items():
            wide = x["touched_only_by_quotes_spanning_several"]
            print(f"  target spec, {k}: {x['cited']} of {x['items']} cited ({x['cited_by_an_uncertainty']} by an uncertainty); "
                  f"{x['cited_specifically']} by a quote that touches no other {k} item, {len(wide)} only by quotes spanning "
                  f"several{(' ' + str(wide)) if wide else ''}; not cited: {x['not_cited']}")
        print("  per source:", {k: f"{x['cited']}/{x['characters']} chars, {x['entries']} entries" for k, x in per_source.items()})
        if "node-types" in src:
            print(f"  node types cited: {len(types)} of {len(type_ranges(src['node-types']['text']))}:", types)
    (OUT / "score.yaml").write_text("# Written by tools/so_intake_trial.py score.\n"
                                    + yaml.safe_dump(report, allow_unicode=True, sort_keys=False, width=118), encoding="utf-8")
    return 0


def brief(variant):
    need_schemas()
    b = json.loads((OUT / variant / "research_brief.json").read_text(encoding="utf-8"))
    errors = sorted(validator("research-brief.schema.json").iter_errors(b), key=lambda e: list(e.absolute_path))
    print(f"variant {variant}: Research Brief {'valid' if not errors else 'INVALID (' + str(len(errors)) + ' errors)'} against the schema")
    for e in errors[:12]:
        print("   ", "/".join(map(str, e.absolute_path)), ":", e.message[:160])
    return 0 if not errors else 1


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "assemble":
        return assemble(*sys.argv[2:3])
    if cmd == "resolve":
        return resolve(sys.argv[2])
    if cmd == "score":
        return score()
    if cmd == "brief":
        return brief(sys.argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
