"""arch_lint: keep the architecture vault consistent. Every fact is edited in one place; this regenerates the rest
and checks that the pieces still fit. Lives in jiuwenswarm docs/architecture/_tools/ (moved from tundle 2026-10-01).

Usage: python arch_lint.py [DOCS] [--check]          regenerate, then lint (DOCS defaults to this vault)

Earlier header, kept:
Keep the architecture docs consistent: every fact is edited in one place, and this regenerates the rest.

Runs on the single source of truth: jiuwenswarm docs/architecture (branch ai4r_main_branch).
Skips OVERVIEW.md (historical task source), the verbatim router design and .obsidian/.

Generates:
- the schema map between `<!-- sync:schema-map -->` markers in schemas/schemas.md, from the field tables:
  every `Ref(kind)`, `decl_hash`, `interface_hash`, `current_hash`, `check_id`, `list<Check>`, port type,
  `vocabulary_ref`, `produced_by` and `policy_ref` field is an edge, so the diagram cannot drift.

Lints:
- every field table on a schema page: header, types from the grammar (INV-11), Req, M1 (checked or unchecked),
  and an Unlocks entry exactly when unchecked; INV-12 suffixes for ids, hashes, times and Ref fields;
- INV-13: every reason code in the policy's `reason_code` registry is UPPER_SNAKE;
- every record page is listed in the records table of schemas.md;
- links: no broken Markdown or wiki links;
- Mermaid blocks: ASCII only, no ';' in labels.

Usage: python architecture_sync.py [DOCS]            regenerate, then lint
       python architecture_sync.py [DOCS] --check    lint only; exit 1 on any problem
DOCS defaults to ~/huawei/jiuwenswarm/docs/architecture.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
V = Path(ARGS[0]) if ARGS else Path(__file__).resolve().parent.parent
V = V.resolve()
SKIP = {"OVERVIEW.md", "model_router_design_en.md"}  # verbatim external originals are not linted
SCHEMAS = V / "schemas"
CHECK = "--check" in sys.argv
problems = []

from example_views import refresh as refresh_example_views
if not refresh_example_views(V, CHECK):
    problems.append("types/evidence-bundle.md: stale generated example or flow view; run flow_views.py and arch_lint.py")

# Record pages in reading order; foundation pages are listed separately.
RECORDS = ["declaration", "candidate", "port-types", "checks", "verdict", "standing", "binding", "observation",
           "artifact", "verification-record", "finding"]
FOUNDATION = ["common", "policy"]
M1 = ("checked", "unchecked")


def rd(p):
    return p.read_bytes().decode("utf-8")


def wr(p, s):
    if rd(p) != s:
        if CHECK:
            problems.append(f"{p.relative_to(V)}: out of date; run architecture_sync.py")
        else:
            p.write_bytes(s.encode("utf-8"))


def title(s):
    m = re.search(r"^# (.+?)(?: · .*)?$", s, flags=re.M)
    return m.group(1).strip() if m else ""


def replace_marked(s, name, body):
    pat = re.compile(rf"(<!-- sync:{name} -->\n)(.*?)(<!-- /sync:{name} -->)", flags=re.S)
    if not pat.search(s):
        problems.append(f"missing marker sync:{name}")
        return s
    return pat.sub(lambda m: m.group(1) + body.strip() + "\n" + m.group(3), s, count=1)


def fields_section(s):
    m = re.search(r"^## Fields[^\n]*\n(.*?)(?=^## |\Z)", s, flags=re.M | re.S)
    return m.group(1) if m else None


schema_pages = {p.stem: p for p in SCHEMAS.glob("*.md")}
# The Declaration is the capsule's own schema, so it lives in the capsule folder.
schema_pages["declaration"] = V / "capsule" / "fields.md"
for stem in RECORDS + FOUNDATION:
    if stem not in schema_pages:
        problems.append(f"schemas/{stem}.md: missing")
stitle = {k: title(rd(p)) for k, p in schema_pages.items()}

# ---------------- schema map, generated from the field tables ----------------
# An edge A -> B means record A points at record B. Common is left out: every record extends it.
KIND_PAGE = {"artifact": "artifact", "test_case": "checks", "test_suite": "checks", "verdict": "verdict",
             "verification_result": "verification-record", "verification_request": "verification-record",
             "observation": "observation", "candidate": "candidate", "standing": "standing", "finding": "finding",
             "binding": "binding", "policy": "policy", "declaration": "declaration"}
MAP_PAGES = [x for x in RECORDS + FOUNDATION if x != "common" and x in schema_pages]
ROW = re.compile(r"^\| `([^`]+)` \| `([^`]+)` \| (?:req|opt) \| [^|]* \|[^|]*\| (.*) \|$", flags=re.M)


def field_rows(s):
    sec = fields_section(s) or ""
    return ROW.findall(sec)


edges = {}
for stem in MAP_PAGES:
    for f, ty, desc in field_rows(rd(schema_pages[stem])):
        leaf = f.split(".")[-1].split("[]")[-1]
        targets = [KIND_PAGE.get(k, k) for k in re.findall(r"Ref\((\w+)\)", ty)]
        if leaf in ("decl_hash", "interface_hash", "current_hash", "inherited_from_hash", "parent_hash",
                    "co_parent_hashes") or (stem == "candidate" and f == "declaration"):
            targets.append("declaration")
        if leaf in ("check_id", "check_ids", "criterion_check_id") or "list<Check>" in ty:
            targets.append("checks")
        if "reg(port_type)" in ty or leaf in ("vocabulary_version", "vocabulary_ref"):
            targets.append("port-types")
        if leaf == "produced_by":  # an id, not a Ref, but still a pointer
            targets.append("observation")
        if leaf == "subjects" and "list<object>" in ty:  # typed subjects: the kinds are named in the description
            targets += [pg for tok, pg in (("decl_hash", "declaration"), ("check_id", "checks"), ("verdict_id", "verdict"))
                        if tok in desc]
        if leaf == "policy_ref":
            targets.append("policy")
        if leaf == "checks" and "list<object>" in ty and "check_id" in desc:  # {check_id, source} lists
            targets.append("checks")
        for t in targets:
            if t != stem and t in MAP_PAGES:
                edges.setdefault((stem, t), [])
                if leaf not in edges[(stem, t)]:
                    edges[(stem, t)].append(leaf)


def nid(stem):
    return "s_" + re.sub(r"[^A-Za-z0-9]", "_", stem)


def mermaid(pages):
    out = ["```mermaid", "flowchart LR"]
    for x in pages:
        name = stitle[x].split(":")[0].strip()
        shape = ('[/"', '"/]') if x == "policy" else ('["', '"]')
        out.append(f"    {nid(x)}{shape[0]}{name}{shape[1]}")
    for (a, b), labels in sorted(edges.items()):
        out.append(f"    {nid(a)} -->|{', '.join(labels)}| {nid(b)}")
    out.append("```")
    return "\n".join(out)


p = SCHEMAS / "schemas.md"
s = rd(p)
s = replace_marked(s, "schema-map", mermaid(MAP_PAGES))
wr(p, s)

# ---------------- the Unlocks grouping, generated from the Unlocks column ----------------
# One group per Unlocks tag. A child row is left out when its parent row is already in the group.
groups = {}
for stem in RECORDS + FOUNDATION:
    if stem not in schema_pages:
        continue
    s = rd(schema_pages[stem])
    rec = stitle[stem].split(":")[0].strip()
    for row in re.findall(r"^\| `[^`]+` \| `[^`]+` \| (?:req|opt) \| unchecked \|[^\n]*$", fields_section(s) or "", flags=re.M):
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", row.strip())[1:-1]]
        f = cells[0].strip("`")
        for tag in (x.strip() for x in cells[4].split(",") if x.strip()):
            fl = groups.setdefault(tag, {}).setdefault(rec, [])
            if not any(f.startswith(g + ".") or f.startswith(g + "[].") for g in fl):
                fl.append(f)
rows = ["| Unlocks | Unchecked fields |", "|---|---|"]
for tag in sorted(groups, key=lambda x: (x != "RSI", x.lower())):
    parts = [rec + " " + ", ".join(f"`{f}`" for f in fl) for rec, fl in groups[tag].items()]
    rows.append(f"| {tag} | {'; '.join(parts)} |")
p = V / "capsule" / "stages.md"
if p.exists():
    wr(p, replace_marked(rd(p), "unlocks", "\n".join(rows)))

# ---------------- lint: field tables ----------------
BASE = {"string", "text", "integer", "number", "boolean", "time", "sha256", "id", "uri", "json", "object",
        "EvidenceRef", "Reason", "Predicate", "Check", "Port"}


def type_ok(t):
    t = t.strip().strip("`").strip()
    if t.endswith("?"):
        t = t[:-1]
    if t in BASE:
        return True
    if re.fullmatch(r"enum\([A-Za-z0-9_]+(, ?[A-Za-z0-9_]+)*\)", t) or re.fullmatch(r"reg\([a-z_]+\)", t) \
            or re.fullmatch(r"Ref\([a-z_]+\)", t):
        return True
    m = re.fullmatch(r"list<(.+)>", t)
    if m:
        return type_ok(m.group(1))
    m = re.fullmatch(r"map<([^,]+), ?(.+)>", t)
    if m:
        return type_ok(m.group(1)) and type_ok(m.group(2))
    return False


HEADER = "| Field | Type | Req | M1 | Unlocks | Description |"
# Payload types (types/*.md) follow the same field-table rules as schema pages.
TYPE_PAGES = {f"../types/{p.stem}": p for p in sorted((V / "types").glob("*.md")) if p.stem != "types"}
schema_pages.update(TYPE_PAGES)
for stem in RECORDS + FOUNDATION + list(TYPE_PAGES):
    if stem not in schema_pages:
        continue
    s = rd(schema_pages[stem])
    sec = fields_section(s)
    if sec is None:
        problems.append(f"schemas/{stem}.md: no '## Fields' section")
        continue
    tables = re.findall(r"(^\|.*\|\n\|[-| ]+\|\n(?:^\|.*\|\n?)+)", sec, flags=re.M)
    if not any(t.startswith("| Field ") for t in tables):
        problems.append(f"schemas/{stem}.md: no field table in Fields")
    for tb in tables:
        lines = tb.strip("\n").split("\n")
        if not lines[0].startswith("| Field "):
            continue  # a reference table, not a field table
        if lines[0].strip() != HEADER:
            problems.append(f"schemas/{stem}.md: field table header must be: {HEADER}")
            continue
        for row in lines[2:]:
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", row.strip())[1:-1]]
            if len(cells) != 6:
                problems.append(f"schemas/{stem}.md: row needs 6 cells: {row[:60]}")
                continue
            f, ty, req, m1, unlocks, desc = cells
            if not type_ok(ty):
                problems.append(f"schemas/{stem}.md: {f}: type not in grammar: {ty}")
            if req not in ("req", "opt"):
                problems.append(f"schemas/{stem}.md: {f}: Req must be req or opt")
            if m1 not in M1:
                problems.append(f"schemas/{stem}.md: {f}: M1 must be checked or unchecked")
            elif (m1 == "unchecked") != bool(unlocks):
                problems.append(f"schemas/{stem}.md: {f}: Unlocks is filled exactly when unchecked")
            if len(desc) < 15:
                problems.append(f"schemas/{stem}.md: {f}: description too short")
            # INV-12 suffixes for ids, hashes, times and Ref fields
            leaf = f.strip("`").split(".")[-1].split("[]")[-1]
            base = ty.strip().strip("`").strip().rstrip("?")
            if base in ("sha256", "list<sha256>") and not (leaf == "sha256" or leaf.endswith(("_sha256", "_hash", "_hashes"))):
                problems.append(f"schemas/{stem}.md: {f}: a hash must end _sha256, _hash or _hashes (INV-12)")
            if base == "id" and not (leaf == "id" or leaf.endswith(("_id", "_ref"))):
                problems.append(f"schemas/{stem}.md: {f}: an id must end _id (INV-12)")
            if base == "time" and not (leaf in ("at", "timestamp") or leaf.endswith("_at")):
                problems.append(f"schemas/{stem}.md: {f}: a time must be timestamp or end _at (INV-12)")
            if re.fullmatch(r"Ref\(\w+\)", base) and not leaf.endswith("_ref"):
                problems.append(f"schemas/{stem}.md: {f}: a Ref must end _ref (INV-12)")

# INV-13: reason codes are UPPER_SNAKE; enum wire values retain their source case.
for row in re.findall(r"^\| `reason_code` \|(.*)$", rd(SCHEMAS / "policy.md"), flags=re.M):
    for code in re.findall(r"`([^`]+)`", row.split("|")[0]):
        if not re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*", code):
            problems.append(f"schemas/policy.md: reason code not UPPER_SNAKE: {code}")

index = rd(SCHEMAS / "schemas.md")
for stem in RECORDS + FOUNDATION:
    link = "../capsule/fields.md" if stem == "declaration" else f"{stem}.md"
    if f"]({link})" not in index:
        problems.append(f"schemas/schemas.md: records table does not list {stem}.md")

# ---------------- lint: links and diagrams ----------------
pages = [p for p in V.rglob("*.md") if ".obsidian" not in p.parts and p.relative_to(V).as_posix() not in SKIP]
stems = {p.stem for p in V.rglob("*.md")}
for p in pages:
    s = rd(p)
    body = re.sub(r"````.*?````", "", s, flags=re.S)
    rel = p.relative_to(V)
    for l in re.findall(r"\]\(<?([^)>#\s]+?\.(?:md|pptx))>?(?:#[^)]*)?\)", body):
        if re.match(r"[a-z]+://", l):
            continue
        target = (p.parent / l).resolve()
        if not target.exists():
            problems.append(f"{rel}: broken link {l}")
    for w in re.findall(r"\[\[([^\]|#]+)", re.sub(r"```.*?```", "", body, flags=re.S)):
        if w not in stems and w != "name":
            problems.append(f"{rel}: broken [[{w}]]")
    for blk in re.findall(r"```mermaid\n(.*?)```", body, flags=re.S):
        if re.search(r"[^\x00-\x7f]", blk):
            problems.append(f"{rel}: non-ASCII character in a Mermaid block")
        for lab in re.findall(r"\[([^\]]*)\]", blk) + re.findall(r"\|([^|]*)\|", blk):
            if ";" in lab:
                problems.append(f"{rel}: ';' inside a Mermaid label: {lab[:40]}")

# ---------------- extended checks (2026-10-01): types, retired ids, front matter, graph, size ----------------
from extended import run_extended  # noqa: E402
warnings = run_extended(V, problems, CHECK, rd, wr, fields_section, type_ok, SKIP)
for w in warnings:
    print("warning:", w)

if problems:
    print("\n".join(sorted(set(problems))))
    print(f"{len(set(problems))} problem(s)")
    sys.exit(1)
print("ok")
