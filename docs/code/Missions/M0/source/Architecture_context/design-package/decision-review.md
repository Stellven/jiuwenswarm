# Architecture decisions: contract and reading review

**Human potential; October 8, 2026.** This records choices made to resolve the package audit. Review the reasoning, then the linked definitions. These are selected architecture standards, not demonstrated optimal solutions or runtime passes. Received PRD bytes and D1–D18 retain their authority. Implementation evidence for affected interfaces must be refreshed.

## R1 — Make the executable node boundary exact

**Decision:** add one critical Node Execution Contract schema. Protected binding records admitted CC and dependency pins, typed concrete inputs/outputs, effective per-binding authority and limits, aggregate limits, acceptance/evidence obligations and frozen guard/policy/configuration identities before dispatch. The contract pins a reusable guard profile; its bound check plan points back to the finalized contract. Neither hashes the other recursively.

| Alternative | Benefit | Cost / reason for disposition |
|---|---|---|
| Prose-only node fields | Small reference layer | Existing examples omitted permissions and bindings; independent agents cannot reliably agree |
| Exact node boundary — selected | Makes execution and release inputs compatible; omissions are mechanically detectable | Adds a seventh schema and version maintenance |
| Schema for every runtime object | Broad mechanical coverage | Excess inventory obscures consequential boundaries and constrains replaceable internals |

**Review obligation:** reject missing bindings, unmatched ports, excessive authority, stale scope and missing evidence. A structurally valid contract written by a CC still has no binding authority. [Definition](reference/node-execution.md).

## R2 — Name other shared fields without an exhaustive schema library

**Decision:** keep field contracts for other major records, but name fields, types, requiredness, relationships, owner and failure behavior in one [field catalog](reference/field-catalog.md). Catalog IDs resolve CC ports. Closed required core and namespaced extensions apply. Native specifications realize these contracts consistently; private fields remain private.

| Alternative | Benefit | Cost / reason for disposition |
|---|---|---|
| Information summaries only | Easy to read | Leaves incompatible names, types and missing-output interpretations |
| Named field contracts — selected | Standardizes meaning and shape with limited machinery | Some relationships still need explicit runtime checks |
| Exact schema for every type | Uniform validation | Large maintenance surface without proportional architectural value |

**Consequential choices:** scientific comparison boundaries use named operand/comparator/reference/factor/offset fields, rather than free-form expressions; this supports portable checking but confines M1 to declared simple comparisons and pinned measurement adapters. Readiness prerequisites have individual name/status/reason fields, rather than a string that each client parses differently. RSI profiles explicitly pin adapter, improver and configuration; attempt observations retain the same context. This adds metadata but makes comparable sessions auditable. Invocation usage names tokens/cost and explicit unavailable values: this adds small bookkeeping but prevents absent telemetry being treated as zero or parsed differently.

**Review obligation:** a consumer can identify every mandatory field; no shared port uses an unresolved type. [Other contracts](reference/other-contracts.md) explain semantic obligations. The catalog is authoritative for spelling/type; prose is authoritative for behavior. Disagreement blocks specification until repaired.

## R3 — Show connected artifacts rather than more isolated templates

**Decision:** provide linked synthetic research and RSI examples, including negative science and inactive candidate handling. Complete existing node examples. Teach relationships, not a ready-made scientific result or hidden-suite contents.

| Alternative | Benefit | Cost / reason for disposition |
|---|---|---|
| Many independent templates | Broad field illustration | Conceals incompatible identities and missing evidence chains |
| Few linked paths — selected | Makes producer/consumer compatibility inspectable | A single path cannot cover scientific domains or enforcement mechanisms |
| Executable reference application | Demonstrates implementation | Outside this documentation scope; risks making one algorithm architectural authority |

**Review obligation:** example references and measurements agree; synthetic evidence never claims measured execution or admission authority. [Examples](reference/examples/README.md).

## R4 — Give Target 1 a lawful improvement objective

**Decision:** preserve the helper's fixed sum, required dimensions, stable tie order and Top-1 interface. The frozen referee ranks candidates by passed hidden tests first and paired helper time only at equal pass counts, as §4.4.2 requires. Timing improvement is secondary improvement, never a claim of better scientific selection. All mandatory parent tests, effects and compatibility remain prerequisites. Do not deliberately weaken the parent to manufacture headroom.

