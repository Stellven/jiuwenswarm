---
name: strata-prefill-chunk
description: Construct and evaluate one-variable native prefill-chunk candidates while preserving an admitted Strata profile.
---

Use apply with the baseline profile and chunk_tokens 256, 512 or 1024. Read METHOD.md and preserve the returned change record. The output is a candidate profile; only an operator-frozen lab contract can execute it. A fixed expert budget is preserved and requires the qualified native extension, safe admission and placement hashes.

Call coverage with frozen prompt lengths and the two chunk sizes before choosing a quality set. Short zero-shot questions may fit one chunk in both arms and miss the numerical treatment. Coverage predicts counts, not actual engagement or correctness. Use disjoint training demonstrations or a suitable long-context task when longer correctness inputs are needed.

Start with one representative prompt and numerical comparison. Use a long-prefill/short-decode workload when the hypothesis concerns prompt processing, and a short-prefill/long-decode workload to expose decode costs. Freeze source, placement, precision, routing, request IDs and resource limits; discard declared warmup requests and reverse process order. Read actual native startup chunk size to reject fallback or overrides. Report prefill and decode separately; exact-token differences and ARC answers answer different correctness questions. Attach uncertainty and choose the next bounded test instead of promoting from one fast cell.
