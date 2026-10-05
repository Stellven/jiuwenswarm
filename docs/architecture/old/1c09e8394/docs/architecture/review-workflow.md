---
type: design
status: draft
owner: muk
provides: [architecture.review_workflow]
consumes: []
depends_on: []
tags: [review, process, evidence]
---

# Bounded agent review workflow

Spend review effort on changed semantics and uncertainty. Mechanical checks find structural defects first; fresh agents inspect bounded evidence next; the coordinator verifies and resolves findings. Repeated model agreement does not establish correctness. [Policies](policies.md) remain the authority for source precedence and releases; this page owns review allocation and evidence freshness.

## Prepare one packet per connected change

1. Choose a baseline commit and name the behavior being changed. Separate independent changes into separate packets.
2. Use the [authority index](authority.md) to select owning definitions and affected producers, consumers, Gates, records, run plans, diagrams, examples and configuration. Include exact frozen PRD clauses and relevant adopted decisions/precedents. Identify prior open findings by ID.
3. Run relevant documentation checks. Fix structural failures before agent review. Record command, working directory, candidate revision, exit status and actual output. A skip or unavailable renderer stays explicit.
4. Generate a packet with [review_packet.py](_tools/review_packet.py). It captures the selected diff, full-file hashes, source excerpts and unselected-change inventory. The frozen-source authority page and manifest are automatically pinned. It does **not** infer complete impact or PRD scope. The first reviewer confirms scope and requests missing inputs.
5. Keep each packet small enough for a reviewer to read its complete selected contract and exact clauses. Split by seam or journey when necessary; do not truncate security, recovery or source context to meet a token target.

Example, from repository root; choose actual source lines before running:

```text
python docs/architecture/_tools/review_packet.py create --base BASE_COMMIT --include docs/architecture/system/planner.md --impact docs/architecture/capsule/toolchain.md --source docs/product/prd-m1-full-2026-10-02.txt#LSTART-LEND --focus "Planner validation to freeze" --out REVIEW_DIRECTORY/planner.json
python docs/architecture/_tools/review_packet.py check REVIEW_DIRECTORY/planner.json
```

The source range placeholder must be replaced with real line numbers. Keep exploratory packets outside the repository. A selected durable packet or finding record may live in `reviews/`; received sources remain unchanged. Generated snapshots are evidence at a revision, never another authority for contracts. The JSON is the checked packet; the Markdown companion is a reading aid. Review the JSON directly or verify the companion against it. Hash every artifact actually given to a reviewer when recording a review result. Existing output filenames are refused; choose a new revision filename. Hash the packet itself when recording a review result. A packet containing incomplete impact is not a handoff acceptance record.

## Assign narrow, fresh roles

Use the least costly available agent that can read the packet accurately. Model availability and prices change; no model name or price is a policy requirement. A single agent may perform several explicitly separated roles when a change is small, except the two blind seam derivations. Escalation uses a fresh capable reviewer rather than repeated cheap approvals. Maximum routine concurrency is two reviewers, leaving capacity for the coordinator and independent work.

| Role | Question and required output | When |
|---|---|---|
| Contract | Derive exact inputs, outputs, required files, references, errors, identities and effects from its assigned side. Flag absent semantics. | Every changed shared contract |
| Failure | Try lost writes, duplicates, timeouts, cancellation, restart, quota corruption, trust-boundary access and authority bypass. Cite expected defense and unrun validation hook. | Every connected batch; all security/persistence changes |
| Scope | Trace changed behavior to exact frozen clauses and whitelist. Identify conflicts, unsupported claims and leaked experimental behavior. | Changed product behavior or track allocation |
| Coder | Answer the seven [coder questions](system/coder-requirements.md) using linked owners. List decisions an implementer would otherwise have to invent. | Every connected batch and handoff |

