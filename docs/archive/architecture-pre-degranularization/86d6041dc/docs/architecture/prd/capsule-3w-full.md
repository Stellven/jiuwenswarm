# 3.W Capability Capsule (full version)

**Draft for review.** CC's answer to section 3.W of the PRD template. The short answer to each section comes first. The appendices hold the terms, the five verdicts, the POC confinement gap, the full blacklist and what could come next. Item-by-item design detail is in the repo design pages listed in Appendix F.

- **Where it comes from.** This is drawn from the Capability Capsule (CC) design in the jiuwenswarm repo, branch `ai4r_main_branch`, folder `docs/architecture/`.
- **Proposed items.** Items marked *proposed* are CC design choices not yet written into the schema pages.
- **Draft schemas.** Every schema page there is still a draft, so names can still change before code is built against them.
- **Repo version.** There is a shorter version with links to the design pages: `docs/architecture/prd/capsule-3w.md`.

**In one paragraph.** A capability capsule is one capability the system can run, with a contract that says what it takes, gives, needs, changes and promises. Every field is already in the schema, but M1 checks only what the first working pipeline needs. The rest is accepted and stored, and switched on later without rewriting any capsule. So everything under "not in M1" below is deferred to keep M1 on schedule, not dropped. Two things are permanent: the capsule layer never chooses models, and the system never changes model weights.

---

## 3.W.1 Capability Capsule Definition & Assembly

**Definition & Expectation:** Define the capsule's contract, metadata, dependencies, resources, and executable entry points.

**Whitelist (M1 Scope)**

- **One contract per capsule.** Each capsule has a machine-checked contract, `capsule.json`. A readable `make_capsule.md` is generated from it, so the two never disagree.
- **What the contract states:**
  - what the capsule takes and gives, typed, as strict JSON;
  - how every output is checked;
  - what it calls;
  - what it may change;
  - how long a call may take;
  - whether it may ask a person;
  - what RSI (recursive self-improvement) may change.
- **Code is pinned by hash.** Code that changed after testing does not load.
- **Three kinds of capsule:** code tools, Markdown skills a model follows, and shared prompt text.
- **The capsules:** the seven from PRD 4.1, plus a code-only benchmark runner and three operators (proposed). The sciencediscovery prompts and rubrics are copied into each capsule.
- **An author kit** checks a capsule before it is submitted.
- **The PRD's contract experiment:** the same pipeline, run with and without per-capsule contracts.

**Blacklist (Excluded from M1)**

- **Other capsule kinds:** MCP tools, remote A2A agents, sub-agents, agent capsules (including the generalist), and capsules built from other capsules.
- **Importing** tools and skills from outside the repo.
- **Per-capsule installation:** package installs, secrets, and resource limits other than time.
- **Declared failure modes, retries and quality targets.**
- **Calls that block waiting for a person.**
- **Autonomous capsule generation.**
- **Permanent:** model choice in the capsule layer.

**Dependencies**

- **sciencediscovery:** the six skills being ported.
- **deepsearch repo:** DeepSearch and CodeSearch, for the operators.
- **Model Routing (Xiaoyang):** the Codex CLI adapter.
- **Verifier (Ramika):** the acceptance-rule format and the verifier's rubric.
- **Requirement Compilation:** the Research Brief schema.

