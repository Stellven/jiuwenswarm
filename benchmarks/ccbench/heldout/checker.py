"""Model-free executor for model-written Python: runs held-out tests and self-written tests in a child process.

Safety (host, no Docker): the child is `python -I` in an empty temp directory with a hard timeout, and code that
imports process / file / network modules or calls eval / exec / open is refused before it runs. This is a guard for a
benchmark of pure functions, not a security boundary; run it on a machine you are happy to run model code on.
"""
import copy
import json
import re
import subprocess
import sys
import tempfile

TIMEOUT_S = 20
MARK = '@@RESULT@@ '
BANNED = re.compile(r'(^|\n)\s*(import|from)\s+(os|sys|subprocess|socket|shutil|pathlib|ctypes|urllib|http|requests|multiprocessing|threading|signal|importlib|builtins)\b'
                    r'|__import__|\beval\s*\(|\bexec\s*\(|\bopen\s*\(|\bcompile\s*\(', re.S)

CHILD = r'''
import copy, json, sys, traceback
payload = json.loads(sys.stdin.read())
MARK = %r
def emit(obj):
    sys.stdout.write(MARK + json.dumps(obj) + "\n"); sys.stdout.flush()
ns = {"__name__": "solution"}
try:
    exec(compile(payload["code"], "solution.py", "exec"), ns)
except BaseException as e:
    emit({"fatal": "%%s: %%s" %% (type(e).__name__, e)}); sys.exit(0)
if payload["mode"] == "selftest":
    try:
        exec(compile(payload["tests"], "tests.py", "exec"), ns)
        emit({"selftest": "pass"})
    except BaseException:
        emit({"selftest": "fail", "trace": traceback.format_exc()[-1500:]})
    sys.exit(0)
fn = ns.get(payload["function"])
if not callable(fn):
    emit({"fatal": "function %%s is not defined" %% payload["function"]}); sys.exit(0)
for i, t in enumerate(payload["tests"]):
    try:
        got = fn(*copy.deepcopy(t["args"]))
        emit({"i": i, "got": json.loads(json.dumps(got))})
    except BaseException as e:
        emit({"i": i, "error": type(e).__name__})
''' % MARK


def same(a, b):
    """Equality that does not let True == 1 or 1 == 1.0 pass."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return type(a) is type(b) and a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def _run_child(payload, timeout):
    with tempfile.TemporaryDirectory() as cwd:
        try:
            done = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD], input=json.dumps(payload).encode('utf-8'),
                                  capture_output=True, timeout=timeout, cwd=cwd)
            out, timed_out = done.stdout, False
        except subprocess.TimeoutExpired as exc:
            out, timed_out = exc.stdout or b'', True
    rows = []
    for line in out.decode('utf-8', 'replace').splitlines():
        if line.startswith(MARK):
            try:
                rows.append(json.loads(line[len(MARK):]))
            except ValueError:
                pass
    return rows, timed_out


def describe(test, row):
    args = json.dumps(test['args'], ensure_ascii=False)[:200]
    want = ('raises ' + test['raises']) if test.get('raises') else json.dumps(test['expect'], ensure_ascii=False)[:200]
    if row is None:
        return 'input %s: expected %s, but no result (timeout or crash)' % (args, want)
    if 'error' in row:
        return 'input %s: expected %s, raised %s' % (args, want, row['error'])
    return 'input %s: expected %s, got %s' % (args, want, json.dumps(row.get('got'), ensure_ascii=False)[:200])


def run_tests(code, function, tests, timeout=TIMEOUT_S):
    """Return dict(results=[{ok, detail}], fatal=str|None, timed_out=bool). One entry per test, always len(tests)."""
    if code is None or not code.strip():
        return dict(results=[dict(ok=False, detail='no code') for _ in tests], fatal='no code', timed_out=False)
    if BANNED.search(code):
        return dict(results=[dict(ok=False, detail='refused: banned import or call') for _ in tests], fatal='refused: banned import or call', timed_out=False)
    rows, timed_out = _run_child(dict(mode='tests', code=code, function=function, tests=tests), timeout)
    fatal = next((r['fatal'] for r in rows if 'fatal' in r), None)
    by_index = {r['i']: r for r in rows if 'i' in r}
    results = []
    for i, test in enumerate(tests):
        row = by_index.get(i)
        if fatal:
            results.append(dict(ok=False, detail=fatal))
        elif row is None:
            results.append(dict(ok=False, detail=describe(test, None)))
        elif test.get('raises'):
            results.append(dict(ok=row.get('error') == test['raises'], detail=describe(test, row)))
        else:
            results.append(dict(ok='got' in row and same(row['got'], test['expect']), detail=describe(test, row)))
    return dict(results=results, fatal=fatal, timed_out=timed_out)


def run_selftest(code, tests_code, timeout=TIMEOUT_S):
    """Run the model's own test script against its own function. Returns (status, text); status is pass / fail / skipped."""
    if not (tests_code or '').strip():
        return 'skipped', 'the answer contained no test script'
    if BANNED.search(code or '') or BANNED.search(tests_code):
        return 'fail', 'refused: banned import or call'
    rows, timed_out = _run_child(dict(mode='selftest', code=code, tests=tests_code), timeout)
    for r in rows:
        if 'fatal' in r:
            return 'fail', r['fatal']
        if r.get('selftest') == 'pass':
            return 'pass', ''
        if r.get('selftest') == 'fail':
            return 'fail', r['trace']
    return 'fail', 'timeout' if timed_out else 'crash with no output'
