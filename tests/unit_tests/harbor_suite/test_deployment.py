"""Deployment transport/custody tests. Fixtures never claim live performance."""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.harbor_suite import deployment as d
from benchmarks.harbor_suite import prepare as generator
from benchmarks.harbor_suite.contracts import canonical, load_cases, pin, read_json
from benchmarks.harbor_pilot.bridge import atomic, run_trial


@pytest.fixture(scope="module")
def bundle(tmp_path_factory, benchmark_case_assets):
    root = tmp_path_factory.mktemp("deployment-bundle")
    original = generator.load_cases
    generator.load_cases = lambda _: [next(c for c in load_cases() if c["id"] == "pipeline01-experiment")]
    try:
        generator.prepare(root/"bundle",python_image="python:3.12-slim-bookworm@sha256:"+"1"*64)
    finally:
        generator.load_cases = original
    return root/"bundle"


@pytest.fixture
def profile(tmp_path):
    api = d.operator()
    p = api.host.setup({"profile":{"project":"ai4r-unit-harbor","root":str(tmp_path/"target"),
        "output":str(tmp_path/"target-results"),"platform":"linux/arm64","ttl_days":7,"docker_context":None},"seccomp":"{}"})
    p.update(app_image="sha256:"+"1"*64,runner_image="sha256:"+"2"*64,build_id="unit-build")
    value = {"schema":"ai4r-operator:1","deployment":p,"ssh":"unit-user@unit-host", "builds":{"images":{
        "ai4r":{"image_id":p["app_image"],"unpacked_bytes":10},
        "benchmark-runner":{"image_id":p["runner_image"],"unpacked_bytes":10}}}}
    path = tmp_path/"profile.json"; api.save(path,value)
    return path


@pytest.fixture
def prepared(bundle,profile,tmp_path):
    path = tmp_path/"control"
    d.prepare(profile,bundle,path,mode="live")
    return path


def transport(monkeypatch,blocked=False):
    calls = []
    class FakeTransport:
        def __init__(self,config): self.config=config
        def request(self,action,**values):
            calls.append((action,values))
            if action == "doctor": return {"prerequisite_error":"unit Docker denied"} if blocked else {"platform":"linux/arm64"}
            if action == "image-check": return {"matches":True}
            if action == "configure": return {"deployment":self.config["deployment"]}
            raise AssertionError(action)
        def transfer(self,source,**values):
            calls.append(("transfer",{**values,"source":str(source),"raw":Path(source).read_bytes()}))
            return {"verified":True}
    monkeypatch.setattr(d.operator(),"Transport",FakeTransport)
    return calls


def test_prepare_is_offline_and_private_labels_are_excluded(bundle,profile,tmp_path,monkeypatch):
    def forbidden(*args): raise AssertionError("prepare cannot contact deployment")
    monkeypatch.setattr(d.operator(),"Transport",forbidden)
    workspace = tmp_path/"offline"
    result = d.prepare(profile,bundle,workspace,mode="live")
    assert result["target_contacted"] is False
    value,_ = d.validate_workspace(workspace)
    assert all(n.startswith("public/") and "referee" not in n and "oracle" not in n for n in value["public_files"])
    assert not list((workspace/"public").rglob("criteria.json"))
    with pytest.raises(ValueError): d.prepare(profile,bundle,workspace)


def test_stage_reuses_operator_and_keeps_exact_per_trial_case_bytes(prepared,monkeypatch,bundle):
    calls = transport(monkeypatch)
    receipt = d.stage(prepared)
    _,config,_ = d.staged(prepared)
    assert config["deployment"]["input_stage"] == receipt["input_stage"]
    sent = [v for action,v in calls if action == "transfer"]
    cases = [v for v in sent if v["kind"] == "cases" and v["path" if "path" in v else "name"].endswith(".json")]
    assert len(cases) == 4  # public aggregate plus three exact trial files.
    for row in cases:
        name = Path(row["source"]).name
        if name != "selected.json": assert row["raw"] == (bundle/"cases"/name).read_bytes()
    assert not any(b'"variants"' in row["raw"] for row in sent)


def test_docker_denial_prevents_staging_or_profile_mutation(prepared,profile,monkeypatch):
    before=profile.read_bytes(); calls=transport(monkeypatch,blocked=True)
    with pytest.raises(ValueError,match="Docker prerequisites"): d.stage(prepared)
    assert profile.read_bytes() == before and [a for a,_ in calls] == ["doctor"]
    assert not (prepared/"stage-receipt.json").exists()


