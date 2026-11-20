"""Read-only static verification of the expert demand predictor candidate."""
from __future__ import annotations

from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from helpers.verify_churn import signature_changes
from helpers.verify_gate import gate_silence

GATE = "LLAMA_EXPERT_PREDICT"
LOG_NAME = "expert_demand_predictor"
MARKERS = tuple(f"{LOG_NAME}: {event}" for event in ("active ", "inactive (", "stats"))
ALLOWED = {
    "src/CMakeLists.txt",
    "src/llama-context.cpp",
    "src/llama-context.h",
    "src/llama-expert-fill.h",  # Only on an existing Fill integration.
    "src/llama-expert-predict.cpp",
    "src/llama-expert-predict.h",
    "src/llama-model.cpp",
    "src/llama-model.h",
}
CXX_SUFFIXES = {".cpp", ".h"}
UNSUPPORTED_OPERATIONS = re.compile(
    rb"^(?:rename (?:from|to) |copy (?:from|to) |deleted file mode |"
    rb"old mode |new mode |new file mode (?!100644$)|GIT binary patch$|Binary files )",
    re.MULTILINE,
)
CPP_TOKEN = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
)
MANDATORY = ("apply_check", "allowed_paths", "router_sampling_untouched",
             "default_off_env_gate", "activation_markers")


def git(directory, *args, data=None, isolated=False):
    env = dict(os.environ)
    if isolated:
        env = {key: value for key, value in env.items() if not key.startswith("GIT_")}
        env["GIT_CEILING_DIRECTORIES"] = str(directory.parent)
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(directory), *args],
        input=data, capture_output=True, check=False, env=env,
    )


def diagnostic(result):
    return result.stderr.decode("utf-8", "replace").strip()


def successful(result):
    if result.returncode:
        raise ValueError(diagnostic(result) or f"git exited {result.returncode}")
    return result.stdout


def worktree_patch(checkout):
    patch = successful(git(
        checkout, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
        "--src-prefix=a/", "--dst-prefix=b/", "--binary", "HEAD", "--",
    ))
    untracked = successful(git(checkout, "ls-files", "--others", "--exclude-standard", "-z"))
    for entry in filter(None, untracked.split(b"\0")):
        path = os.fsdecode(entry)
        result = git(
            checkout, "diff", "--no-index", "--no-ext-diff", "--no-textconv",
            "--src-prefix=a/", "--dst-prefix=b/", "--binary", "--", "/dev/null", path,
        )
        if result.returncode == 1:
            patch += result.stdout
        else:
            patch += successful(result)
    return patch


def strip_comments(source):
    return CPP_TOKEN.sub(
        lambda match: re.sub(r"[^\n]", " ", match[0]) if match[0].startswith("/") else match[0],
        source,
    )


def has_default_off_gate(source, gate):
    # Recognize the capsule's null-guarded exact-value idiom, with either C++
    # strcmp or string_view. Runtime acceptance still exercises actual control flow.
    keep = {'"1"', '""', f'"{gate}"'}
    source = CPP_TOKEN.sub(lambda match: match[0] if match[0] in keep else '""', source)
    gate_read = r'\b(?:std::)?getenv\s*\(\s*"' + re.escape(gate) + r'"\s*\)'
    assignments = re.finditer(r'\b(\w+)\s*=\s*' + gate_read + r'\s*;', source)
    for assignment in assignments:
        name = re.escape(assignment[1])
        exact = (
            rf'\b{name}\s*(?:!=\s*(?:nullptr|NULL)\s*)?&&\s*'
            rf'(?:std::)?strcmp\s*\(\s*{name}\s*,\s*"1"\s*\)\s*==\s*0\b'
        )
        view = rf'\bstd::string_view\s*\(\s*{name}\s*\?\s*{name}\s*:\s*""\s*\)\s*==\s*"1"'
        enabled = rf"(?:{exact}|{view})"
        direct_use = rf"(?:\breturn\s+|(?<![=!<>])=\s*){enabled}\s*;|\bif\s*\(\s*{enabled}\s*\)"
        if re.search(direct_use, source[assignment.end():].split("}", 1)[0]):
            return True
    return False


