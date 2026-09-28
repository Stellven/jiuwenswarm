# Initial Team Adoption Checklist

Maintainer: Code Team Lead. Use this checklist to adopt the documentation package in the actual code repository. An unchecked item means a team configuration or decision remains outstanding; it does not mean this documentation generation failed.

## 1. Confirmed Initialization Facts

- Repository: `https://github.com/Stellven/jiuwenswarm.git`.
- Current local location: `D:\research\ai_for_research\jiuwenswarm_stellven`.
- On 2026-09-25, all five team branches were pushed and verified, each with its corresponding origin tracking branch. Their initial SHA was `52abe68db2dd167485f6bd79d6e36e193d608e64`.
- During the clone on that date, checkout was interrupted by a 404 for the LFS object associated with `docs/assets/videos/JiuwenSwarm_Introduction.mp4`. Code checkout was completed with the LFS pointer retained. Operations that depend on this video still require the object's availability to be restored.
- On 2026-09-28, the five team branches were renamed to the `ai4r_` prefix with unchanged suffixes and preserved history. Existing clones must update local names and upstream tracking using GIT_WORKFLOW.
- These facts do not establish that tests, branch protection, CI, or adoption of team rules are complete.

## 2. Establish Responsibilities and Actual Boundaries

- [ ] Identify the Lead, delegated reviewer, module owners, backups, and people responsible for merging and releases.
- [ ] Confirm the code scope of RSI, Router, Capsule, and Verifier, including shared files and scope across directories. Do not infer module ownership from personal branch names.
- [ ] Read existing global and local AGENTS files and register existing architecture, design, and interface documents.
- [ ] Build the initial FILE_MAP from the implementation and call chains; explicitly identify legacy code that has not yet been reviewed.
- [ ] Record unresolved questions as actionable TODOs with named owners rather than filling them with guesses.

## 3. Place Documentation and AGENTS Files

- [ ] Confirm the package in `docs/code/`, including `Code_SOP.md`, both AGENTS templates, and the entire `code_sop/` directory. Preserve this relative layout and use it as the canonical SOP entry point.
- [ ] Integrate the global template into `AGENTS.md` at the repository root, update its links, and complete required entry points.
- [ ] Integrate local `AGENTS.md` files into actual module subtrees. Merge with existing files instead of overwriting their instructions.
- [ ] Instantiate OWNERSHIP, ENVIRONMENT, TESTING, CURRENT_STATUS, and the required architecture and contract baselines.
- [ ] Integrate the PR template into `.github/pull_request_template.md`; first check for an existing team template.
- [ ] Check adopted links, task paths, and all instruction scopes. A template name containing `_global` or `_local` does not mean it will automatically be read as AGENTS.

## 4. Remote Governance: Check Only After Configuration

- [ ] Confirm that collaborators have the required read, push, review, and merge permissions.
- [ ] Configure applicable protection rules or rulesets for `ai4r_main_branch`, restricting routine direct pushes, force pushes, and deletion.
- [ ] Configure required checks and human review rules so that final approval covers the current implementation. Confirm available platform features and permissions.
- [ ] Identify the Code Team Lead or delegated reviewer as the merge approver. One ordinary platform approval does not by itself establish that the team's role requirements are satisfied.
- [ ] Confirm a merge strategy that preserves merge commits. If another strategy is selected, update the synchronization rules for persistent personal branches.
- [ ] Verify that the PR's default and actual base are the team main branch to avoid merging into another repository default branch.

This package does not provide a CODEOWNERS file with assumed usernames and has not created CI YAML. Configure and verify these mechanisms separately using confirmed identities, paths, and commands if they are adopted.

## 5. Environment and Verification Baseline

- [ ] Verify Python, dependencies, models, data, external services, GPU requirements, and LFS prerequisites on the actual operating system.
- [ ] Record every adopted command, working directory, configuration source, exit code, and result in ENVIRONMENT/TESTING.
- [ ] Separate pre-existing baseline failures from newly introduced failures. Check for skipped tests, tests that were not collected, and scripts that suppress errors.
- [ ] Derive quality, performance, cost, and latency thresholds from the design; do not invent uniform values in the SOP.
- [ ] Validate the complete process with at least one low-risk pilot task: design approval → write_code → implementation → tests → AI review → human review → merge verification → handoff.

### Spec Kit setup and pilot

Follow [SPEC_KIT_WORKFLOW](SPEC_KIT_WORKFLOW.md). Publishing this documentation does not complete the following items.

- [ ] Record the pinned Spec Kit source commit, integration, Python/uv versions, script shell, extensions, and local validation in ENVIRONMENT.
- [ ] Generate setup files in a fresh staging directory and inspect them; merge selected files into the application without overwriting existing AGENTS, configuration, or templates.
- [ ] Ratify `.specify/memory/constitution.md` from the [constitution template](templates/SPEC_KIT_CONSTITUTION_TEMPLATE.md), preserving all seven SOP principles and recording actual human approval.
- [ ] Verify integration command discovery and feature selection on the assigned personal branch. Keep automatic Git branching/commit hooks disabled; register any explicitly adopted extensions and their actions.
- [ ] Validate the local feature-pointer handling and prevent two tasks from selecting or generating into the same checkout concurrently.
- [ ] Run one Standard pilot through specification, clarification, plan, tasks, analysis, Lead design approval, write_code, implementation, actual tests, AI review, human review, integration, and handoff. The [worked example](WORKED_EXAMPLE.md) supplies an unexecuted candidate.
- [ ] Confirm TASK has one artifact mode and exact artifact paths; ACs, design, and implementation progress each have one authority, with no duplicate Manual records.
- [ ] Record pilot results and blockers below before claiming repository integration is operational. Keep Manual fallbacks explicit and preserve all existing gates.

## 6. Adoption Record

| Item | Actual record |
| --- | --- |
| Adopted SOP version | [TODO] |
| Approver, time, and evidence | Pending team approval |
| PR adopting documentation and rules | [TODO] |
| Pilot TASK-ID and outcome | Not performed |
| Spec Kit setup / integration / source commit / pilot evidence | Not performed; complete during repository adoption |
| Outstanding items and owner / date | [TODO] |
| Next review trigger | [TODO: when the pilot ends or the workflow reveals a problem] |

After adoption, use the actual governance documents as the source of current project facts. Retain this checklist as the initialization record.
