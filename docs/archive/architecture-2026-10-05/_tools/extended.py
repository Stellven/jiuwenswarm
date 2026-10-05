"""Extended vault checks for arch_lint (2026-10-01).

- types: compile every types/*.md field table by the generation rules in types/types.md, and validate
  the page's first ```json example against it;
- one definition: no other live page restates a payload type's field table;
- retired ids: names replaced by a payload type are not used outside history text and legacy pages;
- front matter: system pages and the M1 pipeline carry the machine-readable keys; `provides` ids are unique;
- graph: graph.md is generated from front matter; every depends_on target exists;
"""
import json
import re
from pathlib import Path

try:
    import jsonschema
except ImportError:  # the type dry run needs it; say so instead of passing silently (INV-8)
    jsonschema = None

LEGACY = set()
LEGACY_DIRS = ("data-foundation/",)
RETIRED = {"raw_intent": "intake", "run_request": "intake", "ext.cc_runner": "ext.cc"}
HISTORY_HEADINGS = ("history", "what changed", "open", "resolved")
FM_REQUIRED = ("id", "type", "level", "status", "provides", "depends_on")
FM_REQUIRED_LIGHT = ("id", "type", "level")
FM_PAGES = ("system/", "capabilities/", "capsule/", "README.md", "terms.md", "flow.md", "flow-variants.md", "placement.md", "verification.md", "runtime.md", "rsi.md", "build-order.md", "decisions.md")

SHA = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
REF = {"type": "object", "additionalProperties": False, "required": ["id", "sha256"],
       "properties": {"id": {"type": "string"}, "sha256": SHA}}
EVIDENCE_REF = {"type": "object", "additionalProperties": False, "required": ["evidence_type", "reference"],
                "properties": {"evidence_type": {"type": "string"}, "reference": {"type": "string"},
                               "description": {"type": "string"}, "metadata": {"type": "object"}}}
REASON = {"type": "object", "additionalProperties": False, "required": ["code", "message"],
          "properties": {"code": {"type": "string"}, "message": {"type": "string"},
                         "evidence": {"type": "array", "items": EVIDENCE_REF}}}
CHECK = {"type": "object", "additionalProperties": False,
         "required": ["id", "anchor", "target", "over", "applies_at", "runner", "description", "author"],
         "properties": {"id": {"type": "string"}, "anchor": {"type": "string"}, "target": {"type": "string"},
                        "over": {"enum": ["each_call", "outputs", "inputs_and_outputs"]},
                        "applies_at": {"enum": ["admission", "node", "both"]},
                        "runner": {"type": "object", "additionalProperties": False, "required": ["ref", "sha256"],
                                   "properties": {"ref": {"type": "string"}, "sha256": {"type": "string"}}},
                        "description": {"type": "string"}, "author": {"type": "string"}}}
SHAPES = {"Reason": REASON, "EvidenceRef": EVIDENCE_REF, "Check": CHECK}


def _rel(V, p):
    return p.relative_to(V).as_posix()


def _is_legacy(rel):
    return rel in LEGACY or rel.startswith(LEGACY_DIRS) or rel.startswith("_tools/")


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        out[k.strip()] = v
    return out


def _split_cells(row):
    return [c.strip() for c in re.split(r"(?<!\\)\|", row.strip())[1:-1]]


def field_table(text, fields_section):
    sec = fields_section(text) or ""
    rows = {}
    for tb in re.findall(r"(^\|.*\|\n\|[-| ]+\|\n(?:^\|.*\|\n?)+)", sec, flags=re.M):
        lines = tb.strip("\n").split("\n")
        if not lines[0].startswith("| Field "):
            continue
        for row in lines[2:]:
            cells = _split_cells(row)
            if len(cells) == 6:
                f, ty, req, _m1, _un, desc = cells
                rows[f.strip("`")] = (ty.strip("`"), req, desc)
    return rows


