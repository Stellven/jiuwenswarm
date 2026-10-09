"""M0-001/V05: actual API/storage/runtime boundaries; model fixtures labelled."""

import hashlib
import io
import json
import threading
import time
import zipfile

from fastapi.testclient import TestClient
import httpx
import pytest

from intent_compiler.api import create_app
from intent_compiler.checks import validate_field_contract
from intent_compiler.client import CompilerClient, ClientError, cli
from intent_compiler.config import Config
from intent_compiler.runtime import Runtime, SmokeBridge
from intent_compiler.store import Store, StoreError


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    config = Config(tmp_path / "state", root, auth_token="test-token-not-real",
                    model_mode="smoke", profile_id="compiler-smoke")
    store = Store(config.state_dir)
    runtime = Runtime(config, store)
    app = create_app(config, store, runtime)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + config.auth_token}
    with client:
        yield config, store, runtime, app, client, headers


def payload(client, headers, request_id="api-case"):
    ready = client.get("/api/v1/readiness", headers=headers).json()
    return {"schema_version": "1.0.0", "id": "submission:" + request_id,
            "client_request_id": request_id, "account_id": "local-user", "workspace_id": "local-workspace",
            "profile_id": "compiler-smoke", "expected_instance_id": ready["instance_id"],
            "expected_build_id": ready["build_id"], "client_contract_version": "1.0.0",
            "request": "Compare method A with method B on supplied validation data; preserve a qualitative accuracy goal.",
            "documents": [], "resources": []}


