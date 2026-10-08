# Git and integration
This is a supporting transport guide, not a review/authorization workflow.

## Branches
The team integration branch is ai4r_main_branch. Persistent personal branches are ai4r_xiaoyang, ai4r_saurav, ai4r_ramika and ai4r_muk. Record actual checkout, branch and baseline in TASK.

Keep unrelated task changes separable. Concurrent tasks may use task branches and isolated checkouts. A feature-directory name does not change the Git branch. Preserve existing work before switching, synchronizing or resolving conflicts.

## Read-only inspection
Run from the actual checkout:
```powershell
git status --short --branch
git diff --stat
git diff --check
git rev-parse HEAD
```
The local repository used for this package is D:\research\ai_for_research\jiuwenswarm. Do not infer a clean tree or a synchronized remote from a template.

## Integration and evidence
Use the registered TASK scope and Spec Kit work list. Integrate dependent blocks into an identifiable candidate and run the required boundary/system checks.

For commits or PRs when requested, link TASK, describe the behavior and point to native tasks.md evidence. Do not maintain a separate PR-template/checklist authority. The intended team PR base is ai4r_main_branch; inspect the actual target.

Conflict resolutions and base changes can invalidate evidence. Assess affected blocks and downstream journeys, then rerun checks as defined by VERIFICATION.md. Never assume that passing on a feature branch proves the combined candidate.

## No automatic commits
Commands, generated work items and hooks do not require commits. Honor a no-commit instruction, including during synchronization steps that could create merge commits. Record uncommitted candidate identity using the evidence rules.

Do not discard local changes, force-push shared branches or rewrite history to simplify integration. Recovery of data or external side effects may require more than reverting code; represent needed recovery work in the same TASK/Spec Kit system.
