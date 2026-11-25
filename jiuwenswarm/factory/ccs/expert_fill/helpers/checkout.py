"""Read a candidate change from an owned llama.cpp checkout without writing to it. Stdlib + git.

The verifier never writes inside the checkout: pre-images come from `git show BASE:path` (BASE is HEAD
unless the caller names another commit), the candidate patch from diff_path or from the working tree
(tracked and untracked changes against BASE), and any tree it runs is exported with `git archive BASE`
into a scratch directory outside the checkout.

The rules judge only the change under review. When the checkout also holds an earlier node's change that is
not committed, the caller passes it as carried_diff: working-tree files whose content is exactly BASE plus
that patch are attributed to it, kept out of the review and still exported, so the scratch tree is the
working tree. Committing the earlier change (it is then in BASE) or passing diff_path does the same.
"""
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import patchlib


def git(checkout, *args, data=None, accepted=(0,)):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(checkout), *args], input=data,
                            capture_output=True)
    if result.returncode not in accepted:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise ValueError(f"git {args[0]} exited {result.returncode}: {detail}")
    return result.stdout


def resolve(checkout, base=None):
    """(checkout root, base commit sha). base defaults to HEAD."""
    checkout = Path(checkout).expanduser().resolve()
    top = Path(os.fsdecode(git(checkout, "rev-parse", "--show-toplevel")).strip()).resolve()
    if top != checkout:
        raise ValueError(f"checkout must be the root of the Git working tree ({top})")
    head = git(checkout, "rev-parse", "--verify", f"{base or 'HEAD'}^{{commit}}").decode().strip()
    return checkout, head


def working_diff(checkout, base="HEAD"):
    options = ("--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "--src-prefix=a/", "--dst-prefix=b/")
    patch = git(checkout, "diff", *options, base, "--")
    for path in git(checkout, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if path:
            patch += git(checkout, "diff", "--no-index", *options, "--", "/dev/null", os.fsdecode(path),
                         accepted=(0, 1))
    return patch


def candidate_patch(checkout, diff_path=None, base="HEAD"):
    """(patch text, mode) where mode is 'diff_path' or 'working'."""
    if diff_path:
        return Path(diff_path).expanduser().read_bytes().decode("utf-8", errors="replace"), "diff_path"
    return working_diff(checkout, base).decode("utf-8", errors="replace"), "working"


def head_text(checkout, path, base="HEAD"):
    """BASE content of path as text, or None when BASE has no such file."""
    if not git(checkout, "ls-tree", base, "--", path):
        return None
    return git(checkout, "show", f"{base}:{path}").decode("utf-8", errors="replace")


def review_change(checkout, diff_path=None, base=None, carried_diff=None):
    """The change under review, scoped away from an earlier node's carried change.

    Returns dict(checkout, head, mode, files, post, pre, carried, carried_post): files/post are the reviewed file
    patches and their post-images; carried lists the paths attributed to carried_diff and carried_post their
    post-images (exported with the reviewed change). Raises ValueError or patchlib.PatchError."""
    checkout, head = resolve(checkout, base)
    cache = {}

    def pre(path):
        if path not in cache:
            cache[path] = head_text(checkout, path, head)
        return cache[path]
    patch, mode = candidate_patch(checkout, diff_path, head)
    if not patch.strip():
        raise ValueError("there is no change to check")
    files = patchlib.parse_patch(patch)
    post = patchlib.post_images(files, pre)
    carried, carried_post = [], {}
    if carried_diff:
        prior = patchlib.parse_patch(Path(carried_diff).expanduser().read_text(encoding="utf-8", errors="replace"))
        prior_post = patchlib.post_images(prior, pre)
        prior_deleted = {fp["old"] for fp in prior if fp["deleted"]}
        keep = []
        for fp in files:
            path = fp["new"] or fp["old"]
            same = (fp["deleted"] and path in prior_deleted) or (
                not fp["deleted"] and path in prior_post and post.get(fp["new"]) == prior_post[path])
            if same:
                carried.append(path)
                if not fp["deleted"]:
                    carried_post[path] = prior_post[path]
            else:
                keep.append(fp)
        files = keep
        post = {k: v for k, v in post.items() if k not in carried_post}
        if not files:
            raise ValueError(f"the only changes are the carried change ({sorted(carried)}): nothing new to check")
    return dict(checkout=checkout, head=head, mode=mode, files=files, post=post, pre=pre, carried=sorted(carried),
                carried_post=carried_post)


def export_tree(checkout, dest, paths=(), post=None, base="HEAD"):
    """git archive BASE [paths] into dest (outside the checkout), then write post-images over it."""
    dest = Path(dest)
    checkout = Path(checkout).resolve()
    if dest.resolve() == checkout or checkout in dest.resolve().parents:
        raise ValueError("the scratch tree must be outside the checkout")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    data = git(checkout, "archive", "--format=tar", base, *paths)
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
