# CC packages, verification units and Strata methodology intake

Source review:2026-11-14; upstream `muxite-tools-20261114` at `e897ff47a89a2f0e07db1e63b399d45abf0cc02e`, kept read-only. [Exact source receipts](UPSTREAM-CC-ALIGNMENT-SOURCE-PINS.json) pin the current AGENTS, transfer instructions, four maintained protocol documents and consulted delivery notes. A clean upstream checkout establishes document identity, not implementation correctness or hardware qualification.

## Current authority and local alignment

The maintained November4 reading route is `CC Protocols/README.md`, `FORMAT.md`, `USAGE.md`, `IMPLEMENTATION.md`. Earlier `CC and Strata delivery` workshop notes are explicitly proposed/historical inputs; their registry/image-envelope details must not be silently restored as current core requirements. Local branch AGENTS forbids restoring M1 machinery. User instructions and the current branch amendment retain precedence over historical notebook descriptions.

| Surface | Upstream meaning | Consequence for this factory |
|---|---|---|
| Capsule/package | Versioned bundle containing one capabilities map and/or passive materials | A package may contain several related domain operations; package identity and verification unit need not equal one function |
| Capability | Selected finite action or served native interface | Sibling needs/effects never become a union grant |
| Method/skill/reference | Passive included material | Can carry experimental methodology, verification-unit definitions and interpretation limits without inventing an executable |
| Binding | Native, pinned image, host-registered delegate | Packaging is independent of operation lifetime and verification strength |
| Portable identity | Existing canonical release index and exact included bytes | Reuse `Host.prepare/release/describe/material`; do not implement a competing release digest or package registry |
| Semantic checking | Optional selected advisory checks; explicitly required checks are a caller acceptance policy | A new qualification capability consumes evidence by request; it must not make every ordinary tool call run a verifier |
| Product delivery | Separately identified engine/source/image/configuration product | A useful factory CC can produce a Strata engine containing zero CCs |
| Hardware/science evidence | Actual loaded product/generation, frozen workload and independent observations | Declaration, synthetic replay, live-agent integration, engine execution and scientifically accepted gain remain distinct claims |

The local runner already supports multiple capabilities, passive materials, immutable releases, keyed receipts, delegates and opt-in checking. Its local material `kind` and capability `kind` fields are recorded extensions, not a reason to copy upstream schemas over local ones. The historical F25 comparison used an older source pin; this receipt updates source knowledge without changing protocol bytes.

## Useful packages span Strata modules

Package domain operations by a coherent verification boundary. Examples are `strata.prompt` (inspect effective chunk, transform one chunk setting, interpret prompt/decode evidence), `strata.expert_io` (inspect demand readiness, estimate bounded read budgets, interpret wasted reads), `strata.routing` (inspect routed expert sets, compare held-out prediction, enforce authoritative full routing), `strata.cpu` (inspect worker allocation and scheduling evidence), and `strata.speculation` (inspect offered/accepted draft cost and verify target obligations). These are candidate domain groupings, not new protocol categories or evidence that all operations are implemented.

Methodologies cross package boundaries: source applicability, profiler interpretation, one-variable experimental design, reproducible build, load verification, quality/performance analysis and negative-result delivery. A common qualifier can verify identity and explicit bounded checks; domain packages still own their meaningful checks. Growing this domain toolbox serves inference research. Optimizing the qualification mechanism itself is outside the current objective.

## Proposed verification-unit material and qualification CC

Use an ordinary included JSON material to declare a verification unit for a sealed package. A unit binds an ID, the selected existing capability IDs, explicit checker IDs and claim scope. It can group several operations that share invariants while remaining an ordinary domain profile. The package digest already seals that material. Do not add mandatory core fields or a registry service.

Proposed `factory.cc_qualification` package capabilities:

1. `inspect_package`: read a release already prepared by the existing host; return package/member/material identities and declared selected authority. Verify bytes using existing release handling. Never prepare by executing package code or install dependencies.
2. `verify_unit`: load the unit's hashed material, select one allowlisted in-process domain check, and apply it only to saved scoped evidence. Record package release, unit material identity, checker code identity, evidence references, observed result and limitations. Never import a checker from the package, evaluate arbitrary expressions, run commands, fetch URLs or start GPU work.
3. `assess_admission`: compare requested release/capabilities/verification units and retained results against an explicit caller/operator policy. Return eligibility and concrete missing/failed conditions. This is an assessment record, not a session grant, installation, execution, publication or automatic promotion.

Keep inputs bounded and declarative. A checker allowlist is local function dispatch within this capability implementation, not an extensible registry or arbitrary-code hook. Missing evidence is unknown/inconclusive. Unknown checker IDs fail closed. Assessments bind the same exact release and unit; checks from another package version cannot qualify a successor.

## Tiered evidence without accidental certification

