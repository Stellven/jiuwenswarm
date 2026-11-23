#!/usr/bin/env python3
"""System Ontology checker (0.3.0). Every rule is deterministic; no LLM is called.

Usage (from any directory):
  python so_check.py validate                       # structural validation of every description file
  python so_check.py check <spec id>                # check one engine spec: report its problems and match mechanisms
  python so_check.py match --model <id> --hardware <id> [--budget pool=12GB ...]
                                                    # check the preconditions (because) of every mechanism one by one against one set of givens
The --root option names the workspace root (which holds ontology/ and the description files); by default it is the directory above the one this file is in.
"""
from __future__ import annotations

import argparse
import collections
import fnmatch
import pathlib
import re
import sys
from dataclasses import dataclass

import jsonschema
import yaml

UNIT_BYTES = {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12,
              "KiB": 2**10, "MiB": 2**20, "GiB": 2**30, "TiB": 2**40}
BINARY_OF = {"KB": "KiB", "MB": "MiB", "GB": "GiB", "TB": "TiB"}
KIND_TITLE = {"gap": "gap", "unbound_term": "unbound_term", "value_conflict": "value_conflict",
              "infeasible": "infeasible", "incompatible": "incompatible", "low_confidence": "low_confidence",
              "untested": "untested", "schema": "schema", "risk": "risk"}


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML silently keeps the later one when a key is written twice in one object; here that is an error."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"the key {key!r} is written twice", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep)


@dataclass
class Issue:
    kind: str
    blocking: bool
    about: str
    message: str
    owner: str = ""


# ---------------------------------------------------------------- workspace

class Workspace:
    def __init__(self, root: pathlib.Path):
        self.root = root
        onto = root / "ontology"
        self.schema = yaml.safe_load((onto / "schema.yaml").read_text(encoding="utf-8"))
        self.quantities = yaml.safe_load((onto / "quantities.yaml").read_text(encoding="utf-8"))["quantities"]
        self.rules = yaml.safe_load((onto / "rules.yaml").read_text(encoding="utf-8"))
        self.predicates = yaml.safe_load((onto / "predicates.yaml").read_text(encoding="utf-8"))["predicates"]
        self.objects: dict[str, dict] = {}
        self.files: dict[str, pathlib.Path] = {}
        self.load_errors: list[Issue] = []
        for path in sorted(root.rglob("*.yaml"), key=lambda p: p.relative_to(root).as_posix()):   # the same order on every system
            rel = path.relative_to(root).parts
            if onto in path.parents or "validation" in rel:      # records of checks, not descriptions
                continue
            if "_parts" in rel or path.name.startswith("_"):     # inputs of tools (parts to assemble, derivation lists)
                continue
            try:                                             # one file may hold several descriptions separated by ---
                docs = list(yaml.load_all(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader))
            except yaml.YAMLError as e:
                mark = getattr(e, "problem_mark", None)
                where = f"at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
                self.load_errors.append(Issue("schema", True, path.relative_to(root).as_posix(),
                                              f"YAML could not be parsed {where}: {getattr(e, 'problem', e)}. "
                                              f"Text that contains a colon or a comma needs quotes; tools/so_quote.py adds them"))
                continue
            for doc in docs:
                if not isinstance(doc, dict) or ("kind" not in doc and "id" not in doc):
                    continue                                 # not a description file (a derivation list, a node table and the like)
                if "kind" not in doc or "id" not in doc:     # half written: most likely a misspelled key; must not be skipped silently
                    self.load_errors.append(Issue("schema", True, path.relative_to(root).as_posix(),
                                                  f"one description has only {'id' if 'id' in doc else 'kind'} and no"
                                                  f" {'kind' if 'id' in doc else 'id'}; it was not read in"))
                    continue
                if doc["id"] in self.objects:
                    self.load_errors.append(Issue("schema", True, doc["id"],
                                                  f"duplicate id: {path.name} and {self.files[doc['id']].name}"))
                    continue
                self.objects[doc["id"]] = doc
                self.files[doc["id"]] = path

    def of_kind(self, kind: str) -> list[dict]:
        return [o for o in self.objects.values() if o["kind"] == kind]

    def validate(self, obj: dict) -> list[Issue]:
        sub = self.schema["kinds"].get(obj["kind"])
        if sub is None:
            return [Issue("schema", True, obj["id"], f"unknown kind: {obj['kind']}")]
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                  "defs": self.schema["defs"], **sub}
        out = []
        for err in jsonschema.Draft202012Validator(schema).iter_errors(obj):
            for leaf in leaf_errors(err):
                where = ".".join(str(p) for p in leaf.absolute_path) or "(top level)"
                out.append(Issue("schema", True, f"{obj['id']} · {where}", leaf.message))
        return out

    def gap_policy(self, path: str) -> tuple[bool, str]:
        for rule in self.rules["gap_policy"]:
            if fnmatch.fnmatchcase(path, rule["path"]):
                return rule["blocking"], rule["owner"]
        return True, ""


def leaf_errors(err):
    """When a value has several allowed forms (anyOf) and fits none, take the specific error from the branch that got deepest."""
    if not err.context:
        return [err]
    deepest = max(len(e.absolute_path) for e in err.context)
    picked = [e for e in err.context if len(e.absolute_path) == deepest]
    if deepest == len(err.absolute_path):        # every branch fails at the same depth: prefer the error in the object form
        obj = [e for e in picked if e.validator not in ("enum", "type", "const")]
        picked = obj or [err]
        if picked == [err]:
            return [err]
    out = []
    for e in picked:
        out += leaf_errors(e)
    return out


# ---------------------------------------------------------------- values and units

def raw(cell):
    return cell["value"] if isinstance(cell, dict) and "value" in cell else cell


def is_unset(v) -> bool:
    return v is None or raw(v) == "UNSET"


def to_bytes(cell) -> float | None:
    """Convert a value with a unit to bytes. Decimal is used when unit_basis is not declared."""
    if not isinstance(cell, dict) or is_unset(cell) or "unit" not in cell:
        return None
    unit = cell["unit"]
    if cell.get("unit_basis") == "binary":
        unit = BINARY_OF.get(unit, unit)
    if unit not in UNIT_BYTES or not isinstance(cell["value"], (int, float)):
        return None
    return cell["value"] * UNIT_BYTES[unit]


def to_bytes_or_zero(cell) -> float:
    return to_bytes(cell) or 0.0


def fmt_bytes(n: float) -> str:
    return f"{n / 1e9:.4g} GB"


def unit_ambiguous(ws: Workspace, cell) -> bool:
    return (isinstance(cell, dict) and cell.get("unit") in ws.rules["ambiguous_byte_units"]
            and cell.get("unit_basis") in (None, "UNSET"))


def walk(node, path=""):
    """Walk a nested structure and yield (path, node). A list element that has an id uses the id as its path segment."""
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            seg = str(v.get("id", i)) if isinstance(v, dict) else str(i)
            yield from walk(v, f"{path}.{seg}" if path else seg)


# ---------------------------------------------------------------- hardware queries

class Hardware:
    def __init__(self, doc: dict, allocatable: dict[str, float] | None = None):
        self.doc = doc
        self.units = {u["id"]: u for u in doc["compute_units"]}
        self.pools = {p["id"]: p for p in doc["memory_pools"]}
        self.paths = {p["id"]: p for p in doc["access_paths"]}
        self.allocatable = allocatable or {}

    def capacity(self, pool: str) -> float | None:
        """Usable limit: the allocatable capacity the environment gives comes first, then what the hardware itself reports, then the nominal capacity."""
        if pool in self.allocatable:
            return self.allocatable[pool]
        p = self.pools[pool]
        return to_bytes(p.get("allocatable")) or to_bytes(p["capacity_nominal"])

    def nominal(self, pool: str) -> float | None:
        return to_bytes(self.pools[pool]["capacity_nominal"])

    def has_allocatable(self, pool: str) -> bool:
        return pool in self.allocatable or to_bytes(self.pools[pool].get("allocatable")) is not None

    def direct_pools(self, unit: str) -> set[str]:
        return {p["pool"] for p in self.paths.values() if p["kind"] == "direct" and p.get("unit") == unit}

    def readable_pools(self, unit: str) -> set[str]:
        return {p["pool"] for p in self.paths.values()
                if p["kind"] in ("direct", "direct_read") and p.get("unit") == unit}

    def users(self, pool: str) -> list[str]:
        return sorted(u for u in self.units if pool in self.direct_pools(u))

    def reaches(self, src: str, dst: str) -> bool:
        return any(p["kind"] in ("transfer", "page_in") and p.get("origin") == src and p.get("destination") == dst
                   for p in self.paths.values())

    def describe_pools(self) -> str:
        def one(pid, p):
            users = self.users(pid)
            return f"{pid} ({p['kind']}, " + (f"used directly by {', '.join(users)})" if users else "no compute unit uses it directly)")
        return "; ".join(one(pid, p) for pid, p in self.pools.items())


# ---------------------------------------------------------------- predicates for the preconditions of mechanisms

