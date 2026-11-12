# Repair from evidence

Adapted from siminfeng/c2/skills/engine-ab-experiment/SKILL.md, c2/METHODS.md
and c2/MEASUREMENT-GAPS.md. The old static spec/jobq driver instructions are
superseded by the factory decision/evidence and builder/lab interfaces.

Read the actual rejection: evidence.query returns bounded summaries/cursor;
evidence.read(id) returns the record or artifact preview. Follow the source
artifact ids. Do not diagnose from an arm name, submission acknowledgement,
missing metric interpreted as zero, or an old success. Preserve failed evidence.

Form a falsifiable hypothesis with uncertainty and expected discriminating
evidence. Reconsider any assumption contradicted by evidence: in particular,
requested K is not proof of effective K, a switch regex is not a value check,
and thread names do not establish quality or speed. Change exactly one thing
per repair. Record a new decision using expected_rev, evidence_ids and a
reason_for_change citing those evidence ids before the next bounded action.
A stale revision requires rereading the current decision, not overwriting it.

Never edit a scored contract. A changed contract needs a new revision and a
new comparable run set; it cannot repair an existing scored result. Keep
prompt/model/greedy/offload/context identities and baseline fixed. Distinguish
CPU config probes, activation evidence, byte-identical output correctness,
full-engine performance, simulation, and negative/null results. An absent
measurement has an unavailable reason; do not fabricate it. Sampled telemetry
has phase/window and contamination limits (MEASUREMENT-GAPS §§2–6).

Stop on exhausted task budget/deadline, authority or ownership uncertainty,
unsafe headroom, immutable-contract conflict, repeated rejection with no new
hypothesis, missing required evidence, or the decision's explicit stop condition.
Cancel only owned attempts/containers. Publish the stop reason and remaining
uncertainty. Never widen grants, force a patch, change the baseline to get a
win, or silently retry under the same evidence identity.
