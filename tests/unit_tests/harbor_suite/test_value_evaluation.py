import json

import pytest

from benchmarks.harbor_suite.value_evaluation import build_manifest


def inventory(tmp_path, *, qualification="not_run", screening_eligible=True):
    value = {"schema": "ai4r-workflow-runtime:1", "ready": True,
        "qualification_status": qualification,
        "capsules": [
            {"stage": "screening", "name": "research.screening", "version": "m1-4",
             "standing": "active", "eligible": screening_eligible},
            {"stage": "verifier", "name": "research.verifier", "version": "m1-2",
             "standing": "active", "eligible": True},
            {"stage": "search", "name": "research.search", "version": "m1-6",
             "standing": "active", "eligible": True},
            {"stage": "paper_summary", "name": "research.paper_summary", "version": "paper-m1-5",
             "standing": "active", "eligible": True},
        ]}
    path = tmp_path / "runtime-inventory.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_manifest_pins_inventory_and_uses_only_existing_pilot_commands(tmp_path):
    manifest = build_manifest(inventory_path=inventory(tmp_path),
        candidate="research.screening@m1-4", verifier="research.verifier@m1-2",
        profile_id="review-pilot", campaign_id="review-campaign")

    assert manifest["model_calls"] == 0
    assert manifest["status"] == "prep_only_source_run_and_E2_E3_execution_not_performed"
    assert manifest["source_inventory"]["qualification_status"] == "not_run"
    assert manifest["source_inventory"]["ready_is_not_qualification"] is True
    assert manifest["pins"]["candidate"]["name"] == "research.screening"
    assert manifest["scope"]["source_contract_ref"] is None
    assert manifest["scope"]["paper_summary_source_supported"] is False

    commands = manifest["commands"]
    assert commands["phase1_profile"][commands["phase1_profile"].index("profile"):] == [
        "profile", "--profile-id", "review-pilot", "--candidate", "research.screening@m1-4",
        "--verifier", "research.verifier@m1-2", "--output-dir",
        "/var/lib/ai4r/operator/value-evaluation/review-pilot-phase1"]
    assert commands["inspect_real_sources"][-2:] == ["--profile-dir",
        "/var/lib/ai4r/operator/value-evaluation/review-pilot-phase1"]
    assert "<exact-successful-observation-record-id>" in commands["phase2_scope_template"]
    assert "--model-calls" not in commands["phase2_scope_template"]


def test_manifest_refuses_paper_summary_even_when_inventory_says_active(tmp_path):
    with pytest.raises(ValueError, match="disables their integrated workflow"):
        build_manifest(inventory_path=inventory(tmp_path),
            candidate="research.paper_summary@paper-m1-5", verifier="research.verifier@m1-2",
            profile_id="review-pilot", campaign_id="review-campaign")


def test_manifest_refuses_inventory_not_qualifying_candidate(tmp_path):
    with pytest.raises(ValueError, match="not currently active and eligible"):
        build_manifest(inventory_path=inventory(tmp_path, screening_eligible=False),
            candidate="research.screening@m1-4", verifier="research.verifier@m1-2",
            profile_id="review-pilot", campaign_id="review-campaign")


def test_manifest_requires_research_verifier_identity(tmp_path):
    path = inventory(tmp_path)
    with pytest.raises(ValueError, match="independent verifier must be research.verifier"):
        build_manifest(inventory_path=path, candidate="research.screening@m1-4",
            verifier="research.search@m1-6", profile_id="review-pilot",
            campaign_id="review-campaign")


def test_manifest_keeps_pilot_outputs_inside_app_operator_root(tmp_path):
    with pytest.raises(ValueError, match="state_root/operator"):
        build_manifest(inventory_path=inventory(tmp_path),
            candidate="research.screening@m1-4", verifier="research.verifier@m1-2",
            profile_id="review-pilot", campaign_id="review-campaign",
            operator_root="/tmp/evaluation-pilot")
