# Node types draft 0.2: independent checks, round2

40 types, 185 choices. Marks from `validation/criteria.yaml`; the last column says when each was set and how its reading changed.

| Check | Result | Mark | | When the mark was set |
|---|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 231/240 = 96.2% | at least 90% | met | set 2026-11-16 |
| Decisions plainly covered by a choice; 66 decisions the checkers called engine-specific are left out of the denominator | 366/676 = 54.1% | at least 80% | FAIL (not met) | set 2026-11-16 |
| Decisions covered only loosely | 146/676 = 21.6% | no mark |  |  |
| Decisions not covered | 164/676 = 24.3% | at most 5% | FAIL (not met) | set 2026-11-16 |
| Claims an engine contradicts | 74 | at most 0 | FAIL (not met) | set 2026-11-16 |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 0 | no mark |  |  |
| Parts assigned to the wrong type in the reference | 12 | no mark |  |  |

## The files contradict themselves

- ds4: totals say 15 loosely, and 0 are listed (the round lists none)
- hyperqwen: totals say 33 loosely, and 0 are listed (the round lists none)
- ninfer: totals say 21 loosely, and 0 are listed (the round lists none)
- splash: totals say 39 loosely, and 0 are listed (the round lists none)
- strata: totals say 38 loosely, and 0 are listed (the round lists none)

## Per engine

| | ds4 | hyperqwen | ninfer | splash | strata |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 103 | 108 | 102 | 127 | 236 |
| Plainly covered | 57.3% | 38.9% | 57.8% | 50.4% | 60.2% |
| Not covered | 28.2% | 30.6% | 21.6% | 18.9% | 23.7% |
| Contradicted claims | 16 | 14 | 13 | 9 | 22 |
| Unnamed causes at a listed level | 0 | 0 | 0 | 0 | 0 |
| Relaxed `should` rules not yet noted | 0 | 0 | 0 | 0 | 0 |
| Inventory entries the source corrects | 0 | 0 | 0 | 0 | 0 |
| Jobs no type describes | 0 | 0 | 0 | 0 | 0 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 196 | 44 | 0 |
| rater-b | 189 | 50 | 1 |

