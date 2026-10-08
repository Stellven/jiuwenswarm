# Capability Capsule schema, v2.10b (merged, 2026-09-24)

**v2.10b: a capsule says what it promises to keep stable** (Muk, 2026-09-24). §4.9b adds
`evolution.frozen[]`, the parts of the contract a revision may not move, which is where RSI reads its
search space. `evolution.notes_for_builder[]` carries the author's advisory note to a reviser, never as
evidence and never gating. Both are framed as a promise rather than as a permission. And
`coverage.undeclared_notes`, specified since v2.3 and never implemented, is now in the artifact.
`contract_hash` excludes the two advisory sections, so editing a note cannot void a suite.


**v2.10a: a capsule points at code, it never holds it** (Muk, 2026-09-23, after the workshop). This
closes the question §0.2 held open earlier the same day. A capsule is a **leaf** carrying
`identity.carrier {ref, sha256}`, the id of *where the code is* and the hash that id must resolve
to, or a **composite** carrying `members[]` and a DAG. Never both, and `capsule.schema.json`
now enforces it. A hat on a head: the hash is how a changed head is noticed.

**Also v2.10a**: §0.7a records where the shape-and-policy split comes from. **C++26 contract
assertions** put `pre` and `post` on the *declaration* and leave the evaluation semantic
(ignore, observe, enforce, quick-enforce) *implementation-defined*, which is the same division this
schema makes and maps term for term, observe-versus-enforce onto label-versus-block. Verified
2026-09-24 and contested rather than unanimous.

**Also v2.10a**: the ceiling gains its compositional argument (§4.10), the judging rule is stated
exactly (§4.10b), the capability tree gains the justification everyone already accepts (§4.13a), and
`guarantees.checks[]` in `capsule.schema.json` was **missing eight of the fields §3.1 specifies** while
refusing unknown ones, so a check written to spec was rejected. Fixed, same class as the `wiring` bug.

**Also v2.10: composition is specified, and the normative artifact repaired.** §4.10a says how one capsule
goes inside another: `members[]` names them by hash, `wiring[] {from, to}` connects ports (including the
composite's own `inputs.`/`outputs.` boundary), `structure` orders them. `wiring` was specified in §3.x and
checked by the gate in §4.10, but was **missing from `capsule.schema.json`**, whose top-level
`additionalProperties: false` meant a conforming composite was rejected. The field is now in the artifact and
`examples/composite-block.json` carries real boundary wiring.

**v2.9 changes: one schema progressively activated, every stage applies capabilities, overlap and merge,
and quality as a rate** (Muk, 2026-09-23).

- **The schema is whole from day one; what is staged is how much of it is enforced** (§0.7). A field is
  declared from the start and sits inert until the component that reads it exists, so nothing is
  redesigned later and a system with parts missing still works demonstrably.
- **Every stage applies capabilities** (§0.5, rewritten). The unit is the *work a stage does*, not the
  stage. The workflow does not become a capsule; what is never a capsule is anything that **decides**.
- **Assess versus decide** (§4.10). A capsule may produce an assessment; it may never be the thing that
  decides. Enforced by the existing protected-components rule on write access, not by classifying intent.
- **Overlap and merge** (§4.9a). Recurring, high-quality structures become merged capsules with derived
  Declarations and pinned members. A, B and A-B all remain. **There is no split operation.**
- **Quality is a rate over a window** (§4.5c), with a declared minimum number of observations before a
  quality claim means anything. Block only for safety; label for quality.


**v2.8 changes: start extra small, block only for safety, label for quality** (Muk, 2026-09-22). v2.7 was strict in a
way that would have starved AI4Research: research outputs are mostly semantic, so they can only be judged, and an
unmeasured judge blocked provisional capsules and generalists from those steps. v2.8 resolves it:

- **Block only for safety; label for quality** (invariant 14). A run is refused only for identity or safety: a hash
  mismatch, a protected write, an effect outside the declaration, an irreversible effect without approval, a revoked
  or security-suspect capsule. Everything about quality (the level, how good the judge is) changes what a result is
  worth, recorded on each claim, not whether it may run.
- **Judges: calibrate early, label always** (§4.5c). Every judge gates as before. Its standing (`unmeasured`,
  `calibrated`, `measured`) decides what a pass supports. Spot checks on a small share of passes calibrate judges
  through normal use, so nothing waits for full certification.
- **Softer admission and binding.** Provisional capsules and generalists may bind to judged steps; their claims carry
  the reason they are not fully supported. A provisional postcondition may be judged. A person confirms only writes,
  deletes, emissions, executions and external effects; declared reads are accepted as proposed.
- **An extra small library** (§4.13). M1 seeds about ten capsules; generalists cover the rest; the library grows by
  recurrence, and the first option for a recurring gap is to import an existing capability.

**v2.7 changes: node gates, suites that travel with the lineage, and exempt generalists** (Muk, 2026-09-22):

- **Node gates** (§4.5b). The gate a node must pass is compiled at the freeze from three parts, each written by a
  different party: the step's acceptance (from the request), the bound capsule's declared checks, and checks by
  artifact type. `gate_verdicts[]` name the part each came from, so a failure is charged to the right party. An
  admitted capsule should pass its own part; the step's part tests what this request needs, which it never declared.
- **Suites travel with the lineage** (§3.2, §4.7). The Verdict lists every suite a hash was checked with. A child
  inherits its parent's suites: RSI reads the visible ones, adds its own cases, and sees sealed ones only as pass or
  fail. A child is better when it passes all of the parent's suites, its own new cases and a fresh held-out addition.
- **The capability tree** (§4.13a). Every Declaration ever submitted stays a node, rejected ones included, linked by
  `lineage.parent` (and optional `co_parents`). CC stores and exposes per node what its own records guarantee, and
  marks as optional what only the builder can supply. **RSI's selection policy picks where to branch; CC never ranks
  nodes for it.**
- **`guarantees.exempt`** (§3.1, §4.14). An exempt capsule is outside the library's verification policies (no declared
  job to test, never certified), but every plan gate still applies. It replaces the `generalist` flag. **Several
  generalists may exist**, for example a Codex generalist and a Claude generalist. Verdict level `exempt` is the lowest.

**v2.6 changes: authors answer for state and undo** (Muk, 2026-09-22). Capabilities are not inherently stateless: an
MCP server over a live database changes state, undo is not guaranteed, and removing a bad capability does not clean a
context it already shaped. The author declares all of this up front, and CC checks the declaration against what it
observes (invariant 13):

- **`changes.effect_class`**, declared by the author: `pure`, `idempotent`, `compensable` or `irreversible`. The gate
  checks it against the per-effect declarations, and verification tests it (§3.1, §4.5a).
- **External state.** Effects on anything outside the capsule layer's boundary (`ext:` resources) can only be
  `compensate` or `emission`, never `inverse` or `scoped`. Per effect, `idempotent` is declared.
- **Composition keys off the class** (§4.5a): retries, fan-out, exploration and speculative runs are allowed only as
  far as the class allows; irreversible effects need supported inputs, no automatic retry, and a named person or a
  pre-approving run contract.
- **Remote bodies.** A remote capability's advertised interface is fingerprinted at admission and compared at every
  dispatch (`remote_fingerprint`, `REMOTE_CHANGED`).
- **Context taint.** A revoked hash taints every invocation it shared a context with, not only those it was primary in.
- **No numeric trust score.** A mismatch is a typed reason and a Standing move, recorded against the builder.

**v2.5 changes: a capsule holds no task; plan assembly, scheduling and multiplicity** (Muk, 2026-09-22; code read at
AI4Research `b0bf165f9`):

- **A Declaration describes a capability, never a use** (invariant 12). `applies_to` is removed: the task type lives
  only on the Plan step. `summary` may not name stages, workflows, tasks, other capsules or tools. Today's
  `task_types`, `requires_after`, named worker operators and position prose are mapped on import (§4.2).
- **Where each part lives in openJiuwen** (§4.17a, v2.7): the Declaration is a Card, an invocation is a Turn or item,
  generalists are harness providers, approvals are the permission engine's `ASK`.
- **Plan assembly and scheduling** (§4.3a): who writes the plan, who matches supply to it, who schedules, and what CC
  supplies to each, keeping today's workflow.
- **Real multiplicity** (§0.6): one Binding per step with `bound[]` roles (primary, context, dependency) instead of one
  `decl_hash` and `co_loaded[]`; the Binding's `invocations[]` log, one entry per actual run (fan-out items, attempts,
  fallbacks); fan-out on the Plan step (`over`, `gather`); composite members keyed by role, so one Declaration may
  appear twice. Still six records.

**v2.4 changes: a reference by function** (§0). No mechanism changed. §0 adds, for the a-to-g rebuild of the report
and deck:

- the four verbs (pick, verify, improve, remove) and the records each reads;
- the Declaration's fields, marked required or optional;
- how each kind of capability is held (carrier and hashes);
- the deterministic selection criteria, listed;
- the schema's position in the workflow's stages.

**v2.3 changes: a consistency pass after review** (`../verify/V10-overnight-20260922.md` §4). Each rule is now stated
once, and every section agrees with it:

- **Standing** has one writer, the librarian. Findings move it only toward less authority (§4.8).
- **The generalist** binds only where every output has a deterministic or reference gate, and has its own conformance
  suite (§4.14). v2.7 and v2.8 widened this: there may be several generalists, and a calibrated judge counts as a gate.
- **The freeze** checks the sprint's snapshot, so an admission during planning no longer aborts a sprint (§4.4).
- **Contracts** get a `contract_hash`, so a suite written before the code is bound to the contract it tests (§3.1).
- **Versions.** One rule for new versions, and one running-plan policy per retirement reason (§4.7).
- **Records.** The run contract is recorded in the plan; claims carry a status; Findings carry a visibility (§3.4-3.6).
- **Unattended runs** cover every place a person was asked (§4.15). There is also an exploration quota for
  inactive capsules (§4.3).
- **Restored from the 2026-09-15 report:**
  - provenance fields and rejection reasons;
  - negative controls;
  - practice feedback before the gate.

**v2.2 changes.** v2.1 had lost the self-improvement design of the 2026-09-15 capsule report (tundle `AI4Research
Capability Capsule Report - Muk.docx`, §4 and App. G). v2.2 restores it:

- **Goals.** Self-improvement is named as a goal the schema serves (§1).
- **Three clocks around one library:** hot, cold and audit (§4.0).
- **The generalist capsule,** and the run-contract flags that control it (§3.4, §4.14).
- **The cold path** as separated roles: build decision, suite author, implementation, gate (§4.12).
- **Updates.** Monotone versions, and the ways to update the library (§4.7), import first since v2.8.
- **Protection.** Protected components (§4.1), the audit loop (§4.13), scheduling by write scope (§4.4) and unattended
  runs (§4.15).
- **Dependencies.** Unpinned dependencies need a written purpose (§4.11).

**v2.1 changes** (evidence in `DERIVATION.md`). Each item comes from reading jiuwenswarm and the agent-core RSI code
at `02b37f47f` and `e23806c1`:

- **Overlays.** Experience layers, TTSE guidance and hot-loaded packages are hashed and pinned like the body (§3.1,
  §3.5, §4.19).
- **RSI.** RSI's own gate counts as builder evidence, never as a Verdict. RSI's activation pointer becomes the
  Standing, written by the librarian (§4.12, §4.18).
- **Composites.** A composite is gated by its members' Standing (§4.10), as jiuwenswarm's SkillPacks are, but by
  hash. Team skills stay out of v1: their Leader plans, which puts them above the ceiling (§4.10).
- **Fallbacks.** A Binding carries pre-approved fallbacks, as AI4Research's freeze already does (§3.5, §4.5).
- **Planning-time predicates.** Whether a predicate can be evaluated at planning is computed per step from the upstream
  steps' declared effects (§4.3).
- **Enforcement.** A tool-level enforcement rail follows agent-core's `VerificationRail` (§4.5).
- **Imports.** New rules for model fields and summaries (§4.2).
- **Open topics.** Concurrency and migration rules (§4.7).

Status: **draft for the workshop.** This version merges two independent designs:

- **v1.6** (`../SCHEMA.md`): a hashed manifest and the records that name it, built through seven review rounds.
- **The independent version** (`../alt/SCHEMA-ALT.md`): drafted by an agent that never saw v1.6, organised as records
  split by who writes them.

It takes the independent version's structure and keeps every mechanism from both. Both originals stay unchanged, for
comparison (`../alt/COMPARISON.md`). Where a part comes mainly from one of them, it is marked **[v1.6]** or **[ind]**.

**Keys.** `code` = checked in source: agent-core `e23806c1` (with Symphony), skillhub `236f56c`, ScienceDiscovery
`cee1974`, the old AI4Research harness at `stellven/AI4Research/harness/lib` (`b0bf165f9`). **(design)** = a decision
the cited work motivates but does not prove. Papers by arXiv id and page; every cited paper has been read in full, and
the page-level numbers are in `../verify/PAPER-LEDGER.md` and `../alt/READ-LOG.md`.

---

## 0. Reference by function and position (v2.4)

**Capability Capsule makes capabilities easier to pick, verify, improve and remove.** This section is the reference
for those four verbs: which fields each reads, how the capability itself is held, what selection filters on, and where
in the AI4Research workflow the schema acts. The records and mechanisms that implement it follow in §1 to §4. The
reasons, organised by function, are in `../kb/functions/`.

| Verb | What makes it easier | Records and sections |
|---|---|---|
| **Pick** | inputs and outputs are known; deterministic eligibility on declared requirements removes most capsules before a model chooses among the rest | Declaration `ports`, `needs`, `changes.effects`; Verdict level; Standing; composition Findings (§3, §4.3) |
| **Verify** | everything is declared, so every check has a target; hashes prove the checked thing is the run thing; observed effects are compared with declared ones | `checks`, `acceptance`, `effects`; `decl_hash`, `contract_hash`, body hashes; Verdict (§3.1, §3.2, §4.1, §4.5) |
| **Improve** | performance and trust are logged by others than the builder; lineage and hashes give parents and children; gaps feed builds | Binding invocations, `use_outcome` and gap Findings, Verdict `contribution`, Standing history, `lineage` (§3.3, §3.5, §3.6, §4.0, §4.12-4.14) |
| **Remove** | spatiotemporal composability: needs, provided services and each effect's undo are declared, so capsules can be replaced, reverted or removed without breaking dependents | `injects`, `provides`, reversibility, Standing moves, step identity in each invocation (§4.6-4.10) |

### 0.1 The Declaration's fields, required and optional

One unified schema for every kind of capability: a required core, and optional parts declared when they apply. Full
definitions in §3.1.

