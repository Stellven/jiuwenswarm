---
type: schema
id: cc.verdict.v1
status: proposed
tags: [schema]
---

# Verdict · `cc.verdict.v1`

Admission's decision on one Declaration under one policy epoch and one port type vocabulary, with its reasons and evidence. Admission is its only writer. It is written once. Re-admission under a new epoch writes a new Verdict; a Verdict that stops holding is marked by a Finding of kind `invalidation`, never by editing it (INV-2).

**Rules:** INV-2, INV-8, INV-10.

## Fields

Extends [common](common.md), with `scope.candidate_id`, which names the Candidate that submitted the Declaration. Its `id` is the `verdict_id`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `decl_hash` | `sha256` | req | checked |  | The Declaration judged |
| `interface_hash` | `sha256` | req | checked |  | Its interface hash, computed at admission. Test cases bind to it |
| `policy_ref` | `object` | req | checked |  | The rules it was judged under |
| `policy_ref.epoch` | `string` | req | checked |  | The policy epoch name. Example: `e1` |
| `policy_ref.sha256` | `sha256` | req | checked |  | The policy document's hash |
| `vocabulary_ref` | `object` | req | checked |  | The [port type vocabulary](port-types.md) its ports and checks were judged under. A Binding must use the same version of each of its port types |
| `vocabulary_ref.version` | `integer` | req | checked |  | The vocabulary's `vocabulary_version`. Example: `1` |
| `vocabulary_ref.sha256` | `sha256` | req | checked |  | The vocabulary document's hash |
| `outcome` | `enum(admit, reject, defer)` | req | checked |  | The decision. `defer` waits for evidence |
| `reasons` | `list<Reason>` | req | checked |  | Why, as typed codes. Empty only when admitted with nothing to note. Example: `[{"code": "CHECK_FAILED", "message": "text_not_empty failed on case 3"}]` |
| `checks_run` | `list<object>` | req | checked |  | Every check admission ran |
| `checks_run[].check_id` | `id` | req | checked |  | Which check. Example: `text_not_empty` |
| `checks_run[].runner_sha256` | `sha256` | req | checked |  | Which runner code ran it |
| `checks_run[].result` | `enum(pass, fail, unknown)` | req | checked |  | `unknown` when it could not be evaluated; never counted as a pass (INV-8) |
| `checks_run[].evidence` | `list<EvidenceRef>` | opt | checked |  | The test calls behind the result |
| `level` | `enum(provisional, certified, exempt)?` | req | checked |  | Where it may run; null unless `outcome` is `admit`. `certified` (Unlocks: certification) and `exempt` (Unlocks: exempt agents) are unchecked in M1, so every capsule admitted in M1 is `provisional` |
| `test_suites` | `list<Ref(test_suite)>` | req | checked |  | The suites it was checked with: the visible suite admission built from the Candidate's tests, and any sealed suites. This is how a capsule's latest tests are found |
| `environment` | `object` | opt | unchecked | isolated verification | Where admission ran the tests, so a result can be reproduced |
| `environment.runtime` | `string` | req | unchecked | isolated verification | The runtime used. Example: `python 3.11.9` |
| `environment.image_sha256` | `sha256` | opt | unchecked | isolated verification | The sandbox image's hash, when tests ran in one |
| `evidence_requests` | `list<text>` | opt | unchecked | certification | What a `defer` is waiting for. Example: `["a sealed suite"]` |

Reserved names, not specified: `observed`, `remote_fingerprint`, `precondition_parity`, `models_used`, `contribution`, `nearest`, `screening`.

## Elsewhere

Only a failed check or a broken rule rejects; `unknown` defers, with reason `CHECK_UNKNOWN`: policy `rules`. What each level requires: policy `levels`. Reason codes: policy `registries`.

## Reuse

- `FailureReason` (agent-core `symphony/models/evaluation.py:70`): as `Reason`, without `severity`.
- `MetricResult`, `MetricStatus` (`evaluation.py:223`, `:22`): for `checks_run`; `pass` and `fail` map directly, `unknown` from `error`, `not_applicable` or `observed`.
- v2.10b §3.2: the source. Moved to the envelope: `issuer`, `issued_at`, `policy_epoch`. Moved to the Candidate: `builder_gate`. Not kept: `ESCALATE`, `unknown_cause`, `verifiers[]`, `baseline_snapshot`.
- skillhub pins a review's `policy_version` (`market_assets.py:163`): the same pattern.
