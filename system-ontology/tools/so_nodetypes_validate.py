#!/usr/bin/env python3
"""Summarise one round of independent checks of the draft node types against the pass marks.

    python tools/so_nodetypes_validate.py round3            # writes validation/round3/SUMMARY.md
    python tools/so_nodetypes_validate.py round3 --findings # also lists every finding, for whoever revises the types
    python tools/so_nodetypes_validate.py heldout           # the held-out engine: its readers and its checker

A round directory under `validation/` holds what independent readers produced:
  rater-*.yaml          each reader's classification of every anonymised part (validation/parts.anon.yaml)
  check-<engine>.yaml   one engine's inventory checked against the types (validation/CHECK-BRIEF.md)
  heldout-*.yaml        classification of the held-out engine's parts, once the types are frozen
The reference assignment is `reference-assignment-<draft>.yaml` in the round directory when the round kept its own
copy, otherwise `validation/reference-assignment.yaml`. Marks come from `validation/criteria.yaml`, and each row says
when the mark it is judged against was set and whether its reading was changed afterwards.
A result file that is missing is reported as not done; nothing is assumed about it. The program exits with 1 when a
mark is not met or the files contradict themselves (a typed total that does not match the entries listed under it).
Rounds 8 and 9 are scored by `so_nodetypes_experiments.py classify`, with the round's own key.
"""
import collections
import pathlib
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import so_nodetypes_experiments as X  # noqa: E402

ROOT = X.ROOT
V = X.V
pct = X.pct


def load(p):
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


def verdict(ok):
    return "met" if ok else "FAIL (not met)"


def version(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v)))


def mark_history(crit, section, draft):
    """When the mark of `section` was set, and every recorded change to how it is read that applies to `draft`."""
    out = [f"set {crit['set_on']}"]
    for k, v in crit.items():
        if k.startswith(f"{section}_note") and isinstance(v, str):
            m = re.search(r"[Ff]rom draft (\d+(?:\.\d+)*)", v)
            if m and version(draft) >= version(m.group(1)):
                out.append(f"read differently from draft {m.group(1)} on, after results were seen (`{k}`)")
    for k, v in crit.items():
        if k.startswith("thin_draft") and isinstance(v, dict):
            conf = next((x for x in v.values() if isinstance(x, dict) and "draft" in x and "sha256" in str(x["draft"])), None)
            m = re.search(r"draft (\d+(?:\.\d+)*)", str(conf.get("draft"))) if conf else None
            if m and version(draft) >= version(m.group(1)):
                out.append(f"withdrawn for draft {m.group(1)} by `{k}`")
    return "; ".join(out)


def agreement(rd, ref, also, key):
    raters = {p.stem: {a["item"]: a for a in load(p)["assignments"]} for p in sorted(rd.glob("rater-*.yaml"))}
    if not raters or key is None:
        return None
    rows, disagreements, fits = 0, [], {r: collections.Counter() for r in raters}
    unanswered = collections.Counter()
    for item, (engine, part) in sorted(key.items()):
        extra = also.get(engine, {}).get(part) or []
        accepted = {ref[engine][part], *([extra] if isinstance(extra, str) else extra)}
        given = {r: a[item]["node_type"] for r, a in raters.items() if item in a}
        for r, a in raters.items():
            if item in a:
                fits[r][str(a[item].get("fit"))] += 1
            else:
                unanswered[r] += 1
        rows += 1
        # a part some reader did not answer is agreed by nobody
        if len(given) < len(raters) or any(g not in accepted for g in given.values()):
            notes = {r: a[item].get("note", "") for r, a in raters.items() if item in a and a[item].get("note")}
            disagreements.append((engine, part, sorted(accepted), given, notes))
    return {"parts": rows, "agree": rows - len(disagreements), "disagreements": disagreements, "fits": fits,
            "raters": list(raters), "unanswered": dict(unanswered)}


LISTED = {"loosely": ("loosely",), "not_covered": ("not_covered", "not_covered_examples")}


