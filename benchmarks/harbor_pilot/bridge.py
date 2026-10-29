"""Host-only bridge to the existing sequential runner.

The app remains authoritative for execution. A durable active pointer prevents
the next Harbor trial from dispatching while delivery, containment, or collection
of an earlier trial is unresolved. No credential enters the exported folder.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import tempfile
from urllib.parse import urlsplit


TERMINAL = {"completed", "partial", "halted", "cancelled", "failed", "blocked", "interrupted"}
UNLAUNCHED_TERMINAL = {"preparation_failed", "not_submitted", "timed_out"}
MARKER = re.compile(r"^AI4R_HARBOR_CASE: (cpu|paper)$", re.MULTILINE)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe(path, *, directory=False, exists=True):
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Symlink paths are not supported")
    path = path.resolve(strict=exists)
    if exists and (not path.is_dir() if directory else not path.is_file()):
        raise ValueError("Expected a regular directory or file")
    return path


def read_json(path):
    path = _safe(path)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("JSON evidence exceeds the bounded reader")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate JSON field")
            value[key] = item
        return value
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def atomic(path, value):
    path = Path(path)
    _safe(path.parent, directory=True)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Unsafe bridge output")
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    fd, temporary = tempfile.mkstemp(prefix=".pilot-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_pin(path):
    path = _safe(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size": path.stat().st_size}


@dataclass(frozen=True)
class Config:
    bundle_root: Path
    output_root: Path
    endpoint: str
    token_file: Path
    expected_build: str
    http_authority: str | None = None
    cancel_timeout_s: float = 45

    @classmethod
    def load(cls, path):
        value = read_json(path)
        required = {"schema", "bundle_root", "output_root", "endpoint", "token_file", "expected_build"}
        optional = {"http_authority", "cancel_timeout_s"}
        if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional or value["schema"] != "ai4r-harbor-config:1":
            raise ValueError("Unsupported host bridge config")
        for key in required - {"schema"}:
            if not isinstance(value[key], str) or not value[key] or "\x00" in value[key]:
                raise ValueError("Host bridge config requires explicit strings")
        if any(not Path(value[key]).is_absolute() for key in ("bundle_root", "output_root", "token_file")):
            raise ValueError("Host bridge paths must be absolute")
        bundle = _safe(value["bundle_root"], directory=True)
        output = _safe(value["output_root"], directory=True)
        token = _safe(value["token_file"])
        if token.stat().st_size > 16384:
            raise ValueError("Credential reference exceeds its bound")
        if bundle == output or bundle.is_relative_to(output) or output.is_relative_to(bundle):
            raise ValueError("Input and evidence roots must not overlap")
        if token.is_relative_to(bundle) or token.is_relative_to(output):
            raise ValueError("Credential must remain outside all task and evidence roots")
        endpoint = urlsplit(value["endpoint"])
        if endpoint.scheme not in {"http", "https"} or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or endpoint.path not in {"", "/"}:
            raise ValueError("Explicit credential-free HTTP app origin required")
        # An explicitly selected remote origin is supported. Local app traffic
        # always uses the repository's sole published port.
        if endpoint.hostname in {"localhost", "127.0.0.1", "::1"} and endpoint.port != 5175:
            raise ValueError("The local app must use port 5175")
        timeout = value.get("cancel_timeout_s", 45)
        if type(timeout) not in {int, float} or not math.isfinite(timeout) or not 1 <= timeout <= 120:
            raise ValueError("Cancellation timeout must be between 1 and 120 seconds")
        authority = value.get("http_authority")
        if authority is not None and (not isinstance(authority, str) or not re.fullmatch(r"(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(?::[0-9]{1,5})?", authority)):
            raise ValueError("Invalid HTTP authority")
        return cls(bundle, output, value["endpoint"].rstrip("/"), token, value["expected_build"], authority, timeout)


def case_from_instruction(instruction):
    matches = MARKER.findall(instruction)
    if len(matches) != 1:
        raise ValueError("One exact AI4Research pilot case marker is required")
    return matches[0]


def campaign_id(case_id, trial_identity):
    # Suite cases use the same accepted sequential runner identifiers. The
    # pilot instruction parser remains restricted to its original two cases.
    if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,47}", case_id) or not trial_identity:
        raise ValueError("Runner case and durable Harbor trial identity required")
    return "harbor-" + hashlib.sha256((case_id + "\n" + str(trial_identity)).encode()).hexdigest()[:24]


def case_pins(config, case_id, trial_identity):
    case_path = config.bundle_root / "cases" / (case_id + ".json")
    # Use the same accepted case schema as the runner; no parallel task schema.
    from jiuwenswarm.research_sidecar.sequential_cases import load_cases
    document = load_cases(case_path)
    if len(document["cases"]) != 1 or document["cases"][0]["repeats"] != 1:
        raise ValueError("A Harbor trial must map to exactly one runner attempt")
    inputs_root = _safe(config.bundle_root / "inputs", directory=True)
    inputs = {}
    for item in document["cases"][0]["inputs"]:
        path = _safe(inputs_root / item["path"])
        if not path.is_relative_to(inputs_root):
            raise ValueError("Case input escapes the public input root")
        inputs[item["path"]] = file_pin(path)
    result = {"schema": "ai4r-harbor-pins:1", "case_id": case_id,
            "runner_case_id": document["cases"][0]["id"], "trial_identity": str(trial_identity),
            "case": file_pin(case_path), "inputs": inputs,
            "endpoint": config.endpoint, "http_authority": config.http_authority,
            "expected_build": config.expected_build}
    if getattr(config, "target_identity", None):
        result["target_identity"] = config.target_identity
    return result


@contextmanager
def output_lock(root):
    path = root / ".harbor-pilot.lock"
    if path.is_symlink():
        raise ValueError("Unsafe pilot lock")
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            stream.write(b"0")
            stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("Another Harbor pilot observer owns this output root") from None
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("Another Harbor pilot observer owns this output root") from None
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def host_inventory(root):
    """Actual orchestration host observations; no inferred app-host/GPU facts."""
    unavailable = {"status": "unavailable", "reason": "Not exposed by this portable inventory"}
    memory = {"physical_total_bytes": dict(unavailable), "physical_available_bytes": dict(unavailable),
              "commit_limit_bytes": dict(unavailable), "commit_available_bytes": dict(unavailable)}
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        *[(name, ctypes.c_ulonglong) for name in ("total", "available", "commit_total", "commit_available", "virtual_total", "virtual_available", "extended")]]
        observed = MemoryStatus()
        observed.length = ctypes.sizeof(observed)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(observed)):
            memory = {"physical_total_bytes": observed.total, "physical_available_bytes": observed.available,
                      "commit_limit_bytes": observed.commit_total, "commit_available_bytes": observed.commit_available}
    elif Path("/proc/meminfo").is_file():
        fields = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            fields[key] = int(value.strip().split()[0]) * 1024
        memory.update(physical_total_bytes=fields.get("MemTotal", unavailable),
                      physical_available_bytes=fields.get("MemAvailable", unavailable),
                      commit_limit_bytes=fields.get("CommitLimit", unavailable),
                      committed_bytes=fields.get("Committed_AS", unavailable),
                      swap_total_bytes=fields.get("SwapTotal", unavailable),
                      swap_free_bytes=fields.get("SwapFree", unavailable))
    storage = shutil.disk_usage(root)
    return {"schema": "ai4r-harbor-host-inventory:1", "captured_at": now(), "role": "orchestration",
            "host": platform.node(), "os": platform.platform(), "architecture": platform.machine(),
            "cpu_model": platform.processor() or unavailable, "logical_cpus": os.cpu_count(),
            "python": platform.python_version(), "memory": memory,
            "storage": {"total_bytes": storage.total, "free_bytes": storage.free},
            "accelerators": {"status": "unavailable", "reason": "No accelerator inventory probe was performed; absence is not inferred"},
            "execution_host": {"status": "unavailable", "reason": "App execution host must be obtained from app evidence; this is the Harbor host"},
            "background_workload": dict(unavailable), "peak_working_set": dict(unavailable),
            "paging_activity": dict(unavailable), "qualified_performance_profile": False}


async def _execute(args):
    from jiuwenswarm.research_sidecar.sequential import execute
    return await execute(args)


def _args(config, command, ident, case_id=None):
    return argparse.Namespace(command=command, cases=str(config.bundle_root / "cases" / (str(case_id) + ".json")),
                              inputs=str(config.bundle_root / "inputs"), output=str(config.output_root),
                              campaign_id=ident, campaign_dir=str(config.output_root / ident),
                              endpoint=config.endpoint, token_file=str(config.token_file) if config.token_file else None, expected_build=config.expected_build,
                              http_authority=config.http_authority, json=True)


def observation(folder):
    paths = sorted((folder / "runs").glob("*/run_record.json"))
    if len(paths) != 1:
        return {"execution_state": "not_observed", "collection_state": "pending", "app_run_id": None,
                "request_id": None, "terminal_confirmed": False, "evidence_complete": False}
    row = read_json(paths[0])
    state, collected = row.get("execution_state"), row.get("collection_state")
    terminal = state in TERMINAL
    if row.get("app_run_id") is None and state in UNLAUNCHED_TERMINAL:
        ledger = folder / "ledger.sqlite"
        claimed = True  # Without the delivery ledger, an absent app ID proves nothing.
        if ledger.is_file():
            with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
                claimed = db.execute("SELECT 1 FROM attempts WHERE id=?", (row["run_id"],)).fetchone() is not None
        terminal = not claimed
    return {"execution_state": state, "collection_state": collected, "app_run_id": row.get("app_run_id"),
            "request_id": row.get("request_id"), "terminal_confirmed": terminal,
            "evidence_complete": terminal and collected == "complete"}


@dataclass
class BridgeResult:
    folder: Path
    receipt: dict


class BridgeCancelled(asyncio.CancelledError):
    def __init__(self, result):
        super().__init__("Harbor cancellation retained; inspect the pilot receipt")
        self.result = result


async def _contain(config, ident, execute):
    """Bounded app cancellation, terminal observation, and collection."""
    code, error_type = 3, None
    async def stop_and_observe():
        nonlocal code
        if (config.output_root / ident / "campaign.json").is_file() or getattr(config, "reconcile_without_local_campaign", False):
            await execute(_args(config, "cancel", ident))
            code, _ = await execute(_args(config, "resume", ident))
    operation = asyncio.create_task(stop_and_observe(), name="ai4r-pilot-containment")
    bounded = asyncio.create_task(asyncio.wait_for(operation, timeout=config.cancel_timeout_s),
                                  name="ai4r-pilot-containment-deadline")
    # Harbor may cancel the caller again while its timeout/cancellation handler
    # is running. Keep ownership of the same bounded operation and join it
    # before returning: otherwise it could keep writing after output_lock is
    # released and race the next trial's recovery. wait_for cancels and joins
    # the runner operation on expiry; repeated outer cancellation never resets
    # that deadline or abandons either task.
    while not bounded.done():
        try:
            await asyncio.shield(bounded)
        except asyncio.CancelledError:
            continue
        except Exception:
            break
    try:
        bounded.result()
    except (Exception, asyncio.CancelledError) as error:
        error_type = type(error).__name__
    return code, error_type


async def run_trial(config, case_id, trial_identity, *, execute=None, inventory=None):
    if not config.token_file and execute is None:
        raise ValueError("a deployment runner backend is required when no direct credential is referenced")
    execute = execute or _execute
    inventory = inventory or host_inventory
    ident = campaign_id(case_id, trial_identity)
    folder = config.output_root / ident
    pins = case_pins(config, case_id, trial_identity)
    with output_lock(config.output_root):
        controls = config.output_root / ".harbor-pilot-controls"
        controls.mkdir(mode=0o750, exist_ok=True)
        _safe(controls, directory=True)
        pins_path = controls / (ident + ".json")
        recovered = pins_path.exists()
        if recovered:
            if read_json(pins_path) != pins:
                raise ValueError("Pilot task/input/build pins changed; refusing resume")
        else:
            if folder.exists():
                raise ValueError("Refusing to adopt an existing campaign without bridge custody pins")
            atomic(pins_path, pins)
        active_path = config.output_root / ".harbor-pilot-active.json"
        if active_path.exists():
            active = read_json(active_path)
            previous_id = active.get("campaign_id")
            if not isinstance(previous_id, str) or not re.fullmatch(r"harbor-[a-f0-9]{24}", previous_id):
                raise ValueError("Invalid durable pilot active pointer")
            if previous_id != ident:
                previous = config.output_root / previous_id
                prior_pins = read_json(controls / (previous_id + ".json"))
                if any(prior_pins.get(key) != pins.get(key) for key in ("endpoint", "http_authority", "expected_build", "target_identity")):
                    raise ValueError("Unresolved prior campaign belongs to a different pinned target")
                # Resume means reconcile/observe/collect through the existing
                # runner; it can never blindly resend a claimed request.
                if not (previous / "campaign.json").is_file() and not getattr(config, "reconcile_without_local_campaign", False):
                    raise ValueError("Previous pilot attempt is unresolved; dispatch remains locked")
                try:
                    await execute(_args(config, "resume", previous_id))
                except asyncio.CancelledError:
                    # Timeout can arrive while reconciling the earlier attempt,
                    # before this task has any app request of its own.
                    prior_code, prior_error = await _contain(config, previous_id, execute)
                    prior_receipt = {"schema": "ai4r-harbor-receipt:1", "case_id": prior_pins["case_id"],
                                     "campaign_id": previous_id, "runner_exit_code": prior_code,
                                     **observation(previous), "recovered": True, "cancellation_requested": True,
                                     "custody": "live", "inventory_ref": "host-inventory.json",
                                     "error_type": prior_error, "observed_at": now(),
                                     "scientific_assessment": "not_performed"}
                    atomic(previous / "pilot-receipt.json", prior_receipt)
                    if prior_receipt["terminal_confirmed"] and prior_receipt["collection_state"] in {"complete", "not_applicable"}:
                        active_path.unlink()
                    raise BridgeCancelled(BridgeResult(previous, prior_receipt))
                prior = observation(previous)
                if not prior["terminal_confirmed"] or prior["collection_state"] not in {"complete", "not_applicable"}:
                    raise ValueError("Previous app execution or collection remains unresolved")
                atomic(active_path, {"schema": "ai4r-harbor-active:1", "campaign_id": ident, "updated_at": now()})
        else:
            atomic(active_path, {"schema": "ai4r-harbor-active:1", "campaign_id": ident, "updated_at": now()})
        inv_path = controls / (ident + "-inventory.json")
        if not inv_path.exists():
            atomic(inv_path, inventory(config.output_root))
        error_type = None
        cancelled = False
        code = 3
        try:
            if folder.exists() and not (folder / "campaign.json").is_file() and not getattr(config, "reconcile_without_local_campaign", False):
                raise ValueError("Incomplete campaign creation; no submission permitted")
            command = "resume" if folder.exists() or (recovered and getattr(config, "reconcile_without_local_campaign", False)) else "run"
            code, _ = await execute(_args(config, command, ident, case_id))
        except asyncio.CancelledError:
            cancelled = True
            code, error_type = await _contain(config, ident, execute)
        except Exception as error:
            # Error messages may originate in network libraries. Export only the
            # category; runner-owned diagnostics already enforce redaction.
            error_type = type(error).__name__
        folder.mkdir(mode=0o750, exist_ok=True)
        atomic(folder / "host-inventory.json", read_json(inv_path))
        atomic(folder / "bridge-pins.json", pins)
        receipt = {"schema": "ai4r-harbor-receipt:1", "case_id": case_id, "campaign_id": ident,
                   "runner_exit_code": code, **observation(folder), "recovered": recovered,
                   "cancellation_requested": cancelled, "custody": "live", "inventory_ref": "host-inventory.json",
                   "error_type": error_type, "observed_at": now(), "scientific_assessment": "not_performed"}
        atomic(folder / "pilot-receipt.json", receipt)
        if receipt["terminal_confirmed"] and receipt["collection_state"] in {"complete", "not_applicable"}:
            active_path.unlink()
        result = BridgeResult(folder, receipt)
        if cancelled:
            raise BridgeCancelled(result)
        return result
