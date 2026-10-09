from pathlib import Path
import hashlib
import sqlite3

import pytest

from intent_compiler.config import Config
from intent_compiler.intake import IntakeError, qualify
from intent_compiler.store import Store, StoreError, Conflict, Busy


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    config = Config(tmp_path / "state", root, auth_token="unit-test-only")
    store = Store(config.state_dir)
    run_id, _ = store.create_run("case", {"request": "Compare retrieval latency; produce a report."}, config.account_id, config.workspace_id)
    return config, store, run_id


def test_intake_exact_request_unicode_crlf(setup):
    config, store, run_id = setup
    text = "Compare 🧪 latency.\r\nReturn a report; preserve quality."
    out = qualify(config, store, run_id, text)
    ref = out["intake"]["request_ref"]
    assert ref["sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert store.read_bytes(run_id, ref) == text.encode("utf-8")
    assert out["sources"][ref["id"]]["text"] == text
    assert out["intake"]["offset_basis"] == "Unicode code points"
    assert out["intake"]["source_refs"] == []  # empty authorized default is permitted


@pytest.mark.parametrize("text", ["", " \r\n\t"])
def test_intake_empty_rejection_keeps_reason(setup, text):
    config, store, run_id = setup
    with pytest.raises(IntakeError):
        qualify(config, store, run_id, text)
    record = store.get_json(run_id, "Intake_Rejection.json")
    assert record["status"] == "rejected" and record["model_calls"] == 0
    assert store.read_bytes(run_id, "Request.txt") == text.encode("utf-8")


def test_intake_documents_preserve_bytes_and_roles(setup):
    config, store, run_id = setup
    (config.input_root / "notes.md").write_bytes(b"\xef\xbb\xbfContext\r\nDo not change quality.\r\n")
    (config.input_root / "assets").mkdir()
    (config.input_root / "assets" / "data.csv").write_bytes(b"value\n1\n")
    out = qualify(config, store, run_id, "Compare latency and deliver a report.",
                  documents=["notes.md"], resources=[{"path": "assets", "role": "validation_data"}])
    text_ref = out["intake"]["source_refs"][0]
    assert out["sources"][text_ref["id"]]["text"] == "\ufeffContext\r\nDo not change quality.\r\n"
    assert len(out["resource_refs"]) == 2
    roles = [store.get_json(run_id, r)["kind"] for r in out["resource_refs"]]
    assert roles == ["reference_document", "validation_data"]
    assert all("1\n" not in s["text"] for s in out["sources"].values())
    assert store.read_bytes(run_id, "inputs/document-0.md") == (config.input_root / "notes.md").read_bytes()


def _simple_pdf():
    # Independent minimal one-page fixture with literal text and correct xref.
    content = b"BT /F1 12 Tf 72 720 Td (Compare latency and return a report.) Tj ET"
    bodies = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
              b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
              b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
              b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for i, body in enumerate(bodies, 1):
        offsets.append(len(data))
        data += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    start = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return data + b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(start).encode() + b"\n%%EOF\n"


def test_intake_pdf_has_distinct_original_and_extracted_identity(setup):
    config, store, run_id = setup
    original = _simple_pdf()
    (config.input_root / "ref.pdf").write_bytes(original)
    out = qualify(config, store, run_id, "Evaluate latency.", documents=["ref.pdf"])
    ref = out["intake"]["source_refs"][0]
    assert store.read_bytes(run_id, "inputs/document-0.pdf") == original
    assert "Compare latency and return a report." in out["sources"][ref["id"]]["text"]
    assert ref["sha256"] != hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize("suffix", [".txt", ".md", ".pdf"])
def test_reference_resource_uses_document_extraction_and_preserves_license(setup, suffix):
    config, store, run_id = setup
    original = _simple_pdf() if suffix == ".pdf" else "Preserve quality.\r\nUse Unicode: \u03b1.\r\n".encode("utf-8")
    path = "reference" + suffix
    (config.input_root / path).write_bytes(original)
    out = qualify(config, store, run_id, "Compare latency.", resources=[{
        "path": path, "role": "reference_document", "license": "CC-BY-4.0"}])
    assert len(out["intake"]["source_refs"]) == len(out["resource_refs"]) == 1
    text_ref = out["intake"]["source_refs"][0]
    text = out["sources"][text_ref["id"]]["text"]
    assert "Compare latency and return a report." in text if suffix == ".pdf" else text.encode("utf-8") == original
    registration = store.get_json(run_id, out["resource_refs"][0])
    assert registration["kind"] == "reference_document"
    assert registration["license"] == "CC-BY-4.0"
    assert registration["ext"]["m0.intake"]["extracted_ref"] == text_ref
    assert store.read_bytes(run_id, registration["files"][0]["artifact_ref"]) == original
    assert store.get_json(run_id, "Intake_Descriptors.json")["inputs"][0]["role"] == "reference_document"


@pytest.mark.parametrize("kind", ["missing", "unsupported", "invalid_utf8", "bad_pdf", "oversize", "directory"])
def test_required_reference_resource_rejects_before_compilation(setup, kind):
    config, store, run_id = setup
    path = "reference.txt"
    if kind == "unsupported":
        path = "reference.bin"
        (config.input_root / path).write_bytes(b"\xff\xfe")
    elif kind == "invalid_utf8":
        (config.input_root / path).write_bytes(b"\xff\xfe")
    elif kind == "bad_pdf":
        path = "reference.pdf"
        (config.input_root / path).write_bytes(b"not a pdf")
    elif kind == "oversize":
        (config.input_root / path).write_bytes(b"a" * (config.max_source_bytes + 1))
    elif kind == "directory":
        path = "folder.md"
        (config.input_root / path).mkdir()
    with pytest.raises(IntakeError):
        qualify(config, store, run_id, "Compare latency.", resources=[{
            "path": path, "role": "reference_document", "required": True}])
    rejection = store.get_json(run_id, "Intake_Rejection.json")
    assert rejection["model_calls"] == 0 and rejection["reasons"]
    assert store.accepted(run_id, "node") is None


def test_optional_reference_resource_rejection_is_disclosed(setup):
    config, store, run_id = setup
    (config.input_root / "reference.bin").write_bytes(b"\xff\xfe")
    out = qualify(config, store, run_id, "Compare latency.", resources=[{
        "path": "reference.bin", "role": "reference_document", "required": False}])
    assert len(out["intake"]["rejected_inputs"]) == 1
    assert out["intake"]["source_refs"] == out["resource_refs"] == []


def test_reference_resource_directory_discovery_is_deduplicated_with_explicit_license(setup):
    config, store, run_id = setup
    (config.input_root / "docs").mkdir()
    (config.input_root / "docs" / "notes.md").write_bytes(b"Preserve quality.")
    out = qualify(config, store, run_id, "Compare latency.", resources=[{
        "path": "docs/notes.md", "role": "reference_document", "license": "CC-BY-4.0"}])
    assert len(out["intake"]["source_refs"]) == len(out["resource_refs"]) == 1
    assert store.get_json(run_id, out["resource_refs"][0])["license"] == "CC-BY-4.0"


@pytest.mark.parametrize("kind", ["missing", "unsupported", "empty", "oversize", "invalid_utf8", "bad_pdf", "traversal"])
def test_intake_required_invalid_sources_reject(setup, kind):
    config, store, run_id = setup
    if kind == "missing":
        path = "missing.txt"
    elif kind == "unsupported":
        path = "data.docx"
        (config.input_root / path).write_bytes(b"unsupported")
    elif kind == "empty":
        path = "empty.txt"
        (config.input_root / path).write_bytes(b"")
    elif kind == "oversize":
        path = "big.txt"
        (config.input_root / path).write_bytes(b"a" * (config.max_source_bytes + 1))
    elif kind == "invalid_utf8":
        path = "invalid.txt"
        (config.input_root / path).write_bytes(b"\xff\xfe")
    elif kind == "bad_pdf":
        path = "bad.pdf"
        (config.input_root / path).write_bytes(b"not a pdf")
    else:
        path = "../outside.txt"
    with pytest.raises(IntakeError):
        qualify(config, store, run_id, "Compare latency.", documents=[path])
    assert store.get_json(run_id, "Intake_Rejection.json")["reasons"]
    descriptors = store.get_json(run_id, "Intake_Descriptors.json")["inputs"]
    assert descriptors[0]["required"] is True and descriptors[0]["role"] == "reference_document"
    assert store.accepted(run_id, "node") is None


def test_intake_optional_rejection_is_explicit(setup):
    config, store, run_id = setup
    out = qualify(config, store, run_id, "Compare latency.", documents=[{"path": "absent.txt", "required": False}])
    assert len(out["intake"]["rejected_inputs"]) == 1
    assert not out["intake"]["resource_refs"]


def test_intake_optional_failed_duplicate_cannot_waive_required_source(setup):
    config, store, run_id = setup
    (config.input_root / "invalid.txt").write_bytes(b"\xff")
    with pytest.raises(IntakeError):
        qualify(config, store, run_id, "Compare latency.", documents=[
            {"path": "invalid.txt", "required": False}, {"path": "invalid.txt", "required": True}])
    assert len(store.get_json(run_id, "Intake_Rejection.json")["reasons"]) == 2


def test_intake_shared_records_follow_catalog(setup):
    from intent_compiler.checks import validate_field_contract
    config, store, run_id = setup
    (config.input_root / "source.md").write_bytes(b"Preserve quality.")
    out = qualify(config, store, run_id, "Compare latency.", documents=["source.md"])
    assert validate_field_contract("qualified-intake", out["intake"]) == []
    for ref in out["resource_refs"]:
        assert validate_field_contract("resource-snapshot", store.get_json(run_id, ref)) == []


def test_intake_specified_missing_directory_rejects(setup):
    config, store, run_id = setup
    with pytest.raises(IntakeError):
        qualify(config, store, run_id, "Compare latency.", input_directory="missing")


def test_intake_confined_link_denied(setup):
    config, store, run_id = setup
    target = config.input_root.parent / "secret.txt"
    target.write_text("private", encoding="utf-8")
    link = config.input_root / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        # Windows junction directory needs no symlink privilege, exercising same containment.
        import subprocess
        target_dir = config.input_root.parent / "outside"
        target_dir.mkdir()
        (target_dir / "secret.txt").write_bytes(b"private")
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(config.input_root / "junction"), str(target_dir)], capture_output=True)
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        link = config.input_root / "junction" / "secret.txt"
    with pytest.raises(IntakeError):
        qualify(config, store, run_id, "Compare latency.", documents=[str(link)])