| Section | Field | Required? | What it should be | Read by (verb) |
|---|---|---|---|---|
| identity | `name`, `version_label`, `schema_version` | required | a stable name; free-text version; the schema version it is read under | pick, improve |
| | `kind` | required | tool, mcp, skill, prompt, subagent, agent, composite | pick, verify |
| | `carrier` | required | the agent-core spec it loads through (below) | verify, remove |
| | `body[]` | required | every file, each with its SHA-256; a remote service is pinned by endpoint and version instead | verify |
| | `summary` | required | at most 400 characters; the only prose a model reads when choosing | pick |
| | `load_mode` | required | `invoked` (behind a boundary) or `context_injected` (shares the agent's context) | pick, remove |
| | `lineage` | required: `parent` (empty for a root), `relation`, `builder`; optional: the rest (§4.13a) | parent, relation (supersedes, specialises, rollback_of, migrated_from, composes; `fuses` reserved), `co_parents`, `build_trigger`, `context_capsules`, `diagnosis_inputs`, provenance (generating model, prompt, trajectory), `builder_ref` | improve, remove |
| | `overlays[]` | optional | evolved experience, guidance or packages loaded with it, each hashed | verify |
| ports | `inputs[]`, `outputs[]` | required | each with a type from one versioned vocabulary; each output names the check that validates it | pick, verify |
| needs | `when[]` (preconditions) | required; empty only with a stated reason | predicates `{path, operator, value}`, each with `state_source`, `max_age_s`, what happens when the fact is unknown or its source is down, and a parity check | pick, verify |
| | `external[]` (the capability's own dependencies) | required; may be empty | each pinned (hash, model id and version, endpoint and version, or capsule hash), **or** unpinned with `purpose`, `role` and `contracts` (optional) | improve, remove |
| | `network` | required | none, an allowlist, or open | pick, verify |
| | `resources[]`, `injects[]`, `model` | optional | resources with a mode; services it needs; model constraints (never a model choice) | pick, remove |
| changes | `effect_class` | required | `pure`, `idempotent`, `compensable` or `irreversible`: the author's attestation for the whole capability, checked against its effects (§4.5a) | pick, verify, remove |
| | `effects[]` | required; empty only if it changes nothing | per effect: resource, operation (read, write, create, delete, emit, execute), scope, reversibility (inverse, scoped, compensate, emission), risk | verify, remove |
| | `provides[]`, `invariants[]` | optional | services it installs; invariants, each with a check | remove, verify |
| guarantees | `checks[]`, `acceptance` | required; at least one postcondition | each check: kind (including negative controls), anchor (deterministic, reference, judged), runner hash, author, held out or not, where its signal comes from | verify |
| | `exempt` | optional; only `reason: generalist` in v1 | waives the library's verification policies for a do-anything capsule, which then needs no postcondition of its own; plan gates still apply (§4.14) | pick, verify |
| budget | `per_call`, `enforcement`, `on_exhaust` | required for agents; optional otherwise | limits between calls, and how each is enforced | verify |
| members | `members[]`, `wiring[]` | composites only | members keyed by role, each pinned by hash; one Declaration may fill several roles | remove |
| coverage | `undeclared_notes` | optional | what the builder knowingly leaves out | verify |

Computed by the gate, never written by the builder: `decl_hash` (over everything), `contract_hash` (over everything
but the body), agent-core's runtime flags, a composite's derived needs and changes, `context_cost_tokens`.

### 0.2 What a capsule holds, and what it only points at (v2.10a)

**A capsule never holds code. It points at code, and it pins the hash that pointer must produce.**
Decided by Muk on 2026-09-23, closing the question 0.2 held open earlier that day. The image to keep is
a hat on a head: the capsule is the hat, the code is the head, and the hash is how a changed head is
noticed rather than trusted.

A capsule is therefore one of exactly two shapes, and never both at once:

| | **Leaf** | **Composite** |
|---|---|---|
| what does the work | code this capsule points at | other capsules |
| what the Declaration carries | `identity.carrier {ref, sha256}`, the id of where the code is and the hash it must resolve to | `members[] {role, decl_hash}`, `wiring[]`, `structure` (§4.10a) |
| the degenerate case | a single skill, tool or function. This is the common case | n = 1, which simply omits `members[]` |
| what is hashed | the code the id resolves to | each member's `decl_hash` |

`identity.carrier` is an **id**, not a copy: an MCP tool id, a tool name, a module path, a package
coordinate. Whatever resolves the id already knows what sort of thing it is, so the carrier does not
restate it (Muk, 2026-09-24). **What sort of thing it is lives in `identity.kind`**, which is the one
place that says tool, skill, mcp, subagent, bundle or composite. The old carrier named an agent-core
loader class and only repeated `kind`, so it is gone. `identity.body[]` keeps its existing meaning, the
files the Declaration itself covers, and `identity.remote` still pins a service by endpoint and version.
`capsule.schema.json` enforces the either/or: a Declaration carrying both `members[]` and
`identity.carrier` is rejected.

Why pointing rather than holding: nothing is copied, nothing lives in two places, and the capsule stays
a statement *about* code rather than a container *of* code. The cost is that the guarantee is only as
good as the hash check at the load path, which is exactly the check agent-core's binder does not do
today (§4.17), and which the capsule layer adds.

| Kind | Carrier (agent-core) | What is hashed | How it is loaded |
|---|---|---|---|
| tool | `ToolCard` | the tool's source files | the binder, as a tool |
| MCP server | `McpServerSpec` | local: its files. Remote: pinned by endpoint and version | the binder, as a whole server |
| skill | `SkillSpec` (a `SKILL.md` folder) | every file in the folder | the binder, with the offer applied through `SkillUseRail`'s allow-list |
| A2A agent | the A2A client | pinned by endpoint and version; its card is metadata, never evidence | the A2A client |
| subagent, agent template | `AgentTemplateSpec` | the template files | the binder |
| prompt section | `PromptSectionSpec` | the text | the binder |
| bundle | `PluginSpec` (tools, MCP, skills; **no rails**, which would put a capsule in reach of the checks) | every file | the binder |
| composite | its members | each member's `decl_hash` | through each member's carrier |

### 0.3 Two trust levels

| | Provisional | Certified |
|---|---|---|
| tested before admission | loads, stays within its declared effects in a sandbox run, and passes one postcondition on inputs it was not built from | every output covered by a check written by someone who never saw the code; a judged check counts only if the judge's error is measured and low enough; predicate parity tested |
| may bind | any step whose outputs are gated, unless the step requires certified capsules; its claims are `supported` only where every gating check on them is deterministic, reference-based or a calibrated judge (§4.5c) | any step |

Each claim also carries an assurance: enforced > tested > audited > declared. An unpinned dependency (§4.11) keeps the
capsule provisional.

Below both is **exempt** (v2.7): a generalist, outside the library's verification policies. It is enrolled rather
than admitted on a job (§4.1 step 5: it loads, stays within its declared effects in the sandbox, refuses a protected
write, and completes sample step contracts under their gates), binds where nothing else fits and every output has a
gate of any kind, a judge included, and no claim resting on it is ever `supported` (§4.14).

**What blocks and what labels** (invariant 14, v2.8):

| Refuses the run (identity and safety) | Labels the claims (quality) |
|---|---|
| body hash not the pinned hash | the capsule is provisional, not certified |
| a write to a protected component | a gating judge is `unmeasured` |
| an observed effect outside the declaration | the capsule is exempt (a generalist) |
| an irreversible effect without its approval | an input claim is `unsupported` or `stale` |
| a revoked capsule, or one suspect for security or harm | a capsule's own checks passed but the step's acceptance is judged only |
| a failed node gate (the workflow's gate policy decides repair or fail, as today) | |

### 0.4 Selection: strict first, semantic second

| Stage | Done by | What it uses | What it does |
|---|---|---|---|
| **1. Eligibility** | code, deterministic | the declared requirements below | removes every capsule that cannot apply. Each removed capsule becomes a one-line exclusion |
| **2. Ranking** | code, then similarity | structural fit (output types feed the step's inputs), then similarity (for example Symphony's retrieval, or embeddings) | orders the survivors. Similarity **only ranks**; it never admits or excludes |
| **3. Choice** | a model | only `summary` (at most 400 characters) and `ports` of each survivor | picks one, or none |
| **4. Fit review and dispatch check** | a second model; then code | the step's needs; the **same** predicates, re-evaluated on fresh state | confirms the fit; at dispatch, refuses or defers if a predicate no longer holds |

**The deterministic criteria in stage 1** (§4.3):

| Criterion | Declared field | Compared with |
|---|---|---|
| input and output types | `ports` | the step's required inputs and outputs, in one vocabulary |
| preconditions that can be read at planning | `needs.when` | current facts: credentials, installed tools, reachable services, licences, budget left. A predicate counts as readable at planning only if no upstream step changes its state |
| effects | `changes.effects` | the effects the step allows, and the run's effect ceiling; no write to a protected component |
| trust level | the Verdict's level | whether the step requires certified capsules (`requires_certified`, off by default). Exempt capsules are never in a normal offer: they are offered only when the offer is empty after repair, and only those the run contract's `generalists[]` names (§4.14) |
| network | `needs.network` | the sprint's network zone |
| restriction | the Declaration's `name` | the step's `restrict_to[]`, when a registered workflow sets one (a choice on the demand side, never stored on the capsule) |
| model constraints | `needs.model` | the models the sprint may use |
| standing | Standing | only admitted capsules (plus a small exploration quota of inactive ones on steps that do not require certified capsules) |
| composition | composition Findings | no capsule in a set confirmed as harmful with capsules already bound |

The step's task type is not a criterion: a capsule declares no task (invariant 12). Invariants and postconditions are
not stage-1 criteria either: invariants are checked on outputs and screen which capsules
may share a context; postconditions are verified at admission and after the node.

### 0.5 Position in the AI4Research workflow

**Capability Capsule is useful throughout the system** (v2.9, sharpened v2.10b). The unit is the *work a stage does*,
not the stage: `intent -> IntentIR` is a capability, and so is the faithfulness check that assesses its
output. The workflow keeps its shape -- stages, ordering, scheduling and gates stay where they are --
and what changes is that a stage's work is supplied by a declared capsule instead of being hardcoded.
**The workflow does not become a capsule**; that reading was ruled out on 2026-09-18 and is not what
this says. The earlier sentence here, that intake, intent and requirement compilation never see
capabilities, is superseded.

**Sharpened on 2026-09-24**, because "every stage applies capabilities" was read in the room as *one
capsule per stage*, which is not what happens. A stage is a **chain of capabilities**, and some links in
that chain can never be capsules at all. Read in source, `harness/lib/intent_compiler.py:run_pipeline`
is `normalize_input -> compile_candidate -> validate_intent -> review_fidelity -> decide_acceptance`,
with a bounded repair loop. Four of those five **assess** and may each be a capsule, at n = 1. One
**decides**, so it may never be one, and neither may the loop control, because choosing whether to
repair is deciding.

Two things follow, and both are load-bearing:

- **Capsules apply well before planning.** Intent compilation is four capsules deep, so the layer is
  not confined to the DAG-binding stage.
- **A phase holding a decider can never be fused.** A composite is made of capsules and nothing else
  (§4.10a), so a block spanning `decide_acceptance` would need a member that cannot be a member. The
  section before it may be composed or merged; the section containing it may not. That is the same
  compositional argument as the workflow one, one level down.

**CC's own control** acts at **planning, freeze and dispatch**, and in the in-run gates and delivery.
Admission, the audit loop and the librarian run outside the sprint. CC is
upstream of Symphony: its `CapabilityProvider` lists only admitted capsules, and Symphony retrieves and ranks within
them. Code locations are in AI4Research at `b0bf165f9` (`../kb/repos/ai4research-workflow.md`).

| Stage | Where today | What the schema adds |
|---|---|---|
| Planning | the planner's hard filter and binding prompt (`elastic_planner.py` `_hard_capsule_candidate_row`, `_capsule_selection_prompt`, `review_capsule_fit`) | stage-1 criteria above, including preconditions readable at planning; the chooser sees only `summary` and `ports` |
| Freeze | `compile_and_freeze_execution_bundle`; `execution_authority.freeze_node`, `check_live_definitions` | the Binding pins `decl_hash`, Verdict, level, fallbacks and overlays; status must be admitted, never missing-as-stable (§4.4) |
| Dispatch | `operator_runtime.py` and `capability_capsules.py` precondition checks (four hard-coded kinds) | the same predicates, re-evaluated on fresh state through one evaluator; live hash equals pinned hash (§4.5) |
| Scheduling | `graph_scheduler.ready_nodes` (topological order), at most 8 in parallel, write-scope and effect conflicts held back (`graph_scheduler.py:3203`), one lease per operator (`operator_runtime.py:504-515`) | the workflow keeps order, the cap and worker assignment; CC supplies declared write scopes, `resources` modes and the gate's `parallel_safe` flag (§4.3a) |
| In-run gates, delivery | the node dispatcher's gates; invariants judged as prose | declared checks on outputs; observed effects against declared; each claim keeps the invocation that produced it and a status (§3.5) |

### 0.6 A capsule holds no task, and multiplicity is real

**A Declaration describes a capability, never a use** (invariant 12). It names no step, node, sprint, plan, workflow,
stage or task type, no capsule to run before or after it, and no worker. It says what it takes, returns, needs,
changes and guarantees, and it is told what to do through its inputs. Two structural exceptions are not uses: a
pinned `capsule` dependency (a guard or adapter it needs in order to run) and a composite's `members`.

Everything about a use lives in the demand and join records: the **Plan step** (what a node needs), the **Binding**
(what the freeze chose for it) and the Binding's **invocations** (every actual run).

| Relation | Cardinality | Recorded in |
|---|---|---|
| name to Declarations over time | 1 : N versions | `lineage`, Standing history |
| name to the version a sprint uses | 1 : 1 within a sprint (its snapshot); concurrent sprints may run different versions | Standing, Binding `snapshot_id` |
| sprint to Plan steps | 1 : N, hashed as one plan, derived steps included | Plan step |
| Plan step to Binding | 1 : 1 per sprint | Binding |
| Binding to capsules | 1 : N: one `primary`, any `context` capsules, the closed `dependency` capsules, and pre-approved fallbacks | `bound[]`, `fallbacks[]` |
| Declaration to Bindings | 1 : N, across steps, plans and sprints, as a bound capsule or a fallback; one capsule serving many steps is the normal case | `bound[].decl_hash`, `fallbacks[].decl_hash` |
| Binding to invocations | 1 : N: fan-out items × attempts × fallbacks | `invocations[]` |
| composite to members | 1 : N, keyed by role; a member may repeat | `members[] {role, decl_hash}` |
| parent to children | 1 : N; a child has one `parent` and optional `co_parents`; siblings may coexist | `lineage` (§4.13a) |


### 0.7 What is required when (v2.9)

**The normative artifact (Muk, 2026-09-23: agree the schema and data structure early to unblock work).**
This document is the reasoning. The thing tools build against is machine-readable and lives beside it:

| File | What it is |
|---|---|
| `merged/capsule.schema.json` | **Shape.** JSON Schema 2020-12 for the Declaration: every field, its type, its enums. Marks almost nothing required |
| `merged/policy-m1.json` | **Gate.** What the M1 epoch insists on, applied alongside the shape. Versioned, relaxable, recorded on every Verdict |
| `merged/validate_capsule.py` | Validates a Declaration against either, or both |
| `merged/examples/` | A real capability under the schema, the same one as declared today (which the gate rejects), and a composite |

**Why the split.** A required field in a shared schema can never be taken back, so Protocol Buffers
removed `required` and tells authors to document it instead. Here, shape stays stable so tools keep
compiling, and required-ness moves to a policy that can tighten or relax per epoch. It is also what makes
"progressively activated" a mechanism rather than a promise: M2 and M3 are new profiles, not a new schema.

**Tools come later; the schema comes first.** Nothing in the artifact depends on a merge engine, a
librarian or a router existing. A field whose consumer has not been built is present, typed and inert.


**The schema is whole from day one. What is staged is how much of it is enforced.** A field is declared in
the schema from the start and sits **inert** until the component that reads it exists. So nothing is
redesigned later, parts can be missing while the system still demonstrably works, and the milestones below
describe **activation, not construction**.

| | What is running at the end | What starts being enforced |
|---|---|---|
| **M1** | one node | `identity.name`, `identity.kind`, `identity.carrier`, `identity.body[].sha256`, `identity.summary`, `ports.inputs[]`, `ports.outputs[]`, `needs.when[]`, `changes.effect_class`, `guarantees.checks[]`; the hash check before load; one shared predicate evaluator; one Binding per run |
| **M2** | a few chained nodes | port type matching across nodes, the dispatch re-check on fresh state, node gates (§4.5b), gap Findings, `changes.provides` and `invariants` |
| **M3** | a library, about ten capsules | Verdict, Standing, versions, the librarian and the audit loop, held-out suites, judges and their calibration (§4.5c), `guarantees.acceptance` and `evals`, the quality criterion and its minimum observation count, `needs.model` and `budget`, `overlays`, `load_mode`, `exempt` (§4.14) |
| **M4** | overlap and merge | `identity.lineage`, `members[]` and `structure`, the capability tree (§4.13a), merge (§4.9a), composition screening (§4.9) |
| **M5** | spatiotemporal composability | §4.6, within the limits stated there |

**Every enforced field is a cost** -- work for whoever writes a capsule, and a check the gate must run. A
large required core discourages the adoption the design depends on, which is why the M1 core is ten fields.

**Required-ness lives in the gate, not in the schema.** Protocol Buffers removed `required` deliberately,
because a required field can become unnecessary later but can never be removed; its guidance is to
document required-ness instead. So the schema marks nothing required: **the gate's `policy_epoch`
decides what is enforced**, it is versioned, it can be relaxed, and every Verdict records which epoch
admitted under it. That is what makes progressive activation a mechanism rather than a promise.

**Off the ladder entirely:** ranking, sorting and retrieval inside the offer. Symphony already ships these
and they work. CC decides what Symphony may index, through `CapabilityProvider`, and does not rank.

---

## 1. What it is, on one screen

Capability Capsule (CC) is **a schema**: the shared contract that every capability in the openJiuwen-based AI4Research
system declares, and the records kept about it. The capsule layer's code applies the rules on agent-core. The
verifier, the screener, the chooser and routing are tools it uses. **CC is a scheme, not a tool** (supervisor,
2026-09-21).

**What the schema is for.** The schema serves two goals at once:

1. **Safe use.** Before any sprint relies on a capability, check what it declares it needs, changes and promises.
2. **Safe self-improvement.** Agents that build, check and keep their own capabilities while long research runs
   continue (the 2026-09-15 capsule report, §1). Agents must be able to:
   - explore the capability space;
   - decide whether to use a skill, and which;
   - decide whether to make, modify or retire one;
   - implement it, and evaluate it;
   - manage the library as it grows;
   - trace a failure to its downstream impact;
   - keep provenance.

The second goal is why the library is **versioned** (every change is a new hash), **append-only** (nothing is edited
or deleted; retirement is a tombstone), and **monotone** (a new version passes everything its predecessor passed). It is
also why it runs on **three clocks** (§4.0): sprints keep using the library while it is being improved, and nothing an
agent builds can grade itself.

A capsule is **six kinds of record about one capability, kept apart by who is allowed to write each one** [ind]:

| Record | Answers | Written by | Changes? | Key |
|---|---|---|---|---|
| **Declaration** | What does it need, change, promise and spend? | the builder (a person or RSI) | never; a revision is a new Declaration | `decl_hash` |
| **Verdict** | Was this exact Declaration checked, by what, with what result, at which level? | the admission gate | append-only | `decl_hash` + `policy_epoch` |
| **Standing** | Which Declaration is current for this name, and may it be offered? | the librarian | a pointer that moves; every move logged | `name` |
| **Plan step** | What does this node of the plan require? | the planner | hashed with the plan | `plan_hash` + `step_id` |
| **Binding** | In this sprint, which exact Declarations serve which step, why were they allowed, and what did every run of them do? | the freeze; dispatch appends `invocations[]` | append-only | `sprint_id` + `step_id`; each invocation by `invocation_id` |
| **Finding** | What did screening, audit, drift probing, use or a verifier audit reveal later? | screeners, auditors, probes, verification | append-only | the set of hashes it concerns |

**The governing rule** [ind]: **observation may withdraw authority; only a checked declaration may grant it.**
Findings can move a Standing only toward less authority: to `suspect`, `admitted_inactive` (demoted), `revoked` or
`retired`. Never to `admitted`.

**How far each promise is backed** [both]:

- per **capsule**, a **level**: `provisional` (loads, stays within its effects, passes one postcondition) or
  `certified` (every output tested by an author who never saw the code, with an audited judge and predicate parity)
  [v1.6];
- per **claim**, an **assurance**: `enforced` (the runtime prevents a violation), `tested` (the gate ran a check),
  `audited` (compared with a run afterwards) or `declared` (nothing checks it, and the Declaration says so) [ind].

The level says where a capsule may run. The assurance says how much each individual promise is worth.

### 0.7a Where the shape-and-policy split comes from (v2.10a)

Two precedents, and between them they are the whole argument for §0.7. Neither is research, and
neither is ours.

**Protocol Buffers** removed `required` on purpose, because a required field in a shared schema can
never be taken back, and tells authors to document the requirement instead. That is why
`capsule.schema.json` marks almost nothing required.

**C++26 contract assertions** go further, and are the closer parallel. `pre` and `post` are *function
contract specifiers*: the contract is written on the **declaration**, where a caller can see it, not
buried in the body. And how hard the contract is enforced is deliberately not in the source at all:
cppreference states that *"it is implementation-defined which evaluation semantic is used for any given
evaluation of a contract assertion"*, choosing between **ignore**, **observe**, **enforce** and
**quick-enforce**.

That is exactly the division this schema makes, and it maps term for term:

| C++26 contracts | Capability Capsule |
|---|---|
| `pre` on the declaration | `needs.when[]`, evaluable, read by the filter and by dispatch |
| `post` on the declaration | `ports.outputs[].check` naming an entry in `guarantees.checks[]` |
| the contract is part of the interface | the Declaration is the interface; the body is only pointed at (§0.2) |
| **ignore** | a field declared from day one and inert until its consumer exists (§0.7) |
| **observe**: check, report through the handler, carry on | **label** a quality claim, which never blocks (§4.5c) |
| **enforce**: check and stop | **block** for identity and safety (§0.3) |
| the semantic is implementation-defined, not in the source | `policy-m1.json` is a versioned epoch, and each Verdict records the epoch that admitted under it |

The observe-versus-enforce pair is worth saying out loud, because it is the same decision as **block for
safety, label for quality**, reached independently by a language standards committee.

Status, checked 2026-09-24: contracts are **in** C++26. C++26 completed on 2026-03-28, and contracts were
retained on a plenary vote of 114 for, 12 against, 3 abstaining (Herb Sutter's trip report, 2026-03-29).
The design was contested: more than twenty national body comments were filed against it, and a paper
circulated to defer it to C++29. Cite it as a precedent that was argued over and kept, not as a
consensus.

### Invariants

Any respecification keeps these. 1 to 8 are from v1.6; 9 to 11 from the independent version; 12 from v2.5; 13 from
v2.6; 14 from v2.8.

1. The contract is the only interface.
2. The library is append-only. A better version is a new revision, with a new hash.
3. A run sees only the versions it started with.
4. Whatever decides never builds. No capsule may write the gate, the verifier, the suites, or the records admission
   reads (the protected components, §4.1). Each record is written only by its named writer.
5. A capsule is certified only on tests from an author who never saw its implementation.
6. Every write, execute and network effect declares how it is undone: an inverse, a scope that is discarded, a
   compensation, or none (an emission).
7. Admission has a threshold, and this team owns it.
8. Whether a capsule is eligible, at planning and at dispatch, is decided only by its declared predicates, through one
   evaluator, never by a separate heuristic. Choosing among eligible capsules is a model's call and may use any
   evidence.
9. One writer per fact: a fact lives in exactly one record kind, and only its writer states it.
10. Declared and observed facts never share a record.
11. Everything downstream refers to a hash, never to a name.
12. A Declaration describes a capability, never a use: it names no step, node, sprint, plan, workflow, stage, task
    type, other capsule to run with, or worker. Uses live in Plan steps, Bindings and invocations (v2.5).
13. The author answers for what the capability does; CC answers for checking what was declared against what is
    observed. Behaviour found outside the declaration is the author's violation: a typed reason and a Standing move
    recorded against `lineage.builder`, never a score (v2.6).
14. A check refuses a run only for identity or safety. A shortfall in quality (the trust level, the standing of a
    judge) is recorded on the claims it affects, never enforced by refusing the run (v2.8).

---

## 2. Definitions

In the order they are first needed.

- **Capability.** Something an agent can invoke: a tool, an MCP server, a skill folder, a prompt section, a subagent,
  an agent template, or a composite of these. Never model weights.
- **Builder.** Whoever writes a Declaration: a person, or RSI (recursive self-improvement, the team that builds and
  improves capabilities).
- **Sprint (run).** One pass of the AI4Research pipeline: intake, intent, requirement compilation, planning, freeze,
  scheduling, dispatch, operators with in-run gates, delivery of claims.
- **Snapshot.** The set of capsules available when a sprint starts.
- **Run context.** The typed facts at a decision point: artifacts that exist, state variables, services currently
  provided, resources and their modes, secret references, network zone, remaining budget.
- **Vocabulary.** The versioned list of names for artifact types, state paths, resource keys, service keys and the
  predicate operators (`present`, `>=`, `includes`, `resolves_in`, …); a predicate using any other operator is rejected at
  admission. Authored
  by the capsule layer and seeded from Symphony's (`code` `shared/fingerprint/normalization.py:100-142`). A
  Declaration may use only names in it.
- **Predicate.** A named, code-evaluable condition over the run context: `true`, `false` or `unknown`.
- **Predicate parity.** The planner's filter, the dispatch check and the capability's own exit logic agree on a
  predicate (2608.01050 p2-3). Section 4.3.
- **Effect.** A declared change to a named resource: which resource, which operation, what scope, how it is undone.
- **Reversibility.** `inverse` (an undo is declared), `scoped` (the effect happens in a child context that is thrown
  away), `compensate` (a later action offsets it), `emission` (it crosses the system boundary and cannot be undone).
- **Service key.** A name for something one capability installs (*provides*) and another depends on (*injects*):
  Cordis's coeffect key (2608.25512 p6).
- **Check.** An executable test with an id. Its **runner** is the code that executes it, identified by hash. Its
  **anchor** is `deterministic`, `reference` or `judged`.
- **Policy epoch.** The version of the admission rules, vocabulary and verifier set.
- **Offer.** The set of capsules a model is shown when it chooses. The **executability filter** computes it.
- **Freeze.** The step that fixes, before scheduling, exactly which Declarations a sprint will use.
- **Composite.** A capsule whose body is a wired graph of other capsules, each pinned by hash. A jiuwenswarm
  SkillPack and a Swarm (team) Skill are composites when their members are pinned.
- **Overlay.** Content loaded with a capsule, or into the chooser's input, that is not in the capsule's original
  files. Examples: a skill's evolved experience layer, TTSE facts and tips, a hot-loaded harness package.
- **Builder gate.** A check the builder runs on its own candidates, such as RSI's candidate gate. It is evidence for
  a candidate, never admission.
- **Gap.** A recorded need that no admitted capsule met.
- **False-pass ceiling.** The highest audited false-pass rate at which a judge's verdict counts toward certification
  (**design**; default 0.05).
- **H1-H5.** What the design needs from agent-core: H1 reversible registration, H2 dependency tracking, H3 immutable
  versioned artifacts, H4 a reconstructable execution log, H5 observing what code does. agent-core provides H1 fully.

---

## 3. The records

**Reader** names the tool that consumes a field. A field with no reader is not in the schema.

### 3.1 Declaration (the builder; immutable)

`decl_hash` is SHA-256 over the canonical Declaration, including the hash of every body file. Computed, never
declared. Seven sections [ind], with v1.6's fields placed in them.

**identity**

| Field | Type | Reader | Why |
|---|---|---|---|
| `schema_version` | string | every reader | an old Declaration is read under its own schema [v1.6] |
| `name` | stable, vocabulary-safe | librarian, planner | the handle a Standing points from; a contract change is a new name |
| `version_label` | free text, e.g. semver | people, importers | carries skillhub's and A2A's versions; identity is the hash |
| `kind` | tool, mcp, skill, prompt, subagent, agent, composite | binder | picks the carrier. Workflows and team skills are not admissible in v1: a Swarm Skill's Leader decides at run time which roles to involve and schedules them (`docs/en/SwarmSkills.md:241-253`), so it plans, which is above the ceiling (§4.10). Their `dependencies.yaml` is imported as evidence only [v1.6; confirmed v2.1] |
| `carrier` | `{spec: ToolCard, McpServerSpec, SkillSpec, PromptSectionSpec, PluginSpec, AgentTemplateSpec; ref}` | binder | how agent-core loads it unchanged. `PluginSpec` bundles tools, MCP servers, rails and skills (`code` `harness/schema/extension_spec.py:146-164`) [ind] |
| `flags` | ToolCard's `exposure`, `parallel_safe`, `stateless`, `idempotent` | binder | computed by the gate from `changes` and recorded in the Verdict, not hashed with the Declaration; never the other way (`code` `core/foundation/tool/base.py:83-118`) |
| `contract_hash` | computed: SHA-256 over every section except `body`, `lineage`, `coverage` and `evolution.notes_for_builder` | suite author, gate | a suite written before the code is bound to the contract it tests. A body submitted with a different `contract_hash` makes the suite void (v2.3) |
| `body` | list of `{path, sha256}` | gate, binder | what is loaded; a mismatch at load aborts it. AI4Research today hashes only the manifest file (`code` `execution_authority.py:40`) |
| `summary` | at most 400 characters | the chooser, Symphony retrieval | the only prose the chooser sees (2605.24050 p4, by definition) [ind]. Shown as quoted data; it may not name other capsules, tools, stages, workflows or tasks (**design**; v2.5): it says what the capability does, not where it is used |
| `overlays[]` | `{kind: experience, guidance, package; ref; sha256; source: builder, teammate_auto, ttse, auto_harness}` | binder, freeze, audit | content loaded with the capsule outside its original files; hashed so a sprint pins it (v2.1; `DERIVATION.md` D11-D13) |
| `load_mode` | context_injected, invoked | planner, screener | severe drift was rare with one skill loaded and rose fourteen-fold to 66.5% with five (2607.02345 p9); invoked isolation is **design** [v1.6] |
| `lineage` | required: `{parent: decl_hash or none, relation: supersedes, specialises, rollback_of, migrated_from, composes (`fuses` reserved, not implemented); builder}`. Optional, stored when the builder supplies them (v2.7): `{co_parents[]; build_trigger: gap id; context_capsules[]; diagnosis_inputs[]; provenance {generating_model, prompt_ref, trajectory_ref}; builder_ref}`, where `builder_ref` is the builder's own id for this node, such as RSI's tree node | librarian, audit, RSI | revert target; `context_capsules` lists what was in the builder's context, so a harmful capsule's descendants can be found (2608.05810 p7) [ind] |

**ports**

| Field | Type | Reader |
|---|---|---|
| `inputs[]` | `{name, artifact_type (vocabulary), required, schema_ref}` in Symphony's `CapabilityIO` shape (`code` `symphony/models/capability.py:13-21`) | filter, wiring, Symphony |
| `outputs[]` | `{name, artifact_type, schema_ref, check_id}` | wiring, gate |

Every output names the check that validates it; an output with no check is `declared`.

**needs**

| Field | Type | Reader |
|---|---|---|
| `when[]` | `{id, check {path, operator, value}, state_source, evaluable_at: planning or dispatch, max_age_s, on_unknown: defer or exclude, on_unavailable: block or pass (with a reason), parity_check}` | filter (planning-evaluable only), dispatch (all) |
| `injects[]` | `{service_key, interface_version_range}` | composability, screener |
| `resources[]` | `{resource_key, mode: read, write, exclusive}` | filter, scheduler, screener |
| `external[]` (dependencies) | `{kind: package, data, model, service, capsule, secret; pin}`, or `{kind; floating: {purpose, role, contracts[]}}` | gate, drift probe, routing, RSI (repair) |
| `network` | none, allowlist, open | filter, sandbox |
| `model` | `{tool_calling, min_context, modalities}` | **routing**, as a constraint; never a choice |

- `when` is **three-valued**. For a required predicate, `unknown` gives DEFER with a typed request for the missing
  fact, not exclusion (2609.16313 p5) [ind]. A fact older than `max_age_s` counts as `unknown`.
- `evaluable_at` says when the state can be read, but the builder only proposes it. A block at planning holds only
  "without a relevant state change" (2608.01050 p3), and upstream steps change state. So the planner evaluates a
  predicate at planning for a step only if no upstream step in the plan declares an effect on the predicate's
  `state_source`. Code computes this per step from declared effects (v2.1). Otherwise the predicate waits for dispatch.
  (2608.01050 reads state when each message arrives, p3 §4.2.)
- `on_unavailable` applies when a readable source fails; blocking by default is **design**, and `pass` needs a stated
  reason (2608.01050 p5 §6.2) [v1.6].
- `[]` is allowed only with a stated reason. AI4Research's validator already requires preconditions non-empty but checks
  four kinds against the task envelope at dispatch, and its filter never reads them (`code`
  `capability_capsules.py:676-678`, `:1220-1242`; `elastic_planner.py:4553-4648`).
- A dependency is pinned by `sha256`, `{provider, model_id, version}`, `{endpoint, version}` or a capsule hash. A
  `capsule` dependency (guards, adapters) is closed transitively at bind; the verifier is never one (inv 4). A `secret`
  needs a guard and is re-checked at dispatch, as AI4Research does when it resolves a capsule
  (`code` `capability_capsules.py:684-690`, `:1370-1371`). A `floating` dependency is §4.11. A tool or skill a team
  skill needs (its `dependencies.yaml`) is a `capsule` dependency, pinned.

**changes**

| Field | Type | Reader |
|---|---|---|
| `effect_class` | `pure`, `idempotent`, `compensable`, `irreversible` (v2.6) | filter, scheduler, dispatch, gate |
| `effects[]` | `{id, resource_key, op: read, write, create, delete, emit, execute; scope; idempotent (v2.6); reversibility; risk {severity, blast_radius, irreversibility}; assurance}` | filter, screener, sandbox, audit |
| `provides[]` | `{service_key, interface_version, commutative}` | composability, screener |
| `invariants[]` | `{id, statement, check_id}` | screener, audit |

- No effect's scope may include the verifier's inputs: a Darwin Gödel Machine node removed the logging its hidden
  checker read (2505.22954 p70; a 3-task side experiment).
- An `emission` names its policy: `withhold_until_freeze_ok` or `compensate:{capsule}`. No inverse is claimed
  (2608.25512 p70-71).
- `inverse` is allowed only for a location the capsule layer alone can modify and restore, such as a scratch path under
  the sprint's own workspace.
- **External state** (v2.6). A `resource_key` is either inside the capsule layer's boundary (`ws:`, the sprint's
  workspace) or outside it (`ext:<system>:<scope>`, for example `ext:postgres:orders`). An effect on an `ext:` resource
  is `compensate` or `emission`, never `inverse` or `scoped`: the capsule layer cannot restore a system it does not own
  (2608.25512 p70-71). Reads of `ext:` state are declared too, so a capability whose output depends on external state
  is never taken for pure.
- **`idempotent`** per effect: running it twice with the same inputs leaves the same state as running it once. An
  author claiming it names the key that makes it so (for example an upsert on a declared column) in `scope`.
- **`effect_class`** is the author's attestation for the whole capability. It must agree with the effects, or the gate
  rejects with `EFFECT_CLASS_INCONSISTENT`:

  | Class | Allowed effects |
  |---|---|
  | `pure` | reads of its inputs only (no `ext:` or shared `ws:` read) and writes under its own `{instance}` scope only |
  | `idempotent` | every write, create, delete and emit is `idempotent`; a capability that only reads `ext:` state is here, not `pure` |
  | `compensable` | every effect not idempotent has `inverse`, `scoped` or `compensate:{capsule}`, with the compensating capsule pinned as a dependency |
  | `irreversible` | anything else, including every `emission` that is not idempotent |

**guarantees**

| Field | Type | Reader |
|---|---|---|
| `checks[]` | `{id, kind (including `negative_control`: an input the capsule must refuse or mark),  anchor: deterministic, reference, judged; over: each_call, outputs, inputs_and_outputs; runner {ref, sha256}; author; written_before_body; held_out; signal_source: harness or capsule; owner: external or self; assurance}` | gate, verification, audit |
| `acceptance` | the check ids that must pass for admission | gate |
| `evals[]` | `{suite_ref, sha256, metric, threshold, held_out}` | gate, verification |
| `unanchored` | aspects of an output no check covers, e.g. whether an insight is new | planner (`require_anchored` steps) [v1.6] |
| `exempt` | `{reason: generalist}`; any other reason is rejected (`EXEMPT_NOT_ALLOWED`) (v2.7) | gate, filter, freeze, librarian | a do-anything capsule has no job of its own to test; its ports and checks come from each step (§4.14). Replaces v2.2's `generalist: true` |

`over: each_call` replaces AI4Research's `invariants` and `pass_conditions`; `self_check` is dropped, because running
without error is never evidence (2604.00392 p5) [v1.6].

**budget** (agents; optional for others)

| Field | Type | Reader |
|---|---|---|
| `per_call` | `{tokens, wall_s, cost, tool_calls, iterations}` | runtime, scheduler |
| `enforcement` | per dimension: hard, between_calls, post_hoc | audit, scheduler |
| `on_exhaust` | fail, return_partial | runtime |
| `context_cost_tokens` | size of `summary` plus `ports`, computed by the gate and recorded in the Verdict | filter, librarian |

Contracts bind between calls; within one call only `max_tokens` approximately bounds cost (2601.08815 p12-14). A
capsule that exhausts its budget has not passed.

**members** (composites only): `members[] {role, decl_hash}` and `wiring[] {from, to}`, where wiring connects roles.
One Declaration may fill several roles (v2.5), which today's composition search forbids (`code`
`capsule_composition.py:340`, `:559`). The union of members' needs and
changes is `derived` by the gate and recorded in the Verdict, never written by the builder or hashed with the
Declaration (§4.10).

**coverage** (optional): `undeclared_notes`, what the builder knowingly leaves out; the screener gives such capsules
priority [ind].

**Not in the Declaration:** any use of the capability (inv 12): step, node and sprint ids, task types, workflow stages,
capsules to run before or after it, and workers. A capability valid only for some inputs says so with `needs.when`
predicates over its inputs (for example `inputs.paper.language in [en, zh]`), never with a task list. Also not in it:
the tests' contents (inv 5), the Verdict and Standing (a record cannot contain its own hash),
the body's internals (supervisor), selection scores, and conflicts between capsules, which cannot be read from text
(2606.03056 p5-6).

### 3.2 Verdict (the admission gate; append-only)

| Field | Reader | Why |
|---|---|---|
| `decl_hash`, `policy_epoch`, `issuer`, `issued_at` | all | inv 7; `policy_version` is skillhub's name (`code` `market_assets.py:142-175`) |
| `outcome`: ADMIT, REJECT, DEFER, ESCALATE | librarian, RSI | typed; unknown defers, only a violated check rejects (2609.16313 p5, p8) |
| `level`: exempt, provisional, certified | planner, freeze | where the capsule may run (§4.1, §4.14) |
| `reasons[]` | RSI, librarian | typed codes: `VOCAB_UNKNOWN_NAME`, `CHECK_FAILED`, `CHECK_UNKNOWN`, `RUNNER_IN_WRITE_SCOPE`, `EFFECT_OUT_OF_SCOPE`, `EFFECT_ESCALATION` (declared effects beyond the step's or run's ceiling, or onto a protected component), `HASH_MISMATCH`, `SCHEMA_NONCONFORMANT`, `CONTRACT_UNSATISFIABLE`, `INVARIANT_VIOLATED`, `NEGATIVE_CONTROL_FAILED`, `COMPENSATION_UNDECLARED`, `PROVENANCE_UNVERIFIED`, `CONTRACT_HASH_CHANGED`, `UNDECLARED_MEMBER_EFFECT`, `DUPLICATE`, `NOT_MONOTONE`, `DEPENDENCY_UNADMITTED`, `SCREEN_PENDING`, `NEGATIVE_MARGINAL_GAIN`, `INHERITED_SUITE_FAILED`, `EXEMPT_NOT_ALLOWED`, `PARENT_REVOKED` (v2.7), and from v2.6 `EFFECT_CLASS_INCONSISTENT`, `IDEMPOTENCE_FAILED`, `COMPENSATION_FAILED` |
| `evidence_requests[]` | RSI | what a DEFER waits for |
| `checks_run[]` | admission, librarian | `{check_id, runner_sha256, result: pass, fail, unknown; unknown_cause; evidence_sha256}` |
| `builder_gate` | admission, RSI | the builder's own gate result, kept as evidence: e.g. RSI `published` from a target-local candidate gate with no held-out cases (`code` agent-core `rsi/harness_rsi/single_harness/iterative.py:1435-1447`, `:164`). Never counts as a passed check (v2.1) |
| `suites[]` | admission, RSI, librarian | every suite this hash was checked with (v2.7): `{suite_id, hash, author, recorded_at, access: visible or sealed (as `pass_fail_bits` or `diagnostics`), inherited_from: parent `decl_hash` or none}`. A child inherits its parent's suites (§4.7); certification needs sealed or pass-fail bits, since in one case, hacking appeared when checked functions were visible (2505.22954 p70; a 3-task side experiment, not a measured rate) |
| `observed` | admission | effects and outputs seen in the sandbox or at tool-call level (H5). Effects are authored: from documentation, contracts got preconditions right (F1 1.00) and effects least right of any source (0.77) (2606.07904 Table III, p7) |
| `remote_fingerprint` | dispatch, audit | for a remote body (an MCP server, an A2A agent): a hash of its advertised interface (tool names, schemas and descriptions, or the agent card) taken at admission (v2.6) |
| `precondition_parity[]` | admission | `{predicate id, boundary, missing_state, stale_state}` (2608.01050 p5 §6.1) |
| `verifiers[]` | admission, librarian, gates | `{id, version, review_engine, model_name, measured_error {false_pass, false_fail, n, corpus, date}, standing: unmeasured, calibrated or measured, per artifact type (v2.8, §4.5c)}` |
| `models_used[]` | routing | evidence holds for the models it was measured with (**design**) |
| `baseline_snapshot`, `contribution` | librarian | gain against the current pool (2608.05810 p4-6) |
| `nearest[]` | librarian | near-duplicates |
| `screening[]` | freeze | composition Findings consulted |
| `invalidated_by[]` | librarian | a pinned dependency's new hash, a floating dependency's broken contract (a move within its contracts does not void), a new policy epoch, a re-audited verifier, a model outside `models_used` |

### 3.3 Standing (the librarian; a moving pointer, every move logged)

| Field | Type |
|---|---|
| `name`, `current` (a `decl_hash` or null), `previous[]` (revert targets) | |
| `state` | proposed, candidate, admitted, admitted_inactive, outside_cap, suspect, deprecated, revoked, retired, local_waiver, private |
| `reason` | ADMITTED, SUPERSEDED, NO_GAIN_YET, EVICTED_BY_CAP, RETIRED_ON_EVIDENCE, REVERTED, CERTIFICATE_EXPIRED, REVALIDATION_PENDING, SUSPECT_DRIFT, SUSPECT_AUDIT, REVOKED_DEPENDENCY, DEPENDENCY_CONTRACT_VIOLATED, REVOKED_SECURITY, REVOKED_HARM, WAIVER, MEMBER_UNAVAILABLE, CONFORMANCE_FAILED, EFFECT_VIOLATION, PROVENANCE_REVOKED, DEMOTED_TASK_SUCCESS, REMOTE_CHANGED, CLASS_VIOLATION |
| `evidence` | per reason, e.g. RETIRED_ON_EVIDENCE `{n_trials, n_min, tau, contribution, verifier_ref}` |
| `slot` | the library partition and the cap it counts against |
| `since`, `by` | when, and which tool or named person |

`RETIRED_ON_EVIDENCE` and `EVICTED_BY_CAP` are separate on purpose: under false-pass bias injected on a grader,
retirement by the contribution rule fell to 0 to 0.3 against 1.3 clean, while raw deprecations never reached zero
(9.7 clean; 7.7, 3.7, 3.0 biased), so the count hid a stopped curator (2607.07436 Table 1, p6).

`admitted_inactive`: admitted, not yet offered (no gain yet, an expired certificate, revalidation). `outside_cap`:
beyond the cap, bound only by an explicit pin set by the librarian or a named person, never a model. `local_waiver`: one
hash on one machine after passing provisional tests locally, never shared. `private`: admitted, never published.

### 3.4 Plan step (the planner; hashed with the plan) [v1.6]

`step_id`; `task_type`; `requires` {typed inputs, planning-evaluable predicates, allowed effects and whether `emission`
is allowed, `requires_certified` (v2.8, default off; replaces `accepts_provisional`), `judge_tolerance` (v2.8: the highest
false-pass upper bound a calibrated judge may have for its passes to support claims, 0.2 by default, **design**), `require_anchored`, `secrets[]`, `acceptance[] {check_id, runner_sha256,
requirement_id}` (v2.7: this step's part of the node gate, §4.5b)}; `depends_on[]` {step_id, from output, to input};
and, optionally (v2.5):

- `over {input, max_parallel}` and `gather {mode: all | best_effort, min_items}`: **fan-out**. The step's input is
  `collection<T>`; the bound capsule's port takes one `T`, and each item is one invocation. The capsule never knows it is mapped. A capsule whose
  port takes `collection<T>` natively is bound without `over`: the types decide.
- `derived_from: step_id`: a step added by composition expansion (§4.3a).
- `restrict_to[]`: capsule names a registered workflow allows for this step (today's `allowed_capsules`). It narrows
  the offer; it is the demand side's choice and is never stored on a capsule.

The Plan step names no capsule. **The planner never holds a list of capsules to schedule:** it states what each node
needs, and the offer, the freeze and dispatch fill it (§4.3a).

- **Ports, not guesses.** Edges are declared ports. Symphony today proposes edges with a model at confidence 0.7 or more
  (`code` `orchestration/graph/build.py:122`) and matches `unknown` against any same-named input (`input_matching.py:23-33`);
  here `unknown` is allowed only for steps that do not require certified capsules.
- **Provisional capsules may bind any step** (v2.8) that does not set `requires_certified`. What a provisional
  capsule's output supports is decided by its gates, per claim (§4.5c): a task-level judge alone never makes a claim
  `supported` until the judge is calibrated (2604.00392 p5). Steps set `requires_certified` where a wrong output
  cannot be caught later, for example before an irreversible effect.
- **Unmet requirements, typed:** `needs_input` (the user can supply it; Symphony's status, `code` `plan_builder.py:53`),
  `bound_to_generalist` (nothing fits, and the run contract allows the generalist, §4.14), `unsatisfiable_capsule` (a
  gap, after repair, with generalists off, none named, or over the cap), `unsatisfiable_binding` (fits but cannot load),
  `precondition_unknown` (deferred with a request).
- **The run contract** is one record per sprint, hashed into `plan_hash` so every Binding covers it:
  - `generalist_fallback: off | on`;
  - `authoring: off | propose | build`:
    - `off`: generalist steps leave no gap Finding;
    - `propose`: they leave gap Findings, which count toward recurrence;
    - `build`: as `propose`, and this sprint's gaps may also authorise a build.

    Whether the cold path runs at all is a library-level policy, not a per-sprint flag.
  - `generalist_cap`: the most steps per plan that may bind a generalist;
  - `require_supported_delivery: true | false` (v2.8, default false): when true, a delivered claim that is not
    `supported` is withheld and listed, rather than delivered with its label;
  - `generalists[]`: the exempt capsules this sprint may use, by name (for example a Codex and a Claude generalist);
    empty means none (v2.7);
  - `unattended: true | false` (§4.15);
  - `effect_ceiling`: the union of effects the authorising request allows.

  Frozen, so a sprint cannot change it partway through (2026-09-15 report, App. G.3).

### 3.5 Binding (the freeze writes; dispatch appends)

| Field | Why |
|---|---|
| `sprint_id`, `snapshot_id`, `plan_hash`, `evaluation_plan_hash`, `step_id` | AI4Research freezes the plan with its evaluation plan (`code` `elastic_planner.py:7146-7333`) |
| `bound[] {decl_hash, role: primary, context, dependency; verdict_ref, level}` | exactly what is loaded for this step, and why each was allowed. One `primary`; `context` capsules share its context (`load_mode: context_injected`); `dependency` capsules are its closed pinned dependencies (v2.5, replacing one `decl_hash` and `co_loaded[]`) |
| `offered[]`, `blocked[] {decl_hash, predicate id, where}`, `offer_hash`, `selection_tokens` | what the chooser saw; tokens measured in M2 |
| `choice_ref`, or `none` | the model call that chose; at 202 skills 38.5% of trajectories invoked no skill (2605.24050 Table 2, p9) |
| `exempt` | true when the step is bound to an exempt capsule, a generalist (§4.14; v2.7, was `generalist`): lowest trust, listed in the delivery, and its trajectory is referenced from the gap Finding (v2.2) |
| `findings_consulted[]` or `unscreened` | composition Findings covering this co-activation |
| `predicates[] {id, value, context_sha256}` | values at offer; dispatch values are per invocation |
| `resolved[] {service_key, provider_decl_hash}`, `resolved_dependencies[]` | the committed view |
| `overlays[] {ref, sha256}` | the overlays pinned at the freeze; an overlay not listed is not loaded in this sprint (v2.1) |
| `fallbacks[] {decl_hash, verdict_ref}` | pre-approved alternatives, each with its own Verdict and predicates, frozen with the plan; AI4Research's freeze already records `approved_fallback_capsule_ids` (`code` `elastic_planner.py:5886-5888`) (v2.1) |
| `evaluator_version`, `vocabulary_version` | the predicate evaluator and vocabulary the values were computed with, so filter and dispatch provably ran the same code (v2.1) |
| `invocations[]` | dispatch appends one per actual run (v2.5; below) |
| `prev_hash` | ledger integrity [ind] |

**Invocations** (dispatch appends; v2.5). One entry per actual run: each fan-out item, each attempt, each fallback.

| Field | Why |
|---|---|
| `invocation_id`, `item_key` (fan-out item, or none), `attempt` | a retry is a new invocation with `attempt + 1`; today attempts overwrite a mutable state file, keeping the last 20 (`code` `task_lifecycle.py:54-56`, `:305-335`) |
| `decl_hash` run | the primary, or the pre-approved fallback used. Today's frozen fallbacks are never read at run time (`code` only `elastic_planner.py:5886`, `apo_plan_compiler.py:819`, `static_execution_compiler.py:391` mention them) |
| `operator`, `lease_ref`, `session_ref`, `turn_ref`, `model {model_id, version, params}` | the worker the workflow assigned; the openJiuwen session, and the harness-protocol Turn or item that ran it (§4.17a); routing's choice |
| `predicates[] {id, value, context_sha256}` | values at dispatch, on fresh state |
| `inputs_hash`, `output_hash`, `upstream[]`, `step_identity = h(decl_hash, inputs, predecessors)` | a change invalidates exactly the downstream runs (2605.06365 p6-7) |
| `gate_verdicts[] {check_id, source: step, capsule or artifact_type, runner_sha256, result}`, `exit {predicate id or none}`, `outcome`, `observed_cost`; `trajectory_ref` (required when exempt) | nodes retry and gates repair (`code` `elastic_planner.py:5871`, `:6818-6826`) |
| `compensation_ref`, `remote_fingerprint` seen | the undo path of a compensable run; the interface a remote body showed at dispatch (v2.6) |
| `claims[] {claim_id, status: supported, unsupported, stale; reason: judge_unmeasured, judge_demoted, exempt, input_unsupported, revoked (v2.8)}` | ties delivered claims to the run that produced them, and says why a claim is not fully supported, so a reader can weigh it: `judge_unmeasured`, a gating judge on it had no calibration, or its bound exceeded the step's `judge_tolerance`; `judge_demoted`, its judge later dropped a standing (§4.5c); `exempt`, it came from a generalist; `input_unsupported`, it rests on an input that is not supported; `revoked`, its capsule was revoked (the claim is also `stale`). A generalist run's claims are `unsupported`; revocation makes them `stale`; a claim resting on an unsupported or stale input is at most `unsupported` (v2.3) |

Past performance is counted per invocation, so fan-out and retries are visible to the librarian; gap recurrence still
counts sprints (§3.6).

agent-core keeps load records in memory (`code` `harness/deep_agent.py:314`), so a capsule-layer rail writes Bindings
and their invocations to a durable store.

### 3.6 Finding (the planner for gaps; screeners, auditors, probes, verification; append-only)

| Field | Type |
|---|---|
| `kind` | composition, conflict_observed, overlap, drift, audit_violation, use_outcome, gap, fit_failure (v2.7), verifier_audit, build_decision, build_failed |
| `visibility` | `all`, or `builder_hidden`: replay and suite details that would leak held-out cases, readable by the gate, the suite author and the librarian, never by the build decision or implementation roles (v2.3) |
| `subjects[]` | `decl_hash`es (a set for composition); a verifier id for `verifier_audit` |
| `producer` | `{tool, version, model, thresholds}` |
| `measure {name, value, unit}`, `text`, `evidence_ref` | what the producing tool measured, e.g. a screener's plan-level risk or a verifier's false-pass rate. Evidence for the librarian's typed decision; never summed or read as a trust score (v2.6, inv 13) |
| `status` | plan_only, confirmed, refuted, unreviewed |
| `action` | none, block_set, move_to_suspect, revalidate, open_gap, audit_verifier |
| `prev_hash` | ledger integrity |

- **gap** is written by the planner, one Finding per instance (never updated in place). Aggregates across sprints
  are computed by the librarian's queries, not stored. Each instance carries:
  - `identity`: the artifact types consumed and produced, the effects requested, and the step's task type;
  - `sprint_id` and `stage`: recurrence counts distinct sprints per identity, not nodes, since parallel nodes in one
    plan are usually one need;
  - per instance, the generalist's cost (tokens, wall time) and a trajectory reference: its script, the sandbox write
    record and the gate results;
  - `near_miss`: a type-compatible capsule that was excluded or failed the step's gates;
  - `repair_generations`.
- **build_decision** records a "no build" with its reason. The same gap identity is reconsidered only after a policy
  number of further sprints. **build_failed** records an implementation that spent its submissions or time; the gap
  returns to the build decision (v2.3).

  A gap is emitted once per sprint, after the planner's bounded repair is exhausted (`code`
  `elastic_planner.py:4100-4152`).
- **verifier_audit** carries false-pass and false-fail rates per anchor kind, the corpus hash and the date. Defect
  injection is the method The Blind Curator shows works offline (2607.07436 p4-5, p15).
- **conflict_observed** can set `block_set` only after a policy threshold of independent co-occurrences (**design**).
- **composition** is §4.9.

---

## 4. Mechanisms

Code unless marked **[model]**.

### 4.0 Three clocks around one library

The records form one library that three loops share, each on its own clock (2026-09-15 report, App. G.2):

| Clock | Pace | Runs | Reads | Writes |
|---|---|---|---|---|
| **hot** (sprints) | every sprint; cheap and constant | offer, bind or generalist, freeze, dispatch | the snapshot its freeze pinned | Plan steps, Bindings, gap Findings |
| **cold** (build and admit) | when gaps recur, or an audit or duplicate starts an update; rare and expensive | the four roles of §4.12, then the librarian | gap Findings, audit Findings | Declarations, Verdicts; the librarian writes Standing, also on audit Findings: **the only writers of the library** |
| **audit** | on a schedule, ordered by blast radius and time since last checked | regression replay of every admitted capsule's held-out suite; drift probes; verifier audits; invariant checks on real outputs | Bindings, outputs, dependencies | Findings only; the librarian acts on them |

**Why they do not disturb one another:**

- Every read resolves a hash some freeze pinned (invariant 3).
- The cold path writes Declarations and Verdicts, and the librarian alone writes Standing.
- The audit loop only appends Findings.

So concurrent access needs no lock over the library. The hot path never waits for the cold path, and it must work even
if the cold path never admits anything. A capsule admitted while a sprint runs is selectable from the next sprint whose
snapshot is taken after admission: **the sprint is the reuse boundary**.

### 4.1 Admit

1. **Vocabulary and hashes.** Every name is in the vocabulary; the body's files match `body[]`.
2. **Checks out of reach** [ind]. A check is admission evidence only if its runner lies outside the capability's write
   scope, its signal comes from the harness, not from the capsule, and it is not self-owned. At least one acceptance
   check has an author other than the builder and is held out from the builder.
3. **Protected components.** A capsule may never write to what admission depends on:
   - the gate and its rules;
   - the held-out suites and their recorded results;
   - the logs and provenance records the gate reads;
   - the Declaration, Verdict and Standing stores.

   Declaring such a write is rejected (`EFFECT_ESCALATION`), and observing one is rejected (`EFFECT_OUT_OF_SCOPE`).
   The filter also excludes any capsule that declares one, as a new exclusion reason. Protection is by write access,
   not secrecy: the DGM node that gamed its checker had the checking functions hidden from it (2505.22954 p70).
4. **Sandbox run** within the declared `effects[].scope`; a write outside it fails with `EFFECT_OUT_OF_SCOPE`, and the
   run makes the effect claims `enforced` for that run.
5. **Level.**
   - *Provisional*: manifest valid, hashes match, binding loads, the sandbox run stays within effects, and at least one
     postcondition passes on inputs the capsule was not built from. Tests may come after the code. Where the output
     is semantic and no deterministic check exists, the postcondition may be a judged check of any standing (v2.8).
   - *Certified*: every output covered by an anchored check from an author who never saw the implementation (inv 5),
     the builder seeing at most pass or fail bits, judged checks under the false-pass ceiling, and predicate parity
     tested.
   - *Exempt* (v2.7): only for a Declaration with `exempt {reason: generalist}`. It is **enrolled**, not admitted on
     a job: the Verdict is ADMIT at level `exempt` when the body hashes match, it loads, the sandbox run stays within
     its declared effects, a write to a protected component is refused, and it completes a fixed set of sample step
     contracts under their gates (a smoke run of what plan gates will ask, **design**). Any failure is a REJECT with
     the usual typed reasons.
   - Why provisional and certified: 215 of 222 self-built tools failed every held-out test of their own job, and no in-session signal flagged
     them (2604.00392 p1, p5; Haiku 4.5, 3 tool-creating protocols, 3 seeds). The split is **design**.
6. **Screening** against likely co-activation partners (§4.9); a pending screen gives DEFER or admission with a narrower
   offer, as policy decides.
7. **Set-level value** [ind]. Replay a held-out set with the slot, with and without the candidate; a capsule that lowers
   the slot's joint result is rejected (`NEGATIVE_MARGINAL_GAIN`). Removing the marginal-gain gate cost 8 points in one
   run (2608.05810 Table 2, p6).
8. **Decision.** A conjunction over the checks the level requires; no score enters it (2609.16313 p6). Running without
   error is never an anchor. A judged verdict counts toward certification only from a `measured` judge under the
   false-pass ceiling. Any judge may admit at provisional (v2.8); the Verdict records its standing [ind].
9. **Write the Verdict**; the librarian moves the Standing.

### 4.2 Import existing capabilities [v1.6]

An importer fills every field it can derive and invents no guarantee. A person confirms the proposed writes, deletes,
emissions, executions and every `ext:` effect, and writes at least one postcondition; declared reads are accepted as
proposed (v2.8). The capsule enters as provisional.

| Source | Derived | Written to certify |
|---|---|---|
| agent-core `ToolCard` | name, description, inputs, the four flags, file hashes if local | outputs, postconditions |
| MCP server | each tool's name, description, schemas; effect proposals from its hints. agent-core's MCP client keeps only name, description and input schema (`code` `core/foundation/tool/mcp/client/sse_client.py:331-338`), so the importer reads the server's own list | postconditions |
| `SKILL.md` skill (jiuwenswarm, skillhub) | name, description, file hashes, skillhub version | inputs, outputs, postconditions |
| A2A agent | name, description, version, modes, URL | typed inputs and outputs, postconditions |
| old AI4Research manifest | contract, effects; prose invariants become checks only when a runner exists | a suite from an author who never saw the code |
| Symphony fingerprint, ScienceDiscovery package | typed inputs and outputs, hashes, revision | postconditions |
| jiuwenswarm SkillPack (`kind: skillpack`, `server/runtime/skill/skillpack.py:180-228`) | a composite: members from `skills:`, pinned to their current hashes at import; wiring from its workflow graph | the composite's own checks |
| Swarm (team) Skill (`docs/en/SwarmSkills.md:66-74`, `:339-374`) | a composite: `dependencies.yaml` skills and tools become pinned `capsule` dependencies (`required: false` becomes optional); `bind.md` limits become proposed `budget` and `effects` | effects confirmed; acceptance criteria as checks, or `declared` |
| RSI harness package (jiuwenswarm `agents/harness/common/rsi/harness_activation.py:715-772`) | `body[]` from the package, whose own SHA-256 (`:266-293`) is kept beside `decl_hash`; `lineage.parent` from the task's final node; RSI's publication as `builder_gate` | held-out checks from another author |

MCP listings and A2A cards are advertisements; a capsule wraps them and never treats the card as evidence [ind].

**Uses written into today's AI4Research manifests** (v2.5; invariant 12). Of the 85 capsule YAMLs, none carries a
step, node or sprint id, but uses are written in:

| Today's field | How many | In the schema |
|---|---|---|
| `applicability.task_types` | 85 of 85 | kept as import evidence in `lineage.provenance`; never read by the filter. Input limits become `needs.when` predicates over inputs |
| `composition.requires_after` naming a capsule | 42 of 85 (46 with any entry), e.g. `cap.research-report-draft` requires `cap.research-evidence-synthesis` | a data dependency when an artifact connects them: an input port of the type the other produces. Otherwise dropped, with a note: ordering is the plan's `depends_on` |
| `requires_after` naming a guard | 4 of 85 | a pinned `capsule` dependency |
| `operator_compatibility.preferred` | named worker operators | dropped. What the capability truly needs becomes `needs.resources` or a carrier requirement; the worker is assigned by the workflow and recorded in the invocation |
| workflow position in the name or description | 14 of 85 (11 in `metadata.name`, e.g. "Fixed Research Evidence Synthesis"; 3 in the description, e.g. "Freeze the accepted Part A evidence … for Part B consumption") | the importer proposes a neutral `summary`; a person confirms it |

Registered workflows name capsules per stage (`allowed_capsules`, `code` `config/workflows/*.workflow.json`). That is
a demand-side choice and becomes the Plan step's `restrict_to[]`.

Import rules added in v2.1, from the jiuwenswarm corpus (34 bundled skills; none declares inputs, outputs,
preconditions or effects; 9 descriptions exceed 400 characters; `DERIVATION.md` D1-D5):

- `allowed_tools` is a proposal for `effects`, never enforcement: agent-core's skill loader reads only the description
  (`code` `harness/rails/skills/skill_use_rail.py:946-958`).
- Model fields (`models.recommended`, `models.compatible`) are never a choice routing must follow. `compatible` may seed
  `models_used` only after the capsule's checks pass on those models.
- A description over 400 characters gets a proposed `summary`, confirmed by a person. The full text stays in the
  body.

### 4.3 Offer: the executability filter and predicate parity

At each choice point, code evaluates the planning-evaluable `needs.when`, `resources`, `network`, `model`, the step's
`restrict_to[]` if any, the level against the step's `requires_certified`, and any `block_set` Findings for capsules already bound.

- `false`: excluded, with a reason; recorded in `blocked[]`.
- `unknown` on a `defer` predicate: held out, and a typed request is raised.
- `true`: offered. The chooser sees `summary` and `ports` only.

**Predicate parity** (2608.01050 p2-3, p5-6) [v1.6]. One declared predicate, three evaluators: the filter (planning), the
dispatch check (fresh state), and the capability's own exit logic (tested at certification at the boundary, with
missing and stale state). Filter and dispatch share one evaluator by construction (inv 8). A predicate enters the
filter only after its parity check passes; until then it is checked at dispatch only. Parity is a release invariant:
any change to exit logic or a predicate is a new revision. A body that stops on a declared predicate reports its id in
the invocation's `exit`. The paper's three failure modes map to records: predicate drift to `exit` and parity results,
state staleness to `blocked[]` at dispatch, backend drift to `drift` Findings. The guarantee is one-sided: passing the
filter does not mean success. Passing grants no right to any effect, and hiding what cannot run does not replace
access control (p2).

**Tokens.** A removed capsule shrinks from a full catalog row to a one-line exclusion. In the paper the gate removed
59.1% of description tokens after relevance matching, 90.5% combined (2608.01050 p1, p4-5; ten skills, one month,
description tokens only). In Contract2Tool, contract-based filtering used 2,528 tokens a task at 0.980 success,
against 26,172 at 0.775 for all tools and 4,482 at 0.620 for a keyword filter (2606.07904 Table V, p8; synthetic
registry). In AI4Research the binding prompt carries every eligible capsule's full row, again on repair (`code`
`elastic_planner.py:4678-4724`, `:4949`). The saving is measured in M2 against today's filter, with false blocks and
task success beside it, not assumed.

Ranking inside the offer is a tool the scheme uses under these rules; it never re-admits what the filter excluded.

### 4.3a Plan assembly and scheduling (v2.5)

The workflow keeps its shape. Each stage below is today's AI4Research code (`b0bf165f9`), and says what the schema
adds and who owns it. **Demand and supply stay apart until the freeze:** the planner states what each node needs,
capsules state what they can do, and only the Binding joins them.

| # | Stage | Owner | Today | What the schema adds |
|---|---|---|---|---|
| 1 | **Write the plan** | the planner (model, then code) | a model writes the PlanIR and may not name a capsule (`elastic_planner.py:1328-1329`); it sees the capsules' port catalog (`:1431`) | Plan steps: typed inputs and outputs, allowed effects, `task_type`, `depends_on`, optional `over`. The planner sees the library only as the **set of port types available**, never as capsule ids |
| 2 | **Repair the plan against supply** | the planner, from code's defect | a node no capsule chain can implement returns `CAPABILITY_IMPLEMENTATION_MISMATCH` to the model (`:4137-4146`) | unchanged: supply may reshape the plan, but only through types |
| 3 | **Expand by composition** | code | a node becomes a chain of support steps with ids `<parent>__<sha8>_cNN` (`:5922`, `:5915-5919`); a capsule appears at most once in a chain (`capsule_composition.py:340`, `:559`) | derived Plan steps (`derived_from`), each matched on its own; one capsule may fill several. A chain worth reusing is built as a composite, with members keyed by role |
| 4 | **Offer and choose** per step | the capsule layer's filter (code), then the chooser and fit reviewer (models) | a filter on types and effects, then a model reads full catalog rows (§0.5) | §4.3: stage-1 criteria on declared fields, then a choice from `summary` and `ports` |
| 5 | **Freeze** | the freeze (code) | `freeze_node` pins the manifest and `source_sha256` (`execution_authority.py:28-44`, `:47-69`) | one Binding per step: `bound[]` with roles, fallbacks, overlays, `plan_hash` (§3.5, §4.4) |
| 6 | **Schedule** | the workflow's scheduler (code), not CC | ready nodes in topological order (`graph_scheduler.py:2179-2215`); at most 8 in parallel (`graph_node_dispatcher.py:2391-2399`); conflicting write scopes or effects held back (`graph_scheduler.py:3203`); one lease per operator (`operator_runtime.py:504-515`); retries from the node's `failure_policy` (`graph_node_dispatcher.py:5658-5714`) | constraints only: declared write scopes and `resources` modes, and the gate's `parallel_safe` flag for concurrent instances of one capsule. Order, the cap, worker assignment and the retry count stay the workflow's; a retry count belongs to the step, never to a capsule |
| 7 | **Dispatch** | dispatch (code) | a `dispatch_id` per run (`graph_scheduler.py:4149`); predicates checked against the envelope (`capability_capsules.py:1220-1242`) | one invocation per actual run: predicates on fresh state, hash check, the fallback path when the primary cannot run (§3.5, §4.5) |
| 8 | **Gates and delivery** | the workflow's gates | gates per node | declared checks on outputs; each claim keeps the invocation that produced it |

**Fan-out** (a Plan step with `over`). Each item of the collection is one invocation with its `item_key`. Items run
in parallel up to the smallest of the step's `max_parallel`, the sprint's cap and the workers free, and one at a time if
the capsule is not `parallel_safe` or declares an `exclusive` resource. Effect scopes may use `{instance}`, a path
under the invocation's own workspace, so parallel items never write the same place. Outputs are gathered in item
order into `collection<U>`, with a manifest `items[] {item_key, invocation_id, status}`.

- **When some items fail.** Each item retries under the step's `failure_policy`, as far as the capsule's class allows
  (§4.5a). Then `gather.mode` decides: `all` fails the step if any item failed, so nothing downstream sees a partial
  collection; `best_effort` passes the items that succeeded, lists the rest as `failed` in the manifest, and fails the
  step if fewer than `min_items` succeeded. The default is `all`.
- **The collection is checked as a whole.** Before a downstream step consumes it, the step's gate checks the manifest
  in code: every expected `item_key` present exactly once, each with a terminal status, and the `gather` rule met.
  Checks on the capsule still run per invocation (`over: each_call`). A claim built on a `best_effort` collection
  names the manifest, so a reader sees which items are missing.

Today there is no fan-out: a `many` output is one run writing a directory
(`elastic_planner.py:1366-1378`). That stays valid for a capsule whose port takes a collection.

**The same capsule many times.** One Declaration may be bound to many steps in one plan, and to steps in many
sprints; each step has its own Binding and each run its own invocation, so step identity keeps them apart. Within a
sprint, a name resolves to one hash (the snapshot); concurrent sprints may run different versions of it.

**Why this split** (**design**, from the records' writer rule, inv 9): a task written into a capsule makes the capsule
specific, so it can no longer be reused where its ports fit. It also puts plan facts where the builder, not the
planner, writes them. Today's `requires_after` is an example: 42 capsules name the capsule that must run before them,
which fixes the plan's order inside the supply.

### 4.4 Bind and freeze

- **[model]** The chooser binds each step to one capsule from its offer, or to none. With an empty offer after repair,
  the step binds to one of the generalists the run contract names, if it allows them (§4.14).
- **Scheduling by write scope.** The scheduler never runs two steps together whose declared write scopes overlap, and
  treats a step with no declared write scope as an exclusive writer. This is the space half of composability inside a
  sprint, and it bounds generalist steps too (2026-09-15 report §4.1).
- Code checks port types across the plan, the level, admission state and resolved services, and writes Bindings.
- The freeze checks each Binding against the sprint's **snapshot**, not the live Standing. An admission, supersession
  or deprecation during planning changes nothing for this sprint. The freeze rejects a hash only if, since the snapshot,
  it became `suspect` or `revoked` (v2.3). This removes today's abort; AI4Research today
  rejects capsules changed during planning (`code` `execution_authority.py:81-94`) and admits only `stable`
  (`:55-56`), and treats a missing status as stable (`capability_admission.py:14`).
- Model candidates are frozen with the plan (`code` `execution_authority.py:24-25`, `:47-69`); routing picks among
  them, from `models_used` when it is non-empty. A step accepting provisional capsules may run another model, recorded,
  which raises revalidation; any other step is blocked.

### 4.5 Dispatch

Dispatch re-runs the same predicate code over fresh state and appends the values. `true` to `false` refuses; to
`unknown` defers. The live hash must equal the pin (new). Credentials and service health are observed here, never
frozen. The capsule layer checks body hashes and loads from the content-addressed store, because agent-core's binder
loads by name with no hash check (`code` `harness/extension_binder.py:27-60`). For skills, the offer is applied through
`SkillUseRail`'s `enabled_skills` allow-list (`code` `harness/rails/skills/skill_use_rail.py:78`, `:95`, `:255-259`) [ind].

**Enforcement at tool-call level** (v2.1, narrowed after review). agent-core has rails that reject tool calls outside
an allow-list: `VerificationRail` (`code` `harness/rails/subagent/verification_rail.py:166-220`) and `AgentModeRail`
(`harness/rails/agent_mode_rail.py:510`). A capsule-layer rail of the same pattern can enforce the *set of tools* a
bound capsule may call. For example, no `bash` for a capsule that declares no `execute` effect. That makes the tool set
`enforced`, but not the effects behind it:

- `bash` reaches any path, and `VerificationRail` guards paths only for read tools (`:33-57`). Skills are given `bash`
  by default (`harness/rails/skills/skill_use_rail.py:77`, `:94`).
- `mcp__*` tools pass unconditionally (`:180-186`).
- Capsules loaded into one shared context cannot be told apart per call. Attribution needs `load_mode: invoked`, or one
  capsule per agent context.

So file, network and execute effects are `enforced` only in the sandbox. At tool-call level they are `audited`. A
carrier may not bring its own rails: `PluginSpec` can carry rails into the same agent
(`harness/extension_binder.py:45-46`), which would put a capsule in reach of the checks (invariant 4). The gate rejects
a carrier with rails.

**Overlays at dispatch.** Only overlays pinned in the Binding are loaded. An overlay written during the sprint, for
example by a teammate's automatic experience save, reaches the next sprint only as a new provisional revision.
agent-core has overlays of its own:

- `SkillUseRail` appends evolution-experience text, fetched by skill name, to what the chooser reads
  (`harness/rails/skills/skill_use_rail.py:389-409`).
- Its `max_total_chars` cap drops skills by keyword overlap after the offer (`:526-575`).

For AI4Research sprints, the first is pinned as an overlay or switched off, and the second is switched off: the offer
is the filter's, not a heuristic's (invariant 8).

**A dispatch-time DEFER** (**design**). The step waits up to its predicate's `max_age_s` for the missing fact. It then
moves to the first pre-approved fallback whose predicates hold. Failing that, it fails with `precondition_unknown`, and
the typed request goes to the sprint's owner.

### 4.5a State, undo and the author's liability (v2.6)

**Who answers for what** (invariant 13). What a capability does behind its interface is the author's: the schema
cannot see inside a remote database, and CC does not guess. The author declares up front what it touches
(`resource_key`, `ext:` or `ws:`), whether each change is `idempotent`, how it is undone or that it cannot be
(`reversibility`), how far it reaches (`risk.blast_radius`), and the class of the whole (`effect_class`). CC answers
for checking that declaration against what it observes, before use where it can and on every run after. Declaring
first means a stateful or irreversible capability is known to be one before a sprint relies on it, not found out
after a bad run.

**What verification checks** (tools the scheme uses, §4.1):

| Declared | Checked by | On mismatch |
|---|---|---|
| effects and their scopes | the sandbox run at admission; tool-call observation on every invocation (§4.5) | `EFFECT_OUT_OF_SCOPE` at admission; afterwards an `audit_violation` Finding and `EFFECT_VIOLATION` |
| `idempotent` | the gate runs the capability twice on the same inputs in the sandbox and compares the state | `IDEMPOTENCE_FAILED` |
| `compensate:{capsule}` or `inverse` | certification runs the effect, then the compensation, and compares the state with the state before (already required once, §4.6) | `COMPENSATION_FAILED` |
| `effect_class` | the gate, against the effects; the audit, against observed runs | `EFFECT_CLASS_INCONSISTENT` at admission; afterwards `CLASS_VIOLATION` |
| a remote body's interface | `remote_fingerprint` compared at every dispatch | the run is refused and the Standing moves to `suspect`, reason `REMOTE_CHANGED` |

A remote body can still change its behaviour behind an unchanged interface. That is the author's, and the provider's,
to declare. CC finds it only by observation (tool-call audit, drift probes), so a remote capability's effects are at
most `audited`, unless a sandbox or network proxy enforces them.

**No numeric trust score** (Muk, 2026-09-22; §5). Every mismatch is a typed reason on the Verdict or a Finding, and a
Standing move toward less authority (§4.8), recorded with `lineage.builder`. A score would let good results buy out
a broken declaration (2609.16313).

**What composition may do, by class:**

| | `pure` | `idempotent` | `compensable` | `irreversible` |
|---|---|---|---|---|
| automatic retry (a new invocation) | yes | yes | only after its compensation ran and was checked | no: a named person decides |
| fan-out in parallel | if `parallel_safe` | if `parallel_safe` | if `parallel_safe` and each item's compensation is recorded | one item at a time, and only if the step allows it |
| exploration quota, speculative runs | yes | yes | no | no |
| inputs it may act on | any | any | any | only `supported` claims: no provisional, generalist or stale input |
| approval | none | none | none | the step must allow the effect and the run contract's `effect_ceiling` must include it; with `risk.severity: high` a named person approves, and an unattended run blocks (§4.15) |

A compensable invocation records `compensation_ref`, the compensating capsule's hash, so the undo path is known for
every run. Undeclared behaviour is treated as `irreversible` until an audit says otherwise.

**Context taint.** Loading a capsule into an agent's context cannot be undone within that context: what it put there
shaped every later decision. So a `context_injected` capsule, or any capsule in `bound[]` with role `context`, counts
like the primary for revocation. When its hash is revoked for a reason that makes evidence stale (§4.7), every
invocation it shared a context with is traced and its claims become `stale`. A context that held a revoked hash is never reused: the next invocation starts a fresh
one. Tool outputs enter the context as quoted data, never as instructions. What cannot be traced this way is a
poisoning that leaves no claim, so the screener limits how many `context_injected` capsules share one context (§4.9).

### 4.5b Node gates: who writes each part (v2.7) [M2]

Every node must pass its gate after it runs. The gate is compiled in code at the freeze, hashed into the Binding
(`evaluation_plan_hash`), and made of three parts, each written by a different party:

| Part | Written by | In the schema | Today in AI4Research |
|---|---|---|---|
| **step acceptance**: what this request needs | the requirement compiler, from the user's request | the Plan step's `requires.acceptance[]` | each requirement names a check from a shared registry of 43 checks, 23 deterministic and 20 semantic (`code` `config/evaluation-checks.v1.json`; `evaluation_plan.py:277-312`) |
| **capsule checks**: what the capability promised | the promise by the Declaration's author; each runner by the check's `author`, never the builder for a certified capsule | each output's `check_id`, `guarantees.checks` with `over: each_call` or `outputs` | the manifest's `self_check`, `pass_conditions` and `postconditions` as text; a text not in the registry becomes a model-judged review item (`apo_plan_compiler.py:262-290`; `evaluation_plan.py:322-340`) |
| **artifact-type checks**: what every output of a type must satisfy | the vocabulary's owner | the output types | registry checks marked `auto_apply` (`evaluation_plan.py:314-319`) |

**Rules.**

- **Every gating check has a runner with a hash.** A promise with no runner is `declared`: it sits in `unanchored` and
  cannot gate. **Every judged check gates** (v2.8): a failing verdict fails the node, as today, whatever the judge's
  standing; the standing decides what a pass supports (§4.5c). Today a node with no criteria gets a default model
  judge of its objective (`evaluation_plan.py:352-356`); that stays, and its passes are labelled `judge_unmeasured`
  until it is calibrated. Only a step that sets `require_anchored` needs a deterministic, reference or calibrated
  check to freeze.
- **`self_check` is dropped** (§3.1): a check the capability runs on itself is never evidence (2604.00392 p5).
- **The gate policy is the step's:** how many repairs, and what a failure does. Today it defaults to a model judge that
  repairs once, then fails (`elastic_planner.py:5871`).

**Will an admitted capsule pass?** Its own part, very likely: it passed the same runners at admission, on inputs it
was not built from, and each later failure is a `use_outcome` Finding against its hash (repeated failures move it to
`suspect`, CONFORMANCE_FAILED). The step's part, not necessarily: it tests what this request needs, which the capsule
never declared. So the gate is not redundant with admission. Admission checks the capability on samples; the gate
checks this run's outputs on this run's inputs.

**Blame goes to the right party.** Each `gate_verdicts[]` entry names its `source`. A failed capsule check counts
against the capsule. A failed step check with the capsule's own checks passing is a fit failure: the offer, the
chooser or the fit review bound a capsule that does not meet this need. It is recorded as a `fit_failure`
Finding, a near miss that counts toward the step's gap identity (§4.12), not against the capsule's Standing.

**Exempt capsules** (§4.14) have no capsule part of their own. They bind only where the step and artifact-type parts
cover every output deterministically or against a reference.

### 4.5c Judges, and quality as a rate [M3]

**Sharpened, v2.9: block a regression, label a capsule with no better replacement.** The loose form of
invariant 14 is the minority position in release engineering, and the deck should say so before anyone
else does. Google's SRE error budget policy halts all changes other than P0 and security fixes once the
budget is spent; SRE canarying pauses and rolls back on a bad canary; AWS pipelines roll back on the
high-severity alarm during bake time; Kayenta fails a canary below its marginal threshold.

What each of those blocks, however, is a **new change**, while the last known-good version keeps serving.
None removes a capability outright. So the rule splits in three:

1. **A regression against a known-good version is blocked.** A new version measuring worse than the one
   it would replace does not take its place. This matches industry exactly.
2. **A capsule with no better replacement is labelled, not blocked.** Blocking the only version of a
   capability has no support in any of those sources, and it is the case this schema is about: research
   steps whose outputs can only be judged, where refusing to run means the work does not happen.
3. **Safety blocks unconditionally**, replacement or not: hash mismatch, protected write, an effect
   outside the declaration, an irreversible effect without approval, a revoked capsule.

**The one place labelling does not apply is the judge itself.** A judge that fails its own calibration is
**removed from gating**, not labelled: in crowdsourcing a worker who falls below the accuracy threshold
on hidden test questions is removed from the job and their judgments are discarded, and keeping a failing
checker in service behind a warning has no precedent. Label the capsule; remove the judge.

**Deprecate and revoke stay separate**, as Kubernetes separates them: a failed *readiness* probe takes a
pod out of the Service endpoints while the container keeps running, and a failed *liveness* probe
restarts it. A capsule that is merely poor stops being offered. Only safety revokes.

**Over-blocking is itself a failure mode, and industry guards against it.** Envoy's panic threshold (50%
by default) makes the load balancer *disregard health status entirely* when too few hosts are healthy,
and `max_ejection_percent` refuses an ejection that would push the cluster past a cap. A library that
blocks its way down to nothing is the same failure.


**Quality is a rate over a window, never a verdict (v2.9).** Verification has three layers, and they are
different problems:

| Layer | The question | Shape of the answer |
|---|---|---|
| Conformance | Is it what it says it is? | binary, static and on the first run |
| Correctness | Does it do its job on cases it has not seen? | binary, per case |
| **Quality** | Is it good **often enough**, over time? | **a rate over a window** |

What this requires of the schema:

- **A declared quality criterion per output**, separate from its correctness check: a rubric or a named
  judge plus a target, so "good" has a stated meaning rather than one inferred afterwards.
- **A declared minimum number of observations** before the quality claim means anything. Sprints are
  expensive, so there will be tens of runs, not millions, and a rate over three runs is noise. Below the
  minimum the claim is labelled `unmeasured`, and **unmeasured is never silently treated as passing**.
- **A named judge whose own calibration is recorded**, because semantic outputs can only be judged.
  Judges are never capsules (§4.10).
- **Standing carries the distribution**: what moves is a quality rate over a window, not a pass or fail.

This is why a merged capsule cannot inherit a quality record from its members (§4.9a).


**The problem.** Most AI4Research outputs are semantic: literature syntheses, analyses, hypotheses, drafts. They can
only be judged, and today's registry already has 20 semantic checks among its 43 (`code`
`config/evaluation-checks.v1.json`). A lenient judge fails silently: under false-pass bias, retirement by the
contribution rule stopped while raw deprecations looked normal (2607.07436 Table 1, p6). And the verdict depends on
the model: the same audit marked 45% of skills conditional with one model and 5% with another (2603.21019 Table 2).
If an unmeasured judge could not gate, most research steps would have nothing admissible; if it could certify, a
lenient judge would certify silently.

**The resolution.** A judge always gates, and its **standing** decides what a pass is worth. Standing is recorded per
judge, per model and per artifact type, in the Verdict's `verifiers[]`:

| Standing | How it is reached | What a pass supports |
|---|---|---|
| **unmeasured** | the default | the node passes and runs on; claims resting on it are `unsupported`, reason `judge_unmeasured` |
| **calibrated** | at least 30 items of that artifact type, about half with injected defects, and the false-pass rate's upper bound recorded (**design**) | claims `supported`, assurance `audited`, when the upper bound is within the step's `judge_tolerance` (0.2 by default, **design**) |
| **measured** | at least 200 items, and the upper bound under the certification ceiling (0.05 by default) (**design**) | counts toward certification |

- **Calibration happens through use.** A small share of judged passes (5% by default, **design**) is re-checked by a
  person or by a reference check, and each re-check becomes a calibration item. So a judge moves from unmeasured to
  calibrated in normal sprints, and nothing waits for the full certification suites of M3. Defect injection is the
  method The Blind Curator shows works (2607.07436 p4-5, p15).
- **A disagreement found by a spot check** writes a `verifier_audit` Finding; a judge whose upper bound rises past its
  standing drops a standing, and the claims it passed since its last check are re-labelled `judge_demoted`.
- **Retirement still needs a measured judge** (§4.13), because retirement is where a lenient judge does silent harm.
- **Why a label, not a block.** Refusing on missing evidence costs work: in Cognitive Admission Control, a controller
  that could not fetch missing evidence completed 90 of 120 effects, against 120 when it deferred and fetched it
  (2609.16313 p10). A labelled claim keeps
  the work and tells the reader exactly how far to trust it.

### 4.6 Composability in space and time (2608.25512) [M5]

**"Uninstall" means no longer routed, and drained. It never means gone (v2.9).** No runtime checked makes
the stronger promise: POSIX states that "a successful return from `dlclose()` does not guarantee that the
symbols associated with handle are removed"; musl makes `dlclose` a deliberate no-op; the Java Language
Specification (§12.7) makes class unloading optional and dependent on the class loader becoming
collectable; .NET's collectible load contexts unload **cooperatively**, so `Unload()` only *initiates*
it; OSGi keeps a "pending removal" wiring and its class loader until dependents are refreshed; Erlang,
the best-known hot-swap system, purges old code by **terminating the processes still running it**; and a
forced Linux module unload sets the kernel taint flag. The design therefore follows Kubernetes' shape --
stop offering it, run the shutdown path, drain in-flight work, and reclaim on restart -- and claims
nothing about the old code having ceased to exist inside a running process.


Cordis names two needs of dynamically composed systems: temporal (removing a component reverses what it did) and
spatial (components declare and resolve dependencies, and their lifecycles follow them) (p4-6). It is a formal model
with one qualitative case study, and agent harnesses are its future work (p69, p82): this schema borrows its vocabulary
and boundary, not a measured result. Reversal holds only inside a system boundary; emissions can only be withheld or
compensated (p70-71).

| Operation | How the schema does it | Where it cannot |
|---|---|---|
| **Add** | admitted; its `injects` must be satisfied by admitted providers or be optional; cycles among `injects`/`provides` are rejected | |
| **Replace** | a new version (§4.7): new hash, new Verdict, monotone; plus **replacement compatibility**: outputs cover every port an admitted dependent consumes, `provides` covers every injected key within range; **no new powers**: no new write, delete or emission without re-screening [ind] | frozen sprints keep the old hash on purpose |
| **Revert** | Standing to `previous[0]`, with a valid Verdict under the current epoch; `rollback_of` activates at once | emissions made meanwhile are not undone |
| **Remove** | stop offering (deprecated), then retire only when no admitted capsule injects a key it alone provides; agent-core undoes registrations in reverse order (H1) | Cordis does not check that an inverse is correct (p58-59); certification exercises each declared inverse and compensation once |

Composition happens **between sprints, not within one**: a sprint keeps what it pinned (inv 3). Removing a capsule
undoes its registrations, never what it did to `ext:` state or to a context it was in: those are §4.5a's. Effects are declared,
compared with what was observed, and sandboxed where needed; Cordis too leaves sandboxing to a mechanism outside the
language (p72-73). Cordis leaves dependency compatibility by structural contracts open and notes semver cannot be
enforced (p75-76); `interface_version_range` and pinned dependencies fill that gap.

### 4.7 Revise, revert, revoke

- **Revise:** one rule, the new-version row below, which includes §4.6's replacement compatibility. A candidate
  that is not monotone or not compatible is rejected as a version (`NOT_MONOTONE`), and may be re-proposed as a
  specialisation or a new capsule.
- **Five ways to update** (2026-09-15 report, App. G.7, plus import in v2.8). A near-miss gap, an audit failure or a
  duplicate rejection starts an update, and the build decision chooses one, trying import first:

  | Option | When | Admitted if |
  |---|---|---|
  | **import** (v2.8, tried first) | an existing capability already does what the gap needs: another AI4Research manifest, a jiuwenswarm or skillhub skill, an MCP server | the import path of §4.2, entering as provisional |
  | **new version** (`supersedes`) | contract types unchanged and no effect added | it passes its predecessor's whole regression suite **and** new cases for the gap. Versions are **monotone**: nothing the predecessor passed may fail (**design**, after SkillDAG's rule that online edits keep prior hits, 2606.03056, and DGM's archive rule, 2505.22954 §4.2) |
  | **specialisation** (`specialises`, new name) | a narrower applicability of the same capability | it passes its own held-out suite; the parent stays |
  | **new capsule** | the contract changes, or nothing similar exists | full admission |
  | **no build** | the gap is rare, or its trajectories disagree | always valid (2607.23332) |

- **Suites travel with the lineage** (v2.7). The Verdict's `suites[]` lists every suite a hash was checked with. A
  child (`supersedes`, or `specialises` for the parent's cases whose inputs satisfy the child's `needs.when`) inherits
  them by reference. A child with `co_parents` also inherits each co-parent's suites, restricted to the cases whose
  inputs satisfy the child's ports and `needs.when`. Building the child, RSI:
  - reads the **visible** suites in full, and may add its own cases, which join the child's visible suites;
  - sees the **sealed** suites only as pass or fail per check, never their contents.

  The child is better than its parent when it passes every inherited suite, visible and sealed, its new cases, and a
  **fresh held-out addition** written by verification for this generation, and its contribution against the pool is
  at least the parent's. Failing an inherited suite is `INHERITED_SUITE_FAILED`. RSI's own cases are builder
  evidence: they can reject a child, never certify it. The fresh addition keeps a lineage from fitting only the
  suites it can read: in one case, hacking appeared when checked functions were visible (2505.22954 p70; a 3-task side experiment, not a measured rate).
- **Activation** [v1.6]: a first revision activates on admission. An admitted new version activates if it improves on
  the baseline snapshot (2608.05810 p5-6); otherwise it is `admitted_inactive`. On activation the predecessor moves to
  `deprecated` (SUPERSEDED), and is retired and unloaded once no frozen plan resolves it. The duplicate check never
  compares a version with the predecessor it versions.
- **Concurrency** (v2.1): Standing moves are serialised per name and logged; a sprint reads one `snapshot_id`; a
  revert waits while a builder task on the same name is active, as RSI's rollback already does (`code` jiuwenswarm
  `agents/harness/common/rsi/harness_activation.py:682-692`).
- **Migration** (v2.1, **design**): moving a Declaration to a new `schema_version` is a new Declaration with
  `relation: migrated_from`. It keeps its Verdict only if every check id and runner hash is unchanged.
- **Revoke, retire, and running plans: one policy, by reason** (2026-09-15 report, App. G.6):

  | Reason | Running steps | Evidence already produced | Lineage |
  |---|---|---|---|
  | SUPERSEDED, deprecated, redundant | finish | valid | unaffected |
  | DEMOTED_TASK_SUCCESS | finish | valid | unaffected; the capsule becomes `admitted_inactive` |
  | CONFORMANCE_FAILED | finish, flagged | claims downstream become `stale` | unaffected |
  | EFFECT_VIOLATION | abort; the capsule is quarantined | `stale` and audited | unaffected |
  | PROVENANCE_REVOKED, REVOKED_SECURITY, REVOKED_HARM | abort | `stale` | every capsule with it in `context_capsules` becomes `suspect` [ind]; so does every descendant through `parent` or `co_parents`. A descendant whose builder did not report `context_capsules` is traced through its parents only, and the tree index shows it as `context_unreported` (v2.7) |

  **Which runs a revocation reaches** (v2.6). Every invocation whose Binding lists the hash in `bound[]`, whatever its
  role (primary, context or dependency), and every invocation that ran it as a fallback. "Evidence already produced"
  above applies to all of them: a context capsule shaped the run as much as the primary did (§4.5a). This is the
  run-time context. The Lineage column is different: `lineage.context_capsules` is what the *builder* had in context
  when it built another capsule.

  Pinned steps not yet dispatched are blocked, as today (`code` `capability_capsules.py:1318-1319`). Inverse and
  compensation actions are offered to a named person, never run automatically, and never on unattended runs
  (**design**).

### 4.8 Standing transitions

```
proposed --build--> candidate --ADMIT--> admitted (or admitted_inactive until it improves)
candidate --REJECT--> retired
admitted --drift | block | member unavailable--> suspect --revalidate ADMIT--> admitted
admitted --replay fails | invariant violated (CONFORMANCE_FAILED)--> suspect --revalidate REJECT--> retired
admitted --task success declines (DEMOTED_TASK_SUCCESS)--> admitted_inactive
admitted --superseded | cap--> deprecated or outside_cap --no dependents, no frozen plan resolves it--> retired
admitted --REMOTE_CHANGED | CLASS_VIOLATION--> suspect --revalidate ADMIT (new fingerprint or class, checks re-run)--> admitted
suspect --CLASS_VIOLATION with an undeclared effect--> revoked (EFFECT_VIOLATION)
any --EFFECT_VIOLATION | PROVENANCE_REVOKED | security | harm--> revoked
(every move is written by the librarian; a Finding can cause a move only toward less authority)
```

### 4.9 Composition screening (2607.02345)

Capsules are **screened together, never certified together**: severity is compositional, not additive (Fig. 6, p9).
The schema supplies, authored and tested, what SkillFuzz had to extract from instruction prose with a model (p4):

| SkillFuzz reads | The schema supplies |
|---|---|
| preconditions, postconditions | `needs.when`, `guarantees.checks` |
| modifies set | `effects` of kind write, create, delete, with scopes |
| invariants | `changes.invariants`, and checks `over: each_call` |
| domain scope, abstract actions | typed ports and `needs.when` predicates over inputs, `summary`; effect kinds, `kind` |
| extraction confidence | the Verdict's level and each claim's assurance; provisional and `declared`-heavy capsules first |
| which skills share a context | `load_mode: context_injected`; the Binding's `bound[]` with role `context` |
| shared services | `injects`, `provides`, `commutative` [ind] |

Two passes run in code before any model [ind]: resource overlap (two capsules writing one resource, or one deleting
what another reads) and invariant clash. The model search then runs over sets ranked by these, as SkillFuzz's seed
ranking does. Findings are `composition` Findings keyed by the set of hashes, `plan_only` until execution confirms or
refutes them: 80.6% of SkillFuzz's high-risk plan flags were confirmed in execution (Table II, p6-7; one run per
condition). A step never co-loads a confirmed high-severity set; a plan-only set needs a named person's approval
(**design**). A new hash for any member voids the Finding and queues a re-screen, which the paper leaves open (p9).
The screener's thresholds are uncalibrated (p10) and are recorded in `producer.thresholds`.

