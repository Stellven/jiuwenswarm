"""Real file/CLI controls for frozen definitions, without product execution.

The four-module metadata below is deliberately unqualified developer test data.
Its referee hashes are not protected ground truth or runtime authorizations.
"""
import copy
import hashlib
import json
import os

import pytest

from jiuwenswarm.research_sidecar.campaign import freeze_campaign
from jiuwenswarm.research_sidecar.cli import _campaign, runner_main
from jiuwenswarm.research_sidecar.evidence import canonical


MODULES = ("capsule", "verifier", "routing", "rsi")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bind_visible(case):
    case["referee_ref"]["visible_sha256"] = digest(
        canonical({k: v for k, v in case.items() if k != "referee_ref"})
    )


def pin_cases(campaign, cases):
    campaign["cases"] = [
        {"case_id": c["case_id"], "case_version": c["case_version"], "case_sha256": digest(canonical(c))}
        for c in cases
    ]
    campaign["pins"]["oracle_versions"] = {c["case_id"]: c["oracle_version"] for c in cases}


@pytest.fixture
def definitions(tmp_path):
    """Complete source-shaped definitions and actual visible bytes, no labels."""
    bench = tmp_path / "bench"
    cases = []
    for module, scenario, requirement in zip(MODULES, ("s01", "s05", "s07", "s08"), ("cc01", "vf01", "rt03", "rs01")):
        case_id = "loader_" + module
        path = "cases/" + case_id + "/1/fixtures/input.json"
        raw = canonical({"topic": "Research workflow contract validation", "module": module})
        file = bench / path
        file.parent.mkdir(parents=True)
        file.write_bytes(raw)
        case = dict(
            schema="benchmark-case:1", case_id=case_id, case_version=1, supersedes=None,
            scenario_id=scenario, variant_id="baseline", topic="Research workflow contract validation",
            research_question="Are declared research inputs preserved byte for byte before dispatch?",
            domain_codes=["c01"], module_requirements=[requirement], delivery_profile="extended",
            milestone="m1", classification="extended_performance", split="development",
            expected_behavior="complete", entry_mode="run",
            task_prompt="Use the declared visible research input through the supported interface.",
            permitted_resources=[], input_fixtures=[dict(fixture_id="visible_input", path=path,
                sha256=digest(raw), provenance="Independently authored developer loader control", role="input")],
            seed=0, budgets=dict(wall_time_s=30, invocations=1, compute=dict(cpu_s=1, gpu_s=0),
                memory_physical_mb=64, memory_committed_mb=64, storage_mb=16, concurrency=1,
                tools=[], effects=[]), gpu_required=False, host_profile="other_declared",
            hardware_requirements=dict(min_physical_mb=64, min_commit_mb=64, arch="x86_64", accelerator="none"),
            human_intervention="none", repair_policy="none", fault_plan_ref=None, checkpoints=[],
            node_bundle_ref=None, capsule_binding=None, model_configuration_ref="fixed",
            repeat_policy=dict(repeats=1, stochastic=False), required_evidence=["invocation-observation"],
            oracle_version="oracle:1", referee_ref=dict(label_id="controlled_" + module,
                referee_sha256="0" * 64, visible_sha256="0" * 64),
        )
        bind_visible(case)
        cases.append(case)
    campaign = dict(
        schema="benchmark-campaign:1", campaign_id="loader_control", frozen_at="2026-10-19T12:00:00Z",
        milestone="m1", purpose="pilot", suite_version="suite:m1:1", cases=[],
        configurations=[dict(config_id="fixed", kind="ai4research_fixed_dag", adapter="product_client",
            model_identifier="controlled-unqualified-model", model_route="codex-cli-default", profile_id=None,
            adapter_pin=None, notes="Developer metadata only; no model or runtime qualification")], pairs=[],
        pins=dict(benchmark_runner_version="developer-control", oracle_versions={}, app_build="unqualified-control",
            client_contract_version="client:1", capsule_catalogue={}, planner="static", router="none",
            verifier="unqualified-control", model_settings={}, runtime_config_sha256="0" * 64,
            external_snapshots=[]), repeats=1, seeds=dict(base_seed=0, per_repeat=[0, 1]),
        order=dict(randomized=False, order_seed=0), host_profile="other_declared",
        environment_profile=dict(os="controlled", background_workload="controlled", power="unknown",
            pagefile_policy="unknown", concurrency="1"), evaluation_profile_id=None, fault_plan=[],
        analysis_policy=dict(ci_methods=[], cluster_by="variant", alpha=.05, reporting_criteria_ref="developer-control"),
        judge_config_ref=None, retry_policy="none", unavailable_modules=[],
    )
    pin_cases(campaign, cases)
    registry = {c["case_id"]: module for c, module in zip(cases, MODULES)}
    return bench, bench / "campaigns" / campaign["campaign_id"], campaign, cases, registry


