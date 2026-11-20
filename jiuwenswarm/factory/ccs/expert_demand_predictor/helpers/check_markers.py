#!/usr/bin/env python3
"""Summarize INFO marker counts and effective tensor load modes."""
import argparse
import json
from pathlib import Path
import re

LOAD_MODE = re.compile(r"\bload_tensors:.*?\(load_mode = ([^)]+)\)")


def inspect(lines, name):
    counts = dict.fromkeys(("active", "inactive", "stats"), 0)
    modes = []
    pattern = re.compile(rf"(?<![\w.]){re.escape(name)}:\s*(active|inactive|stats)(?=\s|$)")
    for line in lines:
        mode = LOAD_MODE.search(line)
        if mode and mode[1] not in modes:
            modes.append(mode[1])
        marker = pattern.search(line)
        if marker:
            counts[marker[1]] += 1
    return {"markers": counts, "load_modes": modes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--name", default="expert_demand_predictor", help="marker prefix")
    parser.add_argument("--require-active", action="store_true", help="require one active line")
    parser.add_argument("--require-mmap", action="store_true", help="require effective load mode mmap")
    parser.add_argument("--expect-silent", action="store_true",
                        help="Fail if any line contains the component's marker prefix")
    args = parser.parse_args()
    if args.expect_silent:
        prefix = re.compile(rf"(?<![\w.]){re.escape(args.name)}:")
        try:
            with args.log.open(encoding="utf-8", errors="replace") as log:
                unexpected = [number for number, line in enumerate(log, 1) if prefix.search(line)]
        except OSError as exc:
            parser.exit(1, f"{exc}\n")
        if unexpected:
            print(json.dumps({"unexpected_marker_lines": unexpected}))
            return 1
    try:
        with args.log.open(encoding="utf-8", errors="replace") as log:
            result = inspect(log, args.name)
    except OSError as error:
        parser.error(str(error))
    print(json.dumps(result))
    return int(
        (args.require_active and result["markers"]["active"] != 1)
        or (args.require_mmap and result["load_modes"] != ["mmap"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
