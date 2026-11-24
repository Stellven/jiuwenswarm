#!/usr/bin/env python3
"""Generate the human-readable documents from the definition files, and check that every term is defined.

  python so_docs.py

Writes
  ontology/schema-reference.md        every field of every file kind, with type and meaning
  ontology/dictionary.md              the dictionary, from ontology/dictionary.yaml
  examples/systems/<name>/<NAME>.md   the two-layer description of each system found

Checks (exit status 1 if any fails)
  - every field in schema.yaml has a description, directly or through the definition it refers to
  - every file kind, enumerated value and registered quantity has a dictionary entry
  - no dictionary term is defined twice, and none has more than one sense
  - every term of the factory's own vocabulary that shares a word with one of ours is listed in the
    dictionary's factory_vocabulary table, and none of our files contains a phrase that vocabulary forbids

These documents are never edited by hand. Change the definition files and run this again.
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONTO = ROOT / "ontology"
def _design_package() -> pathlib.Path:
    """The factory's design package, found by walking up from this directory to the repository that holds it."""
    for base in [ROOT, *ROOT.parents]:
        cand = base / "docs" / "architecture" / "design-package"
        if cand.is_dir():
            return cand
    return ROOT / "design-package-not-found"


FACTORY_GLOSSARY = _design_package() / "glossary.md"

# Definitions shown once under "Common types" and referred to by name in the tables.
NAMED = {"status": "status", "resolution": "resolution", "cell": "value", "cell_list": "list value",
         "equivalence_level": "equivalence level", "equivalence": "equivalence", "equivalence_case": "equivalence case",
         "statement": "statement",
         "claim": "claim", "invariant": "invariant", "commit_rule": "commit rule", "allocation": "allocation",
         "timing": "timing", "resolved_at": "resolved_at", "budget": "budget", "template": "template"}
ASPECTS = ["boundary", "interface", "execution", "state", "composition", "policy", "binding", "contract", "delivery"]
KIND_ORDER = ["system", "component", "hardware", "model", "environment", "workload_profile", "mechanism",
              "engine_spec", "evidence"]
PART_TITLE = {"meta": "The ontology itself", "given": "Given: model, hardware, environment",
              "engine": "Engine: the spec and its aspects", "component": "System and component layers",
              "knowledge": "Knowledge: mechanisms, workload profiles, evidence", "inference": "Inference vocabulary"}
HANDLING_TITLE = {"renamed": "renamed on our side", "qualified": "both keep the word; ours is always qualified",
                  "same_sense": "same meaning", "unrelated": "incidental"}
STOP = {"the", "of", "on", "off", "a", "an", "and", "for", "to", "in", "cc", "m1", "prd", "core", "may", "enabled",
        "rsi", "codex", "static", "alternate", "finalization", "checking", "evolution", "propose"}


def load(name: str):
    return yaml.safe_load((ONTO / name).read_text(encoding="utf-8"))


def ref_name(node) -> str | None:
    r = node.get("$ref", "") if isinstance(node, dict) else ""
    return r.rsplit("/", 1)[1] if r else None


# ---------------------------------------------------------------- field reference

def type_text(node: dict) -> str:
    name = ref_name(node)
    if name:
        return NAMED.get(name, name)
    if "const" in node:
        return f"always `{node['const']}`"
    if "enum" in node:
        return "one of " + ", ".join(f"`{v}`" for v in node["enum"])
    if "anyOf" in node:
        return " or ".join(dict.fromkeys(type_text(x) for x in node["anyOf"]))
    t = node.get("type")
    if t == "array":
        return "list of " + type_text(node.get("items", {}))
    if isinstance(t, list):
        return "number, text or true/false"
    return {"string": "text", "number": "number", "boolean": "true/false", "object": "object", None: "any"}[t]


def object_branch(node: dict, defs: dict):
    """Return (expandable object definition or None, whether the whole thing may be written open/UNSET)."""
    name = ref_name(node)
    if name and name not in NAMED:
        node = defs[name]
    whole = False
    if "anyOf" in node:
        whole = any(set(b.get("enum", [])) >= {"open", "UNSET"} for b in node["anyOf"])
        objs = [b for b in node["anyOf"] if b.get("type") == "object" and "properties" in b]
        node = objs[0] if len(objs) == 1 else {}
    if node.get("type") == "array":
        return object_branch(node.get("items", {}), defs)
    if node.get("type") == "object" and "properties" in node:
        return node, whole
    return None, whole


def describe(sub: dict, defs: dict) -> str:
    if sub.get("description"):
        return sub["description"]
    name = ref_name(sub)
    if name:
        return defs[name].get("description", "")
    if sub.get("type") == "array":
        return describe(sub.get("items", {}), defs)
    return ""


def rows(node: dict, defs: dict, prefix: str, out: list, undescribed: list):
    obj, _ = object_branch(node, defs)
    if obj is None:
        return
    required = set(obj.get("required", []))
    for key, sub in obj["properties"].items():
        name = ref_name(sub)
        is_list = (defs[name] if name and name not in NAMED else sub).get("type") == "array"
        path = f"{prefix}{key}" + ("[]" if is_list else "")
        child, whole = object_branch(sub, defs)
        expand = child is not None and name not in NAMED
        kind = ("list of objects" if is_list else "object") if expand else type_text(sub)
        if whole:
            kind += "; the whole aspect may be `open` or `UNSET`"
        desc = describe(sub, defs)
        if not desc and "const" not in sub:
            undescribed.append(path)
        out.append(f"| `{path}` | {kind} | {'yes' if key in required else ''} | {desc} |")
        if expand:
            rows(sub, defs, path + ".", out, undescribed)


def table(node: dict, defs: dict, undescribed: list, prefix: str = "") -> list[str]:
    out = ["| Field | Type | Required | Meaning |", "|---|---|---|---|"]
    rows(node, defs, prefix, out, undescribed)
    return out


