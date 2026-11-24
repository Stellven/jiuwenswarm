"""Check the structure and limits of a version 1 engine placement JSON file."""
import argparse
import json
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024
MAX_OVERRIDES = 4095


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def validate(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Plan exceeds 4 MiB")
    plan = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    if (not isinstance(plan, dict) or set(plan) != {"version", "overrides"}
            or type(plan["version"]) is not int or plan["version"] != 1):
        raise ValueError("Expected exactly version (integer 1) and overrides")
    rows = plan["overrides"]
    if not isinstance(rows, list) or len(rows) > MAX_OVERRIDES:
        raise ValueError("Expected overrides array with at most 4095 rows")
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"pattern", "buft"}:
            raise ValueError(f"Row {index}: expected exactly pattern and buft")
        for key, value in row.items():
            if not isinstance(value, str) or not value or "\0" in value:
                raise ValueError(f"Row {index}: invalid {key}")
            value.encode("utf-8")  # Reject escaped unpaired surrogates.
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        count = validate(args.plan)
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Valid plan structure ({count} override rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
