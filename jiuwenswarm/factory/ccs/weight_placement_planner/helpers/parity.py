"""Run a fixed one-shot stock/candidate control and compare completion tokens."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from check_markers import is_active, summarize


def tokens(path):
    with path.open(encoding="utf-8") as stream:
        result = json.load(stream)
    values = result.get("tokens") if isinstance(result, dict) else None
    if not isinstance(values, list) or not values or any(type(value) is not int for value in values):
        raise ValueError(f"Missing or invalid completion tokens in {path}")
    return values


def compare(args):
    env = os.environ.copy()
    for variable in (args.gate, *args.clear_env):
        env.pop(variable, None)
    env["MODEL"] = str(args.model.resolve(strict=True))

    args.output.mkdir()
    runs = [
        ("stock", args.stock_bin, args.stock_arg, env),
        ("candidate", args.candidate_bin, args.candidate_arg,
         dict(env, **({args.gate: "1"} if args.active else {}))),
    ]
    for label, binary, specific, run_env in runs:
        subprocess.run(
            ["bash", str(args.one_shot), str(binary), str(args.output / label), "5175",
             *args.common_arg, *specific, "-lv", "4"],
            env=run_env, check=True,
        )

    stock = summarize(args.output / "stock.server.log", args.name)
    candidate = summarize(args.output / "candidate.server.log", args.name)
    print(json.dumps({"stock": stock, "candidate": candidate}, sort_keys=True))
    mode = stock["effective_load_mode"]
    if not mode or mode != candidate["effective_load_mode"]:
        raise ValueError("Missing or differing effective load modes")
    if args.load_mode is not None and mode != args.load_mode:
        raise ValueError(f"Expected effective load mode {args.load_mode}, got {mode}")
    if args.active and not is_active(candidate):
        raise ValueError("Expected one active and one stats marker, with zero inactive markers")
    if not args.active and candidate["markers"]:
        raise ValueError("Gate-unset candidate emitted component markers")
    if tokens(args.output / "stock.json") != tokens(args.output / "candidate.json"):
        raise ValueError("Completion token mismatch")
    print("Completion tokens match")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--one-shot", type=Path, default=Path(os.environ.get("FACTORY_ONE_SHOT", "~/predemo/one_shot.sh")).expanduser(),
                        help="one_shot.sh wrapper (default: $FACTORY_ONE_SHOT or ~/predemo/one_shot.sh)")
    parser.add_argument("--stock-bin", type=Path, required=True)
    parser.add_argument("--candidate-bin", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new directory for logs and JSON")
    parser.add_argument("--name", required=True, help="component name before the colon")
    parser.add_argument("--gate", required=True, help="gate environment variable")
    parser.add_argument("--clear-env", action="append", default=[], help="clear extra inherited env")
    parser.add_argument("--active", action="store_true", help="enable candidate gate and require markers")
    parser.add_argument("--load-mode", help="require this effective loader mode in both logs")
    for name in ("common", "stock", "candidate"):
        parser.add_argument(f"--{name}-arg", action="append", default=[],
                            help="repeat for each argument, e.g. --common-arg=-ngl --common-arg=0")
    args = parser.parse_args()
    try:
        compare(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
