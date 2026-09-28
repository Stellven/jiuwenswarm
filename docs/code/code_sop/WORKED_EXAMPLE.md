# Applying This SOP: Manual and Spec Kit Examples

The fictional teaching examples below have no actual implementation, test execution, approval, or merge. They illustrate how documents connect; they do not define Router's actual interfaces or architecture. Select one artifact mode per real task and register its actual sources in TASK.

## Manual Example: Add an Observable Failure Result to a Confirmed Module Interface

For fictional task `AI4R-EXAMPLE`, suppose a module must return an agreed failure result when no candidate is available. Both the current interface and its consumer need to change, so the task follows the high-risk path. This example represents an existing Manual task or a new task with an explicitly approved Manual fallback because Spec Kit setup is blocked. New Standard/High risk tasks use Spec Kit by default after setup and successful pilot validation. If the actual design differs, substitute the real scenario; do not copy this example as a product requirement.

| Stage | Actions and records | Condition for proceeding |
| --- | --- | --- |
| Preparation | The owner confirms actual code paths. The author synchronizes their personal branch and records the main-branch SHA and baseline condition. | Paths, roles, environment, and baseline are confirmed. |
| Task | TASK states that no available candidate must produce the agreed failure result. AC-01 verifies the output, AC-02 verifies consumer handling, and AC-03 verifies the existing normal path. | The Lead confirms the task scope. |
| Design | DESIGN explains the approach. CONTRACT defines schema, error semantics, and compatibility strategy. An ADR records tradeoffs when needed. | The Lead, provider, and consumer confirm the specific version. |
| Authorization | The Lead publishes write_code, listing the interface, implementation, and consumer paths that may change. | Authorization covers this implementation. |
| Planning | PLAN separates contract, implementation, consumer, and unit/integration testing steps. FILE_MAP records file and function relationships. | The steps remain within the approved design. |
| Development | The author implements in small steps and updates the checklist. Compatibility conflicts trigger a CHANGE_REQUEST. | The conflict is resolved or the revision is approved. |
| Verification | TEST_REPORT maps AC-01/02/03 to commands, test cases, environment, and actual results. | Required checks pass and have real evidence. |
| AI review | review records checks of the current diff, contracts, exceptions, and callers. The author addresses findings. | Blocking findings are resolved and reviewed again. |
| Human review | The Lead reads affected functions and confirms consistency across providers and consumers and the feasibility of rollback. | The current version has human approval. |
| Merge and handoff | The PR merges into the team main branch. The actual merge result is verified, and status and HANDOFF are updated. | Verification after merging and handoff are complete. |

## Manual Traceability Chain

```text
AC-01 in TASK
  -> Approach in DESIGN
  -> Failure output contract in CONTRACT
  -> Implementation boundaries in write_code
  -> File and function steps in PLAN
  -> Corresponding checks and results in TEST_REPORT
  -> AI findings and resolutions + human decision in review
  -> PR merge commit and acceptance record in HANDOFF
```

In this Manual example, maintain acceptance criteria only in TASK. Other documents reference AC identifiers and describe their implementation and verification mappings. If acceptance criteria change, update their approval through the change record rather than only changing test expectations.

## Spec Kit Example: Propose an Offline SOP Link Checker

Fictional task `AI4R-SPEC-EXAMPLE` proposes a small new tool that checks local Markdown file links under `docs/code/`. This is a Standard task because it introduces new behavior. The proposed implementation and test paths are `scripts/check_code_sop_links.py` and `tests/unit_tests/scripts/test_code_sop_links.py`; neither is claimed to exist or be approved. Owner, actual feature directory, branch, implementation authority, and results remain pending.

After repository setup, TASK registers `Artifact mode: Spec Kit`, the actual `specs/<feature-directory>/`, personal/approved task branch, baseline, and artifact versions. The sequence below names workflow stages, not executable commands. Use [SPEC_KIT_WORKFLOW](SPEC_KIT_WORKFLOW.md) for the verified tool version and invocation details.

