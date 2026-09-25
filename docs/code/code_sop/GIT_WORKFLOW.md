# Team Git Workflow

Repository: `Stellven/jiuwenswarm`. This document provides instructions; it does not mean every command below has been executed. Windows examples use PowerShell. Run each step individually and resolve any failure before continuing.

## 1. Branch Relationships

The team main branch is `huawei_waterloo_main_branch`. Personal branches are `huawei_waterloo_xiaoyang`, `huawei_waterloo_saurav`, `huawei_waterloo_ramika`, and `huawei_waterloo_muk`. Each personal branch tracks its remote branch with the same name. Bring updates from the team main branch into each personal branch through an explicit merge.

All five branches were pushed to origin on 2026-09-25. The examples below use Xiaoyang's branch; other developers should substitute their own branch. The branch checked out at the time of this documentation is still the team main branch. Developers should switch to their personal branch when starting work.

## 2. Checks Before Starting

```powershell
Set-Location 'D:\research\ai_for_research\jiuwenswarm_stellven'
git remote -v
git status --short --branch
git branch -vv
git fetch origin --prune
```

Confirm that origin is correct and that another task has not been mixed in. Understand and preserve uncommitted work before proceeding; do not automatically clean, overwrite, or stash someone else's changes. Run the following only after confirming that switching branches is safe:

```powershell
git switch huawei_waterloo_xiaoyang
git merge --ff-only origin/huawei_waterloo_xiaoyang
git merge origin/huawei_waterloo_main_branch
git rev-parse HEAD
git rev-parse origin/huawei_waterloo_main_branch
```

If `--ff-only` fails, the local and remote personal branches have diverged. Inspect their history, identify whose changes are involved, and determine how to merge them. Do not overwrite them with a force push. See Section 5 for conflicts when merging the team main branch.

For a fresh clone that has only the remote personal branch and no local branch with the same name, first use `git switch --track origin/huawei_waterloo_xiaoyang` to establish tracking. Do not recreate a branch that already exists.

## 3. Implement, Commit, and Push

Record the synchronized implementation and base SHAs, then develop according to the approved design and write_code. Stage exact file paths to avoid committing local configuration, data, or another task's files.

```powershell
git diff --stat
git diff
# Replace these placeholders with actual paths; do not run them unchanged.
git add -- '<task-file-path-1>' '<task-file-path-2>'
git diff --cached
git diff --cached --check
git commit -m 'AI4R-001: describe the approved behavior change'
git push origin huawei_waterloo_xiaoyang
```

Run the checks specified by write_code before committing. Replace the TASK-ID and description in the commit message with the actual task. Pushing a personal branch updates the shared working location; it does not establish that tests passed or that a merge was approved.

If a push is rejected, fetch and understand the remote updates first. If an LFS object is missing, record the object and contact its maintainer to restore it; skipping a check does not restore the object. Do not use `--force`, disable hooks, or delete history to bypass the problem.

## 4. PR and Merge

1. A Draft PR may be opened early for collaboration. Fetch and merge the latest team main branch again before formal review.
2. After resolving conflicts or adding changes, rerun affected checks and update TEST_REPORT, AI review, and any required human confirmation.
3. The PR head is the personal or task branch. The base must be `huawei_waterloo_main_branch`. Complete the [PR template](templates/PR_TEMPLATE.md).
4. Complete AI review and address its findings first. The Code Team Lead or independent delegate then reviews the current functions and call chains.
5. The person merging verifies that the current head and base match the evidence, blocking findings are closed, and approval remains valid. Required checks must have passed or be covered by a specific Lead-approved deferral explicitly permitting merge. All other gates still apply; a deferral cannot bypass known blocking defects or current acceptance failures. Deferred checks remain incomplete, and the task cannot be Done until they are completed.
6. Use a merge commit by default. Verify the actual merge commit afterward, then update status and handoff records.

This workflow does not assume that GitHub already enforces these rules. Consult the team's adoption record for the actual protection configuration. An unapproved PR must not be merged simply because the interface enables the Merge button.

Keep persistent personal branches after merging and repeat the synchronization steps before the next task. Do not repeatedly carry old task commits left after a squash merge into new PRs. If the team switches to a squash strategy, the Lead should define a task-branch alternative or a safe migration process.

## 5. Resolve Conflicts

```powershell
git status
git diff --name-only --diff-filter=U
```

Contact the owners of conflicting files and read the intent of both changes and the latest contracts. Resolve files individually, run the affected tests, stage the exact paths, and complete the merge. Do not blindly select ours/theirs for whole groups of files.

If you are not ready to resolve this merge, first confirm that this merge is in progress, then use:

```powershell
git merge --abort
```

This command attempts to restore the pre-merge state. It does not replace saving uncommitted work before starting. If restoration fails, preserve the current state and seek help instead of continuing with reset/clean. Update the baseline and affected evidence after recovery.

## 6. Concurrent Tasks and Upstream Updates

A persistent personal branch carries only one task awaiting merge at a time. For concurrent tasks, obtain the Lead's agreement and create short-lived task branches from the latest team main branch, with names such as `task/AI4R-001-xiaoyang`. Each PR contains only its own task. Separate task working directories may use git worktree, but file and dependency boundaries must still be explicit.

Absorb updates from the upstream default branch through a separate integration task and PR. Record the source SHA, conflicts, compatibility, regression scope, and owners. Do not mistake `origin/HEAD` for the team main branch and replace local history with it.

## 7. Failures After Merging and Rollback

Use the [incident template](templates/INCIDENT_TEMPLATE.md) to establish impact, containment, and recovery goals first. Prefer a new revert PR on the shared main branch to preserve history; do not force-push a branch pointer backward. Data migrations, model artifacts, and external side effects may not be restored by Git revert and must be handled separately.

Create an authorized rollback task branch from the latest team main branch. Verify the commit to revert and its parents first. Replace all placeholders in these commands:

```powershell
git show --no-patch --pretty=raw '<commit-SHA-to-revert>'
# For an ordinary commit:
git revert '<ordinary-commit-SHA>'
# Only for a merge commit, after verifying that parent 1 is the team mainline to retain:
git revert -m 1 '<merge-commit-SHA>'
```

Select the appropriate revert command for the actual commit type; do not execute both examples in sequence. Check the revert diff, perform the required recovery verification, and follow AI review, human review, and PR procedures. If the revert itself conflicts, assess current dependencies first instead of overwriting entire files with historical versions. Treat subsequent fixes and reintroduction of the feature as new tasks.