def added_cpp_lines(patch, preimages, postimages):
    """Find real additions at their applied position, including shifted hunks."""
    added = {
        line[1:].decode("utf-8", "replace")
        for line in patch.splitlines()
        if line.startswith(b"+") and not line.startswith(b"+++ ")
    }
    for path, source in postimages.items():
        before = preimages[path].splitlines()
        after = source.splitlines()
        code = strip_comments(source).splitlines()
        for operation, _, _, first, last in SequenceMatcher(None, before, after).get_opcodes():
            if operation in {"insert", "replace"}:
                yield from (code[index] for index in range(first, last) if after[index] in added)


def syntax_checks(checkout, scratch, paths, record):
    compiler = shutil.which("g++")
    if not paths or not compiler:
        record("cxx_syntax", "skipped", "No C++ units in scope or g++ unavailable.", "compile")
        return
    includes = [scratch / "src", checkout / "src", checkout / "include",
                checkout / "ggml/include", checkout / "ggml/src"]
    flags = ["-std=c++17", "-fsyntax-only", *(f"-I{path}" for path in includes)]
    for path in paths:
        unit = scratch / path
        args = ["-x", "c++", "-include", str(unit), "-"] if unit.suffix == ".h" else [str(unit)]
        result = subprocess.run([compiler, *flags, *args], cwd=scratch, input=b"",
                                capture_output=True, check=False, env={**os.environ, "LC_ALL": "C"})
        message = diagnostic(result)
        missing = re.search(r"fatal error: (.+?): No such file or directory", message)
        known_headers = {"ggml.h", "ggml-alloc.h", "ggml-backend.h", "ggml-cpp.h",
                         "ggml-cpu.h", "ggml-opt.h", "gguf.h", "llama.h", "build-info.h"}
        if result.returncode == 0:
            status, message = "pass", "g++ -std=c++17 -fsyntax-only"
        elif missing and missing[1] in known_headers:
            status = "skipped"
        else:
            status = "fail"
        record(f"cxx_syntax:{path}", status, message[:2000], "compile")


