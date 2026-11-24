# Node types draft 0.8: independent checks, heldout

44 types, 505 choices. Marks from `validation/criteria.yaml`; the last column says when each was set and how its reading changed.

| Check | Result | Mark | | When the mark was set |
|---|---|---|---|---|
| Blind agreement | not done |  | not done |  |
| Decisions plainly covered by a choice; 2 decisions the checkers called engine-specific are left out of the denominator | 60/119 = 50.4% | at least 80% | FAIL (not met) | set 2026-11-16 |
| Decisions covered only loosely | 29/119 = 24.4% | no mark |  |  |
| Decisions not covered | 30/119 = 25.2% | at most 5% | FAIL (not met) | set 2026-11-16 |
| Claims an engine contradicts | 6 | at most 0 | FAIL (not met) | set 2026-11-16; read differently from draft 0.6 on, after results were seen (`claims_note_2026_11_16`); read differently from draft 0.7 on, after results were seen (`claims_note_2026_11_16_second`) |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 7 | no mark |  |  |
| Parts assigned to the wrong type in the reference | 0 | no mark |  |  |
| Jobs the checker found that no type describes | 6 | no mark |  |  |
| Held-out engine, heldout-a: the reader's own fit marks (0 of 47 parts the reader flags as outside an engine left out of the denominator) | 40/47 clean = 85.1%, 0 without a type = 0% | clean at least 75%, none at most 5% | met | set 2026-11-16 |
| Held-out engine, heldout-b: the reader's own fit marks (0 of 47 parts the reader flags as outside an engine left out of the denominator) | 38/47 clean = 80.9%, 1 without a type = 2.1% | clean at least 75%, none at most 5% | met | set 2026-11-16 |
| Leave one engine out, each engine in turn (the generalisation mark applies to every fold) | one fold done: llama-cpp | every engine | not tested | set 2026-11-16 |

## Per engine

| | llama-cpp |
|---|---|
| Decisions (engine-specific excluded) | 119 |
| Plainly covered | 50.4% |
| Not covered | 25.2% |
| Contradicted claims | 6 |
| Unnamed causes at a listed level | 7 |
| Relaxed `should` rules not yet noted | 3 |
| Inventory entries the source corrects | 3 |
| Jobs no type describes | 6 |

