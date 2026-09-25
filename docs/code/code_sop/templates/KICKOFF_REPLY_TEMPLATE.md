# Weekend kickoff reply — [Your name]

> Save as `<your-name>_kickoff_reply.md` and send it in the kickoff thread, or paste the completed fields there. This is the only new form required from everyone for kickoff. Keep answers short and factual. Use Not attempted, Blocked, or Unconfirmed where appropriate. Do not include credentials. A reply is not approval to implement or merge.

## 1. Access and branch

- Name: [Fill in].
- Application repository access: [Confirmed / Blocked with error].
- Documentation repository access: [Confirmed / Blocked with error].
- Application origin: [Actual remote URL].
- Local application working directory: [Your path].
- Personal branch: [Actual `huawei_waterloo_xiaoyang`, `huawei_waterloo_saurav`, `huawei_waterloo_ramika`, or `huawei_waterloo_muk`].
- Current HEAD: [Full SHA, or Not cloned].
- Latest fetched `origin/huawei_waterloo_main_branch`: [Full SHA and fetch time, or Not fetched].
- Baseline merged into the personal branch: [Same as latest fetched / Older baseline with reason / Not yet synchronized].
- Existing uncommitted work: [None / Files and ownership; do not overwrite it].

## 2. Environment and attempted checks

- Operating system / shell: [Fill in].
- Git / Git LFS / Python versions: [Actual command output, or Not installed/checked].
- Environment route: [pip virtual environment / uv / Other explained / Not selected].
- Dependency setup: [Completed with evidence / Attempted but blocked / Not attempted].
- LFS/resource state: [Objects available / Pointers retained / Checkout failed / Not checked; identify missing resources].

| Working directory | Command actually attempted | Result / relevant output | Blocker or next step |
| --- | --- | --- | --- |
| [Path] | [Command, or Not attempted] | [Actual exit code/result; do not guess] | [Action or none] |

Include setup and any task-relevant baseline checks you actually attempted. If the applicable test command or prerequisites are unknown, state that instead of guessing. Do not label the environment ready based only on successful cloning.

## 3. Proposed responsibility

- Current or preferred module/area: [RSI / Router / Capsule / Verifier / Shared area / Undecided].
- Relevant experience or contribution: [One or two sentences].
- Code paths and AGENTS files inspected: [Actual paths, or Not yet inspected].
- Initial understanding of the area's responsibility: [Short summary with evidence, or Unconfirmed].
- Ownership/interface questions: [What needs Lead or another owner's confirmation].

The personal branch assignment does not determine module ownership. The Lead will confirm responsibilities and code boundaries after the replies.

## 4. One proposed first task

- Problem and evidence: [What should change and why].
- Intended observable behavior: [Who would observe what result].
- In scope / out of scope: [Brief boundaries].
- Likely files, functions, or interface: [Evidence-based candidates; mark uncertain paths].
- Suggested acceptance check: [A concrete test, inspection, or measurement].
- Dependencies, services, data, or other owners needed: [Known requirements or Unconfirmed].
- Main risk / question before implementation: [Fill in or none known].

Task status: **Proposed; design and implementation authority pending.** Existing explicit authorization may be referenced with its scope and evidence; do not invent an approval.

## 5. Availability and help needed

- Available time this weekend: [Your estimate, not a promised team deadline].
- Next setup or design step: [Concrete action].
- Help needed and from whom: [Access, environment, design, or owner decision].
- Minimum reading completed: [SOP / index / Git workflow / applicable AGENTS; identify remaining reading].

After the Lead confirms scope, use [TASK](TASK_TEMPLATE.md) and [WRITE_CODE](WRITE_CODE_TEMPLATE.md) for the first approved task, with the simplified workflow where appropriate.