| Claim boundary | Required evidence | Cannot establish |
|---|---|---|
| Package identity | Existing host validates declaration, sealed included files and material identity | Runtime availability, safe native execution or scientific correctness |
| Bounded domain invariant | Explicit named in-process check over scoped saved evidence; include negative cases | Arbitrary code safety, completeness of observability or hardware transfer |
| Runtime qualification | Saved independently collected loaded binary/config/generation and cleanup/resource evidence | A speed/quality improvement merely from successful execution |
| Scientific claim | Frozen same-day comparable experiment, correctness, engagement, native metrics and uncertainty | Broad task generalization or automatic promotion |

These are claim-specific requirements, not an automatic ladder. A policy may ask for identity only, a pure-transform invariant, or a specific runtime/scientific evidence set. Several units can be required for a multi-operation package; checks apply to the relevant capabilities and cannot authorize unselected siblings.

The first implementation should use existing saved native protocol/configuration evidence and pure profile-transform receipts. New runtime checks can be added only when their source and evidence interpretation are explicit. A synthetic verifier test proves checker behavior on those cases. A native CC receipt proves the wrapper ran. Root's actual Jiuwen session must separately demonstrate discovery, useful invocation, a measured module experiment, evidence review and a next decision. A negative optimization outcome can still complete that real improvement loop.

## Implementation boundary and status

Root approved the bounded domain intake design. `jiuwenswarm/factory/cc_qualification.py` and its three-capability package now implement this configuration-check boundary; targeted development tests now pass; actual live-agent research use remains separate pending evidence at this writing. The current checker requires the known workbench implementation-file set and binds those file hashes, API routing and checker identity in addition to the package release and unit material. Admission policy is read from operator task constraints. No protocol schema, runner registry, removed M1 path, installation workflow or hardware runtime was changed. Preserve actual native/image/delegate and live-agent evidence separately when the package is exercised.

## Recorded development verification

The qualification/hypothesis/ablation/methodology group passed82tests. Package catalog and declaration-view tests passed20tests, asserting23top-level packages and31catalog entries including8nested components. The updated qualifier-only suite passed17tests, including separate external implementation, checker and API-routing identity invalidations, wrong-task rejection, extra-change/full-expert/static-cache negative cases, sealed-material tampering and refusal to inherit a sibling verification unit. These runs used the existing CPU test container and did not launch an inference engine or execute intake package code. Root separately reports9inference-methodology tests passed, including an actual native CC call, private-evidence denial and claim boundaries. Native wrapper execution is not a live Jiuwen-agent or hardware/scientific pass.

## Concrete package composition and an unscored workflow example

`factory.inference_lab` now groups nine callable methodology operations in one sealed package. `engine.strata_prefill_workbench` groups seven related prompt-module operations; `factory.cc_qualification` groups three explicit intake/verification operations. This is actual declaration/implementation grouping, not a proposal that every function must become a separate capsule.

| Research step | Implemented inference_lab capability | Result boundary |
|---|---|---|
| Read retained observations across engine layers | `diagnose` | Report-backed uncertainties; no causality or gain inferred |
| Choose the smallest useful verification scope | `test_scope` | Advisory obligations for configuration, offline replay, subsystem, integration or recovery claims |
| Record a new source/evidence-based idea | `propose` | Immutable unmeasured hypothesis with applicability, counters and falsification |
| Hold other variables fixed | `ablation` | Design only; existing frozen-template admission controls execution |
| Specify cache/warmup interpretation | `cache_protocol` | Distinguishes process warmup, cache state and storage claims |
| Identify bounded profiling preparation | `profile_plan` | Plan/availability evidence; no engine launch |
| Interpret retained native/profiler artifacts | `analyze_profile` | Instrumentation gaps and phase candidates; traced timings do not score speed |
| Evaluate a routing prediction from saved traces | `evaluate_prediction` | Request-separated causal replay against controls; no inference-speed claim |
| Use a result to choose the next question | `followup` | Next-input proposal; no contract mutation or job submission |

For example, an agent can diagnose retained prompt cost, select `subsystem_performance`/`prefill` with test_scope, and propose a bounded positive-chunk intervention. It then uses the seven-capability prompt workbench's inspect/design/apply/verify_profile operations, saves the actual profile pair, and invokes qualification verify_unit/assess_admission under the operator's selected policy. Existing loop selection/submission and host admission govern the actual experiment; workbench status/result and inference_lab followup close the evidence path. This paragraph describes a possible authorized workflow, not a claim that a live run or beneficial result has occurred.

Future source-derived packages should widen useful Strata interventions: routing/readiness cost models that distinguish critical-path waits from useful overlap; CPU placement or scheduling and native kernel cost crossovers calibrated for GB10 shared DRAM; and prediction policies with causal decision-time inputs, explicit byte budgets and held-out controls. Offline `evaluate_prediction` already implements a bounded analysis method. Engine-integrated learned prediction, automatic placement decisions, new kernels and routing/readiness optimization implementations are not supplied by this qualification package. Each needs source applicability, meaningful negative controls and an appropriately scoped admitted experiment; existing paper results do not establish transfer to this model/hardware.
