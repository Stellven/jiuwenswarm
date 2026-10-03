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

Every governed research stage has applicable independent semantic criteria, as frozen PRD 4.1.4/4.2 requires. A reusable pure nested operator receives immediate mechanical Gate checks and Tier2 status NOT_RUN with an explanation that its mechanical profile contains no semantic criteria; its source evidence is independently judged by the enclosing stage before release. One research.verifier capability receives the immutable stage profile and evidence; stage-specific criteria remain independently authored and pinned. Mechanical helper modules use deterministic checks inside their enclosing stage and do not create additional capsule Gates. Publication follows the Report Gate and performs mechanical manifest/commit checks.

## AdmissionProfile

```text
AdmissionProfile {
  profile_ref: ProfileRef(kind=admission)
  provider: tested_admission | puppet_admission
  allowed_levels: list<exempt | provisional>
  suite_refs: list<Ref(test_suite)>
  allowlist_ref: EvidenceRef?
}
```

The provider cannot weaken mechanical declaration, hash, dependency, permission or interface validation performed before it is called.

## RetryProfile

The sole wire-shape owner is services-v1 retry_profile: version, profile_id, max_execution_retries=0, duplicate_policy=reuse_reserved_result, recovery=explicit_review. ProfileRef.id equals profile_id; its hash pins the complete canonical object under the Binding policy epoch. M1 permits no autonomous execution retries for any Declaration effect class. Replay/status reuses reserved state rather than performing another operation. Explicit recovery follows [lifecycle](../system/lifecycle.md); a new execution receives a new human-approved attempt. Effect-class names remain the [Declaration vocabulary](policy.md), including idempotent rather than idempotent_effect. A future retry policy needs a new profile revision and dependent rechecks.

## ExecutionProfile

An ExecutionProfile pins platform, process identity, readable and writable roots, network policy, credential exposure, IPC transport, resource limits, and doctor check ids. A missing or unvalidated requirement is `unsupported` and fails closed.

## Binding additions

Every work Binding pins `retry_profile_ref` and `execution_profile_ref`; every gate binding pins `gate_profile_ref`. Admission records pin `admission_profile_ref`. Freeze rejects missing, wrong-kind, hash-mismatched or policy-epoch-mismatched references with `POLICY_UNRESOLVED`.
