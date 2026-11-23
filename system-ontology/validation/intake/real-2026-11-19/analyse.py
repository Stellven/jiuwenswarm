"""What the real Intent and Requirements stages did with each query: readiness, counts, and what of each attached
file their output cites. Reads the result files beside this script; writes nothing."""
import collections
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
FIELDS = ("context", "in_scope", "out_of_scope", "constraints", "preferences", "user_targets", "uncertainties")


def spans(x):
    out = []

    def walk(v):
        if isinstance(v, dict):
            if "source_ref" in v and "start" in v:
                out.append((v["source_ref"].get("sha256"), v["start"], v["end"]))
            for w in v.values():
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)
    walk(x)
    return out


def items_of(name, text):
    """(label, start, end) of the items of a node-level or system-level file, by the position of each item's first line."""
    if name == "nodes.yaml":
        pat = r"(?m)^- component: (\S+)"
    elif name == "node-types.yaml":
        pat = r"(?m)^- id: (\S+)\n  group:"
    elif name == "system.yaml":
        pat = r"(?m)^- id: (\S+)\n  sender:"
    else:
        return []
    ms = list(re.finditer(pat, text))
    return [(m.group(1), m.start(), (ms[i + 1].start() if i + 1 < len(ms) else len(text))) for i, m in enumerate(ms)]


for v in "ABCD":
    pin, pres = HERE / f"intent_in_{v}.json", HERE / f"intent_{v}_result.json"
    if not pres.exists():
        continue
    q = json.loads(pin.read_text(encoding="utf-8"))
    res = json.loads(pres.read_text(encoding="utf-8"))
    docs = {hashlib.sha256(d["text"].encode("utf-8")).hexdigest(): d for d in q["documents"]}
    docs[hashlib.sha256(q["request"].encode("utf-8")).hexdigest()] = {"name": "request", "text": q["request"]}
    rc = res["receipt"]
    print(f"\n===== query {v}: {sum(len(d['text']) for d in docs.values()):,} characters in {len(docs)} sources")
    print(f"Intent: {res['status']}" + (f" | halt: {rc['halt']['reason'][:150]}" if rc.get("halt") else "")
          + f" | checks {[c['outcome'] for c in rc.get('checks', [])]}"
          + f" | verifier {[f['outcome'] for r in (rc.get('semantic_verifier') or {}).get('reviews', {}).values() for f in r.get('findings', [])]}")
    ir = (res.get("outputs") or {}).get("intent")
    if not ir:
        continue
    u = ir["uncertainties"]
    print(f"  readiness {ir['readiness']['status']}; uncertainties {len(u)}, blocking {sum(1 for x in u if x.get('blocking'))}; "
          + ", ".join(f"{f} {len(ir.get(f) or [])}" for f in FIELDS[:-1]))
    cover = collections.defaultdict(set)
    by_field = collections.defaultdict(lambda: collections.Counter())
    hit_items = collections.defaultdict(lambda: collections.defaultdict(set))
    for f in ("interpretation",) + FIELDS:
        entries = ir.get(f) or []
        entries = entries if isinstance(entries, list) else [entries]
        for e in entries:
            for sha, a, b in spans(e):
                d = docs.get(sha)
                if not d:
                    continue
                cover[d["name"]].update(range(a, b))
                by_field[d["name"]][f] += 1
                for label, s0, s1 in items_of(d["name"], d["text"]):
                    if a < s1 and b > s0:
                        # a quote that covers many items says nothing about any one of them
                        wide = sum(1 for _, t0, t1 in items_of(d["name"], d["text"]) if a < t1 and b > t0)
                        hit_items[d["name"]]["one" if wide == 1 else "wide"].add((label, f, e.get("id") if isinstance(e, dict) else ""))
    for d in docs.values():
        n = d["name"]
        its = items_of(n, d["text"])
        line = f"  {n:16} {len(cover[n]):6,} of {len(d['text']):6,} characters cited ({len(cover[n]) * 100 // max(len(d['text']), 1):3}%) | by {dict(by_field[n])}"
        print(line)
        if its:
            one = {x[0] for x in hit_items[n]["one"]}
            wide = {x[0] for x in hit_items[n]["wide"]} - one
            print(f"      {len(its)} items in this file: {len(one)} cited by a quote of their own, {len(wide)} only inside a quote that spans several")
            for label in sorted(one):
                where = sorted({f"{f}:{i}" for l, f, i in hit_items[n]["one"] if l == label})
                print(f"        {label}: {where[:4]}")
    pb = HERE / f"requirements_{v}_result.json"
    if pb.exists():
        rb = json.loads(pb.read_text(encoding="utf-8"))
        rcb = rb["receipt"]
        print(f"Requirements: {rb['status']}" + (f" | halt: {rcb['halt']['reason'][:170]}" if rcb.get("halt") else "")
              + f" | checks {[c['outcome'] for c in rcb.get('checks', [])]}"
              + f" | verifier {[f['outcome'] for r in (rcb.get('semantic_verifier') or {}).get('reviews', {}).values() for f in r.get('findings', [])]}")
        br = (rb.get("outputs") or {}).get("brief")
        if br:
            lists = {k: len(x) for k, x in br.items() if isinstance(x, list)}
            un = br.get("unresolved_items") or []
            print(f"  brief lists: {lists}")
            print(f"  unresolved {len(un)}, blocking {sum(1 for x in un if str(x.get('disposition', x.get('blocking'))).lower() in ('blocking', 'true'))}")