### 4.9a Overlap and composition (v2.9) [M4]

A capsule holds a **set** of capabilities; a single capability is a capsule of one. Once a library has run
long enough to carry evidence, recurring high-quality structures are promoted to merged capsules so that
placements can be made at a larger grain. **There is no split operation:** if every capsule can exist as a
set of one, every combination can be built up, and no further atomisation is needed. This is a **design
choice that goes against the grain** [des]: LLVM's `HotColdSplitting` cuts cold regions into new
functions and Oracle's view merging dissolves a view boundary by inlining it, so hierarchy is normally
flattened for optimisation. The choice buys simplicity at the cost of never recovering a finer grain
than the parts were authored at.

**Qualification.** An ordered pair A -> B becomes a candidate only on **both** enough support and a high
enough success rate, counted in **sprints, not nodes** (threshold 2, §4.12). A recurring *structure*
qualifies the same way, by the signature of its qualified edges.

**The pruning assumption, stated as an assumption** [des]. Two capsules that each fail their declarations
are assumed to fail together too, in either order, so failing parts are never merged. Proved wrong by a
pair that succeeds together while each member fails alone.

**The converse does not hold.** Two capsules that each pass are **not** assumed to pass together. Quality
is distributional (§4.5c), so a block's quality is not the product of its members' and cannot be inferred
from them: a merged capsule is measured as a capsule. This asymmetry is the load-bearing part of the rule.

