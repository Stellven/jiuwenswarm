"""Unified diff reading for the verifier, standard library only.

Parses a git-style patch into file patches, lists the touched paths, and applies a file patch to a pre-image
strictly (every context and removed line must match; the hunk may sit at another offset, like `git apply`).
The verifier uses it to rebuild post-images from the checkout's HEAD so its static rules read whole files,
and so the rules can be tested from a diff and a stock file alone.
"""
import re

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchError(ValueError):
    pass


def _path(token):
    token = token.split("\t", 1)[0].strip()
    if token == "/dev/null":
        return None
    if token.startswith('"'):
        raise PatchError(f"quoted path {token} is not supported")
    return token[2:] if token[:2] in ("a/", "b/") else token


def parse_patch(text):
    """[{old, new, new_file, deleted, binary, mode_change, hunks: [{old_start, old_len, new_start, new_len, lines}]}]"""
    files, cur, lines = [], None, text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            cur = {"old": None, "new": None, "new_file": False, "deleted": False, "binary": False,
                   "mode_change": False, "hunks": [], "header": line}
            files.append(cur)
            parts = line[len("diff --git "):].split(" ")
            if len(parts) == 2:
                cur["old"], cur["new"] = _path(parts[0]), _path(parts[1])
        elif cur is None and line.startswith("--- "):
            cur = {"old": None, "new": None, "new_file": False, "deleted": False, "binary": False,
                   "mode_change": False, "hunks": [], "header": line}
            files.append(cur)
            cur["old"] = _path(line[4:])
        elif cur is not None and line.startswith("--- ") and not cur["hunks"]:
            cur["old"] = _path(line[4:])
            if cur["old"] is None:
                cur["new_file"] = True
        elif cur is not None and line.startswith("+++ ") and not cur["hunks"]:
            cur["new"] = _path(line[4:])
            if cur["new"] is None:
                cur["deleted"] = True
        elif cur is not None and line.startswith("new file mode"):
            cur["new_file"] = True
        elif cur is not None and line.startswith("deleted file mode"):
            cur["deleted"] = True
        elif cur is not None and line.startswith(("old mode", "new mode", "rename ", "copy ", "similarity")):
            cur["mode_change"] = True
        elif cur is not None and (line.startswith("Binary files") or line.startswith("GIT binary patch")):
            cur["binary"] = True
        elif cur is not None and line.startswith("@@ "):
            m = HUNK.match(line)
            if not m:
                raise PatchError(f"bad hunk header: {line}")
            old_len = int(m[2]) if m[2] is not None else 1
            new_len = int(m[4]) if m[4] is not None else 1
            hunk = {"old_start": int(m[1]), "old_len": old_len, "new_start": int(m[3]), "new_len": new_len,
                    "lines": []}
            seen_old = seen_new = 0
            i += 1
            while i < len(lines) and (seen_old < old_len or seen_new < new_len):
                body = lines[i]
                tag = body[:1]
                if tag == "\\":
                    i += 1
                    continue
                if tag not in (" ", "+", "-") and body != "":
                    break
                if body == "":
                    tag, body = " ", " "
                hunk["lines"].append((tag, body[1:]))
                seen_old += tag in (" ", "-")
                seen_new += tag in (" ", "+")
                i += 1
            if seen_old != old_len or seen_new != new_len:
                raise PatchError(f"truncated hunk in {cur.get('new') or cur.get('old')}")
            cur["hunks"].append(hunk)
            continue
        i += 1
    if not files:
        raise PatchError("no file patches found")
    for fp in files:
        if fp["new"] is None and fp["old"] is None:
            raise PatchError(f"cannot read the paths of: {fp['header']}")
    return files


def touched_paths(files):
    out = set()
    for fp in files:
        for p in (fp["old"], fp["new"]):
            if p:
                out.add(p)
    return out


def apply_file(pre_text, fp):
    """Post-image text of one file patch applied to pre_text (None for a new file). Raises PatchError."""
    if fp["binary"]:
        raise PatchError(f"{fp['new'] or fp['old']}: binary patch")
    if pre_text is not None:
        pre_text = pre_text.replace("\r\n", "\n")  # a CRLF checkout of an LF file (core.autocrlf)
    lines = [] if pre_text is None else pre_text.split("\n")
    trailing = pre_text is not None and pre_text.endswith("\n")
    if trailing:
        lines = lines[:-1]
    out, pos = [], 0
    for hunk in fp["hunks"]:
        old = [body for tag, body in hunk["lines"] if tag in (" ", "-")]
        new = [body for tag, body in hunk["lines"] if tag in (" ", "+")]
        want = max(hunk["old_start"] - 1, 0) if old else hunk["old_start"]
        at = None
        for delta in range(0, len(lines) + 1):
            for cand in (want + delta, want - delta):
                if pos <= cand <= len(lines) - len(old) and lines[cand:cand + len(old)] == old:
                    at = cand
                    break
            if at is not None:
                break
        if at is None:
            raise PatchError(f"{fp['new'] or fp['old']}: hunk at -{hunk['old_start']} does not apply")
        out.extend(lines[pos:at])
        out.extend(new)
        pos = at + len(old)
    out.extend(lines[pos:])
    text = "\n".join(out)
    if out and (trailing or pre_text is None):
        text += "\n"
    return text


def added_lines(fp):
    return [body for hunk in fp["hunks"] for tag, body in hunk["lines"] if tag == "+"]


def post_images(files, read_pre):
    """{path: post_text} for every non-deleted file; read_pre(path) returns the pre-image text or None."""
    out = {}
    for fp in files:
        if fp["deleted"]:
            continue
        pre = None if fp["new_file"] else read_pre(fp["old"])
        if pre is None and not fp["new_file"]:
            raise PatchError(f"{fp['old']}: not in the checkout")
        out[fp["new"]] = apply_file(pre, fp)
    return out