def finish(client, headers, run_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        data = client.get("/api/v1/runs/" + run_id, headers=headers).json()
        if data["status"] in {"completed", "halted", "cancelled", "paused"}:
            return data
        time.sleep(.02)
    pytest.fail("Fixture runtime did not finish in the finite test wait")


def test_authenticated_readiness_contract_and_writable_capture(setup):
    config, store, runtime, app, client, headers = setup
    denied = client.get("/api/v1/readiness")
    assert denied.status_code == 401
    assert not validate_field_contract("client-error", denied.json())
    ready = client.get("/api/v1/readiness", headers=headers)
    assert ready.status_code == 200
    data = ready.json()
    assert not validate_field_contract("client-readiness", data)
    assert data["ready"]
    assert data["ext"]["m0.intent"]["invalid_for_product"]
    assert data["ext"]["m0.intent"]["schema_versions"]["research-brief"] == "2.0.0"
    assert store.artifacts("readiness-probe")
    assert config.auth_token not in json.dumps(data)
    assert client.get("/api/v1/readiness", headers={**headers, "Origin": "http://untrusted.test"}).status_code == 403
    assert client.get("/api/v1/readiness", headers={**headers, "X-Workspace-ID": "different"}).status_code == 403


@pytest.mark.parametrize("field,value,status_code", [
    ("account_id", "other", 403), ("workspace_id", "other", 403),
    ("profile_id", "disable-gates", 409), ("expected_instance_id", "other", 409),
    ("expected_build_id", "other", 409), ("schema_version", "0.9.0", 422),
    ("client_contract_version", "9.0.0", 422), ("gate_verdict", "PASS", 422),
])
def test_wrong_scope_target_profile_version_or_authority_rejected(setup, field, value, status_code):
    _, _, runtime, _, client, headers = setup
    body = payload(client, headers)
    body[field] = value
    rejected = client.post("/api/v1/runs", json=body, headers=headers)
    assert rejected.status_code == status_code
    assert not validate_field_contract("client-error", rejected.json())
    assert not runtime.bridge.calls


def test_submission_reconciliation_release_and_hash_exact_named_export(setup):
    config, store, runtime, _, client, headers = setup
    body = payload(client, headers)
    first = client.post("/api/v1/runs", json=body, headers=headers)
    assert first.status_code == 202
    run_id = first.json()["run_id"]
    final = finish(client, headers, run_id)
    assert final["status"] == "completed", final
    assert not validate_field_contract("client-status", final)
    repeated = client.post("/api/v1/runs", json=body, headers=headers)
    assert repeated.status_code == 202
    assert repeated.json()["run_id"] == run_id
    assert len(runtime.bridge.calls) == 4
    reconciled = client.get("/api/v1/requests/" + body["client_request_id"], headers=headers)
    assert reconciled.json()["run_id"] == run_id
    changed = {**body, "request": body["request"] + " changed"}
    assert client.post("/api/v1/runs", json=changed, headers=headers).status_code == 409
    canonical_ref = final["ext"]["m0.intent"]["submission_ref"]
    assert not validate_field_contract("client-submission", store.get_json(run_id, canonical_ref))
    response = client.get("/api/v1/runs/" + run_id + "/manifest", headers=headers)
    manifest = response.json()
    assert not validate_field_contract("client-retrieval", manifest)
    paths = {f["path"] for f in manifest["files"]}
    assert {"Request.txt", "Qualified_Intake.json", "Intent_IR.json", "Research_Brief.json", "Accepted_node.json", "Gate_Node.json"}.issubset(paths)
    bundle_ref = manifest["ext"]["m0.intent"]["bundle_ref"]
    assert not validate_field_contract("run-bundle", store.get_json(run_id, bundle_ref))
    manifest_again = client.get("/api/v1/runs/" + run_id + "/manifest", headers=headers).json()
    assert manifest_again["id"] == manifest["id"]
    archive = client.get("/api/v1/runs/" + run_id + "/bundle", headers=headers)
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zip:
        for file in manifest["files"]:
            captured = zip.read(file["path"])
            assert hashlib.sha256(captured).hexdigest() == file["artifact_ref"]["sha256"]
            assert config.auth_token.encode() not in captured
    result = client.get("/api/v1/runs/" + run_id + "/result", headers=headers)
    assert result.status_code == 200
    assert result.json()["research_brief"]["schema_version"] == "2.0.0"
    assert result.json()["output_refs"] == [store.accepted(run_id, "node")]
    assert result.json()["node_acceptance_ref"] == store.acceptance_record(run_id, "node")
    assert client.get("/api/v1/runs/" + run_id + "/result?schema_version=1.0.0", headers=headers).status_code == 409
    assert client.get("/api/v1/runs/" + run_id + "/result?artifact_id=Intent_IR.json", headers=headers).status_code == 409
    assert client.get("/api/v1/runs/" + run_id + "/manifest?audience=verifier", headers=headers).status_code == 403


def test_failed_intake_retained_export_and_fresh_correction_link(setup):
    _, store, runtime, _, client, headers = setup
    body = payload(client, headers)
    body["documents"] = [{"path": "does-not-exist.md", "required": True}]
    rejected = client.post("/api/v1/runs", json=body, headers=headers)
    assert rejected.status_code == 422
    run_id = rejected.json()["run_id"]
    assert not runtime.bridge.calls
    assert client.get("/api/v1/runs/" + run_id + "/result", headers=headers).status_code == 409
    manifest = client.get("/api/v1/runs/" + run_id + "/manifest", headers=headers).json()
    assert not validate_field_contract("client-retrieval", manifest)
    assert manifest["ext"]["m0.intent"]["missing_evidence"]
    corrected = payload(client, headers, "corrected-request")
    corrected["previous_run_id"] = run_id
    response = client.post("/api/v1/runs", json=corrected, headers=headers)
    assert response.status_code == 202
    assert response.json()["run_id"] != run_id
    final = finish(client, headers, response.json()["run_id"])
    assert final["status"] == "completed"
    assert store.get_run(run_id)["status"] == "halted"
    assert store.get_run(final["run_id"])["previous_run_id"] == run_id


def test_resource_only_reference_document_reaches_disclosed_reasoning_with_exact_binding(setup):
    config, store, runtime, _, client, headers = setup
    supplied = config.input_root / "supplied"
    supplied.mkdir()
    constraint = "\ufeffKeep all evaluation data on the approved local device.\r\n不要修改原始验证数据。\r\n"
    original_bytes = constraint.encode("utf-8")
    (supplied / "constraints.md").write_bytes(original_bytes)
    data_text = "VALIDATION_DATA_SENTINEL_8675309\n"
    asset_text = "PROJECT_ASSET_SENTINEL_314159\n"
    (supplied / "validation.csv").write_text(data_text, encoding="utf-8")
    (supplied / "asset.txt").write_text(asset_text, encoding="utf-8")
    body = payload(client, headers, "resource-only-reference")
    assert body["documents"] == []
    body["resources"] = [
        {"path": "supplied/constraints.md", "role": "reference_document", "license": "CC-BY-4.0-test-fixture"},
        {"path": "supplied/validation.csv", "role": "validation_data", "license": "validation-test-license"},
        {"path": "supplied/asset.txt", "role": "project_asset", "license": "asset-test-license"},
    ]
    submitted = client.post("/api/v1/runs", json=body, headers=headers)
    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]
    final = finish(client, headers, run_id)
    assert final["status"] == "completed", final
    assert len(runtime.bridge.calls) == 4
    intake = store.get_json(run_id, final["ext"]["m0.intent"]["intake_ref"])
    assert not validate_field_contract("qualified-intake", intake)
    assert len(intake["source_refs"]) == 1
    source_ref = intake["source_refs"][0]
    assert store.read_bytes(run_id, source_ref) == original_bytes
    snapshots = {store.get_json(run_id, ref)["kind"]: (ref, store.get_json(run_id, ref))
                 for ref in intake["resource_refs"]}
    assert set(snapshots) == {"reference_document", "validation_data", "project_asset"}
    reference_ref, reference = snapshots["reference_document"]
    assert reference["license"] == "CC-BY-4.0-test-fixture"
    assert reference["ext"]["m0.intake"]["extracted_ref"] == source_ref
    assert store.read_bytes(run_id, reference["files"][0]["artifact_ref"]) == original_bytes
    assert reference["revision"] == hashlib.sha256(original_bytes).hexdigest()
    disclosed = store.get_json(run_id, "intention_Disclosed_Input.json")
    assert disclosed["intake"]["source_refs"] == [source_ref]
    assert disclosed["sources"][source_ref["id"]] == {"text": constraint, "ref": source_ref}
    assert any(binding["role"] == "reference_document" and binding["resource_ref"] == reference_ref
               for binding in disclosed["resource_bindings"])
    reasoning_text = "\n".join(source["text"] for source in disclosed["sources"].values())
    assert data_text.strip() not in reasoning_text
    assert asset_text.strip() not in reasoning_text
    for role, license_name in (("validation_data", "validation-test-license"), ("project_asset", "asset-test-license")):
        resource_ref, snapshot = snapshots[role]
        assert snapshot["license"] == license_name
        assert any(binding["role"] == role and binding["resource_ref"] == resource_ref
                   for binding in disclosed["resource_bindings"])
    assert source_ref in store.get_json(run_id, "Intent_IR.json")["context_refs"]


