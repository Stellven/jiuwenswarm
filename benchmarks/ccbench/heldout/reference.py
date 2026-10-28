"""Reference solutions, used only by test_heldout.py to prove that the hand-written expected values in cases.json
are mutually consistent with the spec (a second, independent derivation). Never shown to a model."""
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def merge_intervals(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def compare_versions(a, b):
    x, y = [int(p) for p in a.split('.')], [int(p) for p in b.split('.')]
    n = max(len(x), len(y))
    x, y = x + [0] * (n - len(x)), y + [0] * (n - len(y))
    return (x > y) - (x < y)


def round_half_up(value, ndigits):
    q = Decimal(1).scaleb(-ndigits)
    r = Decimal(value).quantize(q, rounding=ROUND_HALF_UP)
    if r == 0:
        r = abs(r)
    return format(r, 'f')


def rle_decode(s):
    return ''.join(ch * int(n or 1) for n, ch in re.findall(r'(\d*)([a-z])', s))


def business_days(start, end, holidays):
    d0, d1, hol = date.fromisoformat(start), date.fromisoformat(end), set(holidays)
    count, d = 0, d0
    while d < d1:
        if d.weekday() < 5 and d.isoformat() not in hol:
            count += 1
        d += timedelta(days=1)
    return count


def top_k_words(text, k):
    counts = {}
    for w in re.findall(r"[a-z']+", text.lower()):
        w = w.strip("'")
        if w:
            counts[w] = counts.get(w, 0) + 1
    return [[w, c] for w, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


def wrap_text(text, width):
    lines, cur = [], ''
    for w in text.split():
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += ' ' + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def parse_duration(s):
    units = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
    body = s.strip()
    if not body or not re.fullmatch(r'(\d+[dhms]\s*)+', body):
        raise ValueError(s)
    found = re.findall(r'(\d+)([dhms])', body)
    if len({u for _, u in found}) != len(found):
        raise ValueError(s)
    return sum(int(n) * units[u] for n, u in found)


def dedupe_records(records, key):
    last, order, out = {}, [], []
    for r in records:
        if key in r:
            token = (type(r[key]).__name__, repr(r[key]))
            if token not in last:
                order.append(token)
                out.append(('k', token))
            last[token] = r
        else:
            out.append(('r', r))
    return [dict(last[x]) if tag == 'k' else dict(x) for tag, x in out]


def brackets_balanced(s):
    pairs, stack, i, n = {')': '(', ']': '[', '}': '{'}, [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            i += 1
            while i < n and s[i] != '"':
                i += 2 if s[i] == '\\' else 1
            if i >= n:
                return False
        elif c in '([{':
            stack.append(c)
        elif c in pairs:
            if not stack or stack.pop() != pairs[c]:
                return False
        i += 1
    return not stack
