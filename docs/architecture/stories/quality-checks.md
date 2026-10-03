# Story quality checks

This document records architectural walkthrough findings and documentation checks for the [stories](README.md). The base package is commit 2aa0b90b1; its [checkpoint](../handoff-checkpoint-2026-10-03.json) describes that historical snapshot. Current owner corrections below supersede the affected prose, not the frozen PRD or its original hashes. Product code and Spec Kit are outside this work.

## Findings and corrections

| Finding | Correction | Affected contract and recheck |
|---|---|---|
| Screening began with an RSI table row in place of its opening front-matter delimiter | Restore the delimiter; add a lint guard requiring active M1 pages to start with metadata | Screening and generated graph |
| Screening prompt brief and issue 50 still said the helper could not mutate, contrary to frozen RSI scope and the page's Declaration | Mark old issue 50 superseded by R4; state required isolated helper implementation optimization preserving exact outcomes, with separate conditional text sessions | Screening, ranking, RSI and decision ledger; story 2/6 |
| Experimental spatial flow unconditionally led to real Gate/release although approved Gate ablations have another authority | Label ordinary governed branch and add the NOT_RUN/PARTIAL evidence and experimental advance branch | Experiment diagram, existing evidence/advance schema and story 7 |
| Module-map status still claimed connected review was pending | Link completed review while retaining draft status pending Muk approval | Module map and story destinations |
| Fresh reviewer found the RSI story omitted its explicit baseline query | Add evaluate(purpose=baseline, parent TrialRef) before proposals; distinguish preflight headroom from loop query reservation | Story 6, engine/oracle sequence |
| Fresh reviewer found “repeated final denied” conflated exact duplicate replay with another evaluation | Exact identical request returns committed status/result; early/new second final evaluation is denied | Story 6, oracle duplicate contract |

These are consistency corrections to adopted contracts. They add no runtime scope or new product behavior. The narratives point to owners rather than defining new payload schemas.

## Mechanical and independent review evidence

Executed from the repository root on October 3:

| Command | Observed documentation result |
|---|---|
| `python docs/architecture/_tools/validate_stories.py` | 118 checks pass: complete scientific payload shapes, missing/unknown fields, independent Decimal/predicate expectations, Screening rank/tie/filter example, production capability/input connections, destination references and M1 metadata |
| `python docs/architecture/_tools/arch_lint.py` then `--check` | Generation and architecture link/schema/metadata/graph checks pass; malformed leading M1 metadata now fails lint |
| `python docs/architecture/_tools/validate_services.py` | 419 service-schema cases pass |
| `python docs/architecture/_tools/validate_handoff.py` | 20 frozen hashes match; eight independent input contracts and 18 producer/consumer joins agree; RSI admission seam agrees; 131 generated payload cases pass |
| `git diff --check` and staged equivalent | No introduced whitespace errors |

Fresh reviewer m1_handoff_review independently read README and stories 01–08 against the owning contracts. It found the two RSI sequence/replay issues above, then reread the actual corrections and closed both. No remaining concrete discrepancy was found in that reviewed packet. The reviewer did not execute the numerical tooling; the results above were executed by the author. This is a bounded review, not exhaustive proof.

No product execution is implied. The checker covers complete schema-shaped scientific fixtures and deliberately limited independent arithmetic expectations; it does not implement the general product classifier. Story excerpts with short labels are explanatory projections, not valid request bodies or record refs. Fixture hashes are placeholders; record existence, source-reference membership and actual process/HTTP behavior are not tested by these checks.

## Downstream observations

Builders should turn each story's injection point into actual integrated fixtures: count successor invocations, inspect committed records/capture, verify exact model/profile and namespace identities, test process/access boundaries and record observed HTTP/status behavior. Use the [case index](../system/boundary-cases.md) for additional variants beyond these eight connected narratives. Finite walkthrough coverage is not proof that every possible defect has been excluded.
