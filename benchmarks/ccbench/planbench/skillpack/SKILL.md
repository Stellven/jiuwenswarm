---
name: available-capabilities
description: The tools and skills available in this session, with what each does and where to read more. Use it to choose capabilities when planning.
---

# Available tools and skills

Tools are Python functions in `tools/`; skills are folders in `skills/`. Use the exact name below when naming a capability.

| Name | Kind | What it does | File |
|---|---|---|---|
| `utility.calculate` | tool | Explicit count/sum/mean/min/max on selected table columns with bounded decimal128 half-even arithmetic; no arbitrary formulas or missing-value inference | `tools/utility_calculate.py` |
| `utility.calculate_typed` | tool | calculate with independent exact JSON type preservation in addition to original value checks | `tools/utility_calculate_typed.py` |
| `utility.table_normalize` | tool | Parse an explicitly selected UTF-8 JSON/CSV file into ordered scalar rows without inference or value conversion | `tools/utility_table_normalize.py` |
| `utility.table_normalize_typed` | tool | table normalize with independent exact JSON type preservation in addition to original value checks | `tools/utility_table_normalize_typed.py` |
| `utility.markdown_report` | tool | Render explicit supplied sections and selected JSON data into an escaped Markdown artifact and digest manifest without adding research claims | `tools/utility_markdown_report.py` |
| `utility.markdown_report_typed` | tool | markdown report with independent exact JSON type preservation in addition to original value checks | `tools/utility_markdown_report_typed.py` |
| `utility.packet_report` | tool | Render explicitly selected packet content into an escaped Markdown report without adding research claims | `tools/utility_packet_report.py` |
| `utility.summary_to_packet` | skill | Deterministically preserve a structured paper summary and all source refs in a low-trust work packet | `skills/utility-summary-to-packet/SKILL.md` |
| `research.search` | skill | Runs the plan-bound queries over permitted connectors, captures exact excerpts and proposes 1 to 3 grounded ideas | `skills/research-search/SKILL.md` |
| `research.screening` | skill | Scores each candidate on three fixed dimensions, filters forbidden dependencies, ranks with a pure helper and selects one opportunity | `skills/research-screening/SKILL.md` |
| `research.hypothesis` | skill | opportunity card to frozen hypothesis blueprint | `skills/research-hypothesis/SKILL.md` |
| `research.builder` | skill | Frozen intervention implemented through bounded native Builder actions and protected compile, unit and public smoke checks; independent gate and Benchmark retain acceptance and scoring | `skills/research-builder/SKILL.md` |
| `research.benchmark` | skill | Schema-routed benchmark: classification remains the default; registered Pi requests use protected Pi scoring and baseline-first jobs | `skills/research-benchmark/SKILL.md` |
| `research.evaluation` | skill | Applies the registered rules to the benchmark measurements and records a scientific verdict with per-metric findings. | `skills/research-evaluation/SKILL.md` |
| `research.delivery` | skill | Writes the fixed-structure research report and the delivery manifest from the accepted lifecycle artifacts | `skills/research-delivery/SKILL.md` |
| `research.paper_summary` | skill | Summarize canonical PDF pages with exact source quotations and page coordinates | `skills/research-paper-summary/SKILL.md` |
| `research.paper_summary_delivery` | skill | Render accepted paper summary into Markdown and an exact evidence manifest | `skills/research-paper-summary-delivery/SKILL.md` |
| `research.generalist` | skill | Low-trust fallback for a frozen task: permitted packet files, generated artifacts and bounded pure expressions; no ambient tools or host execution | `skills/research-generalist/SKILL.md` |

The general planning skill is `skills/plan-research-workflow/SKILL.md`.
