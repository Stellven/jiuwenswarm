# Examples

`Tier 3 · Part of: [Reference](../README.md)`

Examples are for people. The field tables and check tables define each contract, and a builder works from them. This folder holds one linked research chain (request to delivery), the CC declarations, one routing pass case, one RSI admission pass case, and 15 invalid records that each name the check that rejects them in `rejected_by`. `validate.py` fails when that check passes on an invalid record. All data is synthetic. [index.json](index.json) lists every record with its contract.

## Linked research path

`lifecycle_research_brief.json` → `candidate_set.json` → `screening_result.json` → `opportunity_card.json` → `hypothesis_blueprint.json` → `poc_manifest.json` → `benchmark_payload.json` → `evaluation_verdict.json` → `delivery_manifest.json` and `research_report.md`.