def p_sparse_selection(model, hw, budgets, args, ctx):
    if not model["operations"]:
        return "unknown", "the model description has no operations"
    best = None
    for op in model["operations"]:
        if op["kind"] != "selection" or "operation" not in op["selects"]:
            continue
        ratio = op["selects"]["pick"] / op["selects"]["out_of"]
        if best is None or ratio < best[1]:
            best = (op, ratio)
    if best is None:
        return "fails", "the model has no selection operation"
    op, ratio = best
    sel = op["selects"]
    if ratio > args.get("max_pick_ratio", 0.5):
        return "fails", f"{op['id']} selects {sel['pick']}/{sel['out_of']} each time, which is not sparse"
    ops = {o["id"]: o for o in model["operations"]}
    data = {d["id"]: d for d in model["data"]}
    target = ops.get(sel["operation"])
    if target is None:
        return "unknown", f"the selection's target {sel['operation']} is not in the model description"
    ctx["selection"], ctx["target"] = op, target
    ctx["data"] = [data[d] for d in target.get("reads", []) if d in data and data[d]["kind"] == "weight"]
    return "holds", f"{op['id']} selects {sel['pick']} of {sel['out_of']} {sel['operation']} per {sel['per']}"


def p_selected_data_partitioned(model, hw, budgets, args, ctx):
    if not ctx.get("data"):
        return "unknown", "could not determine which weights the selected operation reads"
    flat = [d["id"] for d in ctx["data"] if not d.get("partitioned_by")]
    if flat:
        return "fails", f"{', '.join(flat)} does not declare partitioned_by"
    return "holds", "; ".join(f"{d['id']} is partitioned by {', '.join(d['partitioned_by'])}" for d in ctx["data"])


def _selected_size(ctx):
    sizes = [to_bytes(d.get("size")) for d in ctx.get("data", [])]
    return None if not sizes or None in sizes else sum(sizes)


def p_selected_data_exceeds_direct_pool(model, hw, budgets, args, ctx):
    size = _selected_size(ctx)
    if size is None:
        return "unknown", "the size of the selected operation's weights is unknown"
    pools = sorted({p for u in hw.units for p in hw.direct_pools(u)}, key=lambda p: hw.capacity(p) or 0)
    verdicts = []
    for pool in pools:
        limits = budgets.get(pool) or [hw.capacity(pool)]
        if None in limits:
            continue
        over = [lim for lim in limits if size > lim]
        if over and len(over) == len(limits):
            ctx["fast_pool"] = pool
            return "holds", f"{fmt_bytes(size)} exceeds the limit of {pool}: {', '.join(fmt_bytes(l) for l in limits)}"
        if over:
            ctx.setdefault("fast_pool", pool)
            verdicts.append(f"for {pool}: holds when the budget is {', '.join(fmt_bytes(l) for l in over)}, "
                            f"fails when it is {', '.join(fmt_bytes(l) for l in limits if l not in over)}")
    if verdicts:
        return "depends", f"weights {fmt_bytes(size)}. " + "; ".join(verdicts)
    return "fails", f"the weights, {fmt_bytes(size)}, fit in every memory pool used directly (" + \
        ", ".join(f"{p} {fmt_bytes(hw.capacity(p))}" for p in pools if hw.capacity(p)) + ")"


def p_slower_pool_can_hold(model, hw, budgets, args, ctx):
    size, fast = _selected_size(ctx), ctx.get("fast_pool")
    if size is None or fast is None:
        return "unknown", "the conditions before this one did not determine the size of the weights or the fast memory pool"
    found = []
    for pool in hw.pools:
        cap = hw.capacity(pool)
        if pool == fast or cap is None or cap < size:
            continue
        if hw.reaches(pool, fast):
            found.append((pool, f"by transfer to {fast}"))
        elif any(pool in hw.readable_pools(u) for u in hw.units):
            found.append((pool, "a compute unit can read it directly"))
    if not found:
        return "fails", f"no memory pool other than {fast} is large enough and reachable"
    ctx["slow_pool"] = [p for p, _ in found]
    return "holds", f"fast pool {fast}; slow pool " + ", ".join(f"{p} ({how})" for p, how in found)


def p_units_with_distinct_direct_pools(model, hw, budgets, args, ctx):
    sets = {u: hw.direct_pools(u) for u in hw.units}
    desc = "; ".join(f"{u} uses {', '.join(sorted(s)) or 'none'} directly" for u, s in sets.items())
    return ("holds" if len({frozenset(s) for s in sets.values()}) > 1 else "fails"), desc


def p_measured_property(model, hw, budgets, args, ctx):
    prop = args["property"]
    for st in model.get("statements", []):
        if st["property"] == prop and st["status"] == "measured":
            return "holds", f"{prop} = {st['value']} (measured, source {st.get('source', 'not stated')})"
    best = None
    for pr in ctx.get("_profiles", []):
        if pr["of"] == model["id"] and pr["property"] == prop:
            if best is None or STATUS_RANK.index(pr["status"]) > STATUS_RANK.index(best["status"]):
                best = pr
    if best is not None and best["status"] == "measured":
        return "holds", f"{prop} has a measured profile, {best['id']}"
    if best is not None:
        ctx["_weak"] = True
        return "holds", f"{prop} has only a {STATUS_TITLE.get(best['status'], best['status'])} profile, {best['id']}, not a measured one"
    return "unknown", f"no measured statement of {prop}; an experiment is needed"


def p_has_draft_operation(model, hw, budgets, args, ctx):
    if not model["operations"]:
        return "unknown", "the model description has no operations"
    drafts = [o for o in model["operations"] if o["kind"] == "draft"]
    if not drafts:
        return "fails", "the model has no draft operation"
    ctx["draft"] = drafts[0]
    d = drafts[0].get("drafts", {})
    return "holds", f"{drafts[0]['id']}" + (f", proposes up to {d['up_to']}" if "up_to" in d else "")


PREDICATES = {f.__name__[2:]: f for f in (
    p_sparse_selection, p_selected_data_partitioned, p_selected_data_exceeds_direct_pool,
    p_slower_pool_can_hold, p_units_with_distinct_direct_pools, p_measured_property,
    p_has_draft_operation)}

STATUS_RANK = ["assumed", "simulated", "derived", "proposed", "reported", "vendor_stated", "measured"]
STATUS_TITLE = {"assumed": "assumed", "simulated": "simulated", "derived": "derived", "proposed": "proposed", "reported": "reported",
                "vendor_stated": "vendor_stated", "measured": "measured"}
OUTCOME = {"holds": "holds", "fails": "fails", "depends": "depends on the requirement", "unknown": "unknown"}
VERDICT = {"not_applicable": "does not apply", "undetermined": "cannot be judged, the given is not enough", "conditional": "conditional candidate",
           "needs_evidence": "candidate, evidence needed", "candidate": "candidate"}


def match_hypothesis(ws: Workspace, hyp: dict, model: dict, hw: Hardware, budgets: dict):
    ctx, rows, notes = {"_profiles": ws.of_kind("workload_profile")}, [], []
    for cond in hyp["because"]:
        fn = PREDICATES.get(cond["predicate"])
        if fn is None or cond["predicate"] not in ws.predicates:
            rows.append((cond, "unknown", f"the predicate {cond['predicate']} is not registered in the ontology"))
            continue
        outcome, detail = fn(model, hw, budgets, cond.get("args", {}), ctx)
        rows.append((cond, outcome, detail))
        if outcome == "fails" and cond.get("essential", True) is False:
            notes.append(cond.get("effect_if_fails", ""))
    hard = [o for c, o, _ in rows if c.get("essential", True)]
    if "fails" in hard:
        verdict = "not_applicable"
    elif "holds" not in hard and "depends" not in hard:
        verdict = "undetermined"
    elif "depends" in hard:
        verdict = "conditional"
    elif "unknown" in hard:
        verdict = "needs_evidence"
    else:
        verdict = "candidate"
    return verdict, rows, notes, ctx


def print_match(ws, hyp, model, hw, budgets):
    verdict, rows, notes, ctx = match_hypothesis(ws, hyp, model, hw, budgets)
    print(f"\n  mechanism {hyp['id']} → {VERDICT[verdict]}")
    for cond, outcome, detail in rows:
        opt = "" if cond.get("essential", True) else " (not essential)"
        print(f"    [{OUTCOME[outcome]}] {cond['text']}{opt}")
        print(f"        {detail}")
    if verdict != "not_applicable":
        for n in notes:
            print(f"    effect_if_fails: {n}")
    return verdict, rows


# ---------------------------------------------------------------- spec checks

REQUIREMENT_COMMON = {"id", "quantity", "kind", "text", "status", "source", "candidates", "value", "unit", "threshold", "note"}


def requirement_fields(req: dict) -> dict:
    """The fields a requirement actually gives. A field written in candidates also counts as given."""
    fields = dict(req)
    for cand in req.get("candidates", []):
        for k, v in cand.items():
            fields.setdefault(k, v)
    return fields


