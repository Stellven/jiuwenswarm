"""Replay frozen historical exports through Harbor, without calling the app.

This is artifact-transport and grading validation only. It never establishes
fresh AI4Research execution, recovery, or model quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 4096
CASE_RUNS = {"cpu": "case1-cpu-r1", "paper": "case3-paper-r1"}


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _pin(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("oversized replay file")
    return {"sha256": digest.hexdigest(), "size": size}


def _inventory(root):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("symlink historical source root")
    root = root.resolve(strict=True)
    result = []
    size = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink in historical source")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("non-regular replay input")
        pin = _pin(path)
        result.append({"path": path.relative_to(root).as_posix(), **pin})
        size += pin["size"]
        if len(result) > MAX_FILES or size > MAX_BYTES:
            raise ValueError("historical replay exceeds finite bounds")
    return result


def freeze(source, inventory, destination):
    """Explicitly pin an existing export; no source bytes are rewritten."""
    source = Path(source).absolute()
    inventory = Path(inventory).absolute()
    destination = Path(destination).absolute()
    if any(p.is_symlink() for p in (source, *source.parents, inventory, *inventory.parents)):
        raise ValueError("symlink source roots are forbidden")
    source = source.resolve(strict=True)
    inventory = inventory.resolve(strict=True)
    if destination.is_relative_to(source):
        raise ValueError("replay pin must be outside original evidence")
    host = _json(inventory)
    if not host.get("captured_at"):
        raise ValueError("archived host inventory timestamp unavailable")
    value = {
        "schema": "ai4r-harbor-replay:1",
        "custody": "historical_replay",
        "source": str(source),
        "inventory": {"path": str(inventory), **_pin(inventory)},
        "files": _inventory(source),
    }
    # Refuse an incomplete copied results folder before starting Harbor.
    paths = {row["path"] for row in value["files"]}
    for run in CASE_RUNS.values():
        required = {f"runs/{run}/run_record.json", f"runs/{run}/collection_manifest.json",
                    f"runs/{run}/artifacts/originals.zip"}
        if not required <= paths:
            raise ValueError("historical source lacks original artifact bytes")
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return value


def stage(config, case_id, destination):
    """Revalidate frozen original bytes and publish a clearly labeled copy."""
    if case_id not in CASE_RUNS:
        raise ValueError("unsupported replay case")
    config = _json(config) if not isinstance(config, dict) else config
    if config.get("schema") != "ai4r-harbor-replay:1" or config.get("custody") != "historical_replay":
        raise ValueError("explicit historical replay config required")
    source = Path(config["source"])
    if _inventory(source) != config["files"]:
        raise ValueError("frozen historical evidence changed")
    inventory = Path(config["inventory"]["path"])
    if _pin(inventory) != {key: config["inventory"][key] for key in ("sha256", "size")}:
        raise ValueError("archived inventory changed")
    destination = Path(destination)
    if destination.exists() or any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError("replay output already exists")
    if destination.absolute().is_relative_to(source.resolve(strict=True)):
        raise ValueError("replay output must be outside original evidence")
    shutil.copytree(source, destination)
    # Validate the copy too; a concurrent source mutation cannot silently pass.
    if _inventory(destination) != config["files"]:
        raise ValueError("replay copy differs from frozen source")
    shutil.copyfile(inventory, destination / "archived-host-inventory.json")
    if _pin(destination / "archived-host-inventory.json") != {
        key: config["inventory"][key] for key in ("sha256", "size")
    }:
        raise ValueError("copied archived inventory differs from frozen source")
    campaign = _json(destination / "campaign.json")
    run = _json(destination / "runs" / CASE_RUNS[case_id] / "run_record.json")
    receipt = {
        "schema": "ai4r-harbor-receipt:1", "case_id": case_id,
        "campaign_id": campaign["campaign_id"], "run_id": run["run_id"],
        "request_id": run["request_id"], "app_run_id": run["app_run_id"],
        "runner_exit_code": None, "execution_state": run["execution_state"],
        "collection_state": run["collection_state"], "recovered": False,
        "cancellation_requested": False, "custody": "historical_replay",
        "inventory_ref": "archived-host-inventory.json",
        "terminal_confirmed": run["execution_state"] in {"completed", "partial", "halted", "failed", "blocked", "cancelled"},
        "evidence_complete": run["collection_state"] == "complete",
        "error_type": None, "live_execution_performed": False,
        "scope": "Frozen October 23 exports transported through Harbor; no app call or new model execution.",
    }
    (destination / "pilot-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


# Keep pinning/staging usable with just the standard library.
try:
    from harbor.agents.base import BaseAgent
except ImportError:
    BaseAgent = object


class HistoricalReplayAgent(BaseAgent):
    """A transport adapter for frozen exports, explicitly separate from live."""

    @staticmethod
    def name():
        return "ai4r-historical-replay"

    def version(self):
        return "1"

    async def setup(self, environment):
        pass

    async def run(self, instruction, environment, context):
        cases = re.findall(r"^AI4R_HARBOR_CASE: (cpu|paper)$", instruction, flags=re.MULTILINE)
        if len(cases) != 1:
            raise ValueError("one exact pilot case marker required")
        config = os.environ.get("AI4R_HARBOR_REPLAY_CONFIG")
        if not config:
            raise ValueError("AI4R_HARBOR_REPLAY_CONFIG is required")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai4r-replay-", dir=self.logs_dir) as temporary:
            evidence = Path(temporary) / "evidence"
            receipt = stage(config, cases[0], evidence)
            # Harbor collects the retained copy before the separate verifier.
            await environment.upload_dir(evidence, "/app/ai4r-evidence")
        context.metadata = {"custody": "historical_replay", "live_execution_performed": False,
                            "case_id": cases[0], "original_campaign_id": receipt["campaign_id"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("freeze")
    command.add_argument("--source", required=True, type=Path)
    command.add_argument("--inventory", required=True, type=Path)
    command.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args(argv)
    result = freeze(args.source, args.inventory, args.destination)
    print(json.dumps({"custody": result["custody"], "file_count": len(result["files"]),
                      "destination": str(args.destination)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