def write_reference(schema: dict, quantities: dict, predicates: dict) -> list[str]:
    defs, kinds = schema["defs"], schema["kinds"]
    undescribed: list[str] = []
    L: list[str] = []
    add = L.append
    add(f"# System Ontology {schema['ontology_version']} draft: field reference\n")
    add("Generated by `tools/so_docs.py` from the files in `ontology/`. Do not edit by hand. Where this document and "
        "the definition files disagree, the definition files win. Terms are defined in [the dictionary](dictionary.md).\n")
    add("## 1. How to read this\n")
    add("- Every description file is a YAML file with `kind` and `id` at the top. `kind` says which of the nine file kinds it is.")
    add("- `[]` in a field path means a list; the fields after it belong to each item.")
    add("- A field that is not listed here is a structural error.")
    add("- Write `UNSET` where a value is needed but no source has provided it. Write `open` where the factory may choose. "
        "Never leave a needed value blank and never guess.")
    add("- Fields whose type is a list of names (stages, states, policies, operations, mechanisms, components) are references. "
        "Each entry must be a name declared elsewhere, as the field's meaning says; they are checked.\n")
    add("### Writing the YAML\n")
    add("- Put any text that contains a colon, a comma, a `#` or a quote inside double quotes. Unquoted, YAML splits it into fields without warning.")
    add("- Identifiers such as `comp/ds4/expert-cache` need no quotes.")
    add("- A list is written `[a, b]` or one `- item` per line. A field typed as a list must be a list even with one entry.")
    add("- Several descriptions may share one file, separated by a line containing only `---`. No separator is needed before the first.")
    add("- A key written twice in the same object is an error.")
    add("- Write byte sizes with `unit_basis: decimal` or `binary`. With `binary`, `GB` means GiB.\n")
    add("The description of an engine has two layers. **System**: the engine as a whole. **Component**: one part with a single "
        "responsibility, written independently of the target machine. What a component occupies on a particular machine is written "
        "in the `composition` aspect of the engine spec for that target.\n")
    add("| File kind | What it is |\n|---|---|")
    for k in KIND_ORDER:
        add(f"| `{k}` | {kinds[k].get('description', '')} |")
    add("")
    add("## 2. Common types\n")
    add("| Type | Meaning | Values or fields |\n|---|---|---|")
    for name, shown in NAMED.items():
        d = defs[name]
        if "enum" in d:
            detail = ", ".join(f"`{v}`" for v in d["enum"])
        else:
            obj = d if d.get("type") == "object" else next((b for b in d.get("anyOf", []) if b.get("type") == "object"), {})
            detail = ", ".join(f"`{p}`" for p in obj.get("properties", {}))
        add(f"| {shown} | {d.get('description', '')} | {detail} |")
    add("")
    for name in ("cell", "equivalence_case", "statement", "claim", "invariant", "budget"):
        d = defs[name]
        obj = d if d.get("type") == "object" else next(b for b in d["anyOf"] if b.get("type") == "object")
        add(f"**Fields of a {NAMED[name]} written as an object**\n")
        L.extend(table(obj, defs, undescribed, f"{NAMED[name]}."))
        add("")
    n = 3
    for k in KIND_ORDER:
        add(f"## {n}. `{k}`\n")
        add(kinds[k].get("description", "") + "\n")
        if k == "engine_spec":
            top = {"type": "object", "required": kinds[k]["required"],
                   "properties": {p: v for p, v in kinds[k]["properties"].items() if p not in ASPECTS}}
            L.extend(table(top, defs, undescribed))
            add("\nThe nine aspects follow. In a target spec every aspect except `contract` may be written whole as `open` or `UNSET`.\n")
            for a in ASPECTS:
                add(f"### `{a}`\n")
                add(defs[a].get("description", "") + "\n")
                L.extend(table({"$ref": f"#/defs/{a}"}, defs, undescribed, f"{a}."))
                add("")
        else:
            L.extend(table(kinds[k], defs, undescribed))
            add("")
        n += 1
    add(f"## {n}. Quantities and what a requirement on each must state\n")
    add("| Quantity | Meaning | Fields a requirement must carry | Notes on those fields |\n|---|---|---|---|")
    for qid, q in quantities.items():
        notes = " ".join(f"`{f}`: {t}" for f, t in (q.get("field_notes") or {}).items())
        add(f"| `{qid}` | {q['title']} | {', '.join(f'`{f}`' for f in q['required_fields'])} | {notes} |")
    add("")
    n += 1
    add(f"## {n}. Predicates a mechanism's preconditions may use\n")
    add("Each is evaluated by program against the given part and returns one of: holds, fails, depends (on a requirement not yet decided), unknown (information missing).\n")
    add("| Predicate | Meaning | Arguments |\n|---|---|---|")
    for pid, pr in predicates.items():
        add(f"| `{pid}` | {pr['text']} | {', '.join(f'`{a}`' for a in (pr.get('args') or {}))} |")
    add("")
    n += 1
    example = ROOT / "examples" / "minimal" / "toy.yaml"
    if example.exists():
        add(f"## {n}. A complete small example\n")
        add("An invented engine with two components, with its hardware, model and system. It is a real file "
            "(`examples/minimal/toy.yaml`) and passes the same checks as every other description.\n")
        add("```yaml\n" + example.read_text(encoding="utf-8").rstrip() + "\n```\n")
        n += 1
    add(f"## {n}. Deliberately left loose\n")
    add("- `properties` on hardware items and `software` on an environment are free name and value pairs; no property names are fixed.")
    add("- `measured_under` and `results` on evidence are free objects.")
    add("- The fields of a requirement beyond the common ones are decided by the quantity table above, not listed in the structure.")
    add("- `interface` has only basic fields. Request lifecycle, concurrency, scheduling and fairness are not defined.")
    add("- A policy's `trigger` and an action's `steps` are text the program does not interpret.")
    add("- `calls` on a component are described in words; no machine-checkable signature is defined.")
    (ONTO / "schema-reference.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return sorted(set(undescribed))


# ---------------------------------------------------------------- dictionary

def schema_values(schema: dict) -> set:
    values: set = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "enum":
                    values.update(str(x) for x in v)
                elif k == "const":
                    values.add(str(v))
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema)
    return values


