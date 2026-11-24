"""Summarize component INFO markers and effective loader modes in a server log."""
import argparse
import json
from pathlib import Path
import re


def read_signals(log, name):
    marker = re.compile(rf"(?<![\w.]){re.escape(name)}: (active\b|inactive\b|stats\b)(.*)")
    mode = re.compile(r"\bload_tensors:[^\n]*\(load_mode = ([\w-]+)\)")
    report = {label: [] for label in ("active", "inactive", "stats")}
    report["load_modes"] = mode.findall(log)
    for match in marker.finditer(log):
        report[match[1]].append(match[2].strip())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--name", required=True, help="Component log prefix")
    parser.add_argument("--require-active", action="store_true",
                        help="Require an active line and an effective mmap load")
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
        report = read_signals(args.log.read_text(errors="replace"), args.name)
    except OSError as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    if args.require_active:
        return int(not report["active"] or set(report["load_modes"]) != {"mmap"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
