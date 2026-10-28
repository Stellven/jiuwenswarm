## T1 class counts

| arm | correct | correct_flagged | justified_halt | wrong_halt | flagged_wrong | silent_wrong | unavailable |
|---|---|---|---|---|---|---|---|
| plain | 5 | 2 | 0 | 0 | 0 | 1 | 0 |
| careful | 6 | 1 | 0 | 0 | 0 | 1 | 0 |
| cc | 7 | 0 | 0 | 0 | 0 | 0 | 1 |
| ccmcp | 5 | 1 | 0 | 0 | 0 | 1 | 1 |

## T1 cost

| arm | runs | correct | wrong | stopped | false stop | unavailable | mean input | mean output | mean total | mean calls | mean wall s | tokens per correct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| plain | 8 | 7 | 1 | 0 | 0 | 0 | 174050 | 366 | 174416 | 4.2 | 74.4 | 199332 |
| careful | 8 | 7 | 1 | 0 | 0 | 0 | 169406 | 518 | 169925 | 4.0 | 71.6 | 194200 |
| cc | 8 | 7 | 0 | 0 | 0 | 1 | 168699 | 320 | 169020 | 4.1 | 66.3 | 193165 |
| ccmcp | 8 | 6 | 1 | 0 | 0 | 1 | 164661 | 340 | 165002 | 3.9 | 103.7 | 220002 |
