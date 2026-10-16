# Routing acceptance scenarios

`Tier 2 · Part of: [Model routing](model-routing.md) · Serves: Standard`

These package-owned scenarios preserve A01 to A40. RTR-1 to RTR-8 govern the platform boundary. Calibration and benchmark scenarios apply only to their declared evaluation profiles; the optional selection ablation is outside the M1 default. Router integration and verification status are reported separately from the PRD core gate. These are expected outcomes, not completed tests.

| ID | Scenario | Observable pass condition |
|---|---|---|
| A01 | Domain/category and inventory publication | Only the eight CS/ML task categories and the package qualification inventory: exactly 12 E + 12 T rows; tools never become executor candidates. |
| A02 | Published identity without real access | Source-qualified entry remains disabled/unmeasured until exact endpoint/adapter/license/resource tests pass |
| A03 | Native versus requested/API profiles | Exact `gpt-6.1-sol` benchmark config retained; required Codex CLI adapter is distinct and limitation explicit |
| A04 | Given Capsule missing/schema/pin/binding invalid | Specific error before model calls; no Capsule discovery/default/substitution or chat fall-through |
| A05 | Task/input/policy aliases forged | `BOUND_CONTEXT_MISMATCH`; bound objective/input/profile controls task and selector summary |
| A06 | Current M1 static bindings | The exact admitted Capsule snapshot and frozen plan assignments are preserved for both static and planned runs; routing never selects a Capsule or plans the DAG. |
| A07 | Typed tool or optional selector enters E pool | Rejected from executor candidates/fallback; deterministic checks/simulators are not extra models |
| A08 | Capability/context/tool/schema incompatibility | Exact hard exclusion and source; no provider-native structured-output inference from JSON ports alone |
| A09 | Host inventory absent or stale | Test/repeat does not start without actual refreshed host/readiness evidence and manifest correlation |
| A10 | Memory/GPU/architecture/dependency unavailable | Attributable readiness block; available shared GB10 capacity and declared dependency limits enforced; no undeclared host substitution. |
| A11 | Zero or one compatible model | Zero compatible models returns NoRoute and the bridge records the Codex fallback. A singleton still obeys the development quality/coverage rule; only selection calls are skipped. |
| A12 | Default multi-model choice | Frozen development scope/quality criterion used; minimum supported complete expected cost and deterministic tie-break; zero selector calls |
| A13 | Development coverage missing | Declared compatible baseline or `PROFILE_COVERAGE_MISSING`; no invented quality/tier/difficulty from brand/size |
| A14 | Optional selector unauthorized/invalid/timed out | Zero call when ineligible; otherwise at most one audited call, eligible IDs only and one permitted original-set router alternate model |
| A15 | Shared context or selected model fails preflight | Invalid protected Capsule pins or bound context returns IntegrityFault and halts the node. Other router blocks return NoRoute. A model-specific alternate is allowed once before freeze within the original eligible set; preserve initial and final choices. |
| A16 | Duplicate/changed/crashed routing | Atomic claim before side effect; duplicate reuse/in-progress, changed fingerprint conflict, no cross-user or uncertain-call replay |
| A17 | Frozen dispatch invalid or concurrent | One dispatch owner; final native predicates/capability/authority pass before call-start/send; no model switch after freeze |
| A18 | Audit unavailable | Router audit failure returns NoRoute/AUDIT_UNAVAILABLE for the Codex fallback. Bridge route or call-start persistence failure starts no call and halts the node; no provider dispatch occurs inside the router. |
| A19 | Failed or telemetry-missing call | All outcomes retained, actual versus estimated/unavailable distinguished; unknown is not zero |
| A20 | Complete execution expense | Worker/verifier/selector/actual permitted planning/fallback/tool costs included; calibration/authoring/RSI separate; initial/final route distinct |
| A21 | Public pass@N/pricing used as local quality | Public scope retained as advisory; no measured cheap-tier, one-attempt, whole-task latency or savings claim inferred |
| A22 | Private calibration context requested by agent | Protected access blocked; runtime sees development aggregates and ordinary task only |
| A23 | Real RT06 calibration and repeats | Same pinned contracts/data/tools/budgets/eligible oracle; frozen criterion, tier/deployment results/uncertainty/costs before scored run |
| A24 | No qualifying tier or uncertain calibration | Quality outcomes retained; difficulty/regret unresolved with exact coverage denominator, never dropped |
| A25 | Cheaper insufficient tier, missing initial choice or negative gap | Preserve exact RT07 denominators, missing-selection coverage and null initial tier; report insufficient route/actual failure separately; negative gap cannot count as quality-preserving improvement |
| A26 | Unreliable monetary data | Exact savings/regret unavailable; labeled time/call proxy separate from observed money |
| A27 | Model-judged scoring/calibration | Independent two-reviewer labels and pinned judge; estimate and one-sided 95% upper false-pass bound <0.45 overall/every scored family before inclusion |
| A28 | Ineligible mandatory scoring judge | Affected full score unavailable; no check omission/renormalization; report judged share and mandatory dependence |
| A29 | Router-only paired comparison | Same Capsules/DAG/verifier/inputs/tools/budget/hardware; exact fixed baseline versus routed; profile/pool frozen and order randomized |
| A30 | Module attribution | Router comparison freezes RSI/improver; RSI comparison freezes router/model; no-Capsule control is separately authorized harness work |
| A31 | Mechanical versus semantic checking | Mandatory mechanical failure prevents verifier call; producer/selector cannot assign favorable criteria |
| A32 | Persisted release and negative result | Only exact advancing gate/artifacts release; valid negative result accepted; unsupported success or stale subject blocked |
| A33 | Expected-halt versus productive populations | Correct fault halt accuracy separate from feasible full completion; retain all launched failures/timeouts/blocks |
| A34 | S07 four variants | Lower cost, difficult/verifier, compatibility and endpoint-fault coverage with private empirical difficulty and regret |
| A35 | Fast pilot/sample limits | Minimum variants/repeats plus mandatory threat coverage; paired/clustering-aware uncertainty; unresolved claims inconclusive |
| A36 | Real duration profiles | Actual meaningful 2-/4-/10-hour CS/ML work, checkpoints/drift/budgets/terminal evidence; accelerated/idle time gives no duration claim |
| A37 | M1 interruption | Retain failure/effects, no silent repair/replay/resume; new run cannot replace original denominator |
| A38 | RSI/promotion | Required screening scope, protected checks/query limits and lineage; later human activation, no automatic pool/Capsule promotion |
| A39 | Version/configuration change | Requalification for changed model/parser/precision/head/contract/profile; active runs keep original pins |
| A40 | Benchmark review | Real endpoint/hardware qualification, scoring eligibility and benchmark evidence are required for release claims; documentation checks and drafted cases establish no runtime PASS. |
