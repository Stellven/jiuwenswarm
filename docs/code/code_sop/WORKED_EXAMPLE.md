# Applying This SOP to One Task

The following fictional teaching example, `AI4R-EXAMPLE`, has no actual implementation, test execution, approval, or merge. It illustrates how the documents connect; it does not define Router's actual interfaces or architecture.

## Scenario: Add an Observable Failure Result to a Confirmed Module Interface

Suppose a module must return an agreed failure result when no candidate is available. Both the current interface and its consumer need to change, so the task follows the high-risk path. If the actual design differs, substitute the real scenario; do not copy this example as a product requirement.

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

## Minimum Traceability Chain

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

Maintain acceptance criteria only in TASK. Other documents reference AC identifiers and describe their implementation and verification mappings. If acceptance criteria change, update their approval through the change record rather than only changing test expectations.

## Handling Report SHAs in Practice

Let the implementation commit be `C` and the tested team main-branch baseline be `B`. The author runs checks on the clean implementation at C, then creates commit `D` containing only the result report. The report references C and B. The PR/review explains that D only adds records and verifies that C to D contains no changes to implementation, configuration, tests, contracts, or acceptance criteria. Another report commit is not required merely to record D's SHA.

If a later fix creates commit `E`, the original test conclusions do not automatically cover the portions changed by E. Run the affected checks and review again, then record the new implementation scope. Reassess main-branch updates according to their impact as well.

## Simplifying a Small Change

Suppose the task only fixes a broken link in explanatory documentation. TASK records the problem, the criterion for a correct link, and a brief design. write_code identifies the file and boundaries. The plan, checklist, and link verification can be three sections within TASK. Obtain a brief approval first, complete the edit and link check, then record AI and human review. A broken-link fix does not require new architecture, contract, ADR, release, or incident documents.

## Handoff During a Task

If someone else takes over before completion, record the actual status rather than Done. HANDOFF lists the branch, implementation SHA, uncommitted working-tree changes, last successful check, unresolved questions, required prerequisites, and next commands. The recipient resumes from these entry points without depending on the original author's chat history.
