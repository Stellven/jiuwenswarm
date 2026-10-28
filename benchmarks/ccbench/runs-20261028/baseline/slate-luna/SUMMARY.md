# Luna test slate

Model gpt-6-luna. Product commit 5db04b5037f2a20dab09bde596758ceb75d11a79 (dirty: False). Image ai4r:ccbench-native sha256:0d0941949c6655ef4b935fe23bc24e74633fb83144581d6a7c56e68ede00ce7e.
Arms: plain = model + JiuwenSwarm; careful = plain + one sentence telling it to check; cc = plain + AI4Research layer (T3 to T5 use the bench names).
Tokens come from the model usage records. A "-" is a figure that was not recorded; nothing is estimated.

## T3

| arm | runs | correct | wrong | stopped | false stop | unavailable | mean input | mean output | mean total | mean calls | mean wall s | tokens per correct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| heldout:cc | 10 | 10 | 0 | 0 | 0 | 0 | - | - | 4434 | 1.1 | 9.3 | 4434 |
| heldout:plain | 10 | 9 | 1 | 0 | 0 | 0 | - | - | 3598 | 1.0 | 7.9 | 3998 |
| heldout:selftest | 10 | 9 | 1 | 0 | 0 | 0 | - | - | 7311 | 1.2 | 11.3 | 8124 |
| heldout:verify | 10 | 9 | 1 | 0 | 0 | 0 | - | - | 4270 | 1.0 | 8.4 | 4744 |
| contract:cc | 10 | 5 | 5 | 0 | 0 | 0 | - | - | 3816 | 1.0 | 9.7 | 7631 |
| contract:plain | 10 | 6 | 4 | 0 | 0 | 0 | - | - | 4587 | 1.0 | 8.8 | 7646 |
| contract:verify | 10 | 2 | 8 | 0 | 0 | 0 | - | - | 2247 | 1.0 | 7.7 | 11235 |

## T4

| arm | runs | correct | wrong | stopped | false stop | unavailable | mean input | mean output | mean total | mean calls | mean wall s | tokens per correct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| haltbench:cc | 10 | 3 | 2 | 5 | 0 | 0 | - | - | 3441 | 1.6 | 12.5 | 11469 |
| haltbench:plain | 10 | 2 | 4 | 4 | 0 | 0 | - | - | 2440 | 1.0 | 7.0 | 12201 |
| haltbench:verify | 10 | 4 | 2 | 4 | 0 | 0 | - | - | 3653 | 1.0 | 6.5 | 9132 |

## T5

| arm | runs | correct | wrong | stopped | false stop | unavailable | mean input | mean output | mean total | mean calls | mean wall s | tokens per correct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_declared | 12 | 7 | 5 | 0 | 0 | 0 | - | - | 106029 | 1.0 | 12.3 | 181764 |
| B_skill_full | 12 | 7 | 5 | 0 | 0 | 0 | - | - | 8031 | 1.0 | 10.1 | 13767 |

