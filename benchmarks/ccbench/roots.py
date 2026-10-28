"""Environment roots shared by the ccbench harnesses.

AI4R_CODE_ROOT   product repo (default: the repo that contains this file)
AI4R_BENCH_DATA  old evidence root: traps/, stored baselines, native sessions
                 (default: ~/huawei/outputs/cc-sweep-20261026)
AI4R_CODEX_BIN   codex executable (default: `codex` on PATH)
"""
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def code_root():
    value = os.environ.get('AI4R_CODE_ROOT')
    return Path(value) if value else HERE.parents[1]


def bench_data():
    value = os.environ.get('AI4R_BENCH_DATA')
    return Path(value) if value else Path.home() / 'huawei' / 'outputs' / 'cc-sweep-20261026'


def need_data(*parts):
    """Path under AI4R_BENCH_DATA; exit with a clear message if it is missing."""
    path = bench_data().joinpath(*parts)
    if not path.exists():
        raise SystemExit('%s not found. Set AI4R_BENCH_DATA to the old evidence root (now %s).' % (path, bench_data()))
    return path


def codex_bin():
    """Resolved codex executable, or None when it cannot be found."""
    value = os.environ.get('AI4R_CODEX_BIN')
    if value:
        return value if Path(value).is_file() else shutil.which(value)
    return shutil.which('codex')


def require_codex():
    found = codex_bin()
    if not found:
        raise SystemExit('codex executable not found. Put `codex` on PATH or set AI4R_CODEX_BIN to its full path.')
    return found
