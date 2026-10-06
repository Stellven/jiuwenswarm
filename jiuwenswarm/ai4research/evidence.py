"""Portable trial records and minimal, read-only native inspection views."""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path

from .common import GovernanceError, canonical_json, hash_json, sha256_bytes
from .state import INTERFACE_REVISION, RunStore


class EvidenceViews:
    """Derive views from custody; a projection never owns acceptance.

    Bundles are local authenticated inspection artifacts, not RSI exports. Each
    immutable snapshot manifest names all captured members and their hashes.
    """

    def __init__(self, store: RunStore):
        self.store = store

    def inspect(self, run_id: str, *, caller_id: str) -> dict:
        run = self.store.get_run(run_id, caller_id=caller_id)
        attempts = [{key: attempt.get(key) for key in
                     ("attempt_id", "invocation_id", "role", "node_id", "outcome", "started_at", "finished_at", "evidence")}
                    for attempt in run["attempts"]]
        status_events = [event for event in run["events"] if event["event_type"] == "status"]
        return {"interface_revision": INTERFACE_REVISION, "run_id": run_id,
                "workspace_id": run["workspace_id"], "status": run["status"],
                "last_status": status_events[-1]["payload"] if status_events else None,
                "accepted_ref": run["accepted_ref"], "decision": run["decision"],
                "pins": run["pins"], "configuration": run["configuration"],
                "attempts": attempts, "events": run["events"], "artifact_refs": run["artifacts"]}

    def bundle(self, run_id: str, *, caller_id: str) -> dict:
        """Read and validate every captured member before advertising a bundle."""
        run = self.store.get_run(run_id, caller_id=caller_id)
        members = []
        for ref in run["artifacts"]:
            content = self.store.get_artifact(ref, caller_id=caller_id)
            members.append({"reference": ref, "size_bytes": len(content)})
        manifest = {"interface_revision": INTERFACE_REVISION, "run_id": run_id,
                    "user_id": run["user_id"], "workspace_id": run["workspace_id"],
                    "client_request_id": run["client_request_id"],
                    "original_ref": run["original_ref"], "status": run["status"],
                    "accepted_ref": run["accepted_ref"], "decision": run["decision"],
                    "configuration": run["configuration"], "contract": run["contract"],
                    "pins": run["pins"], "attempts": run["attempts"],
                    "events": run["events"], "members": members,
                    "predecessor_run_id": run["predecessor_run_id"],
                    "audience": "local", "mode": run["mode"]}
        return {"manifest": manifest, "manifest_sha256": hash_json(manifest)}

    def _path(self, relative: str) -> Path:
        root = self.store.artifacts_dir
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise GovernanceError("policy_denied", "Evidence view escapes local custody")
        item = path
        while item != root:
            if item.is_symlink():
                raise GovernanceError("policy_denied", "Evidence view symlinks are forbidden")
            item = item.parent
        return path

    def _immutable_file(self, path: Path, payload: bytes) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path, flags, 0o600)
            except FileExistsError:
                with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
                    if stream.read() != payload:
                        raise GovernanceError("invalid_input", "Existing evidence projection has been changed")
                return
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise GovernanceError("persistence_failed", "Portable evidence view could not be persisted") from exc

    def write_bundle(self, run_id: str, *, caller_id: str) -> dict:
        """Persist an immutable portable snapshot, with manifest written last.

        Partial files after failure are unusable without a validated manifest.
        Rebuilding a projection cannot alter the authoritative run or decision.
        """
        bundle = self.bundle(run_id, caller_id=caller_id)
        # Short directory names support the Windows authoring host. Full hashes
        # remain in refs/manifests; a name collision refuses differing bytes.
        key = sha256_bytes(run_id.encode("utf-8"))[:24]
        prefix = f"records/bundles/{key}/{bundle['manifest_sha256'][:24]}"
        for member in bundle["manifest"]["members"]:
            ref = member["reference"]
            self._immutable_file(self._path(f"{prefix}/{ref['artifact_id']}.bin"),
                                 self.store.get_artifact(ref, caller_id=caller_id))
        records = b"".join(canonical_json(event) + b"\n" for event in bundle["manifest"]["events"])
        self._immutable_file(self._path(f"{prefix}/records.jsonl"), records)
        path = self._path(f"{prefix}/manifest.json")
        self._immutable_file(path, canonical_json(bundle["manifest"]))
        return {"run_id": run_id, "manifest_sha256": bundle["manifest_sha256"],
                "locator": str(path.relative_to(self.store.artifacts_dir)).replace("\\", "/"),
                "audience": "local"}

    def verify_bundle(self, reference: dict, *, caller_id: str) -> dict:
        """Validate exported local bytes and current caller attribution."""
        if (not isinstance(reference, Mapping)
                or set(reference) != {"run_id", "manifest_sha256", "locator", "audience"}
                or not isinstance(reference.get("run_id"), str) or not reference["run_id"].strip()
                or not isinstance(reference.get("manifest_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", reference["manifest_sha256"])):
            raise GovernanceError("invalid_input", "Portable bundle reference is malformed")
        run = self.store.get_run(reference["run_id"], caller_id=caller_id)
        key = sha256_bytes(reference["run_id"].encode("utf-8"))[:24]
        expected = f"records/bundles/{key}/{reference['manifest_sha256'][:24]}/manifest.json"
        if reference.get("locator") != expected or reference.get("audience") != "local":
            raise GovernanceError("policy_denied", "Bundle reference exceeds local audience or scope")
        try:
            payload = self._path(expected).read_bytes()
            if sha256_bytes(payload) != reference["manifest_sha256"]:
                raise GovernanceError("invalid_input", "Bundle manifest identity changed")
            manifest = json.loads(payload)
            if manifest["run_id"] != reference["run_id"] or manifest["user_id"] != caller_id:
                raise GovernanceError("policy_denied", "Bundle has foreign attribution")
            for field in ("workspace_id", "original_ref", "configuration", "contract", "pins", "mode", "client_request_id", "predecessor_run_id"):
                if manifest[field] != run[field]:
                    raise GovernanceError("invalid_input", "Bundle context differs from authoritative frozen context")
            if manifest["events"] != run["events"][:len(manifest["events"])]:
                raise GovernanceError("invalid_input", "Bundle observations are not authoritative history")
            statuses = [event["payload"]["status"] for event in manifest["events"] if event["event_type"] == "status"]
            if not statuses or manifest["status"] != statuses[-1]:
                raise GovernanceError("invalid_input", "Bundle status differs from its captured history")
            attempts, captured_refs, captured_decision, captured_accepted = {}, {run["original_ref"]["artifact_id"]: run["original_ref"]}, None, None
            for event in manifest["events"]:
                observation = event["payload"]
                if event["event_type"] == "attempt_started":
                    attempts[observation["attempt_id"]] = dict(observation, outcome="RUNNING")
                elif event["event_type"] == "attempt_finished":
                    attempts[observation["attempt_id"]].update(observation)
                elif event["event_type"] == "artifact":
                    ref = observation["reference"]
                    captured_refs[ref["artifact_id"]] = ref
                elif event["event_type"] == "decision":
                    captured_decision = observation["decision"]
                    captured_accepted = observation["receipt"]["accepted_ref"]
            if manifest["attempts"] != list(attempts.values()):
                raise GovernanceError("invalid_input", "Bundle attempts differ from authoritative captured observations")
            if manifest["decision"] != captured_decision or manifest["accepted_ref"] != captured_accepted:
                raise GovernanceError("invalid_input", "Bundle release differs from its authoritative captured decision")
            member_refs = {member["reference"]["artifact_id"]: member["reference"] for member in manifest["members"]}
            if len(member_refs) != len(manifest["members"]) or member_refs != captured_refs:
                raise GovernanceError("invalid_input", "Bundle must contain every attributable captured artifact exactly once")
            directory = self._path(expected).parent
            for member in manifest["members"]:
                ref = member["reference"]
                path = self._path(str((directory / f"{ref['artifact_id']}.bin").relative_to(self.store.artifacts_dir)))
                content = path.read_bytes()
                if len(content) != member["size_bytes"] or sha256_bytes(content) != ref["sha256"]:
                    raise GovernanceError("invalid_input", "Bundle member differs from captured exact bytes")
                if content != self.store.get_artifact(ref, caller_id=caller_id):
                    raise GovernanceError("invalid_input", "Bundle member is not attributable captured evidence")
            records = self._path(str((directory / "records.jsonl").relative_to(self.store.artifacts_dir))).read_bytes()
            expected_records = b"".join(canonical_json(event) + b"\n" for event in manifest["events"])
            if records != expected_records:
                raise GovernanceError("invalid_input", "Bundle records differ from immutable manifest")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise GovernanceError("persistence_failed", "Portable bundle is incomplete or unreadable") from exc
        return manifest
