#!/usr/bin/env python3
"""Find words and numbers of a source engine in the description of an engine derived from it.

    python tools/so_leftovers.py sys/muse-on-spark            # the rules that ran, then every finding
    python tools/so_leftovers.py sys/muse-on-spark --count    # totals only

A system that names other systems under `derived_from` describes a new engine for another model or machine. This
program reads the descriptions of the models and machines on both sides and looks, in every text of the derived
system, its components and its flows, for:

  model_number     a number the main source's model states and this engine's model does not: how many experts are
                   picked and out of how many, every numeric statement (layers, hidden size, ...), the sizes of its
                   data, and the products of these. A number of three digits or more is looked for wherever it stands,
                   in digits or in words; a smaller one only beside the thing it counts
  model_feature    a name of something the main source's model has and this engine's model has not
  machine_feature  a kind of memory the source's machines have and this engine's machines have not, and a capacity
                   of the source's machines
  source_engine    the name of a source engine
  implementation   an identifier of an implementation: a command-line flag, an environment variable, a function, a
                   source or data file. A name that this engine's own model, machine or target states is not one
  declared         a term listed by hand in `_derive.yaml` under `source_only_terms`, for what the descriptions
                   cannot tell

What these rules are and are not. They are word patterns. They find a source fact said in the usual words; the same
fact said otherwise passes, and a true sentence about this engine that uses one of the words is found as well. They
do not show that a text is right for this engine. That rests on where each text comes from, which
`tools/so_derive.py` controls: a text is written for this engine in `_derive.yaml`, or it is the source's text and is
listed in `_derive.kept.yaml` as read. A finding on a sentence that is true of this engine is settled by listing the
sentence in `_derive.kept.yaml` under `allow`, with the reason.

Texts that say where the design comes from (`derived_from`, `sources`) are about the source by definition and are
not read. `coverage`, `summary`, `product` and `uncatalogued_mechanisms` say what the design takes and leaves out, so
the source's name, features and listed terms may stand there; numbers and identifiers may not.

A rule that cannot be built is said, never skipped: `status()` lists what could not be checked and why, and
`tools/so_check.py system` reports each as a blocking issue.
"""
import collections
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

LINEAGE_KEYS = {"derived_from", "sources"}
NAME_ALLOWED = {"coverage", "summary", "product", "uncatalogued_mechanisms"}
LINEAGE_OK = ("source_engine", "model_feature", "machine_feature", "declared")
# Words too common to stand for a feature of a model on their own.
GENERIC = {"state", "table", "keys", "key", "history", "lookup", "weights", "weight", "data", "cache", "head", "blocks",
           "block", "output", "input", "token", "tokens", "layer", "layers", "model", "size", "total"}
