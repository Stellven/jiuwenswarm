---
id: activity-m1-ml-readiness-20261026
status: software-verified-live-acceptance-pending
source: Sources/Prompts/2026-10-26-reliability-ml-campaign.txt; Sources/Prompts/2026-10-26-publish-working-checkpoint.txt
last_reviewed: 2026-10-26
next_action: Rebuild from published M1, verify authenticated readiness, then run a frozen ML Builder and independent Benchmark demonstration
---
# M1 reliability and ML readiness checkpoint

Working code and retained verification were pushed to **ai4r_M1** at `ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7`. Implementation source is `a138e435fe0f6e33a0684ac0458404e3d3d1700b`; the later publication commit adds only report/evidence. The integration branch is `m1/all-features-20261025`. [Detailed report](https://github.com/Stellven/jiuwenswarm/blob/ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7/docs/research/m1-reliability-status-20261026.md) and [machine-readable receipt](https://github.com/Stellven/jiuwenswarm/blob/ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7/docs/capsules/verification-20261026/ml-readiness/summary.json).

This is a software-verified checkpoint published at the user's request before completing the live campaign. ML is now the primary demonstration; π is optional. The official benchmark and statistical study remain with their owner. No overall accuracy gain or scientific acceptance is claimed.

## Changes and extent

- Added opt-in, separately versioned evidence-aware review. The host binds selected original task/source inputs and passing Tier 1 results; each output still has its own verifier call and host gate. Historical output-only profiles remain. E2 replay explicitly rejects v2 evidence review before any model call until that replay projection is implemented.
- Fixed utility admission check names and independent-review budget allocation in four new immutable `m1-2` releases: normalizer, calculator, Markdown report and Generalist. Added `summary_to_packet m1-1` and `packet_report m1-1`, retaining exact provenance and low trust. Real admitted/bound/gated DAGs exercise summary → checked adapter → report and normalizer → calculator → report.
- Separated shared packet/runtime dependencies from mutable authoring helpers. Historical manifests retain exact old bytes. Old malformed `packet_schema` associations are not grandfathered around current `result_schema` policy; unavailable historical releases remain unavailable.
- Added Docker-only E2/E3 preparation CLI and exact-source request templates, with no acceptance authority. The CLI is fixture-tested; its complete live Compose source-production procedure is still unvalidated.
- Added root-private synthetic signal/no-signal classification task preparation. Public capture executes with permanent UID/GID 10001 and no supplementary groups. Stop the app while selecting private task labels: the quiescence check is not an atomic lock against concurrent starts. The helper creates no admission, readiness, measured improvement or acceptance.
- Added an opt-in durable 900-attempt / 10,800-second live completion budget, beginning at the first attempt and charging failures. New ML captures explicitly request `gpt-6-luna`; historical captures are preserved. OpenJiuwen remains the agent runtime and Codex remains completion-only. No API key, model router, RSI or M2 sandbox work was added.

Implementation and independent checking used user-authorized Luna agents; the supervisor reviewed changes and retained results. Review caught and removed a proposed historical-eligibility bypass. It also caught finite-scope installation/pin regressions before publication.

## Verification and reproduction

| Evidence | Result and meaning |
| --- | --- |
| Final current-release Docker selection | **319 passed**, zero failures/errors/skips, exit 0, no source changes |
| Independent fresh Git archive | **28 passed**, zero failures/errors/skips; Planner release pins passed; overlaps the selection above |
| First preflight | 254 passed / 3 failed, source changed; retained as non-passing evidence |
| Second preflight | 328 passed / 2 failed, source changed; retained as non-passing evidence |
| Historical finite-startup comparison | Parent `e1ca360c` and candidate reproduce the same two failures; parent has 11 passed / 2 failed in the exact same verification image |
| Interrupted and failed launches | One stopped check for LF portability normalization; two fresh-archive launch failures before tests; retained separately |

The replay defect rejected the new known verifier wrapper as unavailable before historical output-only review. The bounded fix retains exact implementation/store identity and restores provider-failure/rejection observations. Evidence-aware E2 does not silently fall back to output-only review.

From the integration checkout, PowerShell:

```powershell
./deploy/m1/check-capsules.ps1 -Group all -Image ai4r-verify:20261025 -Output C:/Temp/ai4r-my-fresh-check -TimeoutSeconds 900
./deploy/m1/check-capsules.ps1 -Group ml-readiness -Image ai4r-verify:20261025 -Output C:/Temp/ai4r-my-fresh-ml-check
```

Image `sha256:09979a044c9eace8e3ef17cd142eb26a27306e14ea80939c0628356eaca2e97a`; source manifest `a8b4912574f360eb69a4576029d3e1f12207c638080ddb68e9c849cfb142eaaa`. Use the Dockerfile verification target to rebuild dependencies if this image tag is absent. Compare source/image identities and exact target lists; selections overlap and counts must not be added. The launcher has no network, read-only source, resource/deadline limits and source-change detection. The retained fresh-archive receipt includes exact portable commands and release-pin verification.

## PRD V10 story matrix

| Story | Exercised mechanism | Remaining claim |
| --- | --- | --- |
| US09 POC | Native Builder loop, custody and package checks in controlled tests | No accepted live ML POC |
| US10 baseline comparison | Classification prediction protocol and independent scoring mechanics | No new measured live baseline/candidate comparison |
| US11 scientific outcome | Registered-rule recomputation and evaluation checks | No live measurement-backed scientific conclusion |
| US13 halted run | Recovery/status and provider failure versus abstention/rejection checks | Historical finite readiness/root-peer failures remain |
| US15 final report | Prior live PDF delivery, current controlled report/adapter DAGs | No new live scientific report or entailment-accuracy evaluation |
| US16 evidence retrieval | Prior archive retrieval, current source/image/JUnit/hash receipts | No live ML experiment archive |
| US17 previous results | Exact replay preparation and historical output-only replay tests | Full live E2/E3 Compose authoring/replay procedure unvalidated |

PRD source is the maintained `ai4r_muk` commit `889682f0afc3d06c2ad88e71534483a31d2eb560`, `docs/product/received-prds/prd-m1-v10-2026-10-15.txt`, SHA-256 `6d85972cdc8cf586a3d76b80d56510d695f03bfcf7838661afc7f71c35f4b3fc`. The received source and prior D20/D24 default were not rewritten; a separate opt-in review amendment records the authorized departure.

## Not yet demonstrated

**Zero live campaign completion attempts** were issued; its three-hour clock has not started. No new application image was deployed, no independently scored live ML POC/full ML journey exists, and no raw upstream comparison ran. The native diagnostic has controlled SDK tests only. Upstream JiuwenSwarm `aa8489799f2e62eae89ef608b7ec1676ede47ad7` declares SDK `0ab5913b250d565b35bff3828dae438939cb1acd`; our installed SDK is `9e3390195a9ea15235b2b5f7412cb2aa440622cc`. The diagnostic is explicitly not that upstream harness.

The current app/sign-in and old frozen runs remain intact. Rebuild from the published source before exercising new runtime code. Next steps are authenticated readiness, small isolated live reviewer cases, a frozen Builder → independent Benchmark ML run, and then one small complete ML journey. This does not mark the approved campaign complete.

## Notebook custody

Seven changed library files have byte-for-byte pre-edit `.snapshot` backups and SHA-256 receipts in `Resources/review-batches/2026-10-26-ml-readiness-campaign`. Three exact visible prompts and their hashes were captured. Validation and a scoped checkpoint are stored with that batch. Imported archives and unrelated notebook/owner-repository work are preserved. The checkpoint is scoped to this update, not a new full-vault migration.
