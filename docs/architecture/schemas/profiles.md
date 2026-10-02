---
type: schema
status: draft
tags: [schema, policy, profiles]
depends_on: [policy.md, binding.md, verification-record.md]
---

# Policy-selected profiles

Profiles select one uniform behavior without adding call-site exceptions. Every profile is immutable content addressed under the policy epoch; a Binding pins the exact reference. The pattern follows policy/data separation in [Open Policy Agent](https://www.openpolicyagent.org/docs).

## Profile reference

`ProfileRef` is `{kind, id, sha256}`. `kind` is `admission`, `gate`, `retry`, or `execution`; `id` is the stable policy-local name; `sha256` binds the complete profile. A reference resolves only inside the Binding's policy epoch.

## GateProfile

```text
GateProfile {
  profile_ref: ProfileRef(kind=gate)
  required_type_checks: list<check_id>
  required_capsule_checks: list<check_id>
  semantic_criteria: list<rubric_ref>
  evidence_rules: list<rule_id>
  blocking: map<result, action>
}
```

`semantic_criteria` may be empty when no semantic judgment applies. Every stage still uses the same Gate API and produces the same durable Verification. Delivery's profile therefore has deterministic manifest/publication checks and zero semantic criteria; it is not an exception.

## AdmissionProfile

```text
AdmissionProfile {
  profile_ref: ProfileRef(kind=admission)
  provider: tested_admission | puppet_admission
  allowed_levels: list<exempt | provisional | certified>
  suite_refs: list<Ref(test_suite)>
  allowlist_ref: EvidenceRef?
}
```

The provider cannot weaken mechanical declaration, hash, dependency, permission or interface validation performed before it is called.

## RetryProfile

Operation classes are `pure`, `read_only`, `idempotent_effect`, and `nonrepeatable_effect`. A RetryProfile supplies a finite attempt count and backoff only for allowed classes. `idempotent_effect` additionally requires request-result reuse. Model calls and `nonrepeatable_effect` have one attempt in M1; another try is an explicit new attempt.

## ExecutionProfile

An ExecutionProfile pins platform, process identity, readable and writable roots, network policy, credential exposure, IPC transport, resource limits, and doctor check ids. A missing or unvalidated requirement is `unsupported` and fails closed.

## Binding additions

Every work Binding pins `retry_profile_ref` and `execution_profile_ref`; every gate binding pins `gate_profile_ref`. Admission records pin `admission_profile_ref`. Freeze rejects missing, wrong-kind, hash-mismatched or policy-epoch-mismatched references with `POLICY_UNRESOLVED`.