def check_spec(ws: Workspace, spec: dict) -> tuple[list[Issue], Hardware | None, dict | None, dict]:
    issues: list[Issue] = list(ws.validate(spec))
    sid = spec["id"]

    # 1. resolve the givens
    given, resolved = spec["given"], {}
    for role in ("model", "hardware", "environment"):
        ref = given[role]
        if is_unset(ref):
            continue
        obj = ws.objects.get(ref)
        if obj is None or obj["kind"] != role:
            issues.append(Issue("unbound_term", True, f"given.{role}", f"no {role} description found: {ref}"))
            continue
        issues += ws.validate(obj)
        resolved[role] = obj
    model = resolved.get("model")
    allocatable = {a["pool"]: to_bytes(a) for a in resolved.get("environment", {}).get("allocatable", [])}
    hw = Hardware(resolved["hardware"], allocatable) if "hardware" in resolved else None

    # 2. how each quantity is measured: add the fields the definition of the quantity requires; a missing one is recorded as UNSET
    reqs = spec["contract"]["requirements"]
    for req in reqs:
        q = req.get("quantity")
        if q is None:
            continue
        if q not in ws.quantities:
            issues.append(Issue("unbound_term", True, f"contract.requirements.{req['id']}",
                                f"the quantity {q} is not registered in the ontology"))
            continue
        have = requirement_fields(req)
        measured_only = req["kind"] == "report"
        known = REQUIREMENT_COMMON | set(ws.quantities[q]["required_fields"])
        for f in sorted(set(have) - known):
            issues.append(Issue("schema", True, f"contract.requirements.{req['id']}.{f}",
                                f"the field {f} is neither a common field nor a field registered for the quantity {q}", "the author of the spec"))
        for f in ws.quantities[q]["required_fields"]:
            if f in ("value", "unit", "threshold") and measured_only:
                continue
            if f not in have:
                req[f] = "UNSET"

    # 3. every UNSET is a gap
    for path, node in walk(spec):
        if node == "UNSET" or (isinstance(node, dict) and node.get("value") == "UNSET"):
            blocking, owner = ws.gap_policy(path)
            note = ""
            m = re.fullmatch(r"contract\.requirements\.([^.]+)\.([^.]+)", path)
            if m:
                req = next(r for r in reqs if r["id"] == m.group(1))
                note = ws.quantities.get(req.get("quantity"), {}).get("field_notes", {}).get(m.group(2), "")
            issues.append(Issue("gap", blocking, path, note or "not given", owner))

    # 4. several candidate values side by side
    for path, node in walk(spec):
        if isinstance(node, dict) and len(node.get("candidates", [])) > 1:
            vals = ", ".join(f"{c.get('value')} {c.get('unit', '')}".strip() for c in node["candidates"])
            issues.append(Issue("value_conflict", True, path,
                                f"one requirement has {len(node['candidates'])} candidates ({vals}); none is chosen yet", "the project"))

    # 5. memory requirements: bound to a memory pool, unit basis, feasibility
    budgets: dict[str, list[float]] = {}
    for req in reqs:
        q = ws.quantities.get(req.get("quantity"), {})
        if q.get("dimension") != "bytes":
            continue
        for i, cand in enumerate(req.get("candidates") or [req]):
            about = f"contract.requirements.{req['id']}" + (f".candidates.{i}" if "candidates" in req else "")
            pool = cand.get("pool", req.get("pool"))
            if hw is None or is_unset(pool):
                continue
            if pool not in hw.pools:
                issues.append(Issue("unbound_term", True, about,
                                    f"the requirement refers to the memory pool '{pool}', but {hw.doc['id']} has no such memory pool. "
                                    f"Its memory pools: {hw.describe_pools()}", "the project"))
                continue
            if q.get("role") != "budget":
                continue
            cell = {**cand, "unit_basis": cand.get("unit_basis", req.get("unit_basis"))}
            size = to_bytes(cell)
            if size is None:
                continue
            budgets.setdefault(pool, []).append(size)
            nominal, cap = hw.nominal(pool), hw.capacity(pool)
            if hw.has_allocatable(pool) and size > cap:
                issues.append(Issue("infeasible", True, about,
                                    f"the budget {fmt_bytes(size)} exceeds the allocatable capacity of {pool}, {fmt_bytes(cap)}", "the project"))
            elif nominal is not None and size > nominal:
                issues.append(Issue("infeasible", True, about,
                                    f"the budget {fmt_bytes(size)} exceeds the nominal capacity of {pool}, {fmt_bytes(nominal)}", "the project"))
            elif nominal is not None and size == nominal:
                # a memory pool shared with the operating system cannot all go to the engine; device memory it has to itself merely has no headroom
                shared = hw.pools[pool]["kind"] in ws.rules["os_shared_pool_kinds"]
                issues.append(Issue("infeasible" if shared else "gap", shared, about,
                                    f"the budget {fmt_bytes(size)} equals the nominal capacity of {pool}; " +
                                    ("nothing is left for the system and other processes; this number may be a fact about the hardware and not a budget" if shared
                                     else "nothing is left over; a measured allocatable capacity is needed to confirm it"), "the project" if shared else "one experiment can supply it"))

    # 6. completeness and status of the givens themselves
    if model is not None and not model["operations"]:
        b, owner = ws.gap_policy("given.model.operations")
        issues.append(Issue("gap", b, "given.model.operations",
                            f"{model['id']} describes no operations and no data, so the conditions of no mechanism can be checked", owner))
    for role, obj in resolved.items():
        cells = [(p, n) for p, n in walk(obj) if isinstance(n, dict) and "value" in n]
        assumed = [p for p, n in cells if n.get("status", obj.get("default_status")) == "assumed"]
        if obj.get("default_status") == "assumed" or assumed:
            issues.append(Issue("low_confidence", False, f"given.{role}",
                                f"{obj['id']} contains assumed values" + (f" ({len(assumed)} of them)" if assumed else " (the whole description is assumed by default)")
                                + "; conclusions drawn from them cannot be taken as facts", f"the owner of the {role} source"))
        for p, n in cells:
            if unit_ambiguous(ws, n):
                issues.append(Issue("gap", False, f"given.{role}.{p}",
                                    f"{n['value']} {n['unit']} does not say whether it is decimal or binary; the two differ by about "
                                    f"{(UNIT_BYTES[BINARY_OF[n['unit']]] / UNIT_BYTES[n['unit']] - 1) * 100:.0f}%",
                                    f"the owner of the {role} source"))
        issues += statement_conflicts(ws, obj, role)

    if spec["spec_level"] == "resolved" and hw is not None and model is not None:
        issues += check_resolved(ws, spec, model, hw, budgets)
    return issues, hw, model, budgets


def statement_conflicts(ws: Workspace, obj: dict, role: str) -> list[Issue]:
    """Incompatible values for the same property of the same object under the same conditions, within the highest status present."""
    rank = ws.rules["status_rank"]
    table: dict[tuple, list[dict]] = {}
    for st in obj.get("statements", []):
        key = (st["subject"], st["property"], yaml.safe_dump(st.get("conditions", {}), sort_keys=True))
        table.setdefault(key, []).append(st)
    for pool in obj.get("memory_pools", []):
        cell = pool["capacity_nominal"]
        if isinstance(cell, dict):
            key = (pool["id"], "capacity_nominal", yaml.safe_dump({}, sort_keys=True))
            table.setdefault(key, []).append({**cell, "subject": pool["id"], "property": "capacity_nominal"})
    out = []
    for (subject, prop, _), sts in table.items():
        top = max(rank.index(s["status"]) for s in sts if s.get("status") in rank)
        peers = [s for s in sts if s.get("status") in rank and rank.index(s["status"]) == top]
        values = [to_bytes(s) if to_bytes(s) is not None else s["value"] for s in peers]
        nums = [v for v in values if isinstance(v, (int, float))]
        differ = (len(set(map(str, values))) > 1 if len(nums) != len(values)
                  else max(nums) - min(nums) > ws.rules["value_tolerance"] * max(abs(max(nums)), 1e-12))
        if len(peers) > 1 and differ:
            shown = ", ".join(f"{s['value']} {s.get('unit', '')} ({s.get('source', 'source not stated')})" for s in peers)
            out.append(Issue("value_conflict", True, f"given.{role}.{subject}.{prop}",
                             f"statements of the same status, {peers[0]['status']}, give different values: {shown}", f"the owner of the {role} source"))
    return out


