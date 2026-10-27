# Benchmark reports

## 27 October 2026 — matched AI4R reference and replacement local pool

[Current measured results and evidence](2026-10-27-matched-router/README.md):
both arms scored 24/24 exact-correct worker answers and 20/24 correct answers
through the gate. Automatic v8 used 18.19% fewer total reported tokens than
fixed ChatGPT inside AI4R. Verifier false blocks remain explicit. This is a
routing-component comparison, not complete workflow acceptance.

## 26 October 2026 — Hybrid model routing

[External presentation: Hybrid v5 versus all ChatGPT](2026-10-26-hybrid-router/external/benchmark-report.md)
([illustrated HTML](2026-10-26-hybrid-router/external/benchmark-report.html))
focuses on reported token use and worker-answer quality.

[Internal presentation: verifier/gate false blocks](2026-10-26-hybrid-router/internal/benchmark-report.md)
([illustrated HTML](2026-10-26-hybrid-router/internal/benchmark-report.html))
details the ten correct v5 answers that were blocked.

[External report and supporting-data ZIP](../output/AI4R_Hybrid_v5_External_Benchmark_2026-10-27.zip)
contains only the external view and its relevant v5/ChatGPT data.

The original full report is retained below.

[Open the illustrated English HTML report](2026-10-26-hybrid-router/benchmark-report.html)
or [read the Markdown report](2026-10-26-hybrid-router/benchmark-report.md).

The report compares six measured MR01 development configurations, with five
figures and a compact per-observation evidence index. These are model-routing
component results, not full AI4R workflow acceptance. Current v5 scored 21/24
exact-correct worker answers with 12.46% fewer reported tokens than the 24/24
all-ChatGPT baseline; its verifier/gate advanced only 11 correct answers.

The HTML embeds its figures and needs no web server. Full native receipts stay
on Spark; no credentials or reviewer answer files are copied into this folder.