def test_storage_prerequisite_failure_is_explicit(setup, monkeypatch):
    _, store, _, _, client, headers = setup
    real_put = store.put_bytes
    def fail_probe(run_id, *args, **kwargs):
        if run_id == "readiness-probe":
            raise StoreError("injected read-only storage")
        return real_put(run_id, *args, **kwargs)
    monkeypatch.setattr(store, "put_bytes", fail_probe)
    ready = client.get("/api/v1/readiness", headers=headers).json()
    assert not ready["ready"]
    assert next(p for p in ready["prerequisites"] if p["name"] == "storage")["status"] == "unavailable"


def test_candidate_brief_has_no_external_consumer_before_node_commit(tmp_path):
    entered, proceed = threading.Event(), threading.Event()
    root = tmp_path / "input"
    root.mkdir()
    config = Config(tmp_path / "state", root, auth_token="test-token", profile_id="compiler-smoke", model_mode="smoke")
    store = Store(config.state_dir)
    class LastReviewBridge(SmokeBridge):
        def invoke(self, **kwargs):
            if kwargs["role"] == "requirements.verifier":
                entered.set()
                assert proceed.wait(5)
            return super().invoke(**kwargs)
    runtime = Runtime(config, store, bridge=LastReviewBridge())
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(create_app(config, store, runtime)) as client:
        submitted = client.post("/api/v1/runs", json=payload(client, headers), headers=headers)
        run_id = submitted.json()["run_id"]
        assert entered.wait(3)
        assert any(x["id"] == "Research_Brief.json" for x in store.artifacts(run_id))
        assert store.accepted(run_id, "node") is None
        rejected = client.get("/api/v1/runs/" + run_id + "/result?artifact_id=Research_Brief.json", headers=headers)
        assert rejected.status_code == 409
        assert rejected.json()["category"] == "result_not_released"
        proceed.set()
        assert finish(client, headers, run_id)["status"] == "completed"
        assert client.get("/api/v1/runs/" + run_id + "/result", headers=headers).status_code == 200


