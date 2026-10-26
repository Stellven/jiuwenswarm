"""Checks bind Pi timings to protected root scores and captured executor jobs."""
import statistics
import json

from .stages import ResearchChecks, require
from ..contracts import validate
from ..process_evidence import validate_process_evidence


class PiBenchmarkChecks(ResearchChecks):
    def __init__(self, stage="benchmark", *, executor=None):
        super().__init__(stage, executor=executor)
        self.check_ids = [*self.check_ids, "pi_cases_complete", "pi_scores_protected"]

    async def _benchmark(self, ctx, inputs, outputs):
        from ..capsules.pi_benchmark import PRIMARY_CASES, EXTRA_CASES, BOUNDARY_CASES
        blueprint, manifest = inputs["hypothesis_blueprint"], inputs["poc_manifest"]
        payload, receipt = outputs["benchmark_payload"], outputs["execution_receipt"]
        ready = inputs["build_receipt"]
        validate("urn:ai4r:prediction-build-receipt:4.0.0" if ready.get("schema_version") == "4.0.0" else
                 "urn:ai4r:prediction-build-receipt:3.0.0" if ready.get("schema_version") == "3.0.0" else
                 "urn:ai4r:prediction-build-receipt:2.0.0", ready)
        require(blueprint["repeat_count"] == 5 and ready["readiness"] == "READY"
                and (ready.get("schema_version") == "4.0.0" or (not ready["trial_executed"] and not ready["packages_installed"]))
                and ready["manifest_ref"] == ctx.input_ref("poc_manifest")
                and ready["archive_ref"] == ctx.input_ref("poc_artifact_bundle"), "build_receipt_ready")
        require(payload["blueprint_ref"] == receipt["blueprint_ref"] == ctx.input_ref("hypothesis_blueprint")
                and payload["poc_ref"] == receipt["poc_ref"] == ctx.input_ref("poc_manifest")
                and payload["execution_receipt_ref"] == ctx.output_refs["execution_receipt"]
                and payload["provisioning_receipt_ref"] == ctx.output_refs["provisioning_receipt"],
                "protocol_matches_blueprint")
        cases = payload["cases"]
        require([case["case_id"] for case in cases] == [case for case, _ in (*PRIMARY_CASES, *EXTRA_CASES, *BOUNDARY_CASES)],
                "pi_cases_complete")
        expected_runs = 27
        require(len(receipt["runs"]) == expected_runs, "raw_repeats_present")
        protected = [item["record"]["receipt"] for item in ctx.store.iter_records(
            run_id=ctx.contract["run_id"], kinds=("scientific_execution",))
            if item["record"].get("attempt_id") == ctx.contract["attempt_id"]
            and item["record"].get("node_id") == ctx.contract["node_id"]]
        require(len(protected) == expected_runs, "raw_repeats_present")
        seen = set()
        scores = {}
        affinities = set()
        memory_ceiling = min(ctx.contract["subnode_limits"]["memory_mb"],
                             ctx.contract["bindings"][0]["limits"]["memory_mb"]) * 1024 * 1024
        hardware = receipt["hardware_inventory"]
        for expected_sequence, public in enumerate(receipt["runs"], 1):
            seq = public["sequence"]
            require(seq == expected_sequence, "empirical_sequence_contiguous")
            matching = [raw for raw in protected if raw.get("sequence") == seq]
            require(len(matching) == 1, "raw_repeats_present")
            raw = matching[0]
            score_ref = raw.get("trusted_scoring_ref")
            score = ctx.read_json(score_ref) if score_ref else None
            case_id = score.get("case_id") if score else None
            key = (case_id, raw.get("role"), raw.get("repeat_index"))
            require(key not in seen and key[0] in {case["case_id"] for case in cases}, "raw_repeats_present")
            seen.add(key)
            require(all(raw.get(k) == public.get(k) for k in ("sequence", "role", "repeat_index", "seed",
                "subject_ref", "exit_code", "started_at", "wall_time_s", "timeout_s", "stdout_ref", "stderr_ref"))
                and raw.get("argv") == public.get("command"),
                "protocol_matches_blueprint")
            limits = raw.get("observed_limits", {})
            try:
                is_m1 = raw.get('execution_mode') == 'm1_app_process'
                if is_m1:
                    process_ok = validate_process_evidence(ctx.store, raw, expected_uid=10002, expected_gid=10002,
                        contract_ref=ctx.observation['contract_ref'], invocation_id=raw.get('invocation_id'), job_id=raw.get('job_id'))
                    proof = ctx.read_json(limits['process_observation_ref']) if process_ok else {}
                    memory_max = pids_max = 0
                else:
                    process_ok = False
                    memory_max, pids_max = int(limits.get("memory_max", "0")), int(limits.get("pids_max", "0"))
                    proof = ctx.read_json(limits["isolation_probe_ref"])
                no_effective_caps = int(proof.get("cap_effective", "-1"), 16) == 0
                hardware_bytes = ctx.store.read_blob(raw["hardware_ref"])
                hardware_value = json.loads(hardware_bytes.decode("utf-8"))
            except (KeyError, TypeError, ValueError, UnicodeError):
                require(False, "pi_scores_protected")
            affinity = limits.get("cpu_affinity")
            require(raw.get("observed_runtime") is True
                    and raw.get("contract_ref") == ctx.observation["contract_ref"]
                    and type(raw.get("invocation_id")) is str and bool(raw["invocation_id"])
                    and raw.get("identity", {}).get("executor_uid") == 10002
                    and raw.get("identity", {}).get("executor_gid") == 10002
                    and (process_ok if is_m1 else memory_max > 0 and memory_max <= memory_ceiling
                         and 0 < pids_max <= 64)
                    and type(affinity) is list and bool(affinity)
                    and all(type(cpu) is int and cpu >= 0 for cpu in affinity)
                    and affinity == sorted(set(affinity))
                    and hardware_value == hardware
                    and hardware.get("hardware_id") == public.get("hardware_ref")
                    and proof.get("ready") is True and proof.get("executor_uid") == 10002
                    and proof.get("executor_gid") == 10002
                    and (is_m1 or proof.get("network") == "none")
                    and proof.get("no_new_privileges") == "1"
                    and no_effective_caps
                    and proof.get("cpu_affinity") == affinity
                    and (is_m1 or limits.get('network') == 'none'),
                    "pi_scores_protected")
            affinities.add(tuple(affinity))
            if score_ref:
                require(ctx.store.record_kind(score_ref) == "pi_scoring_receipt", "pi_scores_protected")
                require(ctx.store.record_ref(score["id"]) == score_ref
                    and score.get("contract_ref") == ctx.observation["contract_ref"]
                    and score.get("job_id") == raw.get("job_id")
                    and score.get("case_id") == case_id
                    and score.get("sequence") == seq and score.get("repeat_index") == raw.get("repeat_index")
                    and score.get("role") == raw.get("role") and score.get("subject_ref") == raw.get("subject_ref")
                    and score.get("invocation_id") == raw.get("invocation_id")
                    and score.get("cpu_affinity") == affinity
                    and type(score.get("digits")) is int and 0 <= score["digits"] <= 100_000
                    and type(score.get("correct")) is bool
                    and ((score.get("correct") is True and score.get("elapsed_s") == raw.get("wall_time_s"))
                         or (score.get("correct") is False and score.get("elapsed_s") is None)), "pi_scores_protected")
                require(score_ref in payload["raw_evidence_refs"], "pi_scores_protected")
                require(score.get("stdout_ref") == raw.get("stdout_ref") and score.get("stderr_ref") == raw.get("stderr_ref"),
                        "pi_scores_protected")
                scores[seq] = score
        require(len(affinities) == 1, "pi_scores_protected")
        require(len(seen) == expected_runs, "raw_repeats_present")
        for case in cases:
            primary = case["case_id"] in {"pi-10000", "pi-100000"}
            expected_repeats = 5 if primary else 1
            for role in ("baseline", "treatment"):
                actual = case.get(role)
                if actual is None:
                    require(role == "baseline" and not primary, "pi_cases_complete")
                    continue
                require(actual["repeats"] == expected_repeats, "pi_cases_complete")
                linked = [raw for raw in protected if raw.get("role") == role and
                          (ctx.read_json(raw["trusted_scoring_ref"]).get("case_id") if raw.get("trusted_scoring_ref") else None) == case["case_id"]]
                require(len(linked) == actual["repeats"], "pi_cases_complete")
                times = []
                correctness = []
                digit_values = set()
                for expected_repeat, raw in enumerate(linked):
                    score_ref = raw.get("trusted_scoring_ref")
                    require(score_ref is not None, "pi_scores_protected")
                    score = ctx.read_json(score_ref)
                    require(score["repeat_index"] == expected_repeat, "protocol_matches_blueprint")
                    digit_values.add(score["digits"])
                    correctness.append(score["correct"] is True)
                    if score["correct"] is True:
                        times.append(raw["wall_time_s"])
                require(case["digits"] in digit_values and len(digit_values) == 1, "pi_cases_complete")
                complete = len(correctness) == expected_repeats and all(correctness)
                median = statistics.median(times) if complete else None
                spread = max(times) - min(times) if complete else None
                require(actual["median"] == median and actual["spread"] == spread
                        and actual["correct"] == all(correctness), "pi_cases_complete")
        primary = next(case for case in cases if case["case_id"] == "pi-100000")
        expected_speedup = (primary["baseline"]["median"] / primary["treatment"]["median"]
            if primary["baseline"]["correct"] and primary["treatment"]["correct"]
            and primary["baseline"]["median"] and primary["treatment"]["median"] else None)
        require(payload["speedup"] == expected_speedup, "pi_cases_complete")
        empirical = ctx.read_json(receipt["empirical_results_ref"])
        validate("empirical-results:field-contract:2", empirical)
        require(len(empirical["runs"]) == expected_runs, "values_match_empirical_results")
        for row, raw in zip(empirical["runs"], receipt["runs"]):
            score = scores.get(raw["sequence"])
            measured = score is not None and score.get("correct") is True and raw.get("exit_code") == 0
            require(row["sequence"] == raw["sequence"] and
                (row["status"] == "measured" and row["metrics"] == {"elapsed_s": raw["wall_time_s"]}
                 and row["unmeasured_metrics"] == {} if measured else
                 row["status"] == "unmeasured" and row["metrics"] == {}
                 and row["unmeasured_metrics"] == {"elapsed_s": "metric_not_emitted"}),
                "values_match_empirical_results")
