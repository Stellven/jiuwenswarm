"""Read-only static verification for a llama.cpp placement planner change."""
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

STAGE = "native CC execution"
ENV_GATE = "LLAMA_PLACEMENT_PLAN"
MARKERS = tuple(
    f"weight_placement_planner: {suffix}" for suffix in ("active", "inactive (", "stats")
)
ALLOWED = {
    "common/arg.cpp",
    "common/common.cpp",
    "common/common.h",
    "src/CMakeLists.txt",
    "src/llama-model.cpp",
    "src/llama-model-loader.cpp",
    "src/llama-placement-plan.cpp",
    "src/llama-placement-plan.h",
    "src/llama-placement-plan-log.h",
    "tests/CMakeLists.txt",
    "tests/test-weight-placement-planner.cpp",
    "scripts/placement_budget.py",
    "scripts/tests/test_placement_budget.py",
}
CPP = {".cc", ".cpp", ".cxx", ".h", ".hpp"}
INCLUDE_DIRS = ("include", "src", "common", "ggml/include", "ggml/src", "vendor", ".")
MISSING_INCLUDE = re.compile(r"fatal error: (.*?): No such file or directory")
COMMENT_OR_LITERAL = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)


def command(cwd, *args, data=None):
    return subprocess.run(args, cwd=cwd, input=data, capture_output=True, check=False)


def diagnostic(process):
    return (process.stderr or process.stdout).decode(errors="replace").strip()[-1500:]


def working_diff(root):
    options = ("--binary", "--no-ext-diff", "--no-textconv", "--no-renames",
               "--src-prefix=a/", "--dst-prefix=b/")
    tracked = command(root, "git", "diff", *options, "HEAD", "--")
    untracked = command(root, "git", "ls-files", "--others", "--exclude-standard", "-z")
    if tracked.returncode or untracked.returncode:
        raise ValueError(diagnostic(tracked) or diagnostic(untracked))
    patches = [tracked.stdout]
    for entry in untracked.stdout.split(b"\0"):
        if entry:
            result = command(root, "git", "diff", "--no-index", *options,
                             "--", "/dev/null", os.fsdecode(entry))
            if result.returncode != 1:
                raise ValueError(diagnostic(result) or "Could not diff an untracked path.")
            patches.append(result.stdout)
    return b"".join(patches)


def inspect_diff(root, patch):
    # Restrict the verifier to ordinary Git text hunks with regular-file modes.
    for line in patch.splitlines():
        if line.startswith((b"rename ", b"copy ", b"old mode ", b"new mode ",
                            b"GIT binary patch", b"Binary files ")):
            raise ValueError("Expected a text patch without renames, copies or mode changes.")
        if line.startswith((b"new file mode ", b"deleted file mode ")) and line.split()[-1] not in {
            b"100644", b"100755",
        }:
            raise ValueError("Only regular files are supported.")

    result = command(root, "git", "apply", "--numstat", "-z", "-", data=patch)
    if result.returncode:
        raise ValueError(diagnostic(result))
    paths = {}
    for entry in result.stdout.rstrip(b"\0").split(b"\0"):
        added, deleted, name = entry.split(b"\t", 2)
        if not added.isdigit() or not deleted.isdigit() or not name:
            raise ValueError("Invalid Git numstat record.")
        path = os.fsdecode(name)
        if path in paths:
            raise ValueError(f"Repeated patch path: {path}")
        paths[path] = None

    sections = re.split(rb"(?m)^diff --git ", patch)[1:]
    if len(sections) != len(paths):
        raise ValueError("Expected one Git diff section per changed path.")
    for path, section in zip(paths, sections):
        paths[path] = bool(re.search(rb"(?m)^new file mode ", section))
    return paths