def checks(rd):
    """engine -> what its checker found, for every check-<engine>.yaml in the round. Typed totals are compared with
    the entries listed under them and with the per-type rows; a difference is reported, never smoothed over."""
    out, mismatches = {}, []
    for p in sorted(rd.glob("check-*.yaml")):
        e = p.stem[len("check-"):]
        d = load(p)
        dc = d["decision_coverage"]
        t = dc["totals"]
        for field, keys in LISTED.items():
            listed = next((dc[k] for k in keys if dc.get(k) is not None), None)
            n = len(listed or [])
            if n != t.get(field, 0):
                mismatches.append(f"{e}: totals say {t.get(field, 0)} {field}, and {n} are listed"
                                  + (" (the round lists none)" if listed is None or not n else ""))
        per = dc.get("per_type") or []
        for field in ("decisions", "covered", "loosely", "not_covered", "engine_specific"):
            if per and sum(x.get(field, 0) for x in per) != t.get(field, 0):
                mismatches.append(f"{e}: per-type rows sum to {sum(x.get(field, 0) for x in per)} {field}, totals say {t.get(field, 0)}")
        parts = t["covered"] + t["loosely"] + t["not_covered"] + t["engine_specific"]
        if parts != t["decisions"]:
            mismatches.append(f"{e}: covered, loosely, not covered and engine-specific add up to {parts}, totals say {t['decisions']} decisions")
        out[e] = {
            "totals": t,
            "real": t["decisions"] - t["engine_specific"],
            "per_type": per,
            "not_covered": dc.get("not_covered") or dc.get("not_covered_examples") or [],
            "loosely": dc.get("loosely") or [],
            "contradictions": d.get("contradictions") or [],
            "relaxations": d.get("relaxations") or [],
            "new_causes": d.get("new_causes") or [],
            "wrong": d.get("wrong_assignments") or [],
            "inventory_errors": d.get("inventory_errors") or [],
            "missing_from_the_types": d.get("missing_from_the_types") or [],
        }
    return out, mismatches


def heldout(rd, crit):
    """Each held-out reader's own fit marks. Parts the reader flags as outside an engine are left out of the
    denominator, as the mark says, and how many were left out is returned with the figures."""
    res = []
    parts = len(X.inventory(X.HELD_OUT)[0])
    for p in sorted(rd.glob("heldout-*.yaml")):
        a = load(p)["assignments"]
        dropped = sum(1 for x in a if x.get("outside_an_engine"))
        c = collections.Counter(x["fit"] for x in a if not x.get("outside_an_engine"))
        # a part of the held-out inventory the reader did not answer stays in the denominator and is not plainly one type
        missing = max(parts - len(a), 0)
        n = sum(c.values()) + missing
        ok = bool(n) and c["clean"] / n >= crit["clean_fit_min"] and c["none"] / n <= crit["no_type_max"]
        res.append((p.stem, n, c, ok, dropped, len(a)))
    return res