**The merged Declaration is derived, not written.** Ports come from the boundary of the internal
`structure`; `changes` covers the union of its members'; `needs` is the union minus what members satisfy
internally; `members[] {role, decl_hash}` pins every internal by hash; `identity.lineage` carries
`relation: composes` with A and B as `parent` and `co_parents`. The block's suite is the union of its members'
suites plus its own (the monotone rule, §4.7). The composite checks of §4.10 apply unchanged.

**Approval.** A merge is proposed and approved, never applied automatically. Sprints are costly and
infrequent, so the evidence is thin: thresholds tuned for high-frequency systems do not transfer.
**Qualification opens the question; benefit answers it** -- Redshift builds an automated materialized
view only when expected benefit beats the cost to create and refresh it, and Azure SQL auto-applies a
tuning action only above a gain floor.

**A departure, carefully scoped** [des]. Two minimums must not be confused. A minimum before a *quality
claim* counts is standard practice: Envoy computes no success-rate verdict below
`success_rate_request_volume` and runs no detection at all below `success_rate_minimum_hosts`, SonarQube
ignores coverage conditions until there are 20 new lines, and Kayenta gives "no data" its own class,
excludes it from the score and fails a canary when half the metrics are missing. A minimum before
*merging* is the departure: for triggering a combined unit everyone uses small fixed counts and a benefit
floor, then validates and reverts, because their observations are cheap. Ours are rare, so a person
approves instead.

