"""Shared job logic: run a public tool CLI and extract the answer. No model calls."""
import json
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def frac_str(q):
    """Exact decimal text for a Fraction with a finite decimal expansion."""
    q = Fraction(q)
    if q.denominator == 1:
        return str(q.numerator)
    d = q.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    if d != 1:
        raise ValueError('not a finite decimal')
    sign = '-' if q < 0 else ''
    q = abs(q)
    places = 0
    while (q * 10 ** places).denominator != 1:
        places += 1
    n = int(q * 10 ** places)
    s = str(n).rjust(places + 1, '0')
    return sign + s[:-places] + '.' + s[-places:]


def extract(job, table):
    """Apply the job's extractor to a parsed table result {'columns','rows'}."""
    ex = job['extract']
    cols, rows = table['columns'], table['rows']
    idx = {c: i for i, c in enumerate(cols)}
    t = ex['type']
    if t == 'last':
        return str(rows[-1][idx[ex['field']]])
    if t == 'nth':
        return str(rows[ex['n'] - 1][idx[ex['field']]])
    if t in ('where', 'strlen'):
        hit = [r for r in rows if str(r[idx[ex['key']]]) == ex['val']]
        if len(hit) != 1:
            raise ValueError('lookup is not unique')
        v = hit[0][idx[ex['field']]]
        return str(len(v)) if t == 'strlen' else str(v)
    if t == 'count_nonempty':
        return str(sum(1 for r in rows if str(r[idx[ex['field']]]) != ''))
    raise ValueError(t)


def run_tool(public_dir, job, python=None):
    """Run the tool CLI exactly as a user would. Returns (rc, stdout)."""
    public_dir = Path(public_dir)
    cmd = [python or sys.executable, '-B', job['tool_file'], *job['argv']]
    p = subprocess.run(cmd, cwd=str(public_dir), capture_output=True, text=True, encoding='utf-8', timeout=120)
    return p.returncode, p.stdout


def tool_answer(public_dir, job, python=None):
    """The answer a user gets from the tool for this job, or None if the tool errored."""
    rc, out = run_tool(public_dir, job, python)
    if rc != 0:
        return None
    if job['kind'] == 'calc':
        return out.strip()
    return extract(job, json.loads(out))
