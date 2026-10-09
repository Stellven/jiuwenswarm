"""Protected local intake qualification. No semantic readiness judgment."""
from __future__ import annotations

import os
from pathlib import Path

from .config import Config
from .store import Store, digest


class IntakeError(ValueError):
    def __init__(self, reason, rejections=None):
        super().__init__(reason)
        self.reason = reason
        self.rejections = rejections or [reason]


def _confined(config: Config, locator: str | Path) -> Path:
    root = config.input_root
    raw = Path(locator)
    path = raw if raw.is_absolute() else root / raw
    if ".." in raw.parts or not path.absolute().is_relative_to(root):
        raise IntakeError("Input path is outside the authorized root")
    cursor = path.absolute()
    while True:
        if cursor.is_symlink() or (cursor.exists() and getattr(cursor, "is_junction", lambda: False)()):
            raise IntakeError("Input symlink/junction is not permitted")
        if cursor == root:
            break
        if cursor.parent == cursor:
            raise IntakeError("Input path does not resolve inside authorized root")
        cursor = cursor.parent
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise IntakeError("Input path escapes authorized root")
    return resolved


def _read(path: Path, bound: int) -> bytes:
    if not path.is_file():
        raise IntakeError("Input is not a readable regular file")
    with path.open("rb") as stream:
        data = stream.read(bound + 1)
    if not data or len(data) > bound:
        raise IntakeError("Input file is empty or exceeds configured byte limit")
    return data


