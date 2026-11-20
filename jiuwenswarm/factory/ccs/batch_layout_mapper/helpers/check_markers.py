"""Report component markers and effective load mode from a saved server log."""

import argparse
import json
from pathlib import Path
import re


MARKER_KINDS = ("active", "inactive", "layout", "stats")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--name", required=True, help="Component name before the colon")
    parser.add_argument("--require", action="append", choices=MARKER_KINDS, default=[])
    parser.add_argument("--load-mode", help="Require all tensor-load records to report this mode")
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

    marker = re.compile(rf"\b{re.escape(args.name)}: (active|inactive|layout|stats)\b")
    load_mode = re.compile(r"\bload_tensors:.*\(load_mode = ([^)]+)\)")
    lines = {kind: [] for kind in MARKER_KINDS}
    modes = []
    try:
        with args.log.open(encoding="utf-8", errors="replace") as log:
            for number, line in enumerate(log, start=1):
                if match := marker.search(line):
                    lines[match[1]].append({"line": number, "text": line.strip()})
                if match := load_mode.search(line):
                    modes.append(match[1])
    except OSError as exc:
        parser.exit(1, f"{exc}\n")

    effective_modes = list(dict.fromkeys(modes))
    missing = [kind for kind in args.require if not lines[kind]]
    mode_matches = args.load_mode is None or effective_modes == [args.load_mode]
    print(json.dumps({"markers": lines, "load_modes": effective_modes,
                      "missing": missing, "load_mode_matches": mode_matches}, indent=2))
    return int(bool(missing) or not mode_matches)


if __name__ == "__main__":
    raise SystemExit(main())