def check_resolved(ws: Workspace, spec: dict, model: dict, hw: Hardware, budgets: dict) -> list[Issue]:
    """Resolved spec: whether components, policies and binding connect, whether everything fits, and whether it can be traced."""
    out: list[Issue] = []
    ops = {o["id"]: o for o in model["operations"]}
    data = {d["id"]: d for d in model["data"]}

    def section(aspect, key):
        a = spec.get(aspect)
        return a.get(key, []) if isinstance(a, dict) else []

    # the engine's own state can also take up a memory pool; its size is not in the model description but comes from the capacity of the residency item or from the policy budget
    for st in section("state", "states"):
        data.setdefault(st["id"], {"id": st["id"], "kind": "engine_state"})

    derived_budgets: dict[str, float] = {}
    spec["_derived_budgets"] = derived_budgets
    impls = {i["id"]: i for i in section("binding", "implementations")}
    policies = {p["id"]: p for p in section("policy", "policies")}
    components = section("composition", "components")

    # every stage is implemented by a component
    implemented = {s for c in components for s in c.get("implements", [])}
    for stage in section("execution", "stages"):
        if stage["id"] not in implemented:
            out.append(Issue("gap", True, f"execution.stages.{stage['id']}", "no component implements this stage", "the factory"))

    # implementations: the operation exists, the compute unit exists, and it can read the declared memory pool
    for i in impls.values():
        about = f"binding.implementations.{i['id']}"
        if i["of"] not in ops:
            out.append(Issue("unbound_term", True, about, f"the operation {i['of']} is not in the model description", "the factory"))
        if i["runs_on"] not in hw.units:
            out.append(Issue("unbound_term", True, about, f"the compute unit {i['runs_on']} is not in the hardware description", "the factory"))
            continue
        for pool in i.get("reads_from", []):
            if pool not in hw.readable_pools(i["runs_on"]):
                out.append(Issue("incompatible", True, about,
                                 f"{i['runs_on']} has no path to read {pool}", "the factory"))

    # residency: it fits. For the kinds of allocation see the schema; a policy budget may be written as derived from the allocatable capacity at startup
    residency = section("binding", "residency")
    hard: dict[str, float] = {}
    soft: dict[str, float] = {}
    backing: dict[str, set] = {}
    deferred = []
    for r in residency:
        about = f"binding.residency.{r['data']}@{r['pool']}"
        if r["data"] not in data or r["pool"] not in hw.pools:
            out.append(Issue("unbound_term", True, about, "the data or the memory pool is not in the given descriptions", "the factory"))
            continue
        pool, alloc = r["pool"], r.get("allocation", "pinned")
        if "by_policy" in r:
            deferred.append((r, about))
            continue
        if alloc == "transient":
            cap = to_bytes(r.get("capacity"))
            if cap is None:
                out.append(Issue("gap", True, about, "the transient staging area declares no capacity", "the factory"))
            else:
                hard[pool] = hard.get(pool, 0) + cap
            continue
        if alloc == "elastic":
            lo, hi = to_bytes(r.get("floor")), to_bytes(r.get("cap"))
            if lo is None or hi is None or hi < lo:
                out.append(Issue("gap", True, about, "an elastic allocation must declare floor and cap, with cap not below floor", "the factory"))
            else:
                hard[pool] = hard.get(pool, 0) + lo
                soft[pool] = soft.get(pool, 0) + (hi - lo)
            continue
        size = to_bytes(data[r["data"]].get("size"))
        if size is None:
            size = to_bytes(r.get("capacity"))
        if alloc in ("reclaimable_mapping", "read_through"):
            back = r.get("backed_by")
            if back not in hw.pools:
                out.append(Issue("gap", True, about, "it does not declare which memory pool the data comes from (backed_by)", "the factory"))
            elif not hw.reaches(back, pool):
                out.append(Issue("incompatible", True, about, f"there is no path from {back} to {pool}", "the factory"))
            elif size is None:
                out.append(Issue("gap", True, about, f"the size of {r['data']} is unknown, so whether {back} can hold it cannot be judged", "the owner of the model source"))
            elif (hw.capacity(back) or 0) < size:
                out.append(Issue("infeasible", True, about, f"{r['data']} ({fmt_bytes(size)}) exceeds the capacity of {back}", "the factory"))
            elif alloc == "reclaimable_mapping":
                backing.setdefault(pool, set()).add(back)
                soft[pool] = soft.get(pool, 0) + size
            continue
        if size is None:
            engine_own = data[r["data"]].get("kind") in ("engine_state", "model_state")
            out.append(Issue("gap", True, about,
                             f"the size of {r['data']} is unknown, so whether it fits cannot be judged" + ("; it depends on the configuration: give a capacity on the residency entry" if engine_own else ""),
                             "the author of the spec" if engine_own else "the owner of the model source"))
            continue
        hard[pool] = hard.get(pool, 0) + size
    for r, about in deferred:
        pool = r["pool"]
        pol = policies.get(r["by_policy"])
        if pol is None:
            out.append(Issue("unbound_term", True, about, f"the policy {r['by_policy']} does not exist", "the factory"))
            continue
        budget = pol.get("budget")
        derive = budget.get("derive") if isinstance(budget, dict) else None
        if derive:
            # base of the derivation: the memory budget when there is one (the smallest of several candidates), otherwise the allocatable capacity
            base = min(budgets[pool]) if budgets.get(pool) else hw.capacity(pool)
            if base is None or not (budgets.get(pool) or hw.has_allocatable(pool)):
                out.append(Issue("gap", True, about,
                                 f"the budget of the policy {r['by_policy']} is derived at startup from the allocatable capacity of {pool}, but the environment does not give this value", "one experiment can supply it"))
                continue
            amount = base * derive.get("fraction", 1.0) - hard.get(pool, 0) - to_bytes_or_zero(derive.get("reserve"))
            if amount <= 0:
                out.append(Issue("infeasible", True, about,
                                 f"derived by the formula, the policy {r['by_policy']} has no budget left in {pool}"
                                 f" ({fmt_bytes(base)} × {derive.get('fraction', 1.0)} minus the pinned allocations {fmt_bytes(hard.get(pool, 0))})", "the factory"))
                continue
            derived_budgets[r["by_policy"]] = amount
            hard[pool] = hard.get(pool, 0) + amount
        elif to_bytes(budget) is None:
            out.append(Issue("gap", True, about, f"the policy {r['by_policy']} declares no budget it may use", "the factory"))
        else:
            hard[pool] = hard.get(pool, 0) + to_bytes(budget)
    for pool in sorted(set(hard) | set(soft)):
        limit = min(budgets[pool]) if budgets.get(pool) else hw.capacity(pool)
        if limit is None:
            continue
        h, m = hard.get(pool, 0), soft.get(pool, 0)
        if h > limit:
            out.append(Issue("infeasible", True, f"binding.residency@{pool}",
                             f"the data pinned in {pool} adds up to {fmt_bytes(h)}, which exceeds the limit {fmt_bytes(limit)}", "the factory"))
        elif h + m > limit:
            out.append(Issue("risk", False, f"binding.residency@{pool}",
                             f"pinned allocations {fmt_bytes(h)} plus file mappings {fmt_bytes(m)} add up to {fmt_bytes(h + m)}, which exceeds the limit "
                             f"{fmt_bytes(limit)}; file pages will be reclaimed and reads fall back to {', '.join(sorted(backing.get(pool, [])))}, "
                             f"so the speed may drop sharply", "an experiment"))

    # assignment: judged in order; the implementation referred to exists and can read the data it depends on; every operation has a fallback; omitting needs permission
    transient_at = {(r["data"], r["pool"]) for r in residency if r.get("allocation") == "transient"}
    stage_ids = {st["id"] for st in section("execution", "stages")}
    assignments: dict[str, list[dict]] = {}
    for a in section("binding", "assignment"):
        about = f"binding.assignment.{a['operation']}"
        if a["operation"] not in ops:
            out.append(Issue("unbound_term", True, about, "the operation is not in the model description", "the factory"))
            continue
        assignments.setdefault(a["operation"], []).append(a)
        if "stage" in a and a["stage"] not in stage_ids:
            out.append(Issue("unbound_term", True, about, f"the stage {a['stage']} is not in the execution structure", "the factory"))
        when = a.get("when", {})
        if a.get("omit"):
            hyp = ws.objects.get(a.get("because", ""))
            if hyp is None or a["because"] not in spec.get("mechanisms", []) or hyp.get("equivalence") != "approximate":
                out.append(Issue("incompatible", True, about,
                                 "omitting an operation changes the output; because must refer to an adopted mechanism whose equivalence is approximate", "the factory"))
            continue
        impl = impls.get(a.get("use"))
        if impl is None:
            out.append(Issue("unbound_term", True, about, f"the implementation {a.get('use')} does not exist", "the factory"))
            continue
        if impl["of"] != a["operation"]:
            out.append(Issue("incompatible", True, about, f"the implementation {a['use']} does not implement {a['operation']}", "the factory"))
            continue
        reads = impl.get("reads_from", [])
        if "copy_ready_in" in when and when["copy_ready_in"] not in reads:
            out.append(Issue("incompatible", True, about,
                             f"the condition relies on a copy in {when['copy_ready_in']}, but {a['use']} does not read this memory pool", "the factory"))
        if "transient_fetch" in when:
            tf = when["transient_fetch"]
            path = hw.paths.get(tf["via"])
            if path is None or path["kind"] not in ("transfer", "page_in") or path.get("destination") != tf["into"]:
                out.append(Issue("incompatible", True, about,
                                 f"the path {tf['via']} of the transient fetch does not exist, or is not a transfer path into {tf['into']}", "the factory"))
            elif tf["into"] not in reads:
                out.append(Issue("incompatible", True, about, f"{a['use']} does not read {tf['into']}, so it cannot use the data fetched there", "the factory"))
            elif not any((d, tf["into"]) in transient_at for d in ops[a["operation"]].get("reads", [])):
                out.append(Issue("gap", True, about,
                                 f"a transient fetch needs a transient staging area declared in {tf['into']} for the data this operation reads", "the factory"))
        if "held_by" in when:
            if when["held_by"] not in hw.units:
                out.append(Issue("unbound_term", True, about, f"the compute unit {when['held_by']} is not in the hardware description", "the factory"))
            elif impl["runs_on"] != when["held_by"]:
                out.append(Issue("incompatible", True, about, f"{a['use']} does not run on {when['held_by']}", "the factory"))
    for op in {i["of"] for i in impls.values()} | set(assignments):
        if not any(x.get("otherwise") for x in assignments.get(op, [])):
            out.append(Issue("infeasible", True, f"binding.assignment.{op}",
                             "there is no default assignment (otherwise); when no condition is met, nothing performs this operation", "the factory"))

    # policies: what is controlled exists, the path an action goes through exists, there are signals to read
    residency_keys = {(r["data"], r["pool"]) for r in section("binding", "residency") if "by_policy" in r}
    for p in policies.values():
        about = f"policy.policies.{p['id']}"
        c = p.get("controls", {})
        if c.get("item") == "residency" and (c.get("data"), c.get("pool")) not in residency_keys:
            out.append(Issue("incompatible", True, about, "the residency entry the policy claims to control is not marked in the binding as decided by it", "the factory"))
        if not p.get("signals"):
            out.append(Issue("gap", True, about, "the policy declares no signals it reads", "the factory"))
        for act in p.get("actions", []):
            if "via" in act and act["via"] not in hw.paths:
                out.append(Issue("unbound_term", True, about, f"the path {act['via']} of the action {act['id']} is not in the hardware description", "the factory"))
        for name, val in (p.get("parameters") or {}).items():
            if val == "open":
                out.append(Issue("gap", False, f"{about}.parameters.{name}", "the policy parameter is still open", "an experiment"))

    # mechanisms adopted: what they do may fill only items left open in the target; the conditions that must be kept and the observation points are all in place
    target = ws.objects.get(spec.get("target_spec", ""))
    invariants = {i["id"] for i in section("state", "invariants")}
    observed = {o for c in components for o in c.get("observation_points", [])}
    for hid in spec.get("mechanisms", []):
        hyp = ws.objects.get(hid)
        about = f"mechanisms.{hid}"
        if hyp is None or hyp["kind"] != "mechanism":
            out.append(Issue("unbound_term", True, about, "this mechanism was not found", "the factory"))
            continue
        for d in hyp["do"]:
            if target is None:
                break
            aspect = target.get(d["aspect"])
            was_open = aspect == "open" or (isinstance(aspect, dict) and aspect.get(d["item"]) == "open")
            if not was_open:
                out.append(Issue("incompatible", True, about,
                                 f"the mechanism changes {d['aspect']}.{d['item']}, but the target spec does not leave it open", "the factory"))
        level = equivalence_level(hyp)
        floor = contract_floor(spec)
        if floor is not None and EQ_ORDER.index(level) > EQ_ORDER.index(floor):
            out.append(Issue("incompatible", True, about,
                             f"the mechanism's equivalence level is {EQ_TITLE[level]}; the contract allows at most {EQ_TITLE[floor]}", "the project"))
        for other in hyp.get("conflicts_with", []):
            if other in spec.get("mechanisms", []):
                out.append(Issue("incompatible", True, about, f"it conflicts with {other}, which is also adopted", "the factory"))
        for other in hyp.get("requires", []):
            if other not in spec.get("mechanisms", []):
                out.append(Issue("gap", True, about, f"it requires {other}, but the spec does not adopt it", "the factory"))
        declared = {s.get("of", s["id"]): s for s in section("state", "states")}
        for rule in hyp["needs"].get("state_rules", []):
            for d in model["data"]:
                if d["kind"] == "model_state" and rule not in declared.get(d["id"], {}):
                    out.append(Issue("gap", True, about,
                                     f"the mechanism needs every model state to declare {rule}; the state {d['id']} does not", "the factory"))
        for inv in hyp["needs"].get("invariants", []):
            if inv["id"] not in invariants:
                out.append(Issue("gap", True, about, f"the mechanism needs {inv['id']} ({inv['text']}) to be upheld; the spec does not have it", "the factory"))
        for o in hyp["needs"].get("observation_points", []):
            if o not in observed:
                out.append(Issue("gap", True, about, f"no component provides the observation point {o} the mechanism needs", "the factory"))

    # tracing: whether each contract requirement has evidence tied to an artifact
    evidence = ws.of_kind("evidence")
    for req in spec["contract"]["requirements"]:
        key = f"{spec['id']}#{req['id']}"
        if not any(key in e["verifies"] for e in evidence):
            out.append(Issue("untested", False, f"contract.requirements.{req['id']}", "no evidence linked to an artifact", "System Lab"))
    return out