def compile_scalar(t, req, desc, problems, where):
    nullable = t.endswith("?")
    t = t[:-1] if nullable else t
    s = None
    if t in ("string", "uri", "time"):
        s = {"type": "string"}
    elif t == "text":
        s = {"type": "string", "pattern": "\\S"} if req == "req" else {"type": "string"}
    elif t == "id":
        s = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"}
    elif t in ("integer", "number", "boolean"):
        s = {"type": t}
    elif t == "sha256":
        s = SHA
    elif t == "json":
        s = {}
    elif t == "object":
        s = {"type": "object"}
    elif t in SHAPES:
        s = SHAPES[t]
    elif re.fullmatch(r"enum\((.+)\)", t):
        s = {"enum": [x.strip() for x in t[5:-1].split(",")]}
    elif re.fullmatch(r"reg\([a-z_]+\)", t):
        s = {"type": "string"}  # membership is checked against the pinned policy, not compiled (types.md rule)
    elif re.fullmatch(r"Ref\([a-z_]+\)", t):
        s = REF
    elif t.startswith("list<") and t.endswith(">"):
        s = {"type": "array", "items": compile_scalar(t[5:-1], "req", "", problems, where)}
    elif t.startswith("map<") and t.endswith(">"):
        inner = t[4:-1].split(",", 1)[1].strip()
        s = {"type": "object", "additionalProperties": compile_scalar(inner, "req", "", problems, where)}
    if s is None:
        problems.append(f"{where}: cannot compile type {t}")
        s = {}
    if desc.startswith("At least one.") and s.get("type") == "array":
        s = dict(s, minItems=1)
    if nullable:
        s = {"anyOf": [s, {"type": "null"}]}
    return s


def compile_object(rows, prefix, problems, where):
    props, required = {}, []
    for path, (ty, req, desc) in rows.items():
        if not path.startswith(prefix):
            continue
        name = path[len(prefix):]
        if "." in name or name.endswith("[]") or "[]" in name:
            continue
        if ty == "object" and any(k.startswith(path + ".") for k in rows):
            sch = compile_object(rows, path + ".", problems, where)
        elif ty == "list<object>":
            sch = {"type": "array", "items": compile_object(rows, path + "[].", problems, where)}
            if desc.startswith("At least one."):
                sch["minItems"] = 1
        else:
            sch = compile_scalar(ty, req, desc, problems, f"{where}: {path}")
        props[name] = sch
        if req == "req":
            required.append(name)
    return {"type": "object", "additionalProperties": False, "properties": props, "required": required}


def check_types(V, problems, rd, fields_section):
    type_fields = {}
    for p in sorted((V / "types").glob("*.md")):
        if p.stem == "types":
            continue
        text = rd(p)
        rows = field_table(text, fields_section)
        where = f"types/{p.name}"
        if not rows:
            problems.append(f"{where}: no field table")
            continue
        schema = compile_object(rows, "", problems, where)
        type_fields[p.name] = {k for k in rows if "." not in k and "[]" not in k and k != "ext"}
        ex = re.search(r"^## Example[^\n]*\n.*?```json\n(.*?)```", text, flags=re.M | re.S)
        if not ex:
            problems.append(f"{where}: no ## Example with a json block")
            continue
        try:
            value = json.loads(ex.group(1))
        except json.JSONDecodeError as e:
            problems.append(f"{where}: example is not valid JSON: {e}")
            continue
        if jsonschema is None:
            problems.append(f"{where}: jsonschema not installed; example not validated")
            continue
        errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(value), key=lambda e: list(e.path))
        for e in errors[:5]:
            problems.append(f"{where}: example does not match the page's fields at /{'/'.join(map(str, e.path))}: {e.message[:120]}")
    return type_fields


def check_one_definition(V, problems, rd, fields_section, type_fields, SKIP):
    for p in V.rglob("*.md"):
        rel = _rel(V, p)
        if ".obsidian" in p.parts or rel in SKIP or rel.startswith("types/") or _is_legacy(rel):
            continue
        rows = field_table(rd(p), fields_section)
        top = {k for k in rows if "." not in k and "[]" not in k and k != "ext"}
        for tname, tf in type_fields.items():
            if len(top & tf) >= 3 and top <= tf | {"ext"}:
                problems.append(f"{rel}: restates the field table of types/{tname}; link to it instead")


