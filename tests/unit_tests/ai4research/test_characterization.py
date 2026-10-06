"""Development harness wiring only; all semantic findings are scripts.

No provider/model calls, protected POSIX availability or actual referee
reliability are established by this explicitly labelled fixture suite.
"""
import argparse
import asyncio
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.ai4research import characterization as measure
from jiuwenswarm.ai4research.common import GovernanceError, canonical_json, sha256_bytes
from tests.fixtures.ai4research.trial_support import ScriptedBridge, assessment_fixture, make_trial

CORPUS = Path(__file__).parents[2] / "fixtures/ai4research/intent/characterization/locked-candidates.json"


class ScriptedFindings(ScriptedBridge):
    def __init__(self, corpus, wrong_first=False):
        super().__init__()
        self._cases = [case for case in corpus["cases"] for _ in range(3)]
        self.wrong_first = wrong_first

    async def complete(self, *, role, model, input_data, identities, timeout_seconds):
        assert role == "verifier"
        case = self._cases[len(self.calls)]
        self.calls.append({"role": role, "input": copy.deepcopy(input_data), "identities": identities})
        fail = case["required_finding"] if case["expected"] == "FAIL" else None
        uncertain = case["required_finding"] if case["expected"] == "INCONCLUSIVE" else None
        if self.wrong_first and len(self.calls) == 1:
            fail = "F1"
        result = assessment_fixture(input_data, failed_check=fail, inconclusive_check=uncertain)
        return {**identities, "text": canonical_json(result).decode(), "model": model,
                "model_calls": 1, "effects": [], "mock": True, "runtime_version": "scripted-fixture-only",
                "usage": None, "cost": None, "seed": None}


def forbidden_label_keys(value):
    if isinstance(value, dict):
        assert not {"expected", "required_finding", "case_id", "label_authority"}.intersection(value)
        for child in value.values():
            forbidden_label_keys(child)
    elif isinstance(value, list):
        for child in value:
            forbidden_label_keys(child)


def test_exact_locked_candidate_bytes_and_spans_are_predeclared(tmp_path):
    corpus = measure.load_corpus(CORPUS)
    assert len(corpus["cases"]) == 9 and corpus["repetitions_real"] == 3
    assert sha256_bytes(CORPUS.read_bytes()) == measure.CORPUS_SHA256
    changed = tmp_path / "changed.json"
    changed.write_bytes(CORPUS.read_bytes() + b" ")
    with pytest.raises(GovernanceError, match="frozen corpus"):
        measure.load_corpus(changed)


@pytest.mark.asyncio
async def test_all_fixed_measurements_are_verifier_only_and_never_release(tmp_path):
    trial = make_trial(tmp_path / "trial")
    trial.application.bridge = ScriptedFindings(measure.load_corpus(CORPUS))
    report = await measure.run_campaign(trial.application, trial.context, corpus_path=CORPUS,
        output_dir=tmp_path / "measurements", fixture_mode=True)
    assert report["status"] == "FIXTURE_ONLY"
    assert report["expected_observations"] == report["recorded_observations"] == report["matched_observations"] == 27
    assert report["false_acceptances"] == report["false_refusals"] == 0
    assert report["accepted_ref"] is None and report["production_release"] is False
    assert len(trial.application.bridge.calls) == 27
    assert all(call["role"] == "verifier" for call in trial.application.bridge.calls)
    for call in trial.application.bridge.calls:
        forbidden_label_keys(call["input"])
        assert call["input"]["execution"]["compiler"]["status"] == "NOT_RUN"
        assert call["input"]["execution"]["model_calls"] == 0
    assert trial.application.store.list_runs(caller_id=trial.context.user_id) == []
    capture = measure.DevelopmentCapture(tmp_path / "measurements/development-state")
    for outcome in report["outcomes"]:
        assert outcome["compiler"] == "NOT_RUN" and outcome["accepted_ref"] is None
        assert outcome["actual_model_calls"] == 1 and len(outcome["attempts"]) == 1
        assert outcome["attempts"][0]["role"] == "verifier"
        run = capture.get_run(outcome["run_id"], caller_id=trial.context.user_id)
        assert run["accepted_ref"] is None
        assert not any(event["event_type"] == "attempt_started" for event in run["events"])
        raw = capture.get_artifact(outcome["assessment_ref"], caller_id=trial.context.user_id)
        assert sha256_bytes(raw) == outcome["assessment_ref"]["sha256"]
        with pytest.raises(GovernanceError, match="no compiler or replay"):
            capture.begin_attempt(run["run_id"], "verifier", caller_id=trial.context.user_id)
        with pytest.raises(GovernanceError, match="no accepted-artifact release"):
            capture.commit_decision(run["run_id"])
    manifest = json.loads((tmp_path / "measurements/manifest.json").read_bytes())
    assert len(manifest["cases"]) == 27 and manifest["labels_disclosed_to_assessor"] is False
    assert manifest["corpus_sha256"] == measure.CORPUS_SHA256