def test_immutable_store_rejects_overwrite_swap_and_escape(setup):
    _, store, run_id = setup
    ref = store.put_bytes(run_id, "Candidate.json", b"{}")
    with pytest.raises(StoreError):
        store.put_bytes(run_id, "Candidate.json", b"[]")
    with pytest.raises(StoreError):
        store.put_bytes(run_id, "../escape.txt", b"bad")
    (store.files / run_id / "Candidate.json").write_bytes(b"[]")
    with pytest.raises(StoreError):
        store.read_bytes(run_id, ref)


def test_duplicate_submission_conflict_and_one_active_run(setup):
    config, store, run_id = setup
    original = store.get_run(run_id)["submission"]
    assert store.create_run("case", original, config.account_id, config.workspace_id) == (run_id, False)
    with pytest.raises(Conflict):
        store.create_run("case", {"request": "different"}, config.account_id, config.workspace_id)
    with pytest.raises(Busy):
        store.create_run("new", original, config.account_id, config.workspace_id)
    assert store.find_request("case", config.account_id, config.workspace_id) == run_id


def test_restart_pauses_and_keeps_identity_artifacts_account(setup):
    config, store, run_id = setup
    out = qualify(config, store, run_id, "Compare latency.")
    store.update_run(run_id, status="running", intake_ref=out["intake_ref"])
    instance = store.instance_id
    reopened = Store(config.state_dir)
    reopened.pause_interrupted()
    assert reopened.instance_id == instance
    assert reopened.get_run(run_id)["status"] == "paused"
    assert reopened.read_bytes(run_id, "Request.txt") == b"Compare latency."
    with sqlite3.connect(reopened.accounts_db) as con:
        assert con.execute("SELECT account FROM profiles").fetchall() == [(config.account_id,)]


