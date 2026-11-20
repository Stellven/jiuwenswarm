"""Best-effort local C++ checks for marker logging in a candidate diff."""

from bisect import bisect_left
from collections import defaultdict
import re


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
TOKEN = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
DIRECTIVE = re.compile(r"^[ \t]*#(?:[^\n\\]|\\[^\n]|\\\n)*", re.M)
LOG_CALL = re.compile(r"\b(?:LLAMA_)?LOG_[A-Z][A-Z_0-9]*\s*\([^;]*?;")
CPP_SUFFIXES = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx")


def diff_hunks(patch):
    """Yield the new pathname, first postimage line and lines for each hunk."""
    for section in re.split(r"(?m)^diff --git ", patch.decode(errors="replace"))[1:]:
        path = re.search(r"(?m)^\+\+\+ b/([^\t\n]+)", section)
        if path:
            hunks = re.split(r"(?m)(?=^@@ )", section)
            for hunk in hunks[1:]:
                lines = hunk.split("\n")
                if header := HUNK.match(lines[0]):
                    yield path[1], int(header[1]), lines[1:]


def added_lines(patch):
    paths = defaultdict(list)
    for path, number, lines in diff_hunks(patch):
        if not path.endswith(CPP_SUFFIXES):
            continue
        for line in lines:
            if line.startswith("+"):
                paths[path].append(number)
            if line.startswith(("+", " ")):
                number += 1
    return paths


def blank(match):
    return re.sub(r"[^\n]", " ", match[0])


def marker_calls(source, lines, prefix):
    """Select calls whose macro, argument or closing line was added."""
    code = TOKEN.sub(blank, source)
    code = DIRECTIVE.sub(blank, code)
    marker = re.compile(rf"(?<![\w.]){re.escape(prefix)}")
    for call in LOG_CALL.finditer(code):
        first = code.count("\n", 0, call.start()) + 1
        last = first + call[0].count("\n")
        index = bisect_left(lines, first)
        if index == len(lines) or lines[index] > last:
            continue
        start = call.start()
        if any(token[0].startswith('"') and marker.search(token[0])
               for token in TOKEN.finditer(source, start, call.end())):
            yield start, first


def log_guards(source, gate, positions):
    """Recognize direct getenv aliases and simple, lexically dominating guards."""
    uncommented = TOKEN.sub(lambda token: blank(token) if token[0].startswith("/") else token[0], source)
    code = DIRECTIVE.sub(blank, TOKEN.sub(blank, source))
    reads = re.compile(
        rf'\b(\w+)\s*=\s*(?:std::|::)?getenv\s*\(\s*"{re.escape(gate)}"\s*\)\s*;'
    )
    aliases = {match[1] for match in reads.finditer(uncommented)}
    events = [(pos, "log", None) for pos in positions]
    for read in reads.finditer(uncommented):
        if code[read.start():read.start() + len(read[1])] == read[1]:
            events.append((read.end(), "read", read[1]))
    for alias in aliases:
        absent = rf"(?:!\s*{alias}\b|{alias}\s*==\s*nullptr|nullptr\s*==\s*{alias})"
        present = rf"(?:{alias}\b|{alias}\s*!=\s*nullptr|nullptr\s*!=\s*{alias})"
        for match in re.finditer(rf"\bif\s*\(\s*{absent}\s*\)\s*", code):
            tail = code[match.end():]
            early = re.match(r"(?:return\b[^;]*;|\{\s*return\b[^;]*;\s*\})", tail)
            if early:
                # A dangling if nested under another unbraced control statement
                # does not dominate later statements in the enclosing block.
                previous = code[:match.start()].rstrip()
                if not previous or previous.endswith((";", "{", "}")):
                    events.append((match.end() + early.end(), "guard", alias))
            elif tail.startswith("{"):
                events.append((match.end(), "absent", alias))
            elif match.end() in positions:
                events.append((match.end(), "absent_log", alias))
        exact = rf"\s*&&\s*(?:std::)?strcmp\s*\(\s*{alias}\s*,\s*\)\s*==\s*0"
        for match in re.finditer(rf"\bif\s*\(\s*{present}(?:{exact})?\s*\)\s*(?=\{{)", code):
            events.append((match.end(), "present", alias))

    # Scope stacks prevent a guard in a sibling block or function from
    # supplying evidence for a log. Branch guards apply only within the block.
    events.extend((brace.start(), brace[0], None) for brace in re.finditer(r"[{}]", code))
    scopes = [{"read": set(), "guard": set(), "absent": set()}]
    pending = None
    outcomes = {}
    for position, kind, alias in sorted(events):
        if kind == "{":
            scope = {"read": set(), "guard": set(), "absent": set()}
            if pending:
                branch, name = pending
                scope[branch].add(name)
                pending = None
            scopes.append(scope)
        elif kind == "}":
            if len(scopes) > 1:
                scopes.pop()
        elif kind == "read":
            scopes[-1]["read"].add(alias)
        elif kind == "log":
            if any(scope["absent"] for scope in scopes):
                outcomes[position] = "absent"
            elif position not in outcomes and any(scope["guard"] for scope in scopes):
                outcomes[position] = "guarded"
        elif any(alias in scope["read"] for scope in scopes):
            if kind == "guard":
                scopes[-1]["guard"].add(alias)
            elif kind == "absent_log":
                outcomes[position] = "absent"
            else:
                pending = ("guard" if kind == "present" else "absent", alias)
    return outcomes


def gate_silence(patch, read_postimage, gate, prefix):
    """Classify added marker calls with the supplied full candidate source."""
    absent = []
    unknown = []
    found = False
    for path, lines in added_lines(patch).items():
        try:
            source = read_postimage(path)
        except OSError:
            source = None
        if source is None:
            unknown.append(f"{path} (postimage unavailable)")
            continue
        calls = dict(marker_calls(source, sorted(lines), prefix))
        found |= bool(calls)
        guards = log_guards(source, gate, calls)
        for position, line in calls.items():
            where = f"{path}:{line}"
            if guards.get(position) == "absent":
                absent.append(where)
            elif guards.get(position) != "guarded":
                unknown.append(where)
    if absent:
        detail = f"Marker logging in a recognized unset-{gate} branch: {', '.join(absent)}."
        if unknown:
            detail += f" No preceding local gate test recognized at {', '.join(unknown)}."
        return "fail", detail
    if unknown:
        return "inconclusive", f"No preceding local {gate} test recognized at {', '.join(unknown)}."
    if not found:
        return "inconclusive", "No added LOG_* or LLAMA_LOG_* call with this marker prefix was recognized."
    return "pass", f"Every recognized added marker call follows a local {gate} presence test."