**Versions: what happens to A-B when A becomes A'.**

| Question | Rule |
|---|---|
| Does A-B break? | No. It pinned A by `decl_hash` and keeps running on it; a frozen sprint keeps what it pinned (inv 3) |
| Does A-B become A'-B? | Never. Internals are locked; a member change is a new block, not an edit. §4.11's unpin-with-a-purpose is the only exception |
| Is A-B now wrong? | Stale, not invalid, and still offered. If A is **revoked** rather than superseded, A-B moves to `suspect`, reason `MEMBER_UNAVAILABLE` (§4.10) |
| Is A'-B built automatically? | No. It becomes a candidate only when A' passes §4.6 replacement compatibility against A **and** something asks for the pair again. Built on demand, never eagerly |
| If A' is strictly better? | The librarian may promote A'-B as a candidate. A-B is not retired **by the act of merging or revision**, though it remains an ordinary library member and may be retired later on evidence, as Redshift drops unused automated views and Azure SQL drops indexes that did not help |

**Costs, recorded because they are real** [des]: a merged block is one node, holds one lease and takes the
union of its members' write scopes, so there is **less parallelism inside the block**; a failure inside it
**retries the whole block** unless the block declares internal retry; and a gap inside it is attributed to
**the block, not the member**, so attribution coarsens as blocks grow.

