# Opt-in evidence-aware review amendment (D20 / D24)

**Status:** User-authorized, separately versioned M1 pilot amendment; activation is
explicit and remains subject to the ordinary admission, standing and campaign
controls. This note does not change the received PRD or rewrite the D20/D24
baseline. See the maintained [D20/D24 decisions](../code/Missions/docs/source/Architecture_Design/method/decisions.md#d20)
and the [checking boundary](../code/Missions/docs/source/Architecture_Design/checking/README.md).

## Scope

D20 and D24 continue to define the default: the semantic verifier sees only the
pinned declaration and exact output, and its criteria are answerable from that
pair. Existing verifier releases, output-only profiles, captures and receipts
retain that behavior.

The amendment adds a distinct opt-in v2 profile, `task_sources_tier1_v1`, for a
new immutable work-CC/check-profile release. It allows specifically selected
criteria to use a bounded host projection of explicitly named original task or
source inputs and the outcomes of mandatory, passing Tier 1 checks. The verifier
CC itself must also be selected at a new immutable release that declares the
optional evidence input. A profile is evidence-aware only when its version,
mode, selected criterion IDs, input names and byte ceiling all pass the host's
exact checks. No existing association or default pin is switched in place.

For a paper summary, the host may resolve the exact typed `documents` buffer
through its captured inventory, the accepted Brief and the original
`resource_reads` ceiling, then disclose canonical extracted text within the
profile's byte limit. For evaluation-oriented work, a profile may select an
original accepted input such as `benchmark_payload` or `payload` when that port
is present. It does not traverse arbitrary refs or raw score files. Tier 1
outcomes are disclosed as check IDs and `PASS` values; detailed check reasons
and private evidence are not included.

The separate evaluation replay path currently supports output-only verifier
profiles. It rejects `task_sources_tier1_v1` for E2 until replay passes the
exact host-built evidence projection into review and retains that projection in
the accepted review context. This general amendment does not imply that
evaluation replay has this integration.

The projection excludes worker conversations, observations, gold or expected
answers, answer keys, private solutions and unselected inputs. Source bytes are
untrusted data, never reviewer instructions. The fixed reviewer instructions
must say which criteria may use the selected evidence; all other criteria,
including generic output conformance and internal consistency, remain
output-only. Tier 1 and the protected host gate remain authoritative.

## Refusal and failure behavior

Missing or mismatched evidence is a host binding error and prevents the model
call. A valid reviewer reply that marks a blocking criterion `INCONCLUSIVE`
produces a non-advancing assessment and halts that gate. A provider timeout or
other bridge failure remains a provider failure: it is not converted into an
abstention assessment, and the gate cannot advance. There are no implicit
retries.

The reviewer cannot set artifact identity, attach trusted evidence references,
change criteria, choose the final gate action or release output. The host
retains the exact subject and review context, recomputes the evidence
projection before assessment acceptance, and validates the assessment against
the pinned criteria.

## Assurance limits

This change exposes evidence to a semantic model; it does not establish that
the model reasons correctly about it. The source-injection check verifies that
host code keeps hostile source bytes in the data payload and does not splice
them into system instructions. It does not prove that a model will resist that
instruction. An abstention test verifies verdict routing, not whether a live
model abstains at the right rate.

No generic contradiction resolver, arithmetic checker or citation-entailment
checker is introduced by this amendment. Where a specific pipeline already has
deterministic hash, span, payload-recomputation or range checks, those checks
continue to provide their existing bounded guarantee. A citation that resolves
to bytes is not thereby shown to entail a claim. Contradictory evidence and
unsupported scientific interpretations remain uncertain unless a pinned
criterion and an actual independent check cover them.

The controlled tests establish host projection, binding, refusal and failure
handling only. They are not live-model evaluations, calibration receipts,
production qualification or evidence of reviewer accuracy. Any campaign
results must keep provider failures separate from semantic `FAIL` or
`INCONCLUSIVE` findings and must identify the exact new CC/profile pins.
