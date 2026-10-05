---
type: review
status: draft
version: 1
owner: muk
sources: [../../product/SOURCE_FREEZE.md, ../../product/prd-m1-full-2026-10-02.txt, ../../product/prd-m1-rsi-full.md, ../system/handoff.md, ../system/deployment.md, ../system/model-auth.md, ../system/benchmark-export.md, ../system/experiments.md, ../system/records.md, ../capsule/fixture-oracle.md, ../capsule/toolchain.md]
tags: [review, handoff, security, m1]
---

# Fresh final architecture review, 2026-10-03

Independent review of the current frozen sources and the Docker, authentication, HTTP, experiment, RSI and coding-handoff boundaries. This review changes no product contracts or implementation. Findings below describe the inspected revision; the release owner must verify corrections and record their dispositions before handoff.

## Assessment

The seven coder questions now have named owner pages, proposed code locations, callable interfaces, persistence/cancellation rules and failure-injection surfaces. The Docker modular monolith is an explicit deployment amendment in SOURCE_FREEZE and decision R10, so the older container deferral is not a current blocker. Internal credential, fixture and generated-code custody remains separate within the one deployable. Public service schemas and generated capsule payload schemas have distinct owners. The benchmark adapter requalifies intake, preserves request identity, forbids implicit restart and retrieves evidence by authorized manifest membership.

The architecture distinguishes defined, checked and runtime-validated. Unexecuted Docker Desktop/kernel/GPU probes, native terminal integration and pinned device-login availability are downstream validation obligations, not reasons by themselves to reject this documentation. Concrete handoff gaps remain below.

## Findings requiring disposition

### F1 — Freeze must resolve the frozen library snapshot

`types/run-plan.md` defines library_snapshot_sha256 as the immutable snapshot used to resolve capabilities and dependencies. `system/planner.md` validates exact snapshot versions but subsequently says freeze re-resolves dependencies. `capsule/toolchain.md` M03 steps 1–2 still resolve current Standing. An activation between validation and freeze can therefore execute another implementation while the run records the earlier reviewed snapshot.

Resolve every work/verifier/dependency version from the pinned snapshot, validate its admission evidence, and explicitly define any revoked-version refusal. Do not silently substitute a current alias. This satisfies frozen PRD 1.4 contract-bound execution, 4.6.2 binding and 5.6.5 reproducibility.

Independent case: validate snapshot A, activate alias B, then freeze A. Expected: exact A pins or an explicit refusal; zero dispatches on refusal, never B under A's snapshot hash.

### F2 — Launcher recipe omits the required source_text handoff

`m1/pipeline.md` requirement requires intake and source_text, and makes extraction/IntentIR ordinary preparation modules. `capsule/toolchain.md` M01 step 7 still passes only intake in args.inputs. Its build-order example still admits research.compile_intent and runs intent then requirement. The canonical producer recipe cannot initialize the current eight-stage plan as written.

Update the launcher sequence to publish the required source_text and its exact ref before freeze/dispatch; use the same preparation for CLI and benchmark HTTP. Replace the outdated first-slice example with the current capsule inventory. Frozen PRD 3.1–3.2 and 6.5 require a usable intake-to-Brief boundary.

Independent case: text-only and document-backed intake each produce the complete launcher input mapping; missing extraction evidence or source_text commit failure yields zero requirement invocations.

### F3 — Restore the frozen all-three RSI fixture rule and planted corpus

The frozen RSI source, `docs/product/prd-m1-rsi-full.md` §3.Y.1 line 75, says a model-backed fixture passes only if all three executions pass. `capsule/fixture-oracle.md` and `capsule/rsi-engine.md` specify k=3 and paired counts but omit this aggregation rule. Majority voting or counting executions as fixtures changes wins/losses, headroom and final evidence. The same source §3.Y.5 line 309 requires at least ten known-bad and three known-good planted children; the V1–V23 suite does not explicitly preserve that corpus minimum.

State the all-three rule in the oracle score owner and add the planted-corpus requirement. No new owner decision or scoring algorithm is needed. Frozen master PRD 4.4.8–4.4.10 and the selected RSI owner source supply these acceptance obligations.

