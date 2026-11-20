"""Owned HTTP/SSE boundaries with actual processes; no product model trace is mocked.

The admitted plans and handler below are explicitly isolated test fixtures. They
verify transport and execution custody, not an LLM's composition decisions.
"""
from __future__ import annotations

import hashlib
import asyncio
import json
from pathlib import Path
import sys
import threading
import time
import uuid

from fastapi import FastAPI
import httpx
import pytest

from jiuwenswarm.software_factory import library_api
from jiuwenswarm.software_factory.workflow_library import write_json


PREFIX = "/api/v1/factory/library"


class ASGIClient:
    """Use the actual ASGI app without Starlette's background thread portal."""
    def __init__(self, app):
        self.app = app

    def request(self, method, url, **kwargs):
        async def invoke():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                        base_url="http://testserver") as client:
                return await client.request(method, url, **kwargs)
        return asyncio.run(invoke())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


@pytest.fixture
def boundary(tmp_path, monkeypatch):
    service = library_api.LibraryService(tmp_path / "factory")
    monkeypatch.setattr(library_api, "LibraryService", lambda root: service)

    async def owner(request, action="status"):
        return request.headers.get("x-test-owner", "alice")

    app = FastAPI()
    app.include_router(library_api.create_library_router(service.root, owner), prefix="/api/v1/factory")
    yield ASGIClient(app), service
    service.pool.shutdown(wait=True)


def completed(client, path):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        response = client.get(path)
        assert response.status_code == 200, response.text
        value = response.json()
        if value["status"] in {"completed", "verified", "failed", "blocked"}:
            return value
        time.sleep(0.01)
    pytest.fail("Actual local test operation did not terminate")


def test_build_history_stream_and_product_are_owned(boundary, monkeypatch):
    from jiuwenswarm.software_factory import functional_live, guided_replay

    client, service = boundary
    release = threading.Event()
    task = {"description": "Isolated live build transport fixture",
            "required_outputs": ["strata.source"], "inputs": {}}

    def isolated_run(workspace, supplied, *, run_id, emit, source_root):
        assert supplied == task
        assert source_root == service.root / 'build-sources'
        emit("planner.test_boundary", {"run_id": run_id})
        assert release.wait(timeout=5)
        write_json(workspace / "guided-replay.json", {
            "schema": guided_replay.SCHEMA, "provenance": {"runId": run_id},
        })
        return {"status": "verified"}

    monkeypatch.setattr(functional_live, "run_live_workflow", isolated_run)
    assert client.post(PREFIX + "/build", json={"task": {}}).status_code == 422
    assert client.post(PREFIX + "/build", json={"task": task, "command": "arbitrary"}).status_code == 422
    assert client.get(PREFIX + "/builds").json() == {"jobs": []}

    response = client.post(PREFIX + "/build", json={"task": task})
    assert response.status_code == 202
    started = response.json()
    assert started["kind"] == "builds"
    job_id = started["id"]
    path = PREFIX + "/builds/" + job_id
    try:
        assert client.get(path + "/product").status_code == 409
        other = {"x-test-owner": "bob"}
        for suffix in ("", "/product", "/stream"):
            assert client.get(path + suffix, headers=other).status_code == 404
        assert client.get(PREFIX + "/builds", headers=other).json() == {"jobs": []}
        assert client.get(path + "/stream?after=-1").status_code == 422
    finally:
        release.set()

    job = completed(client, path)
    assert job["status"] == "verified"
    assert job["product_ready"] is True
    assert client.get(PREFIX + "/builds").json()["jobs"][0]["id"] == job_id
    response = client.get(path + "/stream?after=1")
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert frames == job["events"][1:]
    assert [event["type"] for event in frames] == ["planner.test_boundary", "job.finished"]

    output = service.directory("builds", job_id) / "guided-replay.json"
    response = client.get(path + "/product")
    assert response.status_code == 200
    assert response.content == output.read_bytes()
    assert response.headers["x-content-sha256"] == hashlib.sha256(response.content).hexdigest()
    output.write_text("{}")
    assert client.get(path + "/product").status_code == 409


def test_library_policy_and_invalid_requests_have_http_errors(boundary):
    client, service = boundary
    response = client.get(PREFIX)
    assert response.status_code == 200
    assert response.json()["workflows"] == []
    policy = client.get(PREFIX + "/policy").json()
    assert hashlib.sha256(policy["content"].encode()).hexdigest() == policy["sha256"]
    for body in [{"repository_url": "https://example.com/arbitrary"},
                 {"repository_url": "https://github.com/niko1221/strata", "command": "arbitrary"}]:
        assert client.post(PREFIX + "/import", json=body).status_code == 422
    assert client.post(PREFIX + "/execute", json={"plan_id": "../outside"}).status_code == 404
    assert client.get(PREFIX + "/plans/" + "a" * 32).status_code == 404
    assert client.get(PREFIX + "/definitions/" + "a" * 32).status_code == 404
    assert not list((service.root / "projects").glob("*"))