**Composition now, merging later (Muk, 2026-09-23).** The vocabulary is settled: what ships is the
**non-merge A-B**, that is **composition** -- the block pins A and B by hash, their internals are locked,
and it runs A then B unchanged. **Merging**, in the sense of rewriting a block's internals so its members
run in one pass, is a later operation and is not implemented here. `relation` records `composes` for what
ships and reserves `fuses` for the rewrite. That buys a larger placement grain and
a block-level quality record. It does **not** buy any execution saving, and the design should not pretend
otherwise -- if A and B each iterate N items, the block still iterates twice.

**Merging proper (fusion)** is the separate, later operation that would: rewrite the block's internals so the two run in one
pass, drop a pre-check of B that A already guarantees, and fold shared work. It is **out of scope here** and
listed as a next step, but the boundary is worth stating now because it is the first question a compiler
person will ask:

- One rule would change: *internals are locked* becomes **the contract is locked, the implementation is
  free.* The union-of-suites rule stays, so a dropped check must be shown redundant by the suite that
  covered it still passing.
- The composite is the **oracle**: a fused block is compared against A-then-B on replayed inputs, and must
  pass §4.6 replacement compatibility and §4.5c's block-a-regression rule.
- Legality would come from author declarations, not from a catalogue. TensorRT can fuse from a published
  list of pairs known to give the same result; there is no such list for capabilities, and the **iteration
  shape** a fusion pass would need is not in this schema today.
- Failure behaviour is observable and constrains it: unfused, A failing on item 5 leaves no B effects;
  fused, items 1-4 already have B applied. Compensable and irreversible effects could not be interleaved
  without the block declaring its own atomicity.
- A fuser is a cold-path builder, so §4.10's ceiling still holds: it emits a Declaration, has no write
  access to gates or suites, and by AllocBench the party proposing a fusion must not be the party building it.

Nothing in v2.9 depends on fusion, and no field is added for it.

**Where this already exists.** `symphony/flow/` implements the engine: `ExperienceRecipe.combination_structure`
(a capability set with its own DAG), `qualified_edges` (support and success rate), grouping that excludes
failing edges, `resolve_status_grade` (`candidate` / `verified`), `content_identity()` (a new version only
on real change), `CapabilityPackager` (content-hashed packages), `PackageReviewGate` (ten deterministic
checks) and `FlowStore` (immutable versions). What it lacks is the declaration: no ports, effects or
guarantees on a block; no lineage to its members; no held-out test; members referenced by id rather than
pinned by hash. Those four gaps are what this section adds.

