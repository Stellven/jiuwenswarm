"""Summarize status lines for a named component and effective loader modes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

LOAD_MODE = re.compile(r"\bload_tensors:.*?\(load_mode = ([^)]+)\)")


def summarize(path, name):
    marker = re.compile(rf"(?<![\w.]){re.escape(name)}:\s+([\w-]+)")
    markers = Counter()
    modes = []
    with path.open(encoding="utf-8", errors="replace") as log:
        for line in log:
            if match := marker.search(line):
                markers[match[1]] += 1
            if match := LOAD_MODE.search(line):
                modes.append(match[1])
    return {
        "markers": dict(markers),
        "load_modes": modes,
        "effective_load_mode": modes[-1] if modes else None,
    }


def is_active(summary):
    counts = summary["markers"]
    return counts.get("active") == 1 and counts.get("inactive", 0) == 0 and counts.get("stats") == 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--name", required=True, help="component name before the colon")
    parser.add_argument("--expect-active", action="store_true",
                        help="require one active and one stats line, with zero inactive lines")
    parser.add_argument("--load-mode", help="require this last reported loader mode")
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
        summary = summarize(args.log, args.name)
    except OSError as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(summary, sort_keys=True))
    if args.expect_active and not is_active(summary):
        return 1
    if args.load_mode is not None and summary["effective_load_mode"] != args.load_mode:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
