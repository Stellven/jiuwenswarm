# Offline RSI produces an inactive candidate

## Starting item

The offline controller targets the permitted isolated ranking-helper implementation. Parent/library/policy/model/config, mutation paths, dev fixtures and evaluator/profile pins are frozen. A later mainline Candidate is possible only when that parent's evolution/admission policy permits it; an RSI-forbidden parent yields isolated evidence only. This story assumes the allowed parent.

`cc/rsi/session.py` allocates controller session S1 and commits the private parent TrialRef before `cc/security/oracle.py` begins its separately identified oracle session. The oracle privately selects disjoint loop/final sets of at least 20 fixtures each and verifies required parent headroom. Neither the proposer nor an ordinary run/export receives those cases or expected answers.

## The connected sequence

| Order | Code and API boundary | Evidence and authority |
|---|---|---|
| 1 | Controller → oracle begin_session | Exact parent TrialRef and frozen pins; private session and lifetime policy |
| 2 | Controller → evaluate(purpose=baseline, parent TrialRef) | Reserve the first loop query and commit baseline aggregate evidence; session headroom preflight does not replace this query |
| 3 | Controller → protected proposer model | rsi_controller scoped call; private prompt/reply capture, no hidden data |
| 4 | `cc/rsi/attempts.py` → visible hard checks | One permitted helper edit; rejected schema/policy/check changes stop before hidden query |
| 5 | Controller → private Trial publication | Exact child files and visible/parent-suite evidence; no public Candidate yet |
| 6 | Controller → evaluate(purpose=proposal) | Oracle reserves quota durably, then runs incumbent/child in fresh confined children |
| 7 | Oracle → controller aggregate result | Private paired outcomes produce wins/losses/ties and disposition; no per-case vectors |
| 8 | Controller → close_session | Seal best incumbent, accepted lineage and zero-to-five ablation trials; proposals close permanently |
| 9 | Controller → scheduled ablation evaluations → finish_close | Complete only the fixed schedule; commit closed evidence before final |
| 10 | Custodian → evaluate_final | One final comparison of best child against original parent; proposer gets no final optimization feedback |
| 11 | `cc/rsi/submit.py` → submit_rsi | Only promotable exact sealed trial becomes public Candidate with allowed files/visible evidence |
| 12 | `cc/admission.py` → AdmissionProvider | Tested or developer-selected Puppet admission, mandatory integrity first; admitted_inactive |
| 13 | Authenticated human → librarian activate | Attributable activation record with expected parent hash; affects future snapshots only |

One baseline query, at most 23 proposal queries and up to five ablations fit within 30 loop queries, leaving one loop reservation unused. Final evaluation has its own once/session reservation. The immutable loop-set lifetime limit is 90; restart/copying a session cannot reset it.

## Example score and library boundary

Illustrative loop result: wins=2, losses=0, ties=18 permits keeping the child if all hard checks pass. Illustrative final result: wins=5, losses=0, ties=15 meets the zero-loss and fifth-percentile Beta(6,1)>0.5 rule. These are expected aggregate inputs, not observed optimization results. Model-backed fixture arms pass only when all three repeated calls pass; deterministic cases use one call.

Puppet admission can grant only honest exempt status from the pinned developer allowlist. It cannot call this candidate certified, invent suites, activate it or manufacture runtime Verification. Active R1 remains pinned to its old Binding even after a later manual alias activation.

## Interrupted or forbidden paths

Crash after query reservation consumes that reservation; a duplicate reads status/evidence and never silently re-executes. Missing closing results block finish_close. Early final or a new request for a second final evaluation is denied; an exact duplicate final request returns its committed status/result without another evaluation. The 31st session or 91st lifetime loop query is denied. A frozen-path change is rejected before a hidden query. Security violation creates the oracle's durable target-wide latch; only authenticated human clearance with remediation and a current boundary report permits separately requested continuation. No Candidate is published for no_candidate.

[RSI engine](../capsule/rsi-engine.md), [oracle](../capsule/fixture-oracle.md), [records](../system/records.md), [admission](../capsule/admission.md) and [library](../capsule/library.md) own the separate contracts. Hidden captures remain private after every transition.
