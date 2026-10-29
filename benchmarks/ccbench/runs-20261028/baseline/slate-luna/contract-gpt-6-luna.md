| arm | units | correct+compliant | correct | compliant | field acc | first-attempt c+c | retry rate | rescued | broken | calls | tokens | wall s | identical reply across reps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| plain | 10 | 0.600 | 0.600 | 1.000 | 0.700 | 0.600 | 0.00 | 0 | 0 | 10 | 45873 | 87.9 | None |
| verify | 10 | 0.200 | 0.200 | 1.000 | 0.533 | 0.200 | 0.00 | 0 | 0 | 10 | 22470 | 77.0 | None |
| cc | 10 | 0.500 | 0.500 | 1.000 | 0.700 | 0.500 | 0.00 | 0 | 0 | 10 | 38156 | 97.0 | None |

cc vs plain: pairs=10 cc_only=1 plain_only=2
cc vs verify: pairs=10 cc_only=4 verify_only=1