For a changed seam, give producer and consumer reviewers only their respective owner and relevant shared contracts/source clauses. Do not provide the other derivation or an expected answer. Compare their recorded fixtures through the [canary](PROCESS.md#the-canary). Disagreement is a documentation finding; never edit a blind fixture merely to match. A reviewer cannot replace the source by its memory of a library.

Common reviewer instruction:

```text
Confirm the packet's impact set. Read the selected owners and exact source clauses.
Review only your assigned role; follow links needed to establish a finding.
Return: scope read, missing inputs, findings with evidence, and residual uncertainty.
Each finding: ID; severity; source/contract path and line; expected versus specified
behavior; consequence; affected boundary; proposed correction; validation hook.
Use BLOCKER for contradictory authority/security/scope or an unbuildable boundary;
MAJOR for unspecified required behavior; MINOR for nonsemantic clarity/navigation.
Do not claim runtime tests passed. Do not rewrite contracts or approve unrelated files.
```

## Escalate uncertainty, not document size

Escalate any disputed source interpretation, shared security/credential boundary, durable release authority, hidden-fixture custody, or correction affecting multiple tracks. Also escalate if a cheap reviewer cannot establish the exact evidence or two blind derivations disagree after the first correction. The coordinator can fix obvious source-verified defects directly; a second agent rereads the affected claim after a semantic fix.

Record why escalation happened and its bounded question. There is no fixed retry loop or approval count. If evidence is still absent, retain a named design/implementation obligation and constrain only the affected acceptance claim. A larger context is appropriate when impact crosses many owners; low cost must not hide omitted consumers.

## Resolve and retain evidence

Each finding receives `fixed`, `rejected-with-source`, or `open-obligation`, with rationale, affected owners and exact evidence. Rejection requires a cited contract or source, not author preference. An open obligation names its owner, consequence and required validation. Link existing obligation IDs rather than duplicate their normative definitions.

Record packet SHA-256, baseline/candidate commit, selected input hashes, role, source ranges actually read, commands actually run, findings and dispositions. A working-tree candidate additionally needs the packet's byte pins. Reviewer findings and disposition can share one record. Short human briefs include only material choices, unresolved risk and extent reviewed.

Before reusing evidence, run packet freshness checking. Changed selected bytes or diff invalidate that packet. A new unrelated commit alone does not invalidate unchanged selected input evidence. A source baseline change invalidates its dependent interpretation even when a quoted paragraph looks identical. The coordinator checks newly changed paths against the impact set and transitive authority links: a hash check cannot detect an omitted new consumer. Regenerate packets for affected evidence; keep old evidence as historical, not current. Documentation hashes cannot prove semantic completeness or runtime behavior.

## Cadence and journey rotation

| Point | Required review |
|---|---|
| Every edit | Relevant mechanical checks; full suite before a coherent commit |
| Shared contract change | Impact confirmation, blind producer/consumer derivations and seam canary |
| Connected batch | Failure and coder review; scope review when product behavior changes |
| Every third connected batch, or shared authority/security change | One fresh journey below; rotate so all five are covered |
| Coding handoff release | Fresh review of all five journeys at the release pins, plus source coverage and outstanding obligations |

The five journeys are production intake through delivery; halt/durable Gate/recovery; offline RSI through admission and manual activation; isolated planner validation through dispatch; benchmark invocation through correlated export. Use [stories](stories/README.md), [temporal diagrams](system/temporal.md) and the [atlas](system/diagram-atlas.md) as entry points, then read the actual owners. A previous journey review is reusable only for unchanged inputs and scope. Local packet success is not full M1 acceptance.

## Mechanical check entry points

From repository root:

```text
python docs/architecture/_tools/arch_lint.py --check
python docs/architecture/_tools/validate_services.py
python docs/architecture/_tools/validate_handoff.py
python docs/architecture/_tools/validate_stories.py
python docs/architecture/_tools/validate_library.py
git diff --check
```

Regenerate authored views with `arch_lint.py` before `--check` when needed. Mermaid parsing/rendering is a separate documentation check; record the renderer version and files actually rendered. These tools establish specific structural properties, not execution of failure scenarios. Actual product tests belong to the coding process.

## Borrowed practice and replacement boundary

The focused producer/consumer method borrows [Pact's consumer/provider contract pattern](https://docs.pact.io/). The finding/diff workflow borrows [Google's small-change review guidance](https://google.github.io/eng-practices/review/developer/small-cls.html): a bounded coherent change is easier to review and fix. Neither source validates an AI reviewer or guarantees maximum integrity. Packet selection and freshness are local engineering controls. Replace the script with CI change-impact tooling when module dependencies are machine-readable; retain canonical ownership, blind derivation and honest evidence semantics.