*Where this is defined in the repo: [Appendix F](#appendix-f-where-each-part-is-defined).*

---

## 3.W.2 Capsule Governance, Certification & Registry Management

**Definition & Expectation:** Validate, certify, register, version, publish, suspend, deprecate, and audit capsules.

**Whitelist (M1 Scope)**

- **Validate.** Admission is the only way into the library, for hand-written capsules and RSI versions alike. It:
  - checks the contract;
  - confirms the files are the ones submitted;
  - applies the rules;
  - runs the tests;
  - records a decision, with reasons.
- **Certify.** One trust level, *provisional*: the capsule's own tests pass.
- **Register.** The library stores code by hash, and writes every record once.
- **Version.** Any change is a new version with a new admission. Old versions are kept.
- **Suspend, deprecate, retire, revoke, roll back.** A person does each one with a command, and the reason is recorded.
- **Audit.** Every admission and every call is recorded.
- **Judging at admission.** The verifier judges the other capsules' judged checks at admission, but never its own.

**Blacklist (Excluded from M1)**

- **Higher trust:** a *certified* level, based on hidden tests written by someone else. Also the *exempt* level.
- **The automatic librarian:** drift detection, quality measurement, security revocation.
- **Publishing** to a store, and signing capsules.
- **Isolated verification** of capsules from outside.
- **Screening sets of capsules** that fail together.
- **Uninstalling.**

**Dependencies**

- **Capsule authors:** the test cases.
- **Verifier (Ramika):** the verifier admitted first.
- **RSI (Saurav):** new versions.
- **RSI data foundation (Suraj):** the fixtures.
- **Verifier fine-tuning (James):** new judge versions.
- **agent-core:** its key-value store.

*Where this is defined in the repo: [Appendix F](#appendix-f-where-each-part-is-defined).*

---

## 3.W.3 Capability Discovery, Scoring & Selection

**Definition & Expectation:** Find and rank eligible capsules by compatibility, policy, quality, cost, and performance.

**Whitelist (M1 Scope)**

- **No search and no ranking.** The Default DAG names the capsule at each node.
- **Eligibility is checked when each run starts.** Each capsule must be:
  - admitted and current;
  - unchanged since admission;
  - type-compatible with its neighbours.

  A verifier that RSI could change is refused.
- **Contracts are ready for selection.** They already carry everything selection will read, so adding selection later rewrites no capsule.
- **A read-only catalogue of admitted capsules** for Planner Phase 2 (proposed).

**Blacklist (Excluded from M1)**

- **Finding capsules:** search and retrieval, including through Symphony.
- **Choosing among them:**
  - ranking by quality, cost or speed;
  - dynamic selection on the main path;
  - chaining by type;
  - picking older versions.
- **Filling gaps** when no capsule fits.
- **Permanent:** selecting models.

**Dependencies**

- **The Default DAG script** (Planner Phase 1).
- **Planner Phase 2:** the catalogue.
- **Later:** Symphony, and cost data from Model Routing.

*Where this is defined in the repo: [Appendix F](#appendix-f-where-each-part-is-defined).*

---

## 3.W.4 Capsule Invocation & Composition

**Definition & Expectation:** Execute capsules with governed inputs and compose compatible capsules into reusable capabilities.

**Whitelist (M1 Scope)**

- **One runner.** One CC runner runs every capsule call, as Swarmflow's backend.
- **Before each call** it checks the code's hash, the inputs and the preconditions.
- **Pinned calls only.** A capsule can call only what it pinned at admission. Operators run under their caller's pin.
- **Recording.** Every output and every call is recorded.
- **Time budgets.** Each call has a time budget. A capsule that runs too long is kept apart from a runtime that hangs, so blame lands on the right party.
- **The PRD's Stage Evidence Bundle** is built from these records.
- **The two-tier gate.** Code checks first; the verifier's judgement comes second.
- **Five verdicts,** mapped from the gate's decision (proposed; needs Ramika's agreement).
- **Composition is chaining,** with a gate between every pair of capsules.

**Blacklist (Excluded from M1)**

- **Composites:** capsules made of capsules (A-B).
- **Fusion (AB):** rewriting a proven chain into one capsule.
- **Merged versions** and the composer.
- **Spatiotemporal composability:** installing or removing capsules while a run is going.
- **Retries and repair loops.**
- **Token and money budgets.**
- **Sandboxing.**
- **Duplicate-call skipping.**
- **Calls that block waiting for a person.**

**Dependencies**

- **Harness:** Swarmflow.
- **Model Routing (Xiaoyang):** the Codex CLI adapter.
- **Verifier (Ramika):** tier 2 and the verdicts.
- **The Default DAG script:** it halts the run on a failed gate.
- **deepsearch:** DeepSearch and CodeSearch, including any API keys they need.

**Known gap.** Code that the POC step runs is not confined at M1, for files or network, until a sandbox is added.

*Detail: [Appendix B](#appendix-b-the-five-verdicts) (the five verdicts), [Appendix C](#appendix-c-poc-confinement) (POC confinement).*

---

## 3.W.5 Capability Capsule Evolution & Version Promotion

**Definition & Expectation:** Improve capsules from runtime evidence, validate candidates, and promote or roll back versions.

**Whitelist (M1 Scope)**

- **RSI only where the author allows it.** Each capsule says whether RSI may build new versions, and lists exactly which parts it may change. Nothing else can change.
- **The verifier never evolves.**
- **Every run leaves records,** which become RSI's sample fixtures.
- **RSI versions pass the same admission,** plus rules that check the version only changed what was allowed.
- **A person activates each new version.** A person rolls back by returning to an earlier version.

**Blacklist (Excluded from M1)**

- **Automatic promotion,** and RSI on live runs.
- **Building new capsules** from gaps.
- **Automatic dependency updates.**
- **Hidden tests** at admission.
- **Drift monitoring.**
- **Evolving the whole workflow.**
- **Permanent:** changing model weights.

**Dependencies**

- **RSI (Saurav):** a separate branch.
- **RSI data foundation (Suraj).**
- **Verifier fine-tuning (James).**
- **The librarian command,** for activations and rollbacks.
- **PRD section 2's Integration Gate.**

*Where this is defined in the repo: [Appendix F](#appendix-f-where-each-part-is-defined).*

---

## Open points

1. **The capsule count.** PRD 4.1 lists six workflow capsules plus the verifier. The kickoff says "5 workflow + 1 verifier". This answer follows PRD 4.1.
2. **The five-verdict mapping** needs the Verifier's agreement (Appendix E).
3. **Differs from the PRD: token ceilings.** PRD 4.3 wants token budget ceilings in tier 1. The Codex runtime reports no token usage, so M1 gates on time only.
4. **Differs from the PRD: the contract experiment.** The PRD says it decides "if manual schemas are required". Here it measures what per-capsule contracts add, because the Verifier and RSI both read the contracts.
5. **POC confinement.** Executed POC code is not confined until a sandbox or Code Mode is used ([Appendix C](#appendix-c-poc-confinement)).
6. **Blocking human interaction.** It waits until `human_session` can take a reply on the Codex runtime.

---

# Appendices

## Appendix A. Terms

| Term | Meaning |
|---|---|
| CC | Capability Capsule: the capsule schema and the tools that serve it |
| RSI | recursive self-improvement: code that builds new capsule versions from evidence |
| Declaration | a capsule's machine-checked contract, `capsule.json` |
| `make_capsule.md` | the readable form of the Declaration, generated from it |
| operator | a tool capsule that wraps an outside service, such as DeepSearch |
| admission | the only way a capsule enters the library |
| library | the store of admitted capsules and their records |
| Candidate | a submission to admission: the Declaration, its files and its tests |
| Verdict | admission's decision on one version |
| level | how a version was tested: `provisional` (its own tests pass), `certified` (tests someone else wrote also pass), `exempt` (untestable in advance) |
| Standing | which version of a capsule name is current, and its state |
| librarian | the tool that moves Standings after admission |
| epoch | one version of the policy: the rules, defaults and registries a Verdict or run pins |
| freeze | the step at run start that pins every node's capsule |
| Binding | the pin that makes one capsule version one node of a run |
| hot path | a live run, as opposed to admission or offline work |
| Observation | the record of one call |
| Artifact | one value, such as an output |
| gate | the check after a node. Its **fold** turns the check results into one decision |
| Verification | the gate's record of one output's checks |
| Finding | something learned later: a gap, drift, a measurement |
| sealed suite | tests a builder cannot see, which return only pass or fail |
| checked / unchecked | whether M1 requires and tests a field. Unchecked fields are stored but not relied on |

## Appendix B. The five verdicts

*Proposed; needs the Verifier's (Ramika's) agreement.*

**How the gate decides.** The gate runs two tiers and folds the results into one decision: `pass`, `fail` or `blocked`.

- **Tier 1** is code: the capsule's own checks, plus checks that the call ended normally and within its time budget.
- **Tier 2** is the verifier's judgement on the acceptance criteria, and runs only if tier 1 passes.

**The five verdicts are derived from that decision.** The only extra inputs are whether an output carries caveats (`issues`), and who owns the reason a call stopped.

| Verdict | When | The run |
|---|---|---|
| `PASS` | the decision is `pass`, and no output carries caveats | continues |
| `PASS_WITH_KNOWN_LIMITATIONS` | the decision is `pass`, and an output carries caveats | continues; the caveats go into the report's limitations |
| `FAIL` | the decision is `fail`: a check failed on the output | halts |
| `ENVIRONMENT_BLOCKED` | the decision is `blocked`, and the reason is owned by the runtime (it was unavailable or hung) | halts |
| `ESCALATE_TO_HUMAN` | any other `blocked`: a capsule crash, a refused call, or a check the judge could not decide | halts |

**Blame lands on the right party.**

- **A capsule's own fault is never "environment blocked".** A crash, or a capsule running past its own time budget (`BUDGET_EXCEEDED`), is the capsule's fault.
- **Only a runtime outage or hang (`TIMEOUT`) counts as the environment's.**

**Who owns what (proposed).** CC supplies the checks, the records and the fold. The Verifier owns the tier 2 rubrics and these verdicts.

**Halting.** The Default DAG script halts the run on any of the three halting verdicts, and opens `human_session` where that is available. On the Codex runtime the run stops and shows the failure.

## Appendix C. POC confinement

**The gap.** Code that the POC step generates and then runs is not confined at M1: it can reach any file or network the host allows.

**Why.**

- **The permission rail never runs.** The Codex runtime skips jiuwenswarm's permission rail, so on this runtime a capsule's declared effects are enforced only by the CC runner and a sandbox.
- **There is no sandbox in M1.**
- **What the runner can still do:** refuse file paths for the calls that go through `op.workspace_io`. Code that `benchmark_runner` launches as a process does not go through it.

**What closes it.** Running that code in the jiuwenbox sandbox (files, network, resources), or in a Code Mode worktree.

**What we ask.** Accept this gap for M1, stated openly, or say which of the two to schedule.

## Appendix D. The full blacklist

Everything below is in the schema or the tools list, and deferred to keep M1 on schedule.

**Capsule kinds and reach**

- MCP tools, remote A2A agents, sub-agents, agent templates (the generalist), composite capsules.
- Remote capsules pinned by endpoint.
- Importing skills, tools and MCP servers from hubs and repos.
- Per-capsule package installs and lockfiles, start-up config, secrets, and every resource limit except time.

**Contracts**

- Declared failure modes, and the retries and fallbacks built on them.
- Quality targets.
- Namespaces, owners, tags and licences.

**Trust and governance**

- The `certified` level, sealed test suites and negative-control tests.
- The `exempt` level.
- The automatic librarian: drift detection, automatic suspension, quality and cost measurement, judge calibration, and comparing declared effects with observed ones.
- A dependency watcher, advisory feeds and automatic security revocation.
- Publishing to a store (Agentic Hub), signing, attestation, and re-admitting capsules from other stores.
- The isolated verification sandbox.
- Screening capsule sets that fail together.
- Uninstalling capsules and undoing their effects.

**Selection**

- A selection index, the Symphony provider, and skill-taxonomy retrieval.
- Ranking by measured quality, cost, latency or pass rate.
- Dynamic selection on the main path (Cluster Mode, Leader Agent, Symphony `plan()`).
- Chaining by port type.
- Gap handling and the generalist fallback.
- Choosing older versions.
- Per-call-site trust requirements.
- Planning-time precondition filtering.

**Invocation and composition**

- Composite capsules (A-B), fusion (AB), merged versions, the composer, and nesting.
- Spatiotemporal composability: installing and uninstalling during a run, resolving what capsules provide and need at run time, and undoing a removed capsule's effects.
- Retries, fallbacks and repair loops.
- Token and money budgets.
- Sandboxed execution.
- Skipping duplicate idempotent calls.
- Calls that block waiting for a person.
- Per-call-site overlays and role-based binding.

**Evolution**

- `submit`-level RSI, and any automatic promotion or rollback.
- RSI on live runs.
- Building new capsules from gaps.
- RSI re-pinning dependencies.
- Blocking RSI copies of capsules.
- Sealed fixtures at admission.
- Drift and quality monitoring.
- Evolving the whole workflow (meta-RSI).

**Permanent**

- Model selection in the capsule layer.
- Changing model weights.

## Appendix E. What could be added next

None of these changes an M1 capsule.

**Trust and governance**

- **`certified` level:** sealed suites written by someone other than the builder, negative controls, and a way to submit sealed suites to admission.
- **The automatic librarian:** measured pass rate, time and cost per version; drift detection; judge calibration; an exploration quota for inactive capsules.
- **Declared against observed:** a tool that compares declared effects with what a call actually touched, and revokes a capsule on a breach.
- **Security:** a dependency watcher and a shared advisory feed that withdraw vulnerable versions at once, along with everything that pins them.

**Reach**

- **Importer:** draft contracts for skills from hubs, MCP servers (one capsule per tool) and A2A agents, confirmed by a person.
- **Isolated verification in jiuwenbox:** install dependencies, inject secrets, enforce resources and network. This also closes the POC confinement gap.
- **Store:** publishing capsules with their contracts and Verdicts to the Agentic Hub. A receiving system re-admits them under its own policy.
- **The generalist:** per-harness generalist capsules at `exempt` level for steps no capsule fits, each leaving a gap record for RSI.

**Selection and planning**

- **A selection index and Symphony provider:** filter strictly by ports, effects and preconditions first, then rank by measured quality and cost.
- **Planner Phase 2 on the main path,** once it beats the Default DAG on the same fixtures.

**Composition**

- **Composites and fusion:** the composer proposes A-B from call pairs that recur and pass. A person approves each one, and it is tested as one block. A proven block may later be fused into one code item.
- **Screening capsule sets:** rank risky pairs from their contracts, then confirm them in a sandbox.
- **Spatiotemporal composability:** installing and uninstalling capsules during long research runs.

**Runs and RSI**

- **Declared failure modes,** with retries and fallbacks, and idempotent de-duplication.
- **RSI growth:** building new capsules from recurring gaps; dependency re-pins guided by each dependency's purpose; `submit`-level RSI once the baseline is stable.
- **Token and money budgets,** once the adapter reports usage.
- **Blocking human interaction,** once `human_session` has a reply path.

## Appendix F. Where each part is defined

All paths are in the jiuwenswarm repo under `docs/architecture/`, branch `ai4r_main_branch`.

| Topic | Page |
|---|---|
| What a capsule is | `capsule/capsule.md` |
| Every Declaration field | `capsule/fields.md` |
| What M1 checks | `capsule/stages.md` |
| `make_capsule.md` | `capsule/make-capsule.md` |
| Library and admission | `capsule/library.md` |
| Trust levels | `capsule/trust.md` |
| RSI | `capsule/rsi.md` |
| Composition | `capsule/composition.md` |
| Permissions | `capsule/permissions.md` |
| Tools, and which tool checks each field | `capsule/tools.md` |
| Schema checks and guards | `capsule/guards.md` |
| Records, policy and reason codes | `schemas/` |
| PRD pushback | `prd/prd-review.md` |
