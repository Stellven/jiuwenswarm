---
type: design
status: draft
version: 1
owner: muk
sources: [library.md, trust.md, ../schemas/verdict.md, ../schemas/profiles.md]
provides: [AdmissionProvider, tested_admission, puppet_admission]
consumes: [cc.candidate.v1, cc.policy.v1]
depends_on: [library.md, trust.md, ../schemas/verdict.md, ../schemas/profiles.md, toolchain.md]
tags: [capsule, admission, puppet-gate]
---

# Admission providers and the Puppet Gate

Admission is the only path into the capsule library. It first performs mandatory mechanical validation, then asks the policy-selected provider for the assurance decision. Availability, assurance and activation remain separate, following the immutable-version and movable-alias pattern of [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/).

## API

```python
async def assess(
    candidate_ref: Ref,
    policy_ref: Ref,
    admission_profile_ref: ProfileRef,
    request_id: str,
) -> Ref:  # AdmissionDecision
    ...
```

The stable request identity is `(candidate_ref.sha256, policy_ref.sha256, admission_profile_ref.sha256, request_id)`. Repeating it returns the original decision. A different request id creates a new assessment, never edits a Verdict.

## Mandatory pre-provider validation

Admission parses the Declaration; verifies Candidate and file hashes; compiles the interface; checks named-port types; verifies complete dependency/check/rubric/profile closure; rejects revoked or cyclic dependencies; validates permission/effect consistency; and records every check actually executed. A failure returns a rejected Verdict without calling the provider.

## Providers

| Provider | Policy input | May grant | Behavior |
|---|---|---|---|
| `tested_admission` | visible/sealed suites and required assurance level | `provisional`, `certified` | replays all external/model responses from fixtures, runs applicable suites, records actual results |
| `puppet_admission` | developer-owned allowlist of exact `decl_hash` values plus actor/reason | `exempt` | admits the selected hash after mandatory validation; runs no assurance suite and never represents one as passed |

The Puppet Gate is library admission only. It cannot write Verification, release a workflow node, grant `certified`, change permissions, activate an RSI child, or choose a different declaration version by capability name.

## Puppet decision record

The Verdict records `admission_basis: developer_decision`, allowlist hash, actor, reason, timestamp, exact candidate/declaration/interface/policy/profile hashes, mechanical `checks_run`, and an empty `test_suites` list unless a suite actually ran. The initial Standing is `admitted`, except an RSI child is always `admitted_inactive`.

Activation is a separate librarian action that writes a durable activation SystemRecord and moves the capability alias to an already admitted exact hash. It cannot increase assurance level.

## Failures

`SCHEMA_NONCONFORMANT`, `CARRIER_CHANGED`, `DEPENDENCY_UNAVAILABLE`, `POLICY_UNRESOLVED`, and `PERMISSION_UNENFORCEABLE` are mandatory-validation failures. `NOT_DEVELOPER_ALLOWED` and `SUITE_FAILED` are provider decisions. Store failure writes no Verdict or Standing. The same request may resume only by reusing its request id after storage recovery.

