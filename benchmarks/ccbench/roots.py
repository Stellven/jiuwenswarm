"""Environment roots shared by the ccbench harnesses.

AI4R_CODE_ROOT   product repo (default: the repo that contains this file)
AI4R_BENCH_DATA  old evidence root: traps/, stored baselines, native sessions
                 (default: ~/huawei/outputs/cc-sweep-20261026)
AI4R_CODEX_BIN   codex executable (default: `codex` on PATH)
AI4R_T2_FIXTURES luna T2 (inputguard) fixture folder: <fixture>/{task.txt, inputs/, fault.json}
                 (default: ~/huawei/outputs/rebench-20261028/B-theirs/fixtures)
AI4R_PRODUCT_COMMIT / AI4R_PRODUCT_DIRTY
                 set by scripts/ai4r-bench from the host checkout (a container may have no usable git)
"""
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def code_root():
    value = os.environ.get('AI4R_CODE_ROOT')
    return Path(value) if value else HERE.parents[1]


def bench_data():
    value = os.environ.get('AI4R_BENCH_DATA')
    return Path(value) if value else Path.home() / 'huawei' / 'outputs' / 'cc-sweep-20261026'


def t2_fixtures():
    value = os.environ.get('AI4R_T2_FIXTURES')
    return Path(value) if value else Path.home() / 'huawei' / 'outputs' / 'rebench-20261028' / 'B-theirs' / 'fixtures'


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


def product_commit():
    """{'commit': sha or None, 'dirty': bool or None} of AI4R_CODE_ROOT. dirty = tracked files differ from HEAD."""
    commit, dirty = os.environ.get('AI4R_PRODUCT_COMMIT'), os.environ.get('AI4R_PRODUCT_DIRTY')
    if commit:
        return {'commit': commit, 'dirty': {'1': True, '0': False}.get(dirty)}
    try:
        root = str(code_root())
        commit = subprocess.run(['git', '-C', root, 'rev-parse', 'HEAD'], capture_output=True, timeout=30, check=True).stdout.decode().strip()
        status = subprocess.run(['git', '-C', root, 'status', '--porcelain', '--untracked-files=no'], capture_output=True, timeout=60, check=True)
        return {'commit': commit, 'dirty': bool(status.stdout.strip())}
    except (OSError, subprocess.SubprocessError):
        return {'commit': None, 'dirty': None}