### 4.10 Composites and the ceiling

The gate checks a composite in four ways [ind]: wires connect compatible types; its declared `needs` and `changes`
cover the union of its members' (`derived`); members' budgets sum to no more than its own; no member's permitted effect
is an invariant another forbids (2602.22302; 2601.08815 p10). Members keep their Verdicts; revising a member means
re-declaring the composite.

### 4.10a Putting one capsule inside another (v2.10)

Composition is **by reference and by wire**, never by copying. A capsule that composes is the
**composite** shape of §0.2: it carries `members[]` and no `identity.carrier`, because its work is done
by other capsules rather than by code it points at. Three fields do all of it, and a capsule being
composed does not change in any way:

| Field | What it does |
|---|---|
| `members[] {role, decl_hash}` | names the capsules inside, each pinned by hash. The role is the local name; one Declaration may fill several roles |
| `wiring[] {from, to}` | connects ports. An endpoint is `<role>.<port>` for a member, or `inputs.<port>` / `outputs.<port>` for the composite's own boundary |
| `structure` | the order they run in, in the shape `symphony/flow` already uses for a distilled recipe |

The boundary wires are what make nesting work. A composite does not re-implement or re-declare what its
members take and return: it declares its own `ports`, then wires them to member ports.

```
wiring: [ {from: "inputs.discovered_paper",   to: "ingest.discovered_paper"},
          {from: "ingest.normalised_paper",   to: "extract.paper"},
          {from: "extract.research_claims",   to: "outputs.research_claims"} ]
```

Because a member is named only by `decl_hash`, and every capsule has one, **a member may itself be a
composite**: nesting needs no extra field and no special case. What the outer capsule sees is a port on
a role, whatever is behind it.

What the gate derives rather than trusts (§4.10): the union of members' `needs` and `changes`, and the
type compatibility of every wire. What the builder still declares: the composite's own ports, checks and
effect class, because a block earns its own quality record and does not inherit one.

**Open at v2.10, deliberately** (Muk, 2026-09-23), in the same spirit as §0.2:

- **Depth.** Nesting is expressible, but no maximum depth is stated, and a deep block's failure
  attribution is already the honest cost named in the impacts (§4.9a). A limit may belong in the policy
  epoch rather than the shape.
- **Cycles.** `structure` says `dag` but nothing forbids a member transitively containing its own
  `decl_hash`. Hash pinning makes a true cycle impossible to construct (the inner hash would have to
  exist before the outer one that contains it), so this may need stating rather than checking.
- **Whether outer ports may be derived.** Today they are declared. Deriving them from the wiring would
  remove a class of mismatch, at the cost of a composite no longer being readable on its own.

**Members gate the composite** (v2.1). A composite is offered only while every member's pinned hash is still admitted:
its Standing is `admitted`, or `deprecated` by supersession, since a superseded hash still passed its gate. A member
that is `suspect`, `revoked` or `retired` moves the composite to `suspect`, reason `MEMBER_UNAVAILABLE`. jiuwenswarm
has had the same cascade for standard SkillPacks since they were introduced on 2026-09-17 (`6f4eaa1b6`;
`server/runtime/skill/skillpack.py:231-258`), and extended it to container packs on 2026-09-21 (`02b37f47f`), with
members referenced by name. Pinning by hash also catches a member that changed rather than one that was disabled.

**The ceiling (design)** [ind]: a capsule is what the freeze binds to a plan node (as primary, context or dependency),
and it does not decide at run time which other capabilities to involve. Anything that plans, freezes,
admits, schedules or judges capsules is above it. AI4Research itself is not a capsule (supervisor, 2026-09-18).

**Assess versus decide (v2.9).** The line is not what a thing looks at, but whether it decides:

> A capsule may produce an **assessment**. A capsule may never be the thing that **decides**.

So a faithfulness check on an IntentIR, or a domain verifier such as a scientific claim checker, **is** a
capsule: it emits a Finding and something else acts on it. The gate, admission, the librarian's Standing
moves, the planner's filter, the freeze and dispatch are **not**, and neither are the gate's rules or its
suites (§4.16.4). **The schema enforces this by write access rather than by classifying intent:** no
capsule may write to the gate, the suites, the logs admission reads, or the record stores. That rule is
checkable; "is this judging?" is not.

**Why the workflow itself cannot be a capsule, compositionally** (v2.10a). The positional answer, that
AI4Research sits above the ceiling, is true but weak. The structural answer is stronger and follows from
§4.10a:

1. A composed capsule **contains capsules**: its members are capsules, by `decl_hash`, and nothing else
   can be a member.
2. Gates and deciders **can never be capsules**. If they were, RSI would be editing its own guards and
   its own checks, which is the one thing the whole design exists to prevent.
3. The workflow contains gates and deciders.

So a workflow-as-capsule would need members that cannot be members. It is not that the workflow is too
big to be a capsule. It is that **it cannot be composed out of capsules at all**, because the parts that
decide are permanently outside the set. The same argument is why a team skill whose Leader schedules
roles at run time stays out of v1 (§3.1, `kind`).

### 4.9b What a capsule promises to keep stable (v2.10b)

Nothing in this schema tells RSI what it may touch, and on 2026-09-24 that turned out to be the wrong
question. The right one is the one the rest of the document asks: **what does this capsule promise?**

`evolution.frozen[]` names the parts of the contract a capsule promises not to move. RSI reads its
search space off that, and so does every consumer: a port on the frozen list is one you may depend on.
A revision that moves a frozen part is **declaring a new capability**, so it takes `relation:
supersedes` and a name of its own rather than replacing this one in place.

This is a promise, not a permission, and it forbids nothing. `contract_hash` already covers every
section but the body and the lineage, so any edit to ports, needs, changes or guarantees is visible,
`CONTRACT_HASH_CHANGED` is already a typed rejection reason, and a suite written against the old
contract is already void. What was missing was not detection. It was the capsule saying which parts a
reviser should treat as fixed, so that RSI neither changes nothing nor breaks every consumer.

The precedent is the one everybody already follows: **semantic versioning** says which changes are
allowed without a major bump, and **Protocol Buffers' `reserved`** marks what must never be reused.
Both are declarations of a stable surface rather than enforcement.

`evolution.notes_for_builder[]` is the other half, and it is **advisory only**: the author's note to
whoever revises this, RSI included. It is never evidence, never gates anything, and no check reads it.
Two consequences follow and both matter:

- It sits **outside `contract_hash`**, with `body`, `lineage` and `coverage`. Editing a note must not
  void a suite.
- Anything that must actually hold does **not** belong here. It belongs in `needs`, `changes` or
  `guarantees`, where something can check it. Prose that gates is the thing this schema rejected when
  it rejected prose preconditions (§3.1).

**Why it is on the declaration and not in the code.** The capsule exists so that a planner, a gate or
RSI can reason about a capability without opening its body. Guidance held at `identity.carrier` would
be invisible until the code is loaded, would move the hash every time a note changed, and would force
the planner to fetch and parse code in order to plan. The code may of course carry it, and a build step
may lift it into the declaration, the way a docstring becomes API documentation.

**`coverage.undeclared_notes[]`**, what the builder knowingly leaves out, was specified in §3.1 from
v2.3 and **never implemented in `capsule.schema.json`**, so a declaration written to spec was rejected.
That is the fourth omission of this class, after `wiring`, eight fields of `guarantees.checks[]`, and
the unenforced leaf-or-composite rule. It is implemented now, and it is outside `contract_hash` too.

### 4.10b No capsule is its own final judge (v2.10a)

Three rules, in order of strength:

- **A capsule may run internal checks.** Nothing forbids a capability from checking itself, and good
  code does. But a self-owned check is **never admission evidence**: `self_check` was dropped in v2.2,
  and a check counts only when its runner is outside the capability's write scope and its signal comes
  from the harness rather than from the capsule (§4.4). `guarantees.checks[]` records this per check, in
  `owner`, `signal_source` and `author`.
- **Someone else's gate always applies.** A capsule never admits itself and never clears its own run.
- **That gate is built from the declaration, and is not limited to it.** At admission the suite author
  sees the Declaration and nothing else, and `contract_hash` binds the suite to the contract it was
  written against, so a body submitted under a different contract voids it. At dispatch the step's gate
  starts from the declaration but also tests what *this request* needs, which the capsule never declared
  (§4.6). That is exactly why the run gate is not redundant with admission.

### 4.10c Everything that judges is identified (v2.10a)

Provenance is only worth having if every part of it can be named. So each check carries an `id`, and
each output names the check id that proves it (`ports.outputs[].check`); each check records `author`,
`owner`, `signal_source`, `written_before_body` and `held_out`, so who wrote it and what it could see
are part of the record; each runner is pinned by `runner_hash`; each suite carries a `suite_id` and hash
in the Verdict; and every Verdict records the `policy_epoch` that admitted under it.

**This costs space, and the cost is accepted** (Muk, 2026-09-23). A Declaration that names its checks,
their authors and their runners is materially larger than one that says "tested". That is the price of
being able to answer, a year and several sprints later, *which* check passed, *who* wrote it, and *what*
it was allowed to see. RSI cannot choose a parent on evidence it cannot identify, and verification
cannot re-run a check it cannot name.

**What cannot be a capsule at all is deliberately left open** (Muk, 2026-09-23). The boundary above is the
shape of the answer, not the answer. Candidates for the rest: anything whose effects cannot be declared,
and anything that must choose *other capabilities* at run time.

### 4.11 Unpinned dependencies [v1.6, extended v2.1]

A dependency is pinned by default. An author may declare it `floating` instead, at a cost to trust, by writing:

- `purpose`: what the dependency does for this capsule, in words (**design**: the paper extracts contracts with a model; jiuwenswarm's
  Swarm Skills already write a purpose per dependency, `docs/en/SwarmSkills.md:339-372`, and CC ties it to unpinning and repair);
- `role`: `operational` (the capsule relies on it) or `incidental` (only mentioned);
- `contracts[] {contract_id, assumption, component, span}`: each assumption the capsule relies on, and where in the
  capsule it is used (2605.10990 p5).

**Costs.**

- The capsule stays provisional.
- Each claim that rests on the dependency is at most `audited`, in the order enforced > tested > audited > declared.
- The floating dependency is resolved **at the freeze**, and the Binding records the version. So a sprint still sees
  only what it started with (invariant 3). A move within the declared contracts does not void the Verdict.

**Checks.** Admission checks each operational contract once. The drift probe re-checks them, incidental mentions
excluded.

**When a contract breaks,** a `drift` Finding carries the purpose, the failed assumption and where it is used, and goes
to RSI as a localised repair ticket.

**Evidence.**

- Given the failed contract, one-round repair succeeded 78% of the time, against 10% without localisation
  (p < 10⁻⁵, p8-9), at about 10K tokens per skill against 18K for three-round Self-refine. It was not significantly
  better than plain drift text (60%, p = 0.213) or three-round Self-refine (80%) (Table 14, p19). The measured effect
  that justifies `role` is detection, below.
- Role-bearing checks gave no false alarms over 599 negative cases, against 40% for contract-free probes. Recall
  ranged from 24% to 76% across five backbones (p4, p7). All single runs.

**When.** Ships with the librarian in M4.

### 4.12 The cold path: from gap to admitted capsule

A `gap` Finding opens when a step's offer is empty after repair, or every offered capsule failed at dispatch.
A `fit_failure` Finding (v2.7), written after a node gate where the capsule's own checks passed and the step's
acceptance failed, names the step's gap identity and the capsule as a near miss. It counts toward that identity's
recurrence exactly as a gap does, and never against the capsule's Standing (§4.5b). With the
generalist on, the step still completes on a generalist (§4.14), and the Finding carries its trajectory.

**What starts a build.** A gap identity recurring over distinct sprints, at the policy threshold, with at least one
contributing sprint whose `authoring` is `build`. An audit failure or a duplicate rejection also starts an update
(§4.7), under the library-level cold-path policy and budget, without the recurrence threshold. The threshold defaults to 2 sprints, the first confirmed repeat that
AllocBench's best policy waits for (2607.23332 Fig. 1, **design**).

**Roles.** The cold path has four roles, and no two share a session. Each separation answers a measured failure:

| Role | Sees | Never sees | Writes | Why |
|---|---|---|---|---|
| **build decision** (model; RSI) | the gap's statistics (sprints, instances, cost, whether trajectories agree) and the build budget | drafts | a Declaration, written **before** any implementation (manifest-first, **design**), whose `contract_hash` the suite is bound to; or an import request naming the existing capability (tried first, v2.8); or a `build_decision` Finding for "no build" | once building meant writing code, first-sight commitment was 85-99% for three of four models (2607.23332 Table 1, p6) |
| **suite author** (model or person; verification) | the Declaration only | the generalists' scripts, logs and outputs; the draft | the held-out suite, before building starts. It may reuse generalist *inputs*, never generalist outputs as expected results | tests written before the tool separated working tools from overfit ones (2604.00392 p5); CoEvoSkills hides its tests from the builder (2604.01687) |
| **implementation** (model; RSI) | the Declaration, the generalists' trajectories, and the parent's visible suites (v2.7) | the sealed suites, including this build's fresh held-out addition | the body; submits to the gate a capped number of times, and receives only admit or reject with a reason. Before the gate it may get practice feedback from a separate verifier session that sees inputs and outputs, never the suite (CoEvoSkills: 41.1% with pass/fail alone, 71.1% with such diagnostics, 2604.01687 Table A1). Spent submissions give a `build_failed` Finding | tools fitted to their task's inputs scored zero on held-out tests (2604.00392); an uncapped loop learns the suite by trial |
| **gate** (code; capsule layer) | recorded suite results, observed effects | nothing a capsule can write | the Verdict | an agent judged by a score changed what the score read (2505.22954 p70) |

**Budget.** The build budget is a hard runtime limit, never shown to the implementation as a price: a visible price
left code-required first-sight commitment near 100% (2607.23332 App. E). A capsule with a large blast radius gets full
verification however often it will be reused.

**Visibility.** Findings marked `builder_hidden` (replay and suite details) are never readable by the build decision
or implementation roles, so the separation above is enforced by read access, not by convention.

**RSI.** RSI owns the build decision and the implementation, returning a Declaration with `lineage.build_trigger` and
`diagnosis_inputs`. It never writes the library, never authors its own acceptance checks, and never sees checker
internals. §4.18 maps this onto the RSI code as it is.

### 4.13 The librarian and the audit loop

- **Audit loop.** Every admitted capsule's held-out suite becomes its regression suite, replayed on a schedule. The
  schedule is ordered by blast radius and by time since the capsule was last checked, so the library is checked
  continuously, not once.
- **What the audit loop's Findings lead to.** The librarian acts on them, using the transitions in §4.8 and the
  policy by reason in §4.7:
  - a failed replay, or an invariant violated on real outputs: `CONFORMANCE_FAILED`;
  - effects outside the declaration: `EFFECT_VIOLATION`;
  - declining task success: `DEMOTED_TASK_SUCCESS`, which only **demotes**, because task success cannot detect broken
    tools (2604.00392).
- **Tombstones.** A retirement is a tombstone, never a deletion, so a pinned version stays resolvable (2026-09-15
  report, App. G.6).

- **Start extra small** (v2.8, **design**). M1 seeds about ten capsules: the ones behind the most frequent plan-step
  types in recent AI4Research sprints, at most one per slot, imported from today's manifests. Caps start at one to
  three per slot. Everything else runs on generalists, which now bind to judged steps too, and leaves gap Findings.
  The library grows only by recurrence, and the first option for a recurring gap is to **import** an existing
  capability (an AI4Research manifest, a jiuwenswarm or skillhub skill, an MCP server) before building one. Why small:
  pass rate fell by 0.21 (95% CI 0.15 to 0.27) as a library grew to 202 skills, with 38.5% of runs invoking no skill
  at all (2605.24050 Tables 1 and 2, p9); a cap mainly controlled variance (2605.19576 p3-6); builds should wait for recurrence (2607.23332).
- **Caps.** Each slot has a cap; to admit past it, the librarian first deprecates the lowest-use capsule that no admitted
  capsule depends on, from Binding counts. Harsh retirement fell below the no-skill floor, and the cap mainly controlled
  variance (2605.19576 p3-6).
- **Evidence floor** [ind]. No retirement on outcome evidence below a minimum number of invocations; retirement driven by
  a model judge is suspended while that judge's measured false-pass rate is at or above the cliff for the threshold in
  use (2607.07436 p4).
- **Curator health.** Zero quality retirements while cap evictions continue is the pattern a lenient judge produced
  (2607.07436 p6); it triggers a verifier audit (**design**; the paper audits before deployment).
- **Overlap and duplicates.** Similarity of `summary` and `ports` only raises an `overlap` Finding; it decides
  nothing (§5). The duplicate check is a test: each capsule runs against the other's regression suite, and a candidate
  that passes the other's suite and adds no case of its own is rejected (`DUPLICATE`). Until the check runs, the newer
  capsule is `admitted_inactive`. On unattended runs it stays inactive rather than being rejected.
- **Exploration quota** (**design**). A step that does not require certified capsules may be offered `admitted_inactive`
  capsules up to a policy share of its offers. Inactive capsules can then collect the Bindings that the evidence floor
  and activation need. This is how the library explores, as distinct from choosing among what is active.
- **Queries.** Use per capsule; block rates and gate-versus-exit disagreements (parity health); open deferrals;
  expiring Verdicts; provisional capsules and what certification needs; unanswered gaps; everything tainted by a
  revoked hash, down to claims; flagged sets and sets never screened.

### 4.13a The capability tree: CC stores and exposes, RSI chooses (v2.7) [M4]

**Why a tree and not a chain** (v2.10a). Every source-control system large enough to matter branches
and forks, and GitHub is the plainest case: a repository is not a line of commits but a tree of them,
several branches coexist, and **the latest commit is not always the best one**. Capability versions are
no different. A linear history would force the library to treat the newest admitted Declaration as the
one to build on, which is the failure the Darwin Godel Machine measured directly: its ablation keeping
only the latest agent did worse, because a poor self-modification makes later gains harder (p8). Keeping
the whole tree is what makes a suboptimal node a stepping stone rather than a dead end.

The library is a tree of capabilities. **Nodes** are every Declaration ever submitted, by `decl_hash`, including
rejected and retired ones: the store is append-only, so a node never disappears, and its Verdict says why it was
rejected. **Edges** are `lineage.parent` with its `relation`, plus optional `co_parents`. A tree spans names: a
specialisation starts a new name but stays linked to its parent. **Standing** is a pointer per name into the tree; the
tree keeps every node, active or not. Several children of one parent may coexist; one of them at most is a name's
current version.

**Who knows what.**

