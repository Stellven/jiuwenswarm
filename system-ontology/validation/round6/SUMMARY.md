# Node types draft 0.6: independent checks, round6

44 types, 500 choices. Marks from `validation/criteria.yaml`; the last column says when each was set and how its reading changed.

| Check | Result | Mark | | When the mark was set |
|---|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 238/240 = 99.2% | at least 90% | met | set 2026-11-16 |
| Decisions plainly covered by a choice; 29 decisions the checkers called engine-specific are left out of the denominator | 660/715 = 92.3% | at least 80% | met | set 2026-11-16 |
| Decisions covered only loosely | 53/715 = 7.4% | no mark |  |  |
| Decisions not covered | 2/715 = 0.3% | at most 5% | met | set 2026-11-16 |
| Claims an engine contradicts | 15 | at most 0 | FAIL (not met) | set 2026-11-16; read differently from draft 0.6 on, after results were seen (`claims_note_2026_11_16`) |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 14 | no mark |  |  |
| Parts assigned to the wrong type in the reference | 0 | no mark |  |  |

## Per engine

| | ds4 | hyperqwen | ninfer | splash | strata |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 115 | 116 | 104 | 134 | 246 |
| Plainly covered | 90.4% | 90.5% | 92.3% | 89.6% | 95.5% |
| Not covered | 0% | 0% | 0% | 0.7% | 0.4% |
| Contradicted claims | 0 | 3 | 6 | 3 | 3 |
| Unnamed causes at a listed level | 4 | 3 | 2 | 2 | 3 |
| Relaxed `should` rules not yet noted | 1 | 0 | 1 | 0 | 0 |
| Inventory entries the source corrects | 5 | 0 | 1 | 3 | 4 |
| Jobs no type describes | 0 | 0 | 0 | 0 | 0 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 224 | 16 | 0 |
| rater-b | 205 | 35 | 0 |

