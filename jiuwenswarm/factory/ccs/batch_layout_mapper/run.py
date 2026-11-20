"""Read-only static verification of a proposed batch layout mapper diff."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from helpers.verify_gate import gate_silence, read_source


ENV_GATE = "LLAMA_BATCH_LAYOUT"
MARKERS = tuple(
    f"batch_layout_mapper: {kind}"
    for kind in ("active", "inactive (", "stats", "layout")
)
ALLOWED = {"tools/server/server-context.cpp", "src/llama-batch-layout.h"}
NATIVE = "native CC execution"
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", re.M)
CPP_COMMENTS = re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|//[^\n]*|/\*.*?\*/', re.S)


def git(checkout, *args, patch=None, env=None):
    return subprocess.run(
        ["git", "-C", str(checkout), *args],
        input=patch, capture_output=True, env=env, check=False,
    )


def diagnostic(result):
    return (result.stderr or result.stdout).decode(errors="replace").strip()


def working_patch(checkout):
    diff = git(checkout, "diff", "--binary", "--no-ext-diff", "--no-textconv",
               "--no-renames", "--src-prefix=a/", "--dst-prefix=b/", "HEAD", "--")
    untracked = git(checkout, "ls-files", "--others", "--exclude-standard", "-z")
    for result in (diff, untracked):
        if result.returncode != 0:
            raise ValueError(diagnostic(result))
    chunks = [diff.stdout]
    for path in untracked.stdout.split(b"\0")[:-1]:
        # A resulting patch with an out-of-scope untracked path must fail the
        # scope check. Do not open that path to obtain its contents.
        if os.fsdecode(path) not in ALLOWED:
            raise ValueError(f"Untracked path outside component scope: {os.fsdecode(path)}")
        addition = git(checkout, "diff", "--no-index", "--binary", "--no-ext-diff",
                       "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/",
                       "--", "/dev/null", os.fsdecode(path))
        if addition.returncode != 1:
            raise ValueError(diagnostic(addition) or f"No diff for {os.fsdecode(path)}")
        chunks.append(addition.stdout)
    return b"".join(chunks)


def added_source(patch):
    """Collect hunk additions by file and complete contents of new files."""
    additions = []
    new_files = {}
    for section in re.split(r"(?m)^diff --git ", patch.decode(errors="replace")):
        hunks = HUNK.split(section)
        if len(hunks) == 1:
            continue
        lines = [
            line[1:] for hunk in hunks[1:] for line in hunk.split("\n") if line.startswith("+")
        ]
        additions.append("\n".join(lines))
        if re.search(r"(?m)^--- /dev/null$", hunks[0]):
            match = re.search(r"(?m)^\+\+\+ b/([^\t\n]+)", hunks[0])
            if match:
                new_files[match[1]] = "\n".join(lines) + "\n"
    return additions, new_files


def has_default_off(source, gate):
    code = CPP_COMMENTS.sub(lambda match: match[1] or " ", source)
    read = re.search(
        r'\bconst\s+char\s*\*\s*(\w+)\s*=\s*(?:std::)?getenv\s*\(\s*"'
        + re.escape(gate) + r'"\s*\)\s*;', code,
    )
    if not read:
        return False
    value = re.escape(read[1])
    return bool(re.search(
        rf'\b{value}\s*!=\s*nullptr\s*&&\s*(?:std::)?strcmp\s*'
        rf'\(\s*{value}\s*,\s*"1"\s*\)\s*==\s*0\b', code[read.end():],
    ))


def syntax_check(checkout, new_files, scratch, add):
    compiler = shutil.which("g++")
    if not compiler or not new_files:
        add("new_file_syntax", "skipped", "g++ unavailable" if not compiler else "No new files", "compile")
        return

    for path, source in new_files.items():
        file = scratch / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(source, encoding="utf-8")

    includes = [
        root / folder
        for root in (scratch, checkout)
        for folder in ("src", "include", "common", "ggml/include", "tools/server", "tools/mtmd", "vendor")
    ]
    include_args = [arg for path in includes if path.is_dir() for arg in ("-I", str(path))]
    for path in new_files:
        file = scratch / path
        args = ["-include", str(file), "-"] if file.suffix == ".h" else [str(file)]
        result = subprocess.run(
            [compiler, "-std=c++17", "-fsyntax-only", "-x", "c++", *include_args, *args],
            cwd=scratch, input=b"", capture_output=True, check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
        detail = diagnostic(result)
        missing_header = re.search(r"fatal error: .+: No such file or directory", detail)
        errors = [line for line in detail.splitlines() if "error:" in line]
        status = "pass" if result.returncode == 0 else "fail"
        if missing_header and len(errors) == 1:
            status = "skipped"
        add(f"new_file_syntax:{path}", status, detail or "g++ -fsyntax-only", "compile")


def silence_postimage(checkout, scratch, patch, paths):
    """Stage explicit-patch postimages without changing the checkout."""
    scratch.mkdir()
    init = git(scratch, "init", "-q", "--template=")
    if init.returncode:
        raise ValueError(diagnostic(init))
    for path in paths:
        source = checkout / path
        if source.is_file():
            dest = scratch / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    applied = git(scratch, "apply", "-", patch=patch)
    if applied.returncode:
        raise ValueError(diagnostic(applied))


def verify(inputs):
    checks = []

    def add(name, status, detail, stage=NATIVE):
        checks.append(dict(name=name, status=status, stage=stage, detail=detail))

    def result():
        return {"checks": checks, "done": bool(checks) and all(c["status"] != "fail" for c in checks)}

    try:
        checkout = Path(inputs["checkout"]).expanduser().resolve(strict=True)
        top = git(checkout, "rev-parse", "--show-toplevel")
        if top.returncode or Path(os.fsdecode(top.stdout.rstrip(b"\n"))).resolve() != checkout:
            raise ValueError("checkout must be the root of a Git working tree")
        gate = inputs.get("env_gate", ENV_GATE)
        if gate != ENV_GATE:
            raise ValueError(f"env_gate must be {ENV_GATE}")
        markers = inputs.get("markers", [])
        if not isinstance(markers, list) or not all(isinstance(m, str) and m for m in markers):
            raise ValueError("markers must be a list of nonempty strings")
        diff_path = inputs.get("diff_path")
        patch = Path(diff_path).expanduser().read_bytes() if diff_path else working_patch(checkout)
        with TemporaryDirectory(prefix="batch-layout-") as temp:
            scratch = Path(temp)
            if diff_path:
                apply = git(checkout, "apply", "--check", "-", patch=patch)
            else:
                # Compare staged, unstaged and untracked changes with HEAD.
                # A temporary index avoids applying an existing change twice.
                env = {**os.environ, "GIT_INDEX_FILE": str(scratch / "index")}
                base = git(checkout, "read-tree", "HEAD", env=env)
                if base.returncode:
                    raise ValueError(diagnostic(base))
                apply = git(checkout, "apply", "--cached", "--check", "-", patch=patch, env=env)
            add("apply_check", "fail" if apply.returncode else "pass",
                diagnostic(apply) or ("Diff applies to checkout" if diff_path else "Diff applies to HEAD"))

            paths_result = git(checkout, "apply", "--numstat", "-z", "-", patch=patch)
            summary = git(checkout, "apply", "--summary", "-", patch=patch)
            unsupported_changes = [
                line.strip()
                for line in summary.stdout.decode(errors="replace").splitlines()
                if not line.strip().startswith(("create mode 100644 ", "delete mode 100644 "))
            ]
            paths = paths_result.stdout.split(b"\0")[:-1]
            touched = set()
            for record in paths:
                # An empty pathname precedes rename/copy paths in Git's -z format.
                fields = record.split(b"\t", 2)
                if len(fields) != 3 or not fields[2] or b"-" in fields[:2]:
                    break
                touched.add(os.fsdecode(fields[2]))
            else:
                if paths_result.returncode == 0 and summary.returncode == 0 and touched:
                    forbidden = touched - ALLOWED
                    violations = [*sorted(forbidden), *unsupported_changes]
                    add("allowed_paths", "fail" if violations else "pass",
                        ", ".join(violations or sorted(touched)))
                    protected = [path for path in forbidden if re.search(r"rout|sampl", path, re.I)]
                    add("router_and_sampling", "fail" if protected else "pass",
                        ", ".join(sorted(protected)) or "No router or sampling file changes")
            if not any(check["name"] == "allowed_paths" for check in checks):
                add("allowed_paths", "fail",
                    diagnostic(paths_result) or diagnostic(summary)
                    or "Expected a nonempty text diff without renames or copies")

            additions, new_files = added_source(patch)
            gate_ok = any(has_default_off(source, gate) for source in additions)
            gate_detail = (
                f"Found getenv({gate}) and the null-guarded exact comparison with 1"
                if gate_ok else f"Missing getenv({gate}) or the null-guarded exact comparison with 1"
            )
            add("default_off_getenv", "pass" if gate_ok else "fail",
                gate_detail)
            missing = [marker for marker in dict.fromkeys((*MARKERS, *markers))
                       if not any(marker in line for source in additions for line in source.splitlines())]
            add("activation_markers", "fail" if missing else "pass",
                "Missing from added lines: " + ", ".join(missing) if missing else "All required strings present")
            if apply.returncode == 0 and any(
                c["name"] == "allowed_paths" and c["status"] == "pass" for c in checks
            ):
                try:
                    postimage = checkout
                    if diff_path:
                        postimage = scratch / "postimage"
                        silence_postimage(checkout, postimage, patch, touched)
                    add("gate_unset_silence", *gate_silence(
                        patch, lambda path: read_source(postimage, path), gate, "batch_layout_mapper:"
                    ))
                except (OSError, ValueError) as exc:
                    add("gate_unset_silence", "inconclusive", str(exc))
            if result()["done"]:
                syntax_check(checkout, new_files, scratch, add)
            else:
                add("new_file_syntax", "skipped", "A static check failed", "compile")
    except (KeyError, OSError, TypeError, ValueError) as exc:
        add("verification_input", "fail", str(exc))
    return result()


def main():
    packet = json.load(sys.stdin)
    if packet.get("capability") != "verify":
        response = {"outcome": "error", "error": {"code": "INVALID_INPUT", "message": "Expected verify"}}
    else:
        response = {"outcome": "ok", "outputs": verify(packet.get("inputs", {}))}
    print(json.dumps(response))


if __name__ == "__main__":
    main()
