"""CLI preparation must preserve exact captured source identity."""
import json

import pytest

from jiuwenswarm.research import evaluation_pilot_cli as cli
from jiuwenswarm.research.state import json_bytes


def test_verifier_pin_must_be_explicit_when_catalog_has_multiple_versions():
    from jiuwenswarm.research.contracts import ResearchError

    rows = [
        {"cc_name": "research.verifier", "cc_version": version,
         "declaration_sha256": version + "-digest"}
        for version in ("m1-2", "m1-3")
    ]
    snapshot = {"entries": rows}
    with pytest.raises(ResearchError, match="pass --verifier"):
        cli._select_verifier_entry(snapshot)
    assert cli._select_verifier_entry(snapshot, "research.verifier@m1-3") == rows[1]


@pytest.mark.asyncio
async def test_scope_cli_helper_builds_fresh_e3_and_exact_source_replay(tmp_path):
    from tests.unit_tests.research.test_evaluation_pilot import _prepared_source

    store, provider, actor, prepared, contract_ref, _, original, _, _ = await _prepared_source(tmp_path)
    (store.root / "operator").mkdir(mode=0o700)
    profile_dir = tmp_path / "phase1"
    profile_dir.mkdir()
    (profile_dir / "config.json").write_bytes(json_bytes(prepared["operator_config"]))
    (profile_dir / "bootstrap.json").write_bytes(json_bytes({
        "binding_ref": prepared["bootstrap_binding_ref"]}))
    (profile_dir / "pilot.json").write_bytes(json_bytes({
        "schema": "ai4r-evaluation-pilot-phase1:1",
        "profile_id": "pilot-ml",
        "configuration_ref": prepared["configuration_ref"],
        "library_snapshot_ref": provider.resources.snapshot_ref,
    }))

    contract = store.read_record(contract_ref, contract_id="subnode-execution-contract")
    declaration = store.read_record(contract["bindings"][0]["declaration_ref"],
                                    contract_id="capsule-declaration")
    source_id = contract_ref["id"]
    observation_id = original.observation_ref["id"]
    sources = cli.source_candidates(store, configuration_ref=prepared["configuration_ref"],
        candidate_pins=[{
            "cc_name": declaration["identity"]["name"],
            "cc_version": declaration["identity"]["version_label"],
            "declaration_sha256": contract["bindings"][0]["declaration_ref"]["sha256"],
        }])
    assert any(row["source_contract_ref"] == contract_ref for row in sources)

    output_dir = store.root / "operator" / "cli-phase2"
    result = cli.scope_from_source(store=store, profile_dir=profile_dir,
        source_contract_id=source_id, observation_id=observation_id,
        output_port="screening_result", campaign_id="cli-campaign", output_dir=output_dir,
        account_id=actor.account_id)

    pilot = json.loads((output_dir / "pilot.json").read_bytes())
    requests = json.loads((output_dir / "requests.json").read_bytes())
    assert result["invalid_for_product"] is True and pilot["invalid_for_product"] is True
    assert pilot["source_contract_ref"] == contract_ref
    assert pilot["source_observation_ref"] == original.observation_ref
    assert [row["entry_point"] for row in requests] == ["E3", "E2"]
    e3, e2 = (row["request"] for row in requests)
    assert e3["inputs"] == [
        {"port": port["name"], "path": f"fresh-e3/input-{port_index}-{input_index}.json",
         "sha256": ref["sha256"]}
        for port_index, port in enumerate(contract["inputs"])
        for input_index, ref in enumerate(port["artifact_refs"])
    ]
    assert e2["output"]["sha256"] == original.output_refs["screening_result"]["sha256"]
    replay_ref = pilot["source_replay_binding_ref"]
    replay = store.read_record(replay_ref)
    assert replay["original_observation_ref"] == original.observation_ref
    assert replay["output_refs"] == original.output_refs
    assert store.read_blob(pilot["configuration_ref"]) == store.read_blob(prepared["configuration_ref"])
    assert not list(store.iter_records(kinds=("gate-decision", "acceptance-commit")))
    store.close()


@pytest.mark.asyncio
async def test_scope_cli_helper_rejects_foreign_config_before_creating_output(tmp_path):
    from tests.unit_tests.research.test_evaluation_pilot import _prepared_source
    from jiuwenswarm.research.contracts import ResearchError

    store, provider, actor, prepared, contract_ref, _, original, _, _ = await _prepared_source(tmp_path)
    (store.root / "operator").mkdir(mode=0o700)
    profile_dir = tmp_path / "phase1"
    profile_dir.mkdir()
    (profile_dir / "config.json").write_bytes(json_bytes(prepared["operator_config"]))
    (profile_dir / "bootstrap.json").write_bytes(json_bytes({
        "binding_ref": prepared["bootstrap_binding_ref"]}))
    (profile_dir / "pilot.json").write_bytes(json_bytes({
        "schema": "ai4r-evaluation-pilot-phase1:1",
        "configuration_ref": prepared["configuration_ref"],
        "library_snapshot_ref": provider.resources.snapshot_ref,
    }))
    foreign = store.read_record(contract_ref, contract_id="subnode-execution-contract")
    foreign["configuration_ref"] = store.put_blob(b"different config")
    foreign_ref = store.put_record("subnode-execution-contract", foreign, record_id="cli-foreign-source")
    output_dir = store.root / "operator" / "should-not-exist"
    with pytest.raises(ResearchError, match="exact phase-one configuration"):
        cli.scope_from_source(store=store, profile_dir=profile_dir,
            source_contract_id=foreign_ref["id"], observation_id=original.observation_ref["id"],
            output_port="screening_result", campaign_id="cli-campaign", output_dir=output_dir,
            account_id=actor.account_id)
    assert not output_dir.exists()
    store.close()
