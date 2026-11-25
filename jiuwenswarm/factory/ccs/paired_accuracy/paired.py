"""Paired accuracy with planned checkpoints (stdlib only).

Two arms answer the same multiple-choice questions in the same fixed random order. The accuracy loss is
acc(reference) - acc(candidate). At each planned checkpoint the Newcombe (1998, method 10) paired interval is
computed with the group-sequential critical value Z_SEQ, so looking at every checkpoint keeps a wrong pass (or a
wrong fail) at or under 2.5% (Pocock-type constant boundary, calibrated by simulation for LOOKS).

Decision against a non-inferiority margin M (points):
  pass  upper bound of the loss < M      (the candidate loses less than M, at 97.5% one-sided)
  fail  lower bound of the loss > M      (it loses more than M)
  else  continue to the next checkpoint; at the last one report the interval without a verdict.
"""
import csv, hashlib, json, math, random
from pathlib import Path

LOOKS = (50, 100, 160, 250, 430)
# Pocock-type constant boundary. Brownian motion at LOOKS/430 gives 2.453 for an overall two-sided 5%; simulating
# this exact rule (Newcombe intervals, these looks, true loss = margin, flip rates 6-20%) showed 3.0-3.5% false
# passes at 2.453 (the intervals are slightly liberal at small counts), 2.0-2.4% at 2.65. 2.65 keeps the false
# pass rate at or under the nominal one-sided 2.5%.
Z_SEQ = 2.65
SEED = 20261125
LETTERS = 'ABCD'


# ---- data ----------------------------------------------------------------------------------------
def mmlu_order(test_dir, seed=SEED):
    """All MMLU test questions (Hendrycks CSVs) in one fixed random order."""
    rows = []
    for f in sorted(Path(test_dir).glob('*_test.csv')):
        subject = f.name[:-len('_test.csv')]
        with open(f, newline='', encoding='utf-8') as fh:
            for i, r in enumerate(csv.reader(fh)):
                rows.append(dict(id=f'{subject}/{i}', subject=subject, question=r[0], choices=r[1:5], answer=r[5].strip()))
    random.Random(seed).shuffle(rows)
    return rows


def prompt(q):
    """The lm-evaluation-harness zero-shot MMLU form, scored on the next token after 'Answer:'."""
    subj = q['subject'].replace('_', ' ')
    body = '\n'.join(f'{L}. {c}' for L, c in zip(LETTERS, q['choices']))
    return f"The following are multiple choice questions (with answers) about {subj}.\n\n{q['question'].strip()}\n{body}\nAnswer:"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def letter_probs(top):
    """{A..D: prob} from a top-k list of (token, logprob); ' A' and 'A' both count. Missing letters get 0."""
    p = {L: 0.0 for L in LETTERS}
    for tok, lp in top:
        t = tok.strip()
        if t in p:
            p[t] += math.exp(lp)
    return p


# ---- statistics ------------------------------------------------------------------------------------
def wilson(x, n, z):
    if n == 0:
        return 0.0, 1.0
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def newcombe_paired(a, b, c, d, z):
    """95%-type interval for p1 - p2 from paired counts: a both right, b only arm 1 right, c only arm 2 right,
    d both wrong (Newcombe 1998, method 10, no continuity correction)."""
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n, z)
    l2, u2 = wilson(a + c, n, z)
    den = (a + b) * (c + d) * (a + c) * (b + d)
    phi = (a * d - b * c) / math.sqrt(den) if den > 0 else 0.0
    diff = p1 - p2
    lo = diff - math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    hi = diff + math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return diff, lo, hi


def pair_counts(ref, cand, ids):
    a = b = c = d = 0
    for i in ids:
        r, k = ref[i]['correct'], cand[i]['correct']
        a += r and k; b += r and not k; c += k and not r; d += not r and not k
    return a, b, c, d


def look(ref, cand, ids, margin_pts, z=Z_SEQ, final=False):
    """One checkpoint over the first len(ids) paired questions. Returns the numbers and the decision."""
    a, b, c, d = pair_counts(ref, cand, ids)
    n = len(ids)
    diff, lo, hi = newcombe_paired(a, b, c, d, z)
    m = margin_pts / 100
    decision = 'pass' if hi < m else 'fail' if lo > m else ('report' if final else 'continue')
    agree = sum(max(ref[i]['probs'], key=ref[i]['probs'].get) == max(cand[i]['probs'], key=cand[i]['probs'].get) for i in ids) / n
    tvd = sum(0.5 * sum(abs(ref[i]['probs'][L] - cand[i]['probs'][L]) for L in LETTERS) for i in ids) / n
    flips = (b + c) / n
    need = math.ceil(1.96 ** 2 * flips / (0.05 ** 2)) if flips else None
    return dict(n=n, z=z, both_right=a, ref_only=b, cand_only=c, both_wrong=d,
                acc_ref=round((a + b) / n, 4), acc_cand=round((a + c) / n, 4),
                loss_pts=round(100 * diff, 2), lo_pts=round(100 * lo, 2), hi_pts=round(100 * hi, 2),
                margin_pts=margin_pts, decision=decision, flip_rate=round(flips, 4),
                answer_agreement=round(agree, 4), mean_tvd=round(tvd, 4), single_look_n_for_5pts=need)


def sequential(ref, cand, order_ids, margin_pts, looks=LOOKS, z=Z_SEQ):
    """Evaluate every planned checkpoint both arms have reached; stop at the first pass/fail."""
    out = []
    have = [i for i in order_ids if i in ref and i in cand]
    if have != order_ids[:len(have)]:
        raise ValueError('rows are not a prefix of the fixed order')
    for k, n in enumerate(looks):
        if len(have) < n:
            break
        r = look(ref, cand, order_ids[:n], margin_pts, z, final=(k == len(looks) - 1))
        out.append(r)
        if r['decision'] in ('pass', 'fail'):
            break
    return out
