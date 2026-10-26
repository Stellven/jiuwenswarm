"""Build a no-dispatch command manifest for the supported E2/E3 pilot flow.

The manifest only prepares commands for the existing ``evaluation-pilot``
authoring CLI. It never installs a profile, runs a workflow, or invokes a
model. In particular, paper-summary workflows are not valid pilot sources:
the existing pilot profile deliberately disables integrated workflow
shortcuts before the source observation is captured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import re

from .contracts import strict_json
from .value_data import write_once


INVENTORY_SCHEMA = "ai4r-workflow-runtime:1"
MANIFEST_SCHEMA = "ai4r-value-evaluation-prep:1"
DEFAULT_INVENTORY = Path.home() / "huawei" / "outputs" / "cc-value-discovery-2026-10-26" / "runtime-inventory.json"
_IDENTITY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_SAFE_ID = re.compile(r"[a-z][a-z0-9_.:-]{0,63}\Z")


def _identity(value: str, label: str) -> tuple[str, str]:
    if not isinstance(value, str) or not _IDENTITY.fullmatch(value):
        raise ValueError(f"{label} must be an exact cc_name@cc_version identity")
    return tuple(value.rsplit("@", 1))


def _container_path(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an absolute Docker path")
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValueError(f"{label} must be a canonical absolute Docker path")
    return value


def _read_inventory(path: Path) -> tuple[dict, str]:
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("runtime inventory must be an absolute regular file")
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("runtime inventory exceeds the 2 MiB limit")
    value = strict_json(raw)
    if (type(value) is not dict or value.get("schema") != INVENTORY_SCHEMA
            or type(value.get("capsules")) is not list):
        raise ValueError("unsupported runtime inventory; expected ai4r-workflow-runtime:1")
    return value, hashlib.sha256(raw).hexdigest()


def _pinned_capsule(inventory: dict, identity: str, label: str) -> dict:
    name, version = _identity(identity, label)
    if name in {"research.paper_summary", "research.paper_summary_delivery"}:
        raise ValueError("paper-summary capsules cannot be pilot source candidates: the existing evaluation-pilot profile disables their integrated workflow")
    rows = [row for row in inventory["capsules"] if type(row) is dict
            and row.get("name") == name and row.get("version") == version]
    if len(rows) != 1:
        raise ValueError(f"{label} is not unique in the supplied runtime inventory")
    row = rows[0]
    if row.get("standing") != "active" or row.get("eligible") is not True:
        raise ValueError(f"{label} is not currently active and eligible in the supplied inventory")
    return {"name": name, "version": version, "inventory_stage": row.get("stage"),
            "inventory_standing": row["standing"], "inventory_eligible": True}


def build_manifest(*, inventory_path: Path, candidate: str, verifier: str,
                   profile_id: str, campaign_id: str,
                   state_root: str = "/var/lib/ai4r",
                   config: str = "/var/lib/ai4r/operator/local-research-unified-v5/config.json",
                   bootstrap: str = "/var/lib/ai4r/operator/local-research-unified-v5/bootstrap.json",
                   operator_root: str = "/var/lib/ai4r/operator/value-evaluation") -> dict:
    """Return ordered argv vectors; no shell interpolation and no side effects."""
    if not _SAFE_ID.fullmatch(profile_id) or not _SAFE_ID.fullmatch(campaign_id):
        raise ValueError("profile_id and campaign_id must be lowercase safe identifiers")
    state_root = _container_path(state_root, "state_root")
    config = _container_path(config, "config")
    bootstrap = _container_path(bootstrap, "bootstrap")
    operator_root = _container_path(operator_root, "operator_root")
    expected_operator = PurePosixPath(state_root) / "operator"
    try:
        PurePosixPath(operator_root).relative_to(expected_operator)
    except ValueError as error:
        raise ValueError("operator_root must remain under state_root/operator") from error
    inventory, digest = _read_inventory(Path(inventory_path))
    candidate_pin = _pinned_capsule(inventory, candidate, "candidate")
    verifier_pin = _pinned_capsule(inventory, verifier, "verifier")
    if verifier_pin["name"] != "research.verifier":
        raise ValueError("independent verifier must be research.verifier")

    phase1 = operator_root.rstrip("/") + "/" + profile_id + "-phase1"
    phase2 = operator_root.rstrip("/") + "/" + profile_id + "-phase2"
    common = ["python", "-m", "jiuwenswarm.research.evaluation_pilot_cli",
              "--state-root", state_root, "--config", config, "--bootstrap", bootstrap]
    profile = common + ["profile", "--profile-id", profile_id,
        "--candidate", candidate, "--verifier", verifier, "--output-dir", phase1]
    sources = common + ["sources", "--profile-dir", phase1]
    # The scope command is intentionally a template until the operator chooses
    # an actual successful source contract and observation from `sources`.
    scope_template = common + ["scope", "--profile-dir", phase1,
        "--source-contract-id", "<exact-source-contract-record-id>",
        "--observation-id", "<exact-successful-observation-record-id>",
        "--campaign-id", campaign_id, "--output-dir", phase2]
    return {
        "schema": MANIFEST_SCHEMA,
        "status": "prep_only_source_run_and_E2_E3_execution_not_performed",
        "model_calls": 0,
        "source_inventory": {"path": str(Path(inventory_path).resolve()),
            "sha256": digest, "schema": inventory["schema"],
            "qualification_status": inventory.get("qualification_status"),
            "ready_is_not_qualification": inventory.get("qualification_status") != "qualified"},
        "pins": {"candidate": candidate_pin, "verifier": verifier_pin,
            "exact_cli_identities": {"candidate": candidate, "verifier": verifier}},
        "scope": {"entry_points": ["E3", "E2"], "candidate_source": candidate,
            "source_contract_ref": None, "source_observation_ref": None,
            "source_run_required_under_phase1_config": True,
            "integrated_workflows_enabled": False,
            "paper_summary_source_supported": False,
            "qualification_status": "not_run"},
        "commands": {"phase1_profile": profile, "inspect_real_sources": sources,
            "phase2_scope_template": scope_template},
        "next_steps": [
            "Run phase1_profile in the configured Docker app; the CLI revalidates exact declarations against its protected current library snapshot.",
            "Install the returned phase-one config/bootstrap in a fresh app startup and run one normal research task that actually invokes the selected standalone capsule.",
            "Run inspect_real_sources, then choose an observed successful contract and its exact observation; do not use planned IDs.",
            "Replace the two scope-template placeholders with those returned record IDs and run the command to author isolated E3 and exact-output E2 requests.",
            "Install the returned phase-two config/bootstrap and use the existing authenticated evaluation API; this manifest does not dispatch the prepared requests.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--candidate", default="research.screening@m1-4")
    parser.add_argument("--verifier", default="research.verifier@m1-2")
    parser.add_argument("--profile-id", default="value-screening-pilot")
    parser.add_argument("--campaign-id", default="value-screening-campaign")
    parser.add_argument("--state-root", default="/var/lib/ai4r")
    parser.add_argument("--config", default="/var/lib/ai4r/operator/local-research-unified-v5/config.json")
    parser.add_argument("--bootstrap", default="/var/lib/ai4r/operator/local-research-unified-v5/bootstrap.json")
    parser.add_argument("--operator-root", default="/var/lib/ai4r/operator/value-evaluation")
    parser.add_argument("--output", type=Path, help="Optional path for the JSON manifest; parents must already exist")
    args = parser.parse_args(argv)
    result = build_manifest(inventory_path=args.inventory, candidate=args.candidate,
        verifier=args.verifier, profile_id=args.profile_id, campaign_id=args.campaign_id,
        state_root=args.state_root, config=args.config, bootstrap=args.bootstrap,
        operator_root=args.operator_root)
    raw = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        if not args.output.parent.is_dir():
            raise ValueError("output parent directory must already exist")
        write_once(args.output, raw.encode("utf-8"), raw=True)
    else:
        print(raw, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