def _history_free_lines(text):
    keep, skipping = [], False
    in_code = False
    for line in text.split("\n"):
        if line.startswith("#"):
            skipping = any(h in line.lower() for h in HISTORY_HEADINGS)
        if line.startswith("```"):
            in_code = not in_code
        if skipping:
            continue
        if re.search(r"replac|retire|supersed|became|becomes|was |renamed|earlier|parked", line, flags=re.I):
            continue
        keep.append(line)
    return keep


def check_retired(V, problems, rd, SKIP):
    for p in V.rglob("*.md"):
        rel = _rel(V, p)
        if ".obsidian" in p.parts or rel in SKIP or _is_legacy(rel) or rel == "open-issues.md":
            continue
        for line in _history_free_lines(rd(p)):
            for old, new in RETIRED.items():
                if re.search(rf"(?<![\w.]){re.escape(old)}(?![\w])", line):
                    problems.append(f"{rel}: retired name `{old}` (use `{new}`): {line.strip()[:80]}")


def check_frontmatter_and_graph(V, problems, rd, wr):
    pages, provided = {}, {}
    for p in V.rglob("*.md"):
        rel = _rel(V, p)
        if not _is_legacy(rel) and rel.startswith('m1/') and not rd(p).startswith('---\n'):
            problems.append(f"{rel}: M1 page must begin with front matter")
        if not rel.startswith(FM_PAGES):
            continue
        fm = frontmatter(rd(p))
        for k in (FM_REQUIRED_LIGHT if rel.startswith("capsule/") else FM_REQUIRED):
            if k not in fm:
                problems.append(f"{rel}: front matter lacks `{k}`")
        for pid in fm.get("provides", []) or []:
            if pid in provided and provided[pid] != rel:
                problems.append(f"{rel}: provides `{pid}`, already provided by {provided[pid]}")
            provided[pid] = rel
        for dep in fm.get("depends_on", []) or []:
            if not (p.parent / dep).resolve().exists():
                problems.append(f"{rel}: depends_on {dep} does not exist")
        pages[rel] = fm
    # doc graph: machine-readable dependency view generated from front matter, never edited by hand
    edges = []
    for rel, fm in sorted(pages.items()):
        base = (V / rel).parent
        for dep in fm.get("depends_on", []) or []:
            target = (base / dep).resolve()
            if target.exists():
                edges.append([rel, _rel(V, target)])
    graph = {"generated_by": "_tools/arch_lint.py", "note": "Generated from front matter. Never edit by hand.",
             "pages": {rel: {"id": fm.get("id"), "level": fm.get("level"), "provides": fm.get("provides", [])}
                       for rel, fm in sorted(pages.items())},
             "edges": edges}
    g = V / "exports" / "doc-graph.json"
    g.parent.mkdir(exist_ok=True)
    if not g.exists():
        g.write_bytes(b"")
    wr(g, json.dumps(graph, indent=1, ensure_ascii=False) + chr(10))


STATUSES = ("draft", "checked", "locked", "blackbox")


def check_status(V, problems, rd):
    """`checked` means: passed the loop, and every page it depends on is checked or locked."""
    fms = {}
    for p in V.rglob("*.md"):
        rel = _rel(V, p)
        if ".obsidian" in p.parts:
            continue
        text = rd(p)
        fm = frontmatter(text)
        if not fm:
            continue
        fms[rel] = (fm, text, p)
    for rel, (fm, text, p) in fms.items():
        st = fm.get("status")
        if st and fm.get("type") in ("design", "capsule", "payload-type", "home") and st not in STATUSES + ("proposed", "processed", "past"):
            problems.append(f"{rel}: status `{st}` is not one of {', '.join(STATUSES)}")
        if st != "checked":
            continue
        banner = re.search(r"^> \*\*(Draft|Checked|Black box)[^*]*\*\*", text, flags=re.M)
        if banner and banner.group(1) == "Draft":
            problems.append(f"{rel}: status checked, but its banner still says Draft")
        for dep in fm.get("depends_on", []) or []:
            target = (p.parent / dep).resolve()
            if not target.exists():
                continue
            drel = _rel(V, target)
            dst = fms.get(drel, ({}, "", None))[0].get("status")
            if dst not in ("checked", "locked", "blackbox"):
                problems.append(f"{rel}: checked, but depends on {drel}, which is `{dst}`")