Independent cases: one failure among three makes that fixture fail; pairing remains per fixture; an insufficient planted corpus cannot claim the required acceptance suite complete. Keep every per-case result private.

### F4 — Capability-disable ablation needs a typed missing-output rule

`system/experiments.md` and services-v1 allow disable actions for capability, semantic_verifier and deterministic_gate. They now give Gate-off its own experimental evidence/advance authority. They do not specify how disabling a producer supplies its successor's mandatory typed input or whether the experimental run stops at that missing output. Replacement actions preserve ports, but disable has no replacement hash.

Define a fail-closed disable contract: reject a disabled producer required by a retained successor, or require an explicitly pinned existing input/substitution and provenance. Do not let missing output become an invented successful artifact. Frozen PRD 5.6.5 permits controlled ablation while preserving explicit deviations; 2.5 and the typed runner contracts forbid manufactured empirical evidence.

Independent case: disable hypothesis while retaining POC. Expected is a documented pre-dispatch rejection or exact preregistered admitted substitution; never an absent blueprint accepted as success. Also test multiple disabled components and failed experimental-advance publication.

## Correction observed during review

The initially inspected Gate-off path attempted normal Verification entries with NOT_RUN despite the record's pass/fail/unknown check enum, and completed lifecycle required production release authority. The author revised experiments/nodes/records during review to use experimental_gate_evidence, nullable verification_ref and separate experimental advancement. This is the appropriate ownership separation. Release checks must confirm services-v1, generated consumers and lifecycle completion agree with that revised shape. A production invocation must reject that authority; a failed experimental evidence/advance write must cause zero successor invocations.

## Authentication source check

Local `codex_subscription/transport.py` explicitly pins 0.144.4, sets a dedicated CODEX_HOME, owns inherited stdio, restricts tools and has `_claim_profile`; `service.py` exposes account/read, login/start, cancel, completed and logout. Its present login/start uses type chatgpt, so the new device-flow adapter is correctly documented as work to add rather than existing support. The architecture places the process-lifetime advisory lock on the persistent auth volume, correcting the cross-container custody requirement independently of the existing root-path lock.

