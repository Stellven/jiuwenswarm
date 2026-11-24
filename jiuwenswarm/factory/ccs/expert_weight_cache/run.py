"""Static verification of an expert weight cache diff."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from helpers.verify_churn import signature_changes
from helpers.verify_gate import gate_silence, read_source


ENV_GATE = "LLAMA_EXPERT_CACHE"
NATIVE_PROFILE_GATE = "LLAMA_EXPERT_CACHE_NATIVE_PROFILE"
ALLOWED_PATHS = {
    "src/CMakeLists.txt", "src/llama-context.cpp", "src/llama-context.h",
    "src/llama-model.cpp", "src/llama-model.h", "src/llama-expert-fill.h",
    "src/llama-expert-weight-cache.cpp", "src/llama-expert-weight-cache.h",
}
NATIVE_PROFILE_PATHS = {
    "src/CMakeLists.txt", "src/llama-context.cpp", "src/llama-moe-cache.cpp", "src/llama-moe-cache.h",
    "src/llama-expert-cache-profile.cpp", "src/llama-expert-cache-profile.h",
}
STATIC = "native CC execution"


def git(checkout, *args, patch=None, accepted=(0,), env=None):
    command = ["git", "--no-optional-locks", "-C", str(checkout), *args]
    result = subprocess.run(command, input=patch, capture_output=True, env=env)
    if result.returncode not in accepted:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise ValueError(f"git {args[0]} exited {result.returncode}: {detail}")
    return result.stdout


def working_diff(checkout):
    options = ("--binary", "--no-ext-diff", "--no-textconv", "--no-renames",
               "--src-prefix=a/", "--dst-prefix=b/")
    patch = git(checkout, "diff", *options, "HEAD", "--")
    for path in git(checkout, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if path:
            patch += git(checkout, "diff", "--no-index", *options, "--", "/dev/null",
                         os.fsdecode(path), accepted=(0, 1))
    return patch


def patch_paths(checkout, patch):
    stats = git(checkout, "apply", "--numstat", "-z", "-", patch=patch)
    paths = set()
    for record in stats.split(b"\0")[:-1]:
        added, removed, path = record.split(b"\t", 2)
        if not path or added == b"-" or removed == b"-":
            raise ValueError("Expected a text patch with regular source paths")
        paths.add(os.fsdecode(path))
    if not paths:
        raise ValueError("Expected a nonempty patch")
    unsafe = rb"^(?:rename |copy |old mode |new mode |deleted file mode |new file mode (?!100644$))"
    if re.search(unsafe, patch, re.MULTILINE):
        raise ValueError("Expected text edits and regular file additions only")
    return paths


def added_hunks(patch):
    """Yield contiguous C++ additions, masking comments in the visible context."""
    source = False
    in_hunk = False
    postimage = []
    added = []
    for line in patch.decode(errors="replace").splitlines():
        if in_hunk and line[:1] in {"+", " ", "-", "\\"}:
            if source and line[0] in {"+", " "}:
                postimage.append(line[1:])
                added.append(line[0] == "+")
            continue
        if postimage:
            yield from source_additions(postimage, added)
            postimage, added = [], []
        if line.startswith("diff --git "):
            source = False
            in_hunk = False
        elif line.startswith("+++ "):
            source = Path(line[4:].split("\t", 1)[0]).suffix in {".cpp", ".h"}
        elif line.startswith("@@ "):
            in_hunk = True
    if postimage:
        yield from source_additions(postimage, added)


def source_additions(postimage, added):
    literals_or_comments = r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|/\*.*?(?:\*/|\Z)|//[^\n]*'''

    def mask(match):
        value = match[0]
        if value.startswith("/"):
            return re.sub(r"[^\n]", " ", value)
        return value

    code = re.sub(literals_or_comments, mask, "\n".join(postimage), flags=re.DOTALL)
    run = []
    for line, is_added in zip(code.split("\n"), added):
        if is_added:
            run.append(line)
        elif run:
            yield "\n".join(run)
            run = []
    if run:
        yield "\n".join(run)


def default_off(hunks, env_gate):
    gate = re.escape(env_gate)
    pattern = (
        rf'^\s*(?:const char\s*\*|auto\s*\*)\s*(\w+)\s*=\s*(?:std::)?getenv\s*\(\s*"{gate}"\s*\)\s*;'
        r'\s*\n\s*const bool\s+\w+\s*=\s*\1\s*!=\s*nullptr\s*&&\s*'
        r'(?:std::)?strcmp\s*\(\s*\1\s*,\s*"1"\s*\)\s*==\s*0\s*;'
    )
    return any(re.search(pattern, hunk, re.MULTILINE) for hunk in hunks)


def added_marker(hunks, marker):
    pattern = rf'^\s*LLAMA_LOG_INFO\s*\(\s*"{re.escape(marker)}'
    return any(re.search(pattern, hunk, re.MULTILINE) for hunk in hunks)


def materialize(scratch, checkout, paths, patch, from_head):
    git(scratch, "init", "-q", "--template=")
    new_paths = []
    for name in sorted(paths):
        dest = scratch / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        source = checkout / name
        if from_head:
            if not git(checkout, "ls-tree", "HEAD", "--", name):
                new_paths.append(name)
                continue
            dest.write_bytes(git(checkout, "show", "HEAD:" + name))
        elif source.is_file():
            shutil.copyfile(source, dest)
        else:
            new_paths.append(name)

    git(scratch, "apply", "--check", "-", patch=patch)
    git(scratch, "apply", "-", patch=patch)
    return new_paths


def syntax_check(scratch, checkout, paths):
    compiler = shutil.which("g++")
    units = [name for name in paths if Path(name).suffix in {".cpp", ".h"}]
    if not units or not compiler:
        return "skipped", "No new C++ units or headers" if not units else "g++ unavailable"

    includes = [scratch / "src", checkout / "src", checkout / "include",
                checkout / "ggml/include", checkout / "ggml/src"]
    options = ["-std=c++17", "-fsyntax-only", *(f"-I{path}" for path in includes)]
    failures, skips, passed = [], [], []
    for name in units:
        # Compile headers via an include to avoid treating them as primary source files.
        cmd = [compiler, *options, "-x", "c++", "-"]
        source = f'#include "{(scratch / name).as_posix()}"\n'
        if name.endswith(".cpp"):
            cmd = [compiler, *options, str(scratch / name)]
            source = None
        result = subprocess.run(cmd, cwd=scratch, input=source, text=True, capture_output=True)
        if result.returncode == 0:
            passed.append(name)
        elif re.search(r"fatal error: .+: No such file or directory", result.stderr):
            skips.append(f"{name}: {result.stderr.strip()}")
        else:
            failures.append(f"{name}: {result.stderr.strip()}")
    detail = {"passed": passed, "missing_headers": skips, "errors": failures}
    if failures:
        return "fail", detail
    return ("skipped" if skips else "pass"), detail


def verify(inputs):
    checks = []

    def record(name, status, detail, stage=STATIC):
        checks.append(dict(name=name, status=status, detail=detail, stage=stage))

    try:
        checkout = Path(inputs["checkout"]).expanduser().resolve()
        if Path(os.fsdecode(git(checkout, "rev-parse", "--show-toplevel")).rstrip()) != checkout:
            raise ValueError("checkout must be the root of the Git working tree")
        env_gate = inputs.get("env_gate", ENV_GATE)
        if env_gate not in (ENV_GATE, NATIVE_PROFILE_GATE):
            raise ValueError(f"env_gate must be {ENV_GATE} or {NATIVE_PROFILE_GATE}")
        native_profile = env_gate == NATIVE_PROFILE_GATE
        allowed = NATIVE_PROFILE_PATHS if native_profile else ALLOWED_PATHS
        report_prefix = "expert_weight_cache_native_profile:" if native_profile else "expert_weight_cache:"
        requested = inputs.get("markers", [])
        if not isinstance(requested, list) or any(not isinstance(item, str) or not item for item in requested):
            raise ValueError("markers must be a list of nonempty strings")
        markers = tuple(dict.fromkeys((*(f"{report_prefix} {label}" for label in ("active", "inactive (", "stats")), *requested)))
        patch_path = inputs.get("diff_path")
        patch = Path(patch_path).expanduser().read_bytes() if patch_path else working_diff(checkout)
        paths = patch_paths(checkout, patch)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        record("patch_input", "fail", str(exc))
        return {"done": False, "checks": checks}

    record("high_churn_signatures", "info", signature_changes(patch))
    forbidden = sorted(paths - allowed)
    record("allowed_paths", "fail" if forbidden else "pass", forbidden or sorted(paths))
    if native_profile:
        native_bank_source = "src/llama-moe-cache.cpp"
        record("native_bank_source", "pass" if native_bank_source in paths else "fail", native_bank_source)
    protected = [path for path in forbidden if re.search(r"router|rout|sampl|graph|models/", path)]
    record("router_sampling_scope", "fail" if protected else "pass", protected)

    applicable = False
    try:
        if patch_path:
            git(checkout, "apply", "--check", "-", patch=patch)
        else:
            # The candidate is already in the working tree. Use a private index
            # loaded from HEAD for the applicability check.
            with tempfile.TemporaryDirectory(prefix="expert-weight-cache-") as temp:
                index = Path(temp) / "index"
                env = {**os.environ, "GIT_INDEX_FILE": str(index)}
                git(checkout, "-c", "core.splitIndex=false", "read-tree", "HEAD", env=env)
                git(checkout, "apply", "--cached", "--check", "-", patch=patch, env=env)
        applicable = True
        record("git_apply_check", "pass", "Checkout" if patch_path else "Checkout HEAD")
    except (OSError, ValueError) as exc:
        record("git_apply_check", "fail", str(exc))

    hunks = list(added_hunks(patch))
    has_gate = default_off(hunks, env_gate)
    record("env_gate_default_off", "pass" if has_gate else "fail", env_gate)
    missing = [marker for marker in markers if not added_marker(hunks, marker)]
    record("activation_markers", "fail" if missing else "pass", missing or list(markers))

    if applicable and not forbidden:
        try:
            with tempfile.TemporaryDirectory(prefix="expert-weight-cache-") as temp:
                scratch = Path(temp)
                new_paths = materialize(scratch, checkout, paths, patch, from_head=not patch_path)
                record("gate_unset_silence", *gate_silence(
                    patch, lambda path: read_source(scratch, path), env_gate, report_prefix
                ))
                status, detail = syntax_check(scratch, checkout, new_paths)
        except (OSError, ValueError) as exc:
            status, detail = "fail", str(exc)
    else:
        status, detail = "skipped", "Requires an applicable patch within the allowlist"
    # A skipped probe has no compiler evidence.
    record("new_files_syntax", status, detail, STATIC if status == "skipped" else "compile")
    return {"done": all(check["status"] != "fail" for check in checks), "checks": checks}


def main():
    packet = json.load(sys.stdin)
    if packet.get("capability") != "verify":
        print(json.dumps({"outcome": "error", "error": {
            "code": "INVALID_INPUT", "message": "Expected the verify capability"}}))
        return
    print(json.dumps({"outcome": "ok", "outputs": verify(packet["inputs"])}))


if __name__ == "__main__":
    main()
