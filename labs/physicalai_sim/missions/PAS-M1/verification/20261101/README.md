# Phase 1 verification snapshot 20261101

Byte-exact copies of the phase 1 evidence index (test plan, Reports and evidence). Failures are kept beside passes. SHA-256 per file in INDEX.json.

| File | Status | Note |
|---|---|---|
| `evidence/RUN-bench-20261101.md` | record |  |
| `evidence/RUN-cg-20261101.md` | record |  |
| `evidence/RUN-ops-20261101.md` | record |  |
| `evidence/RUN-report-20261101.md` | record |  |
| `evidence/RUN-x11-20261101.md` | record |  |
| `evidence/RUN-x14b-20261101.md` | record |  |
| `evidence/RUN-x16-rehearsal-20261101.md` | record |  |
| `evidence/x11/run2/feasibility.json` | FAIL | X1.1 run 2: model entitlement |
| `evidence/x11/run2/models-available.json` | FAIL | X1.1 run 2 |
| `evidence/x11/run1-fail-unknown-session/feasibility.json` | FAIL | X1.1 run 1: tool defect, fixed |
| `evidence/x11/run1-attempt1-static-capture-failed/start.json` | FAIL | X1.1 attempt 1: AI4R local-research capture |
| `evidence/x11/ai4r-build-measure.json` | info | AI4R image build resources |
| `evidence/x14b/agent-only.json` | PASS | X1.4 (b) |
| `evidence/x16/fresh-checkout.json` | REHEARSAL | X1.6 rehearsal, not PASS |
| `evidence/ops/doctor-runner.json` | PASS | doctor in the runner |
| `evidence/ops/port-audit-during-campaign.json` | PASS | host port audit during a run |
| `check-groups/core/result.json` | PASS | .test_logs/simlab/core/20261101T014126-ff875a |
| `check-groups/core/launch.json` | PASS | .test_logs/simlab/core/20261101T014126-ff875a |
| `check-groups/core/junit.xml` | PASS | .test_logs/simlab/core/20261101T014126-ff875a |
| `check-groups/core/source-manifest.json` | PASS | .test_logs/simlab/core/20261101T014126-ff875a |
| `check-groups/executors/result.json` | PASS | .test_logs/simlab/executors/20261101T014348-fc91d3 |
| `check-groups/executors/launch.json` | PASS | .test_logs/simlab/executors/20261101T014348-fc91d3 |
| `check-groups/executors/junit.xml` | PASS | .test_logs/simlab/executors/20261101T014348-fc91d3 |
| `check-groups/executors/source-manifest.json` | PASS | .test_logs/simlab/executors/20261101T014348-fc91d3 |
| `check-groups/benchmark/result.json` | PASS | .test_logs/simlab/benchmark/20261101T014407-bfbeb5 |
| `check-groups/benchmark/launch.json` | PASS | .test_logs/simlab/benchmark/20261101T014407-bfbeb5 |
| `check-groups/benchmark/junit.xml` | PASS | .test_logs/simlab/benchmark/20261101T014407-bfbeb5 |
| `check-groups/benchmark/source-manifest.json` | PASS | .test_logs/simlab/benchmark/20261101T014407-bfbeb5 |
| `check-groups/all/result.json` | PASS | .test_logs/simlab/all/20261101T182309-9aeaad |
| `check-groups/all/launch.json` | PASS | .test_logs/simlab/all/20261101T182309-9aeaad |
| `check-groups/all/junit.xml` | PASS | .test_logs/simlab/all/20261101T182309-9aeaad |
| `check-groups/all/source-manifest.json` | PASS | .test_logs/simlab/all/20261101T182309-9aeaad |
| `check-groups/neg-core-timeout/result.json` | NEGATIVE_CONTROL | .test_logs/simlab/core/20261101T012344-5fd352 |
| `check-groups/neg-core-timeout/launch.json` | NEGATIVE_CONTROL | .test_logs/simlab/core/20261101T012344-5fd352 |
| `check-groups/neg-core-timeout/source-manifest.json` | NEGATIVE_CONTROL | .test_logs/simlab/core/20261101T012344-5fd352 |
| `check-groups/neg-core-source-change/result.json` | NEGATIVE_CONTROL | .test_logs/simlab/core/20261101T012350-4c2581 |
| `check-groups/neg-core-source-change/launch.json` | NEGATIVE_CONTROL | .test_logs/simlab/core/20261101T012350-4c2581 |
| `check-groups/neg-core-source-change/junit.xml` | NEGATIVE_CONTROL | .test_logs/simlab/core/20261101T012350-4c2581 |
| `check-groups/neg-core-source-change/source-manifest.json` | NEGATIVE_CONTROL | .test_logs/simlab/core/20261101T012350-4c2581 |
| `check-groups/neg-executors-timeout/result.json` | NEGATIVE_CONTROL | .test_logs/simlab/executors/20261101T012652-6f9eb0 |
| `check-groups/neg-executors-timeout/launch.json` | NEGATIVE_CONTROL | .test_logs/simlab/executors/20261101T012652-6f9eb0 |
| `check-groups/neg-executors-timeout/source-manifest.json` | NEGATIVE_CONTROL | .test_logs/simlab/executors/20261101T012652-6f9eb0 |
| `check-groups/neg-executors-source-change/result.json` | NEGATIVE_CONTROL | .test_logs/simlab/executors/20261101T012659-6f980b |
| `check-groups/neg-executors-source-change/launch.json` | NEGATIVE_CONTROL | .test_logs/simlab/executors/20261101T012659-6f980b |
| `check-groups/neg-executors-source-change/junit.xml` | NEGATIVE_CONTROL | .test_logs/simlab/executors/20261101T012659-6f980b |
| `check-groups/neg-executors-source-change/source-manifest.json` | NEGATIVE_CONTROL | .test_logs/simlab/executors/20261101T012659-6f980b |
| `check-groups/neg-benchmark-timeout/result.json` | NEGATIVE_CONTROL | .test_logs/simlab/benchmark/20261101T012726-6cbdaa |
| `check-groups/neg-benchmark-timeout/launch.json` | NEGATIVE_CONTROL | .test_logs/simlab/benchmark/20261101T012726-6cbdaa |
| `check-groups/neg-benchmark-timeout/source-manifest.json` | NEGATIVE_CONTROL | .test_logs/simlab/benchmark/20261101T012726-6cbdaa |
| `check-groups/neg-benchmark-source-change/result.json` | NEGATIVE_CONTROL | .test_logs/simlab/benchmark/20261101T012732-f25680 |
| `check-groups/neg-benchmark-source-change/launch.json` | NEGATIVE_CONTROL | .test_logs/simlab/benchmark/20261101T012732-f25680 |
| `check-groups/neg-benchmark-source-change/junit.xml` | NEGATIVE_CONTROL | .test_logs/simlab/benchmark/20261101T012732-f25680 |
| `check-groups/neg-benchmark-source-change/source-manifest.json` | NEGATIVE_CONTROL | .test_logs/simlab/benchmark/20261101T012732-f25680 |
| `check-groups/dev-core-import-check-failure/result.json` | FAILED | .test_logs/simlab/core/20261031T215307-105ff7 |
| `check-groups/dev-core-import-check-failure/launch.json` | FAILED | .test_logs/simlab/core/20261031T215307-105ff7 |
| `check-groups/dev-core-import-check-failure/junit.xml` | FAILED | .test_logs/simlab/core/20261031T215307-105ff7 |
| `check-groups/dev-core-import-check-failure/source-manifest.json` | FAILED | .test_logs/simlab/core/20261031T215307-105ff7 |
| `bench/campaign-F1-F5/evidence-index.json` | record |  |
| `bench/campaign-F1-F5/family_F1.json` | record |  |
| `bench/campaign-F1-F5/family_F1.md` | record |  |
| `bench/campaign-F1-F5/family_F5.json` | record |  |
| `bench/campaign-F1-F5/family_F5.md` | record |  |
| `bench/campaign-F1-F5/profile.json` | record |  |
| `bench/campaign-F1-F5/release-check.json` | record |  |
| `bench/campaign-F1-F5/report.json` | record |  |
| `bench/campaign-F1-F5-build-df0cfd61-superseded/evidence-index.json` | record |  |
| `bench/campaign-F1-F5-build-df0cfd61-superseded/family_F1.json` | record |  |
| `bench/campaign-F1-F5-build-df0cfd61-superseded/family_F1.md` | record |  |
| `bench/campaign-F1-F5-build-df0cfd61-superseded/family_F5.json` | record |  |
| `bench/campaign-F1-F5-build-df0cfd61-superseded/family_F5.md` | record |  |
| `bench/campaign-F1-F5-build-df0cfd61-superseded/profile.json` | record |  |
| `bench/campaign-F1-F5-build-df0cfd61-superseded/release-check.json` | record |  |
| `bench/campaign-F1-F5-build-df0cfd61-superseded/report.json` | record |  |
| `bench/speed.json` | record |  |
| `bench/release-pas-m1-phase1-r1.json` | record |  |
| `compute-log.csv` | record |  |
