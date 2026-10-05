# Product requirements

Supplementary discussion: [October 5 intern meeting notes](meeting-notes-2026-10-05.txt), written by Ramika De Silva and supplied by the user. Preserved verbatim; SHA-256 `4a82837c0fdf90248c829250ef79d49d239afbac4de2ccdf39f1d8ba69cf1fa8`. These notes are not a replacement frozen PRD. The user subsequently confirmed one CC per DAG node; that CC may call other CCs internally. The current architecture uses that convention.

October 5 navigation update: the prior architecture and its reviews are archived. Read the [current architecture](../architecture/README.md) for the staged POC pipeline and subsequent user decisions. Historical source manifests retain their original paths and hashes; architecture files formerly under `docs/architecture/` now live under `docs/archive/architecture-2026-10-05/`. Owner source contents are unchanged.

The PRD and owner contributions are gathered here as verbatim source material. The [frozen source set](SOURCE_FREEZE.md) and its [hash manifest](source-freeze-2026-10-02.json) define the active baseline. The frozen master PRD sets scope; owner files supply compatible domain detail; adopted architecture defines shared interfaces. Later owner revisions enter a proposed-change queue.

| File | What it is | Owner | Copied from |
|---|---|---|---|
| [prd-m1-full-2026-10-02.txt](prd-m1-full-2026-10-02.txt) | the full M1 System PRD, latest; adds three tracks, the model access gate, the run manifest and pre-registered outcome boundaries ([review](https://github.com/Stellven/jiuwenswarm/blob/a3aa887be0dc00d070497c4466f86def98d94a5c/docs/architecture/reviews/2026-10-02-router-v1.7-and-new-team-docs.md)) | Ramika | Discord ("PRD - Full (1).txt"), 2026-10-02 |
| [prd-m1-full-2026-10-01.txt](prd-m1-full-2026-10-01.txt) | the full M1 System PRD as first received; the [full-PRD review](https://github.com/Stellven/jiuwenswarm/blob/a3aa887be0dc00d070497c4466f86def98d94a5c/docs/architecture/prd/prd-m1-full-review.md) cites this copy | Ramika | Discord ("PRD - Full.txt"), 2026-10-01 |
| [prd-m1-section3.md](prd-m1-section3.md) | M1 System PRD, section 3: the main workflow pipeline (3.0 to 3.9), checkpoint | Ramika | Discord, 2026-09-29 |
| [prd-m1-initial-2026-09-28.txt](prd-m1-initial-2026-09-28.txt) | the first M1 PRD draft | Ramika | 2026-09-28 |
| [prd-kickoff-messages.md](prd-kickoff-messages.md) | kickoff messages that update the PRD | Ramika | Discord |
| [FeaturesList_PRD_AI4RESEARCH - Ramika.txt](FeaturesList_PRD_AI4RESEARCH%20-%20Ramika.txt) | the feature list behind the PRD template | Ramika | 2026-09-28 |
| [prd-m1-data-foundation.md](prd-m1-data-foundation.md) | Data Foundation for capsules: run evidence, run records, scorecard, sample run export | Suraj | `tundle`, 2026-09-29 |
| [prd-m1-model-routing.txt](prd-m1-model-routing.txt) | 3.X Foundational Models and Routing | Model Routing | `tundle`, 2026-09-29 |
| [model_router_design_en.md](../archive/architecture-2026-10-05/model_router_design_en.md) | the Model Routing team's technical design, v1.7, unchanged ([made consistent](../archive/architecture-2026-10-05/model-routing/README.md)) | Model Routing | 2026-10-02 |
| [prd-m1-rsi.txt](prd-m1-rsi.txt) | 3.Y RSI, short version | Saurav | `tundle`, 2026-09-29 |
| [prd-m1-rsi-full.md](prd-m1-rsi-full.md) | 3.Y RSI, full version with reasons; updated 2026-10-02 (query caps, violation suite, improver seams) | Saurav | Downloads, 2026-10-02 |
| [prd-m1-verifier.txt](prd-m1-verifier.txt) | 3.V Evaluator Gate and Benchmarking; most M1 scope still to fill in | Ramika | `tundle`, 2026-09-29 |

| [benchmark-experiment-design-v5-2026-10-02.md](benchmark-experiment-design-v5-2026-10-02.md) | end-of-term benchmark design v5: the four-rung ladder, router step, harness hooks | Saurav | Downloads, 2026-10-02 |
| [benchmark-guide-2026-10-02.md](benchmark-guide-2026-10-02.md) | the team's guide to v5 | Saurav | Downloads, 2026-10-02 |

## Upstream design inputs

| File | Source / version | Use |
|---|---|---|
| [report-writer-upstream-2026-10-01.md](report-writer-upstream-2026-10-01.md) | Verbatim sciencediscovery skills/report-writer/SKILL.md at cee1974d463136aa611234e3f8a915a7dc57ae88 | PRD 3.9 static report template; architecture adaptation lives in [Delivery](../archive/architecture-2026-10-05/capabilities/delivery.md) |

Where each workstream's interfaces meet Capability Capsule: [seams](../archive/architecture-2026-10-05/system/seams.md).

## Provenance

**Owner files are never edited here.** Each is a byte-for-byte copy of what the owner sent. Architecture's notes on them live elsewhere: in the [architecture reviews](https://github.com/Stellven/jiuwenswarm/tree/a3aa887be0dc00d070497c4466f86def98d94a5c/docs/architecture/reviews/), the [model routing reply](../archive/architecture-2026-10-05/model-routing/README.md) and [seams](../archive/architecture-2026-10-05/system/seams.md). When an owner sends a new version, the new file is added beside the old one, and the old one stays.

| Vault file | Received as | Received | From | SHA-256 | Replaces |
|---|---|---|---|---|---|
| [model_router_design_en.md](../archive/architecture-2026-10-05/model_router_design_en.md) | `model_router_design_en.md`, "v1.7, 2026-10-02" | 2026-10-02, Downloads | Model Routing (Xiaoyang) | `7e0a3a20cf70760757b8b138cea7f2ff6ad6b9d10b6c36219ef08caefd3e61ad` | v1.4, kept as [model_router_design_en-v1.4-2026-10-01.md](https://github.com/Stellven/jiuwenswarm/blob/a3aa887be0dc00d070497c4466f86def98d94a5c/docs/architecture/model_router_design_en-v1.4-2026-10-01.md) (`b56968442950ad673de8bb5885ac5f7d461592f41a7a6c32fa0fc63e99ed405a`; restored from commit `e025601c7`, so its line endings may differ from the file Xiaoyang sent) |
| [prd-m1-full-2026-10-02.txt](prd-m1-full-2026-10-02.txt) | `PRD - Full (1).txt` | 2026-10-02, Downloads | Ramika | `44928035205bdebae205d2b458bd438c2c6e0103e4eb2d834c6a93e1cfa37294` | none; the 10-01 copy stays |
| [prd-m1-full-2026-10-01.txt](prd-m1-full-2026-10-01.txt) | `PRD - Full.txt` | 2026-10-01, Downloads | Ramika | `2f689644ef9517378f5cf16b28fa372f011811b9f9095aa0ca6996a6a10b13d9` | none |
| [prd-m1-rsi-full.md](prd-m1-rsi-full.md) | `rsi-3y-full (2).md` (`(1)` is identical) | 2026-10-02, Downloads | RSI (Saurav) | `0e1f6430c26496b9693ff63a34feee91027ed648ffc4ce12ea33d17094bd103f` | the 09-29 copy, kept as [prd-m1-rsi-full-2026-09-29.md](prd-m1-rsi-full-2026-09-29.md) (`731b14548c67eadc62277d26167d95cf7463b2bcdaf92b7990fef5c329cd184f`; restored from commit `e025601c7`) |
| [benchmark-experiment-design-v5-2026-10-02.md](benchmark-experiment-design-v5-2026-10-02.md) | `Experiment design v5.md` | 2026-10-02, Downloads | Benchmark (Saurav) | `78e34a576c79b240d3a9df8a6f07dfaef9a83be899ab50892b4ff44bc7104a9b` | none; v1 to v4 are not in the vault |
| [benchmark-guide-2026-10-02.md](benchmark-guide-2026-10-02.md) | `Benchmark Summary.md` | 2026-10-02, Downloads | Benchmark (Saurav) | `8c412eb3800cc9d5f6e182dcbd5f1077a30bb5ee6580dc3dd876d00228ba7488` | none |

Received on 2026-10-02 and not added, because they match copies already here: `M1-technical-design-capsule-run-records.md` (same as [capsule-run-records.md](../archive/architecture-2026-10-05/data-foundation/capsule-run-records.md)), `capsule-3w-full.md`, `PRD - M1 Data Foundation`, `PRD - Model Routing_completed`. `PRD - Model Routing.txt` is the older blank template.
