"""Validate authored metadata and run independent oracle unit tests, not models."""
import argparse
import json
import subprocess
import sys

from .contracts import EXPECTED, EXTENDED, load_cases, resolve_cases_root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-root")
    parser.add_argument("--case", dest="case_ids", action="append", choices=sorted({**EXPECTED, **EXTENDED}), default=[])
    args = parser.parse_args(argv)
    root = resolve_cases_root(args.cases_root)
    cases = (load_cases(root, case_ids=args.case_ids) if any(c in EXTENDED for c in args.case_ids)
             else load_cases(root))
    if args.case_ids:
        cases = [case for case in cases if case["id"] in args.case_ids]
    failed = []
    for case in cases:
        path = root / case["id"]
        result = subprocess.run([sys.executable, "-B", "test_oracle.py"], cwd=path, capture_output=True, text=True)
        print(json.dumps({"case_id": case["id"], "oracle_unit_tests": "passed" if result.returncode == 0 else "failed",
                          "detail": (result.stdout+result.stderr).strip()}))
        if result.returncode:
            failed.append(case["id"])
    print(json.dumps({"case_count": len(cases), "variant_count": sum(len(c["variants"]) for c in cases),
                      "failed": failed, "measurement_scope": "oracle unit tests; no product performance"}))
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