def check_diagram(V, problems, rd):
    """Flow canary: node ids named in flow.md's table exist in its graph source; the example plan only
    uses capabilities listed in the inventory."""
    flow = V / "flow.md"
    inv = V / "capabilities" / "README.md"
    plan = V / "capabilities" / "research-template.plan.json"
    if not flow.exists() or not inv.exists():
        problems.append("flow.md or capabilities/README.md missing")
        return
    text = rd(flow)
    src = re.search(r"<!-- flow-source:begin -->(.*?)<!-- flow-source:end -->", text, flags=re.S)
    if not src:
        problems.append("flow.md: no flow-source block")
        return
    ids = set(re.findall(r"([NG]_[a-z_]+)", src.group(1)))
    ov = re.search(r"## Overview.*?```mermaid\n(.*?)```", text, flags=re.S)
    for nid in set(re.findall(r"\b([NG]_[a-z_]+)\b", ov.group(1) if ov else "")):
        if nid not in ids:
            problems.append(f"flow.md: overview node {nid} is not in the graph source")
    table = text.split("## Which nodes are fixed", 1)[-1].split("## Data in and out", 1)[0]
    for nid in set(re.findall(r"([NG]_[a-z_]+)", table)):
        if nid not in ids:
            problems.append(f"flow.md: node {nid} is in the table but not in the graph source")
    for nid in ids:
        if nid not in text.split("## Graph source", 1)[0]:
            problems.append(f"flow.md: node {nid} is drawn but not described above the source")
    if plan.exists():
        import json
        names = {s["capsule_name"] for s in json.loads(rd(plan))["steps"]}
        names |= {s["gate_capsule_name"] for s in json.loads(rd(plan))["steps"]}
        inv_text = rd(inv)
        for nm in names:
            if f"`{nm}`" not in inv_text:
                problems.append(f"capabilities/research-template.plan.json: {nm} is not in the inventory")


def _with_parents(rows):
    """A page may list `identity.name` without a row for `identity`. Add the missing parent objects, required when any child is."""
    out = dict(rows)
    for path in list(rows):
        parts = path.split(".")
        for k in range(1, len(parts)):
            pre = ".".join(parts[:k])
            if pre.endswith("[]") or pre in out:
                continue
            kids = [r for p, r in rows.items() if p.startswith(pre + ".") and "." not in p[len(pre) + 1:] and "[]" not in p[len(pre) + 1:]]
            out[pre] = ("object", "req" if any(r[1] == "req" for r in kids) else "opt", "")
    return out


def _open_empty_items(node):
    """A list<object> whose item fields are described only in prose compiles to a closed empty object, which would refuse
    every item. Leave such items open and say why."""
    if isinstance(node, dict):
        it = node.get("items")
        if isinstance(it, dict) and it.get("type") == "object" and it.get("additionalProperties") is False and not it.get("properties"):
            node["items"] = {"type": "object", "x-note": "item fields are described in the page's prose, not tabulated"}
        for v in node.values():
            _open_empty_items(v)
    elif isinstance(node, list):
        for v in node:
            _open_empty_items(v)