# What a selection is counted in, whatever the model: the words that stand beside "how many are picked".
SELECTION_WORDS = ["logit", "score", "pick", "choice", "candidate", "top"]
UNITS = r"(?:[KMGT]i?B|bytes?)"
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
IMPLEMENTATION = [
    ("command-line flag", re.compile(r"(?<![\w-])--[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:=\S+)?|(?<![\w-])-[a-z]{1,4}(?=\s+\d)")),
    ("environment variable or build constant", re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9]\b(?:=\S+)?")),
    ("file name", re.compile(r"\b[\w/-]+\.(?:cpp|cu|cuh|hpp|h|c|cc|py|sh|bin|gguf|safetensors|json|txt|toml|ya?ml|cfg|ini|so|md)\b")),
    ("identifier in code", re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b|\b[a-z]+[A-Z][A-Za-z0-9]*\b|\b\w+::\w+(?:::\w+)*|\b[A-Za-z_]\w*\(\)")),
]
NOT_IDENTIFIERS = {"llama.cpp"}                                  # an engine's name that looks like a file name


def words_of(n):
    """An integer below a million in English words, in the two usual forms (with and without "and")."""
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")]
    if n < 1000:
        rest = n % 100
        head = ONES[n // 100] + " hundred"
        return [head] if not rest else [f"{head} and {words_of(rest)[0]}", f"{head} {words_of(rest)[0]}"]
    if n < 1000000:
        rest = n % 1000
        head = words_of(n // 1000)[0] + " thousand"
        return [head] if not rest else [f"{head} {w}" for w in words_of(rest)] + [f"{head} and {words_of(rest)[0]}"]
    return []


def number_forms(v):
    """Regular expressions for one number as a text may write it: digits, digits grouped in threes, words."""
    if isinstance(v, float) and v != int(v):
        return [re.escape(f"{v:g}")]
    n = int(v)
    forms = {str(n), f"{n:,}", f"{n:,}".replace(",", " "), f"{n:,}".replace(",", r"\s")}
    out = [re.escape(f) if "\\s" not in f else f for f in forms]
    if n >= 1000 and n % 100 == 0:                               # 24.6 thousand
        out.append(re.escape(f"{n / 1000:g}") + r"\s*(?:thousand|k)")
    return out + [re.escape(w).replace(r"\ ", r"\s+").replace(r"\-", r"[-\s]") for w in words_of(n)]


def stated_numbers(doc):
    """(key, value, unit) for every number a description states: the key says what it is a number of."""
    out = []
    for o in doc.get("operations", []) or []:
        for k, v in (o.get("selects") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append((f"{o['id']}.{k}", v, None))
    for s in doc.get("statements", []) or []:
        v = s.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append((s.get("property"), v, s.get("unit")))
    for d in doc.get("data", []) or []:
        size = d.get("size")
        if isinstance(size, dict) and isinstance(size.get("value"), (int, float)):
            out.append((f"{d['id']}.size", size["value"], size.get("unit")))
    for p in doc.get("memory_pools", []) or []:
        cap = p.get("capacity_nominal")
        if isinstance(cap, dict) and isinstance(cap.get("value"), (int, float)):
            out.append((f"{p.get('kind')}.capacity", cap["value"], cap.get("unit")))
    return out


def every_number(doc):
    """Every number anywhere in a description, also inside its texts."""
    found = set()

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, bool):
            return
        elif isinstance(x, (int, float)):
            found.add(float(x))
        elif isinstance(x, str):
            for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", x):
                try:
                    found.add(float(m.group(0).replace(",", "")))
                except ValueError:
                    pass
    walk(doc)
    return found


def nouns_for(key, model):
    """Words that name what a number of this key counts, taken from the description itself."""
    parts = re.split(r"[._]", key)
    words = {p for p in parts if len(p) >= 4 and p not in ("size", "selects", "value", "capacity")}
    op = next((o for o in model.get("operations", []) if key.startswith(o["id"] + ".")), None)
    if op is not None:                                           # a selection: what is selected, and the usual words
        target = (op.get("selects") or {}).get("operation") or ""
        words |= {p for p in target.split("_") if len(p) >= 4}
        for d in model.get("data", []):
            if any(d["id"] in (x.get("reads") or []) for x in model.get("operations", []) if x["id"] == target):
                words |= {p for p in d["id"].split("_") if len(p) >= 4}
        words |= set(SELECTION_WORDS)
        words -= {"weights", "weight", "router"}
    return sorted(words)


def number_rules(src_models, dst_models, dst_others):
    """Rules for the numbers the source models state and this engine's descriptions do not."""
    mine = set().union(*[every_number(d) for d in list(dst_models) + list(dst_others)]) if dst_models else set()
    dst_by_key = collections.defaultdict(set)
    for m in dst_models:
        for k, v, _ in stated_numbers(m):
            dst_by_key[re.sub(r"^[^.]+\.(?=out_of|pick|up_to)", "selection.", k)].add(float(v))
    rules = []
    for m in src_models:
        facts = stated_numbers(m)
        by = {re.sub(r"^[^.]+\.(?=out_of|pick|up_to)", "selection.", k): v for k, v, _ in facts}
        derived = []                                             # products a description of the source may state
        ints = [(k, v) for k, v in by.items() if float(v) == int(v) and 1 < v < 100000]
        for i, (ka, a) in enumerate(ints):
            for kb, b in ints[i + 1:]:
                if {ka.split(".")[-1], kb.split(".")[-1]} & {"out_of", "pick", "layers"} and len({ka, kb}) == 2 \
                        and all(x.split(".")[-1] in ("out_of", "pick", "layers") for x in (ka, kb)):
                    derived.append((f"{ka} x {kb}", a * b, None))
        for key, v, unit in facts + derived:
            k = re.sub(r"^[^.]+\.(?=out_of|pick|up_to)", "selection.", key)
            if float(v) in dst_by_key.get(k, set()):
                continue                                         # the same number of the same thing in this engine
            why = f"the source model {m['id']} states {key} = {v:g}" + (f" {unit}" if unit else "") + \
                  (f"; this engine's model has {', '.join(f'{x:g}' for x in sorted(dst_by_key[k]))}" if dst_by_key.get(k) else "")
            forms = "|".join(number_forms(v))
            num = rf"(?<![\w.,])(?:{forms})(?![\w]|[.,]\d)"
            if unit and re.fullmatch(UNITS, unit or "", re.I):   # a size: the number with a byte unit
                rules.append(("model_number", re.compile(rf"{num[:-len('(?![\\w]|[.,]\\d)')]}\s*{UNITS}\b", re.I), why))
                continue
            if float(v) != int(v):
                continue
            if v >= 100 and float(v) not in mine:                # distinctive: wherever it stands
                rules.append(("model_number", re.compile(num, re.I), why))
                continue
            nouns = nouns_for(key, m)
            if not nouns:
                continue
            noun = "(?:" + "|".join(re.escape(n) + r"\w*" for n in nouns) + ")"
            gap = r"(?:[\s,:=_()-]+\w+){0,3}?[\s,:=_()-]+"
            rules.append(("model_number", re.compile(rf"{num}(?={gap}{noun}\b)|(?<=\b)(?:{noun}\b{gap})({forms})(?![\w]|[.,]\d)"
                                                     rf"|\btop[-_ ]?k?\s*=?\s*(?:{forms})(?![\w]|[.,]\d)", re.I), why))
    return rules


def names_of(model):
    return {x["id"] for x in model.get("operations", [])} | {x["id"] for x in model.get("data", [])}


def feature_rules(src_models, dst_models):
    mine = set().union(*[names_of(m) for m in dst_models]) if dst_models else set()
    my_tokens = {t for n in mine for t in n.split("_")}
    rules = []
    for m in src_models:
        for name in sorted(names_of(m) - mine):
            for tok in name.split("_"):
                if len(tok) < 3 or tok in my_tokens or tok in GENERIC:
                    continue
                spelled = "-?".join(re.escape(ch) for ch in tok) if tok.isalpha() else re.escape(tok)
                tail = r"\w*" if len(tok) >= 5 else ""            # drafts, drafting, drafter; but mtp only as a word
                rules.append(("model_feature", re.compile(rf"\b{spelled}{tail}\b", re.I),
                              f"`{name}` exists in the source model {m['id']} and not in this engine's model"))
    return rules


def machine_rules(src_hw, dst_hw, dst_others):
    """What the source's machines have and this engine's machines have not: kinds of memory, and capacities."""
    if not dst_hw:
        return []
    mine_kinds = {p.get("kind") for h in dst_hw for p in h.get("memory_pools", [])}
    mine_ids = {p.get("id") for h in dst_hw for p in h.get("memory_pools", [])}
    mine_numbers = set().union(*[every_number(d) for d in list(dst_hw) + list(dst_others)])
    rules = []
    for h in src_hw:
        for p in h.get("memory_pools", []):
            kind, pid = p.get("kind"), p.get("id")
            if kind and kind not in mine_kinds:
                head = kind.split("_")[0]                         # device_ram: device RAM, device memory
                why = f"{h['id']} has memory of kind {kind}; this engine's machine has {', '.join(sorted(k for k in mine_kinds if k))}"
                rules.append(("machine_feature", re.compile(rf"\b{re.escape(head)}[-\s]+(?:ram|memory)\b", re.I), why))
                if pid and pid not in mine_ids and len(pid) >= 4:
                    rules.append(("machine_feature", re.compile(rf"\b{re.escape(pid)}\b", re.I), why))
            cap = p.get("capacity_nominal")
            if isinstance(cap, dict) and isinstance(cap.get("value"), (int, float)) and float(cap["value"]) not in mine_numbers:
                rules.append(("machine_feature", re.compile(rf"(?<![\w.,]){re.escape(f'{cap['value']:g}')}\s*{UNITS}\b", re.I),
                              f"{cap['value']:g} {cap.get('unit', '')} is the capacity of {pid} on {h['id']}"))
    return rules


def own_names(docs):
    """Every identifier this engine's own descriptions state: ids, names of states, stages and policies, and the
    words of its model, machine and target. A text may use these."""
    names, text = set(), []

    def walk(x, key=None):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str):
            if key in ("id", "name", "property", "subject", "quantity", "pool", "unit", "kind", "role", "resource",
                       "content", "timing", "resolved_at", "held_on", "method") or re.fullmatch(r"[\w./-]+", x):
                names.update(re.split(r"[/.]", x))
                names.add(x)
            text.append(x)
    for d in docs:
        walk(d)
    return names, "\n".join(text)


def build(src_systems, main_models, dst_models, src_hw, dst_hw, dst_others, declared=()):
    """Every pattern to look for, as (rule, pattern, why)."""
    rules = number_rules(main_models, dst_models, list(dst_hw) + list(dst_others))
    rules += feature_rules(main_models, dst_models)
    rules += machine_rules(src_hw, dst_hw, list(dst_models) + list(dst_others))
    names = set()
    for s in src_systems:
        names |= {s["id"].split("/")[-1]} | set(re.findall(r"[A-Za-z][\w.]+", (s.get("product") or {}).get("name", "")))
    for n in sorted(x for x in names if len(x) >= 3):
        rules.append(("source_engine", re.compile(rf"\b{re.escape(n)}\b", re.I), f"`{n}` is a source engine"))
    for what, pat in IMPLEMENTATION:
        article = "an" if what[:1] in "aeiou" else "a"
        rules.append(("implementation", pat, f"{article} {what}; this engine's own descriptions do not state it"))
    for t in declared or []:
        rules.append(("declared", re.compile(rf"\b{re.escape(t['term'])}\b", 0 if t.get("exact_case") else re.I),
                      t.get("why", "listed under source_only_terms")))
    seen, uniq = set(), []
    for r in rules:
        if (r[0], r[1].pattern) not in seen:
            seen.add((r[0], r[1].pattern))
            uniq.append(r)
    return uniq


def find(text, rules, name_allowed=False, own=None):
    """(rule, what was found, why) for every finding in one text. `own`: (names, text) of this engine's own
    descriptions; an identifier they state is not a finding."""
    out = []
    names, own_text = own or (set(), "")
    for rule, pat, why in rules:
        if rule in LINEAGE_OK and name_allowed:
            continue
        for m in pat.finditer(text):
            found = next((g for g in m.groups() if g), None) or m.group(0)
            if found in NOT_IDENTIFIERS:
                continue
            if rule == "implementation":
                bare = found.split("=")[0].rstrip("()")
                if bare in names or bare.lower() in names or (len(bare) >= 4 and bare in own_text):
                    continue
            out.append((rule, found, why))
    return out


def texts(node, path=""):
    """(path, text) of every string in a document, the fields that say where the design comes from left out."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in LINEAGE_KEYS:
                continue
            yield from texts(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            label = (v.get("id") or v.get("name")) if isinstance(v, dict) else None
            yield from texts(v, f"{path}[{label or i}]")
    elif isinstance(node, str):
        yield path, node


STRUCTURAL = {"id", "kind", "system", "parent", "parts", "role", "runs", "components", "sender", "receiver", "timing",
              "content", "refs", "resource", "performs", "implements_stages", "policies", "owns", "reads", "writes",
              "mechanisms", "declares", "model", "hardware", "spec", "resolved_at", "method", "invariants.ref",
              "unit", "unit_basis", "status", "held_on", "level", "input_modalities"}


def prose(doc):
    """(path, text) of the texts of a document that are sentences or names for a reader, not references."""
    for path, text in texts(doc):
        last = re.sub(r"\[.*?\]", "", path).split(".")[-1]
        if last in STRUCTURAL or (last == "invariants" and ".verification" in "." + path):
            continue
        yield path, text


def manifest_of(directory):
    p = pathlib.Path(directory) / "_derive.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


def allowed_of(directory):
    """Sentences that a rule finds and that were read as true of this engine: {(object, text): {found words}}."""
    p = pathlib.Path(directory) / "_derive.kept.yaml"
    if not p.exists():
        return {}
    out = collections.defaultdict(set)
    for a in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("allow") or []:
        out[(a["object"], a["text"])].add(str(a["found"]).lower())
    return out


def compare(objects, system, entries, declared, own_docs=()):
    """The rules for one derived system, from the descriptions on both sides. `system`: a system or the `system`
    part of a derivation list (it needs `targets`). `entries`: its sources as [{system, main_source}]. Returns
    {rules, counts, own, cannot, compared}; `cannot` says what could not be compared and why."""
    cannot = []
    get = lambda i, kind: objects.get(i) if isinstance(i, str) and objects.get(i, {}).get("kind") == kind else None
    src_systems = []
    for d in entries:
        s = get(d["system"], "system")
        if s is None:
            cannot.append(f"the source system {d['system']} is not among the descriptions that could be read")
        else:
            src_systems.append((d, s))

    def of(s, key, kind):
        found = []
        for t in s.get("targets", []) or []:
            o = get(t.get(key), kind)
            if o is None:
                cannot.append(f"{s.get('id')} names the {kind} {t.get(key)}, which could not be read")
            elif o not in found:
                found.append(o)
        return found

    dst_models, dst_hw = of(system, "model", "model"), of(system, "hardware", "hardware")
    if not system.get("targets"):
        cannot.append("the system names no target, so there is no model or machine to compare with the source's")
    mains = [s for d, s in src_systems if d.get("main_source")]
    if src_systems and not mains:
        cannot.append("no source is marked main_source, so no source model or machine is compared")
    main_models, src_hw = [], []
    for s in mains:
        main_models += [m for m in of(s, "model", "model") if m not in main_models and m not in dst_models]
        src_hw += [h for h in of(s, "hardware", "hardware") if h not in src_hw and h not in dst_hw]
    kinds = lambda k: [o for o in objects.values() if isinstance(o, dict) and o.get("kind") == k]
    specs = [get(t.get("spec"), "engine_spec") for t in system.get("targets", []) or []]
    target_specs = [s for s in kinds("engine_spec")
                    if (s.get("given") or {}).get("model") in {m["id"] for m in dst_models}
                    and (s.get("given") or {}).get("hardware") in {h["id"] for h in dst_hw}]
    envs = [e for e in kinds("environment") if e.get("hardware") in {h["id"] for h in dst_hw}]
    dst_others = [s for s in specs if s] + [s for s in target_specs if s not in specs] + envs
    rules = build([s for _, s in src_systems], main_models, dst_models, src_hw, dst_hw, dst_others, declared)
    names, _ = own_names(list(own_docs) + dst_models + dst_hw + dst_others)
    own_text = " ".join(t for d in dst_models + dst_hw + dst_others for _, t in texts(d))
    return {"rules": rules, "counts": dict(collections.Counter(r[0] for r in rules)), "own": (names, own_text),
            "cannot": cannot,
            "compared": {"source models": [m["id"] for m in main_models], "models": [m["id"] for m in dst_models],
                         "source machines": [h["id"] for h in src_hw], "machines": [h["id"] for h in dst_hw]}}


def status(ws, system):
    """What can and cannot be checked for one system: {derived, cannot, rules, counts, own, compared}."""
    sid = system["id"]
    comps = [c for c in ws.of_kind("component") if c["system"] == sid]
    cites = sorted({dv["component"] for c in comps for dv in c.get("derived_from", [])})
    entries = system.get("derived_from", []) or []
    if not (entries or cites):
        return {"derived": False, "cannot": [], "rules": [], "counts": {}, "own": (set(), ""), "compared": {}}
    manifest = manifest_of(ws.files[sid].parent)
    out = compare(ws.objects, system, entries, (manifest or {}).get("source_only_terms"), [system] + comps)
    out["derived"] = True
    cannot = out["cannot"]
    if cites and not entries:
        cannot.append(f"{len(cites)} of its components say they come from other engines' components, and the system names "
                      f"no source under derived_from")
    known = {d["system"] for d in entries}
    for c in cites:
        owner = ws.objects.get(c, {}).get("system")
        if owner == sid:
            cannot.append(f"a component says it comes from {c}, a component of this same system")
        elif owner is not None and owner not in known:
            cannot.append(f"a component says it comes from {c} of {owner}, which the system does not name as a source")
    if manifest is None:
        cannot.append(f"no _derive.yaml beside {ws.files[sid].name}: the terms listed by hand and the record of where "
                      f"each text comes from are missing")
    return out


def scan(docs, rules, own=None, allowed=None):
    """Every place where the documents use a word or a number the rules look for."""
    seen, out = set(), []
    allowed = allowed or {}
    for doc in docs:
        for path, text in prose(doc):
            top = path.split(".")[0].split("[")[0]
            for rule, found, why in find(text, rules, name_allowed=top in NAME_ALLOWED, own=own):
                k = (doc["id"], path, found.lower())
                if k in seen or found.lower() in allowed.get((doc["id"], text), ()):
                    continue
                seen.add(k)
                at = text.find(found)
                a, b = max(0, at - 50), min(len(text), at + len(found) + 50)
                out.append({"object": doc["id"], "field": path, "rule": rule, "found": found, "why": why, "text": text,
                            "context": ("…" if a else "") + text[a:b].replace("\n", " ") + ("…" if b < len(text) else "")})
    return out


def leftovers(ws, system, st=None):
    st = st or status(ws, system)
    if not st["derived"]:
        return []
    comps = [c for c in ws.of_kind("component") if c["system"] == system["id"]]
    return scan([system] + comps, st["rules"], st["own"], allowed_of(ws.files[system["id"]].parent))


def main():
    import so_check as sc
    sys.stdout.reconfigure(encoding="utf-8")
    ws = sc.Workspace(pathlib.Path(__file__).resolve().parent.parent)
    system = ws.objects.get(sys.argv[1]) if len(sys.argv) > 1 else None
    if system is None:
        print(__doc__)
        return 2
    st = status(ws, system)
    if not st["derived"]:
        print(f"{system['id']}: not derived from another engine; nothing to look for")
        return 0
    c = st["counts"]
    print(f"{system['id']}: {sum(c.values())} patterns (" + ", ".join(f"{k} {v}" for k, v in sorted(c.items())) + ")")
    for k, v in (st.get("compared") or {}).items():
        print(f"  {k}: {', '.join(v) or 'none'}")
    for r in st["cannot"]:
        print(f"  CANNOT CHECK: {r}")
    found = leftovers(ws, system, st)
    by_rule = collections.Counter(f["rule"] for f in found)
    print(f"{len(found)} findings in {len({f['object'] for f in found})} objects"
          + ("" if not found else " (" + ", ".join(f"{r} {n}" for r, n in by_rule.most_common()) + ")"))
    if "--count" not in sys.argv:
        for f in found:
            print(f"- {f['object']}  {f['field']}\n    {f['rule']}: {f['found']!r}  ({f['why']})\n    {f['context']}")
    return 1 if found or st["cannot"] else 0


if __name__ == "__main__":
    sys.exit(main())
