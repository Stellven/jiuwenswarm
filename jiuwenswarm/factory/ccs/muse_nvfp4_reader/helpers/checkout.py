"""Read a candidate change from an owned llama.cpp checkout without writing to it. Stdlib + git.

The verifier never writes inside the checkout: pre-images come from `git show HEAD:path`, the candidate
patch from diff_path or from the working tree (tracked and untracked changes against HEAD), and any tree
it runs is exported with `git archive HEAD` into a scratch directory outside the checkout.
"""
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


def git(checkout, *args, data=None, accepted=(0,)):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(checkout), *args], input=data,
                            capture_output=True)
    if result.returncode not in accepted:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise ValueError(f"git {args[0]} exited {result.returncode}: {detail}")
    return result.stdout


def resolve(checkout):
    checkout = Path(checkout).expanduser().resolve()
    top = Path(os.fsdecode(git(checkout, "rev-parse", "--show-toplevel")).strip()).resolve()
    if top != checkout:
        raise ValueError(f"checkout must be the root of the Git working tree ({top})")
    head = git(checkout, "rev-parse", "HEAD").decode().strip()
    return checkout, head


def working_diff(checkout):
    options = ("--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "--src-prefix=a/", "--dst-prefix=b/")
    patch = git(checkout, "diff", *options, "HEAD", "--")
    for path in git(checkout, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if path:
            patch += git(checkout, "diff", "--no-index", *options, "--", "/dev/null", os.fsdecode(path),
                         accepted=(0, 1))
    return patch


def candidate_patch(checkout, diff_path=None):
    """(patch text, mode) where mode is 'diff_path' or 'working'."""
    if diff_path:
        return Path(diff_path).expanduser().read_bytes().decode("utf-8", errors="replace"), "diff_path"
    return working_diff(checkout).decode("utf-8", errors="replace"), "working"


def head_text(checkout, path):
    """HEAD content of path as text, or None when HEAD has no such file."""
    if not git(checkout, "ls-tree", "HEAD", "--", path):
        return None
    return git(checkout, "show", f"HEAD:{path}").decode("utf-8", errors="replace")


def export_tree(checkout, dest, paths=(), post=None):
    """git archive HEAD [paths] into dest (outside the checkout), then write post-images over it."""
    dest = Path(dest)
    checkout = Path(checkout).resolve()
    if dest.resolve() == checkout or checkout in dest.resolve().parents:
        raise ValueError("the scratch tree must be outside the checkout")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    data = git(checkout, "archive", "--format=tar", "HEAD", *paths)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:  # Python < 3.12
            tar.extractall(dest)
    for path, text in (post or {}).items():
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return dest


_CAP = {}


def capped(command, mem_cap="16G", nice=10):
    """Prefix a command with nice and, on Linux with a user systemd, a cgroup memory cap (no swap).
    Returns (command, note). Never loads anything uncapped silently: the note says when no cap applies."""
    if os.name != "posix":
        return list(command), "no cgroup cap on this platform"
    prefix = []
    if mem_cap and str(mem_cap).lower() != "none":
        if "ok" not in _CAP:
            probe = shutil.which("systemd-run") and subprocess.run(
                ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=64M", "true"], capture_output=True)
            _CAP["ok"] = bool(probe) and probe.returncode == 0
        if _CAP["ok"]:
            prefix = ["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={mem_cap}", "-p", "MemorySwapMax=0"]
    note = f"cgroup MemoryMax={mem_cap}" if prefix else "systemd-run --user unavailable: ran without a cgroup cap"
    if nice and shutil.which("nice"):
        prefix += ["nice", "-n", str(nice)]
    return prefix + list(command), note