| Alternative | Benefit | Cost / reason for disposition |
|---|---|---|
| Change weights or choose more promising opportunities | Larger quality search | Changes fixed Target 1 behavior; belongs to a separately authorized target |
| Passed tests, then paired time — selected | Preserves PRD order; a correct parent can have measured timing headroom | Small helper timing is noisy; calibration may show no eligible improvement |
| Latency as primary score | Direct optimization signal | Conflicts with PRD time-only tie-break rule |

**Policy:** seven paired rounds after five warm-up batches; equal batch workload and fixed host/configuration; use medians of paired batch times. At equal pass counts, a gain must be at least 10% and exceed three times the calibrated relative timing noise. These conservative values are chosen standards, not empirical guarantees. Calibration must demonstrate an attainable stronger planted child before proposals. No demonstrated headroom means BLOCKED, not success or relaxed scoring. Loop feedback remains passed/total/queries-left only. [RSI detail](offline-rsi.md#target-1-scoring-and-headroom).

## R5 — Separate dependency selection from resolution and installation

**Decision:** protected environment preparation supplies a reviewed dependency catalog with exact direct/transitive locks and immutable package hashes. Resource qualification exposes compatible catalog entries. Hypothesis selects the environment; Builder emits that exact selected lock and bounded code. The trusted Stage 3.7 provisioner checks the lock and installs only those bytes in the isolated environment. Generated code never resolves or installs packages.

| Alternative | Benefit | Cost / reason for disposition |
|---|---|---|
| Builder resolves online | Flexible package choice | Violates no discovery/install rule; mutable resolution undermines reproduction |
| Approved complete locks — selected | Feasible sequence with reproducible package identity | New packages require protected preparation before a new run |
| Assume framework names imply a lock | Minimal input | Transitive versions and availability remain undefined |

**Review obligation:** no compatible lock or missing package blocks before scientific execution. Provisioning cannot repair the declaration. Hashes establish identity, not package safety; review and confinement remain necessary. [Deployment ownership](placement.md#dependency-preparation-and-provisioning).

## R6 — Show release and admission authority on the first view

**Decision:** split binder, gate and library admission in the overview. RSI produces an inactive candidate, protected admission evaluates eligibility, and a human changes future selection. Preparation and planning use the same protected checking pattern as research. A dependency-release edge does not create a cyclic research DAG.

**Pros:** readers see authority before opening detailed topics; direct producer-to-library arrows no longer imply admission. **Cons:** the first diagram has more nodes. Keep finer sequences in topic views; don't add internal classes. Review diagram and prose together.

## R7 — Shorten orientation, retain depth where it answers a question

**Decision:** the super-important route is README → system architecture → principles. Put the full-M1 phase summary and bounded next build in that route. Move detailed phase exits and Immediate Plan into the should-read route selected by assignment. Preserve component explanations and the decision history in the second tier. AI reference remains exact; humans review relevant contracts when changing them.

**Pros:** fewer mandatory files, less repeated orientation, clear escalation by question. **Cons:** a human must follow phase links before approving a specific build; shortening alone does not prove comprehension. Err toward retaining purpose, failure, authority and rationale. Existing component explanations remain available rather than replaced by compact summaries.

## R8 — Preserve a fair versioned compression experiment

**Decision:** freeze the original pair, then create a new pair from the repaired full input. Both receive identical contracts, examples, PRD, decisions, exceptions, responsibility/phase tables and assignment boundaries. Compact retains real section headings and essential behavior; its reductions target rationale and repeated explanation. Full retains detailed causal explanations and more views.

**Pros:** corrections do not bias one condition; both inputs can perform well; original results remain attributable. **Cons:** a second pair requires separate identities and inventories. Input size is only an independent variable, not a winner criterion. No implementation trials are run here. [Experiment method](design-method.md#measuring-sufficient-detail).

## Decisions and source amendments

| ID | Current decision | Source disposition |
|---|---|---|
| D1 | Static Phase 1 baseline; bounded direct admitted CC planning in Phase 3 | §§1.3, 4.8, 6.5, 6.12; no live restructuring |
| D2 | Deterministic checks, independent verifier, protected gate | §§1.4, 4.2; replaces optional semantic checking |
| D3 | Protected host owns release; freeze referee assets | §§4.1.5, 4.2.8, 4.4.5 |
| D4 | No automatic repair/replay; blocking outcomes halt | §§1.4, 4.6.4; human correction is new linked work |
| D5 | Separate bounded generative Intent and Requirements CCs, each checked | **Authorized local exception** to §§3.2/4.7 single-generation Brief fallback. Freeze combined budgets; retain non-interactive baseline |
| D6 | One Docker app, Python/TypeScript, SQLite state and artifact files | **Authorized local realization/exception** to source container/native-only and persistence assumptions in §§4.1.4, 4.5, 5.1, 5.2, 5.4. Generated-code confinement remains separately required |
| D7 | Preserve CC concepts with one reconciled current machine contract | §4.1; historical sources are provenance, not competing serialization authorities |
| D8 | Required offline RSI in Phase 2; interfaces precede planner completion | §§1.3, 4.4, 6.11; immediate slice excludes execution |
| D9 | Mandatory evidence fails closed; optional telemetry can be unavailable | §§1.4, 4.2, 4.5, 6.4 |
| D10 | Verifier assesses; gate decides; control plane shows halt/triage | §§4.2, 4.3.4, 4.6.4, 5.3; headless never waits |
| D11 | Optional benchmarker uses ordinary scoped client boundary | §§5.3.1, 5.6.5; no privileged product control |
| D12 | Durable product identity/profile separate from local execution host | §§1.1, 2.3, 5.4; optional cloud profile storage grants no remote execution |
| D13 | Node objective/contract differs from CC invocation | §§1.4, 4.1, 4.2; per-call checking plus node aggregate acceptance |
| D14 | Account for all stages/phases and applicable Phase 3 efforts | §§1.3, 6.12, 6.14; preliminary Leader checks never replace plan acceptance |
| D15 | Independent guard profiles and output-led evidence review | §§1.4, 4.1, 4.2, 5.4; review is assessment, not replacement authorship |
| D16 | Three reading levels; critical schemas and other major field contracts | §§1.7, 6.13 and October 7 user direction; replaces agent-owned competing wire shapes |
| D17 | Intent acceptance requires fidelity **and** usefulness to Requirements | §§3.2.1, 4.7.3, 4.2; topic-only extraction with material missing purpose/result blocks |
| D18 | Readable IRs, decisions and views; raw evidence separate | §§5.1.2, 5.3.1, US05–US17; no mandatory opaque binary decoding |

## Human review priorities

1. Does the explicit node authority match the permissions intended for CCs and verifiers?
2. Is passed-tests-first timing comparison a useful Target 1 demonstration with realistic headroom?
3. Can approved dependency preparation support the intended research cases without runtime discovery?
4. Can a reader locate every M1 responsibility, its failures and phase from the three-document route?

These are review questions about selected decisions, not unresolved behavior or a new coding approval workflow.

## R9 — Resolve the independent review within M1 scope

**Decision:** use named PlanInput/PlanOutput fields for concrete accepted inputs or future predecessor ports. M1 uses one work CC per execution subnode; additional work CCs occupy separate gated subnodes within their declared node. Verifiers remain protected checking assignments. Composite creation/execution, arbitrary capsule member graphs, fusion and merging remain later work.

| Alternative | Benefit | Cost / disposition |
|---|---|---|
| Infer planning ports from unnamed contract inventories | Smaller fields | Cannot represent concrete inputs or resolve future named ports; rejected |
| Named planning ports and one work CC per subnode — selected | Compatible boundaries; directly uses existing checks/gates | More external nodes for additional work; PRD's broader permitted sets unused |
| Internal multi-CC member graph/release contracts | Expresses intra-node composition | Adds deferred composition machinery; rejected for M1 after user scope clarification |

The PRD §§4.1.3–4.1.4 permits one or more admitted CCs per node. This is a bounded realization of the permitted single-CC option, not removal of product obligations or a claim that a new exception was needed. Private helpers remain within the owning CC. The independent review's member-wiring gap is resolved by explicit deferral, not implementation of member graphs.

**Custody:** RSI attempts pin a separate genesis/root and hash profile, avoiding first-attempt self-hashing. A distinct security-clearance record links halted session, violation, authorized actor, remediation and validated guardrail evidence. Keeping clearance separate from activation costs one small field contract but prevents incident recovery granting child eligibility. Optional ports remain optional; source spans use exact UTF-8-decoded code points without CRLF normalization. These close already-required obligations.

Pre-implementation format version remains 1.0.0. The unused experimental revision 3 is invalidated explicitly; no released implementation compatibility or observed runtime success is claimed.

## R10 — Check field suitability and make contracts easy to find

**Decision:** retain exact schemas for the seven consequential boundaries and named field contracts for other shared artifacts. The contract index links every current definition, producer/consumer and available fixture. Field summaries must match their own section, including nested types. CC budget-enforcement keys must exactly match declared limit dimensions; unsupported composite dispatch remains blocked for M1.

| Alternative | Benefit | Cost / disposition |
|---|---|---|
| Require an exact schema and fixture for every internal type | Uniform syntax checks | Expands inventory and obscures consequential architecture; rejected |
| Selected schemas, complete named fields, direct index — selected | Compatible shared boundaries and short reading routes | Relational/semantic obligations still require protected runtime checks |
| Accept arbitrary budget mode maps | Flexible metadata | Missing or unattached modes make enforcement meaning ambiguous; rejected |

This pre-implementation schema clarification preserves version 1.0.0 and the declared budget dimensions; it is not asserted compatible with already generated implementations. Native agreements must reconcile it. A schema can recognize future composite metadata while current admission/binding rejects its execution. The renamed full and compact folders share all current authoritative reference content; frozen historical comparison inputs are unchanged.

**Authority clarification authorized by the user:** the PRD defines requirements as a whole; design interprets them and controls implementation-facing details. Prefer design for implementation conflicts. This does not silently waive product obligations: D5/D6 and any later product departure remain explicit authorized decisions. Both package READMEs state the rule before the reading route.

## R11 — Complete compiler node, subnode vocabulary and Brief compatibility

**User-authorized revision:** Intention Compiler is the whole PRD node; its Intention and Requirements work plus checking/gates cooperate inside it. Success reaches Research_Brief.json. Earlier one-work-CC “nodes” are now subnodes. M1 still defers composite/merged CC creation and arbitrary composition; predefined node structure is allowed.

| Choice | Advantages | Costs / disposition |
|---|---|---|
| Keep Intent-only entrypoint | Smaller build | Repeats the observed missing-Brief failure; rejected as current assignment |
| Whole node with explicit foundations — selected | Matches PRD output and makes required infrastructure discoverable | Larger bounded build; does not claim full Stage 2/M1 completion |
| Only rename diagrams | Small diff | Leaves competing runtime scope and acceptance contracts; rejected |
| Versioned node/subnode scope — selected | Parent obligations and one-CC permissions remain distinct | Breaks earlier generated interfaces; affected evidence requires reconciliation |
| Exact schema for every type | Maximum serialization detail | Adds bloat/private implementation prescription; rejected |
| Field charts, selected critical schemas — selected | Shared meaning and consumers stay precise; agents choose private realization | Requires compatibility checks at implemented public boundaries |

D5 now permits a fixed bounded sequence rather than requiring exactly one generative pass. The selected baseline retains separate Intention/Requirements generations and their independently assigned verifiers; combined budgets are frozen. This is explicitly different from literal §§3.2.1/4.7 one-pass wording. No automatic retry, autonomous clarification or dynamic workflow selection follows from it.

Research Brief 2.0 adds qualified-intake/context/input bindings, fixed research lane and attributed normalized constraints/targets. Protocol defaults remain in Hypothesis. Gate 2.0 names node/subnode scope and permits no-output halt evidence. Subnode Execution Contract 1.0 replaces the old CC-sized Node Execution Contract 1.0; the enclosing node uses a 2.0 field chart. Exact JSON remains limited to critical shared boundaries. Versions are per contract; no implicit compatibility or migration is claimed.

**Review questions:** Does the Brief preserve every product obligation without selecting the scientific solution? Can a faithful but unusable IR block before Requirements? Can a component implementer locate all required foundations and prove Brief release? Does final node acceptance aggregate evidence without giving CCs release authority?
