# Ten-case Harbor suite authoring contract

This is development benchmark material. The owner is the benchmark, not the
product. These files introduce no product wire fields, permissions, or release
criteria. Protected labels/oracles never enter an evaluated app/container.

Each case author owns only `cases/<case-id>/` and supplies:

- `case.json`, the authoring metadata below (not submitted as a product request).
- `public/` containing frozen, small technology/CS research inputs.
- `referee/criteria.json`, independently specified expected behavior per variant.
- `oracle.py`, a stdlib-only independent checker, copied only to a separate verifier.
- `test_oracle.py`, executable unittest tests of correct/defective/missing evidence.
- `README.md`, concise research obligation, interface binding and remaining readiness.

Required case.json shape (all paths relative to its case directory):

```json
{
  "schema": "ai4r-harbor-suite-case:1",
  "id": "cc01-transfer",
  "module": "cc",
  "title": "Short title",
  "scenario_ids": ["s01"],
  "milestone": "m1",
  "classification": "core_m1_acceptance",
  "requirements": ["B01", "CC01"],
  "domains": ["c02"],
  "entrypoint": "single_cc",
  "objective": "Technical research/workflow obligation",
  "primary_metric": {"name": "...", "definition": "Exact numerator and denominator"},
  "budgets": {"wall_time_s": 600, "max_model_calls": 20,
    "physical_memory_mb": 1024, "committed_memory_mb": 2048,
    "storage_mb": 512, "concurrency": 1, "gpu_required": false},
  "product_prerequisites": ["Declared supported interface and authority"],
  "evidence_requirements": ["gate-decision", "invocation-observation"],
  "variants": [{"id": "valid", "split": "development",
    "task": "Visible task; NEVER include answers, planted labels, oracle rules or grading thresholds that are not task requirements",
    "inputs": [{"path": "public/input.json", "kind": "docs"}],
    "expected_behavior": "complete", "seed": 1701}],
  "oracle_version": "1"
}
```

Modules: cc, mr, rsi, verifier, pipeline. Entrypoints: run, single_cc,
node_replay, routing, rsi. Classification: core_m1_acceptance,
m2_m3_progress, extended_performance. MR/RSI are milestone m2 and explicitly
reusable at m3, never M1 acceptance. At least three independently designed
variants per top-level case; mandatory fault/domain categories may need more.
Verifier cases collectively cover all ten Requirements12.1 acceptance cases.
MR01/MR02 collectively retain all c01-c08 domain rows. Real long-horizon claims
are out of this fast suite. Full campaigns use three repeats per stochastic
configuration; a one-repeat smoke profile is explicitly a wiring check only.

The parent supplies Harbor packaging, invocation, export validation and an
offline normalized-evidence reader. Do not author placeholder product tokens,
approved grants, fake run IDs or fabricated production observations.

`oracle.py` exports `evaluate(evidence, criteria) -> dict` with:

```json
{"checks": [{"id": "stable-check", "status": "pass",
  "reason": "Evidence-based explanation", "evidence_refs": []}],
 "metrics": {}, "critical_violations": []}
```

Check statuses: pass, fail, unavailable. Missing evidence must never pass.
Each check should cite source record Refs when present. A producer verdict or
script exit code alone is not correctness. No model judge is enabled. Semantic
claims beyond deterministic labels remain explicitly human_review_required.

Normalized evidence interface:

```json
{"variant_id":"valid", "entrypoint":"single_cc",
 "execution":{"launched":true,"terminal":true,"status":"completed"},
 "records":[{"kind":"gate-decision","ref":{"id":"...","sha256":"..."},
             "record":{"actual":"original product fields"}}],
 "artifacts":{"safe/original/path.txt":"bounded original UTF-8 text"},
 "module_observations":{}}
```

`records` carries original validated product records, not case-generated
claims. `module_observations` is reserved for protected E2/E3/RSI exports and
read-only projections independently joined to original records; don't accept
unbound booleans claiming correct enforcement. Read owning product contracts,
current sidecar adapters, and archived cases for actual record field names.
Write README interface requirements for any additional projection required;
the parent must implement/validate it or report the dependent check unavailable.

Source authority: repository AGENTS.md; approved QA/BENCHMARK_REQUIREMENTS.md
v0.12; QA/BENCHMARK_INTERFACE_CONTRACT.md v0.5 is proposed and must be reconciled
with maintained architecture/product contracts. Reuse research_sidecar clients,
existing private evaluation/custodian paths, gate and identity checks. Plain
research prompts cannot stand in for isolated module tests. Unsupported/missing
bindings produce explicit BLOCKED outcomes, never a mock performance result.

Every authored fixture is DEVELOPMENT material; held-out status requires
independent custody/review. No modifying the app or repairing scored artifacts
to force a pass. Each case's self-tests are labeled oracle unit tests only.