def test_server_worker_survives_transport_disconnect_and_explicit_cancel(tmp_path):
    entered, proceed = threading.Event(), threading.Event()
    root = tmp_path / "input"
    root.mkdir()
    config = Config(tmp_path / "state", root, auth_token="test-token", profile_id="compiler-smoke", model_mode="smoke")
    store = Store(config.state_dir)
    class ControlledBridge(SmokeBridge):
        def invoke(self, **kwargs):
            if not self.calls:
                entered.set()
                assert proceed.wait(5)
            return super().invoke(**kwargs)
    runtime = Runtime(config, store, bridge=ControlledBridge())
    app = create_app(config, store, runtime)
    headers = {"Authorization": "Bearer test-token"}
    transport = TestClient(app)
    with transport:
        body = payload(transport, headers)
        response = transport.post("/api/v1/runs", json=body, headers=headers)
        run_id = response.json()["run_id"]
        assert entered.wait(3)
        # A disconnected independent client leaves server-owned execution alive.
        separate_client = TestClient(app)
        separate_client.close()
        assert store.get_run(run_id)["status"] not in {"cancelled", "halted"}
        cancel_body = {"schema_version": "1.0.0", "id": "cancel-1", "request_id": "cancel-1", "run_id": run_id}
        cancelled = transport.post("/api/v1/runs/" + run_id + "/cancel", json=cancel_body, headers=headers)
        assert cancelled.status_code == 200
        assert not validate_field_contract("client-cancellation", cancelled.json())
        proceed.set()
        final = finish(transport, headers, run_id)
        assert final["status"] == "cancelled"
        assert len(runtime.bridge.calls) == 1
        duplicate = transport.post("/api/v1/runs/" + run_id + "/cancel", json=cancel_body, headers=headers)
        assert duplicate.status_code == 200
        assert duplicate.json() == cancelled.json()
        assert transport.get("/api/v1/runs/" + run_id + "/bundle", headers=headers).status_code == 200


def test_headless_finite_wait_halt_and_no_automatic_resubmit(tmp_path, monkeypatch, capsys):
    requests = []
    status = {"schema_version": "1.0.0", "id": "status:test:1", "client_request_id": "test", "run_id": "test-run",
              "revision": 1, "stage": "halted", "status": "halted", "candidate_refs": [], "accepted_refs": [],
              "decision_ref": None, "reasons": ["Semantic failure"], "bundle_ref": None}
    readiness = {"schema_version": "1.0.0", "id": "readiness:test", "client_contract_version": "1.0.0", "instance_id": "test", "build_id": "test-build",
                 "operations": ["submit"], "prerequisites": [], "ready": True,
                 "ext": {"m0.intent": {"profiles": ["compiler-only"]}}}
    def handler(request):
        requests.append(request)
        if request.url.path.endswith("readiness"):
            return httpx.Response(200, json=readiness)
        if request.url.path.endswith("/bundle"):
            return httpx.Response(200, content=b"labelled-test-export")
        if request.method == "POST":
            raise httpx.ReadError("ambiguous delivery", request=request)
        return httpx.Response(200, json=status)
    transport = httpx.MockTransport(handler)
    real_init = CompilerClient.__init__
    def initialise(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)
    monkeypatch.setattr(CompilerClient, "__init__", initialise)
    export = tmp_path / "failed.zip"
    assert cli(["run", "--request", "actionable", "--client-request-id", "test", "--export", str(export), "--timeout", "1"]) == 2
    assert export.read_bytes() == b"labelled-test-export"
    assert sum(request.method == "POST" for request in requests) == 1
    assert any("/requests/test" in request.url.path for request in requests)
    client = CompilerClient("http://test", "test")
    monkeypatch.setattr(client, "status", lambda run_id: {**status, "status": "running"})
    with pytest.raises(ClientError, match="Finite client wait"):
        client.wait("test-run", timeout=.03, poll_interval=.01)
    client.close()


