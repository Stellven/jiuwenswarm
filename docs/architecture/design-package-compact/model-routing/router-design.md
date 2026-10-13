# Model router: maintained component design

**Routing-owner responsibility.** This projection adopts the compatible behavior of the [received v1.8 draft](../sources/model-routing/README.md). The [shared contract](../reference/capsule-model-routing.md) owns cross-component fields. The [catalog](model-catalog.md) separates executors from scientific tools. This component is Phase 3; the Phase 1 Codex adapter remains separately governed.

## Input and authority

The router receives one `RouteRequest` containing `SelectedCapsuleInput` from protected upstream code. Validate the existing declaration schema, exact original-byte pins, finalized node/subnode ownership, one binding, typed accepted inputs, outputs, admission and applicable prerequisites. No library search, unversioned-name resolution, Capsule combination or substitution is permitted.

Only the protected binding or an authenticated exact-reference lookup establishes trust. A client-provided permission object or trust flag is insufficient. `task_type` and domain labels describe work; they come from upstream and agree with the task. Absent labels may be normalized upstream to `general`; explicit unknown labels fail. The component has one Executor type. Protected work/verifier binding labels remain local attribution and profile authorization, never an extra client-controlled `role` field.

## Filter and select

Scan enabled, qualified API executor deployments inside the intersection of Capsule requirements, protected profile, request restrictions and data policy. A credential reference resolves privately; exports never contain secrets. Exclude incompatible modality/tool/explicit native-output capabilities, context/output capacity, disallowed models/families, unsupported access, denied disclosure, substantiated hard-budget failures and sourced blocking deployment state. Retain candidate exclusions with deployment-scoped evidence.

`tool_calling=false` imposes no positive requirement and grants no tools. Omitted or empty declaration family restrictions mean no family requirement; nonempty restrictions narrow compatibility. Profile/request allowlists are authorization constraints: omission adds no restriction, while an explicitly empty effective scope denies all models. JSON ports alone do not require native structured output. Scientific-tool dependencies are not executor candidates. Required capability verification differs from task-quality evidence: unknown comparable quality alone does not exclude an otherwise compatible deployment.

Estimate complete context: system/method instructions, supported overlays, tools/schemas, actual inputs, authorized history and reserved output. Respect declared `min_context` and recheck before each model call. Tokenizer-derived estimates are preferred; disclose conservative fallback estimates and their basis. The owner's 10% margin is a configurable starting proposal.

Zero candidates fails without a Judge or task-model call. One candidate is selected directly. Multiple candidates use at most one separately configured, pinned Judge call, with no retry or recursive selection. Supply bounded permitted task/method descriptions and evidence-backed candidate cards. Public quality, cost and latency observations retain checkpoint, provider, protocol, timestamp and work-unit scope. Missing evidence cannot support a reason. Treat instructions in task text or candidate descriptions as data.

Validate the Judge's closed result: candidate ID, bounded explanation and reason in `DOMAIN_FIT / QUALITY_EVIDENCE / COST_PREFERENCE / LATENCY_PREFERENCE / TIE_BREAK`. Prefer documented task fit, then supplied soft preferences and comparable evidence, then configured priority and ID order. This is not a trained weighted router. A missing Judge permission, disclosure allowance, credential, budget, valid result or endpoint uses only the profile's single compatible fallback. Capsule/binding invalidity and zero compatible candidates cannot be repaired by fallback.

Owner starting configuration proposals are a 20-second Judge deadline, 30-second routing deadline and 1,024 output tokens including provider-counted reasoning. Each remains bounded by protected allowances; none is an SLA or measured performance claim. Deployment-matched tariffs or credible conservative full-chain estimates are required for a configured hard monetary cap. Hypothetical GPU-hour allocations are soft estimates. Account credits are not exact per-call consumption or per-model quota.

## Freeze, dispatch and failure

State sequence: received → validated → filtered → selected (optional single fallback) → preflight → ready → executing → succeeded, failed or outcome_unknown. Pre-execution errors become routing_failed; unexecuted expiry becomes expired. Persist selection and the ready-to-executing transition before task dispatch. Preflight verifies the same binding, endpoint, prerequisites, authority and budget reservations.

Fallback is permitted once before freeze, including when the initial model fails preflight. It must satisfy the original eligible scope and current checks. After a decision is frozen, invalidity terminates that decision; it is never rewritten. Dispatch rechecks current Capsule eligibility and model access. Revocation during execution stops subsequent calls. Optional timing fluctuations alone do not revoke a route.

Use `execution_id` as the routing idempotency key. Equal immutable request identities return the existing record; changed Capsule, input, contract, profile or snapshot identities conflict. Serialize concurrent duplicates to prevent duplicate Judge calls and conflicting decisions. Live remaining-budget checks do not mutate the original snapshot or frozen decision. The suggested 30-second ready validity is a protected configuration proposal; expiry does not invalidate an already executing binding. A new route requires explicit upstream work and new attributable execution/invocation identity.

Do not silently retry a 429, timeout, authentication failure or 5xx. Partial effects and uncertain external-call outcomes remain recorded; never resend automatically after a crash. Disable lower-layer SDK retries and group failover for this profile. Exactly-once external effects are not claimed without provider support.

## Execution adapter and review

The owner module exposes in-process `route`, execution-adapter, call-record and authorized route-query operations. The governed CC runner loads the pinned implementation, authorizes effects and captures outputs. Its bridge consumes the frozen provider binding; an API adapter cannot create another scheduler or choose Capsule methods. Reuse a single `ResolvedModel` DTO privately. The existing `ModelSelection.route_id` identifies a model-group member and is not the routing decision ID. Resolve the explicit final model; never use session defaults or pass a group to automatic failover. API keys stay inside credential resolution.

An upstream-assigned verifier uses its separate read-only Capsule, context and profile. It emits the existing [Verifier Assessment](../reference/checking.md#verifier-assessment) for the exact artifact and returns it to protected checking/gates. A separate engineering-review Capsule may define `approve/request_changes/insufficient_evidence`; that illustrative developer-review format neither replaces runtime assessments nor grants release. Approved test commands, if needed, run only in a disposable authorized sandbox. A prompt is not a permission boundary.

## Evidence and implementation acceptance

Persist route attempts, frozen decisions, model calls and scientific-tool jobs with distinct purposes. A routing Judge is overhead, not task execution or semantic verification. Its call is authorized directly by the pinned profile and recorded before the final task route exists; no recursive Judge routing is introduced. Correlate it with the route attempt and subject Capsule, then link the final decision through append-only evidence.

Record requested/effective identity and its basis, provider request ID, configuration revision, timestamps, outcome, usage and explicit unavailable reasons. Scientific tools retain their own request/sample/compute accounting. Partial costs stay partial; unknown is not zero. Internal correlation metadata stays local instead of being inserted into provider prompts solely for telemetry. Redact explanations and restrict access to authorized audiences.

The shared scenario matrix defines required integration behavior. The routing owner must demonstrate registry qualification, selection/fallback, provider binding and audit; the runner owner must demonstrate protected export, dispatch, budget and checking integration under the native TASK/interface agreement. Documentation examples and mocks establish no runtime acceptance. Owner milestone dates remain proposed forecasts; release follows actual prerequisite and verification evidence.
