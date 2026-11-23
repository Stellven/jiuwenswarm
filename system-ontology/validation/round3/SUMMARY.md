# Node types draft 0.3: independent checks, round3

44 types, 329 choices. Marks from `validation/criteria.yaml`; the last column says when each was set and how its reading changed.

| Check | Result | Mark | | When the mark was set |
|---|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 231/240 = 96.2% | at least 90% | met | set 2026-11-16 |
| Decisions plainly covered by a choice; 40 decisions the checkers called engine-specific are left out of the denominator | 485/702 = 69.1% | at least 80% | FAIL (not met) | set 2026-11-16 |
| Decisions covered only loosely | 156/702 = 22.2% | no mark |  |  |
| Decisions not covered | 61/702 = 8.7% | at most 5% | FAIL (not met) | set 2026-11-16 |
| Claims an engine contradicts | 41 | at most 0 | FAIL (not met) | set 2026-11-16 |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 0 | no mark |  |  |
| Parts assigned to the wrong type in the reference | 11 | no mark |  |  |

## Per engine

| | ds4 | hyperqwen | ninfer | splash | strata |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 113 | 111 | 104 | 133 | 241 |
| Plainly covered | 67.3% | 63.1% | 66.3% | 57.1% | 80.5% |
| Not covered | 10.6% | 8.1% | 12.5% | 13.5% | 3.7% |
| Contradicted claims | 4 | 10 | 8 | 7 | 12 |
| Unnamed causes at a listed level | 0 | 0 | 0 | 0 | 0 |
| Relaxed `should` rules not yet noted | 1 | 1 | 2 | 1 | 3 |
| Inventory entries the source corrects | 4 | 2 | 4 | 2 | 5 |
| Jobs no type describes | 0 | 0 | 0 | 0 | 0 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 211 | 29 | 0 |
| rater-b | 195 | 45 | 0 |

