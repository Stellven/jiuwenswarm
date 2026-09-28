# Spec Kit in the AI4Research SOP

Status: documented integration; repository installation, constitution ratification, and pilot execution remain adoption work. Publishing this guide does not perform them. The [seven governing principles](../Code_SOP.md#1-the-seven-governing-principles) are unchanged.

Documentation validation on 2026-09-28 checked the pinned upstream sources and ran their PowerShell feature resolver in an isolated temporary fixture. Explicit selection, pointer fallback, missing-artifact rejection, and preservation of the selector and Git branch passed. This check did not install the CLI, initialize the application, or execute an end-to-end feature pilot.

Spec Kit supplies structured specification, design, task generation, and implementation assistance. Human design approval, the Lead's `write_code.md`, real verification, AI review, human review, and merge authorization still come from the SOP. Generated text and command completion do not establish any approval.

## 1. Supported baseline and applicability

This guide targets upstream **v1.0.12**, commit `e77daa9021d20db26b878f7dfa5640fe5a42d04e`, with the Codex integration and PowerShell scripts. Record the actual installed versions and generated assets in `docs/governance/ENVIRONMENT.md`; review upgrades as environment changes. Upstream `main` and older tutorials can describe different commands.

- After setup and a successful pilot, use Spec Kit for new Standard and High-risk tasks.
- Simplified tasks retain the short manual path, with the same human gates.
- Existing approved tasks remain in their recorded artifact mode. Do not silently move their acceptance criteria, design, or progress into newly generated files.
- If Spec Kit is unavailable, the Lead may record use of the manual Standard/High-risk path, the reason, owner, and revisit condition. Tool availability does not waive any gate.

Use [TASK](templates/TASK_TEMPLATE.md) to record `Manual` or `Spec Kit`, the exact feature directory, owner, risk path, branch, baseline, and approval references. A task has one artifact mode at a time; an approved migration identifies the replacement authority and preserves old versions.

## 2. One authority for each fact

The paths below are relative to the application repository root, **not** `docs/code/`. `<feature>` is an exact directory registered in TASK, for example `specs/AI4R-001-router-validation`.

| Information | Spec Kit mode: authoritative record | Relationship to existing templates |
| --- | --- | --- |
| Task identity, routing, risk, artifact mode, owners, approval references | `docs/tasks/<TASK-ID>/TASK.md` | TASK becomes the registry and links to the records below; do not copy their requirements or progress |
| Requirements and stable acceptance criteria | `<feature>/spec.md` | Use `AC-01`, `AC-02`, etc.; all tests and reviews reference this file and version |
| Feature design and verification strategy | `<feature>/plan.md` | Incorporate applicable DESIGN prompts: alternatives, interfaces, failure behavior, quality methods, migration, and recovery |
| Implementation work, dependencies, step progress, discoveries, remaining work | `<feature>/tasks.md` | Incorporate applicable PLAN prompts; generated checkboxes need completion evidence |
| Approved shared interfaces | `docs/contracts/<contract>.md` | Feature `contracts/` files are proposals or references until approved changes enter the shared contract; label them accordingly |
| Architecture and durable decisions | `docs/architecture/`, `docs/adr/` | Refer to shared versions; feature `research.md` and `data-model.md` support the design |
| Human implementation authorization | `docs/tasks/<TASK-ID>/write_code.md` | Lead approval identifies the spec, plan, task scope, allowed files, checks, and stop conditions |
| SOP gate completion | `docs/tasks/<TASK-ID>/IMPLEMENTATION_CHECKLIST.md` | Records process gates only; implementation work and progress stay in `tasks.md` |
| Executed checks and real outcomes | `docs/tasks/<TASK-ID>/TEST_REPORT.md` | Commands, environment, covered commits, results, logs, and limits |
| AI findings and subsequent human decision | `docs/tasks/<TASK-ID>/review.md` | Actual diff review using the REVIEW template; neither analyze nor converge replaces it |
| Team task state | `docs/governance/CURRENT_STATUS.md` | Sole current task-state summary; native checkboxes are implementation progress |

In Spec Kit mode, do not also maintain `docs/design/<TASK-ID>.md` or `docs/exec-plans/<TASK-ID>.md` for the same design/work plan. Use the [DESIGN](templates/DESIGN_TEMPLATE.md) and [PLAN](templates/PLAN_TEMPLATE.md) templates as completeness prompts inside the native files. Manual mode keeps the original locations. Shared AGENTS, ownership, environment, testing, code maps, and handoff records still apply in both modes.

## 3. Install and adopt safely in an existing repository

Template conformance is mandatory under [SOP Section 4.1](../Code_SOP.md#41-mandatory-template-conformance-for-ai-and-human-authors). Keep native artifact structure, incorporate every applicable DESIGN/PLAN requirement, and include a mapping from each source template section to its native artifact section (or a specific N/A reason). TASK, write_code, TEST_REPORT, review, and other SOP records retain their own template structures. Generated defaults do not waive required fields or evidence.

The setup owner first checks the pinned [core reference](https://github.com/github/spec-kit/blob/e77daa9021d20db26b878f7dfa5640fe5a42d04e/docs/reference/core.md), prepares Python **3.11 or newer**, [uv](https://docs.astral.sh/uv/getting-started/installation/), Git, and the Codex CLI, and records actual versions in ENVIRONMENT. The pinned package's [Python requirement](https://github.com/github/spec-kit/blob/e77daa9021d20db26b878f7dfa5640fe5a42d04e/pyproject.toml) applies to Spec Kit; application dependencies retain their own verified requirements. The following commands are adoption instructions, not an installation report:

```powershell
uv tool install specify-cli --from 'git+https://github.com/github/spec-kit.git@e77daa9021d20db26b878f7dfa5640fe5a42d04e'
specify version
specify --help
specify init --help
```

Run commands individually; resolve failures before continuing. This version initializes from the templates, scripts, and workflow bundled with the installed package/source. Installed presets, extensions, and project overrides can change the effective output; record and inspect those inputs and the generated assets as part of setup.

Generate the integration in a **new staging directory**, separate from the application checkout:

```powershell
$specKitStaging = Join-Path $env:TEMP ('ai4r-spec-kit-' + [guid]::NewGuid().ToString('N'))
specify init $specKitStaging --integration codex --script ps --non-interactive
```

`--non-interactive` suppresses prompts; it does not bypass the Codex CLI availability check. If staging occurs on a machine whose agent runs elsewhere, the setup owner may explicitly use `--ignore-agent-tools` for generation, then verify the actual agent environment separately before claiming setup complete.

The setup owner then performs a reviewed adoption change on their assigned personal branch:

1. Inspect the staged `.specify/` templates, scripts, memory, and `.agents/skills/` instructions. Record asset versions and hashes. Inspect optional presets, extensions, workflows, and hooks before enabling them.
2. Compare each proposed file with existing application files. Integrate selected content explicitly; preserve existing AGENTS, agent configuration, and project rules. Do not run a blind `init --here --force`, copy over conflicts, or initialize inside `docs/code/`.
3. Start `.specify/memory/constitution.md` from the [constitution template](templates/SPEC_KIT_CONSTITUTION_TEMPLATE.md). Fill project facts, link the actual SOP and instruction paths, and obtain recorded Lead ratification before using it as adopted policy. An AI-generated ratification date or signature is invalid.
4. Link the constitution, TASK registry, approved native artifacts, and `write_code.md` from root and applicable local AGENTS. Read and reconcile generated skills with these rules.
5. Keep the optional upstream Git extension disabled. In this pinned version, core feature directories do not require new Git branches; the Git extension introduces repository/branch operations and optional automatic commits. The team's existing [Git workflow](GIT_WORKFLOW.md) remains authoritative.
6. Validate feature selection, generated artifacts, human stop points, and a low-risk pilot. Review the actual generated diff and record the result in the adoption checklist before enabling the Standard/High-risk default.

Keep `.specify/feature.json` local and untracked. During adoption, check `git ls-files -- .specify/feature.json`; add `/.specify/feature.json` to the local exclude file located by `git rev-parse --git-path info/exclude`, or adopt an explicit reviewed `.gitignore` entry. An ignore rule does not untrack an existing file: if it is already tracked, make that transition a reviewed adoption change while preserving each user's current selection. Never stage the local selector or credentials. TASK records the shared task identity and exact feature directory.

## 4. Select a feature without changing branches

Synchronize the assigned personal branch with `origin/ai4r_main_branch` using GIT_WORKFLOW. Keep one pending task per persistent personal branch; separate concurrent work requires the Lead-approved task-branch procedure. A feature directory is not a Git branch name.

From the application root, replace this example with the exact TASK registration:

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'specs/AI4R-001-router-validation'
$env:SPECIFY_FEATURE_NO_PERSIST = '1'
```

Pass these variables into the **process that runs the agent and its tools**. An already running IDE agent may not inherit a new terminal's environment. Also give the agent the TASK-ID and exact feature path in its prompt; verify selection through that agent's tool environment before generation or implementation.

After adopting `.specify/`, inspect the resolved paths:

```powershell
& ./.specify/scripts/powershell/check-prerequisites.ps1 -PathsOnly -Json
```

Confirm `REPO_ROOT`, `FEATURE_DIR`, and the intended spec/plan/tasks paths. This option reports paths; it does not prove the files exist, that they are approved, or that checks passed. Inspect the actual files at each stage. `SPECIFY_FEATURE_DIRECTORY` takes precedence over `.specify/feature.json`'s `feature_directory`; `SPECIFY_FEATURE` is only a label and must not be used to select a directory or branch. Core scripts honor `SPECIFY_FEATURE_NO_PERSIST` for selector persistence; command instructions or hooks can still write files, so inspect the resulting diff.

Before another task, clear or replace the environment overrides in that same process and repeat the path check. On handoff, the next executor takes the feature path from TASK and sets their own local selection; do not transfer an implicit pointer as authority. For multiple active sessions, use separate authorized working directories and explicit feature selection in each session. Do not run concurrent specification commands against one checkout: the command can write the shared local pointer even when core script persistence is disabled.

## 5. Lifecycle and human gates

The Codex integration installs skills under `.agents/skills/speckit-<name>/SKILL.md`. The `$speckit-...` expressions below are **Codex chat invocations**, not PowerShell commands. Other integrations use their own verified syntax; do not assume old slash-command examples apply.

| SOP stage | Spec Kit activity | Required outcome before continuing |
| --- | --- | --- |
| Adoption | `$speckit-constitution`, if used, drafts an amendment from the team template | Lead ratifies the actual text/version; inspect the constitution diff and any separate installed-hook actions |
| Prepare | Confirm branch, baseline, environment, instructions, TASK registration, and resolved feature path | Correct work scope; recorded baseline checks and existing failures |
| Define | `$speckit-specify`, then `$speckit-clarify` where requirements are unclear | `spec.md` has stable AC IDs, non-goals, measurable criteria, and no invented thresholds |
| Design | `$speckit-plan` and targeted research; apply DESIGN completeness prompts | `plan.md` references shared architecture/contracts and covers failure paths, verification, compatibility, and recovery as applicable |
| Draft execution plan | `$speckit-tasks` proposes steps from the specification/design; apply PLAN prompts and explicitly request agreed verification tasks | Scope, file paths, dependencies, checks, and stop conditions are ready for human review; drafted tasks authorize no execution |
| Preflight | `$speckit-checklist` where useful; `$speckit-analyze` for consistency | Resolve material contradictions without silently rewriting approved requirements; generated checklist quality is not proof of executed tests |
| Approve and authorize | Lead reviews the identified spec/plan versions and proposed task scope, then issues `write_code.md`; affected owners confirm cross-module changes | Real design decision and implementation authorization cover the actual versions and paths; unresolved blockers remain blockers |
| Implement | `$speckit-implement` with applicable AGENTS, constitution, TASK, approved spec/plan, tasks, and write_code | Author inspects every changed file; work stays within the actual authorization |
| Self-check | Inspect diff, run agreed verification, record TEST_REPORT; optionally run `$speckit-converge` after implementation | Truthful evidence for the implementation/base commits; any remediation goes through scope and evidence checks |
| Review | Follow `review.md`: AI inspects the actual diff, callers, contracts, and evidence, then the Lead reads functions/call chains | Findings addressed, required verification disposition valid, and real human decision covers the current version |
| Integrate and hand off | PR into `ai4r_main_branch`; actual merge checks, status update, and handoff | SOP Definition of Done, including required deferred verification, satisfied |

Use a prompt such as the following, filling actual values and references:

```text
TASK-ID: [ID]. Feature directory: [exact path]. Branch: [assigned branch].
Read the applicable AGENTS, team constitution, TASK registry, and write_code.
Use spec.md as the sole requirements/AC source, plan.md as feature design,
and tasks.md as the sole implementation work/progress record.
Honor the approved versions and allowed paths listed in write_code.
Do not create/switch branches or grant approvals. Preserve existing work.
Stop dependent work if requirements, design, shared contracts, thresholds,
or authorized scope must change. Report the conflict and required decision.
Report actual checks, results, covered commits, and unverified claims.
```

Before design approval and `write_code.md`, drafting specification/design/task proposals is planning work only. Do not let a generated task or quickstart turn into unauthorized production implementation. Ordinary choices already inside approved boundaries do not require repeated approval.

The pinned upstream [task generator](https://github.com/github/spec-kit/blob/e77daa9021d20db26b878f7dfa5640fe5a42d04e/templates/commands/tasks.md) treats test tasks as optional unless the specification or user explicitly requests them. State the agreed risk-proportionate checks and pass criteria in `spec.md`/`plan.md`, and explicitly request those verification tasks when invoking `$speckit-tasks`. Check coverage before implementation; neither an absent generated test nor a checked task box waives the SOP's verification gate.

## 6. Generated commands are actions, not gate evidence

- **Constitution:** the pinned command writes `.specify/memory/constitution.md`; its instructions prohibit modifying dependent templates or source. Installed hooks can add separate effects. Review the diff and any temporary Sync Impact Report before removing that report for commit; no command can ratify its own policy or weaken the seven principles.
- **Plan and tasks:** generated `research.md`, `data-model.md`, `contracts/`, and `quickstart.md` may be useful supporting artifacts. Review their correctness and relationship to shared authorities. A quickstart describes validation; it is not a substitute for TEST_REPORT.
- **Implement:** may write code/tests, update `tasks.md` checkboxes, and create or modify ignore/configuration files. Inspect those changes, including anything outside the expected implementation list. Its checklist prompt does not replace human design approval or expand `write_code.md`.
- **Analyze:** provides consistency findings, not independent human review or proof that code passed tests. Prerequisite scripts and installed hooks may still have side effects even when the analysis intends no artifact edits.
- **Converge:** runs after implementation of the current task list and compares code with the declared specification/design. It can append remediation tasks; it is not a read-only diff review. Review each addition against current authorization before another implementation run. A `Converged` conclusion does not establish testing, acceptance, or merge approval.
- **Hooks and extensions:** commands may invoke installed hooks. Inspect `.specify/extensions.yml`, installed extension code, presets, and workflows before enabling or upgrading them. Do not enable automatic commits, pushes, branch changes, or releases through an unreviewed helper.

If a generated output changes accepted requirements, interfaces, architecture, critical assumptions, or scope, use CHANGE_REQUEST and pause dependent work. Preserve the approved version and record the superseding decision. If implementation changes after verification/review, apply the SOP's evidence-validity rules and rerun affected checks. AI may draft records but must not manufacture results, approvals, identities, or timestamps.

## 7. Official pinned references

- [Release v1.0.12](https://github.com/github/spec-kit/releases/tag/v1.0.12)
- [Core CLI and feature-directory reference](https://github.com/github/spec-kit/blob/e77daa9021d20db26b878f7dfa5640fe5a42d04e/docs/reference/core.md)
- [Agent integrations](https://github.com/github/spec-kit/blob/e77daa9021d20db26b878f7dfa5640fe5a42d04e/docs/reference/integrations.md)
- [Command templates and their actions](https://github.com/github/spec-kit/tree/e77daa9021d20db26b878f7dfa5640fe5a42d04e/templates/commands)
- [PowerShell feature-path resolution](https://github.com/github/spec-kit/blob/e77daa9021d20db26b878f7dfa5640fe5a42d04e/scripts/powershell/common.ps1)
- [Optional Git extension manifest](https://github.com/github/spec-kit/blob/e77daa9021d20db26b878f7dfa5640fe5a42d04e/extensions/git/extension.yml)

For upgrades, compare the new commands, scripts, templates, hooks, and feature-selection rules with this mapping, repeat the pilot checks, and update ENVIRONMENT and this guide together.
