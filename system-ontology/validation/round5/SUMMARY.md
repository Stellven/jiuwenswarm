# Node types draft 0.5: independent checks, round5

44 types, 496 choices. Marks from `validation/criteria.yaml`; the last column says when each was set and how its reading changed.

| Check | Result | Mark | | When the mark was set |
|---|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 236/240 = 98.3% | at least 90% | met | set 2026-11-16 |
| Decisions plainly covered by a choice; 29 decisions the checkers called engine-specific are left out of the denominator | 647/715 = 90.5% | at least 80% | met | set 2026-11-16 |
| Decisions covered only loosely | 64/715 = 9.0% | no mark |  |  |
| Decisions not covered | 4/715 = 0.6% | at most 5% | met | set 2026-11-16 |
| Claims an engine contradicts | 17 | at most 0 | FAIL (not met) | set 2026-11-16 |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 0 | no mark |  |  |
| Parts assigned to the wrong type in the reference | 2 | no mark |  |  |

## Per engine

| | ds4 | hyperqwen | ninfer | splash | strata |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 115 | 115 | 104 | 134 | 247 |
| Plainly covered | 89.6% | 88.7% | 94.2% | 84.3% | 93.5% |
| Not covered | 0% | 1.7% | 0% | 1.5% | 0% |
| Contradicted claims | 5 | 1 | 3 | 5 | 3 |
| Unnamed causes at a listed level | 0 | 0 | 0 | 0 | 0 |
| Relaxed `should` rules not yet noted | 0 | 0 | 1 | 0 | 0 |
| Inventory entries the source corrects | 2 | 0 | 2 | 2 | 2 |
| Jobs no type describes | 0 | 0 | 0 | 0 | 0 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 225 | 15 | 0 |
| rater-b | 206 | 34 | 0 |

