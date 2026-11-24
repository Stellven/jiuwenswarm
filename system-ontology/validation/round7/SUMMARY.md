# Node types draft 0.7: independent checks, round7

44 types, 502 choices. Marks from `validation/criteria.yaml`; the last column says when each was set and how its reading changed.

| Check | Result | Mark | | When the mark was set |
|---|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 239/240 = 99.6% | at least 90% | met | set 2026-11-16 |
| Decisions plainly covered by a choice; 28 decisions the checkers called engine-specific are left out of the denominator | 664/716 = 92.7% | at least 80% | met | set 2026-11-16 |
| Decisions covered only loosely | 49/716 = 6.8% | no mark |  |  |
| Decisions not covered | 3/716 = 0.4% | at most 5% | met | set 2026-11-16 |
| Claims an engine contradicts | 5 | at most 0 | FAIL (not met) | set 2026-11-16; read differently from draft 0.6 on, after results were seen (`claims_note_2026_11_16`); read differently from draft 0.7 on, after results were seen (`claims_note_2026_11_16_second`) |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 23 | no mark |  |  |
| Parts assigned to the wrong type in the reference | 3 | no mark |  |  |

## Per engine

| | ds4 | hyperqwen | ninfer | splash | strata |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 115 | 115 | 104 | 134 | 248 |
| Plainly covered | 92.2% | 89.6% | 91.3% | 94.0% | 94.4% |
| Not covered | 0.9% | 0% | 1.0% | 0% | 0.4% |
| Contradicted claims | 1 | 0 | 0 | 2 | 2 |
| Unnamed causes at a listed level | 2 | 5 | 3 | 7 | 6 |
| Relaxed `should` rules not yet noted | 1 | 1 | 0 | 2 | 2 |
| Inventory entries the source corrects | 1 | 1 | 0 | 1 | 6 |
| Jobs no type describes | 0 | 0 | 0 | 0 | 0 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 220 | 20 | 0 |
| rater-b | 220 | 20 | 0 |

