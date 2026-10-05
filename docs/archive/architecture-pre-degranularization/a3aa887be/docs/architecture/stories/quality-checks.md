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

## Second connected architecture audit

This pass follows d383c1e6e. [R13](../decisions.md#r13-connected-runtime-corrections-from-the-second-audit) records the revised choices and affected boundaries. The earlier check counts above describe the initial story pass, not this revision.

| Issue found | Resolution and ownership |
|---|---|
| Generic skill handler could not execute Screening's internal assessment-to-rank pipeline | Use the existing restricted Python tool handler and pinned screening.py:run entry, with one brokered assessment turn and local helper; preserve public name/ports/ranking rules |
| Single-port tool return was wrapped twice | Return the card value; tool host creates the named outputs map |
| Frozen dependency registry had no concrete path to the wrapper | Materialize canonical registry bytes into a protected, hash-checked body reference file; admission/freeze match the accepted epoch; no caller path or new input port |
| No-winner helper failure had no declared tool-frame representation | Existing no-winner fixture backs a single declared mode; Observation stores CAPSULE_ERROR plus NO_ELIGIBLE_OPPORTUNITY diagnostic and emits no card |
| Retry prose permitted finite/backoff attempts despite M1 no-autonomous-retry policy, and used a renamed effect class | Canonical services-v1 RetryProfile fixes zero retries for all effect classes; profile/Binding/lifecycle owners agree |
| Tool launch/timeout still specified Windows groups and a larger independent frame limit | Validated Linux namespace launcher, whole-tree reaping and pinned IPC frame limit govern tool/check execution |
| Model runtime errors could become capsule exceptions or spoofed unavailability | Failed model_result carries bridge broker_request_id/reason/message; SDK ModelUnavailable returns unavailable frame; trusted broker checks exact failed request attribution |
| Gate diagram collapsed faults into blocked and omitted two commit edges | Source-sensitive fail/environment/inconclusive paths all reach durable Verification publication |
| Mechanical nested Gate used an enum absent from Verification | Use NOT_RUN with mechanical-profile explanation; nested evidence remains governed |
| Binding-missing refusal lacked its required stage alias source | Derive stage identity from committed dispatch/parent reservation and cross-check any existing Binding |
| Malformed descriptor path minted an unreserved dispatch Observation | Entry protocol rejection retains system diagnostics without invoking runner/Gate; reserved calls retain ordinary Observation semantics |
| Observation claimed sampled spans/KV were authoritative; deployment still suggested desktop credential copying | Mandatory sealed capture and durable file commits remain authority; KV/spans are projections, dedicated container login remains custody |

Independent reviewer reread the corrected contracts and caught an additional missing identity field in the failed model_result frame. It was added, along with a targeted regression assertion. Source/body pins change for the proposed Screening implementation and the new RetryProfile definition; unchanged public payload schemas do not silently change version. Base checkpoint manifests remain historical snapshots. New coding allocations must use these revised owners and recheck their stated boundaries.

Fresh reviewer m1_handoff_review reread the corrected wrapper, registry, retry, SDK/launch and Gate contracts. It closed the identified findings, including the failed model_result identity field after checking the actual frame row. No remaining concrete blocker was found in that targeted reread. This is bounded evidence, not exhaustive approval or runtime assurance.

Executed final documentation checks: arch_lint regeneration/check passed; 428 services schema cases passed (including a nonzero-retry rejection); 134 story/interface/metadata checks passed; 131 generated payload cases passed; 20 frozen source hashes matched; eight independently derived input contracts, 18 production joins and the RSI admission seam agreed. git diff --check and staged equivalent passed. Regression assertions inspect folder-tool entry pins, protected wrapper/registry files, local versus nested helper labels, model error identity in the return frame, Gate commit edges and valid tier enum. These are static documentation/schema checks; they do not prove the proposed processes behave this way.

No proposed runtime, image, account, process confinement or stored record resolution is asserted as executed. Frozen source receipts and earlier checkpoint manifests remain unchanged.