def freeze(definitions):
    bench, folder, campaign, cases, registry = definitions
    rows = freeze_campaign(folder, campaign, cases, registry,
        referee_pins={c["case_id"]: c["referee_ref"] for c in cases})
    return bench, folder, rows


def test_freeze_and_load_four_modules_preserves_exact_inputs_and_repeat_order(definitions):
    _, _, campaign, cases, _ = definitions
    cases[0]["repeat_policy"]["repeats"] = 2
    bind_visible(cases[0])
    pin_cases(campaign, cases)
    bench, folder, rows = freeze(definitions)
    before = {p.relative_to(bench): p.read_bytes() for p in bench.rglob("*") if p.is_file()}
    loaded_folder, loaded_campaign, loaded_cases = _campaign(bench, campaign["campaign_id"])
    assert loaded_folder == folder and loaded_campaign == campaign
    assert {c["module"] for c in loaded_cases} == set(MODULES)
    assert len(rows) == 5 and [r["repeat_index"] for r in rows[:2]] == [0, 1]
    assert len({r["run_id"] for r in rows}) == 5
    assert before == {p.relative_to(bench): p.read_bytes() for p in bench.rglob("*") if p.is_file()}


@pytest.mark.parametrize("mode", ["missing", "changed"])
def test_freeze_refuses_missing_or_changed_fixture_before_publishing(definitions, mode):
    bench, folder, _, cases, _ = definitions
    path = bench / cases[0]["input_fixtures"][0]["path"]
    if mode == "missing":
        path.unlink()
    else:
        path.write_bytes(b"changed before freeze")
    with pytest.raises((ValueError, OSError)):
        freeze(definitions)
    assert not folder.exists(), "An invalid input must not publish a partially frozen campaign."


@pytest.mark.parametrize("role", ["input", "replay_bundle", "binding", "source_snapshot", "fault_asset"])
@pytest.mark.parametrize("mode", ["missing", "changed"])
def test_load_rechecks_actual_bytes_of_every_declared_fixture_role(definitions, role, mode):
    bench, _, campaign, cases, _ = definitions
    cases[0]["input_fixtures"][0]["role"] = role
    bind_visible(cases[0])
    pin_cases(campaign, cases)
    freeze(definitions)
    path = bench / cases[0]["input_fixtures"][0]["path"]
    if mode == "missing":
        path.unlink()
    else:
        path.write_bytes(b"changed after freeze")
    with pytest.raises((ValueError, OSError)):
        _campaign(bench, campaign["campaign_id"])


def test_loader_reads_fixture_paths_from_bench_root_not_campaign_directory(definitions):
    bench, folder, campaign, cases, _ = definitions
    freeze(definitions)
    original = bench / cases[0]["input_fixtures"][0]["path"]
    decoy = folder / cases[0]["input_fixtures"][0]["path"]
    decoy.parent.mkdir(parents=True)
    decoy.write_bytes(original.read_bytes())
    original.write_bytes(b"changed original; correct decoy must not mask it")
    with pytest.raises(ValueError):
        _campaign(bench, campaign["campaign_id"])


@pytest.mark.parametrize("link", ["symlink", "hardlink", "parent_symlink"])
def test_loader_denies_linked_fixture_bytes_even_when_hash_matches(definitions, tmp_path, link):
    bench, _, campaign, cases, _ = definitions
    freeze(definitions)
    path = bench / cases[0]["input_fixtures"][0]["path"]
    outside = tmp_path / "other-visible-input.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    if link == "symlink":
        path.symlink_to(outside)
    elif link == "hardlink":
        os.link(outside, path)
    else:
        path.parent.rmdir()
        path.parent.symlink_to(outside.parent, target_is_directory=True)
        (outside.parent / path.name).write_bytes(outside.read_bytes())
    with pytest.raises((ValueError, OSError)):
        _campaign(bench, campaign["campaign_id"])