def source_additions(root, scratch, paths):
    for name in paths:
        if Path(name).suffix not in CPP or not (scratch / name).is_file():
            continue
        # An added line may sit inside an existing block comment. Strip
        # comments from the full candidate before selecting added lines.
        diff = command(scratch, "git", "diff", "--no-index", "--unified=0",
                       "--no-ext-diff", "--no-textconv", "--",
                       str(root / name) if (root / name).is_file() else "/dev/null",
                       str(scratch / name))
        if diff.returncode not in {0, 1}:
            raise ValueError(diagnostic(diff))
        text = (scratch / name).read_text(encoding="utf-8", errors="replace")
        lines = COMMENT_OR_LITERAL.sub(
            lambda match: re.sub(r"[^\n]", " ", match[0]) if match[0].startswith("/") else match[0],
            text,
        ).split("\n")
        for hunk in re.finditer(rb"(?m)^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff.stdout):
            start = int(hunk[1]) - 1
            count = int(hunk[2] or b"1")
            if count:
                yield "\n".join(lines[start:start + count])


def snapshot(root, baseline, source):
    for name in ALLOWED:
        src = root / name
        if not src.resolve().is_relative_to(root):
            raise ValueError(f"Path escapes the checkout: {name}")
        if src.is_symlink():
            raise ValueError(f"Only regular files are supported: {name}")
        if source == "working tree":
            entry = command(root, "git", "ls-tree", "HEAD", "--", name)
            if entry.returncode:
                raise ValueError(diagnostic(entry))
            if not entry.stdout:
                continue
            if not entry.stdout.startswith((b"100644 blob ", b"100755 blob ")):
                raise ValueError(f"Only regular files are supported: {name}")
            blob = command(root, "git", "show", f"HEAD:{name}")
            if blob.returncode:
                raise ValueError(diagnostic(blob))
            content = blob.stdout
        elif src.is_file():
            content = src.read_bytes()
        else:
            continue
        dest = baseline / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        if source == "working tree" and entry.stdout.startswith(b"100755 "):
            dest.chmod(0o755)
        elif source != "working tree":
            shutil.copymode(src, dest)


def default_off(additions, gate):
    # Canonical gate idiom shared with the component specification. Scope and
    # fallback behavior are independently checked at runtime.
    pattern = re.compile(
        r'\bconst\s+char\s*\*\s*(\w+)\s*=\s*(?:std::)?getenv\(\s*"'
        + re.escape(gate)
        + r'"\s*\)\s*;\s*if\s*\(\s*\1\s*&&\s*(?:std::)?strcmp'
          r'\(\s*\1\s*,\s*"1"\s*\)\s*==\s*0\s*\)\s*\{'
    )
    for snippet in additions:
        for match in pattern.finditer(snippet):
            token = next(
                (token for token in COMMENT_OR_LITERAL.finditer(snippet)
                 if token.start() <= match.start() < token.end()),
                None,
            )
            if token is None:
                return True
    return False


def info_markers(additions):
    literals = []
    log_call = re.compile(r'\b(?:LOG_INF|LLAMA_LOG_INFO)\s*\(\s*("(?:\\.|[^"\\])*")')
    for snippet in additions:
        for match in log_call.finditer(snippet):
            if not any(token.start() <= match.start() < token.end()
                       for token in COMMENT_OR_LITERAL.finditer(snippet)):
                literals.append(match[1])
    return literals


def syntax_checks(root, scratch, paths, report):
    units = [path for path, is_new in paths.items() if is_new and Path(path).suffix in CPP]
    compiler = shutil.which("g++")
    if not units or compiler is None:
        report("new_cpp_syntax", "skipped", "No new C++ files." if not units else "g++ unavailable.", "compile")
        return
    dirs = [str(base / directory) for base in (scratch, root) for directory in INCLUDE_DIRS]
    flags = [flag for directory in dirs for flag in ("-I", directory)]
    for name in units:
        # Include headers through stdin to compile them as ordinary headers
        # and handle .h files, which g++ would otherwise treat as C headers.
        source = f'#include "{name}"\n'.encode() if Path(name).suffix in {".h", ".hpp"} else None
        result = command(scratch, compiler, "-std=c++17", "-fsyntax-only", *flags,
                         "-x", "c++", "-" if source else str(scratch / name), data=source)
        detail = diagnostic(result)
        missing = MISSING_INCLUDE.search(result.stderr.decode(errors="replace"))
        status = "pass" if result.returncode == 0 else "skipped" if missing else "fail"
        report(f"new_cpp_syntax:{name}", status, detail if status != "pass" else "", "compile")


def verify(inputs):
    checks = []

    def report(name, status, detail="", stage=STAGE):
        checks.append(dict(name=name, status=status, stage=stage, detail=detail))

    def output():
        return {"checks": checks, "done": not any(check["status"] == "fail" for check in checks)}

    try:
        root = Path(inputs["checkout"]).resolve(strict=True)
        root_check = command(root, "git", "rev-parse", "--show-toplevel")
        if root_check.returncode or Path(os.fsdecode(root_check.stdout.rstrip(b"\n"))).resolve() != root:
            raise ValueError("checkout must be the root of a Git working tree")
        provided = inputs.get("diff_path")
        gate = inputs.get("env_gate", ENV_GATE)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", gate):
            raise ValueError("env_gate must be an environment variable name")
        markers = inputs.get("markers", [])
        if not isinstance(markers, list) or any(not isinstance(m, str) or not m for m in markers):
            raise ValueError("markers must be a list of nonempty strings")
        source = "patch" if provided is not None else "working tree"
        patch = Path(provided).read_bytes() if source == "patch" else working_diff(root)
        if not patch.strip():
            raise ValueError("No changes to verify.")
    except (KeyError, OSError, TypeError, ValueError) as error:
        report("input_diff", "fail", str(error))
        return output()

    # Run the check against the supplied tree for an external patch. In
    # working-tree mode the forward preimage is HEAD, not the edited files.
    if source == "patch":
        result = command(root, "git", "apply", "--check", "-", data=patch)
        report("git_apply_check", "fail" if result.returncode else "pass", diagnostic(result))
    try:
        paths = inspect_diff(root, patch)
    except ValueError as error:
        report("diff_paths", "fail", str(error))
        return output()
    report("high_churn_signatures", "info", signature_changes(patch))
    forbidden = sorted(set(paths) - ALLOWED)
    report("allowed_paths", "fail" if forbidden else "pass", ", ".join(forbidden))
    protected = [p for p in forbidden if re.search(r"rout(?:e|er|ing)|sampl", p, re.I)]
    report("router_sampling_untouched", "fail" if protected else "pass", ", ".join(protected))
    if forbidden or any(check["status"] == "fail" for check in checks):
        return output()

    try:
        with tempfile.TemporaryDirectory(prefix="placement-verify-") as temp:
            scratch = Path(temp, "candidate")
            scratch.mkdir()
            initialized = command(scratch, "git", "init", "-q")
            if initialized.returncode:
                raise ValueError(diagnostic(initialized))
            snapshot(root, scratch, source)
            if source == "working tree":
                result = command(scratch, "git", "apply", "--check", "-", data=patch)
                report("git_apply_check", "fail" if result.returncode else "pass", diagnostic(result))
                if result.returncode:
                    return output()
            # Preserve preimage text so the verifier can check which real
            # source lines the patch added even for working-tree input.
            baseline = Path(temp, "preimage")
            shutil.copytree(scratch, baseline, ignore=shutil.ignore_patterns(".git"))
            result = command(scratch, "git", "apply", "-", data=patch)
            if result.returncode:
                raise ValueError(diagnostic(result))
            report("gate_unset_silence", *gate_silence(
                patch, lambda path: read_source(scratch, path), gate, "weight_placement_planner:"
            ))
            additions = list(source_additions(baseline, scratch, paths))
            gate_ok = default_off(additions, gate)
            report("getenv_default_off", "pass" if gate_ok else "fail", gate)
            literals = info_markers(additions)
            for marker in dict.fromkeys((*MARKERS, *markers)):
                report(f"activation_marker:{marker}",
                       "pass" if any(marker in literal for literal in literals) else "fail")
            syntax_checks(root, scratch, paths, report)
    except (OSError, ValueError) as error:
        report("candidate_snapshot", "fail", str(error))
    return output()


def main():
    packet = json.load(sys.stdin)
    if packet.get("capability") != "verify":
        result = {"outcome": "error", "error": {"code": "INVALID_INPUT", "message": "Expected verify"}}
    else:
        result = {"outcome": "ok", "outputs": verify(packet.get("inputs", {}))}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