def schema_fields(schema: dict) -> set:
    fields: set = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "properties" and isinstance(v, dict):
                    fields.update(str(x) for x in v)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema)
    return fields


def write_dictionary(schema: dict, quantities: dict):
    doc = load("dictionary.yaml")
    terms = {t["term"]: t for t in doc["terms"]}
    needed = schema_values(schema) | set(schema["kinds"]) | set(quantities)
    missing = sorted(t for t in needed if t not in terms)
    seen, dup = set(), []
    for t in doc["terms"]:
        if t["term"] in seen:
            dup.append(t["term"])
        seen.add(t["term"])
    multi = sorted(t["term"] for t in doc["terms"] if "senses" in t)
    known = set(terms) | schema_fields(schema) | schema_values(schema)
    stale = sorted({f"{t['term']}: `{w}`" for t in doc["terms"]
                    for field in ("definition", "not", "example")
                    for w in re.findall(r"`([a-z_]+)`", str(t.get(field, ""))) if w not in known})

    L = [f"# System Ontology {schema['ontology_version']} draft: dictionary\n",
         "Generated by `tools/so_docs.py` from `ontology/dictionary.yaml`. Do not edit by hand.\n",
         "One meaning per term. This dictionary defines the concepts: every file kind, every enumerated value and the "
         "main ideas behind the fields. What each individual field holds is in the [field reference](schema-reference.md). "
         "The Chinese name is given for reference; files use the English term.\n",
         f"{len(terms)} terms.\n"]
    for part, title in PART_TITLE.items():
        entries = [t for t in doc["terms"] if t["part"] == part]
        if not entries:
            continue
        L.append(f"## {title}\n")
        L.append("| Term | 中文 | Definition | Not to be confused with | Example |")
        L.append("|---|---|---|---|---|")
        for t in entries:
            if "senses" in t:
                d = "<br>".join(f"({n}) *{x['where']}*: {x['definition']}" for n, x in enumerate(t["senses"], 1))
            else:
                d = t["definition"]
            L.append(f"| `{t['term']}` | {t.get('zh', '')} | {d} | {t.get('not', '')} | {t.get('example', '')} |")
        L.append("")
    fv = doc.get("factory_vocabulary", [])
    if fv:
        L.append("## Relation to the factory's own vocabulary\n")
        L.append("The factory has its own canonical vocabulary (`docs/architecture/design-package/glossary.md`). "
                 "Agents inside the factory read both. This table lists every factory term that shares a word with one of ours "
                 "and how the overlap is handled. Where it says renamed, the word now belongs to the factory alone.\n")
        L.append("| Factory term | Its meaning there | Our terms | Handling | Note |")
        L.append("|---|---|---|---|---|")
        order = ["renamed", "qualified", "same_sense", "unrelated"]
        for f in sorted(fv, key=lambda x: order.index(x["handling"])):
            L.append(f"| {f['factory_term']} | {f['factory_meaning']} | {', '.join('`' + o + '`' for o in f['ours'])} | "
                     f"{HANDLING_TITLE[f['handling']]} | {f.get('note', '')} |")
        L.append("")
    (ONTO / "dictionary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return missing, dup, multi, stale, len(terms)


# ---------------------------------------------------------------- relation to the factory vocabulary

def words(text: str) -> set:
    out = set()
    for w in re.split(r"[^a-z0-9]+", text.lower()):
        if len(w) > 2 and w not in STOP:
            out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


def read_factory_glossary():
    if not FACTORY_GLOSSARY.exists():
        return None
    terms, forbidden, in_table = [], [], False
    for line in FACTORY_GLOSSARY.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Term | Meaning | Home | Forbidden |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4 or set(cells[0]) <= set("-"):
                continue
            terms.append(cells[0].replace("`", ""))
            forbidden += re.findall(r"`([^`]+)`", cells[3])
    return terms, forbidden


def check_factory_vocabulary() -> list[str]:
    problems = []
    doc = load("dictionary.yaml")
    ours = {t["term"]: words(t["term"].replace("_", " ")) for t in doc["terms"]}
    listed = {f["factory_term"].replace("`", "").lower() for f in doc.get("factory_vocabulary", [])}
    for f in doc.get("factory_vocabulary", []):
        for o in f["ours"]:
            if o not in ours:
                problems.append(f"factory_vocabulary entry '{f['factory_term']}' refers to '{o}', which is not a dictionary term")
    g = read_factory_glossary()
    if g is None:
        return problems + [f"factory glossary not found at {FACTORY_GLOSSARY}; overlap not checked"]
    terms, forbidden = g
    for ft in terms:
        hit = sorted(o for o, w in ours.items() if w & words(ft))
        if hit and ft.lower() not in listed:
            problems.append(f"factory term '{ft}' shares a word with our {', '.join(hit)} and is not in the factory_vocabulary table")
    exempt = {"dictionary.yaml", "dictionary.md", "metadata-alignment.md",
              "unified-dictionary.md", "unified-dictionary.yaml"}  # these quote the factory's own terms
    for path in sorted(ROOT.rglob("*"), key=lambda p: p.relative_to(ROOT).as_posix()):   # the same order on every system
        if not (path.is_file() and path.suffix in (".yaml", ".md")) or "runs" in path.parts or "engines" in path.parts                 or "validation" in path.parts:       # records of what other engines do, in their words; not reworded
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            if phrase.lower() in text:
                problems.append(f"{path.relative_to(ROOT).as_posix()} contains the phrase '{phrase}', which the factory vocabulary forbids")
        # an engine's own identifier that contains the word (an environment variable, a flag) is not prose
        if re.search(r"(?<![_A-Za-z-])fallback(?![_A-Za-z-])", text) and path.name not in exempt:
            problems.append(f"{path.relative_to(ROOT).as_posix()} uses the word fallback, which has one meaning in the factory vocabulary; write default")
    return problems


# ---------------------------------------------------------------- two-layer description of a system

def cell_text(a) -> str:
    if isinstance(a, dict):
        return f"{a.get('value')} {a.get('unit', '')}".strip() + (f" ({a['status']})" if a.get("status") else "")
    return "" if a is None else str(a)


def write_system(sys_id: str, docs: dict) -> pathlib.Path:
    system, sys_path = docs[sys_id]
    comps = {i: d for i, (d, _) in docs.items() if d["kind"] == "component" and d["system"] == sys_id}
    short = lambda i: i.rsplit("/", 1)[-1]
    name_of = lambda i: comps[i].get("title", short(i)) if i in comps else i
    node = lambda i: "n_" + short(i).replace("-", "_")
    flows = system.get("flows", [])
    L: list[str] = []
    add = L.append
    add(f"# {system.get('title', sys_id)}\n")
    add("Generated by `tools/so_docs.py` from the description files in this directory. Do not edit by hand.\n")
    add("A two-layer description. **Layer 1, system**: the engine as a whole. **Layer 2, components**: one entry per part "
        "with a single responsibility, independent of the target machine. Terms are defined in "
        "[the dictionary](../../../ontology/dictionary.md).\n")
    add("## Layer 1: system\n")
    add(system["summary"].strip() + "\n")
    pr = system.get("product", {})
    add("| | |\n|---|---|")
    for k, label in (("name", "Product"), ("revision", "Source revision"), ("upstream", "Source"), ("form", "Form")):
        if k in pr:
            add(f"| {label} | {pr[k]} |")
    add("\n### Targets\n")
    add("| Model | Hardware | Resolved engine spec | Note |\n|---|---|---|---|")
    for t in system.get("targets", []):
        add(f"| `{t['model']}` | `{t['hardware']}` | `{t.get('spec', '')}` | {t.get('note', '')} |")
    if system.get("resource_expectations"):
        add("\n### Resource expectations\n")
        add("| Holding | Held on | Amount | Note |\n|---|---|---|---|")
        for r in system["resource_expectations"]:
            add(f"| {r['holding']} | {r['held_on']} | {cell_text(r.get('amount'))} | {r.get('note', '')} |")
    if system.get("mechanisms"):
        add("\n### Mechanism families used\n")
        for m in system["mechanisms"]:
            h = docs.get(m, ({},))[0]
            add(f"- `{m}`" + (f": {h.get('family', '')}" if h.get("family") else ""))
    if system.get("uncatalogued_mechanisms"):
        add("\n### Mechanisms with no mechanism file yet\n")
        for m in system["uncatalogued_mechanisms"]:
            add(f"- **{m['family']}**: {m['summary']}")
    if system.get("claims"):
        add("\n### Claims\n")
        add("| Claim | Status | Source | Baseline |\n|---|---|---|---|")
        for c in system["claims"]:
            add(f"| {c['text']} | {c['status']} | {c['source']} | {c.get('baseline', '')} |")
    add("\n### What this description covers\n")
    add(system.get("coverage", "").strip() + "\n")

    order = []

    def visit(cid, depth):
        order.append((cid, depth))
        for part in comps[cid].get("parts", []):
            if part in comps:
                visit(part, depth + 1)
    for cid in system["components"]:
        if cid in comps:
            visit(cid, 0)
    add("## Component tree\n")
    add("```mermaid\nflowchart TB")
    add(f'  S["{pr.get("name", sys_id)}"]')
    for cid in system["components"]:
        if cid in comps:
            add(f'  S --> {node(cid)}["{name_of(cid)}"]')
    for cid, c in comps.items():
        for part in c.get("parts", []):
            if part in comps:
                add(f'  {node(cid)} --> {node(part)}["{name_of(part)}"]')
    add("```\n")
    rank = ["code", "header_comment", "docs", "proposal"]

    def carried(c):
        how = {dv["carried_as"] for dv in c.get("derived_from", [])}
        return "adapted" if "adapted" in how else ("reused" if how else "new")
    add("| Component | Role | Runs | Responsibility | Basis |\n|---|---|---|---|---|")
    for cid, depth in order:
        c = comps[cid]
        basis = min((x["basis"] for x in c["sources"]), key=rank.index)
        add(f"| {'&nbsp;&nbsp;&nbsp;' * depth}{name_of(cid)} | `{c['role']}` | {', '.join(c['runs'])} | {c['responsibility']} | "
            f"{'' if c['role'] == 'subsystem' else (carried(c) if basis == 'proposal' else basis)} |")
    if system.get("derived_from"):
        add("\nThis engine is a design. Basis says how each component was obtained: `reused` taken over unchanged from an "
            "existing engine, `adapted` taken over and changed, `new` designed here.\n")
        add("## Derivation from existing engines\n")
        for dv in system["derived_from"]:
            add(f"- `{dv['system']}`" + (" (main source: every one of its leaf components is accounted for below)" if dv.get("main_source") else "") +
                (f": {dv['consulted_for']}" if dv.get("consulted_for") else ""))
        add("\n### Carried over\n")
        add("| Component here | Taken from | How | What changed and why |\n|---|---|---|---|")
        for cid, depth in order:
            c = comps[cid]
            dvs = c.get("derived_from", [])
            if not dvs or c["role"] == "subsystem":
                continue
            add(f"| {name_of(cid)} | {', '.join('`' + x['component'] + '`' for x in dvs)} | {carried(c)} | {dvs[0].get('adaptation', '')} |")
        add("\n### Not carried over\n")
        add("| Component of the existing engine | Why | Reason for this model and hardware |\n|---|---|---|")
        label = {"does_not_apply": "does not apply", "postponed": "postponed"}
        for dv in system["derived_from"]:
            for x in dv.get("not_carried", []):
                add(f"| `{x['component']}` | {label[x['why']]} | {x['note']} |")
        add("")
    else:
        add("\nBasis: `code` the implementation was read; `header_comment` only the file's header comment was read; `docs` documents only.\n")

    def top(i):
        while i in comps and comps[i].get("parent"):
            i = comps[i]["parent"]
        return i
    if flows:
        add("## Flows between top-level components\n")
        add("```mermaid\nflowchart LR")
        seen = set()
        for f in flows:
            a, b = top(f["sender"]), top(f["receiver"])
            if a == b or (a, b) in seen:
                continue
            seen.add((a, b))
            left = f'{node(a)}["{name_of(a)}"]' if a in comps else f'{a}(["{a}"])'
            right = f'{node(b)}["{name_of(b)}"]' if b in comps else f'{b}(["{b}"])'
            add(f"  {left} --> {right}")
        add("```\n")
        add("### All flows\n")
        add("| Flow | From | To | Carries | When | Description |\n|---|---|---|---|---|---|")
        for f in flows:
            c = f["carries"]
            add(f"| `{f['id']}` | {name_of(f['sender'])} | {name_of(f['receiver'])} | {c['content']}" +
                ("".join(f" `{r}`" for r in c.get("refs", []))) + f" | {f.get('timing', '')} | {f.get('description', '')} |")
        add("")

    add("## Layer 2: components\n")
    for cid, depth in order:
        c = comps[cid]
        add(f"{'###' if depth == 0 else '####'} {name_of(cid)}\n")
        add(f"`{cid}` · role `{c['role']}` · runs {', '.join(c['runs'])}" + (f" · part of `{c['parent']}`" if c.get("parent") else "") + "\n")
        add(f"**Responsibility.** {c['responsibility']}\n")
        if c.get("not_responsible_for"):
            add("**Not responsible for.** " + "; ".join(c["not_responsible_for"]) + ".\n")
        if c.get("parts"):
            add("**Parts.** " + ", ".join(name_of(x) for x in c["parts"]) + ".\n")
        facts = []
        if c.get("implements_stages"):
            facts.append(("Implements stages", ", ".join(f"`{x}`" for x in c["implements_stages"])))
        if c.get("performs"):
            facts.append(("Performs model operations", ", ".join(f"`{x}`" for x in c["performs"])))
        st = c.get("state", {})
        for k, label in (("owns", "Owns state"), ("reads", "Reads state"), ("writes", "Writes state")):
            if st.get(k):
                facts.append((label, ", ".join(f"`{x}`" for x in st[k])))
        if c.get("policies"):
            facts.append(("Runs policies", ", ".join(f"`{x}`" for x in c["policies"])))
        if c.get("mechanisms"):
            facts.append(("Implements mechanisms", ", ".join(f"`{x}`" for x in c["mechanisms"])))
        if c.get("requires_capabilities"):
            facts.append(("Requires", "; ".join(c["requires_capabilities"])))
        if c.get("observation_points"):
            facts.append(("Observation points", ", ".join(f"`{x}`" for x in c["observation_points"])))
        if c.get("equivalence"):
            e = c["equivalence"]
            cases = [e] if not isinstance(e, list) else e
            facts.append(("Effect on output", "; ".join(
                f"`{x}`" if isinstance(x, str) else f"`{x['level']}`" + (f" when {x['holds_when']}" if x.get("holds_when") else "")
                + (f". {x['note']}" if x.get("note") else "") for x in cases)))
        if facts:
            add("| | |\n|---|---|")
            for k, v in facts:
                add(f"| {k} | {v} |")
            add("")
        mine = [f for f in flows if cid in (f["sender"], f["receiver"])]
        if mine:
            add("| Direction | Flow | Other end | Carries | When |\n|---|---|---|---|---|")
            for f in mine:
                inbound = f["receiver"] == cid
                other = f["sender"] if inbound else f["receiver"]
                c2 = f["carries"]
                add(f"| {'in' if inbound else 'out'} | {f.get('description', f['id'])} | {name_of(other)} | {c2['content']}" +
                    ("".join(f" `{r}`" for r in c2.get("refs", []))) + f" | {f.get('timing', '')} |")
            add("")
        if c.get("needs_resources"):
            add("| Needs | For |\n|---|---|")
            for r in c["needs_resources"]:
                add(f"| {r['resource']} | {r['purpose']}" + (f" ({r['note']})" if r.get("note") else "") + " |")
            add("")
        for t in system.get("targets", []):
            spec = docs.get(t.get("spec", ""), ({},))[0]
            comp_aspect = spec.get("composition")
            for entry in (comp_aspect.get("components", []) if isinstance(comp_aspect, dict) else []):
                if entry.get("component_ref") != cid:
                    continue
                if entry.get("active") is False:
                    add(f"**On `{t['hardware']}`.** Not active: {entry.get('inactive_reason', '')}\n")
                    continue
                if entry.get("manages") or entry.get("uses"):
                    add(f"**On `{t['hardware']}`.**\n")
                    add("| Where | Purpose | Occupancy | Amount | Fixed at |\n|---|---|---|---|---|")
                    for m in entry.get("manages", []):
                        add(f"| `{m['pool']}` | holds `{m['data']}` (a residency entry of the binding) | | | |")
                    for u in entry.get("uses", []):
                        add(f"| `{u['where']}` | {u['purpose']} | {u.get('allocation', '')} | {cell_text(u.get('amount'))} | {u.get('resolved_at', '')} |")
                    add("")
        if c.get("decisions"):
            add("| Decision | Value | Fixed at | Source |\n|---|---|---|---|")
            for d in c["decisions"]:
                v = d.get("value")
                src = (v.get("source") if isinstance(v, dict) else None) or d.get("source", "")
                add(f"| {d['text']} | {cell_text(v)} | {d.get('resolved_at', '')} | {src} |")
            add("")
        if c.get("calls"):
            add("| Call | Takes | Returns | Guarantees |\n|---|---|---|---|")
            for x in c["calls"]:
                add(f"| `{x['name']}` | {x.get('takes', '')} | {x.get('returns', '')} | {x['does']} |")
            add("")
        if c.get("invariants"):
            add("**Invariants.**\n")
            for inv in c["invariants"]:
                add(f"- `{inv['id']}`: {inv['text']}")
            add("")
        if c.get("verification"):
            add("| Checked by | What | Against | Where |\n|---|---|---|---|")
            for v in c["verification"]:
                add(f"| {v['method']} | {v['checks']} | {v.get('against', '')} | {v.get('source', '')} |")
            add("")
        for key, label in (("costs", "Costs"), ("claims", "Claims")):
            if c.get(key):
                add(f"**{label}.**\n")
                for x in c[key]:
                    extra = f"; baseline: {x['baseline']}" if x.get("baseline") else ""
                    add(f"- {x['text']} ({x['status']}; {x['source']}{extra})")
                add("")
        add("**Sources.** " + "; ".join(f"`{x['ref']}` ({x['basis']})" for x in c["sources"]) + "\n")
        if c.get("not_read"):
            add(f"**Not read.** {c['not_read']}\n")
    out = sys_path.parent / (short(sys_id).upper() + ".md")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out


def all_documents() -> dict:
    docs = {}
    for path in sorted(ROOT.rglob("*.yaml"), key=lambda p: p.relative_to(ROOT).as_posix()):   # the same order on every system
        if ONTO in path.parents or "runs" in path.parts or "validation" in path.parts:
            continue
        try:
            for d in yaml.safe_load_all(path.read_text(encoding="utf-8")):
                if isinstance(d, dict) and "kind" in d and "id" in d:
                    docs[d["id"]] = (d, path)
        except yaml.YAMLError:
            continue
    return docs


FACTORY_REFERENCE = _design_package() / "reference"


def factory_metadata_names() -> dict:
    """Every field name and fixed value of the factory's metadata: the CC declaration schema, the other IR schemas
    and the shared field contracts. Returns name -> list of (where, 'field' or 'value', meaning)."""
    import collections
    import json
    names = collections.defaultdict(list)

    def walk(o, where, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("properties", "$defs", "definitions") and isinstance(v, dict):
                    for n, sub in v.items():
                        names[n].append((f"{where}{path}", "field", sub.get("description", "") if isinstance(sub, dict) else ""))
                        walk(sub, where, path + "." + n)
                elif k == "enum" and isinstance(v, list):
                    for n in v:
                        if isinstance(n, str):
                            names[n].append((f"{where}{path}", "value", ""))
                else:
                    walk(v, where, path)
        elif isinstance(o, list):
            for x in o:
                walk(x, where, path)

    for sp in sorted((FACTORY_REFERENCE / "schemas").glob("*.json")):
        walk(json.loads(sp.read_text(encoding="utf-8")), sp.name.replace(".schema.json", ""))
    decl = FACTORY_REFERENCE / "declaration.md"
    if decl.exists():
        for line in decl.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\| `([A-Za-z_][A-Za-z0-9_.\[\]]*)` \|(.+)\|\s*$", line)
            if not m:
                continue
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) < 4:
                continue
            path = m.group(1).replace("[]", "")
            leaf = path.split(".")[-1]
            where = "capsule-declaration" + ("." + ".".join(path.split(".")[:-1]) if "." in path else "")
            for i, (w, k, mean) in enumerate(names.get(leaf, [])):
                if k == "field" and not mean and w == where:
                    names[leaf][i] = (w, k, cells[-1])
    fc_path = FACTORY_REFERENCE / "field-contracts.json"
    if fc_path.exists():
        fc = json.loads(fc_path.read_text(encoding="utf-8"))
        groups = [(f"type {tn}", t.get("fields") or {}) for tn, t in fc.get("types", {}).items()] + \
                 [(it.get("name", "?"), it.get("fields") or {}) for it in fc.get("interfaces", [])]
        for where, fields in groups:
            for fn, f in (fields.items() if isinstance(fields, dict) else []):
                f = f if isinstance(f, dict) else {}
                names[fn].append((where, "field", f.get("meaning") or f.get("description") or ""))
                for v in f.get("enum") or f.get("values") or []:
                    if isinstance(v, str):
                        names[v].append((f"{where}.{fn}", "value", ""))
    return names


def check_metadata_vocabulary() -> list[str]:
    """Every name our dictionary shares with the factory's metadata has a verdict; no verdict is left over."""
    doc = load("dictionary.yaml")
    listed = {e["name"]: e for e in doc.get("metadata_vocabulary", [])}
    if not (FACTORY_REFERENCE / "schemas").exists():
        return [f"factory metadata not found at {FACTORY_REFERENCE}; overlap not checked"]
    theirs = factory_metadata_names()
    ours = {t["term"] for t in doc["terms"]}
    problems = []
    for n in sorted(ours & set(theirs)):
        if n not in listed:
            where = sorted({w.split(".")[0] for w, _, _ in theirs[n]})[:3]
            problems.append(f"'{n}' is also a name in the factory's metadata ({', '.join(where)}) and has no entry in metadata_vocabulary")
    for n in sorted(set(listed) - (ours & set(theirs))):
        problems.append(f"metadata_vocabulary lists '{n}', which the two sides no longer share")
    for n, e in listed.items():
        if e.get("candidate") and (e["candidate"] in theirs or e["candidate"] in ours):
            problems.append(f"metadata_vocabulary entry '{n}' proposes '{e['candidate']}', which is already a name on one side")
        if e.get("verdict") not in ("same", "minor", "decide"):
            problems.append(f"metadata_vocabulary entry '{n}' has no verdict (same, minor or decide)")
    return problems


def write_metadata_alignment() -> pathlib.Path:
    doc = load("dictionary.yaml")
    terms = {t["term"]: t for t in doc["terms"]}
    theirs = factory_metadata_names()
    entries = doc.get("metadata_vocabulary", [])

    def cell(x):
        return str(x or "").replace("|", "/").replace("\n", " ")

    def where(n):
        ws = sorted({w.split(".")[0] for w, _, _ in theirs.get(n, [])})
        return ", ".join(ws[:3]) + (f" and {len(ws) - 3} more" if len(ws) > 3 else "")

    def rows(verdict, with_candidate):
        out = []
        for e in entries:
            if e["verdict"] != verdict:
                continue
            r = f"| `{e['name']}` | {cell(terms[e['name']]['definition'])} | {cell(e['factory_use'])} ({where(e['name'])}) | {cell(e.get('difference'))} |"
            out.append(r + (f" {('`' + e['candidate'] + '`') if e.get('candidate') else 'keep'} |" if with_candidate else ""))
        return "\n".join(out)

    n = {v: sum(1 for e in entries if e["verdict"] == v) for v in ("decide", "minor", "same")}

    # our one-word terms that are a word inside a longer factory name (binding inside input_bindings, ...)
    def tokens(name):
        return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.split(r"[_.:/ -]+", name.lower()) if w}
    their_tokens = {name: tokens(name) for name in theirs}
    shared_exact = {e["name"] for e in entries}
    inside = []
    for t in terms:
        if "_" in t or t in shared_exact:
            continue
        key = t[:-1] if len(t) > 3 and t.endswith("s") else t
        hits = sorted(name for name, ws in their_tokens.items() if key in ws)
        if len(hits) >= 3:
            inside.append((t, hits))
    inside.sort(key=lambda x: -len(x[1]))
    inside_rows = "\n".join(
        f"| `{t}` | {cell(terms[t]['definition'])} | {len(h)} | {', '.join('`' + x + '`' for x in h[:4])} |" for t, h in inside)
    L = [f"""# Engine ontology dictionary and the factory's metadata: shared names

Generated by `tools/so_docs.py` from `ontology/dictionary.yaml`. Do not edit by hand.

## What this is

The engine ontology dictionary has {len(terms)} terms. Each is a file kind, a field name or a fixed value of the
System Ontology format, so it is a dictionary of metadata. The factory's own metadata is defined under
`docs/architecture/design-package/reference/`: the CC declaration schema, the other IR schemas (intent IR, research
brief, gate decision, verifier assessment and so on) and the shared field contracts. Together they use
{len(theirs)} field names and fixed values.

A program compared the two lists by exact name. They share **{len(entries)} names**. This document gives a verdict for
each. Nothing in the factory's metadata has been changed; any rename would be made in our dictionary.

| Verdict | Count | Meaning |
|---|---|---|
| decide | {n['decide']} | Different meaning, and a reader meets the name often on both sides. We ask for a decision |
| minor | {n['minor']} | Different meaning, but on one side it is only a fixed value or a rarely met field. We propose to keep most |
| same | {n['same']} | Same sense on both sides. No action |

## What we need from you

1. For the **decide** table: rename ours to the candidate, rename to something else, or keep.
2. For the **minor** table: tell us if you want any of them renamed.
3. For the five terms named under "a word inside longer factory names": rename or keep.
4. Tell us whether the dictionary should cover System Ontology only, aligned with CC metadata as here, or become
   one dictionary for both.

## Decide ({n['decide']})

| Name | In the engine ontology | In the factory's metadata | Difference | Candidate for ours |
|---|---|---|---|---|
{rows('decide', True)}

## Minor ({n['minor']})

| Name | In the engine ontology | In the factory's metadata | Difference | Candidate for ours |
|---|---|---|---|---|
{rows('minor', True)}

## Same sense ({n['same']})

| Name | In the engine ontology | In the factory's metadata | Note |
|---|---|---|---|
{rows('same', False)}

## Our terms that are a word inside longer factory names ({len(inside)})

These are not exact matches, so they have no verdict yet. They are listed because a reader who knows
`contract_ref` or `input_bindings` will carry that meaning to our `contract` and `binding`. Three or more
factory names each.

| Our term | In the engine ontology | Factory names containing it | Examples |
|---|---|---|---|
{inside_rows}

Our view: `binding`, `contract`, `policy`, `template` and `selection` are the ones to rename, because on our side
they are structural names of an engine spec and on the factory's side they are structural names of a run plan.
Candidates: `placement`, `acceptance_terms`, `runtime_policy`, `spec_fragment`, `sparse_choice`. (Not `acceptance`:
that is already a field of a CC declaration.) `evidence`, `decisions`,
`request`, `execution` and `hardware` carry the same general sense on both sides.

## One structural observation

A CC declaration and an engine component description are built alike. Both state what the thing needs, what it
guarantees, its limits and the invariants it keeps (`needs`, `guarantees`, `budget`, `changes.invariants` in a
declaration; `needs_resources`, `invariants`, `equivalence`, `decisions` in a component). That is why so many
shared names have the same sense. If one dictionary for both is wanted, these common structural words are the
natural shared core.
"""]
    out = ROOT / "ontology" / "metadata-alignment.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def write_unified_dictionary() -> tuple:
    """One dictionary for both sides, built incrementally: the engine ontology's terms as we maintain them, and the
    factory's metadata names imported read-only from the factory's own files. Nothing on the factory side is edited."""
    doc = load("dictionary.yaml")
    terms = {t["term"]: t for t in doc["terms"]}
    verdicts = {e["name"]: e for e in doc.get("metadata_vocabulary", [])}
    theirs = factory_metadata_names()

    def cell(x):
        return str(x or "").replace("|", "/").replace("\n", " ")

    def uses(name, limit=None):
        seen, out = set(), []
        for w, k, m in theirs.get(name, []):
            key = (w, k)
            if key in seen:
                continue
            seen.add(key)
            out.append({"where": w, "as": k, **({"meaning": m} if m else {})})
        return out if limit is None else out[:limit]

    entries = []
    for name in sorted(set(terms) | set(theirs), key=lambda s: (s.lower(), s.swapcase())):   # a fixed order for names that differ only in case
        e = {"name": name, "side": "both" if name in terms and name in theirs else ("engine" if name in terms else "factory")}
        if name in terms:
            t = terms[name]
            e["engine"] = {k: t[k] for k in ("definition", "part", "zh", "not", "example") if k in t}
        if name in theirs:
            e["factory"] = uses(name)
        if name in verdicts:
            v = verdicts[name]
            e["verdict"] = v["verdict"]
            if v.get("difference"):
                e["difference"] = v["difference"]
        entries.append(e)
    n = {side: sum(1 for e in entries if e["side"] == side) for side in ("engine", "factory", "both")}
    head = ("# Unified metadata dictionary: generated by tools/so_docs.py. Do not edit.\n"
            "# engine: terms of the System Ontology format, maintained in ontology/dictionary.yaml.\n"
            "# factory: field names and fixed values of the CC declaration, the other IR schemas and the shared field\n"
            "#          contracts, read from docs/architecture/design-package/reference/ and never changed from here.\n"
            "# both: the same name on both sides; `verdict` says whether the meaning is the same.\n")
    ypath = ROOT / "ontology" / "unified-dictionary.yaml"
    ypath.write_text(head + yaml.safe_dump({"counts": n, "entries": entries}, allow_unicode=True, sort_keys=False, width=160),
                     encoding="utf-8")

    L = [f"""# Unified metadata dictionary (first increment)

Generated by `tools/so_docs.py`. Do not edit by hand. The machine-readable form is `unified-dictionary.yaml`.

One list of every metadata name a model in the factory can meet, from both sides:

| Side | Names | Source | Who maintains it |
|---|---|---|---|
| Engine | {n['engine'] + n['both']} | `ontology/dictionary.yaml`: file kinds, field names and fixed values of the System Ontology format | System Ontology workstream |
| Factory | {n['factory'] + n['both']} | `docs/architecture/design-package/reference/`: the CC declaration, the other IR schemas, the shared field contracts | The factory's maintainers |

{n['both']} names are on both sides. This increment only reads the factory's files; it changes nothing in them.
A factory name has a meaning here only where the factory's own files give one.

## 1. Names on both sides ({n['both']})

| Name | Verdict | Engine meaning | Factory use |
|---|---|---|---|"""]
    order = {"decide": 0, "minor": 1, "same": 2}
    for e in sorted((x for x in entries if x["side"] == "both"), key=lambda x: (order.get(x.get("verdict"), 9), x["name"])):
        f = e["factory"]
        fu = "; ".join(f"{u['where']}" + (f": {u['meaning']}" if u.get("meaning") else f" ({u['as']})") for u in f[:2])
        if len(f) > 2:
            fu += f"; and {len(f) - 2} more"
        L.append(f"| `{e['name']}` | {e.get('verdict', '')} | {cell(e['engine']['definition'])} | {cell(fu)} |")

    L.append(f"\n## 2. Engine side only ({n['engine']})\n\nFull entries with examples are in [dictionary.md](dictionary.md).\n")
    L.append("| Name | Part | Meaning |\n|---|---|---|")
    for e in entries:
        if e["side"] == "engine":
            L.append(f"| `{e['name']}` | {e['engine'].get('part', '')} | {cell(e['engine']['definition'])} |")

    L.append(f"\n## 3. Factory side only ({n['factory']})\n\nGrouped by the record that defines the name. "
             "A name used by several records is listed under the first.\n")
    groups = {}
    for e in entries:
        if e["side"] == "factory":
            first = e["factory"][0]
            top = first["where"].split(".")[0]
            groups.setdefault(top, []).append((e["name"], first, len(e["factory"])))
    for top in sorted(groups, key=lambda g: (g.startswith("type "), g.lower())):
        L.append(f"\n### {top}\n\n| Name | As | Meaning |\n|---|---|---|")
        for name, first, count in groups[top]:
            meaning = first.get("meaning") or (f"A value of `{first['where']}`" if first["as"] == "value" else "")
            more = f" (also in {count - 1} other places)" if count > 1 else ""
            L.append(f"| `{name}` | {first['as']} | {cell(meaning)}{more} |")
    mpath = ROOT / "ontology" / "unified-dictionary.md"
    mpath.write_text("\n".join(L) + "\n", encoding="utf-8")
    undefined = sum(1 for e in entries if e["side"] == "factory" and e["factory"][0]["as"] == "field"
                    and not any(u.get("meaning") for u in e["factory"]))
    return mpath, n, undefined


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    schema, quantities, predicates = load("schema.yaml"), load("quantities.yaml")["quantities"], load("predicates.yaml")["predicates"]
    undescribed = write_reference(schema, quantities, predicates)
    print("wrote ontology/schema-reference.md")
    missing, dup, multi, stale, count = write_dictionary(schema, quantities)
    print(f"wrote ontology/dictionary.md ({count} terms)")
    docs = all_documents()
    for i, (d, _) in docs.items():
        if d["kind"] == "system":
            print(f"wrote {write_system(i, docs).relative_to(ROOT).as_posix()}")
    # The comparison with the factory's vocabulary reads the factory's design package, which is in the repository and
    # not in this directory. Without it those files are left as they are, and this is said.
    have_factory = FACTORY_GLOSSARY.exists() and (FACTORY_REFERENCE / "schemas").exists()
    factory, metadata = [], []
    if not have_factory:
        print("skipped: ontology/metadata-alignment.md and ontology/unified-dictionary.* compare this vocabulary with the "
              "factory's design package (docs/architecture/design-package in the repository), which was not found from "
              "this directory. They were left as they are and the overlap was not checked.")
    else:
        factory = check_factory_vocabulary()
        metadata = check_metadata_vocabulary()
        print(f"wrote {write_metadata_alignment().relative_to(ROOT).as_posix()}")
    if have_factory:
        upath, counts, undefined = write_unified_dictionary()
        print(f"wrote {upath.relative_to(ROOT).as_posix()} and .yaml ({counts['engine']} engine only, {counts['factory']} factory only, "
              f"{counts['both']} on both sides; {undefined} factory fields have no meaning in the factory's files)")
    ok = True
    for label, items in (("fields without a description", undescribed), ("terms without a dictionary entry", missing),
                         ("terms defined twice", dup), ("terms with more than one sense", multi),
                         ("dictionary entries that name a field or value that does not exist", stale)):
        if items:
            ok = False
            print(f"{label} ({len(items)}): " + ", ".join(items))
    for x in factory:
        ok = False
        print("factory vocabulary: " + x)
    for x in metadata:
        ok = False
        print("factory metadata: " + x)
    if ok:
        print("all checks pass: every field is described, every term is defined once"
              + (", no overlap with the factory glossary or the factory's metadata is unexplained" if have_factory
                 else "; the overlap with the factory's vocabulary was not checked"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
