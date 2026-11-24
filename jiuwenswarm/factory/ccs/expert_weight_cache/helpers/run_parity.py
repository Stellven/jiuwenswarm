"""Compare greedy one-shot server responses under identical command-line settings."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def capture(script, bindir, prefix, model, server_args, enabled):
    env = os.environ.copy()
    env["MODEL"] = str(model)
    env.pop("LLAMA_EXPERT_CACHE", None)
    if enabled:
        env["LLAMA_EXPERT_CACHE"] = "1"
    subprocess.run([str(script), str(bindir), str(prefix), "5175", *server_args],
                   env=env, check=True)
    with prefix.with_suffix(".json").open() as response:
        payload = json.load(response)
    if (not isinstance(payload, dict) or not isinstance(payload.get("tokens"), list)
            or not payload["tokens"] or not isinstance(payload.get("content"), str)
            or not isinstance(payload.get("stop_type"), str)):
        raise ValueError(f"{prefix}.json lacks a completed token response")
    return tuple(payload[field] for field in ("tokens", "content", "stop_type"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--one-shot", type=Path, required=True, help="Executable one-shot script")
    parser.add_argument("--stock", type=Path, required=True, help="Stock server binary directory")
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate binary directory")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("server_args", nargs=argparse.REMAINDER, help="Shared server flags after --")
    args = parser.parse_args()
    server_args = args.server_args
    if server_args[:1] == ["--"]:
        server_args = server_args[1:]
    if any(arg == "--port" or arg.startswith("--port=") for arg in server_args):
        parser.error("the one-shot runner uses port 5175")
    try:
        args.output.mkdir()
        results = [
            capture(args.one_shot.resolve(), bindir.resolve(), args.output / label,
                    args.model.resolve(), server_args, enabled)
            for label, bindir, enabled in (
                ("stock", args.stock, False),
                ("candidate_off", args.candidate, False),
                ("candidate_on", args.candidate, True),
            )
        ]
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    off_equal = results[0] == results[1]
    on_equal = results[0] == results[2]
    print(json.dumps({"gate_unset_matches_stock": off_equal, "gate_set_matches_stock": on_equal}))
    return int(not (off_equal and on_equal))


if __name__ == "__main__":
    raise SystemExit(main())
