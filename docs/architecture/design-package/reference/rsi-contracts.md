# RSI contracts

`Tier 3 · Part of: [Reference](README.md)`

These are the records of the offline [RSI workbench](../side-systems/rsi-workbench.md). A human selects a target, and the workbench records an opportunity decision. A human then starts a session on one admitted parent CC version. The workbench writes attempts, feedback and referee evidence, closes the session with one result, and writes a candidate package to the admission inbox. The admission command checks the package and writes a [library admission](field-catalog.md#library-admission) record. A human then activates the child with an [activation record](field-catalog.md#activation-record), or rolls it back.

The record names follow the RSI v0.2 rulings ([owner rulings](../side-systems/owner-rulings.md#rsi-v02), row 8): the opportunity decision is `rsi-opportunity`, the frozen session is `rsi-session`, the session result is `rsi-session-result`, the review package is `candidate-package` and the completion report is `rsi-completion-report`. Shared types (`Ref`, `CcPin`, `Limits`, `RSIPair`, `RSIScore`, `SplitIdentities`) are in the [field catalog](field-catalog.md#shared-field-types). The declaration rules a child must keep, including lineage and `evolution.may_change`, are in the [declaration reference](declaration.md#evolution-what-rsi-may-change). Rollback is a standing move: a human reactivates an earlier admitted version with an [activation record](field-catalog.md#activation-record), and no new version is built ([D41](../method/decisions.md#d41)).

## Record map

| Contract | Version | Producer → consumers | Examples |
|---|---|---|---|
| [rsi-opportunity](#rsi-opportunity) | 1.0.0 | RSI workbench controller, after a human selects the target → human reviewer, RSI controller, evidence export |
| [rsi-target-profile](#rsi-target-profile) | 1.0.0 | protected target owner → controller, mutation check, referee | [rsi_target_profile.json](examples/rsi_target_profile.json) · invalid: [rsi_target_profile_invalid_wider_than_may_change.json](examples/rsi_target_profile_invalid_wider_than_may_change.json) |
| [rsi-session](#rsi-session) | 1.0.0 | RSI controller, started by a human → proposer, mutation check, referee, evidence builder | [rsi_session.json](examples/rsi_session.json) |
| [rsi-attempt](#rsi-attempt) | 1.0.0 | protected RSI controller → mutation check, referee, evidence | [rsi_attempt_01.json](examples/rsi_attempt_01.json) |
| [rsi-loop-feedback](#rsi-loop-feedback) | 1.0.0 | custodian → proposer |
| [rsi-referee-evidence](#rsi-referee-evidence) | 1.0.0 | protected independent referee → restricted admission, evidence builder | [rsi_referee_evidence.json](examples/rsi_referee_evidence.json) |
| [rsi-evidence-export](#rsi-evidence-export) | 1.0.0 | trusted audience-filtered builder → authorized human, library | [rsi_evidence_export.json](examples/rsi_evidence_export.json) |
| [rsi-session-result](#rsi-session-result) | 1.0.0 | RSI controller → candidate packager, human, evidence export | [rsi_session_result.json](examples/rsi_session_result.json) |
| [candidate-package](#candidate-package) | 1.0.0 | RSI workbench packager → admission inbox, admission command, human | [candidate_package.json](examples/candidate_package.json) |
| [candidate-provenance](#candidate-provenance) | 1.0.0 | candidate builder with protected capture → library admission, human, RSI | [rsi_child_candidate.json](examples/rsi_child_candidate.json) |
| [security-clearance](#security-clearance) | 1.0.0 | authorized security human through protected RSI controller → new-session eligibility, audit |
| [rsi-completion-report](#rsi-completion-report) | 1.0.0 | RSI workbench report builder → human reviewer, product acceptance |

## Opportunity and profile records

### rsi-opportunity

Purpose: the decision to start, or not to start, an RSI attempt on one target. It records the evidence, the attributed cause, the headroom and the reason. This is the RSI v0.2 "opportunity decision" ([owner rulings](../side-systems/owner-rulings.md#rsi-v02), row 8).

`rsi-opportunity:field-contract:1` (version 1.0.0) · Producer: RSI workbench controller (opportunity qualifier), after a human selects the target. Consumers: human reviewer, RSI controller, evidence export.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this opportunity decision. |
| `target_profile_ref` | `Ref` | yes | an `rsi-target-profile` record | Target the opportunity concerns. |
| `parent` | `CcPin` | yes | an admitted library version. `declaration_sha256` equals the target profile `parent_declaration_ref` digest | Exact parent version the evidence was gathered on. |
| `trigger` | `string` | yes | enum `operator_selected`, `authorized_batch` | How the target was chosen. The controller records the human's choice. M1 has no always-on scheduler, so no other value exists. |
| `selected_by` | `string` | yes | 1 to 120 characters, an authenticated human actor | The authenticated human who selected the target or approved the batch. Never a CC or the proposer. |
| `evidence_refs` | `Ref[]` | yes | 1 to 32 items | Observations and benchmark evidence the controller examined, each kept as the original reference with its digest so a reviewer can open it. |
| `attribution` | `string` | yes | enum `implementation`, `upstream_input`, `binding_composition`, `harness`, `verifier`, `environment`, `uncertain` | Demonstrated cause class, set by the controller after visible reproduction. A heuristic label or a CC self-report is never enough. Only `implementation` can lead to `START`. |
| `symptom_reproduced` | `boolean` | yes | none | Whether the symptom reproduced on approved visible inputs, with the exact parent and the frozen environment. |
| `parent_mandatory_passed` | `boolean` | yes | none | Whether the parent passed its mandatory behavior on the development inputs. Development failures add headroom and never waive an obligation. |
| `headroom` | `nullable-number` | yes | 0 to 1. Null when the symptom did not reproduce | Development failure rate of the parent on approved visible inputs, as a fraction (0.25 means one failure in four). The controller measures it. Null means the symptom did not reproduce, and null is not 0. |
| `headroom_minimum` | `number` | yes | 0 to 1, equals the minimum the target profile declares | Smallest headroom that makes an attempt worth starting, as a fraction like `headroom`. Copied from the target profile. The controller does not choose it. |
| `diagnosis_ref` | `nullable-Ref` | yes | non-null when `decision` is `START` | Retained structured diagnosis of the symptom: observed symptom, mechanism, alternative causes, authorized component, proposed direction and falsification checks. Required for `START`. For any other decision it may hold the partial diagnosis or be null. Only `START` reads it. |
| `decision` | `string` | yes | enum `START`, `NO_ATTEMPT`, `NEEDS_REVIEW` | What happens next. `START` freezes a session. `NO_ATTEMPT` records why no attempt runs. `NEEDS_REVIEW` waits for a human. |
| `reason` | `string` | yes | 1 to 300 characters | Why this decision, in plain words, for the human reviewer. The next step follows from `decision` and the invariants, never from this text. |
| `decided_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the controller wrote the decision. UTC, whole seconds. |

**Invariants**

- `START` needs `attribution` `implementation`, `symptom_reproduced` true, `parent_mandatory_passed` true, `headroom` at least `headroom_minimum`, and a non-null `diagnosis_ref`.
- `attribution` `uncertain` gives `NEEDS_REVIEW`, and only an uncertain attribution does. No autonomous search starts from it.
- A cause other than `implementation` gives `NO_ATTEMPT`: an upstream input, a binding, the harness, the verifier or the environment is not a defect of this CC.
- A single reproducible development gap is enough to start. Recurrence is supporting evidence, not a threshold. Expected gain is a hypothesis, not a score.
- The record changes nothing in the target profile or the library.

**Producer obligations (RSI controller)**

- Validate the export identity, audience and exact target version before reading any observation.
- Group observations by CC hash, obligation and normalized failure category. Keep the original references and sample counts.
- Exclude observations whose demonstrated cause is not the implementation. Keep uncertain or multiple causes as `uncertain`. Never force an attribution.
- Reproduce the symptom on approved visible inputs with the exact parent and the frozen environment before choosing `implementation`.
- Record the headroom as measured. A target below the profile minimum gets `NO_ATTEMPT`.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `opportunity_structure` | The record matches `rsi-opportunity:field-contract:1` | no decision is stored |
| `opportunity_pins_consistent` | The parent digest equals the target profile `parent_declaration_ref` digest | no decision is stored |
| `opportunity_start_conditions` | The `START`, `NEEDS_REVIEW` and `NO_ATTEMPT` rules above hold | no decision is stored |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No decision is stored. No session starts | The rejected record and the reason |
| `decision` is `NO_ATTEMPT` or `NEEDS_REVIEW` | No session starts. A human may select the target again | The record and its evidence |



**Minimum quality bar.** A reviewer can tell from this record alone why an attempt started or did not, and which evidence supports it.

### rsi-target-profile

Purpose: the frozen description of one improvement target: the parent, the paths the proposer may change, the tests the child must keep passing, the data splits and the scoring. The target owner writes it. Nothing a candidate does may change it.

`rsi-target-profile:field-contract:1` (version 1.0.0) · Producer: protected target owner. Consumers: controller, mutation check, referee.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this target profile. |
| `parent_ref` | `Ref` | yes | one body file of the parent declaration. Its digest is in `identity.body` | The one body file of the parent declaration that RSI may improve. Its digest is in `identity.body`. |
| `parent_declaration_ref` | `Ref` | yes | the parent declaration bytes. Its `evolution.rsi` is `propose` | Declaration whose `evolution.may_change` bounds `mutable_paths`. |
| `frozen_contract_ref` | `Ref` | yes | the interface contract bytes the child keeps | Interface contract the child must keep unchanged. No candidate result may change it. |
| `required_test_refs` | `Ref[]` | yes | 1 to 16 items | Mandatory parent tests. The child must pass all of them. |
| `mutable_paths` | `string[]` | yes | 1 to 16 unique paths. Each is covered by a `files:` glob in the parent `evolution.may_change` (check `profile_within_may_change`) | The only body paths the proposer may change. The target owner sets them inside what the CC author allowed in `may_change`, never the RSI operator or the proposer. A touched path outside this list is a security violation. |
| `protected_refs` | `Ref[]` | yes | 1 to 32 items. None is a mutable path | Files the proposer must not change and that the referee depends on. Never overlaps `mutable_paths`. |
| `splits` | `SplitIdentities` | yes | four distinct identities | Four distinct partition identities. The hidden ones are known only to the custodian and are never shown to the proposer. |
| `scoring` | `RSIScore` | yes | `primary` is `passed_test_count`, `secondary` is `paired_time_at_equal_counts`, `warmup_batches` is 5, `paired_rounds` is 7 | Passed-tests-first scoring with a timing tie rule. |
| `calibration_ref` | `Ref` | yes | a calibration record with planted good and bad children | Measured headroom and timing noise. |
| `session_query_limit` | `integer` | yes | exactly 30 | Hidden-loop queries one session may spend, as a count. The baseline evaluation counts as one. |
| `lifetime_query_limit` | `integer` | yes | exactly 90 | Hidden-loop queries over the lifetime of the registered loop set. |
| `limits` | `Limits` | yes | positive values | Frozen bounds for every child run: `time_s` in seconds, `model_calls` as a count, `memory_mb` in MiB. Every value must be above zero here, stricter than the shared `Limits` type, because a child run with a zero bound cannot run. The target owner sets them. A candidate cannot change them. |
| `scoring_adapter_ref` | `Ref` | yes | the frozen scoring adapter bytes | Frozen independent scoring adapter. |
| `improver_ref` | `Ref` | yes | the fixed proposer policy and implementation bytes | Fixed proposer policy and implementation. |
| `configuration_ref` | `Ref` | yes | the frozen configuration bytes | Frozen model, host and runtime settings, the same for parent and child. |

**Invariants**

- `mutable_paths` is a subset of the parent declaration `evolution.may_change`: each path is covered by a `files:` glob there. The author of the CC sets what may change, not the RSI operator ([D34](../method/decisions.md#d34)).
- The four split identities differ. The hidden splits are known only to the custodian.
- No protected reference is a mutable path.
- The profile is never edited in response to candidate results.

**Producer obligations (protected target owner)**

- Write `parent_declaration_ref` from the admitted parent declaration, and list only paths its `may_change` allows.
- Pin the scoring adapter, improver and configuration before the first session.
- Block the profile when calibration shows no headroom.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `profile_structure` | The record matches `rsi-target-profile:field-contract:1` | the profile is not used |
| `profile_parent_matches_declaration` | `parent_ref` is one body file of the parent declaration | the profile is not used |
| `profile_within_may_change` | The parent declaration has `evolution.rsi` `propose`. Every mutable path is covered by a `files:` glob of its `may_change`. No path repeats. No protected reference is a mutable path | the profile is not used |
| `profile_scoring_fixed` | The four splits differ. Scoring is passed tests first, then paired time. Warm-up is 5 batches and paired rounds are 7. Query limits are 30 and 90 | the profile is not used |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No session starts from the profile | The rejected profile and the reason |
| Calibration shows no headroom | The profile is blocked. A session would end `BLOCKED` | The profile and the calibration record |

**Examples:** [valid](examples/rsi_target_profile.json) · rejected by `profile_within_may_change`: [rsi_target_profile_invalid_wider_than_may_change](examples/rsi_target_profile_invalid_wider_than_may_change.json) (a mutable path outside `may_change`)

**Minimum quality bar.** A reviewer can tell from the profile and the parent declaration which files RSI may change, and who allowed it.

## Session records

### rsi-session

Purpose: the frozen binding of one RSI session. It fixes the parent, the target, the improver, the referee settings, the limits and the qualification values before attempt 1. Nothing in it changes during the session.

`rsi-session:field-contract:1` (version 1.0.0) · Producer: RSI controller, after a human starts the session. Consumers: proposer (limits only), mutation check, referee, evidence builder, candidate packager.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this frozen session record. |
| `session_id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Session ID that every attempt, query and result names. The controller sets it once when the human starts the session. A changed session needs a new `session_id`. |
| `target_profile_ref` | `Ref` | yes | an `rsi-target-profile` record | Frozen target: parent, mutable paths, tests, splits and scoring. |
| `parent` | `CcPin` | yes | an admitted library version. `declaration_sha256` equals `parent_declaration_ref.sha256` | Exact parent version. The final comparison always runs against it. |
| `parent_declaration_ref` | `Ref` | yes | the parent declaration bytes | Declaration the child must keep, outside the pointers RSI may write. |
| `improver_ref` | `Ref` | yes | equals the target profile `improver_ref` | Fixed proposer policy and implementation. |
| `scoring_adapter_ref` | `Ref` | yes | equals the target profile `scoring_adapter_ref` | Frozen scoring adapter the referee runs. |
| `configuration_ref` | `Ref` | yes | equals the target profile `configuration_ref` | Frozen model, host and runtime settings, the same for parent and child. |
| `hash_profile_ref` | `Ref` | yes | the pinned serialization and hash profile | How attempt records are serialized, hashed and chained. |
| `chain_root_ref` | `Ref` | yes | the protected genesis record. It pins this `session_id`, the target and the hash profile | Root of the attempt hash chain, fixed before attempt 1. |
| `limits` | `RsiSessionLimits` | yes | each value at most its default | Search budget of the session. The proposer sees these limits and nothing else of this record. |
| `pass_count_repeats` | `integer` | yes | enum `1`, `3` | Repeats per fixture for pass counts: 1 for a deterministic target, 3 for a model-backed target. |
| `qualification` | `RsiQualificationPolicy` | yes | no value weaker than the [qualification rule](../side-systems/rsi-workbench.md#qualification-rule) | Qualification values, pinned before any code is proposed. |
| `started_by` | `string` | yes | 1 to 120 characters, an authenticated human actor | The authenticated human who started the session. A session never starts itself, so this is never a CC or the proposer. |
| `frozen_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the controller froze the record, before attempt 1. UTC, whole seconds. |

**RsiSessionLimits**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `max_attempts` | `integer` | yes | 1 to 20. Default 20 | Proposal attempts in the session, including malformed proposals and visible-test rejects. |
| `max_no_progress` | `integer` | yes | 1 to 5. Default 5 | Consecutive attempts without a stronger selection tuple. Search stops when this many pass. |
| `wall_s` | `integer` | yes | 1 to 3600. Default 3600 (60 minutes) | Wall time for the whole search, in seconds. |
| `per_call_s` | `integer` | yes | 1 to 300, at most `wall_s`. Default 300 (5 minutes) | Time limit of one proposal model call, in seconds. |
| `session_query_limit` | `integer` | yes | 1 to 30, at most the target profile `session_query_limit`. Default 30 | Hidden-loop queries this session may spend. The baseline evaluation counts as one query. |
| `lifetime_query_limit` | `integer` | yes | 1 to 90, at least `session_query_limit`, at most the target profile `lifetime_query_limit`. Default 90 | Hidden-loop queries over the lifetime of the registered loop set. A new session never resets it. |

The defaults are RSI v0.2 values that the owner rulings adopt ([ruling 4](../side-systems/owner-rulings.md#rsi-v02)). A profile may narrow them. It may never widen them.

**RsiQualificationPolicy**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `min_pass_rate_gain` | `number` | yes | 0.05 to 1 | Smallest absolute final pass-rate gain that can qualify a child with more passes, as a fraction of fixture units (0.05 means 5 points). |
| `alpha` | `number` | yes | above 0, at most 0.05 | Significance level of the one-sided exact paired binomial test, as a probability. The child's `p_value` must be at most this. |
| `min_timing_gain` | `number` | yes | 0.1 to 1 | Smallest relative timing gain that can qualify a child with equal passes, as a fraction (0.1 means 10 percent faster). |
| `noise_multiplier` | `number` | yes | min 3 | The timing gain must be more than this multiple of the calibrated timing noise. A unitless factor. |
| `warmup_batches` | `integer` | yes | exactly 5 | Warm-up batches the referee runs before timing. |
| `paired_rounds` | `integer` | yes | exactly 7, equal to the target profile `scoring.paired_rounds` | Paired timing rounds, in alternating order. |

**Invariants**

- The genesis record named by `chain_root_ref` pins this `session_id`, `target_profile_ref` and `hash_profile_ref`. It contains no attempt hash.
- `improver_ref`, `scoring_adapter_ref` and `configuration_ref` equal the target profile values.
- `limits.per_call_s` is at most `limits.wall_s`, and `limits.session_query_limit` is at most `limits.lifetime_query_limit`.
- `parent_declaration_ref` equals the target profile `parent_declaration_ref`.
- The session is immutable. A changed value needs a new session with a new `session_id`.

**Producer obligations (RSI controller)**

- Freeze the record before attempt 1 and before any hidden query.
- Count the baseline evaluation as one hidden-loop query ([ruling 6](../side-systems/owner-rulings.md#rsi-v02)).
- Show the proposer only its own limits. Never show it the splits, the scoring adapter or the qualification statistics.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `session_structure` | The record matches `rsi-session:field-contract:1` | the session does not start |
| `session_limits_within_defaults` | Every limit is at most its default and within the target profile. The qualification policy is not weaker than the frozen rule | the session does not start |
| `session_pins_consistent` | The genesis pins this session, target and hash profile. The parent pin equals the parent declaration digest, and the parent declaration equals the target profile's. The improver, adapter and configuration equal the target profile | the session does not start |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No session starts. The result outcome is `BLOCKED` | The rejected record and the reason |
| The parent is suspended or revoked after freeze | Search stops. The result outcome is `BLOCKED` | The session and its attempts |

**Examples:** [valid](examples/rsi_session.json)

**Minimum quality bar.** A reviewer can tell from this record alone which parent was improved, under which limits, and which rule decides qualification.

### rsi-attempt

Purpose: one proposal attempt of a session: the exact child, the diff, the proposer rationale and the observed cost. Attempts form a hash chain from the session genesis record.

`rsi-attempt:field-contract:1` (version 1.0.0) · Producer: protected RSI controller. Consumers: mutation check, referee, evidence.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this attempt record. |
| `session_id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$`, equals the session `session_id` | Session this attempt belongs to. |
| `sequence` | `integer` | yes | 1 to 20 | Position of the attempt in the session, counted from 1 with no gap. |
| `previous_ref` | `nullable-Ref` | yes | null exactly when `sequence` is 1. Otherwise the attempt with `sequence` minus 1 | Previous attempt in the hash chain. |
| `target_ref` | `Ref` | yes | equals the session `target_profile_ref` | Frozen target profile. |
| `parent_ref` | `Ref` | yes | equals the target profile `parent_ref` | The same eligible parent on every attempt. |
| `child_ref` | `Ref` | yes | the exact proposed child body. Differs from `parent_ref` | Exact proposed child. |
| `diff_ref` | `Ref` | yes | a diff that touches only mutable paths | Allowed implementation change. |
| `rationale` | `string` | yes | 1 to 2000 characters | The proposer explanation. It is not proof and is never read as evidence. |
| `visible_evidence_refs` | `Ref[]` | yes | 0 to 32 items | Visible test results the proposer saw. |
| `queries_used` | `integer` | yes | 0 to 30 | Hidden-loop queries spent so far in the session, as a count. Copied from the custodian, never from the proposer. |
| `violations` | `string[]` | yes | 0 to 50 items | Violations the mutation check observed, as short descriptions. The mutation check writes them, never the proposer. A non-empty list ends the session at this attempt. |
| `stop_reason` | `nullable-string` | yes | non-null when `violations` is not empty or the session stops here | Why the session ended at this attempt, in plain words for the human reviewer. Written by the RSI controller. Null while the session continues. Must be set when `violations` is not empty. No check parses it: the outcome comes from the structured fields. |
| `configuration_ref` | `Ref` | yes | equals the target profile `configuration_ref` | Same frozen target context. |
| `observation_refs` | `Ref[]` | yes | 0 to 64 items | Protected model, time and call traces of the attempt, written by the RSI controller. For the referee, the evidence builder and people. The proposer never reads them. |
| `time_s` | `nullable-number` | yes | min 0. Null when not observed | Observed elapsed session time, in seconds. Null means unavailable, and null is never zero. |
| `model_calls` | `nullable-integer` | yes | min 0. Null when not observed | Observed proposal model calls, as a count. Null means unavailable, and null is never zero. |
| `unavailable_reasons` | `string[]` | yes | 0 to 10 items. Non-empty when `time_s` or `model_calls` is null | Why telemetry is missing. Missing telemetry is never reported as zero. |
| `hash_profile_ref` | `Ref` | yes | equals the session `hash_profile_ref` | Pinned serialization and hash profile. |
| `chain_root_ref` | `Ref` | yes | equals the session `chain_root_ref` | Protected genesis record. The first attempt never refers to itself. |

**Invariants**

- `sequence` runs 1 to N with no gap. `previous_ref` is null exactly for `sequence` 1.
- Every attempt shares the session genesis, the hash profile and the target profile.
- `rationale` is the proposer text. It is never evidence.
- A missing time or call count is `null` with a reason in `unavailable_reasons`. It is never zero.
- A non-empty `violations` ends the session at this attempt.

**Producer obligations (RSI controller)**

- Write the record before any dependent state change becomes actionable.
- Copy `queries_used` from the custodian. Never from the proposer.
- Hash every record as captured, with the pinned hash profile.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `attempt_structure` | The record matches `rsi-attempt:field-contract:1` | the attempt is not recorded |
| `attempt_chain_link` | `previous_ref` is null exactly when `sequence` is 1 | the session halts |
| `attempt_matches_genesis` | The genesis record pins this `session_id`, target and hash profile | the session halts |
| `attempt_unavailable_explained` | A null `time_s` or `model_calls` comes with at least one `unavailable_reasons` entry | the attempt is not recorded |
| `attempt_violation_halts` | A non-empty `violations` has a non-null `stop_reason` | the attempt is not recorded |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | The session halts and keeps the evidence | The attempt, the genesis record and the reason |
| A violation is observed | The session ends `SECURITY_HALTED`. A [security clearance](#security-clearance) is needed before a new session | The attempt and the violation evidence |

**Examples:** [valid](examples/rsi_attempt_01.json)

**Minimum quality bar.** A reviewer can follow the chain from the genesis record to the final attempt and see what each attempt cost, without hidden fixture contents.

### rsi-loop-feedback

Purpose: the only feedback the proposer receives from the hidden loop split: counts. It never carries case IDs, content, timing or expected answers.

`rsi-loop-feedback:field-contract:1` (version 1.0.0) · Producer: custodian. Consumers: proposer.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this loop feedback record. |
| `passed` | `integer` | yes | min 0, at most `total` | Aggregate hidden-loop passed count. A count only, with no case identity. The proposer reads this. |
| `total` | `integer` | yes | min 20 | Hidden-loop case count, as a count. A count only, with no case identity. |
| `queries_left` | `integer` | yes | 0 to 30 | Hidden-loop queries still allowed in the session. |

**Invariants**

- `passed` is at most `total`. `total` is at least 20 ([RSI workbench](../side-systems/rsi-workbench.md#data-needed-from-day-one)).
- The record holds no field beyond those listed. Any extra field is refused.
- Feedback from the final split never reaches the proposer.

**Producer obligations (custodian)**

- Count the query against the session and lifetime limits before releasing the record.
- Release counts only. Never release which cases failed.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `feedback_structure` | The record matches `rsi-loop-feedback:field-contract:1`, with no extra field | the proposer does not receive it |
| `feedback_counts_consistent` | `passed` is between 0 and `total` | the proposer does not receive it |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | The proposer does not receive the record. The query stays counted | The record and the reason |



**Minimum quality bar.** A reviewer can confirm that the proposer saw only counts.

### rsi-referee-evidence

Purpose: the protected comparison of parent and child by the independent referee: repeated aggregate results per split, with paired timing. Only restricted admission and the evidence builder read it.

`rsi-referee-evidence:field-contract:1` (version 1.0.0) · Producer: protected independent referee. Consumers: restricted admission, evidence builder.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this referee evidence record. |
| `attempt_ref` | `Ref` | yes | an `rsi-attempt` record | Exact attempt the referee assessed. |
| `target_ref` | `Ref` | yes | equals the attempt `target_ref` | Frozen scorer and splits. |
| `parent_ref` | `Ref` | yes | equals the attempt `parent_ref` | Same parent. |
| `child_ref` | `Ref` | yes | equals the attempt `child_ref` | Same candidate. |
| `pairs` | `RSIPair[]` | yes | 1 to 16 items. Each `split` is the target `hidden_loop` or `hidden_final` identity | Comparable repeated aggregate results of parent and child. |
| `mandatory_parent_tests_passed` | `boolean` | yes | true for a certifiable child | Whether the child passed every mandatory parent test. |
| `integrity_passed` | `boolean` | yes | true for a certifiable child | Whether custody, mutation and effect checks passed. |
| `final_evaluations` | `integer` | yes | exactly 1 (check `referee_integrity_holds`) | Terminal evaluations the referee ran. A second one is a misuse of the final split. |
| `violations` | `string[]` | yes | 0 to 50 items. Empty for a certifiable child | Protected security results. |
| `configuration_ref` | `Ref` | yes | equals the target profile `configuration_ref` | Exact comparable evaluation context of parent and child. |
| `signature` | `string` | yes | 43 to 128 characters of base64url or hex | The custodian's signature over the canonical JSON bytes of this record without `signature`. The referee writes it, running as `rsi_custodian`, only after its checks pass. `rsi_worker` cannot read the key ([D46](../method/decisions.md#d46)). |
| `signer_key_id` | `string` | yes | equals the operator config `rsi.custodian_key_id` | ID of the signing key, not the key itself. A mismatch with the pinned ID blocks certification. |

**Invariants**

- Every pair has a total of at least 20 and `0 <= parent_passed <= child_passed <= total` for a certifiable child.
- Each pair has exactly `scoring.paired_rounds` parent times and child times.
- `final_evaluations` is exactly 1. The final split is read once per session.
- The record names the same parent, child, target and configuration as the attempt.
- `violations` is empty and `integrity_passed` and `mandatory_parent_tests_passed` are true for a certifiable child.
- The signature verifies against the custodian public key pinned in the operator config. In production it is an Ed25519 signature. The example files carry a stand-in, the SHA-256 of the key ID and the canonical bytes, because the package holds no private key.

**Producer obligations (referee)**

- Run the child under the pinned configuration, the same as the parent.
- Report aggregate counts and times only. Never report case identities.
- Refuse a second final evaluation.
- Run as `rsi_custodian` and sign the record before it leaves the referee. Never sign a record whose checks failed.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `referee_structure` | The record matches `rsi-referee-evidence:field-contract:1` | the evidence is not certified |
| `referee_lineage_matches` | Parent, child and target equal those of the attempt, and the configuration equals the target profile | certification is blocked |
| `referee_integrity_holds` | Mandatory parent tests and integrity passed, no violation, and `final_evaluations` is 1 | certification is blocked |
| `referee_pairs_comparable` | Each pair names a hidden split of the target, has a total of at least 20, valid counts and the paired round count. Splits are distinct. Scoring order and query limits are the frozen ones | certification is blocked |
| `referee_signature_valid` | `signer_key_id` equals the pinned custodian key ID, and `signature` verifies over the canonical bytes without `signature` | certification is blocked |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | Certification is blocked. The session ends `INVALID` or `SECURITY_HALTED` | The evidence and the reason |

**Examples:** [valid](examples/rsi_referee_evidence.json) · rejected by `referee_signature_valid`: [rsi_referee_evidence_invalid_signature](examples/rsi_referee_evidence_invalid_signature.json) (a count was edited after signing)

**Minimum quality bar.** A reviewer can recompute every count and median of a [session result](#rsi-session-result) from this record.

### rsi-evidence-export

Purpose: the audience-filtered summary of a referee comparison for a human and the library. It states the result and what was withheld.

`rsi-evidence-export:field-contract:1` (version 1.0.0) · Producer: trusted audience-filtered builder. Consumers: authorized human, library.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this evidence export. |
| `attempt_ref` | `Ref` | yes | the terminal child attempt | Attempt the export describes. |
| `referee_ref` | `Ref` | yes | an `rsi-referee-evidence` record whose `attempt_ref` equals `attempt_ref` | Restricted evidence this export summarizes. |
| `parent_ref` | `Ref` | yes | equals the referee evidence `parent_ref` | Exact parent. |
| `child_ref` | `Ref` | yes | equals the referee evidence `child_ref` | Exact child. |
| `summary` | `string` | yes | 1 to 1000 characters. Holds no hidden split identity, case ID or expected answer | Allowed paired aggregate comparison. |
| `redactions` | `string[]` | yes | 1 to 20 items | Names the kinds of content withheld (hidden cases, identities, answers, scoring detail), never the withheld content itself. Never empty. |
| `violations` | `string[]` | yes | equals the referee evidence `violations` | Allowed security outcomes. |

**Invariants**

- `referee_ref` names a referee evidence record of the same attempt, parent and child.
- The summary holds no hidden split identity, case ID or expected answer.
- `redactions` is never empty: the hidden cases, identities, answers and scoring detail are always withheld.
- A hash of withheld content does not grant permission to read it.

**Producer obligations (evidence builder)**

- Build the export only from the referee evidence, never from proposer-visible data.
- Never feed a final export back into a proposal.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `export_structure` | The record matches `rsi-evidence-export:field-contract:1` | the export is not released |
| `export_matches_referee` | Attempt, parent, child and violations equal those of the referee evidence | the export is not released |
| `export_redacts_hidden` | `redactions` is not empty and the summary names no hidden split identity | the export is not released |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | The export is not released | The referee evidence stays custodian-only |

**Examples:** [valid](examples/rsi_evidence_export.json)

**Minimum quality bar.** A reviewer can read the result and see that nothing hidden was released.

### rsi-session-result

Purpose: the one terminal result of a session. It records the outcome, the retained child and the statistics the qualification rule was applied to.

`rsi-session-result:field-contract:1` (version 1.0.0) · Producer: RSI controller, from referee evidence. Consumers: candidate packager, human reviewer, evidence export, admission command.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this session result. |
| `session_ref` | `Ref` | yes | the frozen `rsi-session` record | Session this result closes. |
| `outcome` | `string` | yes | enum, see below | Terminal outcome of the session. |
| `parent` | `CcPin` | yes | equals the session `parent` | Original parent of the final comparison. |
| `child` | `nullable-CcPin` | yes | non-null for `QUALIFIED`. Null when no child was retained | Retained child version. |
| `child_declaration_ref` | `nullable-Ref` | yes | null exactly when `child` is null. Its digest equals `child.declaration_sha256` | Exact child declaration bytes. |
| `attempt_refs` | `Ref[]` | yes | 0 to 20, in sequence order, a hash chain from the session genesis | Every attempt of the session. |
| `final_attempt_ref` | `nullable-Ref` | yes | an entry of `attempt_refs`. Null when no final comparison ran | Attempt that produced the finalist. |
| `referee_evidence_ref` | `nullable-Ref` | yes | non-null when a final comparison ran | Protected referee evidence of the final comparison. |
| `qualified_by` | `string` | yes | enum `pass_gain`, `timing_tiebreak`, `none`. `none` exactly when `outcome` is not `QUALIFIED` | Which branch of the qualification rule the child met. |
| `statistics` | `nullable-QualificationStatistics` | yes | non-null when a final comparison ran | Counts and statistics the rule was applied to. |
| `attempts_used` | `integer` | yes | 0 to the session `limits.max_attempts` | Attempts the session started. |
| `queries_used` | `integer` | yes | 0 to the session `limits.session_query_limit`. Includes the baseline query | Hidden-loop queries the session spent. |
| `stop_reason` | `string` | yes | 1 to 300 characters | Why search stopped, in plain words, for the human reviewer. The outcome comes from `outcome`, not from this text. |
| `limitations` | `string[]` | yes | at most 20 | Limits of this result, for example synthetic data or unavailable telemetry. For the reader. They do not change `outcome`. |
| `recorded_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the controller closed the session. UTC, whole seconds. |
| `signature` | `string` | yes | 43 to 128 characters of base64url or hex | The custodian's signature over the canonical JSON bytes of this record without `signature` ([D46](../method/decisions.md#d46)). Admission verifies it again. |
| `signer_key_id` | `string` | yes | equals the operator config `rsi.custodian_key_id` | ID of the signing key, not the key itself. A mismatch with the pinned ID blocks the candidate package. |

**Enum `outcome`**

These are the nine terminal outcomes of RSI v0.2. They are RSI session outcomes, not gate verdicts.

| Value | Meaning |
|---|---|
| `QUALIFIED` | The final comparison met the qualification rule. The workbench may write a candidate package |
| `NO_IMPROVEMENT` | Search ended with the original parent as incumbent, or the final comparison showed no qualifying gain. The parent stays active |
| `INCONCLUSIVE` | The evidence cannot decide, for example no defensible independent-unit design or unreliable timing. No gain is claimed |
| `UNEVALUATED_CANDIDATE` | A child was retained, but the final comparison did not run, for example because the deadline or the final reserve ran out |
| `BLOCKED` | Readiness, authority, adapter, headroom or a pin was missing before search. No search ran, or it stopped |
| `CANCELLED` | A human cancelled the session. No new evaluation started |
| `INVALID` | A protected input or the referee drifted, or the candidate hash changed after assessment. The comparison is void |
| `SECURITY_HALTED` | The mutation check found a violation. A [security clearance](#security-clearance) is needed before a new session |
| `ERROR` | The environment, the infrastructure or the evaluator failed |

**Enum `qualified_by`**

| Value | Meaning |
|---|---|
| `pass_gain` | The child passed more hidden-final fixtures, with the minimum gain, zero protected regressions and `p_value` at most `alpha` |
| `timing_tiebreak` | The child passed the same fixtures, with zero protected regressions and a calibrated timing gain |
| `none` | The child did not qualify. Used for every outcome other than `QUALIFIED` |

**QualificationStatistics**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `fixture_units` | `integer` | yes | min 20 | Independent fixture units in the hidden-final split. |
| `parent_passed` | `integer` | yes | 0 to `fixture_units` | Units the parent passed. |
| `child_passed` | `integer` | yes | 0 to `fixture_units` | Units the child passed. |
| `gain_units` | `integer` | yes | min 0. `child_passed - parent_passed` equals `gain_units - loss_units` | Units the parent failed and the child passed (g). |
| `loss_units` | `integer` | yes | min 0 | Units the parent passed and the child failed (l). Any value above 0 is a protected regression. |
| `pass_rate_gain` | `number` | yes | equals `(child_passed - parent_passed) / fixture_units` | Absolute pass-rate gain of the child. |
| `p_value` | `nullable-number` | yes | equals `P[Binomial(g + l, 0.5) >= g]`. Null exactly when `g + l` is 0 | One-sided exact paired binomial probability. With no discordant unit there is no evidence of a gain. |
| `timing` | `nullable-TimingComparison` | yes | non-null when `qualified_by` is `timing_tiebreak` | Calibrated timing comparison for equal passes. |

**TimingComparison**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `warmup_batches` | `integer` | yes | exactly 5 | Warm-up batches before timing. |
| `paired_rounds` | `integer` | yes | exactly 7 | Paired rounds, in alternating order. |
| `parent_median_s` | `number` | yes | above 0 | Median of the parent batch durations, in seconds. |
| `child_median_s` | `number` | yes | above 0 | Median of the child batch durations, in seconds. |
| `relative_gain` | `number` | yes | equals `1 - child_median_s / parent_median_s` | Relative timing gain of the child. |
| `calibrated_relative_noise` | `number` | yes | min 0, from the target calibration | Timing noise measured by calibration, as a fraction. |
| `noise_multiplier` | `number` | yes | equals the session `qualification.noise_multiplier` | Multiple of the noise the gain must exceed. |
| `min_relative_gain` | `number` | yes | at least the session `qualification.min_timing_gain` | Smallest qualifying relative gain. |

**Invariants**

- `qualified_by` is `none` exactly when `outcome` is not `QUALIFIED`.
- `QUALIFIED` needs a non-null `child`, `child_declaration_ref`, `referee_evidence_ref` and `statistics`.
- `pass_gain` needs `child_passed > parent_passed`, `loss_units` 0, `pass_rate_gain` at least the session `min_pass_rate_gain`, and `p_value` at most the session `alpha`.
- `timing_tiebreak` needs `child_passed = parent_passed`, `loss_units` 0, `relative_gain` at least `min_relative_gain` and more than `noise_multiplier × calibrated_relative_noise`.
- A child with fewer passes never qualifies. Timing cannot make up for fewer passes.
- The statistics equal the hidden-final pair of the referee evidence, and the timing medians equal the medians of its paired times.

**Producer obligations (RSI controller)**

- Copy counts and times from the referee evidence. Never recompute them from proposer-visible data.
- Recompute `pass_rate_gain`, `p_value` and `relative_gain` from the counts and times before writing.
- Write one result per session. A later review never edits it.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `result_structure` | The record matches `rsi-session-result:field-contract:1` | no candidate package is written |
| `qualification_rule_holds` | The invariants above hold, and `pass_rate_gain`, `p_value` and `relative_gain` recompute | no candidate package is written |
| `no_evidence_no_hidden_query` | A result with `referee_evidence_ref` null has `queries_used` 0, null `statistics` and an outcome other than `QUALIFIED`. A child rejected before the referee reached a hidden split looks like this ([RSI-2](../side-systems/rsi-workbench.md#build-criteria)) | no candidate package is written |
| `result_matches_referee_evidence` | The statistics equal the single hidden-final pair of the referee evidence, and the child body is the assessed child | no candidate package is written |
| `referee_signature_valid` | `signer_key_id` equals the pinned custodian key ID, and `signature` verifies over the canonical bytes without `signature` | no candidate package is written |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No candidate package. The human sees the reasons | The result, the attempts and the referee evidence |
| Outcome other than `QUALIFIED` | No candidate package. The parent stays active | The result and every attempt |

**Examples:** [valid, qualified by the timing tie-break](examples/rsi_session_result.json)

**Minimum quality bar.** A reviewer can recompute the qualification decision from this record and the referee evidence, without hidden fixture contents.

## Admission inbox

### candidate-package

Purpose: what the workbench writes to the admission inbox for one qualified child. The admission command checks it again before it writes a [library admission](field-catalog.md#library-admission) record. A package grants no standing.

`candidate-package:field-contract:1` (version 1.0.0) · Producer: RSI workbench packager. Consumers: admission inbox, admission command, human reviewer.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this candidate package. |
| `target_profile_ref` | `Ref` | yes | equals the session `target_profile_ref` | Target profile that set the mutable paths. |
| `session_ref` | `Ref` | yes | the frozen `rsi-session` record | Session that produced the child. |
| `session_result_ref` | `Ref` | yes | an `rsi-session-result` with outcome `QUALIFIED` | Result that qualified the child. |
| `provenance_ref` | `Ref` | yes | a `candidate-provenance` record whose `declaration_ref` equals `child_declaration_ref` | Builder, body files and evidence of the child. |
| `parent` | `CcPin` | yes | equals the session `parent`. `declaration_sha256` equals `parent_declaration_ref.sha256` | Parent version and its declaration digest. |
| `child` | `CcPin` | yes | same `cc_name` as `parent`, a new `cc_version`. `declaration_sha256` equals `child_declaration_ref.sha256` | Child version and its declaration digest. |
| `parent_declaration_ref` | `Ref` | yes | the parent declaration bytes | Declaration the child is compared with. |
| `child_declaration_ref` | `Ref` | yes | the child declaration bytes. Its `identity.lineage` names the parent | Declaration admission stores for the child. |
| `diff_ref` | `Ref` | yes | equals the final attempt `diff_ref` | The allowed implementation change. |
| `referee_evidence_ref` | `Ref` | yes | equals the session result `referee_evidence_ref` | Protected paired evidence of the final comparison. |
| `mutable_paths_touched` | `string[]` | yes | 1 to 16 unique paths, each in the target profile `mutable_paths` | Body paths the change touched. The packager derives them from the diff. Admission checks each against the target profile `mutable_paths`, and a path outside it is a security halt. |
| `created_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the workbench wrote the package to the inbox. UTC, whole seconds. |

**Invariants**

- `parent.cc_name` equals `child.cc_name`, and the version labels differ.
- The parent declaration has `evolution.rsi` `propose`. The child declaration differs from it only in the derived identity fields `/identity/version_label`, `/identity/carrier`, `/identity/body` and `/identity/lineage`, and every body file that was added, removed or changed matches a `files:` glob of the parent `evolution.may_change`. Every [always-protected pointer](declaration.md#evolution-what-rsi-may-change), including `/evolution`, is unchanged.
- The child declaration has lineage: `parent` is `parent_declaration_ref`, `relation` is `supersedes` and `builder` is `rsi_workbench`.
- The session result is `QUALIFIED` and names the same parent, child, session and referee evidence.

**Producer obligations (workbench packager)**

- Derive the child declaration from the parent declaration. Change only the version label, the carrier and body pins, and the lineage.
- Hash every file as captured, without reserialization ([hashing profile](declaration.md#hashing-profile)).
- Write the package only for a `QUALIFIED` result. Never write one for any other outcome.

**Host checks (admission command)**

These checks are deterministic. They run in the admission command, outside the workbench, before any library record is written.

| Check ID | Rule | Outcome | Build criterion |
|---|---|---|---|
| `package_structure` | The package matches `candidate-package:field-contract:1` | `rejected` | RSI-5 |
| `package_refs_resolve` | Every Ref resolves to stored bytes with its SHA-256 | `blocked` | RSI-5 |
| `declaration_digests_match` | Each pin equals its declaration name, version label and digest. The provenance names the child declaration. The child keeps the name and changes the version label | `rejected` | RSI-5 |
| `child_lineage_matches_parent` | The child declaration lineage names the parent declaration, with relation `supersedes` and builder `rsi_workbench` | `rejected` | RSI-5 |
| `changes_allowed` | The child declaration equals the parent outside the derived identity fields, and every changed body file is inside the parent `may_change` ([D34](../method/decisions.md#d34)) | `rejected` | RSI-3 |
| `rsi_no_copy` | No body file of the child matches a body file of a CC whose `evolution.rsi` is `none` | `rejected` | RSI-3 |
| `mutable_paths_within_profile` | Every touched path is a target profile mutable path, with no repeat | `rejected`, and the session record shows a security halt | RSI-3 |
| `session_result_qualified` | The session result is `QUALIFIED` and names this parent, child, session and referee evidence | `rejected` | RSI-2 |
| `attempt_chain_verifies` | Attempts run 1..N, each `previous_ref` names the one before, and all share the session genesis, hash profile and target | `blocked` | RSI-6 |
| `diff_matches_final_attempt` | The diff and the child body equal the final attempt | `rejected` | RSI-5 |
| `referee_signature_valid` | The referee evidence and the session result each carry a signature that verifies against the custodian public key pinned in the operator config ([D46](../method/decisions.md#d46)). Only `rsi_custodian` can write to the admission inbox mount, so a package from any other identity never reaches the command | `blocked` | RSI-5 |

RSI-1 (the hot path builds without the workbench) and RSI-4 (the proposer never sees case IDs, expected answers or hidden contents) are checked on the workbench build, not on a package. After these checks pass, the admission command writes an `admitted` library admission record with standing `inactive`. Activation is a separate human [activation record](field-catalog.md#activation-record).

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A content check fails | Admission record with status `rejected`, standing `inactive` | The package, the record and the reasons |
| A ref or the hash chain does not verify | Admission record with status `blocked`, standing `inactive` | The package and the reasons |
| A path outside the profile was touched | `rejected`. The session is treated as `SECURITY_HALTED` and needs a clearance | The package and the violation evidence |

**Examples:** [valid](examples/candidate_package.json) · rejected by `changes_allowed`: [candidate_package_invalid_child_outside_may_change](examples/candidate_package_invalid_child_outside_may_change.json) (the child adds a body file outside `may_change`)

**Minimum quality bar.** The admission command can accept or refuse the child from the package and the records it names, without trusting anything the proposer wrote.

### candidate-provenance

Purpose: who built a candidate and from what: the exact declaration, every body file, the parent body file and the builder record. The admission command reads it with the candidate package.

`candidate-provenance:field-contract:1` (version 1.0.0) · Producer: candidate builder with protected capture. Consumers: library admission, human, RSI.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this candidate provenance record. |
| `declaration_ref` | `Ref` | yes | the exact child declaration bytes | Declaration of the candidate. |
| `implementation_refs` | `Ref[]` | yes | 1 to 64 items, equal in order to the declaration `identity.body` digests | Complete exact body files. |
| `parent_ref` | `nullable-Ref` | yes | null for a first version. For an RSI child, one body file of the parent declaration | Exact prior implementation. |
| `builder_ref` | `Ref` | yes | the builder record or the final RSI attempt | Attributable builder. |
| `evidence_refs` | `Ref[]` | yes | 1 to 32 items | Independent compatibility, security and provenance support. |

**Invariants**

- `implementation_refs` equal the declaration `identity.body` digests, in order.
- `parent_ref` is null for a first version. For an RSI child it is one body file of the parent declaration that `identity.lineage.parent` names.
- The record grants no standing.

**Producer obligations (candidate builder)**

- Capture the declaration and every body file as written, without reserialization.
- Name the builder record: the final RSI attempt for an RSI child.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `provenance_structure` | The record matches `candidate-provenance:field-contract:1` | admission is blocked |
| `provenance_matches_declaration` | The implementation refs equal the declaration body digests in order | admission is blocked |
| `provenance_lineage_consistent` | `parent_ref` is null exactly when the declaration has no lineage parent, and otherwise is a body file of that parent | admission is blocked |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | Admission is `blocked` | The record and the reason |

**Examples:** [valid](examples/rsi_child_candidate.json)

**Minimum quality bar.** A reviewer can tell from the record which bytes make up the candidate and who produced them.

## Safety and completion records

### security-clearance

Purpose: the human decision that lets a new RSI session start after a security halt. It never resumes the halted session and never activates a child.

`security-clearance:field-contract:1` (version 1.0.0) · Producer: authorized security human through protected RSI controller. Consumers: new-session eligibility, audit.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this clearance record. |
| `actor_id` | `string` | yes | 1 to 120 characters, an authorized security reviewer | The authorized security reviewer who decided. A person, not the operator who ran the session. |
| `recorded_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the decision was recorded. UTC, whole seconds. |
| `halted_session_id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$`, a session whose result is `SECURITY_HALTED` | Exact session the violation halted. |
| `violation_refs` | `Ref[]` | yes | 1 to 32 items | Protected incident evidence. |
| `remediation_ref` | `Ref` | yes | the exact remediation bytes | Remediation applied. |
| `guardrail_evidence_refs` | `Ref[]` | yes | 0 to 32 items. At least 1 when `decision` is `cleared` | Independent validated guardrail evidence. |
| `decision` | `string` | yes | enum `cleared`, `denied` | Outcome of the review. |
| `effect_scope` | `string` | yes | exactly `new_rsi_session_only` | What a clearance allows: a new session, nothing else. |

**Invariants**

- `effect_scope` is `new_rsi_session_only`.
- A `cleared` decision has incident evidence, a remediation and at least one guardrail evidence ref.
- A `denied` decision keeps the target blocked for new sessions.
- The actor is an authorized security reviewer, not the operator who ran the session.

**Producer obligations (protected RSI controller)**

- Check that the actor is authorized before writing the record.
- Link the incident evidence of the halted session.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `clearance_structure` | The record matches `security-clearance:field-contract:1` | the record is not stored |
| `clearance_evidence_complete` | A `cleared` decision has non-empty `violation_refs` and `guardrail_evidence_refs` | new sessions stay blocked |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | New sessions stay blocked | The record and the reason |



**Minimum quality bar.** A reviewer can tell why a halted target may or may not start a new session.

### rsi-completion-report

Purpose: the report that closes the M1 RSI acceptance run. It states which build criteria passed, which tests ran, what was gained, what is blocked and which containment limits remain. This is the RSI v0.2 "M1 completion report" ([owner rulings](../side-systems/owner-rulings.md#rsi-v02), row 8).

`rsi-completion-report:field-contract:1` (version 1.0.0) · Producer: RSI workbench report builder, after a human closes the M1 RSI acceptance run. Consumers: human reviewer, product acceptance.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this completion report. |
| `session_result_refs` | `Ref[]` | yes | 1 to 64 items, each an `rsi-session-result` record | Every session in scope, including no-gain and inconclusive ones. |
| `requirement_coverage` | `RsiRequirementStatus[]` | yes | 1 to 32 items, `requirement_id` unique | Status of each RSI build criterion. |
| `executed_tests` | `RsiTestResult[]` | yes | 0 to 200 items, `test_id` unique | Acceptance and security tests that ran. |
| `modalities` | `string[]` | yes | 1 to 2 items, each `code` or `text` | Modalities the sessions covered. `text` appears only when the bounded headless text path ran. |
| `qualified_result_refs` | `Ref[]` | yes | 0 to 64 items, each also in `session_result_refs` with outcome `QUALIFIED` | Sessions that produced a qualifying child. Gains are read from them. |
| `onboarding_evidence_refs` | `Ref[]` | yes | 0 to 16 items | Evidence that a second, unrelated target ran through the same engine. |
| `transfer_claim` | `string` | yes | enum `none`, `supported` | Whether the report claims improver transfer. It is a separate claim gate. |
| `transfer_evidence_refs` | `Ref[]` | yes | 0 to 16 items. At least 1 when `transfer_claim` is `supported` | Held-out transfer evidence. |
| `blockers` | `string[]` | yes | 0 to 50 items. At least 1 when a requirement is `BLOCKED` | Blocked dependencies, each with its reason. |
| `uncertainties` | `string[]` | yes | 0 to 50 items | What the evidence leaves open. |
| `unavailable` | `string[]` | yes | 0 to 50 items | Values that could not be measured, for example monetary cost. |
| `containment_limitations` | `string[]` | yes | 0 to 20 items | Residual containment limits and any discovered vulnerability. |
| `compiled_by` | `string` | yes | 1 to 120 characters | Name of the person or tool that compiled the report, for audit. Display only. It grants nothing and no check branches on it. |
| `recorded_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the report was written. |

**RsiRequirementStatus**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `requirement_id` | `string` | yes | pattern `^RSI-[1-9][0-9]?$`, a build criterion of the [RSI workbench](../side-systems/rsi-workbench.md#build-criteria) | Requirement this row reports. |
| `status` | `string` | yes | enum `PASS`, `FAIL`, `BLOCKED`, `INCOMPLETE` | Result against the criterion. `BLOCKED` and `INCOMPLETE` are never `PASS`. |
| `evidence_refs` | `Ref[]` | yes | 0 to 16 items. At least 1 for `PASS` and `FAIL` | Reviewable evidence of the result. |
| `note` | `string` | yes | 1 to 300 characters | Reason for the status, in plain words. |

**RsiTestResult**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `test_id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Acceptance or security case that ran. |
| `kind` | `string` | yes | enum `acceptance`, `security` | Which suite the case belongs to. |
| `outcome` | `string` | yes | enum `passed`, `failed`, `not_run` | Result. For a security case, `passed` means the attempt was blocked and its evidence kept. |
| `evidence_ref` | `nullable-Ref` | yes | null only when `outcome` is `not_run` | Evidence of the run. |

**Invariants**

- Every `PASS` or `FAIL` requirement has at least one evidence ref. `BLOCKED` and `INCOMPLETE` are never reported as `PASS`.
- A `BLOCKED` requirement has at least one entry in `blockers`.
- Every `qualified_result_refs` entry is a session result in scope with outcome `QUALIFIED`.
- `transfer_claim` `supported` has held-out transfer evidence. Improver transfer is a separate claim gate.
- A security test that ran has evidence. A failed security test means the report does not pass every requirement.
- Missing telemetry is listed under `unavailable`. It is never reported as zero. Measured, unavailable and inferred values stay apart.
- No-gain and inconclusive sessions stay in `session_result_refs`. They count toward honest evaluation but not toward a qualifying child.

**Producer obligations (RSI workbench report builder)**

- Build the report from session results, referee evidence and test records. Never from proposer text.
- Report each build criterion from the [RSI workbench](../side-systems/rsi-workbench.md#build-criteria) with its status, even when it did not run.
- List every discovered vulnerability and containment limit.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `completion_report_structure` | The record matches `rsi-completion-report:field-contract:1` | the report is not accepted |
| `completion_report_claims_backed` | The invariants above hold: evidence for every `PASS` or `FAIL`, blockers for every `BLOCKED`, qualified results in scope, transfer evidence, unique IDs and no all-pass report after a failed security test | the report is not accepted |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | The report is not accepted. The human sees the reasons | The report and the reasons |



**Minimum quality bar.** A reviewer can tell from the report what is proven, what is blocked and what is still open, without trusting a claim that has no evidence.
