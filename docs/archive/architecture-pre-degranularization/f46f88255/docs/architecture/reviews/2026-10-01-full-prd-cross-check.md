---
type: review
status: processed
tags: [review, prd, cross-check]
---

# Fresh-context cross-check: full M1 PRD, 2026-10-01

An independent reviewer read the verbatim full PRD and the current architecture pages without inherited task context. Findings were verified against the cited PRD clauses before being recorded here. This was a PRD cross-check, not the complete area-loop review; the current review process is model-agnostic and documented in [PROCESS](../PROCESS.md).

## Readings 40–44

| Item | Source check | Disposition |
|---|---|---|
| 40: restricted runner account and fixture access | PRD 5.2.1 and 5.4.3 call for a restricted execution identity, but 4.4.9 explicitly describes fixture isolation without root privileges for separate OS accounts. A `jiuwen-runner` UID and owner-only fixture directory are plausible, but installer `sudo` and the pipe-based oracle are not established by the PRD. A separate UID also does not itself prevent network or other system effects required by 2.9. | Keep as a proposal requiring owner confirmation and a complete security-boundary design. Blocks generated-code execution and RSI fixture execution, not Screening. |
| 41: Brief metrics flow into the blueprint | This reconciles the threshold-source passages only if the design preserves three distinct values: the Brief acceptance target (3.2.6), the claim's expected effect (3.5.1), and the falsification boundary (3.5.4). Mixed units, comparators, or metrics still need defined semantics. | Revise the reading to require all three roles and an explicit comparison rule. Blocks hypothesis/evaluation contracts, not Screening. |
| 42: capsule execution | 4.1.4 supports one CC runner for every capsule call; 4.9 describes the Builder separately and incompletely accounts for 3.7. The reading is coherent if the runner executes the 3.6/3.7 capsules while generated benchmark code runs inside a separate restricted execution boundary. | Retain as a proposed role clarification, not a claim that the CC runner itself is a sandbox. Blocks 3.6/3.7 integration pending confirmation. |
| 43: local wheelhouse | 3.6.1 prohibits runtime package installation during POC preparation, while 3.7.1 requires `pip install`. A no-network wheelhouse can reconcile these statements, but provisioning, build-code handling, and artifact-versus-environment failure ownership are architecture proposals. | Retain as a proposed resolution requiring confirmation and bounded provisioning design. Blocks 3.6/3.7 execution only. |
| 44: scientific classification | 3.8.4 requires deterministic comparison and 3.8.5 lists four labels, but does not define the mapping. The proposal must state units/statistics/repeats and how incomplete evidence and validity anomalies affect classification. Scientific `INCONCLUSIVE` must remain distinct from gate `INCONCLUSIVE`; a valid scientific classification proceeds to Delivery when its gate passes. | Keep provisional pending metric semantics and Ramika's classification decision. Blocks hypothesis/evaluation contracts, not Screening. |

## Screening contract findings

| Finding | Source | Disposition |
|---|---|---|
| Scoring scope is ambiguous. 3.4.5's definition includes evidence maturity and a credible verification path, but its whitelist defines scores only for novelty, feasibility, and compute alignment. | PRD 3.4.5, lines 673–680 | Keep exactly three numerical scores as the known contract. Ask whether the two additional qualities are qualitative context or scored dimensions; keep the rubric provisional until answered. |
| Novelty's comparison set is unclear. The PRD says compare with baseline approaches cited in the Brief, but the current Brief type has no literature-citation field; evidence citations live in `idea_set`. | PRD 3.4.5, line 677; `research-brief.md`; `idea-set.md` | Record an owner question before freezing the novelty rubric. |
| The strategic filter has no deterministic data source. A fixed registry and its owner/update policy are absent. | PRD 3.4.6, lines 685–690 | Keep the filter interface provisional and record the policy-data owner question. |
| Ranking can tie; no stable tie-break is specified. | PRD 3.4.7, lines 692–698 | Architecture decision: order by composite score descending, then by the lexicographically ordered source `idea_ids` tuple. Select the first eligible candidate in that order. |
| The PRD gives no result when the filter excludes all candidates. | PRD 3.4.6–3.4.7, lines 685–702 | Architecture decision: do not fabricate a winner; emit the declared `NO_ELIGIBLE_OPPORTUNITY` capsule failure and no `opportunity_card` Artifact. |
| Capsule kind conflicts with RSI workstream material. The M1 RSI PRD calls Screening a `skill`, while a work capsule that invokes the `rank_opportunities` operator must be a `tool` under CC's call rules. | M1 RSI PRD; CC capsule kind rules; current `m1/order.md` | Keep Screening as `tool`; record an interface/ownership question for adapting the RSI prompt-mutation target to a tool capsule. |
| Strategic filter scope differs between definition and whitelist. The definition names several screening dimensions, while the explicit M1 whitelist calls for a deterministic dependency-conflict filter. | PRD 3.4.6, lines 685–690 | Keep the deterministic dependency filter as the only defined eligibility rule and ask the PRD owner whether the other dimensions are card context or additional decisions; do not silently add filters. |

The readings do not block the Screening contract work. Screening remains `blackbox` while its domain rubric and deterministic filter input are unresolved.

## Fresh area review and dispositions (2026-10-01)

A separate fresh-context reviewer checked the Screening pages against PRD 3.4/4.1 and the shared CC contracts. I verified each finding against the PRD and owning pages before applying it.

| Finding | Source check | Disposition |
|---|---|---|
| The gate did not explicitly judge evidence maturity or verification credibility. | PRD 3.4.5 names both qualities; `screening-gate.md` previously assessed grounding and brief fit only. | Add both as qualitative judgments in the two gate rubrics; keep numeric scoring treatment open in issue 48. |
| The lexicographic tie-break can decide a product-visible Top-1 winner but is not in the PRD. | PRD 3.4.7 requires ranked Top-1, without a tie rule. | Retain as a provisional deterministic proposal and ask the owner to accept or replace it (issue 52). |
| Selected-card dependencies/resources may need to reach Hypothesis. | PRD 3.4.6 names dependencies and resource implications; Hypothesis consumes the card. | Keep type changes open until product owner decides which context must flow downstream (issue 51). |
| All-candidates-excluded behavior is not stated by the PRD. | PRD 3.4.6–3.4.7 specifies a conflict filter and Top-1 but no empty-eligible case. | Keep `NO_ELIGIBLE_OPPORTUNITY` as a provisional failure proposal; request owner confirmation (issue 53). |
