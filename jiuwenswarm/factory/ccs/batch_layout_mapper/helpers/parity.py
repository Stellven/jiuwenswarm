"""Run one stock/off/on greedy smoke probe through a one_shot.sh-style wrapper."""

import argparse
import json
import os
from pathlib import Path
import subprocess


GATE = "LLAMA_BATCH_LAYOUT"


def read_completion(path):
    reply = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(reply, dict):
        raise ValueError(f"{path}: expected a completion object")
    content, tokens, stop = (reply.get(key) for key in ("content", "tokens", "stop_type"))
    if (reply.get("error") or not isinstance(content, str)
            or not isinstance(tokens, list) or not tokens
            or not all(type(token) is int for token in tokens)
            or reply.get("stop") is not True or not isinstance(stop, str) or not stop):
        raise ValueError(f"{path}: expected a completed response with token IDs and stop type")
    return content.encode("utf-8"), tokens, stop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrapper", type=Path, default=Path(os.environ.get("FACTORY_ONE_SHOT", "~/predemo/one_shot.sh")).expanduser(),
                        help="one_shot.sh-style wrapper (default: $FACTORY_ONE_SHOT or ~/predemo/one_shot.sh)")
    parser.add_argument("--stock", type=Path, required=True, help="Stock server binary directory")
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate server binary directory")
    parser.add_argument("--out", type=Path, required=True, help="New directory for response and log files")
    parser.add_argument("server_args", nargs=argparse.REMAINDER, help="Common server args after --")
    args = parser.parse_args()
    common = args.server_args
    if common and common[0] == "--":
        common = common[1:]

    env = os.environ.copy()
    env.pop(GATE, None)
    try:
        args.out.mkdir()
        results = {}
        for arm, binary_dir in (("stock", args.stock), ("off", args.candidate), ("on", args.candidate)):
            prefix = args.out.resolve() / arm
            run_env = {**env, GATE: "1"} if arm == "on" else env
            subprocess.run(
                ["bash", str(args.wrapper.resolve()), str(binary_dir.resolve()), str(prefix),
                 "5175", *common, "-lv", "4"],
                env=run_env, check=True, stdout=subprocess.DEVNULL,
            )
            results[arm] = read_completion(prefix.with_suffix(".json"))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")

    matches = {arm: results[arm] == results["stock"] for arm in ("off", "on")}
    print(json.dumps({"matches_stock": matches, "evidence_dir": str(args.out.resolve())}))
    return int(not all(matches.values()))


if __name__ == "__main__":
    raise SystemExit(main())