def test_empty_library_planner_blocks_and_sse_retains_real_error(boundary):
    client, _ = boundary
    response = client.post(PREFIX + "/plan", json={"task": {
        "description": "Exercise empty-library rejection", "required_outputs": ["test.file"]}})
    assert response.status_code == 202
    identity = response.json()["id"]
    path = PREFIX + "/plans/" + identity
    result = completed(client, path)
    assert result["status"] == "blocked"
    assert result["error"]["code"] == "library_empty"
    assert client.post(PREFIX + "/execute", json={"plan_id": identity}).status_code == 409
    assert client.get(path, headers={"x-test-owner": "bob"}).status_code == 404
    assert client.get(path + "/events", headers={"x-test-owner": "bob"}).status_code == 404
    assert client.get(path + "/events?after=-1").status_code == 422
    response = client.get(path + "/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: library" in response.text
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert frames == result["events"]
    assert [event["type"] for event in frames] == ["job.started", "job.blocked"]
    assert "library_empty" in frames[-1]["payload"]["error"]["code"]
    assert client.get(path + "/events?after=" + str(frames[-1]["sequence"])).text == ""


def _isolated_execution(boundary, monkeypatch, *, exit_code=0):
    """Run the real executor/process path, replacing only the test part handler."""
    client, service = boundary
    from jiuwenswarm.software_factory import workflow_runtime

    definition = service.library.register({
        "id": "http_boundary_fixture", "name": "HTTP boundary test fixture",
        "source": {"repository": "test-only", "revision": "test-only", "checkout": str(service.root)},
        "subworkflows": [{"id": "produce", "name": "Execute isolated process",
            "inputs": {}, "outputs": {"source": {"semantic_type": "test.source"}},
            "implementation": {"type": "python",
                               "entrypoint": "jiuwenswarm.software_factory.library_operations:report"}}]})
    graph = {"schema": "factory.task-graph.v1", "nodes": [{"id": "process",
        "workflow": {"id": definition["id"], "version": definition["version"]},
        "subworkflow": "produce", "bindings": {}}],
        "inputs": {}, "outputs": {"source": {"node": "process", "port": "source"}}}

    def real_child(context, inputs, parameters):
        context.run_command([sys.executable, "-c",
            "from pathlib import Path;import sys;"
            "print('actual HTTP boundary child stdout',flush=True);"
            "print('actual HTTP boundary child stderr',file=sys.stderr,flush=True);"
            "Path('boundary-source.txt').write_text('produced by the actual child process\\n');"
            "sys.exit(int(sys.argv[1]))", str(exit_code)])
        return {"source": context.workspace / "boundary-source.txt"}

    real_executor = workflow_runtime.WorkflowExecutor

    class IsolatedTestExecutor(real_executor):
        def __init__(self, library, root):
            super().__init__(library, root, handlers={
                "jiuwenswarm.software_factory.library_operations:report": real_child})

    monkeypatch.setattr(workflow_runtime, "WorkflowExecutor", IsolatedTestExecutor)
    plan_id = uuid.uuid4().hex
    plan_directory = service.directory("plans", plan_id)
    plan_directory.mkdir(parents=True)
    write_json(plan_directory / "job.json", {"id": plan_id, "owner_id": "alice",
        "status": "completed", "graph": graph, "test_fixture": True, "kind": "plans",
        "unmet_requirements": [{"requirement": "native_model_inference", "status": "unverified"}]})
    service.emit('plans', plan_id, 'job.finished', {'id': plan_id, 'status': 'completed', 'test_fixture': True})
    assert client.post(PREFIX + "/execute", json={"plan_id": plan_id},
                       headers={"x-test-owner": "bob"}).status_code == 404
    response = client.post(PREFIX + "/execute", json={"plan_id": plan_id})
    assert response.status_code == 202
    job_id = response.json()["id"]
    result = completed(client, PREFIX + "/executions/" + job_id)
    return client, service, result


def test_owned_job_directory_executes_real_child_and_artifacts(boundary, monkeypatch):
    client, service, result = _isolated_execution(boundary, monkeypatch)
    assert result["status"] == "verified", result
    assert result["acceptance_status"] == "incomplete"
    identity = result["id"]
    directory = service.directory("executions", identity)
    assert (directory / "job.json").is_file()
    assert (directory / "runtime" / identity / "run.json").is_file()
    assert result["unmet_requirements"][0]["status"] == "unverified"
    command = result["nodes"][0]["attempts"][0]["commands"][0]
    assert command["exit_code"] == 0
    assert command["pid"] > 0
    path = PREFIX + "/executions/" + identity
    response = client.get(path + "/events")
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert events == result["events"]
    assert "actual HTTP boundary child stdout" in response.text
    assert "actual HTTP boundary child stderr" in response.text
    assert {"command.started", "command.finished", "node.verified", "run.verified"}.issubset(
        {event["type"] for event in events})
    source = result["outputs"]["source"]
    url = PREFIX + f"/artifacts/{identity}/{source['id']}"
    download = client.get(url)
    assert download.status_code == 200
    assert download.content == Path(source["path"]).read_bytes()
    assert download.headers["x-content-sha256"] == source["sha256"]
    assert client.get(url, headers={"x-test-owner": "bob"}).status_code == 404
    assert client.get(PREFIX + f"/artifacts/{identity}/unpublished").status_code == 404
    Path(source["path"]).write_text("changed after publication")
    assert client.get(url).status_code == 409


def test_real_failed_child_keeps_downloadable_stdout_and_blocks_product(boundary, monkeypatch):
    client, _, result = _isolated_execution(boundary, monkeypatch, exit_code=7)
    assert result["status"] == "failed"
    assert result["nodes"][0]["error"]["code"] == "command_failed"
    assert result["outputs"] == {}
    assert not any(value["kind"] == "test.source" for value in result["artifacts"])
    logs = [value for value in result["artifacts"] if "stdout" in value["id"] or "stderr" in value["id"]]
    assert len(logs) == 2
    for value in logs:
        response = client.get(PREFIX + f"/artifacts/{result['id']}/{value['id']}")
        assert response.status_code == 200
        assert "actual HTTP boundary child" in response.text
    events = client.get(PREFIX + f"/executions/{result['id']}/events").text
    assert "node.failed" in events
    assert '"exit_code": 7' in events


def test_source_browser_rejects_non_library_paths(boundary):
    client, service = boundary
    source = service.root / "upstream"
    source.mkdir()
    (source / "source.cpp").write_text("int source() { return 1; }\n")
    definition = service.library.register({
        "id": "source_fixture", "name": "Source browser fixture",
        "source": {"repository": "test-only", "checkout": str(source)},
        "subworkflows": [{"id": "report", "name": "Report",
            "inputs": {}, "outputs": {"report": {"semantic_type": "test.report"}},
            "implementation": {"type": "python",
                "entrypoint": "jiuwenswarm.software_factory.library_operations:report"}}]})
    query = {"workflow_id": definition["id"], "version": definition["version"], "path": "source.cpp"}
    response = client.get(PREFIX + "/source", params=query)
    assert response.status_code == 200
    assert response.json()["content"] == (source / "source.cpp").read_text()
    for path in ["../index.json", "/etc/passwd", ".git/config"]:
        response = client.get(PREFIX + "/source", params={**query, "path": path})
        assert response.status_code == 422


def test_only_published_owned_project_members_can_be_opened(boundary):
    """Filesystem/API custody fixture, not evidence of code generation."""
    client,service=boundary
    identity=uuid.uuid4().hex
    directory=service.directory('executions',identity)
    project=directory/'node'/'project'
    member=project/'src'/'ascend'/'router.cpp'
    member.parent.mkdir(parents=True)
    member.write_text('int custody_test() { return 7; }\n')
    expected=hashlib.sha256(member.read_bytes()).hexdigest()
    manifest=directory/'project.json'
    write_json(manifest,{'schema':'factory.source-project.v1','source_dir':str(project),
                         'files':{'src/ascend/router.cpp':expected}})
    artifact={'id':'project-custody-test','kind':'source.project','path':str(manifest),
              'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}
    write_json(directory/'job.json',{'id':identity,'status':'verified','owner_id':'alice',
                                    'test_fixture':True,'artifacts':[artifact]})
    url=PREFIX+f'/artifacts/{identity}/{artifact["id"]}/file'
    response=client.get(url,params={'path':'src/ascend/router.cpp'})
    assert response.status_code==200
    assert response.content==member.read_bytes()
    assert response.headers['x-content-sha256']==expected
    assert client.get(url,params={'path':'../../job.json'}).status_code==404
    assert client.get(url,params={'path':'src/ascend/router.cpp'},headers={'x-test-owner':'bob'}).status_code==404
    member.write_text('changed after publication\n')
    assert client.get(url,params={'path':'src/ascend/router.cpp'}).status_code==409


def test_terminal_snapshot_is_not_finished_until_final_event_is_persisted(boundary):
    client,service=boundary
    identity=uuid.uuid4().hex
    directory=service.directory('plans',identity)
    write_json(directory/'job.json',{'id':identity,'owner_id':'alice','status':'completed'})
    before=client.get(PREFIX+'/plans/'+identity).json()
    assert before['status']=='running'
    assert before['runtime_status']=='completed'
    service.emit('plans',identity,'job.finished',{'status':'completed','test_fixture':True})
    after=client.get(PREFIX+'/plans/'+identity).json()
    assert after['status']=='completed'
    frames=client.get(PREFIX+'/plans/'+identity+'/events').text
    assert 'job.finished' in frames