EQ_ORDER = ["bit_exact", "distribution_exact", "numeric", "approximate"]
EQ_TITLE = {"bit_exact": "bit_exact", "distribution_exact": "distribution_exact", "numeric": "numeric", "approximate": "approximate"}


def equivalence_level(hyp: dict) -> str:
    """The equivalence level of a mechanism; when written case by case, the loosest one."""
    e = hyp["equivalence"]
    if isinstance(e, list):
        return max((x["level"] for x in e), key=EQ_ORDER.index)
    return e["level"] if isinstance(e, dict) else e


def contract_floor(spec: dict) -> str | None:
    """The loosest equivalence level the contract allows. Derived from allowed_transformations when equivalence_floor is not written; None when neither is given."""
    c = spec["contract"]
    floor = raw(c.get("equivalence_floor"))
    if floor in EQ_ORDER:
        return floor
    allowed = raw(c.get("allowed_transformations"))
    if is_unset(allowed):
        return None
    allowed = allowed or []
    for level in reversed(EQ_ORDER[1:]):
        if level in allowed:
            return level
    return "bit_exact"


def open_fields(spec: dict) -> list[str]:
    return [p for p, n in walk(spec) if n == "open"]


# ---------------------------------------------------------------- commands

def print_issues(issues: list[Issue]):
    for blocking in (True, False):
        group = [i for i in issues if i.blocking == blocking]
        if not group:
            continue
        print(f"\n{'Blocking' if blocking else 'Non-blocking'} issues ({len(group)})")
        for n, i in enumerate(group, 1):
            print(f"  {n:>2}. [{KIND_TITLE.get(i.kind, i.kind)}] {i.about}")
            print(f"      {i.message}" + (f"  → {i.owner}" if i.owner else ""))


# ---------------------------------------------------------------- system and component levels

EXTERNAL_ENDS = {"external", "model_files"}
BASIS_TITLE = {"code": "code", "header_comment": "header_comment", "docs": "docs"}


DERIVATION: dict[str, dict] = {}                            # derived systems: where each sentence comes from, for cmd_system to show