def verify(inputs):
    checks = []

    def record(name, status, detail, stage="native CC execution"):
        checks.append(dict(name=name, status=status, stage=stage, detail=detail))

    try:
        checkout = Path(inputs["checkout"]).expanduser().resolve(strict=True)
        if not checkout.is_dir() or Path(os.fsdecode(successful(
            git(checkout, "rev-parse", "--show-toplevel")).rstrip(b"\n"))).resolve() != checkout:
            raise ValueError("checkout must be the root of an owned Git working tree")
        gate = inputs.get("env_gate", GATE)
        if gate != GATE:
            raise ValueError(f"env_gate must be {GATE}")
        requested = inputs.get("markers", [])
        if not isinstance(requested, list) or any(not isinstance(m, str) or not m for m in requested):
            raise ValueError("markers must be a list of nonempty literal strings")
        markers = list(dict.fromkeys([*MARKERS, *requested]))
        diff_path = inputs.get("diff_path")
        patch = Path(diff_path).expanduser().read_bytes() if diff_path is not None else worktree_patch(checkout)
        changes = successful(git(checkout, "apply", "--numstat", "-z", "-", data=patch))
        paths = []
        for change in filter(None, changes.split(b"\0")):
            _, _, path = change.split(b"\t", 2)
            paths.append(os.fsdecode(path))
    except (KeyError, OSError, TypeError, ValueError) as error:
        record("candidate_input", "fail", str(error))
    else:
        record("high_churn_signatures", "info", signature_changes(patch))
        forbidden = sorted(set(paths) - ALLOWED)
        unsupported = not paths or len(set(paths)) != len(paths) or UNSUPPORTED_OPERATIONS.search(patch)
        if forbidden or unsupported:
            record("allowed_paths", "fail",
                   f"Out of scope: {', '.join(forbidden)}" if forbidden else
                   "Expected one regular text edit or addition per path.")
        else:
            record("allowed_paths", "pass", ", ".join(paths))
        protected = [path for path in forbidden if (
            path.startswith("src/models/") or
            re.search(r"graph|rout|sampl|ggml", path, re.IGNORECASE)
        )]
        record("router_sampling_untouched", "fail" if protected else "pass",
               ", ".join(protected) or "Protected paths unchanged.")
        try:
            with tempfile.TemporaryDirectory(prefix="expert-demand-predictor-") as directory:
                scratch = Path(directory)
                if diff_path is not None:
                    result = git(checkout, "apply", "--check", "-", data=patch)
                    record("apply_check", "pass" if not result.returncode else "fail",
                           diagnostic(result) or "Patch applies to the supplied checkout.")
                if not forbidden and not unsupported and not any(
                    check["status"] == "fail" for check in checks
                ):
                    for path in paths:
                        target = scratch / path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if diff_path is None:
                            entry = successful(git(checkout, "ls-tree", "HEAD", "--", path))
                            if not entry:
                                continue
                            if not entry.startswith((b"100644 blob ", b"100755 blob ")):
                                raise ValueError(f"Expected a regular HEAD file at {path}")
                            target.write_bytes(successful(git(checkout, "show", f"HEAD:{path}")))
                        else:
                            source = checkout / path
                            if source.exists() or source.is_symlink():
                                if source.is_symlink() or not source.is_file():
                                    raise ValueError(f"Expected a regular checkout file at {path}")
                                shutil.copyfile(source, target)
                    if diff_path is None:
                        result = git(scratch, "apply", "--check", "-", data=patch, isolated=True)
                        record("apply_check", "pass" if not result.returncode else "fail",
                               diagnostic(result) or "Working-tree patch applies to the HEAD versions.")
                    if result.returncode == 0:
                        cxx_paths = [path for path in paths if Path(path).suffix in CXX_SUFFIXES]
                        preimages = {
                            path: (scratch / path).read_text() if (scratch / path).exists() else ""
                            for path in cxx_paths
                        }
                        successful(git(scratch, "apply", "-", data=patch, isolated=True))
                        postimages = {path: (scratch / path).read_text() for path in cxx_paths}
                        record("gate_unset_silence", *gate_silence(
                            patch, postimages.get, gate, LOG_NAME + ":"
                        ))
                        gate_found = any(has_default_off_gate(strip_comments(source), gate)
                                         for source in postimages.values())
                        record("default_off_env_gate", "pass" if gate_found else "fail",
                               "Found guarded getenv and exact enable value." if gate_found else
                               f"Expected guarded getenv({gate}) and exact enable value 1 in candidate C++.")
                        marker_literals = [
                            token[0][1:-1] for line in added_cpp_lines(patch, preimages, postimages)
                            for token in CPP_TOKEN.finditer(line) if token[0].startswith('"')
                        ]
                        missing = [marker for marker in markers if not any(
                            marker in literal for literal in marker_literals
                        )]
                        record("activation_markers", "fail" if missing else "pass",
                               f"Missing from added C++ string literals: {missing!r}" if missing else
                               "All required literals appear on added lines.")
                        syntax_checks(checkout, scratch, cxx_paths, record)
        except (OSError, ValueError) as error:
            record("candidate_inspection", "fail", str(error))

    seen = {check["name"] for check in checks}
    for name in MANDATORY:
        if name not in seen:
            record(name, "skipped", "Candidate could not be inspected for this check.")
    if not any(check["stage"] == "compile" for check in checks):
        record("cxx_syntax", "skipped", "Candidate could not be staged for syntax checking.", "compile")
    return {"done": all(check["status"] != "fail" for check in checks), "checks": checks}


def main():
    packet = json.load(sys.stdin)
    if "inputs" in packet:
        outputs = verify(packet["inputs"])
        # A completed verification can contain negative check results.
        result = {"outcome": "ok", "outputs": outputs}
    else:
        result = verify(packet)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