@pytest.mark.asyncio
async def test_no_implicit_mock_cli_or_python_fallback(tmp_path):
    trial = make_trial(tmp_path / "trial")
    report = await measure.run_campaign(trial.application, trial.context, corpus_path=CORPUS,
        output_dir=tmp_path / "blocked")
    assert report["status"] == "ENVIRONMENT_BLOCKED" and report["matched_observations"] == 0
    assert len(report["outcomes"]) == 27 and all(row["observed"] == "NOT_RUN" for row in report["outcomes"])
    assert all(row["actual_model_calls"] == 0 for row in report["outcomes"])
    assert trial.bridge.calls == []


@pytest.mark.asyncio
async def test_case_failure_retained_without_relabel_or_stopping_later_cases(tmp_path):
    trial = make_trial(tmp_path / "trial")
    trial.application.bridge = ScriptedFindings(measure.load_corpus(CORPUS), wrong_first=True)
    report = await measure.run_campaign(trial.application, trial.context, corpus_path=CORPUS,
        output_dir=tmp_path / "failure", fixture_mode=True)
    assert report["status"] == "FIXTURE_ONLY" and report["matched_observations"] == 26
    assert report["false_refusals"] == 1 and report["false_acceptances"] == 0
    assert report["outcomes"][0]["result"] == "MISMATCH" and report["outcomes"][0]["expected"] == "PASS"
    assert len(trial.application.bridge.calls) == 27
    with pytest.raises(GovernanceError, match="cannot be overwritten"):
        await measure.run_campaign(trial.application, trial.context, corpus_path=CORPUS,
            output_dir=tmp_path / "failure", fixture_mode=True)


@pytest.mark.asyncio
async def test_false_acceptances_are_retained_under_frozen_negative_labels(tmp_path):
    trial = make_trial(tmp_path / "trial")  # Default fixture scripts every finding PASS.
    report = await measure.run_campaign(trial.application, trial.context, corpus_path=CORPUS,
        output_dir=tmp_path / "false-acceptance", fixture_mode=True)
    assert report["status"] == "FIXTURE_ONLY" and report["matched_observations"] == 6
    assert report["false_acceptances"] == 21 and report["false_refusals"] == 0
    assert all(row["accepted_ref"] is None for row in report["outcomes"])
    assert all(row["expected"] != "PASS" and row["observed"] == "PASS" for row in report["outcomes"] if row["false_acceptance"])
    assert len(trial.bridge.calls) == 27 and trial.application.store.list_runs(caller_id=trial.context.user_id) == []


@pytest.mark.asyncio
async def test_corpus_custody_inside_workspace_is_denied_before_calls(tmp_path):
    trial = make_trial(tmp_path / "trial")
    with pytest.raises(GovernanceError, match="outside the trial workspace"):
        await measure.run_campaign(trial.application, trial.context, corpus_path=CORPUS,
            output_dir=Path(trial.context.workspace_path) / "hidden-labels", fixture_mode=True)
    assert trial.bridge.calls == []


@pytest.mark.asyncio
async def test_real_generation_change_is_blocked_before_measurement(monkeypatch):
    class Bridge:
        is_mock = False
    class App:
        bridge = Bridge()
        baseline = {"runtime_identity": {"account_fingerprint": "0" * 64, "account_epoch": "old", "runtime_version": "0.144.4"}}
        async def readiness(self):
            return {"ready": True, "identity_security": {"ready": True}, "model": {"security_ready": True,
                    "account_fingerprint": "0" * 64, "account_epoch": "new", "runtime_version": "0.144.4"}}
    app = App()
    with pytest.raises(GovernanceError, match="generation changed"):
        await measure._ready(app, app.baseline["runtime_identity"], False)


@pytest.mark.asyncio
async def test_cli_passes_admission_receipt_and_releases_all_owned_lifecycle(tmp_path, monkeypatch, capsys):
    observed = []
    class Lease:
        def release(self):
            observed.append("release")
    class Bridge:
        async def close(self):
            observed.append("close")
    class Identity:
        def authenticate(self, token):
            return object()
    class App:
        bridge, identity, process_lease = Bridge(), Identity(), Lease()
        async def shutdown(self):
            observed.append("shutdown")
    token_path = tmp_path / "session.token"
    token_path.write_text("local-fixture-session", encoding="utf-8")
    receipt = tmp_path / "admission.json"
    async def bootstrap(*args, **kwargs):
        assert kwargs["admission_receipt"] == receipt
        return App(), None, None, token_path
    async def failed_campaign(*args, **kwargs):
        raise GovernanceError("security_unavailable", "Fixture unsupported boundary.")
    monkeypatch.setattr(measure, "bootstrap", bootstrap)
    monkeypatch.setattr(measure, "run_campaign", failed_campaign)
    args = argparse.Namespace(state_dir=tmp_path / "state", workspace=tmp_path / "workspace",
        corpus=CORPUS, output_dir=tmp_path / "output", model=None, admission_receipt=receipt)
    assert await measure._main(args) == 3
    output = capsys.readouterr().out
    assert "local-fixture-session" not in output and json.loads(output)["status"] == "BLOCKED"
    assert observed == ["shutdown", "close", "release"]