def check_system(ws: Workspace, system: dict) -> tuple[list[Issue], dict]:
    """Check a system and its components: whether the tree is consistent; whether both ends of each flow and what it carries exist; whether each state has only one owner;
    whether every stage, policy, state and invariant of the spec and every operation of the model has a component responsible for it; whether the composition on each target matches the binding and the hardware."""
    out: list[Issue] = list(ws.validate(system))
    sid = system["id"]
    who = "the author of the system description"
    comps = {c["id"]: c for c in ws.of_kind("component") if c["system"] == sid}
    for c in comps.values():
        out += ws.validate(c)
    # 0. files that cannot be read, duplicate ids: either can make the checks below see less than there is, so they block here
    out += ws.load_errors
    if any(i.kind == "schema" for i in out if i not in ws.load_errors):
        return out, comps                                   # when the structure is wrong, the fields the rules below read cannot be relied on
    systems = {s["id"] for s in ws.of_kind("system")}
    prefixes = {cid.rsplit("/", 1)[0] + "/" for cid in comps}
    for c in ws.of_kind("component"):                       # among these components, one whose system is written wrongly belongs to no system
        if c["system"] not in systems and any(c["id"].startswith(p) for p in prefixes):
            out.append(Issue("unbound_term", True, c["id"], f"its system is written as {c['system']}, and there is no such system; nothing checks it", who))

    # 1. component tree
    for cid, c in comps.items():
        parent = c.get("parent")
        if parent is not None:
            if parent not in comps:
                out.append(Issue("unbound_term", True, cid, f"the parent component {parent} does not exist", who))
            elif cid not in comps[parent].get("parts", []):
                out.append(Issue("incompatible", True, cid, f"it says its parent is {parent}, but the parts of {parent} do not list it", who))
        for part in c.get("parts", []):
            if part not in comps:
                out.append(Issue("unbound_term", True, cid, f"the part {part} does not exist", who))
            elif comps[part].get("parent") != cid:
                out.append(Issue("incompatible", True, cid, f"its parts list {part}, but the parent of {part} is not this component", who))
    for cid in system["components"]:
        if cid not in comps:
            out.append(Issue("unbound_term", True, sid, f"the top-level component {cid} does not exist", who))
        elif "parent" in comps[cid]:
            out.append(Issue("incompatible", True, sid, f"{cid} has a parent and should not be listed as a top-level component", who))
    for cid, c in comps.items():
        if "parent" not in c and cid not in system["components"]:
            out.append(Issue("gap", True, sid, f"{cid} has no parent, yet it is not in the system's list of top-level components", who))
    # a component that cannot be reached from the top-level list (for example two components that are each other's parent) is not part of this tree
    reached, todo = set(), [c for c in system["components"] if c in comps]
    while todo:
        x = todo.pop()
        if x not in reached:
            reached.add(x)
            todo += [p for p in comps[x].get("parts", []) if p in comps]
    for cid in sorted(set(comps) - reached):
        out.append(Issue("incompatible", True, cid, "it cannot be reached from the system's top-level components; it is not in the component tree", who))
    # whatever has parts is a subsystem, and a subsystem must have parts; when a subsystem runs is decided by its parts together
    timing_order = ws.schema["defs"]["timing"]["enum"]

    def runs_of(cid, seen=()):
        c = comps[cid]
        kids = [p for p in c.get("parts", []) if p in comps and p not in seen]
        return set(c.get("runs", [])) if not kids else set().union(*[runs_of(p, seen + (cid,)) for p in kids])

    for cid, c in comps.items():
        if bool(c.get("parts")) != (c.get("role") == "subsystem"):
            out.append(Issue("incompatible", True, cid, f"its role is {c.get('role')}, " + ("yet it has parts" if c.get("parts") else "yet it has no parts"), who))
        if c.get("parts") and cid in reached:
            mine = [t for t in timing_order if t in runs_of(cid)]
            if mine and set(mine) != set(c.get("runs", [])):
                out.append(Issue("incompatible", True, cid, f"its runs is {', '.join(c.get('runs', []))}, "
                                                            f"while its parts together give {', '.join(mine)}", who))

    # 2. targets: hardware, model, resolved spec
    ops_all, data_all, stages_all, pols_all, states_all = set(), set(), set(), set(), set()
    data_kind: dict[str, str] = {}
    targets = []
    for t in system.get("targets", []):
        hw, model, spec = ws.objects.get(t["hardware"]), ws.objects.get(t["model"]), ws.objects.get(t.get("spec", ""))
        if hw is None or model is None or hw.get("kind") != "hardware" or model.get("kind") != "model":
            out.append(Issue("unbound_term", True, sid, f"in the target, {t['hardware']} is not a hardware description, or {t['model']} is not a model description", who))
            continue
        ops_all |= {o["id"] for o in model["operations"]}
        data_all |= {d["id"] for d in model["data"]}
        data_kind |= {d["id"]: d.get("kind") for d in model["data"]}
        if "spec" in t and (spec is None or spec.get("kind") != "engine_spec"):
            out.append(Issue("unbound_term", True, sid, f"the spec {t['spec']} in the target does not exist, or is not an engine spec", who))
            spec = None
        elif spec is not None and ((spec.get("given") or {}).get("model") != t["model"]
                                   or (spec.get("given") or {}).get("hardware") != t["hardware"]):
            out.append(Issue("incompatible", True, sid, f"the spec {spec['id']} in the target is for {(spec.get('given') or {}).get('model')} on "
                                                        f"{(spec.get('given') or {}).get('hardware')}, not for this target", who))
            spec = None
        targets.append((t, hw, model, spec))
    if not targets:
        out.append(Issue("gap", True, sid, "there is no usable target (a model and a hardware); none of the rules that compare with the model and the hardware can be checked", who))

    def part(spec, aspect, key):
        x = (spec or {}).get(aspect)
        return x.get(key, []) if isinstance(x, dict) else []

    declared = system.get("declares", {})
    stages_all |= set(declared.get("stages", []))
    pols_all |= set(declared.get("policies", []))
    states_all |= set(declared.get("states", []))
    for _, _, _, spec in targets:
        stages_all |= {x["id"] for x in part(spec, "execution", "stages")}
        pols_all |= {x["id"] for x in part(spec, "policy", "policies")}
        states_all |= {x["id"] for x in part(spec, "state", "states")}

    # 3. state: a state can have only one owner; a state that is read or written must have an owner
    owners: dict[str, list[str]] = {}
    touched: dict[str, set] = {}
    for cid, c in comps.items():
        st = c.get("state", {})
        for x in st.get("owns", []):
            owners.setdefault(x, []).append(cid)
        for x in st.get("reads", []) + st.get("writes", []):
            touched.setdefault(x, set()).add(cid)
    for x, holders in owners.items():
        if len(holders) > 1:
            out.append(Issue("value_conflict", True, f"state.{x}", f"it has more than one owner: {', '.join(holders)}", who))
    for x in sorted(set(touched) - set(owners)):
        out.append(Issue("gap", True, f"state.{x}", f"{', '.join(sorted(touched[x]))} reads or writes it, but no component owns it", who))

    # 4. flows: ids are not repeated; both ends exist; the data or state carried exists and its kind matches; the timing is one at which one of the two ends runs
    ends = set()
    for fid, n in collections.Counter(f["id"] for f in system.get("flows", [])).items():
        if n > 1:
            out.append(Issue("value_conflict", True, f"{sid} · flows.{fid}", f"{n} flows use this id", who))
    if not system.get("flows") and sum(1 for c in comps.values() if not c.get("parts")) > 1:
        out.append(Issue("gap", True, sid, "no flow is written at all; the relations between components cannot be checked", who))
    want_kind = {"weights": "weight", "model_state": "model_state"}
    for f in system.get("flows", []):
        about = f"{sid} · flows.{f['id']}"
        for end in (f["sender"], f["receiver"]):
            if end not in comps and end not in EXTERNAL_ENDS:
                out.append(Issue("unbound_term", True, about, f"the flow's end {end} is neither a component nor external or model_files", who))
            ends.add(end)
        if f["sender"] == f["receiver"]:
            out.append(Issue("incompatible", True, about, "both ends of the flow are the same component", who))
        refs, content = f["carries"].get("refs", []), f["carries"]["content"]
        known = data_all if content in want_kind else (set(owners) | states_all if content == "engine_state" else data_all | ops_all | set(owners) | states_all)
        for ref in refs:
            if ref not in known:
                out.append(Issue("unbound_term", True, about, f"{ref}, which the flow carries, is not in the model description or the declared states", who))
            elif content in want_kind and data_kind.get(ref) != want_kind[content]:
                out.append(Issue("incompatible", True, about, f"the flow says it carries {content}, while {ref} is {data_kind.get(ref)} in the model description", who))
        if not refs and content in ("weights", "model_state", "engine_state"):
            out.append(Issue("gap", False, about, f"the flow carries {content}, but no refs say which ones", who))
        when = set().union(*[runs_of(e) for e in (f["sender"], f["receiver"]) if e in comps]) if any(e in comps for e in (f["sender"], f["receiver"])) else set()
        if when and f.get("timing") not in when:
            out.append(Issue("incompatible", False, about, f"the flow's timing is {f.get('timing')}, while the components at its ends run {', '.join(t for t in timing_order if t in when)}", who))
    boundary_ends = {f["receiver"] for f in system.get("flows", []) if f["sender"] in EXTERNAL_ENDS} | \
                    {f["sender"] for f in system.get("flows", []) if f["receiver"] in EXTERNAL_ENDS}
    directing = {f["sender"] for f in system.get("flows", []) if f["carries"]["content"] in ("plan", "control")}

    # 5. mechanisms: they exist; one a component uses is also listed by the system
    for holder in [system] + list(comps.values()):
        for hid in holder.get("mechanisms", []):
            if ws.objects.get(hid, {}).get("kind") != "mechanism":
                out.append(Issue("unbound_term", True, holder["id"], f"the mechanism {hid} does not exist", who))
            elif holder is not system and hid not in system.get("mechanisms", []):
                out.append(Issue("incompatible", True, holder["id"], f"it uses the mechanism {hid}, which the system's mechanisms does not list", who))

    # 6. each component
    for cid, c in comps.items():
        leaf = not c.get("parts")
        if leaf and cid not in ends and system.get("flows"):
            out.append(Issue("gap", False, cid, "no flow passes through it; its relations with other components are not written down", who))
        if leaf and not (c.get("state", {}).get("owns") or c.get("policies") or c.get("performs")
                         or c.get("implements_stages") or cid in boundary_ends or cid in directing):
            out.append(Issue("gap", False, cid, "it owns no state, runs no policy, performs no model operation, implements no stage, is not on the engine's outer boundary and sends no plan or control; "
                                                "by the division rules it is not enough to be a component of its own: merge it into another or give the reason", who))
        if leaf and not c.get("verification"):
            out.append(Issue("gap", False, cid, "how to verify it alone is not written", who))
        # a name must be in the target spec or in the declares of the system. When no name of that kind is declared at all, it is not skipped: see after this loop
        for x in c.get("implements_stages", []):
            if stages_all and x not in stages_all:
                out.append(Issue("unbound_term", True, cid, f"the stage {x} it implements is in no target spec and is not declared in the system's declares", who))
        for x in c.get("performs", []):
            if x not in ops_all:
                out.append(Issue("unbound_term", True, cid, f"the operation {x} it performs is not in the model description", who))
        for x in c.get("policies", []):
            if pols_all and x not in pols_all:
                out.append(Issue("unbound_term", True, cid, f"the policy {x} it runs is in no target spec and is not declared in the system's declares", who))
        for x in c.get("state", {}).get("owns", []):
            if states_all and x not in states_all:
                out.append(Issue("unbound_term", True, cid, f"the state {x} it owns is in no target spec and is not declared in the system's declares", who))
        own_inv = {i["id"] for i in c.get("invariants", [])}
        for v in c.get("verification", []):
            for inv in v.get("invariants", []):
                if inv not in own_inv:
                    out.append(Issue("unbound_term", True, cid, f"the invariant {inv} named in its verification is not among its own invariants", who))

    # components use names of some kind while neither the spec nor the system declares any name of that kind: the names cannot be checked, which blocks, one issue per kind
    for what, known, used in (("stage", stages_all, sorted({x for c in comps.values() for x in c.get("implements_stages", [])})),
                              ("policy", pols_all, sorted({x for c in comps.values() for x in c.get("policies", [])})),
                              ("state", states_all, sorted({x for c in comps.values() for x in c.get("state", {}).get("owns", [])}))):
        if used and not known:
            out.append(Issue("gap", True, sid, f"components use {len(used)} {what} names ({', '.join(used[:6])}{' and more' if len(used) > 6 else ''}), "
                                               f"while neither the target spec nor the system's declares declares any {what}; these names cannot be checked", who))

    # 7. against each target
    performed = {x for c in comps.values() for x in c.get("performs", [])}
    impl_stage = {x for c in comps.values() for x in c.get("implements_stages", [])}
    run_pol = {x for c in comps.values() for x in c.get("policies", [])}
    upheld = {i["id"] for c in comps.values() for i in c.get("invariants", [])}
    # names the system itself declares that no component uses
    for what, names, used in (("stage", declared.get("stages", []), impl_stage), ("policy", declared.get("policies", []), run_pol),
                              ("state", declared.get("states", []), set(owners) | set(touched))):
        for x in sorted(set(names) - used):
            out.append(Issue("gap", False, f"{sid} · declares", f"the {what} {x} is declared, but no component " + ("owns, reads or writes it" if what == "state" else "implements or runs it"), who))
    # the kinds of resource a component needs must exist on this machine. fast_memory: memory the main compute unit uses directly; slow_memory: larger
    # memory the main compute unit cannot use directly; storage: persistent storage; accelerator: a GPU or an NPU; cpu: a general-purpose processor.
    asked: dict[str, list[str]] = {}
    for cid, c in comps.items():
        if not c.get("parts"):
            for n in c.get("needs_resources", []):
                asked.setdefault(n["resource"], []).append(cid)
    lacking: dict[str, list[str]] = {}
    for t, hw, model, spec in targets:
        units = {u["id"]: u.get("kind") for u in hw.get("compute_units", [])}
        main = next((u for u, k in units.items() if k in ("gpu", "npu")), next(iter(units), None))
        direct = {p["pool"] for p in hw.get("access_paths", []) if p.get("kind") == "direct" and p.get("unit") == main}
        mem = {p["id"] for p in hw.get("memory_pools", []) if p.get("kind") != "nvme"}
        has = {"fast_memory": bool(mem & direct), "slow_memory": bool(mem - direct),
               "storage": any(p.get("kind") == "nvme" for p in hw.get("memory_pools", [])),
               "accelerator": any(k in ("gpu", "npu") for k in units.values()), "cpu": "cpu" in units.values()}
        for res in asked:
            if not has.get(res, True):
                lacking.setdefault(res, []).append(hw["id"])
    for res, hws in sorted(lacking.items()):
        everywhere = len(hws) == len(targets)                # absent on every target: what these components need does not exist
        who_asks = sorted(set(asked[res]))
        if everywhere:
            for cid in who_asks:
                out.append(Issue("incompatible", True, cid, f"it needs {res}, and {', '.join(hws)} has no such resource", who))
        else:
            out.append(Issue("gap", False, f"{sid} @ {', '.join(hws)}",
                             f"{len(who_asks)} components need {res}, and this machine has no such resource ({', '.join(x.split('/')[-1] for x in who_asks[:8])}"
                             f"{' and more' if len(who_asks) > 8 else ''}); are they active on this target?", who))
    for t, hw, model, spec in targets:
        tag = f"{sid} @ {t['hardware']}"
        served = set(t.get("input_modalities") or [])
        for op in model["operations"]:
            only_for = set(op.get("serves_modality") or [])
            if served and only_for and not (served & only_for):
                continue   # this operation serves only input modalities this target does not take
            if op["id"] not in performed:
                out.append(Issue("gap", True, tag, f"no component performs the model operation {op['id']}", who))
        if spec is None:
            continue
        for x in sorted({x["id"] for x in part(spec, "execution", "stages")} - impl_stage):
            out.append(Issue("gap", True, tag, f"no component implements the stage {x} of the spec", who))
        for x in sorted({x["id"] for x in part(spec, "policy", "policies")} - run_pol):
            out.append(Issue("gap", True, tag, f"no component runs the policy {x} of the spec", who))
        for x in sorted({x["id"] for x in part(spec, "state", "states")} - set(owners)):
            out.append(Issue("gap", True, tag, f"no component owns the state {x} of the spec", who))
        for inv in part(spec, "state", "invariants"):
            if inv["id"] not in upheld:
                out.append(Issue("gap", True, tag, f"no component upholds the invariant {inv['id']} of the spec", who))
        hw_ids = {x["id"] for x in hw["memory_pools"]} | {x["id"] for x in hw["compute_units"]}
        residency = {(r["data"], r["pool"]) for r in part(spec, "binding", "residency")}
        managed, listed = set(), set()
        for entry in part(spec, "composition", "components"):
            about = f"{spec['id']} · composition.{entry['id']}"
            ref = entry.get("component_ref")
            if ref is not None:
                listed.add(ref)
                if ref not in comps:
                    out.append(Issue("unbound_term", True, about, f"the component description {ref} does not exist", "the author of the spec"))
            if entry.get("active") is False and not entry.get("inactive_reason"):
                out.append(Issue("gap", False, about, "marked as not active, but no reason is given", "the author of the spec"))
            for m in entry.get("manages", []):
                managed.add((m["data"], m["pool"]))
                if (m["data"], m["pool"]) not in residency:
                    out.append(Issue("incompatible", True, about, f"the residency entry {m['data']}@{m['pool']} it manages is not in the binding", "the author of the spec"))
            for u in entry.get("uses", []):
                if u["where"] not in hw_ids:
                    out.append(Issue("unbound_term", True, about, f"{u['where']}, where the use is, is not on {hw['id']}", "the author of the spec"))
        if listed:
            for cid, c in comps.items():
                if not c.get("parts") and cid not in listed:
                    out.append(Issue("gap", False, tag, f"the component {cid} does not appear in this target's composition; is it active here?", "the author of the spec"))
            for d, pl in sorted(residency - managed):
                out.append(Issue("gap", False, tag, f"no component manages the residency entry {d}@{pl} of the binding", "the author of the spec"))

    # 8. derivation: the source each component of the new design points to exists; every leaf component of the main source engine is either carried over or listed with the reason it was not
    carried = set()
    for cid, c in comps.items():
        for dv in c.get("derived_from", []):
            src = ws.objects.get(dv["component"])
            if src is None or src.get("kind") != "component":
                out.append(Issue("unbound_term", True, cid, f"it says it comes from {dv['component']}, but there is no such component description", who))
                continue
            carried.add(dv["component"])
            if dv["carried_as"] == "adapted" and len(str(dv.get("adaptation", "")).strip()) < 15:
                out.append(Issue("gap", True, cid, f"it is adapted from {dv['component']}, but what was changed is not written (adaptation is empty or only a few characters)", who))
    for dv in system.get("derived_from", []):
        src_sys = ws.objects.get(dv["system"])
        if src_sys is None or src_sys.get("kind") != "system":
            out.append(Issue("unbound_term", True, sid, f"the source system {dv['system']} does not exist", who))
            continue
        src_comps = {c["id"]: c for c in ws.of_kind("component") if c["system"] == dv["system"]}
        listed_nc = {x["component"] for x in dv.get("not_carried", [])}
        for x in sorted(listed_nc - set(src_comps)):
            out.append(Issue("unbound_term", True, sid, f"{x} in not_carried is not a component of {dv['system']}", who))
        for x in sorted(listed_nc & carried):
            out.append(Issue("incompatible", True, sid, f"{x} is carried and is also listed in not_carried", who))
        if dv.get("main_source"):
            for x, c in sorted(src_comps.items()):
                if not c.get("parts") and x not in carried and x not in listed_nc:
                    out.append(Issue("gap", True, sid, f"the component {x} of the main source {dv['system']} is neither carried nor listed in not_carried with a reason", who))

        for x in dv.get("not_carried", []):
            if len(str(x.get("note", "")).strip()) < 15:
                out.append(Issue("gap", True, sid, f"{x['component']} is listed in not_carried, but the reason is not written in words (note is empty or only a few characters)", who))

    # 9. Descriptions derived from another engine. Three things, each independent of the derivation run that produced the files:
    #    a. Whether everything the comparison needs is there (the source system, the model and hardware on both sides, _derive.yaml). One thing
    #       missing means "cannot be checked", which blocks: having no rule to run must not show as having no problem.
    #    b. The files are what _derive.yaml writes now: derive again in memory and compare file by file. Files edited by hand, out of date,
    #       or whose source description changed do not match here. The rules of the derivation itself (every sentence is either written for
    #       this engine in _derive.yaml, or the sentence of the source itself and listed as read) are in tools/so_derive.py.
    #    c. The word rules (tools/so_leftovers.py) look in every sentence for numbers, names and implementation identifiers of the source. They know only the common forms.
    import so_leftovers
    st = so_leftovers.status(ws, system)
    DERIVATION.pop(sid, None)
    if st["derived"]:
        for r in st["cannot"]:
            out.append(Issue("gap", True, sid, f"cannot be checked against the source: {r}", who))
        for x in so_leftovers.leftovers(ws, system, st):
            out.append(Issue("incompatible", True, x["object"],
                             f"{x['field']} contains content of the source engine, {x['found']!r} ({x['why']}). The text: {x['context']}", who))
        directory = ws.files[sid].parent
        if (directory / "_derive.yaml").exists():
            import so_derive
            try:
                res = so_derive.derive(directory, ws.root)
            except Exception as e:                           # _derive.yaml itself cannot be read
                res = None
                out.append(Issue("schema", True, sid, f"the derivation list _derive.yaml cannot be run: {type(e).__name__}: {e}", who))
            if res is not None:
                for p in res["problems"]:
                    out.append(Issue("incompatible", True, sid, f"deriving again from the derivation list gives a problem: {p}", who))
                if not res["problems"]:
                    fresh = {d["id"]: d for d in [res["system"]] + res["components"]}
                    mine = {sid: system, **comps}
                    for i in sorted(set(fresh) | set(mine)):
                        if i not in mine:
                            out.append(Issue("incompatible", True, i, "the derivation list would write it, and the files do not have it; the files are out of date", who))
                        elif i not in fresh:
                            out.append(Issue("incompatible", True, i, "the files have it, and the derivation list would not write it; it was added by hand", who))
                        elif fresh[i] != mine[i]:
                            keys = sorted(k for k in set(fresh[i]) | set(mine[i]) if fresh[i].get(k) != mine[i].get(k))
                            out.append(Issue("incompatible", True, i, f"the file differs from what the derivation list writes now ({', '.join(keys)}); "
                                                                      f"the file was edited by hand, or the list or the source descriptions changed after it was generated", who))
                    DERIVATION[sid] = {"counts": res["counts"], "read_by": res["read_by"], "patterns": st["counts"]}
    return out, comps


