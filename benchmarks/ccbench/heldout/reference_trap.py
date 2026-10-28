"""Reference solutions for cases-trap.json. Used only by test_heldout.py; never shown to a model.
Written from the spec sentence, before the tests. Each function is self-contained so its source can be run alone."""
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_EVEN


def parse_size(s):
    m = re.fullmatch(r' *([0-9]+) *(B|KB|MB|GB) *', s)
    if not m:
        raise ValueError('bad size')
    return int(m.group(1)) * {'B': 1, 'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3}[m.group(2)]


def bucket_counts(values, edges):
    n = len(edges) - 1
    counts = [0] * n
    for v in values:
        if v < edges[0] or v > edges[n]:
            continue
        if v == edges[n]:
            counts[n - 1] += 1
            continue
        for i in range(n):
            if edges[i] <= v < edges[i + 1]:
                counts[i] += 1
                break
    return counts


def competition_rank(scores):
    return [1 + sum(1 for t in scores if t > s) for s in scores]


def consistent_groups(groups):
    return sorted(k for k, nums in groups.items() if nums and (all(x > 0 for x in nums) or all(x < 0 for x in nums)))


def is_anagram(a, b):
    def norm(t):
        t = unicodedata.normalize('NFKC', t).casefold()
        return sorted(c for c in t if not c.isspace())
    return norm(a) == norm(b)


def to_cents(amount):
    return int((Decimal(amount) * 100).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def format_delta(x):
    t = '%.1f' % x
    if float(t) == 0:
        return '0.0'
    return t if t.startswith('-') else '+' + t


def collapse_adjacent(items):
    out = []
    for it in items:
        if not out or out[-1] != it:
            out.append(it)
    return out
