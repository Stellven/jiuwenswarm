# Verification run: RUN-20261006-FRAMEWORK-01

## 1. Execution identity

| Field | Actual value |
| --- | --- |
| TASK ID / run ID / UTC time | M0-SYSTEM / RUN-20261006-FRAMEWORK-01 / 2026-10-06T17:28:00.322003+00:00 |
| Level and V IDs | Documentary BLOCK / M0-SYSTEM V01; documentary BOUNDARY / M0-SYSTEM V02; AC-001 only |
| Candidate identity | Dirty documentation candidate on ai4r_xiaoyang; HEAD 2cc0b8695d4000cc72af64eb781356697f7fd861; complete relevant file hashes and tracked diff digest in [framework-candidate.json](framework-candidate.json). This is an authoring candidate, not an implemented runtime. |
| Baseline / component revisions | TASKS/TASK/spec/plan/tasks and IF agreements r1; Spec Kit local adapter 1.1.2; native initialization created no project-owned files and preserved existing rules. |
| PRD, spec, plan and IF versions | Primary PRD SHA256 897af8427e2cf4e2427a2097b9b9e8a5a427a7de53b89f4e541d2cc437594036; 184 numbered headings; all 68 supplied source files in [source manifest](../../source-manifest.json); 21 features, 20 owned IF@r1 agreements. |
| Working directory / platform / runtime / dependency versions | D:/research/ai_for_research/jiuwenswarm; Windows-11-10.0.22631-SP0; Python 3.13.1; Windows PowerShell; no application or provider runtime used. |
| Input/fixture/dataset/model/prompt/configuration versions | Supplied PRD and architecture with USR-01/02 clarifications; current documentary registry; isolated copied framework plus eight intentional corruptions. Models, scientific datasets and product prompts: N/A to documentation acceptance; exact upstream verifier source/revision remains PENDING_SOURCE. |
| Dependency mode and actual services | Real local files, Git read-only identity, installed plugin template/setup/prerequisite tools and Python document validator. No live model/search/RSI service or application test. |
| Command or reproducible manual procedure | From repository root: `python docs/code/Missions/M0/tools/validate_framework.py --level BLOCK`, then `--level BOUNDARY`. For each registry feature set SPECIFY_FEATURE_DIRECTORY and run installed `scripts/powershell/check-prerequisites.ps1 -Json -RequireSpec -RequireTasks -IncludeTasks` in a separate PowerShell process. Native plan/task setup used the same explicit selection. Fault mutations and diagnostics are retained in [document-fault-fixtures.json](document-fault-fixtures.json); runner is `D:/research/ai_for_research/.codex_work/m0-spec-kit/check_faults.py`. |

## 2. Per-check observations

| V ID / AC references | Expected outcome / threshold source | Actual outcome | Exit code / counts including skips | Result | Raw artifact location |
| --- | --- | --- | --- | --- | --- |
| M0-SYSTEM V01 / AC-001 | Source identities, complete source allocation, registered four-file artifacts, AC/B/V/T mappings, one IF owner, acyclic definition order, truthful evidence and native prerequisites; spec AC-001 | Validator passed; all 21 features recognized by native prerequisites. Both setup helpers succeeded for all 21 features. | Validator exit 0; 21/21 prerequisites and 21/21 each setup helper; zero required skips | PASS | [BLOCK output](document-block.json), [prerequisites](native-prerequisites.json), [plan setup](setup-plan-results.json), [tasks setup](setup-tasks-results.json) |
| M0-SYSTEM V02 / AC-001 | Connected documentary links and agreement consumers; exact source-copy alignment; English generated prose; requested distinction/adaptation and primary capsule mapping; spec AC-001 | Boundary validator passed. All eight deliberately corrupt fixture variants were refused, and the initial/restored copies passed. Three authorized architecture files match their M0 copies byte-for-byte. | Validator exit 0; 10/10 fixture checks (2 valid + 8 expected refusals); zero required skips | PASS | [BOUNDARY output](document-boundary.json), [fault observations](document-fault-fixtures.json), [candidate/source identity](framework-candidate.json) |

Documentary counts: 21 features, 184 numbered PRD clauses, 169 ACs/blocks, 338 planned checks, 570 work items and 20 owned interfaces. Required product work remains unchecked; planned product commands were not run.

## 3. Scope and validity

- Behavior established: English local Spec Kit framework; full numbered-source/architecture allocation; template-compatible TASK/spec/plan/tasks; one owned revisioned interface with reciprocal consumers; aligned planned paths; native prerequisite discovery; required architecture prose and Spec Kit adaptation obligations. Main-package identities remain unchanged.
- Behavior not established / failures / blockers: no product implementation, installed workstation, secure runner, live provider assessment, complete research journey, scientific result, RSI or Phase 3 behavior established. Upstream verifier bodies/revision, actual profile/fixture protocols and supported runtime environments remain dependent prerequisites. Runtime AC-002 through AC-012 and all other feature ACs remain NOT_RUN.
- Reproducibility details for model/evaluation runs: N/A; document fixtures are exact valid/invalid inputs, not a model reliability measurement. Fault cases cover missing source allocation, stale source bytes, broken link, dependency cycle, duplicate IF owner, unobserved acceptance claim, command/work path disagreement and non-English generated native text.
- Reused earlier evidence and comparison basis: no product evidence reused. Setup outputs and local source inspection are retained only as preparation evidence. Independent architecture/PRD/native reviews produced corrections in the authoritative records; they do not constitute runtime PASS.
- Superseded run IDs / reason: none. Earlier authoring diagnostics were corrected before this accepted documentary run.
- Follow-up V/work-item references: framework T003/T004/T027 complete; runtime T001/T002 and remaining T005 onward remain required as mapped in [tasks.md](../tasks.md). M0-007 AC-010/B10/V19/V20 owns exact upstream adaptation acceptance.
- Candidate/input changes after this run: final evidence links/status entries were checked on the recorded documentary candidate. Material normative document/source/interface changes invalidate V01/V02 and require rerun; product candidate acceptance remains separate.

The local feature pointer selects M0-001. No staging, commit, push, deployment or live-provider campaign was performed.