def cmd_system(ws: Workspace, args) -> int:
    system = ws.objects.get(args.system)
    if system is None or system["kind"] != "system":
        print(f"system not found: {args.system}. Available: " + ", ".join(o["id"] for o in ws.of_kind("system")))
        return 2
    issues, comps = check_system(ws, system)
    print(f"System {system['id']}: {system.get('title', '')}")
    print(f"Component nodes: {len(comps)}\n")

    def show(cid, depth):
        c = comps[cid]
        basis = sorted({x["basis"] for x in c["sources"]}, key=["code", "header_comment", "docs", "proposal"].index)
        how = {dv["carried_as"] for dv in c.get("derived_from", [])}
        if basis[0] == "proposal":
            tag = "adapted" if "adapted" in how else ("reused" if how else "new")
        else:
            tag = BASIS_TITLE[basis[0]]
        mark = "" if c["role"] == "subsystem" else f"  [{tag}]"
        print(f"{'  ' * depth}- {c.get('title', cid)} ({c['role']}){mark}")
        for part in c.get("parts", []):
            if part in comps:
                show(part, depth + 1)

    for cid in system["components"]:
        if cid in comps:
            show(cid, 0)
    leaves = [c for c in comps.values() if c["role"] != "subsystem"]
    by = {b: sum(1 for c in leaves if b in {x["basis"] for x in c["sources"]} and
                 (b == "code" or "code" not in {x["basis"] for x in c["sources"]}) and
                 (b != "docs" or "header_comment" not in {x["basis"] for x in c["sources"]}))
          for b in ("code", "header_comment", "docs")}
    proposed = [c for c in leaves if {x["basis"] for x in c["sources"]} == {"proposal"}]
    if proposed:
        hows = [{dv["carried_as"] for dv in c.get("derived_from", [])} for c in proposed]
        nc = [x for dv in system.get("derived_from", []) for x in dv.get("not_carried", [])]
        print(f"\nThis is a design, not a description of an existing implementation: of {len(proposed)} nodes that are not subsystems, "
              f"{sum(1 for h in hows if h == {'reused'})} reused, {sum(1 for h in hows if 'adapted' in h)} adapted, "
              f"{sum(1 for h in hows if not h)} new; not_carried from the source engines: {len(nc)}"
              f" (does_not_apply {sum(1 for x in nc if x['why'] == 'does_not_apply')}, postponed {sum(1 for x in nc if x['why'] == 'postponed')})")
        dn = DERIVATION.get(system["id"])
        if dn:
            c = dn["counts"]
            print(f"With the subsystems, {c['components']} components: reused {c['reused']}, adapted {c['adapted']}, new {c['new']}.")
            print(f"Texts: {c['texts in all']} in all. {c['texts written for this engine in the derivation list']} are written for this engine in the derivation list; "
                  f"{c.get('source texts kept word for word', 0)} are sentences of the source kept word for word and {c.get('source texts kept with a stated replacement', 0)} are sentences of the source with one stated replacement, "
                  f"all in the list of kept texts with a reason; {c['titles taken from the source as names']} titles keep the source's names; "
                  f"{c['texts of components carried whole']} are in components carried whole.")
            print(f"The list of kept texts was read by: {dn['read_by'] or 'not written'}")
            print("Word patterns: " + ", ".join(f"{k} {v}" for k, v in sorted(dn["patterns"].items())) + ". These patterns know only the common ways of writing; passing the check does not mean every sentence is right.")
    else:
        print(f"\nBasis: of {len(leaves)} nodes that are not subsystems, {by['code']} code, {by['header_comment']} header_comment, {by['docs']} docs")
    print_issues(issues)
    blocking = sum(i.blocking for i in issues)
    print(f"\nConclusion: {'has blocking issues' if blocking else 'consistent'} (blocking {blocking}, non-blocking {len(issues) - blocking})")
    return 1 if blocking else 0



