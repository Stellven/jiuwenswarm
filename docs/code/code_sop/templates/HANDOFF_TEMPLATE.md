# Handoff record: [TASK-ID]

> Suggested location: `docs/tasks/<TASK-ID>/HANDOFF.md`. Use for changes of person or session, pauses, or unresolved work and risks. A completed small change may retain equivalent information in TASK or the PR without a separate file. Handoff state, versions, evidence, remaining work, and next steps are required; use N/A with reasons elsewhere. A handoff records facts and does not grant implementation, review, merge, or release authority.

## 1. Handoff snapshot — required

- Sender / recipient / time and timezone: [Fill in; disclose an unassigned recipient].
- Task goal and approved scope: [Fill in].
- Live task state: [Actual TASK-ID row/link in `docs/governance/CURRENT_STATUS.md`; this is the only current-state source].
- State at handoff and snapshot time: [Copy the state at the stated time; this historical snapshot does not replace CURRENT_STATUS].
- Risk level and main reasons: [Fill in].
- Most important current fact: [One sentence describing actual progress or the blocker].
- Receipt confirmation: [Pending / actual recipient and confirmation evidence].

Use the same state names as CURRENT_STATUS: `Backlog / Design pending / Ready / In progress / Blocked / AI review / Human review / Ready to merge / Merged / Done`.

## 2. Locations and versions needed to resume — required

| Item | Actual location / identifier |
| --- | --- |
| Repository working directory / remote URL | [Fill in] |
| Current working branch / HEAD | [Actual branch and full SHA] |
| Target branch / verified baseline B | `ai4r_main_branch`, [full SHA and verification time] |
| Verified implementation C / integration version | [Actual SHA or reproducible tree; disclose when unverified] |
| Working-tree state | [Clean, or uncommitted/untracked files and ownership] |
| Task registry / artifact mode | [Actual TASK path/version; Manual or Spec Kit] |
| Acceptance source | [Manual: registered TASK section; Spec Kit: registered `spec.md`; exact path/version and AC identifiers] |
| Technical design and implementation authorization | [Manual: registered design/TASK minimum design; Spec Kit: registered `plan.md`; exact artifact and `write_code.md` versions, human approval evidence] |
| Global and applicable local rules | [Root and module `AGENTS.md` paths] |
| Ordered work and progress | [Manual: registered execution plan/TASK brief plan; Spec Kit: registered `tasks.md`; exact path/version and next work-item identifiers] |
| Spec Kit feature context | [Registered feature directory, initialized project root, pinned tool/setup reference, actual branch mapping, and session restoration method; Manual: N/A] |
| Verification evidence | [Actual TEST_REPORT or TASK/PR verification section] |
| AI and human review | [Actual task `review.md` and decision evidence] |
| PR / other evidence | [Actual links; state none if absent] |

Keep references to real files or sections; do not create empty records just to satisfy a link. Do not clear the working tree or overwrite other changes for handoff. Identify ownership and preservation of uncommitted work; another checkout may not contain it.

## 3. Completed work and author understanding — required

Reference the actual FILE_MAP, checklist, or TASK/PR understanding record when available. Summarize only what the recipient needs; do not maintain a competing copy.

| File or file group | Completed behavior / responsibility | Related functions and calls | Verification evidence | Limitations |
| --- | --- | --- | --- | --- |
| [Fill in] | [Fill in] | [Key items] | [Commit, command, log, or source section] | [Fill in] |

- Decisions already made and reasons: [Reference design or plan records].
- Design deviations and authority: [Fill in; unapproved approaches remain Proposed].
- Function-level review actually completed by the Code Lead: [Record and version; state incomplete when applicable].

## 4. Reproducible verification — required

Reference the authoritative report or TASK/PR section. If the relevant evidence is recorded here, provide reproducible details; do not copy results into multiple independently maintained records.

| Working directory | Preconditions / environment | Actual command | Actual result | Version and evidence |
| --- | --- | --- | --- | --- |
| [Fill in] | [Runtime, dependencies, data/model identifiers; no secrets] | [Fill in command or precise evidence reference] | [Passed / Failed / Blocked / Not run] | [C/B and logs] |

- Acceptance and performance: [Registered TASK or `spec.md` version/AC, design measurement protocol, measured baseline/current values or report section; explain N/A].
- Changes after C: [Range, files, verification command, and result].
- Approval applicability: [Covered version and whether approval remains valid; mark pending when unverified].

The handoff does not need its own commit SHA. Later explanatory documentation may reuse implementation evidence only after confirming it does not affect code, execution, tests, design, or acceptance. Other changes and baseline movement require impact assessment, relevant revalidation, and human confirmation.

Native analyze, requirements checklist, and convergence results do not replace runtime evidence, the task's AI review, or human approval. Preserve their actual scope and any convergence-added work still awaiting authorization. Required risk-proportionate verification remains in the registered work-item list; upstream optional-test defaults do not remove it.

## 5. Remaining work, blockers, and risks — required

| Type | Item and impact | Concrete next action | Owner | Dependency / completion criterion |
| --- | --- | --- | --- | --- |
| [To do / Blocker / Risk / Human decision] | [Fill in] | [Executable action] | [Name] | [Fill in] |

Preserve unresolved defects, skipped checks, environment differences, unapproved designs, and unverified baselines. If none are known, state the scope supporting that conclusion. Link deferred checks to their CHANGE_REQUEST, owner, and deadline; incomplete follow-up verification prevents Done.

## 6. Resumption steps and completion criteria — required

1. Read the TASK registry, registered requirements/design/work-item artifacts, `write_code.md`, and applicable `AGENTS.md`; verify exact versions and authorized scope.
2. Check the working tree and branch, preserve existing changes, and assess target-baseline movement.
3. Next actual action: [Specific file, function, issue, or command; avoid only saying "continue development"].
4. Complete verification for the affected scope, update AI `review.md`, then obtain Code Lead review.
5. Completion criteria: [Acceptance evidence, remaining-work closure, version-specific human decision, post-merge checks, and delivery/receipt evidence].

For Spec Kit mode, restore the exact registered feature directory in the process that runs the agent and its scripts; a setting in an unrelated shell does not update an already-running agent. In PowerShell, set `$env:SPECIFY_FEATURE_DIRECTORY = '[registered repository-relative feature directory]'`, then use `& ./.specify/scripts/powershell/check-prerequisites.ps1 -PathsOnly -Json` from the initialized project root to confirm `REPO_ROOT` and `FEATURE_DIR`. This resolves paths without validating artifact existence; check the registered files and versions separately. Do not infer feature selection from the Git branch or a previous session's `.specify/feature.json`, and do not rerun specify/tasks merely to resume. For setup, pointer persistence, and concurrent-session constraints, follow [SPEC_KIT_WORKFLOW](../SPEC_KIT_WORKFLOW.md).

- Details the recipient should not need to guess: [Fill in].
- Human decisions still needed and reasons: [Fill in or none].
- Merge/release facts at the snapshot time: [Actual SHAs, records, and action status; unexecuted actions remain incomplete].

Related templates: [TEST_REPORT](TEST_REPORT_TEMPLATE.md), [REVIEW](REVIEW_TEMPLATE.md), [RELEASE_ROLLBACK](RELEASE_ROLLBACK_TEMPLATE.md).