@pytest.mark.parametrize("part", ["module-map.json", "schedule.json", "case.json"])
def test_loader_rejects_changed_frozen_identity_or_schedule(definitions, part):
    bench, folder, campaign, _, _ = definitions
    freeze(definitions)
    if part == "module-map.json":
        path = folder / part
        value = json.loads(path.read_bytes())
        value["unknown_case"] = "capsule"
    elif part == "schedule.json":
        path = folder / part
        value = json.loads(path.read_bytes())
        value.reverse()
    else:
        path = next((folder / "cases").glob("*/case.json"))
        value = json.loads(path.read_bytes())
        value["task_prompt"] = "Changed after the campaign was frozen"
    path.write_bytes(canonical(value))
    with pytest.raises(ValueError):
        _campaign(bench, campaign["campaign_id"])


def test_freeze_refuses_unregistered_module_mapping_before_publication(definitions):
    _, folder, _, _, registry = definitions
    registry["unregistered_case"] = "capsule"
    with pytest.raises(ValueError):
        freeze(definitions)
    assert not folder.exists()


def test_freeze_refuses_two_versions_of_one_case_before_publication(definitions):
    _, folder, campaign, cases, _ = definitions
    second = copy.deepcopy(cases[0])
    second["case_version"] = 2
    second["supersedes"] = 1
    bind_visible(second)
    cases.append(second)
    pin_cases(campaign, cases)
    with pytest.raises(ValueError):
        freeze(definitions)
    assert not folder.exists()


def test_visible_fixture_cannot_open_the_referee_label_store(definitions):
    bench, folder, campaign, cases, _ = definitions
    # A controlled marker proves path separation; it is not an oracle label.
    private = bench / "labels" / "controlled_referee" / "referee.json"
    private.parent.mkdir(parents=True)
    private.write_bytes(b"developer marker standing in for a separately protected store")
    fixture = cases[0]["input_fixtures"][0]
    fixture["path"] = private.relative_to(bench).as_posix()
    fixture["sha256"] = digest(private.read_bytes())
    bind_visible(cases[0])
    pin_cases(campaign, cases)
    with pytest.raises(ValueError):
        freeze(definitions)
    assert not folder.exists()


def test_freeze_retains_a_controlled_variant_inside_its_existing_module(definitions):
    _, _, campaign, cases, registry = definitions
    variant = copy.deepcopy(cases[1])
    variant["case_id"] += "_alternate"
    variant["variant_id"] = "alternate"
    variant["referee_ref"]["label_id"] = "controlled_verifier_alternate"
    bind_visible(variant)
    cases.append(variant)
    registry[variant["case_id"]] = "verifier"
    pin_cases(campaign, cases)
    bench, _, rows = freeze(definitions)
    _, _, loaded_cases = _campaign(bench, campaign["campaign_id"])
    assert len(loaded_cases) == 5 and {r["module"] for r in rows} == set(MODULES)
    assert {r["variant_id"] for r in rows if r["module"] == "verifier"} == {"baseline", "alternate"}


@pytest.mark.parametrize("path", [".", "./"])
def test_fixture_directory_alias_has_a_bounded_refusal(definitions, path):
    _, folder, campaign, cases, _ = definitions
    cases[0]["input_fixtures"][0]["path"] = path
    bind_visible(cases[0])
    pin_cases(campaign, cases)
    with pytest.raises((ValueError, OSError)):
        freeze(definitions)
    assert not folder.exists()


def test_fixture_drift_blocks_real_cli_before_job_client_ledger_or_result_write(definitions, monkeypatch):
    bench, _, campaign, cases, _ = definitions
    freeze(definitions)
    (bench / cases[0]["input_fixtures"][0]["path"]).write_bytes(b"changed after freeze")
    monkeypatch.setenv("AI4R_QA_ROOT", str(bench))
    def no_client(*args, **kwargs):
        pytest.fail("Invalid fixture reached the product client constructor")
    monkeypatch.setattr("jiuwenswarm.research_sidecar.cli.ResearchClient", no_client)
    assert runner_main(["run", "--campaign", campaign["campaign_id"], "--case", "capsule"]) == 2
    assert not (bench / "results").exists()