def cross_refs(ws: Workspace, obj: dict) -> list[Issue]:
    """Wherever a description points elsewhere by name, the name must exist. The structural check cannot see this."""
    out = []
    if obj["kind"] == "model":
        ops = {o["id"] for o in obj.get("operations", [])}
        data = {d["id"] for d in obj.get("data", [])}
        for o in obj.get("operations", []):
            target = (o.get("selects") or {}).get("operation")
            if target is not None and target not in ops:
                out.append(Issue("unbound_term", True, f"{obj['id']} · operations.{o['id']}", f"the operation {target} it selects is not in this model description"))
            for rel in ("reads", "writes"):
                for x in o.get(rel, []) or []:
                    if x not in data:
                        out.append(Issue("unbound_term", True, f"{obj['id']} · operations.{o['id']}", f"{x}, which it {'reads' if rel == 'reads' else 'writes'}, is not in the data of this model description"))
    if obj["kind"] == "component" and ws.objects.get(obj.get("system"), {}).get("kind") != "system":
        out.append(Issue("unbound_term", True, obj["id"], f"its system is written as {obj.get('system')}, and there is no such system"))
    if obj["kind"] == "system":
        for fid, n in collections.Counter(f.get("id") for f in obj.get("flows", [])).items():
            if n > 1:
                out.append(Issue("value_conflict", True, f"{obj['id']} · flows.{fid}", f"{n} flows use this id"))
    return out


def cmd_validate(ws: Workspace, args) -> int:
    issues = list(ws.load_errors)
    for obj in ws.objects.values():
        errs = ws.validate(obj)
        if not errs:
            errs = errs + cross_refs(ws, obj)
        if obj["kind"] in ("model", "hardware", "environment") and not errs:
            errs = errs + statement_conflicts(ws, obj, obj["kind"])
        issues += errs
        print(f"  {'pass' if not errs else 'FAIL'}  {obj['kind']:<12} {obj['id']}")
    print_issues(issues)
    return 1 if issues else 0


def cmd_check(ws: Workspace, args) -> int:
    spec = ws.objects.get(args.spec)
    if spec is None or spec["kind"] != "engine_spec":
        print(f"engine spec not found: {args.spec}. Available: " + ", ".join(o["id"] for o in ws.of_kind("engine_spec")))
        return 2
    print(f"Spec {spec['id']} ({spec['spec_level']})\n{spec.get('title', '')}")
    issues, hw, model, budgets = check_spec(ws, spec)
    print_issues(issues)

    for pid, amount in spec.pop("_derived_budgets", {}).items():
        print(f"\nDerived at startup: budget of the policy {pid} = {fmt_bytes(amount)}")
    opens = open_fields(spec)
    if opens:
        print(f"\nLeft to the factory ({len(opens)}): " + ", ".join(opens))

    if hw is not None and model is not None and spec["spec_level"] == "target":
        print("\nMechanism matching")
        if not ws.of_kind("mechanism"):
            print("  the workspace has no mechanisms")
        for hyp in ws.of_kind("mechanism"):
            print_match(ws, hyp, model, hw, budgets)

    blocking = sum(i.blocking for i in issues)
    print(f"\nConclusion: {'cannot be finalised' if blocking else 'can be finalised'} (blocking {blocking}, non-blocking {len(issues) - blocking})")
    return 1 if blocking else 0


def cmd_match(ws: Workspace, args) -> int:
    model, hwdoc = ws.objects.get(args.model), ws.objects.get(args.hardware)
    if model is None or hwdoc is None:
        print("the model or hardware description named was not found")
        return 2
    env = ws.objects.get(args.environment) if args.environment else None
    if args.environment and env is None:
        print(f"environment description not found: {args.environment}")
        return 2
    hw = Hardware(hwdoc, {a["pool"]: to_bytes(a) for a in (env or {}).get("allocatable", [])})
    budgets: dict[str, list[float]] = {}
    for item in args.budget or []:
        m = re.fullmatch(r"([^=]+)=([\d.]+)\s*([A-Za-z]+)", item)
        if not m or m.group(3) not in UNIT_BYTES or m.group(1) not in hw.pools:
            print(f"cannot parse the budget {item}; the format is pool=NUMBERUNIT, and the pool must be in the hardware description")
            return 2
        budgets.setdefault(m.group(1), []).append(float(m.group(2)) * UNIT_BYTES[m.group(3)])
    print(f"model {model['id']} × hardware {hwdoc['id']}" + (f" × environment {env['id']}" if env else "")
          + ("; budget " + ", ".join(f"{p}={'/'.join(fmt_bytes(b) for b in bs)}" for p, bs in budgets.items()) if budgets else ""))
    if model.get("default_status") == "assumed":
        print("Note: the whole of this model description is assumed")
    for hyp in ws.of_kind("mechanism"):
        print_match(ws, hyp, model, hw, budgets)
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="System Ontology checker")
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent.parent)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    c = sub.add_parser("check")
    c.add_argument("spec")
    y = sub.add_parser("system")
    y.add_argument("system")
    m = sub.add_parser("match")
    m.add_argument("--model", required=True)
    m.add_argument("--hardware", required=True)
    m.add_argument("--environment")
    m.add_argument("--budget", action="append")
    args = ap.parse_args()
    ws = Workspace(args.root)
    return {"validate": cmd_validate, "check": cmd_check, "match": cmd_match, "system": cmd_system}[args.cmd](ws, args)


if __name__ == "__main__":
    sys.exit(main())
