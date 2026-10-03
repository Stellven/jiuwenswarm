# Authored public service contracts

The service schema also owns normalized routing request/decision, seed-availability records, benchmark HTTP response envelopes, trusted local auth management, preregistered ablation studies and experimental evidence/advance Artifacts. Authentication management is not exposed through benchmark endpoints. [Model auth](../system/model-auth.md) and [track isolation](../system/experiments.md) own those APIs' authority and behavior.

The retry_profile definition owns the closed M1 RetryProfile wire object; [profile meanings](../schemas/profiles.md) and [lifecycle](../system/lifecycle.md) require max_execution_retries=0 for every effect class. Existing reserved-result retrieval is not another execution.

Reproducible documentation checks: `python docs/architecture/_tools/validate_services.py` validates constructed positive and negative service fixtures; `python docs/architecture/_tools/validate_handoff.py` checks frozen source hashes, all generated payload examples and independently derived producer/consumer packets. These scripts use Python/jsonschema in the documentation environment. They do not invoke research, authenticate Codex, resolve real records or validate process security.

These JSON Schemas own service wire shapes; linked design pages own behavior, effects and field meanings. This folder contains documentation contracts, not implementation. Payload/CC record schemas remain generated under `exports/schemas/` from their owning tables. Never maintain a second payload field list here.

[`services-v1.schema.json`](services-v1.schema.json) defines planner request/proposal/validation, experiment request/profile, benchmark request/handle/export and shared failure response. Select the named `$defs` entry for the endpoint. `Ref` uses the exact id/hash encoding owned by [common](../schemas/common.md); semantic reference existence, scope and content hashes require boundary checks beyond JSON Schema.

Planner `plan` imports the generated run_plan schema, and benchmark `task` imports intake. Draft edits change docs and fixtures together; handoff releases pin this file's hash. Shape changes after release require a new service schema revision or explicit adapter. `ext` is the only open extension surface. [Planner](../system/planner.md), [experiments](../system/experiments.md), and [benchmark export](../system/benchmark-export.md) own the APIs.

Service errors project CC Reason into code/message/evidence_refs; the adapter resolves the original EvidenceRefs and includes only public committed references. Codes are validated against the owning API/error registry in addition to structural schema checks. This projection cannot drop required private evidence from the canonical stored reason; it limits what the public reply discloses.
