---
type: schema
id: cc.finding.v1
status: proposed
tags: [schema]
---

# Finding · `cc.finding.v1`

A typed observation about capsules, judges or an unmet need. One Finding per instance, never edited; counts across runs come from queries. A Finding is evidence for a decision, never a score. RSI reads gaps to know what to build; the librarian cites Findings when it moves a Standing; and it carries what write-once records cannot hold: measured cost, latency and pass rate, judge calibration, and the invalidation of a Verdict. The whole record is unchecked in M1.

**Rules:** INV-2, INV-3 (one writer per kind), INV-13 (kinds are a registry).

## Fields

Extends [common](common.md). Its `scope` is a `run_id`, or `library` for Findings that span runs.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `kind` | `reg(finding_kind)` | req | unchecked | RSI, librarian | What was found; the kinds are below |
| `subjects` | `list<object>` | req | unchecked | RSI, librarian | What it is about. Each is `{kind, id}`, where `kind` is `decl_hash`, `check_id`, `judge_decl_hash` or `verdict_id`. Empty for a gap |
| `step_id` | `string` | opt | unchecked | RSI, librarian | The call site where it was seen, if in a run. Example: `extract` |
| `text` | `text` | req | unchecked | RSI, librarian | A short account for people. Example: `No admitted capsule turns a pdf file into text.` |
| `evidence` | `list<EvidenceRef>` | req | unchecked | RSI, librarian | The Observations, Verifications or trajectories behind it |
| `measure` | `object` | opt | unchecked | RSI, librarian | What was measured: `{name, value, unit, n}`, `n` the number of observations. Example: `{"name": "false_pass", "value": 0.08, "unit": "rate", "n": 120}` |
| `detail` | `json` | opt | unchecked | RSI, librarian | Kind-specific detail, in the shape the kind names below |

**Kinds.** Each is a row in the `finding_kind` registry, with one writer.

| Kind | Writer | `detail` |
|---|---|---|
| `gap` | selection | `need {given, want, effects_allowed}`; `near_miss[] {decl_hash, reason_code}`; `generalist_obs_id`, when a general-purpose agent filled the gap |
| `fit_failure` | gate | the Verification id: the capsule passed its own checks but failed a `step` check |
| `use_outcome` | gate | the Verification id in which a capsule's own check failed |
| `drift` | librarian | what moved, against what admission saw |
| `audit_violation` | librarian | effects observed beyond those declared: `effects_observed` against the Declaration's `effects` |
| `verifier_audit` | librarian | a judge's calibration: `false_pass`, `false_fail`, `n`, and the dataset used |
| `measurement` | librarian | measured use of one `decl_hash` over a window: `{window, n, pass_rate, time_s {p50, p95}, tokens {p50, p95}, money_p50}`, from Observations and Verifications. Cost, latency and quality live here, never in the Declaration |
| `invalidation` | librarian | the Verdict that no longer holds, and why: a changed dependency, policy epoch or judge |
| `build_decision`, `build_failed` | RSI | RSI chose not to build for a gap, or tried and failed: the gap's id, and `reasons` (a list of `Reason`) |

A new kind is one registry row `{kind, writer, detail shape}`; readers skip kinds they do not know.

## Elsewhere

How many `use_outcome` Findings make a capsule `suspect`, and which moves a Finding may cause: policy `librarian`. When a Finding is `builder_hidden`: policy `gates`.

## Reuse

- `EvidenceRef` (agent-core `symphony/models/evaluation.py:57`): as is, as a list.
- Per-kind required fields (AI4Research `feedback-event.schema.v1.draft.json`): the pattern; the kind decides the detail shape.
- `RsiTaskCreateRequest` (agent-core `rsi/schema.py:23`): the gap is not reshaped to fit it; a mapping is published instead.
- RSI's candidate gate results (`rsi/harness_rsi/single_harness/iterative.py:1247`): not reused; ad hoc dictionaries.
