# Incident and Post-Merge Failure Record: [INCIDENT-ID]

> Usage: copy to `docs/incidents/<INCIDENT-ID>.md`. Use for failed post-merge checks, release incidents, unreliable data/evaluation results, or other problems requiring coordinated recovery. Ordinary expected development failures may remain in task reports. Facts, impact, timeline, response authority, recovery evidence, and follow-up actions are required; explain N/A for irrelevant items. Emergency records may be shorter, but untested, assumed, or unapproved work must not be marked complete.

## 1. Current status and owners (required)

- Detection time / record update time / time zone: [Fill in].
- Status: [Investigating / Contained / Recovering / Recovered, under observation / Closed].
- Incident owner / technical responder / human decision-maker: [Fill in].
- Severity and basis: [Actual effects on users, data, research conclusions, and duration; do not invent a severity scale if the team has none].
- Related task / PR / release record: [Fill in].
- Most important current fact and next action: [Fill in].
- Affected people, module owners, and communication record: [Actual recipients, channel, and time; explicitly state if no communication occurred].

## 2. Versions, impact, and evidence (required)

| Item | Confirmed facts and evidence |
| --- | --- |
| Failing version | [Actual merge SHA and running artifact/configuration/model/data versions; a branch name alone is insufficient] |
| Last known good version | [SHA, versions, and last successful verification evidence; write Unknown if unknown] |
| Previous testing and approval | [Implementation C, baseline B, reports, human approval, and differences from the failing version] |
| Reproduction | [Working directory, environment, complete command/steps, input identifier, output, and exit code] |
| Impact | [Features, users/callers, data and research artifacts, onset, and duration] |
| Evidence for unaffected scope | [Scope actually checked; leave unchecked areas Unknown] |
| Evidence preservation | [Redacted logs, run IDs, artifact locations, access permissions, and time range] |

Assumptions and unresolved questions: [Separate hypotheses from the facts above; list verification actions and owners]. If research metrics or results may be contaminated, identify artifacts and versions that must stop being cited or require recomputation. Do not silently overwrite original results.

## 3. Timeline (required)

| Time and time zone | Observation / action / decision | Executor or decision-maker | Related version, result, and evidence |
| --- | --- | --- | --- |
| [Fill in] | [First detection] | [Fill in] | [Fill in] |
| [Fill in] | [Scope confirmation or containment] | [Fill in] | [Fill in] |
| [Fill in] | [Recovery and observation] | [Fill in] | [Fill in] |

## 4. Containment, fix, and rollback decisions (required)

- Containment goal and measures: [For example, pause the affected release or disable the failing path; identify exact objects and scope].
- Existing operational authority or human decision: [Who, when, permitted actions, and evidence; this template does not grant execution authority].
- Selected action: [Fix / Restore previous artifact / Revert commit / Recover data / Other specific action].
- Reasoning and alternatives: [Expected effect, risks, recovery time, and irreversible boundaries].
- Rollback target and prerequisites: [Actual code, configuration, data, model, and service versions and recovery conditions].
- Fix design and implementation boundaries: [Brief approved design, `write_code.md`, or explicit authorization record].

| Order | Working directory / environment | Actual command or action | Expected effect | Actual result / exit code | Executor and evidence |
| --- | --- | --- | --- | --- | --- |
| [Fill in] | [Fill in] | [Mark Planned if not executed] | [Fill in] | [Not executed] | [Fill in] |

Preserve logs and necessary incident evidence. Reverting code does not automatically restore data or undo external side effects; specify each recovery method. Use ordinary commits and merges to preserve persistent branch history, without force push. Emergency fixes still require necessary verification and a human decision. For deferred checks, record risks, follow-up owner, deadline, and rollback triggers.

## 5. Recovery verification and closure criteria (required)

| Verification target | Recovery criterion agreed in advance | Actual version and command / working directory | Actual result and evidence | Owner |
| --- | --- | --- | --- | --- |
| [Original failure, key call chain, data, or metric] | [Behavior / numerical threshold / observation window] | [Fill in] | [Not run / Passed / Failed / Blocked] | [Fill in] |

- Observation window / recurrence monitoring / owner: [Fill in].
- Missing evidence and residual risks: [Fill in].
- Post-fix tests, AI review, and human review: [Specific versions and records; preserve incomplete status where applicable].
- Human recovery confirmation: [Name, time, scope, and evidence; initially Pending confirmation].
- Closure criteria and completion: [Facts for each criterion; restored service does not automatically mean all follow-up actions are complete].

## 6. Causes and follow-up actions (required)

- Direct cause / contributing factors: [Evidence-supported conclusions; remain Investigating if unknown].
- Why existing design, tests, review, or monitoring missed it: [Factual analysis without attributing blame to an individual or AI].
- Contracts, tests, environment, or SOP requiring updates: [Paths and reasons].

| Action | Owner | Deadline and time zone | Verifiable completion criterion | Related task / evidence / status |
| --- | --- | --- | --- | --- |
| [Fix, regression test, recomputation, detection improvement, or other action] | [Fill in] | [Fill in] | [Fill in] | [To do] |

Related templates: [RELEASE_ROLLBACK](RELEASE_ROLLBACK_TEMPLATE.md), [TEST_REPORT](TEST_REPORT_TEMPLATE.md), [HANDOFF](HANDOFF_TEMPLATE.md).
