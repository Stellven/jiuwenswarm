| arm | units | case pass | test pass | first-attempt pass | retry rate | rescued | broken | calls | tokens | wall s | same outcome across reps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| plain | 10 | 0.900 | 0.986 | 0.900 | 0.00 | 0 | 0 | 10 | 35980 | 79.5 | None |
| verify | 10 | 0.900 | 0.986 | 0.900 | 0.00 | 0 | 0 | 10 | 42698 | 84.1 | None |
| selftest | 10 | 0.900 | 0.973 | 0.900 | 0.20 | 0 | 0 | 12 | 73113 | 113.3 | None |
| cc | 10 | 1.000 | 1.000 | 0.900 | 0.10 | 1 | 0 | 11 | 44341 | 92.9 | None |

cc vs plain: pairs=10 cc_only_pass=1 plain_only_pass=0
cc vs verify: pairs=10 cc_only_pass=1 verify_only_pass=0
cc vs selftest: pairs=10 cc_only_pass=1 selftest_only_pass=0