| Stage | Authoritative artifact or action | Gate or evidence |
| --- | --- | --- |
| Specify | Draft spec.md with the problem, scope, non-goals, and stable AC identifiers | AC-01: valid local file targets pass; AC-02: missing targets produce a nonzero result with source location and target; AC-03: external URLs and fenced examples are excluded. These are illustrative criteria, not approved requirements. |
| Clarify | Resolve link syntax, fragment handling, repository boundaries, and platform assumptions in spec.md | No hidden requirement decisions; unresolved questions have owners and state whether they block design. |
| Plan | Put technical design, affected files, failure handling, and fixture-based verification strategy in plan.md | Use DESIGN completeness prompts here; do not create a separate docs/design copy. |
| Tasks | Put ordered fixture, implementation, test, and package-check work items in tasks.md | Map work items to ACs and dependencies; use PLAN completeness prompts without a parallel execution plan. |
| Analyze | Check specification, design, work items, and SOP consistency | Record and resolve material findings; this analysis is not AI code review or human approval. |
| Human design approval and write_code | The Lead approves identified specification/design versions and the implementation boundary; write_code references permitted work-item IDs | Until an actual human decision exists, implementation remains unauthorized. One explicit decision may cover the listed artifacts and directive. |
| Implement | Execute only authorized work items on the registered branch; maintain progress in tasks.md | The author explains every changed file. Root/local AGENTS and authorization remain binding. |
| Test | Run the approved fixture and integration checks on the actual implementation; write TEST_REPORT | Record commands, environment, C/B, actual results, and limits before formal review; no results are prefilled here. |
| AI review | Inspect the implementation diff, callers, spec/plan conformance, and test evidence in review.md | Resolve findings and recheck affected work; native analysis does not replace this stage. |
| Human review | The Lead reviews affected functions, parsing/error paths, and evidence | A human decides whether the current version can merge; generated checkboxes are not approval. |
| Merge and handoff | Target ai4r_main_branch, verify the actual merge result, update status, and hand off | Done requires the existing SOP gates, required follow-up checks, and handoff to be complete. |

In the real task, `spec.md` alone defines requirements and acceptance; `plan.md` alone defines the technical design; `tasks.md` alone maintains ordered work and its progress. TASK is the register, write_code supplies human implementation authorization, and IMPLEMENTATION_CHECKLIST records SOP gates and author understanding. Test and review records reference native AC/work-item identifiers without maintaining competing criteria or progress tables. The illustrative AC descriptions above are teaching text, not a second source for any actual task.

## Handling Report SHAs in Practice

Let the implementation commit be `C` and the tested team main-branch baseline be `B`. The author runs checks on the clean implementation at C, then creates commit `D` containing only the result report. The report references C and B. The PR/review explains that D only adds records and verifies that C to D contains no changes to implementation, configuration, tests, contracts, or acceptance criteria. Another report commit is not required merely to record D's SHA.

If a later fix creates commit `E`, the original test conclusions do not automatically cover the portions changed by E. Run the affected checks and review again, then record the new implementation scope. Reassess main-branch updates according to their impact as well.

## Simplifying a Small Change Without Mandatory Tooling

Suppose the task only fixes a broken link in explanatory documentation. Keep the simplified Manual mode: TASK records the problem, the criterion for a correct link, and a brief design. write_code identifies the file and boundaries. The plan, checklist, and link verification can be three sections within TASK. Obtain a brief approval first, complete the edit and link check, then record AI and human review. A broken-link fix does not require native spec/plan/tasks files or new architecture, contract, ADR, release, or incident documents. Existing Manual work is not automatically migrated; record any deliberate source change and retire superseded authority rather than maintaining two versions.

## Handoff During a Task

If someone else takes over before completion, record the actual status rather than Done. HANDOFF lists the branch, implementation SHA, uncommitted working-tree changes, last successful check, unresolved questions, required prerequisites, and next commands. The recipient resumes from these entry points without depending on the original author's chat history.
