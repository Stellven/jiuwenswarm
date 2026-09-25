# Huawei–Waterloo AI4Research Code SOP

An English documentation package for coordinating human and AI-assisted development across RSI, Router, Capsule, Verifier, and related modules.

## Start here

- [Code SOP](Code_SOP.md): the seven principles, responsibilities, development stages, review gates, and completion criteria.
- [Documentation index](code_sop/README.md): the complete catalog of guides, 21 reusable templates, and four module instruction drafts.
- [Weekend kickoff](code_sop/WEEKEND_KICKOFF.md): a ready-to-send team message, download instructions, reply requirements, and attachment list.
- [Adoption checklist](code_sop/ADOPTION_CHECKLIST.md): assign owners, confirm paths and commands, establish repository rules, and run a pilot task.
- [Worked example](code_sop/WORKED_EXAMPLE.md): follow one task from definition through verification, review, and handoff.

## Working with AI

- [Root AGENTS template](AGENTS_global.md) and [local AGENTS template](AGENTS_local.md).
- [Coding protocol](code_sop/write_code.md) and [review protocol](code_sop/review.md).
- [Git workflow](code_sop/GIT_WORKFLOW.md) for the application team's branches.

The main SOP explains the process; detailed instructions and reusable records remain in separate files. Use the index to select the material appropriate to a task rather than copying every template.

## Repository and adoption scope

The canonical package lives in `docs/code/` on `huawei_waterloo_main_branch` in `Stellven/jiuwenswarm`, alongside the application code. Start here after cloning that branch, or use the documentation-only ZIP linked in the kickoff guide. The five `huawei_waterloo_*` branches described in the SOP belong to this same application repository.

The package is a draft for team adoption. Complete marked owner, path, command, and acceptance fields using project evidence. Templates do not establish human approval, successful tests, or configured branch protection. Preserve and integrate existing instructions when adopting AGENTS files in the application repository.