| | What | Guaranteed? |
|---|---|---|
| **CC stores, from its own records** | per node: `decl_hash`, `contract_hash`, name, parent, relation, builder; the Verdict (outcome, typed reasons, level, each suite's result, inherited suites included); Standing state and history; every invocation (outcome, gate verdicts by source, cost); Findings about it (use, drift, audit, composition); its children | **yes**: CC's own writers produce these |
| **CC stores if the builder supplies it** | `co_parents`, `build_trigger`, `context_capsules`, `diagnosis_inputs`, provenance (generating model, prompt, trajectory), `builder_ref`, build cost | **optional**: kept and exposed, never required, never inferred |
| **RSI owns** | which node to branch from (its selection policy), what to change, how many children to try, when to stop, its own scores and tree state, its own gate (kept as `builder_gate` evidence) | not CC's: CC never reads RSI's scores and never ranks nodes for RSI |

**The tree index** (the librarian's read model). One row per node, derived from the records above and never
authoritative: `{decl_hash, name, parent, relation, depth, children_count, standing, level, verdict_outcome,
suites_passed, suites_total, inherited_suites_failed, invocations_n, gate_results_by_source, cost, open_findings,
last_used, context_unreported}`, plus `builder_ref` when present. Queries: ancestors, descendants, siblings, the frontier (nodes with no
admitted child) and a name's subtree. Because every record is append-only and keyed by hash, each new Verdict,
Standing move, invocation or Finding updates one row and its ancestors' counts; nothing is recomputed from scratch.

**What CC enforces on a new child.**

- The parent (and each co-parent) must exist in the store. Branching from any node is allowed, including rejected,
  retired, deprecated or `suspect` ones: suboptimal nodes are stepping stones.
- The child inherits the parent's suites (§4.7). Branching from an active node to replace it needs the monotone rule;
  branching from any other node needs full admission, with the inherited suites attached as targets.
- A parent or co-parent revoked for security, harm or provenance makes the gate reject the child
  (`PARENT_REVOKED`), unless a named person waives it; on unattended runs there is no waiver.

**Why.** The Darwin Gödel Machine keeps every agent it produces in an archive that is never pruned, and picks parents
from the whole archive, roughly in proportion to performance and inversely to the number of children (2505.22954 p4).
Its ablation that keeps only the latest agent did worse, because a poor self-modification makes later gains harder
(p8). That selection needs, per node, its results and its children: exactly what the index exposes. The policy that
uses them is RSI's. RSI already keeps a tree of nodes with `parent_id`, `adopted` and `score` (`code` agent-core
`rsi/schema.py:96-111`, which jiuwenswarm projects for its web view at `agents/harness/common/rsi/models.py:292`); `builder_ref` joins that tree to this one without CC reading its score.

### 4.14 Exempt capsules: the generalists [M3]

A generalist is a capsule whose Declaration carries `guarantees.exempt {reason: generalist}` (v2.7). **Several may
exist**, each its own Declaration with its own carrier and model: for example a Codex generalist and a Claude
generalist. The run contract's `generalists[]` names the ones a sprint may use. When nothing fits a step, the offer
holds those, filtered by the same stage-1 criteria (model, network, effects), and the chooser picks one. Their
invocations accumulate per hash, so the librarian can compare them on the same gap identity. That is evidence for
choosing among them, never certification.

**Exempt from** the library's verification policies: there is no declared job, so no held-out job suite, no
certification, no contribution rule and no monotone rule. **Not exempt from:** every plan gate (§4.5b), Standing and
revocation, declared and observed effects (§4.5a), protected components, budget, the cap, and enrolment
(§4.1 step 5: it loads, stays within its declared effects in the sandbox, refuses a protected write, and completes
sample step contracts under their gates). `exempt.reason` accepts
only `generalist` in v1, so `exempt` is never a way around admission for an ordinary capsule.

**Why it exists** (Muk, 2026-09-22). Without it, a step nothing fits fails with `UNSATISFIABLE_CAPSULE` and leaves
nothing to learn from. With it, the step completes under the plan's gates and leaves its trajectory, gate verdicts by
source and cost, so RSI has material to improve on, and a failure can be explained.

Each generalist is a permanent capsule with one special property: its work can seed new capsules (2026-09-15 report,
§4.1). The chooser binds it (the planner still names no capsule) to a step that neither a single capsule nor a composite fits, if the run contract's
`generalist_fallback` is `on`, the plan is under `generalist_cap`, and **every output type of the step has a gate**,
which may be a judge (v2.8). The 2026-09-15 report required "the deterministic gates attached to the output type";
v2.8 relaxes this so research steps can run, and labels instead: a generalist's claims are never `supported`. It is how self-improvement starts: a plan that
fails today with `UNSATISFIABLE_CAPSULE` (`code` `apo_plan_compiler.py:626`) completes instead, and leaves the record a
build needs.

| Property | Rule |
|---|---|
| Contract | from the **Plan step**, not its own Declaration: the step's types, requested effects and gates are fixed at planning, and the generalist must meet them. It never chooses its own checks |
| Method | a general agent model, preferably writing a script and running it in the sandbox, so code, inputs and outputs are recorded and can be re-run |
| Trust | the lowest, level `exempt`: its Binding carries `exempt: true`. It must pass the step's gates, but no claim resting on it is marked supported, and the delivery lists every generalist step |
| Writes | never the library. It leaves a `gap` Finding with its trajectory and cost; its effects exclude every protected component |
| Weights | fixed. The library and context may evolve, reversibly; the generalist's model does not, since it only sees the cases nothing fits |
| Cap | at most `generalist_cap` steps per plan, so it stays a fallback and not a way around typed contracts |
| Two rules against self-certification | only the implementation role sees its trajectories; its outputs never become expected results in a suite (§4.12) |

Its own Declaration is small: identity, carrier (an `AgentTemplateSpec` naming a harness provider such as
`codex`, `claudecode`, `native` or `dsh`, §4.17a), budget, `kind: agent`, `exempt {reason:
generalist}`, `effect_class`, and
`effects` bounded by `effect_ceiling` minus the protected components. Its ports come per step from the Plan step, and
each Binding records the step's contract (`plan_hash` + `step_id`). The gate **enrols** it once, at level `exempt`
(§4.1 step 5): hashes, loading, effects within its declaration, a refused protected write, and a smoke run on a fixed
set of sample step contracts under their gates (**design**). Its `decl_hash` is stable because the step
contract is not part of it.

### 4.15 Unattended runs

Long runs belong on servers with nobody present to approve each step. With `unattended: true`:

Every place a person is asked becomes a rejection or a wait:

| Where a person is asked | Unattended |
|---|---|
| a plan-only composition set; an `outside_cap` pin | not bound |
| an import's confirmed effects | the import stays `proposed` |
| an overlap pick | the newer capsule stays `admitted_inactive` |
| an inverse or compensation after revocation | not run; recorded for later |
| a DEFER's typed request | waits up to `max_age_s`, then a fallback, then fails |
| a carrier that needs approval, A2A delegation for one | not offered |

The run's `effect_ceiling` is the upper limit of what it can do.

(2026-09-15 report, App. G.8.)

### 4.16 What the system may change

In order of reversibility (2026-09-15 report, App. G.5):

1. The capsule library: yes, reversibly, by versioning, retiring and superseding.
2. Context and prompts: yes, reversibly, as overlays.
3. Model weights, the generalist's included: no.
4. The gate, its rules and its suites: never by the system. People release new versions, and each Verdict records the
   `policy_epoch` that admitted it.

Prefer the most reversible mechanism that achieves an improvement.

### 4.17 Integration with openJiuwen (`code`, agent-core `e23806c1`)

| Hook | Use | Gap the capsule layer fills |
|---|---|---|
| `CapabilityProvider` (`symphony/interfaces/capability.py:13`), atomic for batch mutation (`orchestration/mutations.py:167`) | list admitted skill, subagent and agent capsules with `content_hash = decl_hash` and I/O from `ports`; the extractor uses the provided hash and prefers the provided I/O over any model output (`shared/fingerprint/extractor.py:151`, `:195-202`), and calls no model while `enable_llm_extraction` is off, its default (`settings.py:24`) | Symphony's graph takes only skills, subagents and agents (`orchestration/graph/build.py:161`); tools, MCP and A2A capsules go through the filter and binder |
| `SkillGraphUpdater` (`symphony/interfaces/graph.py:14`) | add, update, delete on each Standing move | one revision per id; every mutation calls a model for ontology matching (`orchestration/mutation_service.py:129`) |
| `apply_extension_hot` (`harness/extension_binder.py:27`) | load the verified body through its carrier | no hash check; load from the immutable store |
| `SkillUseRail(enabled_skills=...)` | apply the offer for skills | none [ind] |
| `before_tool_call` (`harness/observability/rail.py:888`) | tool calls against declared effects | a tool capsule's internals are invisible (H5) |
| `TrajectoryStore`, `LoadRecord.refs` | Bindings | load records are in memory; a capsule-layer rail persists them |
| agent-core RSI module, `RsiTreeNode` (`rsi/schema.py:97-111`) | an adopted node's snapshot maps to a candidate Declaration with `lineage.parent` (**design**) [ind] | |

Symphony's quality results stay observations: they may feed `use_outcome` Findings and never admit anything [ind].
Symphony's evolution, which changes edge weights from `plan.outcome` events and distils skill packs of existing
members (`verify/V3-jiuwenswarm.md` C2-C3), is the same: observation, recorded as Findings.

### 4.17a Where each part lives in openJiuwen (v2.7)

CC adds records and checks. It uses openJiuwen's layers, mechanisms and names, and replaces none of them. **Reuse
comes first:** where openJiuwen, jiuwenswarm, Symphony or AI4Research already does something, CC uses it. What CC
adds new is small: the Declaration format, the records (Verdict, Standing, Binding and its invocations, Findings),
one predicate evaluator shared by the filter and dispatch, the admission gate, judge standing, and the tree index. The
structure is as recorded in the tundle obby vault (`openJiuwen Landscape`, `agent-core/Core 00-06`,
`jiuwenswarm/Swarm 00-05`), read in source at agent-core `e23806c1` and jiuwenswarm `02b37f47f`.

| CC part | The openJiuwen piece it uses | How it fits |
|---|---|---|
| **Declaration** | the **Card** side of openJiuwen's Card-versus-Config rule (`ToolCard`, `AgentCard`, `WorkflowCard`; `.claude/rules/architecture.md`) | a Card is static, serialisable identity, and putting a session id or runner in one is an anti-pattern. Invariant 12 is the same rule: the Declaration is card-like and every use lives in run records. It adds what cards lack: preconditions, effects, trust |
| **loading a capability** | `AbilityManager` and `Runner.resource_mgr` for core abilities (tools, workflows, agents, MCP); `harness/extension_binder` for harness extensions; `create_harness(manifest, provider=...)` for agent templates | the same registration paths, fed from CC's hashed store |
| **Plan steps, scheduling, fan-out** | whichever engine runs the AI4Research plan: today its own graph scheduler; on openJiuwen a core workflow graph (Pregel), Agent Teams tasks, or a Swarmflow script with parallel and pipeline operators (agent-core `agent_teams/workflow`, surfaced by jiuwenswarm) | CC does not change with the engine; fan-out is Swarmflow's parallel operator or a workflow loop |
| **invocation** | the harness protocol: a capsule run as an agent is one **Turn** (exactly one start and one terminal event; `TurnResult` with usage and exact cost); a tool capsule's call is one provider **item** (`ItemLifecycleEvent`) | one invocation per Turn or item. A pause and resume stays one invocation, since `PAUSED` and `RESUMED` keep the same Turn; a retry after a terminal event is a new one (**design**, following the one-terminal-event rule). `observed_cost` comes from `TurnResult`; the event sequence and correlation ids are its trace |
| **trajectories** | `agent_evolving`'s canonical OTLP `Trajectory`, and Symphony's trajectory v2 evidence format | consumed, not redesigned: `trajectory_ref` points at one |
| **durable records** | `TrajectoryStore` and `LoadRecord` (in memory); jiuwenswarm's hash-chained Eternal Conversation history where a session opts in; checkpointers (`core/session/checkpointer`, Redis in `extensions`), which resume a run after a crash but do not record what ran; openJiuwen's pluggable stores in `extensions` (DB, KV, vector) | a capsule-layer rail writes Bindings and invocations durably, into openJiuwen's own stores rather than a new database |
| **judges** | the harness's built-in `verification` subagent (spec S_18); `agent_evolving`'s evaluators; Symphony's evaluation metrics (six of nine are model judges, off by default); AI4Research's 20 semantic registry checks and its default `llm_eval` gate | each is a judge with a standing per model and artifact type (§4.5c): it gates from day one, spot checks calibrate it, and only a measured one certifies (**design**) |
| **effects and approvals** | the harness `PermissionEngine` (`ALLOW`, `ASK`, `DENY`) with `PermissionInterruptRail`, and jiuwenswarm's policy mapping severity to them; `SysOperation` sandboxes with `SYSTEM`, `SESSION` or `CUSTOM` isolation, such as jiuwenbox | an irreversible, high-severity effect is an `ASK`, and `DENY` on an unattended run; an `{instance}` scope is a per-invocation `SESSION` sandbox. Permissions are off by default in jiuwenswarm, so a CC sprint turns them on |
| **ToolCard flags** | `exposure`, `parallel_safe`, `stateless`, `idempotent` | computed by the gate from the declared effects and `effect_class`, never trusted as written |
| **context taint** | Session VCS: `commit`, `snapshot`, `rewind`, `fork` | a context that held a revoked hash is not reused: the next invocation starts a new session, or forks from a snapshot taken before the capsule loaded (**design**) |
| **generalists** | `harness_providers`: `native`, `claudecode`, `codex`, `dsh`, behind `HarnessProtocol`; Agent Teams' `external_cli` role | each generalist's carrier is an `AgentTemplateSpec` naming a provider; enrolment checks the host capabilities its `HarnessCard` requires |
| **remote bodies** | A2A `AgentCard` (`extensions/a2a`); MCP servers | `remote_fingerprint` hashes the card or the tool listing |
| **overlays** | the experience layer (`evolutions.json`), written through `agent_evolving`'s `EvolutionStore` after preview and approval; the TTSE bank | pinned per sprint, or not loaded |
| **the tree, RSI** | agent-core's `rsi/harness_rsi` and its tree nodes (`RsiTreeNode`, `rsi/schema.py:96-111`), which jiuwenswarm projects for its web view (`agents/harness/common/rsi/models.py:292`); `agent_evolving`'s candidate validation from one snapshot | `builder_ref` joins RSI's tree; RSI's gate is builder evidence, and CC's gate admits |
| **Symphony** | `CapabilityProvider`, `SkillGraphUpdater` (above) | CC decides what Symphony may index |
| **prod-eligibility** | openJiuwen's aim for production use: globally unique identity, effects declared across hosts, admission records others can audit, no assumption that a person is watching | `decl_hash`, `ext:` effects, Verdicts, unattended runs |

**Names.** openJiuwen's vocabulary is `Session > Turn > Step`, with `Round` reserved for multi-agent phases. Three CC
terms sit beside it and must not be confused with it:

| CC term | Means | Not to be confused with |
|---|---|---|
| **Plan step** | one node of the AI4Research plan (`step_id`) | an agent-core **Step**, one cycle of an agent loop |
| **invocation** | one actual run of a capsule for a Plan step: a Turn for an agent capsule, an item for a tool capsule | a Turn or item that is not a capsule run |
| **capability** | anything an agent can call on; openJiuwen calls tools, workflows, agents and MCP servers **abilities**, and a capsule wraps one ability or skill | a Card, which is only its identity |

### 4.18 RSI, as it is in code (v2.1)

| RSI today (jiuwenswarm `02b37f47f`, agent-core `e23806c1`) | In the schema |
|---|---|
| a search tree of `RsiTreeNode`s with `parent_id`, `adopted`, `score`, `snapshot_artifact_id`, `changes` (`agents/harness/common/rsi/models.py:292-306`) | `lineage.parent`, `diagnosis_inputs`; `context_capsules` is new and asked of RSI; `builder_ref` holds the node id. RSI's `score` stays RSI's (§4.13a) |
| a candidate gate that accepts when the target cases the change was built for improve, then an epoch replay of the whole suite that promotes only if nothing regresses against the previous best (agent-core `rsi/harness_rsi/single_harness/iterative.py:1435-1447`, `:609-611`, `:927-929`); held-out cases 0 by default and forced to 0 by the single-harness orchestrator jiuwenswarm uses (`:164`; `config/config.py:172`; jiuwenswarm `rsi/harness_provider.py:5`) | `builder_gate` in the Verdict: evidence, never a passed check, because every case it scores is one the builder optimised on. Admission needs held-out checks from another author. A held-out split inside RSI needs a code change to the single-harness orchestrator, owned by RSI |
| its training suite is loaded as 训练集 (training set) (`validation_dataset.py:24-32`) | never an acceptance suite for what was trained on it |
| a published package hashed over paths and contents, the installation id taken from the hash (`harness_activation.py:266-293`, `:772`) | `body[]` hashes; `decl_hash` |
| an active pointer with a retained history and rollback, written by RSI and by a user-invoked rollback that pushes to live agents (`:416-464`, `:620-680`) | the Standing, with `previous[]`, written by the librarian after a Verdict. The RSI pointer becomes a proposal the librarian acts on, so it has one writer |
| rollback refused while any RSI task is queued, running or paused (`:682-692`) | adopted: the concurrency rule in §4.7 |

### 4.19 jiuwenswarm (v2.1)

| jiuwenswarm today (`02b37f47f`) | In the schema |
|---|---|
| 34 bundled skills declare a name and description; none declares inputs, outputs, preconditions or effects (`DERIVATION.md` D1-D2) | imported as provisional; a person confirms effects |
| SkillPacks: members by name; a disabled or missing member blocks the pack (`server/runtime/skill/skillpack.py:180-258`) | composites with pinned members; `MEMBER_UNAVAILABLE` (§4.10) |
| Swarm Skills: declared skill and tool dependencies with `required`, boundaries and acceptance criteria, read by a model at preflight (`docs/en/SwarmSkills.md:119`, `:339-374`) | the same declarations, made code-evaluable and pinned (§4.2) |
| a Teammate's evolved experience is saved automatically and loaded with the skill next time (`docs/en/SkillSelfEvolution.md:55`, `:119`) | an `overlay`; a new provisional revision, never an in-place change to a pinned capsule |
| TTSE injects facts and catalog tips with no approval dialog (`docs/en/TTSE.md:3`) | an `overlay` on the chooser's input: pinned per sprint, or not loaded |
| Auto Harness Expert packages are hot-loaded after user confirmation in the pipeline description (`docs/en/AutoHarness.md:60`), though the same page's FAQ says "immediately after generation" (`:297`); Meta changes go by PR (`:38-41`) | a package is a new body: a candidate Declaration through the gate. A person's confirmation is recorded, but it is not a check |

---

## 5. Rejected, with reasons

| Alternative | Why not |
|---|---|
| one manifest with a `status` and a `quality` block | mixes author claims, gate results and observed quality; Symphony's fingerprint is exactly this [ind] |
| a model-derived fingerprint as the contract | an observation of the text, not a commitment; kept as a retrieval view [ind] |
| a scalar quality score for admission | a compensatory score can buy out a failed hard requirement (2609.16313 Prop. 1, p6) |
| the slide's eight components as eight sections | Governance and Eval are what others do to a capsule: Verdict and Standing [ind] |
| prose preconditions and invariants | nothing evaluates prose |
| similarity to decide "same capability" | a hash proves identity; similarity does not |
| a capsule acting as gate, verifier, freeze or scheduler | these must sit outside what they judge (2505.22954) |
| AI4Research itself as a capsule | ruled out by the supervisor, 2026-09-18 |
| capsules selecting models | routing picks models; `needs.model` is a constraint |
| three tiers | the evidence draws one line; two levels plus per-claim assurance [v1.6] |
| inferred conflicts between capsules | observable only in execution (2606.03056 p5-6); declared resource and invariant clashes are screened instead |
| Alita-G's selection-text tables | 1.2 points, one run, built and scored on one set (2510.23601 p8-9) |
| `defect_class`, `components.size`, `n_queries`, a run-pin `version` | no reader |
| a builder's own gate (e.g. RSI `published`) as admission | it is target-local, with no held-out cases (`DERIVATION.md` D9); kept as `builder_gate` evidence |
| skill frontmatter `allowed_tools` or `models` as binding | not enforced by the loader, and a model choice belongs to routing |