def qualify(config: Config, store: Store, run_id: str, request: str, documents=None,
            resources=None, input_directory=None) -> dict:
    documents = list(documents or [])
    resources = list(resources or [])
    rejections: list[str] = []
    store.register_profile(config.account_id, {"account_id": config.account_id, "workspace_id": config.workspace_id})
    try:
        # Rejection is also an inspectable attempt; capture original text before qualification.
        if isinstance(request, str):
            request_bytes = request.encode("utf-8")
            if len(request_bytes) <= config.max_resource_bytes:
                request_ref = store.put_bytes(run_id, "Request.txt", request_bytes, artifact_type="original-request", media_type="text/plain; charset=utf-8")
            else:
                store.put_json(run_id, "Original_Request_Unavailable.json", {
                    "sha256": digest(request_bytes), "bytes": len(request_bytes),
                    "reason": "Rejected original request exceeds protected evidence-capture limit; body unavailable"})
        descriptors = []
        for role, items in (("reference_document", documents), ("resource", resources)):
            for index, item in enumerate(items):
                descriptor = {"path": item} if isinstance(item, str) else item
                if not isinstance(descriptor, dict):
                    descriptor = {"invalid_type": type(item).__name__}
                safe = dict(descriptor)
                locator = safe.get("path")
                if isinstance(locator, str) and Path(locator).is_absolute():
                    try:
                        safe["path"] = Path(locator).relative_to(config.input_root).as_posix()
                    except ValueError:
                        safe["path"] = "outside-authorized-root"
                descriptors.append({"index": index, "role": descriptor.get("role", role),
                                    "required": descriptor.get("required", True), "descriptor": safe,
                                    "original_descriptor_sha256": digest(json_bytes_for(descriptor))})
        store.put_json(run_id, "Intake_Descriptors.json", {"inputs": descriptors})
        if not isinstance(request, str) or not request.strip():
            raise IntakeError("Original request must be nonempty")
        if len(request.encode("utf-8")) > config.max_source_bytes:
            raise IntakeError("Original request exceeds configured byte limit")
        profile_ref = store.put_json(run_id, "Local_Profile.json", {"id": "profile:" + config.account_id,
                                      "user_id": config.account_id, "workspace_id": config.workspace_id,
                                      "synthetic": False})
        workspace_ref = store.put_json(run_id, "Workspace.json", {"id": config.workspace_id, "user_id": config.account_id,
                                        "access": "supplied-input-read-only"})
        # An empty default directory is legitimate, but an explicitly missing one is not.
        specified = input_directory is not None or config.input_directory is not None
        directory_locator = input_directory if input_directory is not None else config.input_directory
        if directory_locator is None:
            default = config.input_root / "docs"
            default.mkdir(parents=True, exist_ok=True)
            directory_locator = default
        directory = _confined(config, directory_locator)
        if not directory.is_dir():
            raise IntakeError("Input directory is not readable")
        entries = sorted(directory.iterdir(), key=lambda p: p.name)
        directory_ref = store.put_json(run_id, "Input_Directory.json", {"id": "directory:input",
                                       "role": "reference-documents", "specified": specified,
                                       "entries": [p.name for p in entries]})
        # Both advertised reference-document entry points share extraction and qualification.
        # Explicit resource metadata precedes directory discovery for the same file.
        documents.extend(dict(item) for item in resources
                         if isinstance(item, dict) and item.get("role") == "reference_document")
        for entry in entries:
            documents.append({"path": str(entry), "required": True})
        sources = {request_ref["id"]: {"text": request, "ref": request_ref}}
        source_refs, resource_refs, registrations = [], [], []
        seen_paths = set()
        for index, item in enumerate(documents):
            item = {"path": item} if isinstance(item, str) else item
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise IntakeError("Document descriptor requires a path")
            required = item.get("required", True)
            try:
                path = _confined(config, item["path"])
                if path in seen_paths:
                    continue
                if path.suffix.lower() not in (".txt", ".md", ".pdf"):
                    raise IntakeError("Unsupported reference document extension")
                raw = _read(path, config.max_source_bytes)
                original_ref = store.put_bytes(run_id, f"inputs/document-{index}{path.suffix.lower()}", raw,
                                  artifact_type="original-document", media_type="application/pdf" if path.suffix.lower() == ".pdf" else "text/plain; charset=utf-8")
                if path.suffix.lower() == ".pdf":
                    import io
                    from pypdf import PdfReader
                    from pypdf.errors import PyPdfError
                    try:
                        reader = PdfReader(io.BytesIO(raw))
                        if reader.is_encrypted:
                            raise IntakeError("Encrypted PDF is unsupported")
                        text = "\n".join(page.extract_text() or "" for page in reader.pages)
                    except PyPdfError as exc:
                        raise IntakeError("PDF extraction failed: " + type(exc).__name__) from exc
                else:
                    text = raw.decode("utf-8")  # Keep BOM, CRLF and codepoints exactly.
                if not text.strip() or len(text.encode("utf-8")) > config.max_source_bytes:
                    raise IntakeError("Extracted document text is empty or exceeds configured limit")
                text_ref = store.put_bytes(run_id, f"inputs/document-{index}.extracted.txt", text.encode("utf-8"),
                                 artifact_type="extracted-source", media_type="text/plain; charset=utf-8", source_refs=[original_ref])
                sources[text_ref["id"]] = {"text": text, "ref": text_ref}
                source_refs.append(text_ref)
                reg = {"schema_version": "1.0.0", "id": f"resource:document-{index}",
                       "kind": "reference_document", "origin": str(path.relative_to(config.input_root)),
                       "revision": original_ref["sha256"], "files": [{"path": original_ref["id"], "artifact_ref": original_ref,
                           "media_type": "application/pdf" if path.suffix.lower() == ".pdf" else "text/plain", "audience": "authorized-user"}],
                       "access": "read-only-reference", "license": item.get("license", "unknown"), "availability": "available", "environment_ref": None,
                       "ext": {"m0.intake": {"extracted_ref": text_ref, "original_bytes": len(raw), "qualification": "supported-readable-bounded"}}}
                rr = store.put_json(run_id, f"Resource_Document_{index}.json", reg, artifact_type="resource-snapshot")
                resource_refs.append(rr)
                registrations.append(reg)
                seen_paths.add(path)
            except (OSError, ValueError, RuntimeError) as exc:
                detail = "Local file unavailable or unreadable" if isinstance(exc, OSError) else str(exc)
                reason = f"document-{index}: {type(exc).__name__}: {detail}"
                rejections.append(reason)
                if required:
                    raise IntakeError("Required document failed qualification", rejections) from exc
        for index, item in enumerate(resources):
            if not isinstance(item, dict) or item.get("role") not in ("project_asset", "validation_data", "reference_document"):
                raise IntakeError("Resource requires a supported explicit role")
            if item["role"] == "reference_document":
                continue  # Already captured as original bytes plus extracted reasoning text above.
            try:
                path = _confined(config, item["path"])
                captured = []
                total = 0
                if path.is_dir():
                    paths = []
                    for base, dirs, names in os.walk(path, followlinks=False):
                        for name in dirs + names:
                            child = Path(base) / name
                            _confined(config, child)
                        paths.extend(Path(base) / name for name in names)
                else:
                    paths = [path]
                for file_index, source_path in enumerate(sorted(paths)):
                    raw = _read(source_path, config.max_resource_bytes - total)
                    total += len(raw)
                    if total > config.max_resource_bytes:
                        raise IntakeError("Resource snapshot exceeds aggregate byte limit")
                    name = f"inputs/resource-{index}/file-{file_index}{source_path.suffix}"
                    ref = store.put_bytes(run_id, name, raw, artifact_type="resource-file")
                    captured.append({"path": name, "artifact_ref": ref, "media_type": "application/octet-stream", "audience": "authorized-user"})
                if not captured:
                    raise IntakeError("Supplied resource is empty")
                reg = {"schema_version": "1.0.0", "id": f"resource:asset-{index}", "kind": item["role"],
                       "origin": str(path.relative_to(config.input_root)), "revision": digest(json_bytes_for(captured)),
                       "files": captured, "access": "read-only-captured-resource", "license": item.get("license", "unknown"),
                       "availability": "available", "environment_ref": None}
                rr = store.put_json(run_id, f"Resource_Asset_{index}.json", reg, artifact_type="resource-snapshot")
                resource_refs.append(rr)
                registrations.append(reg)
            except (OSError, ValueError, RuntimeError, KeyError) as exc:
                detail = "Local file unavailable or unreadable" if isinstance(exc, OSError) else str(exc)
                reason = f"resource-{index}: {type(exc).__name__}: {detail}"
                rejections.append(reason)
                if item.get("required", True):
                    raise IntakeError("Required resource failed qualification", rejections) from exc
        intake = {"schema_version": "2.0.0", "id": "intake:" + run_id, "request_ref": request_ref,
                  "source_refs": source_refs, "offset_basis": "Unicode code points", "resource_refs": resource_refs,
                  "rejected_inputs": rejections, "user_id": config.account_id, "profile_ref": profile_ref,
                  "workspace_ref": workspace_ref, "input_directory_ref": directory_ref}
        intake_ref = store.put_json(run_id, "Qualified_Intake.json", intake, artifact_type="qualified-intake", schema_version="2.0.0")
        store.put_json(run_id, "Qualification.json", {"status": "qualified", "registrations": registrations,
                                                       "rejected_inputs": rejections, "source_refs": [request_ref] + source_refs})
        return {"intake_ref": intake_ref, "intake": intake, "sources": sources, "resource_refs": resource_refs}
    except (OSError, ValueError, RuntimeError) as exc:
        reasons = getattr(exc, "rejections", None) or rejections or [str(exc)]
        store.put_json(run_id, "Intake_Rejection.json", {"schema_version": "1.0.0", "id": "rejection:" + run_id,
                        "status": "rejected", "reasons": reasons, "model_calls": 0})
        raise IntakeError(str(exc), reasons) from exc


def json_bytes_for(value):
    from .store import json_bytes
    return json_bytes(value)
