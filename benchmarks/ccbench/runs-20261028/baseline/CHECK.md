# CHECK: headline numbers recounted from raw score files

Written by tools/build_index.py from 287 scored rows (all-runs.csv). A "-" expected value is reported, not asserted.

| number | recounted | expected | ok |
|---|---|---|---|
| A native sol: wrong of 36 | 3 | 3 | yes |
| A native sol: correct of 36 | 33 | 33 | yes |
| A CC routes: wrong of 12 | 0 | 0 | yes |
| A native sol rep 1 only: wrong of 12 | 1 | 1 | yes |
| A native sol rep 2 only: wrong of 12 | 1 | 1 | yes |
| A native sol rep 3 only: wrong of 12 | 1 | 1 | yes |
| T1 sol low plain: wrong of 8 | 1 | 1 | yes |
| T1 sol low careful: wrong of 8 | 1 | 1 | yes |
| T1 sol low cc: wrong of 8 | 0 | 0 | yes |
| T1 sol low ccmcp: wrong of 8 | 1 | 1 | yes |
| T1 sol low plain: correct of 8 | 7 | 7 | yes |
| T1 sol low careful: correct of 8 | 7 | 7 | yes |
| T1 sol low cc: correct of 8 | 7 | 7 | yes |
| heldout cc: passed of 10 | 10 | 10 | yes |
| heldout plain: passed of 10 | 9 | 9 | yes |
| heldout verify: passed of 10 | 9 | 9 | yes |
| heldout selftest: passed of 10 | 9 | 9 | yes |
| contract cc: correct and compliant of 10 | 5 | 5 | yes |
| contract plain: correct and compliant of 10 | 6 | 6 | yes |
| contract verify: correct and compliant of 10 | 2 | 2 | yes |
| T5 declared: valid of 12 | 7 | 7 | yes |
| T5 skill_full: valid of 12 | 7 | 7 | yes |
| B ours: sessions stopped of 11 (8 faults + 3 controls) | 6 | - | yes |

## haltbench labels per arm (luna)

| arm | label | runs |
|---|---|---|
| cc | correct | 3 |
| cc | correct_stop | 5 |
| cc | wrong_value | 2 |
| plain | correct | 2 |
| plain | correct_stop | 4 |
| plain | fabricated | 1 |
| plain | wrong_value | 3 |
| verify | correct | 4 |
| verify | correct_stop | 4 |
| verify | fabricated | 1 |
| verify | wrong_value | 1 |

Result: all match
