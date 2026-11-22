# Explicit package verification and scoped eligibility

A CC is a versioned package containing related capabilities and materials. This package exposes three operations: inspect existing release identity; check an explicit domain verification unit; assess selected capability eligibility. Existing host sealing and schemas remain authoritative. No package-supplied code, expression, command or URL is executed/fetched by the checks.

The first supported unit is `profile-single-change`, checker `strata.prefill_profile.v1`, for package `engine.strata_prefill_workbench`. It independently checks baseline256/candidate512, exactly one argument value changed, full six experts, explicit no-draft/static-cache settings, eight CPU threads, host reserve and fixed environment obligations. It does not call the producer's apply or verify_profile implementation. Negative cases should include extra variable changes, expert skipping, adaptive cache, chunk overrides and missing evidence.

The package declares ordinary material `verification_units` pointing to JSON:

```json
{"format":"factory-verification-units/1","units":[{"id":"profile-single-change","capabilities":["apply","verify_profile"],"checker":"strata.prefill_profile.v1","claim":"Configuration invariants only; no runtime benefit claim"}],"implementation_modules":["jiuwenswarm.factory.prefill_workbench","jiuwenswarm.factory.prefill_worker","jiuwenswarm.factory.strata_prefill","jiuwenswarm.factory.strata_components","jiuwenswarm.factory.benchmark","jiuwenswarm.factory.benchmark_worker","jiuwenswarm.factory.benchmark_data","jiuwenswarm.factory.benchmark_analysis","jiuwenswarm.factory.engine_adapters","jiuwenswarm.factory.strata_lab","jiuwenswarm.factory.lab_recorder","jiuwenswarm.factory.lab_lifecycle","jiuwenswarm.factory.targets"]}
```

For this known package/checker, the full fixed implementation-module list is required. Names map to audited local source files; arbitrary modules are never imported. Each verification binds portable release, unit material bytes, current implementation-module hashes, API routing hash and checker module hash. This is known local source identity, not complete interpreter/dependency closure or OS isolation.

Live use:

1. Call workbench inspect/design/apply as appropriate; retain the baseline input and returned candidate profile.
2. Publish a current-task observation through the existing evidence tool with values exactly `{"baseline_profile":BASE,"candidate_profile":CANDIDATE}`. Publication is retention of caller-supplied data, not a measurement.
3. Call `verify_unit` with the exact workbench release, unit ID `profile-single-change` and published evidence ID. A failed result remains saved evidence.
4. Call `assess_admission` with an existing operator policy ID and verification observation IDs. The policy lives in task constraints, not caller tool inputs:

```json
{"cc_qualification":{"policies":[{"id":"prefill-config","release":"SEALED64HEX","capabilities":["apply","verify_profile"],"required_units":["profile-single-change"],"allowed_effects":["process.exec"]}]}}
```

Assessment rechecks current package/source identities and evidence, runs the bounded invariant again, and rejects wrong-task/stale/changed identities. Missing/failed required units or insufficient capability coverage/effect ceilings block eligibility. A successful sibling check cannot qualify submit/status/result automatically. Session authorization, frozen experiment templates, job admission, quiet lease and loaded-product verification remain separate requirements.

The result is eligibility for these selected capabilities under this task policy and these bounded checks. It never grants authority, executes a job, installs dependencies or promotes a package. Configuration checking, real runtime qualification and scientific acceptance remain distinct. Semantic checks stay opt-in for ordinary tools. Scientific negative results can complete a useful research loop.

The separately versioned `strata.prefill_profile.v2` checker supports only `engine.strata_prefill_chunk`'s `apply` capability and requires exactly the local `strata_prefill` and `strata_components` implementation modules. Its sealed unit adds `parameters`: `{"baseline_chunk":256,"candidate_chunks":[512,1024],"allow_fixed_budget":true}`. Candidate chunks must be a nonempty unique subset of512/1024. With opt-in enabled, both profiles may retain the same decimal `DS4_EXPERT_BUDGET_BYTES` from1 through128GiB; insertion, deletion, changes and malformed values fail. The checker preserves the v1 fixed full-six/no-drafting obligations and one-field proof while accepting the declared chunk. This does not establish native fixed-budget support, placement parity or runtime correctness. V1 remains exact256-to512 and excludes this environment extension. Unknown checkers, package identities, backend closures and capability boundaries remain unsupported.
