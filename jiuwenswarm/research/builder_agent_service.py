"""Protected, in-memory host boundary for bounded Builder sessions.

The model sees logical actions only. This module never accesses the local
filesystem or runs candidate code; checks are delegated to the trusted host.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import json
import re
import time
from typing import Any, Awaitable, Callable

from .capsules.builder_loop import package

DELIVERY_FILES = frozenset({"requirements.txt", "poc_patch.py", "run_benchmark.py"})
WORKSPACE_FILES = DELIVERY_FILES | {"tests.py"}
MAX_TOOL_CALLS = 40
MAX_JOBS = 12
MAX_MODEL_ORDINAL = 20
MAX_TIME_S = 600
MAX_FILE_BYTES = 1024 * 1024
MAX_TEST_BYTES = 64 * 1024
MAX_ARGUMENT_BYTES = 2 * 1024 * 1024
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SECRET_PATH_PARTS = frozenset({".ssh", ".aws", ".azure", ".config", "secrets", "credentials", "token", "keys"})


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _safe_result(value: Any, limit: int = 64 * 1024) -> Any:
    raw = _canonical(value)
    if len(raw) <= limit:
        return copy.deepcopy(value)
    return {"truncated": True, "sha256": _digest(raw), "size_bytes": len(raw),
            "preview": raw[:limit].decode("utf-8", "ignore")}


def _validate_relative_path(value: Any) -> str:
    if type(value) is not str or not value or "\\" in value or value.startswith("/"):
        raise ValueError("path must be a relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("path traversal is forbidden")
    if any(part.lower() in _SECRET_PATH_PARTS or any(term in part.lower() for term in ("credential", "secret", "token")) for part in parts):
        raise ValueError("protected credential paths are forbidden")
    if value not in WORKSPACE_FILES:
        raise ValueError("path is outside the Builder workspace allowlist")
    return value


class BuilderAgentService:
    """Own logical Builder files, check evidence, and submission packaging.

    ``execute_check`` is the trusted executor callback for unit/smoke checks.
    ``action_authorizer`` may bind each action to protected model-call evidence.
    """

    def __init__(self, *, initial_files: dict[str, str],
                 execute_check: Callable[[str, dict[str, str], str | None], Awaitable[dict]],
                 action_authorizer: Callable[[str, dict, int], Awaitable[bool]] | None = None,
                 read_log: Callable[[dict], Awaitable[Any]] | None = None,
                 session_id: str = "builder-session", max_tool_calls: int = MAX_TOOL_CALLS,
                 max_jobs: int = MAX_JOBS, timeout_s: float = MAX_TIME_S):
        if type(initial_files) is not dict or set(initial_files) != DELIVERY_FILES:
            raise ValueError("initial files must contain exactly the three delivery files")
        if any(type(value) is not str for value in initial_files.values()):
            raise ValueError("initial file contents must be text")
        if sum(len(value.encode("utf-8")) for value in initial_files.values()) > MAX_FILE_BYTES:
            raise ValueError("initial delivery files exceed one MiB")
        if not session_id or type(session_id) is not str:
            raise ValueError("session_id must be nonempty text")
        if not 1 <= max_tool_calls <= MAX_TOOL_CALLS or not 1 <= max_jobs <= MAX_JOBS:
            raise ValueError("configured action limits exceed policy")
        if not 0 < timeout_s <= MAX_TIME_S:
            raise ValueError("configured time limit exceeds policy")
        self.session_id = session_id
        self._files = dict(initial_files)
        self._files["tests.py"] = ""
        self._execute_check = execute_check
        self._action_authorizer = action_authorizer
        self._read_log = read_log
        self._issued_log_refs: dict[bytes, dict] = {}
        self._max_tool_calls = max_tool_calls
        self._max_jobs = max_jobs
        self._deadline = time.monotonic() + timeout_s
        self._tool_calls = 0
        self._jobs = 0
        self._last_ordinal = 0
        self._journal: list[dict[str, Any]] = []
        self._passing: dict[str, dict[str, Any]] = {}
        self._passed_snapshot: str | None = None
        self._submitted: dict[str, Any] | None = None
        self._stopped_reason: str | None = None
        self._lock = asyncio.Lock()

    @property
    def snapshot_sha256(self) -> str:
        return self._snapshot()["sha256"]

    def stop(self, reason: str) -> None:
        self._stopped_reason=str(reason)[:200]
        self._invalidate_checks()

    def _snapshot(self) -> dict[str, Any]:
        rows = {name: _digest(self._files[name].encode("utf-8")) for name in sorted(WORKSPACE_FILES)}
        return {"files": rows, "sha256": _digest(_canonical(rows))}

    def inspect(self) -> dict[str, Any]:
        """Return a bounded copy of workspace and evidence state."""
        snapshot = self._snapshot()
        return {"session_id": self.session_id, "snapshot": snapshot,
                "passing_snapshot": self._passed_snapshot,
                "files": dict(self._files), "journal": copy.deepcopy(self._journal),
                "checks": copy.deepcopy(self._passing), "tool_calls": self._tool_calls,
                "jobs": self._jobs, "submitted": self._submitted is not None}

    async def dispatch(self, action: str, args: dict, model_ordinal: int) -> dict[str, Any]:
        """Validate and execute one authorized logical action; never raises routine diagnostics."""
        async with self._lock:
            before = self._snapshot()["sha256"]
            self._tool_calls += 1
            if self._stopped_reason is not None:
                return self._record(action,args,model_ordinal,before,{'blocked':True,'error':self._stopped_reason})
            if self._tool_calls > self._max_tool_calls:
                return self._record(action, args, model_ordinal, before, {"ok": False, "blocked": True, "error": "tool_call_limit"})
            if time.monotonic() > self._deadline:
                return self._record(action, args, model_ordinal, before, {"ok": False, "blocked": True, "error": "time_limit"})
            if type(model_ordinal) is not int or not 1 <= model_ordinal <= MAX_MODEL_ORDINAL or model_ordinal <= self._last_ordinal:
                return self._record(action, args, model_ordinal, before, {"ok": False, "error": "invalid_model_ordinal"})
            self._last_ordinal = model_ordinal
            if type(action) is not str or action not in {
                "list_files", "search_files", "read_file", "write_file", "apply_patch",
                "run_checks", "read_log", "submit_candidate", "report_blocked",
            }:
                return self._record(action, args, model_ordinal, before, {"ok": False, "error": "unknown_action"})
            if type(args) is not dict or len(_canonical(args)) > MAX_ARGUMENT_BYTES:
                return self._record(action, args, model_ordinal, before, {"ok": False, "error": "invalid_arguments"})
            if self._action_authorizer is not None:
                allowed = await self._action_authorizer(action, copy.deepcopy(args), model_ordinal)
                if allowed is not True:
                    return self._record(action, args, model_ordinal, before, {"ok": False, "error": "action_not_authorized"})
            try:
                result = await self._dispatch(action, args, model_ordinal)
            except asyncio.CancelledError:
                raise
            except (ValueError, TypeError, KeyError, SyntaxError) as exc:
                result = {"ok": False, "error": str(exc)[:1000]}
            return self._record(action, args, model_ordinal, before, result)

    async def _dispatch(self, action: str, args: dict, ordinal: int) -> dict[str, Any]:
        if self._submitted is not None:
            return {"ok": False, "error": "session_already_submitted"}
        if action == "list_files":
            self._exact_args(args, set())
            return {"ok": True, "files": sorted(self._files)}
        if action == "search_files":
            self._exact_args(args, {"pattern"})
            pattern = args["pattern"]
            if type(pattern) is not str or len(pattern) > 500:
                raise ValueError("pattern must be a string of at most 500 characters")
            hits = []
            for name, content in sorted(self._files.items()):
                for line_number, line in enumerate(content.splitlines(), 1):
                    if pattern.casefold() in line.casefold():
                        hits.append({"path": name, "line": line_number, "text": line[:500]})
            return {"ok": True, "matches": hits[:100]}
        if action == "read_file":
            self._exact_args(args, {"path"})
            name = _validate_relative_path(args["path"])
            return {"ok": True, "path": name, "content": self._files[name], "sha256": _digest(self._files[name].encode())}
        if action in {"write_file", "apply_patch"}:
            required = {"path", "content", "expected_sha256"} if action == "write_file" else {"path", "old", "new", "expected_sha256"}
            self._exact_args(args, required)
            name = _validate_relative_path(args["path"])
            expected = args["expected_sha256"]
            if type(expected) is not str or not _HASH.fullmatch(expected):
                raise ValueError("expected_sha256 must match the current file snapshot")
            current = self._files[name]
            current_hash = _digest(current.encode("utf-8"))
            if current_hash != expected:
                return {"ok": False, "error": "stale_file_hash", "current_sha256": current_hash}
            if action == "write_file":
                replacement = args["content"]
            else:
                if type(args["old"]) is not str or not args["old"] or type(args["new"]) is not str:
                    raise ValueError("patch old/new values must be nonempty/text")
                if current.count(args["old"]) != 1:
                    raise ValueError("patch context must occur exactly once")
                replacement = current.replace(args["old"], args["new"], 1)
            if type(replacement) is not str:
                raise ValueError("file content must be text")
            encoded = replacement.encode("utf-8")
            limit = MAX_TEST_BYTES if name == "tests.py" else MAX_FILE_BYTES
            if len(encoded) > limit:
                raise ValueError("file exceeds its byte limit")
            if name in DELIVERY_FILES and (len(encoded)+sum(len(self._files[key].encode('utf-8'))
                    for key in DELIVERY_FILES if key!=name)) > MAX_FILE_BYTES:
                raise ValueError('delivery files exceed one MiB total')
            self._files[name] = replacement
            self._invalidate_checks()
            return {"ok": True, "path": name, "sha256": _digest(encoded), "snapshot_sha256": self.snapshot_sha256}
        if action == "run_checks":
            self._exact_args(args, {"check"}, {"check", "test_name"})
            check = args["check"]
            if check not in {"compile", "unit", "smoke"}:
                raise ValueError("check must be compile, unit or smoke")
            test_name = args.get("test_name")
            if test_name is not None and (type(test_name) is not str or len(test_name) > 200):
                raise ValueError("test_name must be short text")
            snapshot = self._snapshot()["sha256"]
            files = dict(self._files)
            if check == "compile":
                if not files["tests.py"].strip():
                    raise ValueError("nonempty tests.py is required")
                for name, content in files.items():
                    if name.endswith(".py"):
                        compile(content, name, 'exec')
                report = {"passed": True, "executor_evidence": False, "detail": "all Python files compiled without execution"}
            else:
                if not files["tests.py"].strip():
                    raise ValueError("nonempty tests.py is required")
                if self._jobs >= self._max_jobs:
                    return {"ok": False, "blocked": True, "error": "job_limit"}
                self._jobs += 1
                remaining = max(0.001, self._deadline - time.monotonic())
                try:
                    report = await asyncio.wait_for(self._execute_check(check, files, test_name), timeout=remaining)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    raise
                except Exception as exc:
                    raise RuntimeError("protected check runner failed") from exc
                if isinstance(report,dict) and report.get('execution_performed') is False:
                    self._jobs-=1
                if isinstance(report, dict):
                    refs = list(report.get("log_refs", []))
                    for key in ("stdout_ref", "stderr_ref"):
                        ref = report.get(key)
                        if isinstance(ref, dict):
                            refs.append(ref)
                    for ref in refs:
                        if isinstance(ref, dict):
                            self._issued_log_refs[_canonical(ref)] = copy.deepcopy(ref)
                if type(report) is not dict or report.get("passed") is not True:
                    report = {"passed": False, "detail": "protected executor did not report a passing check",
                              "executor_result": _safe_result(report)}
                else:
                    report = _safe_result(report)
            record = {"passed": report.get("passed") is True, "snapshot_sha256": snapshot,
                      "report_sha256": _digest(_canonical(report)), "report": report,
                      "model_ordinal": ordinal}
            self._passing[check] = record
            if all(self._passing.get(required, {}).get("passed") is True and
                   self._passing[required].get("snapshot_sha256") == snapshot
                   for required in ("compile", "unit", "smoke")):
                self._passed_snapshot = snapshot
            else:
                self._passed_snapshot = None
            return {"ok": record["passed"], "check": check, "snapshot_sha256": snapshot, "report": report}
        if action == "read_log":
            self._exact_args(args, {"ref"})
            ref = args["ref"]
            if type(ref) is not dict or _canonical(ref) not in self._issued_log_refs:
                raise ValueError("log reference was not issued by this Builder session's check runner")
            if self._read_log is None:
                raise ValueError("no protected log reader is configured")
            remaining = max(0.001, self._deadline - time.monotonic())
            try:
                value = await asyncio.wait_for(self._read_log(copy.deepcopy(ref)), timeout=remaining)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                raise
            except Exception as exc:
                raise RuntimeError("protected log reader failed") from exc
            return {"ok": True, "ref": ref, "log": _safe_result(value)}
        if action == "report_blocked":
            self._exact_args(args, {"reason"})
            reason = args["reason"]
            if type(reason) is not str or not reason.strip():
                raise ValueError("reason must be nonempty text")
            return {"blocked": True, "reason": reason[:1000], "snapshot_sha256": self.snapshot_sha256}
        if action == "submit_candidate":
            self._exact_args(args, set())
            snapshot = self._snapshot()["sha256"]
            if self._passed_snapshot != snapshot:
                return {"ok": False, "error": "current_snapshot_lacks_compile_unit_smoke_passes", "snapshot_sha256": snapshot}
            payload = {name: self._files[name] for name in DELIVERY_FILES}
            bundle, encoded = package(payload)
            self._submitted = {"submitted": True, "session_id": self.session_id,
                               "snapshot_sha256": snapshot, "files": payload,
                               "file_hashes": {name: _digest(raw) for name, raw in encoded.items()},
                               "journal": copy.deepcopy(self._journal),
                               "tests": self._files["tests.py"],
                               "checks": copy.deepcopy(self._passing),
                               "bundle_bytes": bundle, "bundle_sha256": _digest(bundle)}
            return self._submitted
        raise ValueError("unsupported action")

    @staticmethod
    def _exact_args(args: dict, required: set[str], allowed: set[str] | None = None) -> None:
        allowed = required if allowed is None else allowed
        if not required <= set(args) or not set(args) <= allowed:
            raise ValueError("arguments do not match the action schema")

    def _invalidate_checks(self) -> None:
        self._passing.clear()
        self._passed_snapshot = None

    def _record(self, action: Any, args: Any, ordinal: Any, before: str, result: Any) -> dict[str, Any]:
        if isinstance(result,dict) and result.get('blocked') is True:
            self._stopped_reason=result.get('error',result.get('reason','blocked'))
        # Keep binary package bytes out of the journal while returning the exact
        # package object to the trusted caller that publishes the candidate.
        journal_value = result
        if action == "submit_candidate" and isinstance(result, dict) and result.get("submitted"):
            journal_value = {key: result.get(key) for key in (
                "submitted", "session_id", "snapshot_sha256", "file_hashes", "bundle_sha256"
            )}
        safe_result = _safe_result(journal_value)
        after = self._snapshot()["sha256"]
        row = {"sequence": self._tool_calls, "action": action if type(action) is str else "<invalid>",
               "model_ordinal": ordinal if type(ordinal) is int else None,
               "arguments_sha256": _digest(_canonical(args)), "before_snapshot_sha256": before,
               "after_snapshot_sha256": after, "result_sha256": _digest(_canonical(safe_result)),
               "result": safe_result, "evidence_ref": result.get("evidence_ref") if isinstance(result, dict) else None}
        self._journal.append(row)
        if action == "submit_candidate" and self._submitted is not None:
            self._submitted["journal"] = copy.deepcopy(self._journal)
        if action == "submit_candidate" and isinstance(result, dict) and result.get("submitted"):
            return copy.deepcopy(self._submitted)
        return copy.deepcopy(safe_result) if isinstance(safe_result, dict) else {"result": safe_result}