def test_changed_target_or_public_bytes_cannot_run(prepared,profile):
    original = profile.read_bytes(); value=read_json(profile)
    value["ssh"]="different-host"; profile.write_bytes(canonical(value))
    with pytest.raises(ValueError,match="target/images/build changed"): d.validate_workspace(prepared)
    profile.write_bytes(original)
    first=next((prepared/"public/inputs").rglob("*.json")); first.write_bytes(first.read_bytes()+b" ")
    with pytest.raises(ValueError,match="workspace changed"): d.validate_workspace(prepared)


def test_changed_local_model_policy_requires_new_harbor_workspace(prepared,profile):
    value=read_json(profile)
    value['deployment']['local_model']={'schema':'ai4r-local-model-deployment:1','catalog_sha256':'a'*64}
    profile.write_bytes(canonical(value))
    with pytest.raises(ValueError,match='target/images/build changed'):d.validate_workspace(prepared)


def test_credentials_never_become_operator_bridge_arguments(prepared,monkeypatch):
    transport(monkeypatch); d.stage(prepared)
    config=d.OperatorConfig.load(prepared/"deployment.json")
    assert config.token_file is None
    captured=[]
    executor=d.OperatorExecutor(config)
    async def request(action,**values):
        captured.append((action,values))
        return {"returncode":3,"stdout":"unit pending"}
    monkeypatch.setattr(executor,"request",request)
    args=SimpleNamespace(command="cancel",campaign_id="harbor-"+"a"*24)
    code,_=asyncio.run(executor(args))
    assert code == 3 and len(captured) == 1
    assert captured[0][1]["args"] == ["cancel","--campaign-dir","/results/harbor-"+"a"*24,"--json"]
    assert "token" not in json.dumps(captured)


def test_remote_resume_does_not_require_a_successful_initial_fetch(bundle,tmp_path):
    from benchmarks.harbor_suite.contracts import task_key
    key=read_json(bundle/"task-index.json")["tasks"][0]["task_key"]
    output=tmp_path/"output"; output.mkdir()
    config=d.OperatorConfig(tmp_path,bundle,output,"unit-build","unit-target")
    calls=[]
    async def execute(args):
        calls.append(args.command)
        raise ValueError("unit connection lost before any fetch")
    asyncio.run(run_trial(config,key,"stable-trial",execute=execute,inventory=lambda _:{}))
    asyncio.run(run_trial(config,key,"stable-trial",execute=execute,inventory=lambda _:{}))
    assert calls == ["run","resume"]
    assert (output/".harbor-pilot-active.json").exists()


def test_backend_target_change_cannot_reconcile_against_another_host(bundle,tmp_path):
    key=read_json(bundle/"task-index.json")["tasks"][0]["task_key"]
    output=tmp_path/"output";output.mkdir()
    config=d.OperatorConfig(tmp_path,bundle,output,"unit-build","unit-target")
    async def interrupted(args): raise ValueError("unit uncertain")
    asyncio.run(run_trial(config,key,"first-trial",execute=interrupted,inventory=lambda _:{}))
    config.target_identity="another-target"
    with pytest.raises(ValueError,match="different pinned target"):
        asyncio.run(run_trial(config,key,"second-trial",execute=interrupted,inventory=lambda _:{}))


def test_snapshot_changed_bytes_cannot_be_published(tmp_path):
    source=tmp_path/"snapshot";source.mkdir();file=source/"campaign.json";file.write_text("original")
    row={"path":"campaign.json",**pin(file)}
    atomic(source/".transfer-manifest.json",{"snapshot":{"id":"unit-snapshot","campaign":"evidence","files":[row]}})
    file.write_text("changed")
    with pytest.raises(ValueError,match="fetch changed"): d.OperatorExecutor.publish_snapshot(source,tmp_path/"evidence")
    assert not (tmp_path/"evidence/campaign.json").exists()


def test_preflight_cannot_stage(bundle,profile,tmp_path):
    folder=tmp_path/"preflight";d.prepare(profile,bundle,folder)
    with pytest.raises(ValueError,match="never stage"): d.stage(folder)


def test_stage_receipt_cannot_redirect_case_directory(prepared,monkeypatch):
    transport(monkeypatch);d.stage(prepared)
    path=prepared/"stage-receipt.json";value=read_json(path);value["case_directory"]="/cases/another"
    path.write_bytes(canonical(value))
    with pytest.raises(ValueError,match="identity changed"): d.staged(prepared)
