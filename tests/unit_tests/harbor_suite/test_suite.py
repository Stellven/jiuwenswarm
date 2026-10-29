"""Custody and scheduling checks; these tests never represent product trials."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.harbor_suite.adapter import dispatch, receipt, select_task, validate_bundle
from benchmarks.harbor_suite.contracts import EXPECTED, canonical, load_cases, read_json, resolve_cases_root, task_key, validate_case
from benchmarks.harbor_suite.evidence import Unavailable, normalize_evaluation, project_declared_outputs
from benchmarks.harbor_suite.grade import assess
from benchmarks.harbor_suite.prepare import prepare
from benchmarks.harbor_suite.report import summarize

IMAGE = "python:3.12-slim-bookworm@sha256:"+"1"*64
pytestmark = pytest.mark.usefixtures("benchmark_case_assets")


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    path = tmp_path_factory.mktemp("suite") / "bundle"
    prepare(path, python_image=IMAGE)
    return path


def test_exact_ten_cases_and_required_modules():
    cases = load_cases()
    assert {c["id"] for c in cases} == set(EXPECTED)
    assert {k: sum(c["module"] == k for c in cases) for k in ("cc", "mr", "rsi", "verifier", "pipeline")} == {
        "cc": 2, "mr": 2, "rsi": 2, "verifier": 2, "pipeline": 2}
    assert all(len(c["variants"]) >= 3 for c in cases)
    assert all(c["classification"] == "m2_m3_progress" for c in cases if c["module"] in {"mr", "rsi"})
    assert set.union(*(set(c["domains"]) for c in cases if c["module"] == "mr")) == {"c0"+str(i) for i in range(1,9)}


def test_task_keys_fit_existing_runner_without_collisions():
    keys = [task_key(c["id"], v["id"], r) for c in load_cases() for v in c["variants"] for r in range(1,4)]
    assert len(keys) == len(set(keys)) and all(len(k) <= 48 for k in keys)


def test_metadata_rejects_private_upload_path_and_held_out_claim():
    case = copy.deepcopy(load_cases()[0])
    case["variants"][0]["inputs"][0]["path"] = "referee/criteria.json"
    with pytest.raises(ValueError): validate_case(case)
    case = copy.deepcopy(load_cases()[0]); case["variants"][0]["split"] = "held_out"
    with pytest.raises(ValueError): validate_case(case)


def test_verifier_definitions_cover_all_ten_phase_one_outcomes():
    root = resolve_cases_root()
    mechanical = read_json(root/"vf01-mechanical/referee/criteria.json")
    semantic = read_json(root/"vf02-semantic/referee/criteria.json")
    covered = {x for v in mechanical["variants"].values() for x in v["acceptance_cases"]}
    covered |= {int(v["prd_4_2_9"]) for v in semantic["variants"].values() if v.get("prd_4_2_9")}
    assert covered == set(range(1,11))


def test_frozen_agent_context_contains_no_referee_material(bundle):
    manifest = read_json(bundle/"bundle-manifest.json")
    for task in read_json(bundle/"task-index.json")["tasks"]:
        env = bundle/"tasks"/task["task_key"]/"environment"
        assert {p.name for p in env.iterdir()} == {"Dockerfile", ".dockerignore"}
        public = [n for n in task["public_inputs"]]
        assert all("/public/" in n and "referee" not in n for n in public)
        tests = env.parent/"tests"
        assert (tests/"oracle.py").is_file() and (tests/"criteria.json").is_file()
    assert manifest["protected_material_present"]
    assert all(r["audience"] == "referee" for r in manifest["files"] if "/tests/" in r["path"])


def test_job_disables_retries_and_parallel_app_requests(bundle):
    job = read_json(bundle/"job.json")
    assert job["n_attempts"] == job["n_concurrent_trials"] == 1
    assert job["retry"]["max_retries"] == 0
    validate_bundle(bundle)


def test_changed_frozen_input_is_rejected_before_dispatch(bundle, tmp_path):
    # Separate tiny frozen context avoids mutating the shared prepared bundle.
    path = tmp_path/"frozen"; path.mkdir()
    (path/"task-index.json").write_text("changed")
    (path/"bundle-manifest.json").write_text(json.dumps({"schema":"ai4r-harbor-suite-bundle:1", "files":[
        {"path":"task-index.json","sha256":"0"*64,"size":7}]}))
    with pytest.raises(ValueError, match="changed"): validate_bundle(path)


def test_marker_cannot_select_foreign_or_multiple_tasks(bundle):
    index = read_json(bundle/"task-index.json"); key = index["tasks"][0]["task_key"]
    assert select_task("AI4R_HARBOR_TASK_KEY: "+key, index)["task_key"] == key
    for text in ["AI4R_HARBOR_TASK_KEY: foreign", "AI4R_HARBOR_TASK_KEY: "+key+"\nAI4R_HARBOR_TASK_KEY: "+key]:
        with pytest.raises(ValueError): select_task(text, index)


def test_absent_module_bindings_never_dispatch_or_call_oracle(bundle, tmp_path):
    task = read_json(bundle/"task-index.json")["tasks"][0]
    config = {"mode":"live", "output_root":tmp_path}
    async def forbidden(*args): raise AssertionError("no authority to launch")
    folder, row, cancelled = asyncio.run(dispatch(config, task, "stable-trial", runner=forbidden))
    assert row["status"] == "blocked" and row["launched"] is False and cancelled is None
    def oracle(*args): raise AssertionError("blocked is not a quality sample")
    result = assess(folder, task, {}, oracle)
    assert result["status"] == "unavailable" and result["case_correctness"] is None
    assert result["reward"] == dict(evidence_integrity=0,execution_available=0,case_correctness=0,baseline_success=0)
    assert asyncio.run(dispatch(config, task, "stable-trial", runner=forbidden))[0] == folder


def test_forged_task_scope_does_not_become_blocked_success(bundle, tmp_path):
    task = read_json(bundle/"task-index.json")["tasks"][0]
    row = receipt(task, status="blocked", blockers=["no binding"]); row["repeat"] += 1
    (tmp_path/"suite-receipt.json").write_text(json.dumps(row))
    result = assess(tmp_path, task, {}, lambda *args: None)
    assert result["status"] == "invalid_evidence" and not result["evidence_integrity"]


def test_ordinary_run_cannot_be_relabeled_isolated_evaluation(tmp_path):
    archive = tmp_path/"arbitrary.zip"; archive.write_bytes(b"not an export")
    with pytest.raises(ValueError):
        normalize_evaluation(archive, task={"entrypoint":"run"},request_id="x",campaign_id="x",expected_request={})


def test_isolated_decoder_retains_original_non_json_text(tmp_path, monkeypatch):
    # Reader is stubbed only to isolate the text projection; no live/integrity
    # claim is derived from this synthetic unit fixture.
    from types import SimpleNamespace
    from jiuwenswarm.research_sidecar.evaluation_records import EvaluationRecords
    ref = {"id":"unit-text","sha256":hashlib.sha256(b"# Research report\n").hexdigest()}
    fake = SimpleNamespace(request={"entry_point":"E2"},terminal={"state":"completed"},
        by_kind={("output",("unit-text",ref["sha256"])):{"artifact_ref":ref,"path":"outputs/report.md"}},
        require_complete=lambda:None,bytes_ref=lambda _:b"# Research report\n")
    monkeypatch.setattr(EvaluationRecords,"from_archive",lambda *args,**kwargs:fake)
    archive = tmp_path/"unit.zip"; archive.write_bytes(b"unit")
    value = normalize_evaluation(archive,task={"entrypoint":"node_replay","variant_id":"unit"},
        request_id="unit",campaign_id="unit",expected_request={})
    assert value["artifacts"]["outputs/report.md"] == "# Research report\n"
    assert value["records"] == []


def output_projection_fixture():
    from types import SimpleNamespace
    raw = '{"declared":true,"kind":"self-selected-wrong-type"}'
    output = {"id":"unit-output","sha256":hashlib.sha256(raw.encode()).hexdigest()}
    contract_ref = {"id":"unit-contract","sha256":"1"*64}
    scope = dict(run_id="unit-run",node_id="unit-node",subnode_id="unit-work",attempt_id="unit-attempt")
    contract = {"kind":"subnode-execution-contract","ref":contract_ref,
                "record":{**scope,"outputs":[{"contract_id":"declared:v1"}]}}
    observation = {"kind":"invocation-observation","ref":{"id":"unit-observation","sha256":"2"*64},
                   "record":{**scope,"contract_ref":contract_ref,"output_refs":[output]}}
    def validate(kind, value):
        if not value.get("declared"): raise ValueError("not declared schema")
    schemas = {"declared:v1":{"ref":"same"},"declared":{"ref":"same"},"other":{"ref":"other"}}
    return {"records":[contract,observation]}, {(output["id"],output["sha256"]):raw}, SimpleNamespace(schemas=schemas,validate=validate)


def test_output_type_comes_from_actual_declared_schema_not_payload_kind():
    normalized, texts, contracts = output_projection_fixture()
    project_declared_outputs(normalized,texts,contracts)
    assert normalized["records"][-1]["kind"] == "declared"


def test_unbound_or_ambiguous_output_is_not_promoted():
    normalized,texts,contracts = output_projection_fixture()
    normalized["records"][0]["record"]["outputs"].append({"contract_id":"other"})
    project_declared_outputs(normalized,texts,contracts)
    assert len(normalized["records"]) == 2
    normalized,texts,contracts = output_projection_fixture()
    normalized["records"].pop(0)
    project_declared_outputs(normalized,texts,contracts)
    assert len(normalized["records"]) == 1


def test_output_projection_rejects_foreign_scope_and_changed_bytes():
    normalized,texts,contracts = output_projection_fixture()
    normalized["records"][1]["record"]["node_id"] = "foreign"
    with pytest.raises(ValueError,match="scope mismatch"): project_declared_outputs(normalized,texts,contracts)
    normalized,texts,contracts = output_projection_fixture()
    for key in texts: texts[key] += " "
    with pytest.raises(ValueError,match="bytes changed"): project_declared_outputs(normalized,texts,contracts)


def test_report_retains_missing_and_unavailable_in_denominator(bundle):
    index = read_json(bundle/"task-index.json"); task = index["tasks"][0]
    result = {**{k:task[k] for k in ("case_id","variant_id","repeat","expected_model")},
              "task_sha256":hashlib.sha256(canonical(task)).hexdigest(),
              "status":"unavailable","execution_available":False,"case_correctness":None}
    report = summarize(index,[result])
    assert report["scheduled"] == len(index["tasks"]) and report["missing"] == len(index["tasks"])-1
    assert report["cases"][0]["correctness_given_scored"] is None
    with pytest.raises(ValueError): summarize(index,[result,result])
    result["task_sha256"] = "0"*64
    with pytest.raises(ValueError, match="different frozen task"): summarize(index,[result])


def test_known_failure_cannot_hide_behind_missing_optional_evidence(bundle, monkeypatch):
    from benchmarks.harbor_suite import grade
    task = next(t for t in read_json(bundle/"task-index.json")["tasks"] if t["entrypoint"] == "run")
    monkeypatch.setattr(grade,"validate_receipt",lambda *args: {})
    monkeypatch.setattr(grade,"normalize_run",lambda *args: {"records":[]})
    def oracle(*args):
        return {"checks":[dict(id="false-advance",status="fail",reason="Actual false advancement",evidence_refs=[]),
                          dict(id="optional",status="unavailable",reason="Not captured",evidence_refs=[])],
                "metrics":{},"critical_violations":["false_advance"]}
    result = assess(Path("unused"),task,{},oracle)
    assert result["status"] == "failed" and result["case_correctness"] is False


def test_existing_bundle_is_immutable(bundle):
    with pytest.raises(ValueError): prepare(bundle,python_image=IMAGE)
