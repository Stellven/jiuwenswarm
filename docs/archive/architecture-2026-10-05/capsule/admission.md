---
id: capsule.admission
type: module-spec
status: draft
version: 1
sources: [library.md, trust.md, ../schemas/verdict.md, ../schemas/profiles.md]
provides: [AdmissionProvider, tested_admission, puppet_admission]
consumes: [cc.candidate.v1, cc.policy.v1]
depends_on: [library.md, trust.md, ../schemas/verdict.md, ../schemas/profiles.md, toolchain.md]
tags: [capsule, admission, puppet-gate]
level: detail
prd: [4.1.2, 4.2.1]
---

# Admission providers and the Puppet Gate

PRD: 4.1.2, 4.2.1

> Answers: How does a candidate capsule get into the library, and what does the Puppet Gate decide?

## Purpose

Admission is the only path into the [capsule](capsule.md#term-capability-capsule) library. It first performs mandatory mechanical validation, then asks the policy-selected provider for the assurance decision. Availability, assurance and activation remain separate, following the immutable-version and movable-alias pattern of [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-admission"></a>**admission** | The only path into the capsule library: mandatory mechanical validation of a Candidate, then an assurance decision by the policy-selected provider, recorded as a Verdict. Admission never grants a runtime Gate PASS. |
| <a id="term-tested-admission"></a>**tested_admission** | The default admission provider: it runs the visible test suites against fixtures and may grant `provisional`. `certified` is post-M1. |
| <a id="term-puppet-admission"></a>**Puppet admission** (also: puppet_admission, Puppet Gate) | A developer-decision admission provider for exact allowlisted `decl_hash` values: it runs mandatory validation but no assurance suite, and may grant `exempt`. It is library admission only and cannot release a workflow node. |
| <a id="term-provisional"></a>**provisional** | The assurance level `tested_admission` grants after the visible suites actually ran and passed. It is below `certified`, which M1 never grants. |
| <a id="term-exempt"></a>**exempt** | The assurance level Puppet admission grants to an allowlisted hash after mandatory validation. It means a developer decided, not that any suite passed. |
| <a id="term-admitted-inactive"></a>**admitted_inactive** | The Standing state of an admitted RSI child: it is in the library but not current, until a person activates it with a separate request. |

## Interface: API

```python
async def assess(
    candidate_ref: Ref,
    policy_ref: Ref,
    admission_profile_ref: ProfileRef,
    request_id: str,
) -> Ref:  # AdmissionDecision
    ...
```

Schema: `library-rsi-v1.schema.json#admission_request`. `assess` returns the Ref of the committed Verdict; the provider's output (AdmissionDecision) is the body of that Verdict and has the shape `library-rsi-v1.schema.json#admission_decision`. A mandatory-validation failure is recorded as a rejected decision under the policy-selected provider's basis; no provider is called.

The stable request identity is `(candidate_ref.sha256, policy_ref.sha256, admission_profile_ref.sha256, request_id)`. Repeating it returns the original decision. A different request id creates a new assessment, never edits a Verdict.

## Behavior: mandatory pre-provider validation

Admission parses the [Declaration](fields.md#term-declaration); verifies Candidate and file hashes; compiles the interface; [checks](fields.md#term-check) named-port types; verifies complete dependency/check/rubric/profile closure; rejects revoked or cyclic dependencies; validates permission/effect consistency; and records every check actually executed. A failure returns a rejected Verdict without calling the provider.

## Providers

| Provider | Policy input | May grant | Behavior |
|---|---|---|---|
| `tested_admission` | visible suites and required M1 assurance level | `provisional` | replays external/model responses from [fixtures](../system/test-surfaces.md#term-fixture), [runs](../system/lifecycle.md#term-run) applicable suites, records actual results; `certified` is post-M1 |
| `puppet_admission` | developer allowlist of exact `decl_hash` values plus actor/reason | `exempt` | admits the selected hash after mandatory validation; runs no assurance suite and never represents one as passed |

The provider is chosen by policy. `tested_admission` is the default; Puppet is available only for hashes on the developer allowlist. Either way an [RSI child](rsi.md#term-parent-and-child) is admitted as `admitted_inactive`, and only a separate activation request makes it current. The Puppet [Gate](../verification.md#term-gate) is library admission only. It cannot write [Verification](../schemas/verification-record.md#term-verification), release a workflow node, grant `certified`, change permissions, activate an [RSI](../rsi.md#term-rsi) child, or choose a different declaration version by capability name.

## Puppet decision record

The Verdict records `admission_basis: developer_decision`, allowlist hash, actor, reason, timestamp, exact candidate/declaration/interface/policy/profile hashes, mechanical `checks_run`, and an empty `test_suites` list unless a suite actually ran. The initial Standing is `admitted`, except an RSI child is always `admitted_inactive`.

Schema: `library-rsi-v1.schema.json#admission_decision`: `provider` selects `tested_admission` (`admission_basis: test_evidence`, level `provisional`, no `developer_decision`) or `puppet_admission` (`admission_basis: developer_decision`, level `exempt`, required `developer_decision` with allowlist hash, actor, reason and time, empty `test_suites`). A decision with a `parent_decl_hash` (an RSI child) that is admitted must carry standing `admitted_inactive`.

Activation is a separate librarian action that writes a durable activation [SystemRecord](../system/records.md#term-systemrecord) and moves the capability alias to an already admitted exact hash. Rollback is the same action pointing at a historical admitted hash. The first activation of the seed capsules is `cc bootstrap` (actor `installer`, `expected_current_hash` null). A running run keeps its pinned [library snapshot](library.md#term-library-snapshot). It cannot increase assurance level. Its messages are in [library](library.md#frozen-library-snapshot-and-activation).

## Failure: failures

| Situation | Outcome | Recovery |
|---|---|---|
| Mandatory validation fails (`SCHEMA_NONCONFORMANT`, `CARRIER_CHANGED`, `DEPENDENCY_UNAVAILABLE`, `POLICY_UNRESOLVED`, `PERMISSION_UNENFORCEABLE`) | no Verdict is granted | fix the Candidate and submit under a new request id |
| Provider decision `NOT_DEVELOPER_ALLOWED` or `SUITE_FAILED` | Verdict records the refusal | change the allowlist or the suites, then a new request id |
| Store failure | no Verdict and no Standing is written | repeat the same request identity |


`SCHEMA_NONCONFORMANT`, `CARRIER_CHANGED`, `DEPENDENCY_UNAVAILABLE`, `POLICY_UNRESOLVED`, and `PERMISSION_UNENFORCEABLE` are mandatory-validation failures. `NOT_DEVELOPER_ALLOWED` and `SUITE_FAILED` are provider decisions. Store failure writes no Verdict or Standing. The same request may resume only by reusing its request id after storage recovery.

## Tests

Fixtures and fakes: toy tool and skill capsule folders and changed-byte copies; the Puppet exemption. Rows in [test surfaces](../system/test-surfaces.md#verification-table): [V04](../system/test-surfaces.md#verification-table), [V28](../system/test-surfaces.md#verification-table).
