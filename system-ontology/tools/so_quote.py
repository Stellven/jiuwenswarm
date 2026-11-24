#!/usr/bin/env python3
"""Put quotes around the free text in description files.

YAML reads ": " inside text as the key-value separator and ", " inside the brace form as the field separator, so a note with a colon
or a comma is silently split into several fields. This program splits the brace form on each line by the known field names and puts
double quotes around its text values; an ordinary "key: text" line is also quoted when the text contains ": " or " #". Values already quoted are left alone.

Usage: python so_quote.py <file> [<file> ...]
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAIN = re.compile(r"^(?:-?\d+(?:\.\d+)?(?:e[+-]?\d+)?|true|false|null|open|UNSET)$", re.I)


def known_keys() -> set[str]:
    """Every field name that appears in the definition files."""
    schema = yaml.safe_load((ROOT / "ontology" / "schema.yaml").read_text(encoding="utf-8"))
    keys: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "properties" and isinstance(v, dict):
                    keys.update(str(x) for x in v)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema)
    return keys


def quote(text: str) -> str:
    t = text.strip()
    if not t or t[0] in "\"'[{&*!|>" or PLAIN.match(t):
        return t
    if re.match(r"^[A-Za-z0-9_./@+-]+$", t):          # short values such as identifiers need no quotes
        return t
    return '"' + t.replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_flow(body: str, keys: set[str]) -> list[tuple[str, str]] | None:
    """Split the content of a brace form into (key, value) by the known field names. Splits at the outermost level only. Returns None when it cannot tell."""
    marks, depth, in_str = [], 0, None
    i = 0
    while i < len(body):
        ch = body[i]
        if in_str:
            if ch == "\\":
                i += 1
            elif ch == in_str:
                in_str = None
        elif ch in "\"'":
            in_str = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        elif depth == 0 and (i == 0 or body[i - 2:i] == ", "):
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*): ", body[i:])
            if m and m.group(1) in keys:
                marks.append((i, m.group(1), i + m.end()))
        i += 1
    if not marks or marks[0][0] != 0:
        return None
    out = []
    for n, (start, key, vstart) in enumerate(marks):
        end = marks[n + 1][0] - 2 if n + 1 < len(marks) else len(body)
        out.append((key, body[vstart:end].strip()))
    return out


def fix_flow(text: str, keys: set[str]) -> str:
    """text has the form {...}. The brace values inside it are handled recursively."""
    inner = text[1:-1].strip()
    parts = split_flow(inner, keys)
    if parts is None:
        return text
    done = []
    for key, value in parts:
        if value.startswith("{") and value.endswith("}"):
            value = fix_flow(value, keys)
        else:
            value = quote(value)
        done.append(f"{key}: {value}")
    return "{" + ", ".join(done) + "}"


def fix_line(line: str, keys: set[str]) -> str:
    if line.lstrip().startswith("#") or not line.strip():
        return line
    m = re.match(r"^(\s*(?:- )?)(.*)$", line)
    lead, rest = m.group(1), m.group(2)
    if rest.startswith("{") and rest.rstrip().endswith("}"):
        return lead + fix_flow(rest.rstrip(), keys)
    k = re.match(r"^([A-Za-z_][A-Za-z0-9_]*): (.*)$", rest)
    if not k:
        return line
    key, value = k.group(1), k.group(2).rstrip()
    if value.startswith("{") and value.endswith("}"):
        return f"{lead}{key}: {fix_flow(value, keys)}"
    if value and value[0] not in "\"'[{&*!|>" and (": " in value or " #" in value or value.endswith(":")):
        return f"{lead}{key}: {quote(value)}"
    return line


def main() -> int:
    keys = known_keys()
    for name in sys.argv[1:]:
        path = pathlib.Path(name)
        src = path.read_text(encoding="utf-8")
        out = "\n".join(fix_line(l, keys) for l in src.split("\n"))
        list(yaml.safe_load_all(out))                    # the result must parse, otherwise it is not written back
        if out != src:
            path.write_text(out, encoding="utf-8")
        print(f"{'quotes added' if out != src else 'nothing to change'}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