The cited official [authentication guidance](https://learn.chatgpt.com/docs/auth), [account-auth automation guidance](https://learn.chatgpt.com/docs/auth/ci-cd-auth) and [App Server reference](https://learn.chatgpt.com/docs/app-server) were accessible on October 3. The dedicated writable profile and serialized ownership are coherent with the source evidence. Current documentation does not prove the pinned binary/account supports device login, automatic refresh or a particular model; doctor must demonstrate those downstream. Fresh login, cancellation/expiry, cache corruption/refresh interruption, profile contention, stale-seed refusal and secret exclusion have explicit invocation/expected outcomes in model-auth.

## Verified correction recheck

Reread the actual updated owner pages after the release author reported fixes. F1 is resolved by toolchain M03 steps 1–2: snapshot-only resolution, exact planner/freeze snapshot agreement, current revocation may deny but never substitute. Planner now names the alias-activation-between-validation-and-freeze fixture and its expected exact-pin/refusal outcome.

F2 is fully resolved after a second consumer recheck. M01 publishes canonical intake/source_text through ordinary extraction/hints, freezes before run_started, supplies every launcher input and uses Brief-to-Search first integration. Runner's `What the script gets` now carries committed Binding Refs and both intake/source_text ports. Its backend verifies that exact Binding before reading decl_hash or constructing the requirement descriptor; no current alias is resolved. The producer and consumer mappings agree.

F3 is resolved in fixture-oracle's Frozen comparison and score: exactly three calls per model-backed arm; all three must pass; wins/losses/ties use fixture-binary outcomes; one failure out of three fails; at least ten known-bad and three known-good planted variants must be demonstrated before optimization. These match the frozen owner source.

F4 is resolved in experiments and planner: disable is refused when a required successor input or objective output depends on that producer, replacements retain exact typed ports/schema versions, and no synthetic output/substitution/replanning is permitted.

The Gate-off correction is now confirmed in services-v1: both experimental objects are closed; experimental_advance requires gate_evidence_ref and permits null verification_ref; experimental_gate_evidence requires NOT_RUN with null Verification or PARTIAL with a real reference. Experiments keeps the Gate as sole Verification writer. Records permits completed isolated steps with exactly one production release or experimental advance, forbids the latter in production, and requires exact study/profile/Observation validation. Nodes routes the approved experimental authority separately. No skipped check is converted to a passing production Verification.

All four findings are closed by rereading the corrected owning contracts, and no additional evidence-backed design blocker was found in the reviewed packet. The release author reports 345 service checks, 131 payload checks, 20 source-hash checks, 18 seam checks, architecture lint and diff checks passing; these are author-reported mechanical results, not independently executed by this reviewer. This conclusion does not assert exhaustive proof or runtime success. Root owns final release evidence and staging.

## Release boundary

Source hash checks, schema/example/link/graph validation, independent producer/consumer expectations and dispositions for F1–F4 are documentation acceptance. The author/root owns their final recheck and staging. Actual image/profile launch, confinement probes, account/device flow, HTTP recovery, native terminal behavior and private RSI execution remain implementation acceptance. This review reports no executed runtime or security result.

## Final coverage read

Reread `system/boundary-cases.md`, runner's three worked calls and the RSI temporal sequence. The index names invocation owners and expected outcomes across production, offline RSI and isolated experiments; it explicitly describes specified cases, not executed product results. The two final prose corrections are verified: process/model transport failure has process cleanup semantics, while an accepted benchmark HTTP disconnect leaves the run continuing and recoverable by request identity; running RSI proposals precede sealed closing ablations.

The runner examples use local_search, Brief's required intake/source_text and durable nested mechanical Verification. The RSI sequence preserves private Trial → close/finish → custodian final → promotable Candidate → mandatory integrity/admission → explicit activation. These agree with the owning contracts. No additional evidence-backed architecture blocker remains in this final coverage read; unresolved product decisions and unvalidated execution profiles remain the explicit downstream blockers already recorded by the packet. No runtime assertion is added.

## F5 — Model-call scope and private capture: closed

The final targeted read found that environment's former ModelBridgeRequest required a research run_id and public Artifact captures, while ModelCallContext omitted scope. Offline RSI/controller and hidden oracle calls exist under private sessions before any public Candidate. Admission also has candidate/session rather than run identity. The old bridge mapping therefore could not carry these calls without inventing identity or crossing capture custody.

Reread the corrected services-v1 model_call_scope, scoped_capture_ref, private_model_capture, model_bridge_request and model_bridge_result definitions. The four closed discriminated scopes are run, admission, rsi_controller and oracle. They reject mixed identities; private oracle scope binds quota request, Trial, case call, arm and repeat. Requests require reserved obs_id/turn; turn captures and completed replies enforce the scope's public_artifact/rsi_private/oracle_private namespace. Cancel/status use separate management request identities targeting an existing turn. Record hashes and underlying content hashes retain distinct meanings.

Environment and storage authorize each scope through its owner reservation, fixed pins, capability and private/public capture writer. Private capture metadata binds scope/request/obs/turn/role/content hash/size/sealing; the bridge waits for durable capture before complete and does not automatically replay uncertain calls. Oracle bytes and refs cannot enter public store retrieval, events, StageContext, proposer replies or benchmark export. Runner carries exact ModelCallScope and nullable capsule identity; native conversation identity derives from canonical scope hash plus request/obs/turn. Oracle and seams explicitly keep private Trial execution separate from public Candidate/admission. Routing remains run-only; non-run calls use their fixed pinned model.

The last stale observability prose and diagram were reread after correction. They now describe scoped model requests and distinguish turn cancel/status from pre-call AuthProvider/doctor management. The release author reports executing 419 service checks, including all four scopes, namespace/mixed-identity refusals and management request shapes; the reviewer read their validator cases but did not execute that validation. F5 is closed by source verification, with no remaining evidence-backed architecture blocker in this targeted read. Actual IPC authorization, private capture durability, provider metadata handling and runtime isolation remain implementation validation obligations; no runtime success is claimed.
