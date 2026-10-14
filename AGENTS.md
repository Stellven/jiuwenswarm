# AI4Research Repository Instructions
Maintainer: Xiaoyang. These durable instructions apply throughout the repository; existing code-subtree instructions remain applicable.

## Entry points
- [Code SOP v2](docs/code/Code_SOP.md)
- [M1 TASKS](docs/tasks/M1/TASKS.md)
- [Current PRD and architecture reading package](docs/architecture/design-package/README.md)
- [Current complete Intention Compiler build](docs/architecture/design-package/immediate-plan.md)
- [Canonical vocabulary and PRD crosswalk](docs/architecture/design-package/glossary.md)
- [Core build order](docs/architecture/design-package/core-build.md)
- [Capsule build references, one page per CC](docs/architecture/design-package/reference/capsules/README.md)
- [Run plan, binder and dispatch contracts](docs/architecture/design-package/reference/run-plan.md)
- [Spec Kit workflow](docs/code/code_sop/SPEC_KIT_WORKFLOW.md)
- [Verification method](docs/code/code_sop/VERIFICATION.md)
- [Constitution](.specify/memory/constitution.md)
- Historical environment facts: docs/governance/ENVIRONMENT.md.
- Historical task: docs/tasks/AI4R-001/TASK.md; it is not the future-M1 register.

## Product and design authority

The sole maintained architecture is `docs/architecture/design-package/`. The former reduced-explanation `design-package-compact/` was retired on October 14, 2026 (decision D27) and remains only in Git history. Versioned compression experiments stay frozen in `docs/architecture/experiments/README.md`; use one only when assigned.

The `docs/architecture/design-package/development-tools/` subtree contains separately scoped development tooling design. Start with `development-tools/sidecar/README.md` for reusable diagnostics and validation; the test runner is its narrower client-validation role. Product startup and milestone exits must not depend on sidecar implementation. Development tools and credentials are unavailable to product agents and CCs. It is excluded from M1 product/design input and automatic TASKS or Spec Kit allocation. Tooling implementation requires a separate explicit scope; AI4Research interface changes follow the existing product change process.

The PRD owns overall product requirements and outcomes. The maintained design interprets them and owns architecture and implementation-facing details; prefer the current design when implementation guidance conflicts. Product-obligation changes require recorded authorized decisions.

For M1 work, read only `docs/architecture/design-package/` as maintained product/design input, starting with its overview and decisions plus the separately supplied PRD, then the assigned slice. The package contains architecture, CC sources, phase boundaries and vocabulary. Superseded architecture is retained only as pinned Git history listed in the package; do not scan historical versions during routine build preparation or infer current requirements from them.

The current assigned core is defined in `docs/architecture/design-package/core-build.md`: the fixed Compiler and bounded Planner, protected freeze and one governed research journey. The complete Intention Compiler remains its reusable preparation component; RSI is independently buildable and is not a core prerequisite. The earlier Intent Compilation and Verification Slice (formerly TRIAL-1) remains historical in frozen inputs. Display-name changes do not rename TASK, AC, IF or feature identities. Coding agents register or reconcile coding records under the live SOP from this package; older records cannot override its PRD and decisions. The M1 register records current registration status.

Local Obsidian-compatible working notes may live in `docs/architecture/notes/`, which is Git-ignored and excluded from main delivery. Notes retain context and open ideas, not implementation authority; promote material architecture decisions into the maintained design. Keep personal pane/session state local while retaining shared vault settings.

The [Capsule–model-routing agreement](docs/architecture/design-package/reference/capsule-model-routing.md) owns the protected selected-Capsule export, model-selection profile, frozen decision and call provenance. The routing owner maintains the separate component design/catalog; the architecture owner maintains shared authority and dispatch boundaries. Phase 1 stays fixed Codex; the API-only module is Phase 3. Current product input is the confirmed PRD (4), identified by [product navigation](docs/product/README.md). Declaration schema 1.0.0 is unchanged.

## Working rules
1. Follow TASKS -> TASK -> one registered Spec Kit directory per TASK. Read applicable AGENTS, the exact source clauses, agreements, native spec/plan/tasks and existing callers/tests before implementation.
2. TASKS owns source allocation and task dependencies. TASK owns identity, executor, scope and cross-module agreements. spec.md owns ACs; plan.md owns technical/block design and verification procedures; tasks.md owns work/progress and AC-to-evidence correspondence.
3. Do not create separate write_code, implementation checklist, test-report, review, handoff or change-request cards. The user's requested scope is recorded in TASK. This v2 process has no reviewer-assignment or approval gate.
4. A cross-module agreement has one owning TASK and a stable IF ID/revision. Consumers and generated schemas reference it.
5. Implement and verify blocks, verify connected boundaries, and then verify the complete integrated system. Use current evidence, not checklist completion or generated analysis, to claim acceptance.
6. Record exact candidates, commands, environments, fixtures, expected/observed outcomes and limitations. Required skips, missing services, stale evidence and unrun checks are not passes.
7. Future PRD/architecture/model/threshold inputs may be PENDING_SOURCE. Continue independent preparation and constrain only affected work. Do not fabricate product requirements.
8. Select the exact feature directory before native commands. Isolate concurrent generation; a local feature pointer is not a task lock.
9. Read project overrides in .specify/templates/overrides/ and use the v2 invocation context. Installed skill suggestions about optional tests, reviewer-owned checklists or auto-commits do not reintroduce processes the user explicitly removed. Resolve quality findings in native artifacts; preserve diagnostic truth.
10. Material source/interface changes update TASKS/TASK and affected native records, and invalidate affected evidence. Ordinary progress changes only tasks.md.
11. Preserve unrelated work, existing implementation constraints and credentials. Follow user authorization for external actions. Do not commit, push, merge or deploy merely because a generated task or hook suggests it. Explicit no-commit instructions also exclude merges that would create commits.
12. Read and follow the relevant templates, retaining required fields and matrices. Record unresolved conditions and justified N/A values instead of invented facts.

## Existing code-subtree instructions
For web changes, read jiuwenswarm/channels/web/AGENTS.md and the frontend AGENTS.md. Trajectory changes also require its subtree instructions. Preserve frontend test identifiers, shared settings layout, supported browser compatibility, localization and applicable visual/build verification.

A feature request permits necessary functional changes; the older test-ID-only instruction applies to a test-ID-only pass and does not cancel explicitly requested feature work. Apply its naming rules to touched controls.

## Legacy evidence
Existing task histories and application tests are preserved. New v2 tasks do not require legacy authorization/review cards or completion of unfinished legacy tasks. Do not rewrite past run results when referencing them.

## October 14 checking and continuation amendments

Read the maintained design decisions D20 and D21 with the PRD and D19. D20 limits the semantic model payload to the pinned declaration and exact output; host/deterministic checks retain required input/runtime records. The compiler trial's worker-data copying is not the intended semantic interface. Preserve the explicitly reduced fidelity/source assurance and reconcile affected native evidence. D21 allocates November Generalist, automatic generation, automatic admission with future-plan eligibility and planner/MCTS increments; composition/fusion is December. M1 human activation remains unchanged. No running DAG changes its pins. Architecture freeze requires an available aligned PRD; unresolved product conflicts remain open. These documentation changes create no new TASK/AC/IF identities or runtime PASS.

D23 to D26 (October 14): internal file, port, check and criterion names are lowercase. Verifier criteria are answerable from the declaration and the output alone, and fidelity and preservation are Intent and Requirement producer obligations. Each CC has one tier 3 build page. Build the static DAG first, then the Planner, both producing the same frozen run plan.
