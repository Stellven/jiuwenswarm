"""Read-only human-facing catalogue and ledger for existing campaign evidence.

This module only projects supplied frozen manifests and Dataset records. It does
not dispatch work, grade outputs, or decide acceptance. Derived verification
tasks are listed as reuse of their parent probe rows, not new trials.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

from .value_data import Dataset, canonical, csv_bytes, write_once


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _public_description(root: Path, ident: str, group: str) -> str:
    """Read only public task text; never inspect private oracle files."""
    if group in {"base", "supplemental"}:
        relative = ident.replace("/", "--") + ".json"
        task = _read(root / "public" / relative)
        return str(task.get("objective", ""))
    if group == "paper":
        task = _read(root / ident / "task.json")
        return str(task.get("task", task.get("objective", task.get("prompt", ""))))
    if group == "planning":
        return "Assess the five public planning constraints using candidate.json and frozen context."
    return ""


def _base_row(population, case_id, group, root, fields):
    return {
        "population": population,
        "case_id": str(case_id),
        "purpose": fields.get("purpose", fields.get("role", fields.get("family", ""))),
        "difficulty": fields.get("difficulty", "not_recorded_in_source"),
        "public_input_sha256": fields.get("task_sha256", fields.get("public_sha256", fields.get("request_sha256", ""))),
        "expected_behavior": fields.get("expected_behavior", ""),
        "provenance": fields.get("provenance", fields.get("source", "")),
        "runtime_prerequisites": fields.get("runtime_prerequisites", fields.get("readiness", "not_recorded")),
        "measurement_status": fields.get("measurement_status", "not_recorded"),
        "scope_note": fields.get("scope_note", ""),
        "description": _public_description(root, str(case_id), group) if root else "",
        "counting_note": fields.get("counting_note", "One catalogue entry from this source inventory."),
    }


def load_catalogue(*, base_bank=None, supplemental_bank=None, planning_manifest=None,
                   paper_manifest=None, semantic_manifest=None, verification_source=None,
                   design_matrix=None, dataset=None):
    """Return separate source populations; derived rows never inflate trial totals."""
    rows, designs = [], []

    def case_bank(path, population, group):
        if not path:
            return
        root = Path(path).absolute()
        manifest = _read(root / "manifest.json")
        if manifest.get("schema") != "ai4r-value-case-bank:1":
            raise ValueError(f"unexpected {population} manifest schema")
        for entry in manifest["cases"]:
            task_path = root / "public" / (entry["id"].replace("/", "--") + ".json")
            task_sha = hashlib.sha256(canonical(_read(task_path))).hexdigest()
            if task_sha != entry["task_sha256"]:
                raise ValueError(f"public task hash mismatch: {entry['id']}")
            rows.append(_base_row(population, entry["id"], group, root, {
                **entry,
                "purpose": entry.get("id", "").split("/", 1)[0],
                "expected_behavior": "Use the public task objective and response schema; private expected outputs remain separate.",
                "provenance": entry.get("source", ""),
                "runtime_prerequisites": entry.get("readiness", "not_recorded"),
                "scope_note": "Frozen task; measurement status is taken from the manifest.",
            }))

    case_bank(base_bank, "base_frozen_80", "base")
    case_bank(supplemental_bank, "public_source_supplemental_8", "supplemental")

    if planning_manifest:
        path = Path(planning_manifest).absolute()
        manifest = _read(path)
        for item in manifest["cases"]:
            rows.append(_base_row("planning_component_8", item["case_id"], "planning", path.parent, {
                **item, "purpose": "production_planning_component", "expected_behavior": "Report all failed named planning constraints from public task.",
                "provenance": "Constructed component fixture; no capsule admission or full-unit run claimed.",
                "runtime_prerequisites": "component-only; public request and validator skill available",
                "measurement_status": item.get("measurement_status", "not_recorded"),
                "scope_note": manifest.get("component_only", "component-only; not full planning evidence"),
            }))

    if paper_manifest:
        path = Path(paper_manifest).absolute()
        manifest = _read(path)
        for item in manifest["cases"]:
            rows.append(_base_row("primary_pdf_cases_4", item["id"], "paper", path.parent, {
                **item, "purpose": "PDF paper workflow", "expected_behavior": "Produce a schema-conforming result that the frozen case oracle can grade.",
                "provenance": "Primary locally authored PDF task bank; no model dispatch unless run record says so.",
                "runtime_prerequisites": item.get("readiness", "not_recorded"),
                "scope_note": "PDF case bank; transport readiness is distinct from completed E1 comparison.",
            }))

    if semantic_manifest:
        path = Path(semantic_manifest).absolute()
        manifest = _read(path)
        for item in manifest["cases"]:
            rows.append(_base_row("semantic_component_8", item["id"], "semantic", path.parent, {
                **item, "purpose": item.get("role", "semantic verifier component"),
                "expected_behavior": "Run as a semantic-verifier component case; detailed expected label is not copied into this public catalogue.",
                "provenance": "Frozen public semantic component; no E2/E3 admission or gate is implied.",
                "runtime_prerequisites": "component service/admission not run",
                "measurement_status": item.get("measurement_status", "not_run"),
                "scope_note": manifest.get("scope", "component-only"),
            }))

    if verification_source:
        # Reuse selection coordinates from the existing bank definition. The
        # display catalogue deliberately omits expected verdict/private rationale.
        from .value_verification_cases import SELECTION
        records = Dataset(dataset).records() if dataset else []
        candidates = [r for r in records if r["kind"] == "capability_probe"]
        original = {r["id"]: r for r in candidates}
        source_record = _read(verification_source)
        if source_record.get("kind") != "capability_probe":
            raise ValueError("verification source must be a retained capability_probe record")
        rows_by_coordinate = {}
        for row in source_record["value"].get("rows", []):
            key = (row.get("module"), row.get("case_id"), row.get("fault"))
            rows_by_coordinate.setdefault(key, []).append(row)
        for i, (module, case_id, fault, _verdict, _rationale) in enumerate(SELECTION, 1):
            matching = rows_by_coordinate.get((module, case_id, fault), [])
            if len(matching) != 1:
                raise ValueError(f"verification source does not contain unique coordinate {case_id}/{fault}")
            source_row = matching[0]
            pair_id = source_record["value"].get("paired_with")
            if pair_id not in original:
                raise ValueError("verification task lacks the original paired probe record")
            rows.append({
                "population": "fault_verification_reuse_9",
                "case_id": f"verify-{i:03d}", "purpose": f"artifact verification: {module}",
                "difficulty": "not_recorded_in_source", "public_input_sha256": source_row.get("input_sha256", ""),
                "expected_behavior": "Classify the proposal against its original packet and supplied contract; private expected labels omitted.",
                "provenance": f"Reuses row {case_id}/{fault} from probe {source_record['id']} (paired original {pair_id}).",
                "runtime_prerequisites": "verification task not run",
                "measurement_status": "not_run",
                "scope_note": "Derived from existing probe; zero additional independent trials claimed.",
                "description": f"Review the proposed artifact for {fault.replace('_', ' ')}.",
                "counting_note": "Reused underlying probe row; do not add as an independent artifact trial.",
            })

    if design_matrix:
        matrix = _read(design_matrix)
        for item in matrix.get("cases", []):
            designs.append({
                "population": "design_matrix_only",
                "case_id": item.get("case_id", ""), "family": item.get("family", ""),
                "graph_question": item.get("graph_question", ""), "focus": item.get("focus", ""),
                "status": item.get("status", "design_only_not_a_runnable_or_executed_trial"),
                "coverage_status": item.get("coverage_status", "planned_not_observed"),
                "task_sha256": "", "counting_note": "Planning sketch; not an additional frozen/executed case.",
            })
    return rows, designs


def _record_row(record, selection_ids, pair_by_id):
    value = record["value"]
    kind = record["kind"]
    result = value.get("result", {}) if isinstance(value.get("result"), dict) else {}
    summary = value.get("summary") or value.get("reason") or result.get("status") or ""
    rows = value.get("rows", []) if isinstance(value.get("rows"), list) else []
    coordinates = {(r.get("case_id"), r.get("fault"), r.get("input_sha256"), r.get("artifact_sha256"))
                   for r in rows if isinstance(r, dict)}
    unique_pairs = {(r.get("input_sha256"), r.get("artifact_sha256")) for r in rows if isinstance(r, dict)}
    actual = {}
    if kind == "native_cc_pair":
        arms = value.get("arms", {})
        actual = {"comparison_eligible": value.get("comparison_eligible"),
            "native_correct": arms.get("native-skills", {}).get("correct"),
            "cc_correct": arms.get("cc", {}).get("correct"),
            "native_model_calls": arms.get("native-skills", {}).get("model_calls"),
            "cc_model_calls": arms.get("cc", {}).get("model_calls"),
            "content_delta_cc_minus_native": value.get("content_delta_cc_minus_native")}
    elif kind == "product_qualification":
        actual = {"grade": value.get("grade", result.get("grade")),
                  "result_status": result.get("status"), "result_outcome": result.get("outcome")}
    elif kind in {"native_trial", "native_qualification"}:
        actual = {"status": value.get("status"), "reason": value.get("reason"),
                  "attempts": value.get("attempts"), "experimental_calls": value.get("experimental_calls")}
    return {
        "record_id": record["id"], "kind": kind, "recorded_at": record.get("recorded_at", ""),
        "status": value.get("status", result.get("status", result.get("outcome", "recorded"))),
        "selected_in_current_report": record["id"] in selection_ids,
        "paired_with": value.get("paired_with", ""),
        "pair_relation": "explicitly paired rerun" if value.get("paired_with") else "unpaired record",
        "parent_record_ids": ";".join(str(x) for x in value.get("sources", []) if isinstance(x, str))
            if isinstance(value.get("sources"), list) else "",
        "case_id": value.get("case_id", value.get("row", {}).get("case_id", "")),
        "model_calls": value.get("model_calls", value.get("experimental_calls", "")),
        "observed_rows": len(rows), "unique_coordinates_in_record": len(coordinates),
        "unique_input_artifact_pairs_in_record": len(unique_pairs),
        "population_note": ("Contains repeated source artifacts; rows are not independent trials."
            if kind == "capability_probe" else "Full retained record; import status is preserved."),
        "scope": value.get("scope", value.get("comparison_scope", "")),
        "summary": summary,
        "actual_outcomes": canonical(actual).decode("utf-8"),
        "evidence_refs": canonical({k: v for k, v in value.items() if k in {
            "source", "sources", "archive", "retained_sources", "result", "grade", "attempts", "calls_consumed", "calls_remaining"
        }}).decode("utf-8"),
        "known_repeats_of": pair_by_id.get(record["id"], ""),
    }


def render(*, catalogue, records, output, selection=None, designs=()):
    destination = Path(output).absolute()
    if destination.exists():
        raise ValueError("output must be a fresh directory; existing evidence is never overwritten")
    repo = Path(__file__).parents[2].absolute()
    if destination.is_relative_to(repo):
        raise ValueError("viewer output must stay outside the Git checkout")
    destination.mkdir(parents=True)
    selected = set((selection or {}).get("record_ids", []))
    pair_by_id = {r["id"]: r["value"].get("paired_with", "") for r in records}
    ledger = [_record_row(r, selected, pair_by_id) for r in records]
    write_once(destination / "case-catalogue.csv", csv_bytes(catalogue, [
        "population", "case_id", "purpose", "difficulty", "public_input_sha256", "expected_behavior",
        "provenance", "runtime_prerequisites", "measurement_status", "scope_note", "description", "counting_note"]), raw=True)
    write_once(destination / "run-ledger.csv", csv_bytes(ledger, list(ledger[0]) if ledger else ["record_id", "kind", "status"]), raw=True)
    write_once(destination / "run-ledger.jsonl", b"".join(canonical({
        "projection": row, "source_record": source
    }) + b"\n" for row, source in zip(ledger, records, strict=True)), raw=True)
    if designs:
        write_once(destination / "design-matrix.csv", csv_bytes(designs, [
            "population", "case_id", "family", "graph_question", "focus", "status", "coverage_status", "task_sha256", "counting_note"]), raw=True)
    counts = {}
    state_counts = {}
    for row in catalogue:
        counts[row["population"]] = counts.get(row["population"], 0) + 1
        key = (row["population"], str(row.get("runtime_prerequisites", "not_recorded")),
               str(row.get("measurement_status", "not_recorded")))
        state_counts[key] = state_counts.get(key, 0) + 1
    probe_rows = [r for r in ledger if r["kind"] == "capability_probe"]
    total_probe_rows = sum(r["observed_rows"] for r in probe_rows)
    raw_probe_values = [r["value"] for r in records if r["kind"] == "capability_probe"]
    all_probe_observations = [row for value in raw_probe_values for row in value.get("rows", [])]
    unique_probe_pairs = {(r.get("input_sha256"), r.get("artifact_sha256")) for r in all_probe_observations}
    distinct_probe_coordinates = {(r.get("case_id"), r.get("fault"), r.get("input_sha256"), r.get("artifact_sha256"))
                                  for r in all_probe_observations}
    current_selected = sum(r["selected_in_current_report"] for r in ledger)
    summary = {
        "schema": "ai4r-value-view:1", "catalogue_rows_by_population": counts,
        "readiness_measurement_counts": {f"{pop}|{ready}|{measured}": count
            for (pop, ready, measured), count in sorted(state_counts.items())},
        "catalogue_rows_total_not_deduplicated_across_populations": len(catalogue),
        "design_matrix_sketches_not_in_catalogue_count": len(designs),
        "dataset_record_count": len(records), "selected_dataset_record_count": current_selected,
        "capability_probe_record_count": len(probe_rows), "capability_probe_rows_retained": total_probe_rows,
        "capability_probe_unique_case_fault_content_coordinates_across_records": len(distinct_probe_coordinates),
        "capability_probe_unique_input_artifact_pairs_across_records": len(unique_probe_pairs),
        "capability_probe_repeat_observations_over_unique_coordinates": max(0, total_probe_rows - len(distinct_probe_coordinates)),
        "verification_reuse_rows_are_additional_trials": False,
        "read_only_projection": True,
        "caveat": "Counts are per source population/record. Derived verification cases reuse probe rows; selected views do not replace unselected or failed records.",
    }
    write_once(destination / "index.json", summary)
    lines = ["# Existing campaign cases and run ledger", "",
        "Generated from frozen manifests and retained Dataset records. No tasks were dispatched or graded by this viewer.", "",
        "## Case populations", "", "| Population | Entries |", "| --- | ---: |"]
    for pop, count in sorted(counts.items()):
        lines.append(f"| {pop} | {count} |")
    lines += ["", "Readiness and measurement status stay separate: runnable means the named component fixture can run offline, not that a product capsule was admitted or an agent trial occurred.", "",
        "| Population | Readiness | Measurement status | Entries |", "| --- | --- | --- | ---: |"]
    for (pop, ready, measured), count in sorted(state_counts.items()):
        lines.append(f"| {pop} | {ready} | {measured} | {count} |")
    lines += ["", f"The optional design matrix contains {len(designs)} planning sketches, kept separate from frozen runnable cases.",
        "Population counts are not added into a single ‘unique trial’ total: the verification bank reuses probe artifacts, and design sketches are not executions.", "",
        "## Retained run records", "", f"Dataset records: **{len(records)}**; selected for the current report: **{current_selected}**.",
        f"Capability-probe rows retained: **{total_probe_rows}** across {len(probe_rows)} records, representing {len(distinct_probe_coordinates)} unique case/fault/content coordinates and {len(unique_probe_pairs)} unique input/artifact pairs. The remaining {max(0, total_probe_rows - len(distinct_probe_coordinates))} rows repeat an existing coordinate across reruns; they are retained observations, not new cases.",
        "The CSV ledger marks explicit parent pairing, current-report selection, status, source references, and reused-content notes. No records are dropped because they are failed, superseded, or unselected.", ""]
    write_once(destination / "README.md", "\n".join(lines).encode("utf-8"), raw=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-bank")
    parser.add_argument("--supplemental-bank")
    parser.add_argument("--planning-manifest")
    parser.add_argument("--paper-manifest")
    parser.add_argument("--semantic-manifest")
    parser.add_argument("--verification-source")
    parser.add_argument("--design-matrix")
    parser.add_argument("--selection")
    args = parser.parse_args(argv)
    rows, designs = load_catalogue(base_bank=args.base_bank, supplemental_bank=args.supplemental_bank,
        planning_manifest=args.planning_manifest, paper_manifest=args.paper_manifest,
        semantic_manifest=args.semantic_manifest, verification_source=args.verification_source,
        design_matrix=args.design_matrix, dataset=args.dataset)
    records = Dataset(args.dataset).records()
    selection = _read(args.selection) if args.selection else None
    result = render(catalogue=rows, records=records, output=args.output, selection=selection, designs=designs)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
