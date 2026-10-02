# Product requirements

The PRD and its per-workstream sections, gathered in one place. Each file is a verbatim copy; the owner's own version wins when they differ. Architecture reads these and never edits them: see [what architecture covers](../architecture/architecture.md).

| File | What it is | Owner | Copied from |
|---|---|---|---|
| [prd-m1-full-2026-10-01.txt](prd-m1-full-2026-10-01.txt) | the full M1 System PRD, sections 1 to 6; supersedes the section 3 checkpoint ([architecture review](../architecture/prd/prd-m1-full-review.md)) | Ramika | Discord ("PRD - Full.txt"), 2026-10-01 |
| [prd-m1-section3.md](prd-m1-section3.md) | M1 System PRD, section 3: the main workflow pipeline (3.0 to 3.9), checkpoint | Ramika | Discord, 2026-09-29 |
| [prd-m1-initial-2026-09-28.txt](prd-m1-initial-2026-09-28.txt) | the first M1 PRD draft | Ramika | 2026-09-28 |
| [prd-kickoff-messages.md](prd-kickoff-messages.md) | kickoff messages that update the PRD | Ramika | Discord |
| [FeaturesList_PRD_AI4RESEARCH - Ramika.txt](FeaturesList_PRD_AI4RESEARCH%20-%20Ramika.txt) | the feature list behind the PRD template | Ramika | 2026-09-28 |
| [prd-m1-data-foundation.md](prd-m1-data-foundation.md) | Data Foundation for capsules: run evidence, run records, scorecard, sample run export | Suraj | `tundle`, 2026-09-29 |
| [prd-m1-model-routing.txt](prd-m1-model-routing.txt) | 3.X Foundational Models and Routing | Model Routing | `tundle`, 2026-09-29 |
| [model_router_design_en.md](../architecture/model_router_design_en.md) | the Model Routing team's technical design, v1.4, unchanged ([made consistent](../architecture/model-routing/README.md)) | Model Routing | 2026-10-01 |
| [prd-m1-rsi.txt](prd-m1-rsi.txt) | 3.Y RSI, short version | Saurav | `tundle`, 2026-09-29 |
| [prd-m1-rsi-full.md](prd-m1-rsi-full.md) | 3.Y RSI, full version with reasons | Saurav | `tundle`, 2026-09-29 |
| [prd-m1-verifier.txt](prd-m1-verifier.txt) | 3.V Evaluator Gate and Benchmarking; most M1 scope still to fill in | Ramika | `tundle`, 2026-09-29 |

## Upstream design inputs

| File | Source / version | Use |
|---|---|---|
| [report-writer-upstream-2026-10-01.md](report-writer-upstream-2026-10-01.md) | Verbatim sciencediscovery skills/report-writer/SKILL.md at cee1974d463136aa611234e3f8a915a7dc57ae88 | PRD 3.9 static report template; architecture adaptation lives in [Delivery](../architecture/m1/delivery.md) |

Where each workstream's interfaces meet Capability Capsule: [seams](../architecture/seams.md).