def test_cancel_is_persisted_and_no_completion_without_release(setup):
    _, store, run_id = setup
    cancel = store.request_cancel(run_id, "cancel-1")
    assert cancel["status"] == "acknowledged" and store.cancelled(run_id)
    with pytest.raises(StoreError):
        store.update_run(run_id, status="running")
    with pytest.raises(StoreError):
        store.update_run(run_id, status="completed")
    assert store.get_run(run_id)["accepted_refs"] == []


def test_cancel_reconciliation_retains_same_record_after_terminal(setup):
    _, store, run_id = setup
    first = store.request_cancel(run_id, "cancel-1")
    store.update_run(run_id, status="cancelled")
    assert store.request_cancel(run_id, "cancel-1") == first
    assert store.request_cancel(run_id, "cancel-2")["status"] == "terminal"
    assert store.get_run(run_id)["status"] == "cancelled"


def test_capture_failure_never_registers_absent_artifact(setup, monkeypatch):
    _, store, run_id = setup
    def fail(_):
        raise OSError("injected durable-write failure")
    monkeypatch.setattr("intent_compiler.store.os.fsync", fail)
    with pytest.raises(OSError):
        store.put_bytes(run_id, "not-durable.txt", b"candidate")
    assert all(r["id"] != "not-durable.txt" for r in store.artifacts(run_id))
    assert store.accepted(run_id, "node") is None


def test_config_freeze_contains_no_token_or_host_paths(setup):
    config, _, _ = setup
    import json
    text = json.dumps(config.freeze())
    assert config.auth_token not in text and str(config.state_dir) not in text
    assert config.freeze()["hardware_readiness"]["available"] is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1, True])
def test_config_rejects_nonfinite_or_invalid_headless_budget(tmp_path, value):
    with pytest.raises(ValueError):
        Config(tmp_path / "state", tmp_path / "input", call_time_s=value)


@pytest.mark.parametrize("mode,profile", [("smoke", "compiler-only"), ("codex", "compiler-smoke"), ("arbitrary", "compiler-only")])
def test_config_rejects_unapproved_or_mislabelled_route(tmp_path, mode, profile):
    with pytest.raises(ValueError):
        Config(tmp_path / "state", tmp_path / "input", model_mode=mode, profile_id=profile)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_config_rejects_invalid_optional_token_budget(tmp_path, value):
    with pytest.raises(ValueError):
        Config(tmp_path / "state", tmp_path / "input", token_budget=value)
