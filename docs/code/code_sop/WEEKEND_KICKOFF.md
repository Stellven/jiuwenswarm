# Weekend Project Kickoff

Copy only the short message below into the team thread. The attachment list and setup reference are supporting material.

## Ready-to-send message

Hi everyone — for this weekend:

1. Download the [SOP pack](https://github.com/Stellven/jiuwenswarm/raw/refs/heads/ai4r_main_branch/docs/code/AI4Research_Weekend_Kickoff_Pack.zip), clone the [code](https://github.com/Stellven/jiuwenswarm), and use your personal branch.
2. Read `Code_SOP.md`, the Spec Kit guide, and the applicable `AGENTS.md` files.
3. Send your [kickoff reply](https://github.com/Stellven/jiuwenswarm/blob/ai4r_main_branch/docs/code/code_sop/templates/KICKOFF_REPLY_TEMPLATE.md): setup/blockers, preferred module, proposed first task with an acceptance check, and weekend availability.

We'll confirm responsibilities and approve designs before coding.

Attachments: SOP pack and kickoff reply template.

## What to send

| Resource | Location |
| --- | --- |
| Short message | Copy the section above |
| Documentation-only attachment | [AI4Research_Weekend_Kickoff_Pack.zip](../AI4Research_Weekend_Kickoff_Pack.zip) |
| Reply form | [KICKOFF_REPLY_TEMPLATE.md](templates/KICKOFF_REPLY_TEMPLATE.md) |
| Main SOP and full index | [Code_SOP.md](../Code_SOP.md) and [documentation index](README.md), also inside the pack |

The canonical documentation lives in `docs/code/` on `ai4r_main_branch` in `Stellven/jiuwenswarm`. The ZIP contains Markdown documentation only. Application source, dependencies, and task-specific assets are obtained separately.

## Setup reference — keep outside the message

| Person | Application working branch |
| --- | --- |
| Xiaoyang | `ai4r_xiaoyang` |
| Saurav | `ai4r_saurav` |
| Ramika | `ai4r_ramika` |
| Muk | `ai4r_muk` |

These branches exist on origin. Merge updates from `ai4r_main_branch` into your personal branch before starting; application PRs target that main branch. Personal branch names do not determine module ownership.

Use Git, Git LFS, and Python satisfying the repository requirement `>=3.11,<3.14`. The [environment guide](templates/ENVIRONMENT_TEMPLATE.md) contains candidate setup commands; record their actual results. Report access or setup blockers without sharing credentials. Confirm task-specific models, datasets, GPUs, and services with the module owner.

For Spec Kit tasks, follow the [Spec Kit guide](SPEC_KIT_WORKFLOW.md) for the pinned Specify CLI, uv, and agent integration. The Lead coordinates repository bootstrap once; teammates use the reviewed setup after synchronizing their branches. Report tooling readiness in the existing reply form. Do not each initialize over the shared repository's instructions or create a second set of requirements.

Follow the [Git workflow](GIT_WORKFLOW.md) and read applicable existing AGENTS files before editing. Use the [coding protocol](write_code.md) before implementation and the [review protocol](review.md) before review. The kickoff reply is the only new form everyone needs at this stage.

## Fresh-clone notes

Run from your chosen workspace. Existing clones should follow the Git workflow and preserve uncommitted work instead of cloning over an occupied directory.

```text
git clone --branch ai4r_main_branch https://github.com/Stellven/jiuwenswarm.git jiuwenswarm_stellven
```

The LFS object for `docs/assets/videos/JiuwenSwarm_Introduction.mp4` previously returned a server 404. If it prevents checkout, a fresh code-only clone may retain LFS pointers while the object is unavailable. This does not repair or download the missing assets, disable push hooks, or establish that resource-dependent tests pass.

PowerShell:

```powershell
$previousLfsSkip = $env:GIT_LFS_SKIP_SMUDGE
try {
    $env:GIT_LFS_SKIP_SMUDGE = '1'
    git clone --branch ai4r_main_branch https://github.com/Stellven/jiuwenswarm.git jiuwenswarm_stellven_code_only
    if ($LASTEXITCODE -ne 0) { throw 'Clone failed; record the error before continuing.' }
} finally {
    $env:GIT_LFS_SKIP_SMUDGE = $previousLfsSkip
}
```

Bash or zsh:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --branch ai4r_main_branch https://github.com/Stellven/jiuwenswarm.git jiuwenswarm_stellven_code_only
```

After a successful clone, enter its directory and switch to your personal branch. For Xiaoyang, when no local personal branch exists yet:

```text
git switch --track origin/ai4r_xiaoyang
git status --short --branch
git rev-parse HEAD
git rev-parse origin/ai4r_main_branch
```

Substitute the assigned branch for other teammates. Record HEAD and the fetched main-branch baseline separately in the reply. Report retained pointers and obtain the actual objects before running checks that depend on them. The SOP package is available in `docs/code/` after cloning the team main branch; on an existing personal branch, merge the latest main-branch updates to receive it.
