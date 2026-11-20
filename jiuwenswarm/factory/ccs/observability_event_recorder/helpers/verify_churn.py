"""Report likely replacements of function signatures in high-churn files."""

from collections import defaultdict
import re

from helpers.verify_gate import blank, diff_hunks, TOKEN


HIGH_CHURN = {
    "src/llama-moe-cache.cpp", "src/llama-moe-cache.h",
    "ggml/src/ggml-backend.cpp", "ggml/include/ggml-backend.h",
    "src/llama-context.cpp", "src/llama-context.h",
}
SIGNATURE = re.compile(
    r"(?m)^[ \t]*(?P<type>(?:[\w:<>]+[ \t]+)+(?:[*&]+[ \t]*)*)"
    r"(?P<name>[\w:]+)\s*\((?P<args>[^;{}]*?)\)"
    r"(?P<qualifiers>[ \t]*(?:(?:const|volatile|noexcept|override|final|&&?)\b[ \t]*)*)"
    r"\s*(?=[{;])"
)
NON_TYPES = {"return", "if", "else", "while", "switch", "for", "case", "throw", "co_return"}


def signatures(lines, changed):
    side = [line for line in lines if line.startswith((" ", changed))]
    code = "\n".join(line[1:] for line in side)
    changed_lines = {number for number, line in enumerate(side) if line.startswith(changed)}
    stripped = TOKEN.sub(lambda token: blank(token) if token[0].startswith("/") else token[0], code)
    for match in SIGNATURE.finditer(stripped):
        if NON_TYPES.intersection(match["type"].split()):
            continue
        first = stripped.count("\n", 0, match.start())
        last = first + match[0].count("\n")
        if any(number in changed_lines for number in range(first, last + 1)):
            name = match["name"]
            tokens = tuple(re.findall(r"\w+|[^\w\s]", match[0]))
            yield name, tokens


def signature_changes(patch):
    removed = defaultdict(set)
    added = defaultdict(set)
    for path, _, lines in diff_hunks(patch):
        if path in HIGH_CHURN:
            for name, signature in signatures(lines, "-"):
                removed[path, name].add(signature)
            for name, signature in signatures(lines, "+"):
                added[path, name].add(signature)
    findings = [
        f"{path}: {name}" for path, name in sorted(removed.keys() & added.keys())
        if removed[path, name] - added[path, name] and added[path, name] - removed[path, name]
    ]
    if findings:
        return "Potential existing signature changes: " + ", ".join(findings) + ". Review the additive alternatives."
    return "No existing function signature replacements recognized in high-churn files."
