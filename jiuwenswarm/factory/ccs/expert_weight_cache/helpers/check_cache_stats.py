"""Check a single cache stats line against its admitted byte budget."""
import argparse
import json
from pathlib import Path
import re

from check_markers import read_signals


FIELDS = {"leases", "reuses", "evictions", "bytes_copied_saved", "peak_bytes"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--name", required=True, help="Component log prefix")
    parser.add_argument("--admitted-bytes", type=int, required=True)
    parser.add_argument("--expect", choices=("reuse", "bypass"), required=True)
    args = parser.parse_args()
    if args.admitted_bytes < 0:
        parser.error("--admitted-bytes must be nonnegative")
    try:
        report = read_signals(args.log.read_text(errors="replace"), args.name)
    except OSError as exc:
        parser.error(str(exc))
    rows = report["stats"]
    pairs = re.findall(r"\b(\w+)=([0-9]+)(?=\s|$)", rows[0]) if len(rows) == 1 else []
    counters = {key: int(value) for key, value in pairs}
    if not FIELDS <= counters.keys() or len(counters) != len(pairs):
        parser.error("expected one stats line with each required counter exactly once")

    errors = []
    if counters["peak_bytes"] > args.admitted_bytes:
        errors.append("peak_bytes exceeds admitted bytes")
    if counters["reuses"] > counters["leases"]:
        errors.append("reuses exceeds leases")
    if args.expect == "reuse":
        if not report["active"] or report["inactive"] or set(report["load_modes"]) != {"mmap"}:
            errors.append("expected an active mmap run without an inactive transition")
        if not all(counters[field] > 0 for field in ("reuses", "bytes_copied_saved")):
            errors.append("expected positive reuse and avoided upload bytes")
    elif (not report["inactive"] or report["active"] or
          counters["reuses"] or counters["bytes_copied_saved"]):
        errors.append("expected inactive bypass with zero reuse and savings")
    print(json.dumps({"counters": counters, "errors": errors}, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