def test_deep_feature_state_export_keeps_compact_paths_and_exact_hashes(tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    # Reproduces the long feature/evidence root observed by the actual live client.
    state = tmp_path / ("s" * max(1, 150 - len(str(tmp_path))))
    config = Config(state, input_root, auth_token="deep-test-token", model_mode="smoke", profile_id="compiler-smoke")
    store = Store(state)
    headers = {"Authorization": "Bearer deep-test-token"}
    with TestClient(create_app(config, store, Runtime(config, store))) as client:
        submitted = client.post("/api/v1/runs", json=payload(client, headers), headers=headers)
        run_id = submitted.json()["run_id"]
        assert finish(client, headers, run_id)["status"] == "completed"
        old_path = state / "artifacts" / run_id / "exports" / ("bundle-" + "a" * 64) / "Run_Bundle.json"
        assert len(str(old_path)) > 260
        response = client.get("/api/v1/runs/" + run_id + "/bundle", headers=headers)
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            bundle_file = next(f for f in manifest["files"] if f["path"].endswith("/Run_Bundle.json"))
            assert len(str(state / "artifacts" / run_id / bundle_file["path"])) < 260
            captured = archive.read(bundle_file["path"])
            assert hashlib.sha256(captured).hexdigest() == bundle_file["artifact_ref"]["sha256"]
            assert len(json.loads(captured)["id"].removeprefix("bundle-")) == 64


def test_client_normalizes_non_json_http_errors_without_body_disclosure(tmp_path):
    def handler(request):
        return httpx.Response(500, text="Internal Server Error: private server details must not be reflected")
    client = CompilerClient("http://test", "test", transport=httpx.MockTransport(handler))
    with pytest.raises(ClientError) as readiness_error:
        client.readiness()
    assert readiness_error.value.status_code == 500
    assert readiness_error.value.detail["category"] == "server_response_invalid"
    with pytest.raises(ClientError) as export_error:
        client.export("known-run", tmp_path / "missing.zip")
    assert export_error.value.status_code == 500
    assert export_error.value.detail["category"] == "export_unavailable"
    assert export_error.value.detail["run_id"] == "known-run"
    assert "private server details" not in json.dumps(export_error.value.detail)
    assert not (tmp_path / "missing.zip").exists()
    client.close()


def test_approved_evaluation_profile_labels_every_external_boundary(tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    config = Config(tmp_path / "state", input_root, auth_token="evaluation-test-token",
                    model_mode="codex", profile_id="compiler-evaluation")
    store = Store(config.state_dir)
    # Trusted constructor fixture only; no client can select or inject this bridge.
    bridge = SmokeBridge()
    assert not getattr(bridge, "invalid_for_product", False)
    runtime = Runtime(config, store, bridge=bridge)
    headers = {"Authorization": "Bearer evaluation-test-token"}
    with TestClient(create_app(config, store, runtime)) as client:
        ready = client.get("/api/v1/readiness", headers=headers).json()
        assert ready["ext"]["m0.intent"]["invalid_for_product"]
        body = payload(client, headers, "evaluation-profile")
        body["profile_id"] = "compiler-evaluation"
        submitted = client.post("/api/v1/runs", json=body, headers=headers)
        assert submitted.status_code == 202
        run_id = submitted.json()["run_id"]
        final = finish(client, headers, run_id)
        assert final["status"] == "completed", final
        assert final["ext"]["m0.intent"]["invalid_for_product"]
        for route in ("manifest", "result"):
            response = client.get("/api/v1/runs/" + run_id + "/" + route, headers=headers)
            assert response.status_code == 200
            assert response.json()["ext"]["m0.intent"]["invalid_for_product"]
        assert store.get_json(run_id, final["ext"]["m0.intent"]["configuration_ref"])["invalid_for_product"]
