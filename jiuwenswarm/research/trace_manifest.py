"""Offline, host-owned invocation traces; integrity is not proof of execution.

Blob refs are objects containing only a lowercase ``sha256`` digest. Derivation
operands may additionally select a JSON ``pointer`` within a referenced blob.
Detail is bounded scalar metadata; arguments, results and payloads belong in blobs.
Sequences start at one, with a null genesis predecessor. Event digests exclude
only event_sha256; the manifest digest excludes only manifest_sha256. Hashes use
state.json_bytes, with no clocks, randomness, storage or external calls.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from .contracts import ResearchError, validate
from .state import json_bytes


TRACE_SCHEMA = "urn:ai4r:capsule-trace:1.0.0"


def _digest(value: dict, field: str) -> str:
    return hashlib.sha256(json_bytes({k: v for k, v in value.items() if k != field})).hexdigest()


class TraceBuilder:
    """Capture one invocation. Returned data never aliases the private journal."""

    def __init__(self, invocation_id, contract_ref, declaration_ref, profile_ref):
        self._manifest = copy.deepcopy({
            "schema_version": "1.0.0", "invocation_id": invocation_id,
            "contract_ref": contract_ref, "declaration_ref": declaration_ref,
            "profile_ref": profile_ref, "events": [],
        })
        self._finalized = None
        self._validate([], {"status": "pending", "final_artifact_sha256": None}, [])

    def _validate(self, events, terminal, claims):
        value = {**self._manifest, "events": events, "terminal": terminal,
                 "claims": claims, "manifest_sha256": "0" * 64}
        validate(TRACE_SCHEMA, value)

    def append_event(self, kind, producer, args_ref=None, input_refs=None,
                     result_ref=None, detail=None) -> dict:
        """Append a detached event; omitted inputs mean an empty list."""
        events = self._manifest["events"]
        if self._finalized is not None or (events and events[-1]["kind"] == "submit"):
            raise ResearchError("trace_terminal", "Cannot append after submit or finalization")
        event = copy.deepcopy({
            "seq": len(events) + 1, "kind": kind, "producer": producer,
            "prev_event_sha256": events[-1]["event_sha256"] if events else None,
            "args_ref": args_ref, "input_refs": [] if input_refs is None else input_refs,
            "result_ref": result_ref, "detail": detail,
        })
        event["event_sha256"] = _digest(event, "event_sha256")
        self._validate([event], {"status": "pending", "final_artifact_sha256": None}, [])
        events.append(event)
        return copy.deepcopy(event)

    def finalize(self, terminal, claims) -> dict:
        """Seal the trace; identical repeated finalizations are idempotent.

        Failed invocations may finalize without a submit or final artifact.
        Claim truth and derivation operations are for a later verifier to assess.
        """
        if self._finalized is not None:
            if terminal != self._finalized["terminal"] or claims != self._finalized["claims"]:
                raise ResearchError("trace_terminal", "Finalized trace cannot change")
            return copy.deepcopy(self._finalized)
        manifest = copy.deepcopy({**self._manifest, "terminal": terminal, "claims": claims})
        manifest["manifest_sha256"] = _digest(manifest, "manifest_sha256")
        validate(TRACE_SCHEMA, manifest)
        for claim in manifest["claims"]:
            if any(seq > len(manifest["events"]) for seq in claim["evidence_event_seqs"]):
                raise ResearchError("trace_claim", "Claim references an absent event")
        self._finalized = manifest
        return copy.deepcopy(manifest)


def verify_chain(manifest: Any) -> list[str]:
    """Return integrity failures, including malformed input, without trusting it.

    A party able to rewrite all hashes can forge a trace. Callers must separately
    pin the host's manifest digest and verify referenced blobs and claim meaning.
    """
    failures = []
    try:
        validate(TRACE_SCHEMA, manifest)
    except ResearchError as exc:
        failures.append("invalid_manifest: " + str(exc))
    if not isinstance(manifest, dict):
        return failures
    try:
        if manifest.get("manifest_sha256") != _digest(manifest, "manifest_sha256"):
            failures.append("bad_manifest_digest")
    except (ResearchError, TypeError, ValueError):
        failures.append("bad_manifest_digest")
    events = manifest.get("events")
    if not isinstance(events, list):
        return failures
    previous = None
    terminal = False
    for expected, event in enumerate(events, 1):
        if terminal:
            failures.append(f"event_after_terminal: {expected}")
        if not isinstance(event, dict):
            failures.append(f"invalid_event: {expected}")
            previous = None
            continue
        if type(event.get("seq")) is not int or event["seq"] != expected:
            failures.append(f"seq_gap: {expected}")
        if event.get("prev_event_sha256") != previous:
            failures.append(f"bad_prev_hash: {expected}")
        try:
            if event.get("event_sha256") != _digest(event, "event_sha256"):
                failures.append(f"bad_event_digest: {expected}")
        except (ResearchError, TypeError, ValueError):
            failures.append(f"bad_event_digest: {expected}")
        previous = event.get("event_sha256")
        terminal = terminal or event.get("kind") == "submit"
    return failures
