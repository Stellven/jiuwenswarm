---
type: schema
status: draft
tags: [schema, policy, profiles]
depends_on: [policy.md, binding.md, verification-record.md]
prd: [4.1.4, 4.2.8]
id: schemas.profiles
level: detail
---

# Policy-selected profiles

PRD: 4.1.4, 4.2.8

Profiles select one uniform behavior without adding call-site exceptions. Every profile is immutable content addressed under the [policy epoch](policy.md#term-epoch); a [Binding](binding.md#term-binding) pins the exact reference. The pattern follows policy/data separation in [Open Policy Agent](https://www.openpolicyagent.org/docs).

## Profile reference

`ProfileRef` is `{kind, id, sha256}`. `kind` is `admission`, `gate`, `retry`, or `execution`; `id` is the stable policy-local name; `sha256` binds the complete profile. A reference resolves only inside the Binding's policy epoch.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-profileref"></a>**ProfileRef** | A reference `{kind, id, sha256}` to one immutable policy profile of kind `admission`, `gate`, `retry` or `execution`. It resolves only inside the Binding's policy epoch. |
| <a id="term-gateprofile"></a>**GateProfile** (also: Gate profile) | The pinned set of deterministic, semantic and evidence rules, and the actions for each result, that a Gate applies at one call site. It supplies criteria as data to the shared verifier. |
| <a id="term-executionprofile"></a>**ExecutionProfile** (also: execution profile) | The pinned execution limits of a call: platform, process identity, readable and writable roots, network, credentials, IPC, resource limits and model-call limits. A missing or unvalidated requirement is `unsupported` and fails closed. |
| <a id="term-retryprofile"></a>**RetryProfile** (also: retry profile) | The pinned retry rule of a call. At M1 it allows zero autonomous execution retries; a new execution needs a new human-approved attempt. |

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

Every governed research stage has applicable independent semantic criteria, as [frozen](../system/lifecycle.md#term-freeze) PRD 4.1.4/4.2 requires. A reusable pure nested [operator](../capabilities/README.md#term-operator) receives immediate mechanical Gate [checks](../capsule/fields.md#term-check) and Tier2 status [NOT_RUN](../decisions.md#term-not-run) with an explanation that its mechanical profile contains no semantic criteria; its source evidence is independently judged by the enclosing stage before release. One [research.verifier](../capsule/gate-capsules.md#term-verifier) capability receives the immutable stage profile and evidence; stage-specific criteria remain independently authored and pinned. Mechanical helper modules use deterministic checks inside their enclosing stage and do not create additional [capsule](../capsule/capsule.md#term-capability-capsule) [Gates](../verification.md#term-gate). Publication follows the Report Gate and performs mechanical manifest/commit checks.

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

The sole wire-shape owner is services-v1 retry_profile: version, profile_id, max_execution_retries=0, duplicate_policy=reuse_reserved_result, recovery=explicit_review. ProfileRef.id equals profile_id; its hash pins the complete canonical object under the Binding policy epoch. M1 permits no autonomous execution retries for any [Declaration](../capsule/fields.md#term-declaration) [effect class](../capsule/fields.md#term-effect-class). Replay/status reuses reserved state rather than performing another operation. Explicit recovery follows [lifecycle](../system/lifecycle.md); a new execution receives a new human-approved attempt. Effect-class names remain the [Declaration vocabulary](policy.md), including [idempotent](../contracts/principles.md#term-idempotency) rather than idempotent_effect. A future retry policy needs a new profile revision and dependent rechecks.

## ExecutionProfile

An ExecutionProfile pins platform, process identity, readable and writable roots, network policy, credential exposure, IPC transport, resource limits, and doctor check ids. A missing or unvalidated requirement is `unsupported` and fails closed.

Schema: `tools-v1.schema.json#execution_profile`.

For brokered inference, the profile additionally pins model_call_limits, whose sole wire shape is services-v1 model_call_limits: a map from exact declaration hash to nonnegative integer maximum direct [model turns](../system/model-bridge.md#term-model-turn) per reserved call. Entries cover every reachable work, verifier and nested dependency; absence is POLICY_UNRESOLVED, never an unlimited default. Zero forbids model calls. Freeze verifies body/profile agreement, including the [POC two-call default](../capabilities/poc.md#bounded-generation-design) and [Report one-call default](../capabilities/write-report.md#bounded-synthesis-design). The broker counts direct turns by reserved [obs_id](../system/observability.md#term-obs-id)/decl_hash before forwarding and enforces the global durable run quota separately. A nested call has its own direct ceiling and also consumes the parent run's allowance; its Declaration/profile cannot reset the total. Standard skill max-turn and timeout caps additionally apply. This profile data is authored by developers, never by [RSI](../rsi.md#term-rsi) or model proposals. Changing a ceiling requires profile/body version pins and affected fixture rechecks.

## Binding additions

Every work Binding pins `retry_profile_ref` and `execution_profile_ref`; every gate binding pins `gate_profile_ref`. Admission records pin `admission_profile_ref`. Freeze rejects missing, wrong-kind, hash-mismatched or policy-epoch-mismatched references with `POLICY_UNRESOLVED`.
