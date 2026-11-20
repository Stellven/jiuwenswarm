#!/usr/bin/env python3
"""Print matched one-shot commands or compare completion content and token IDs."""
import argparse
import json
from pathlib import Path
import shlex

GATE = "LLAMA_EXPERT_PREDICT"
HARNESS = Path.home() / "predemo/one_shot.sh"


def commands(args):
    for label, binary, gate in (
        ("stock", args.stock_bin, ["-u", GATE]),
        ("off", args.candidate_bin, ["-u", GATE]),
        ("on", args.candidate_bin, [GATE + "=1"]),
    ):
        output = args.output_dir / label
        yield [
            "env", *gate, "MODEL=" + str(args.model), "bash", str(HARNESS),
            str(binary), str(output), "5175", *args.server_args, "-lm", "mmap", "-lv", "4",
        ]


def completion(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or type(data.get("content")) is not str:
        raise ValueError(f"{path}: expected completion content")
    tokens = data.get("tokens")
    if not isinstance(tokens, list) or not tokens or any(type(token) is not int for token in tokens):
        raise ValueError(f"{path}: expected nonempty integer token IDs")
    return data["content"].encode("utf-8"), tokens


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    plan = subparsers.add_parser("plan", help="print commands for an authorized shell")
    plan.add_argument("stock_bin", type=Path)
    plan.add_argument("candidate_bin", type=Path)
    plan.add_argument("model", type=Path)
    plan.add_argument("output_dir", type=Path)
    plan.add_argument("server_args", nargs=argparse.REMAINDER, help="shared server flags after --")
    compare = subparsers.add_parser("compare", help="compare stock, off and on completion JSON")
    compare.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if args.action == "plan":
        if args.server_args[:1] == ["--"]:
            args.server_args.pop(0)
        for command in commands(args):
            print(shlex.join(command))
        return 0

    try:
        stock, off, on = [completion(args.output_dir / f"{name}.json") for name in ("stock", "off", "on")]
    except (OSError, ValueError) as error:
        parser.error(str(error))
    results = {"candidate_off_matches": off == stock, "candidate_on_matches": on == stock}
    print(json.dumps(results))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