def export_schemas(V, problems, CHECK, rd, fields_section):
    """Write every payload type, record and the Declaration as a JSON Schema file under exports/.
    The pages stay the source; these files are generated by the same compiler as the type dry run, so code can
    import them instead of re-deriving them. The vocabulary builder (toolchain M00a) must produce the same output."""
    import hashlib
    out = V / "exports"
    manifest = []
    files = {}

    def emit(kind, stem, page, rows, version, title):
        where = f"{kind}/{stem}"
        shapes = sorted({p.split(".")[0] for p in rows if "." in p and re.fullmatch(r"[A-Z][A-Za-z]+", p.split(".")[0])})
        saved = dict(SHAPES)
        for s in shapes:  # named shapes such as Port and Predicate: rows `Port.name`, used as `list<Port>`
            SHAPES[s] = compile_object(_with_parents({k: v for k, v in rows.items() if k.startswith(s + ".")}), s + ".", problems, where)
        top = {k: v for k, v in rows.items() if k.split(".")[0] not in shapes}
        sch = compile_object(_with_parents(top), "", problems, where)
        SHAPES.clear()
        SHAPES.update(saved)
        _open_empty_items(sch)
        doc = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"cc:{kind}:{stem}",
               "title": title, "x-source": page, "x-version": version}
        doc.update(sch)
        data = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        rel = f"schemas/{kind}/{stem}.schema.json"
        files[rel] = data
        manifest.append({"kind": kind, "name": title, "source": page, "version": version, "file": rel,
                         "sha256": hashlib.sha256(data).hexdigest()})

    def meta(text, stem):
        fm = frontmatter(text) or {}
        ver = str(fm.get("version", "")) if isinstance(fm, dict) else ""
        sv = re.search(r"^# .*`(cc\.[a-z_]+\.v\d+)`", text, flags=re.M)
        ver = ver or (sv.group(1) if sv else "")
        m = re.search(r"^# `([^`]+)`", text, flags=re.M)
        return ver, (m.group(1) if m else stem)

    common_rows = field_table(rd(V / "schemas" / "common.md"), fields_section)
    for p in sorted((V / "types").glob("*.md")):
        if p.stem == "types":
            continue
        text = rd(p)
        rows = field_table(text, fields_section)
        if rows:
            ver, name = meta(text, p.stem)
            emit("types", p.stem, f"types/{p.name}", rows, ver, name)
    for p in sorted((V / "schemas").glob("*.md")):
        text = rd(p)
        rows = field_table(text, fields_section)
        if p.stem in ("common", "invariants", "profiles", "schemas", "policy") or not rows:
            continue
        if "Extends [common]" in text:
            rows = {**common_rows, **rows}
        ver, name = meta(text, p.stem)
        emit("records", p.stem, f"schemas/{p.name}", rows, ver, name)
    text = rd(V / "capsule" / "fields.md")
    ver, name = meta(text, "declaration")
    # the Declaration carries only `schema_version` and `ext` from common (its page says so)
    decl_rows = {k: v for k, v in common_rows.items() if k in ("schema_version", "ext")}
    decl_rows.update(field_table(text, fields_section))
    emit("records", "declaration", "capsule/fields.md", decl_rows, ver, "declaration")
    mdoc = {"generated_by": "_tools/arch_lint.py", "note": "Generated from the field tables. Never edit by hand.",
            "schemas": manifest}
    files["manifest.json"] = (json.dumps(mdoc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    for rel, data in files.items():
        dst = out / rel
        if not dst.exists() or dst.read_bytes() != data:
            if CHECK:
                problems.append(f"exports/{rel}: out of date; run arch_lint.py")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
    for stale in out.rglob("*.schema.json") if out.exists() else []:
        if str(stale.relative_to(out)).replace("\\", "/") not in files:
            problems.append(f"exports/{stale.relative_to(out)}: no source page; delete it")


def run_extended(V, problems, CHECK, rd, wr, fields_section, type_ok, SKIP):
    check_status(V, problems, rd)
    check_diagram(V, problems, rd)
    type_fields = check_types(V, problems, rd, fields_section)
    check_one_definition(V, problems, rd, fields_section, type_fields, SKIP)
    check_retired(V, problems, rd, SKIP)
    check_frontmatter_and_graph(V, problems, rd, wr)
    export_schemas(V, problems, CHECK, rd, fields_section)
    return []
