# Screening selects or stops

## Starting items

Search has emitted an admitted idea_set with ideas I1, I2 and I3 plus their source/chunk evidence. The Brief supplies the goal and compute constraint. These labels and scores are an illustrative ranking case, not actual LLM judgments. Different mechanisms remain separate in this case; a consolidated group would carry the sorted tuple of all represented source idea IDs.

The [Screening capsule](../m1/screening.md) receives only idea_set and research_brief through `cc/runner/pipeline.py` and the restricted tool handler. Its pinned screening.py:run wrapper makes one brokered model call returning screening_assessments, validates that internal value and invokes the ordinary helpers/rank_opportunities.py helper. The helper is not a separately admitted capsule or an independent pipeline stage.

## The local decision

| Candidate | Novelty | Feasibility | Compute alignment | Sum | Frozen dependency assessment | Rank |
|---|---|---|---|---|---|---|
| I3 | 5 | 5 | 5 | 15 | unknown required package; ineligible | 1 |
| I1 | 3 | 4 | 5 | 12 | all compatible; eligible | 2 |
| I2 | 4 | 4 | 4 | 12 | all compatible; eligible | 3 |

Each score includes its one-sentence evidence-grounded justification. The helper queries the ordinary dependency module using the registry pinned by the owner version/Binding. It retains all three rows, including I3's rejection reason. It orders descending sum, then ascending lexicographic sorted idea_ids tuple. The winner is I1, the first eligible row; “highest score” alone would choose incorrectly here.

The helper returns the full opportunity_card, not merely “I1.” Its card retains source IDs, chunk IDs, assumptions, risks, strategic context and verification path. Its scores retain ranks, dependency evidence and rationale. These shapes have one authority: [assessments](../types/screening-assessments.md) and [card](../types/opportunity-card.md).

The Python wrapper returns that card value; the single-output tool host adds the opportunity_card port name to the result frame. The registry is the canonical policy snapshot materialized as a protected read-only body file, whose hash admission/freeze verify. No registry path or extra public input is supplied by the model.

## Handoff to Hypothesis

The wrapper cannot overwrite the helper's winner with model prose. Runner validates output shape and provenance, seals raw model evidence, and asks the supervisor store to commit the card Artifact and Observation. `cc/gate.py` runs the pinned Screening profile: deterministic score/provenance/filter checks and applicable shared-verifier criteria. The supervisor commits the release before supplying the same card Ref to `research.form_hypothesis`.

Hypothesis receives the original Brief and intake alongside that card. It resolves references through the trusted store; no raw source path or entire mutable Search process is passed across the seam.

## Stop and malformed variants

- Make all three dependencies conflict/unknown: return NO_ELIGIBLE_OPPORTUNITY, no card Artifact, no Hypothesis call. Human triage sees retained failure evidence. No success-shaped empty card is invented.
- Give a score of 6, omit an input idea, duplicate its representation or cite a missing chunk: invalid assessments/output fail before release.
- Change the registry on disk after freeze: the helper uses the frozen pin or refuses corrupt/missing content; it cannot pick a new policy.
- Optimize helper code offline: exact ordering, eligibility, schema and reference outcomes remain fixed. A candidate version enters through the [RSI story](06-offline-rsi.md), never through mutation of this running call.

The [ranking owner](../m1/op-rank-opportunities.md) fixes observable order without choosing the internal sorting algorithm. The story checker independently checks this numerical ranking case; real model grounding and reference resolution remain implementation checks.
