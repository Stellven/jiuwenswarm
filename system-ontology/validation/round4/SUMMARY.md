# Node types draft 0.4: independent checks, round4

44 types, 486 choices. Marks from `validation/criteria.yaml`; the last column says when each was set and how its reading changed.

| Check | Result | Mark | | When the mark was set |
|---|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 237/240 = 98.8% | at least 90% | met | set 2026-11-16 |
| Decisions plainly covered by a choice; 28 decisions the checkers called engine-specific are left out of the denominator | 635/715 = 88.8% | at least 80% | met | set 2026-11-16 |
| Decisions covered only loosely | 70/715 = 9.8% | no mark |  |  |
| Decisions not covered | 10/715 = 1.4% | at most 5% | met | set 2026-11-16 |
| Claims an engine contradicts | 23 | at most 0 | FAIL (not met) | set 2026-11-16 |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 0 | no mark |  |  |
| Parts assigned to the wrong type in the reference | 3 | no mark |  |  |

## Per engine

| | ds4 | hyperqwen | ninfer | splash | strata |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 116 | 115 | 104 | 134 | 246 |
| Plainly covered | 88.8% | 80% | 90.4% | 86.6% | 93.5% |
| Not covered | 0.9% | 3.5% | 1.0% | 2.2% | 0.4% |
| Contradicted claims | 7 | 4 | 7 | 2 | 3 |
| Unnamed causes at a listed level | 0 | 0 | 0 | 0 | 0 |
| Relaxed `should` rules not yet noted | 0 | 1 | 0 | 0 | 0 |
| Inventory entries the source corrects | 1 | 1 | 3 | 2 | 4 |
| Jobs no type describes | 0 | 0 | 0 | 0 | 0 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 220 | 20 | 0 |
| rater-b | 207 | 33 | 0 |