def summarise(name, findings=False):
    """(lines, rows, problems) of one round."""
    rd = V / name
    crit = load(V / "criteria.yaml")
    types = load(ROOT / "ontology/node-types.draft.yaml")
    own_types = sorted(rd.glob("node-types.draft-*.yaml"))
    if own_types:
        types = load(own_types[0])
    draft = types["draft_version"]
    own_ref = sorted(rd.glob("reference-assignment-*.yaml"))
    ref = load(own_ref[0] if own_ref else V / "reference-assignment.yaml")
    also = ref.pop("also", {}) or {}
    key = load(V / "parts.key.yaml")
    held = any(rd.glob("heldout-*.yaml"))
    expected = [X.HELD_OUT] if held else X.INDUCTION

    L = [f"# Node types draft {draft}: independent checks, {name}", "",
         f"{len(types['types'])} types, {sum(len(t.get('choices', [])) for t in types['types'])} choices. "
         f"Marks from `validation/criteria.yaml`; the last column says when each was set and how its reading changed.", ""]
    rows, problems = [], []

    ag = agreement(rd, ref, also, key)
    if ag:
        m = crit["agreement"]["same_type_min"]
        miss = f"; parts without an answer from a reader: {ag['unanswered']}" if ag["unanswered"] else ""
        rows.append(("Blind agreement: every reader and the reference name the same type" + miss,
                     f"{ag['agree']}/{ag['parts']} = {pct(ag['agree'], ag['parts'])}",
                     f"at least {m:.0%}", verdict(ag["agree"] / ag["parts"] >= m), mark_history(crit, "agreement", draft)))
    else:
        rows.append(("Blind agreement", "not done", "", "not done", ""))

    ck, mismatches = checks(rd)
    problems += mismatches
    if ck:
        dec = sum(c["real"] for c in ck.values())
        cov = sum(c["totals"]["covered"] for c in ck.values())
        loose = sum(c["totals"]["loosely"] for c in ck.values())
        nc = sum(c["totals"]["not_covered"] for c in ck.values())
        con = sum(len(c["contradictions"]) for c in ck.values())
        dropped = sum(c["totals"]["engine_specific"] for c in ck.values())
        m = crit["decision_coverage"]
        missing = [e for e in expected if e not in ck]
        tag = f" ({', '.join(missing)} not done)" if missing else ""
        hist = mark_history(crit, "decision_coverage", draft)
        rows.append((f"Decisions plainly covered by a choice{tag}; {dropped} decisions the checkers called engine-specific "
                     "are left out of the denominator", f"{cov}/{dec} = {pct(cov, dec)}", f"at least {m['covered_min']:.0%}",
                     verdict(not missing and cov / dec >= m["covered_min"]), hist))
        rows.append(("Decisions covered only loosely", f"{loose}/{dec} = {pct(loose, dec)}", "no mark", "", ""))
        rows.append(("Decisions not covered", f"{nc}/{dec} = {pct(nc, dec)}", f"at most {m['not_covered_max']:.0%}",
                     verdict(not missing and nc / dec <= m["not_covered_max"]), hist))
        rows.append(("Claims an engine contradicts", str(con), f"at most {crit['claims']['contradicted_max']}",
                     verdict(not missing and con <= crit["claims"]["contradicted_max"]), mark_history(crit, "claims", draft)))
        nc_ = sum(len(c["new_causes"]) for c in ck.values())
        rows.append(("Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5)", str(nc_), "no mark", "", ""))
        rows.append(("Parts assigned to the wrong type in the reference", str(sum(len(c["wrong"]) for c in ck.values())), "no mark", "", ""))
        miss_jobs = sum(len(c["missing_from_the_types"]) for c in ck.values())
        if miss_jobs:
            rows.append(("Jobs the checker found that no type describes", str(miss_jobs), "no mark", "", ""))
    else:
        rows.append(("Decision coverage and claims", "not done", "", "not done", ""))

    g = crit["generalisation"]
    for rname, n, c, ok, dropped, total in heldout(rd, g):
        unanswered = n + dropped - total
        rows.append((f"Held-out engine, {rname}: the reader's own fit marks ({dropped} of {total} parts the reader flags as "
                     "outside an engine left out of the denominator"
                     + (f"; {unanswered} parts not answered, counted as not plainly one type" if unanswered else "") + ")",
                     f"{c['clean']}/{n} clean = {pct(c['clean'], n)}, {c['none']} without a type = {pct(c['none'], n)}",
                     f"clean at least {g['clean_fit_min']:.0%}, none at most {g['no_type_max']:.0%}", verdict(ok),
                     mark_history(crit, "generalisation", draft)))
    if held and g.get("applies_to") == "every_fold":
        rows.append(("Leave one engine out, each engine in turn (the generalisation mark applies to every fold)",
                     f"one fold done: {X.HELD_OUT}", "every engine", "not tested", mark_history(crit, "generalisation", draft)))

    L += ["| Check | Result | Mark | | When the mark was set |", "|---|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows] + [""]
    if problems:
        L += ["## The files contradict themselves", ""] + [f"- {p}" for p in problems] + [""]

    if ck:
        L += ["## Per engine", "", "| | " + " | ".join(ck) + " |", "|---|" + "---|" * len(ck)]
        L.append("| Decisions (engine-specific excluded) | " + " | ".join(str(c["real"]) for c in ck.values()) + " |")
        L.append("| Plainly covered | " + " | ".join(pct(c["totals"]["covered"], c["real"]) for c in ck.values()) + " |")
        L.append("| Not covered | " + " | ".join(pct(c["totals"]["not_covered"], c["real"]) for c in ck.values()) + " |")
        L.append("| Contradicted claims | " + " | ".join(str(len(c["contradictions"])) for c in ck.values()) + " |")
        L.append("| Unnamed causes at a listed level | " + " | ".join(str(len(c["new_causes"])) for c in ck.values()) + " |")
        L.append("| Relaxed `should` rules not yet noted | " + " | ".join(str(len(c["relaxations"])) for c in ck.values()) + " |")
        L.append("| Inventory entries the source corrects | " + " | ".join(str(len(c["inventory_errors"])) for c in ck.values()) + " |")
        L.append("| Jobs no type describes | " + " | ".join(str(len(c["missing_from_the_types"])) for c in ck.values()) + " |")
        L.append("")
    if ag:
        L += ["## Readers' own fit marks", "", "| Reader | clean | partial | none |", "|---|---|---|---|"]
        L += [f"| {r} | {f['clean']} | {f['partial']} | {f['none']} |" for r, f in ag["fits"].items()] + [""]

    if findings:
        if ag:
            L += ["## Disagreements on type", ""]
            for engine, part, acc, given, notes in ag["disagreements"]:
                L.append(f"- {engine}/{part}: reference {' or '.join(acc)}; " + ", ".join(f"{r} {g}" for r, g in given.items())
                         + ("" if not notes else " — " + " | ".join(f"{r}: {n}" for r, n in notes.items())))
            L.append("")
        for title, field, fmt in [
            ("Wrong assignments", "wrong", lambda x: f"{x['part']}: {x['assigned']} -> {x['better']}. {x['why']}"),
            ("Contradicted claims", "contradictions", lambda x: f"[{x['type']}] {x['part']}: {x['claim']}\n    evidence: {x['evidence']}\n    fix: {x['fix']}"),
            ("New causes", "new_causes", lambda x: f"[{x['type']}] {x['part']}: {x['level']} — {x['cause']}\n    evidence: {x['evidence']}"),
            ("Relaxations", "relaxations", lambda x: f"[{x['type']}] {x['part']}: {x['rule']} — {x['how']}"),
            ("Inventory errors", "inventory_errors", lambda x: f"{x['part']}.{x['field']}: recorded {x['recorded']!r}; source shows {x['source_shows']!r}"),
            ("Decisions not covered", "not_covered", lambda x: f"[{x['type']}] {x['part']}: {x['decision']}\n    missing ({x.get('kind', '?')}): {x.get('missing_choice', '')}"),
            ("Decisions covered loosely", "loosely", lambda x: f"[{x['type']}] {x['part']}: {x['decision']}\n    nearest: {x.get('nearest_choice', '')}"),
        ]:
            L += [f"## {title}", ""]
            for e, c in ck.items():
                for x in sorted(c[field], key=lambda x: x.get("type", x.get("assigned", ""))):
                    L.append(f"- {e} {fmt(x)}")
            L.append("")
    failed = [r for r in rows if r[3].startswith("FAIL")]
    return L, rows, problems, failed


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    findings = "--findings" in sys.argv
    if not args:
        sys.exit(__doc__)
    rd = V / args[0]
    if (rd / "parts.key.yaml").exists():
        print(f"validation/{args[0]} has its own key of parts; it is scored by "
              f"`python tools/so_nodetypes_experiments.py classify validation/{args[0]}/parts.key.yaml {args[0]}`")
        return 2
    L, rows, problems, failed = summarise(args[0], findings)
    out = rd / ("FINDINGS.md" if findings else "SUMMARY.md")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[: 14 + len(rows) + 24] if findings else L))
    print(f"\nwritten: {out.relative_to(ROOT)}")
    if failed or problems:
        print(f"RESULT: FAIL. {len(failed)} marks not met" + (f"; {len(problems)} places where the files contradict themselves" if problems else ""))
        return 1
    print("RESULT: pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
