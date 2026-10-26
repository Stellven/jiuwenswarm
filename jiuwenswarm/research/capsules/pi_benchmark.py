"""Sequential baseline and candidate Pi measurements with root score evidence."""
from __future__ import annotations

import hashlib
import json
import math
import statistics

from ..contracts.types import ResearchError
from ..environment import validate_lock
from ..contracts import validate
from ..state import json_bytes
from ._common import captured, produced

PRIMARY_CASES = (("pi-10000", 10_000), ("pi-100000", 100_000))
EXTRA_CASES = (("pi-unseen-1", None), ("pi-unseen-2", None), ("pi-unseen-3", None))
BOUNDARY_CASES = tuple((f"pi-boundary-{digits}", digits) for digits in (0, 1, 2, 17))


async def execute(ctx, inputs):
    if ctx.executor is None:
        raise ResearchError("unavailable", "The scientific executor is unavailable")
    blueprint, manifest = inputs["hypothesis_blueprint"], inputs["poc_manifest"]
    ready, lock = inputs["build_receipt"], inputs["environment_lock"]
    validate("urn:ai4r:prediction-build-receipt:4.0.0" if ready.get("schema_version") == "4.0.0" else
             "urn:ai4r:prediction-build-receipt:3.0.0" if ready.get("schema_version") == "3.0.0" else
             "urn:ai4r:prediction-build-receipt:2.0.0", ready)
    if (blueprint.get("repeat_count") != 5 or ready.get("readiness") != "READY"
            or (ready.get("schema_version") != "4.0.0" and ready.get("trial_executed"))
            or (ready.get("schema_version") != "4.0.0" and ready.get("packages_installed"))
            or ready.get("manifest_ref") != ctx.input_ref("poc_manifest")
            or ready.get("archive_ref") != manifest.get("archive_ref")
            or ready.get("archive_ref") != ctx.input_ref("poc_artifact_bundle")
            or manifest.get("blueprint_ref") != ctx.input_ref("hypothesis_blueprint")):
        raise ResearchError("build_receipt_not_ready", "Benchmark requires the exact accepted Pi build")
    pins = validate_lock(lock, ctx.store.read_blob, lock["platform"])
    provision = await ctx.executor.provision(ctx.contract, inputs, pins)
    provision_ref = captured(ctx, provision)
    ctx.record_host("provisioning_receipt", provision_ref)
    if provision.get("status") != "succeeded":
        raise ResearchError("provisioning_failed", "Frozen environment provisioning failed")
    hardware = await ctx.executor.hardware_inventory(ctx.contract)
    hardware_ref = captured(ctx, hardware)
    runs, empirical_rows, score_refs, by_case = [], [], [], {}
    for case_id, digits in (*PRIMARY_CASES, *EXTRA_CASES, *BOUNDARY_CASES):
        roles = ("baseline", "treatment") if case_id in {"pi-10000", "pi-100000"} else ("treatment",)
        by_case[case_id] = {"digits": digits, "roles": {}}
        for role in roles:
            subject = blueprint["baseline_identity"]["resource_ref"] if role == "baseline" else manifest["archive_ref"]
            timings, corrects, case_runs = [], [], []
            repeats = 5 if case_id in {"pi-10000", "pi-100000"} else 1
            for repeat_index in range(repeats):
                sequence = len(runs) + 1
                job = await ctx.executor.measure_job(ctx.contract, inputs, role=role, repeat_index=repeat_index,
                    seed=blueprint["seed"], sequence=sequence, subject_ref=subject, hardware_ref=hardware_ref,
                    case_id=case_id)
                raw = await ctx.executor.run(job)
                ctx.store.append_record("scientific_execution", {"run_id": ctx.contract["run_id"],
                    "node_id": ctx.contract["node_id"], "attempt_id": ctx.contract["attempt_id"], "receipt": raw})
                if (raw.get("sequence") != sequence or raw.get("role") != role or raw.get("repeat_index") != repeat_index
                        or raw.get("seed") != blueprint["seed"] or raw.get("subject_ref") != subject
                        or raw.get("hardware_ref") != hardware_ref):
                    raise ResearchError("execution_receipt_mismatch", "Measured job identity differs from its frozen request")
                score_ref = raw.get("trusted_scoring_ref")
                score = ctx.read_json(score_ref) if score_ref else None
                score_elapsed = None
                if score is not None:
                    score_refs.append(score_ref)
                    if (score.get("case_id") != case_id or (digits is not None and score.get("digits") != digits)
                            or score.get("role") != role or score.get("repeat_index") != repeat_index
                            or score.get("sequence") != sequence or score.get("subject_ref") != subject
                            or score.get("contract_ref") != ctx.contract_ref
                            or type(score.get("digits")) is not int or not 0 <= score["digits"] <= 100_000):
                        raise ResearchError("pi_score_mismatch", "Root Pi score does not verify this measured job")
                    digits = score["digits"]
                    by_case[case_id]["digits"] = digits
                    correct = score.get("correct") is True
                    elapsed = score.get("elapsed_s")
                    if correct and type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0:
                        score_elapsed = elapsed
                        timings.append(elapsed)
                    corrects.append(correct)
                elapsed_raw = raw.get("wall_time_s")
                measured = (raw.get("exit_code") == 0 and score is not None
                            and score.get("correct") is True and type(elapsed_raw) in (int, float)
                            and math.isfinite(elapsed_raw) and elapsed_raw >= 0)
                empirical_rows.append({"sequence": sequence,
                    "status": "measured" if measured else "unmeasured",
                    "metrics": {"elapsed_s": elapsed_raw} if measured else {},
                    "unmeasured_metrics": {} if measured else {"elapsed_s": "metric_not_emitted"}})
                public = {key: raw[key] for key in ("sequence", "role", "repeat_index", "seed", "subject_ref",
                    "exit_code", "started_at", "wall_time_s", "timeout_s", "stdout_ref", "stderr_ref") if key in raw}
                public.update(command=list(raw["argv"]), hardware_ref=hardware["hardware_id"])
                runs.append(public)
                case_runs.append({"sequence": sequence, "score_ref": score_ref, "elapsed_s": score_elapsed,
                                  "correct": bool(corrects and corrects[-1])})
            all_correct = len(corrects) == repeats and all(corrects)
            by_case[case_id]["roles"][role] = {"repeats": len(case_runs),
                "median": statistics.median(timings) if all_correct else None,
                "spread": max(timings) - min(timings) if all_correct else None,
                "correct": all_correct, "runs": case_runs}
    receipt = {"schema_version": "1.0.0", "id": "execution_receipt", "blueprint_ref": ctx.input_ref("hypothesis_blueprint"),
        "poc_ref": ctx.input_ref("poc_manifest"), "hardware_inventory": hardware,
        "empirical_results_ref": captured(ctx, {"schema_version": "2.0.0", "id": "empirical_results", "runs": empirical_rows}),
        "runs": runs}
    receipt_ref = captured(ctx, receipt)
    ctx.record_host("execution_receipt", receipt_ref)
    primary = by_case["pi-100000"]["roles"]
    payload = {"schema_version": "1.0.0", "id": "pi_benchmark_payload", "blueprint_ref": ctx.input_ref("hypothesis_blueprint"),
        "poc_ref": ctx.input_ref("poc_manifest"), "environment_lock_ref": ctx.input_ref("environment_lock"),
        "execution_receipt_ref": receipt_ref, "provisioning_receipt_ref": provision_ref,
        "cases": [{"case_id": cid, "digits": row["digits"], **row["roles"]} for cid, row in by_case.items()],
        "primary_case": "pi-100000", "speedup": (primary["baseline"]["median"] / primary["treatment"]["median"]
            if primary.get("baseline", {}).get("correct") and primary.get("treatment", {}).get("correct")
            and primary.get("baseline", {}).get("median") and primary.get("treatment", {}).get("median") else None),
        "raw_evidence_refs": list({(ref["id"], ref["sha256"]): ref for ref in
            [provision_ref, receipt_ref, receipt["empirical_results_ref"]] + [run[k] for run in runs for k in ("stdout_ref", "stderr_ref")] + score_refs}.values())}
    return {"benchmark_payload": produced(payload, "urn:ai4r:pi-benchmark-payload:1.0.0"),
            "execution_receipt": produced(receipt, "execution-receipt"),
            "provisioning_receipt": produced(provision, "provisioning-receipt")}
