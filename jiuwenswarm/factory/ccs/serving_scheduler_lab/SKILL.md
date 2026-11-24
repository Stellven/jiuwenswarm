---
name: serving-scheduler-lab
description: Explore bounded token scheduling, chunked prefill and decode fairness with CPU traces and explicit timeline estimates. Use for CPU reference experiments and planning; runtime integration requires separate engine verification.
---

Use the package's finite native capabilities with inline JSON. Read [METHOD.md](METHOD.md) for input contracts and experiment boundaries, [COMPONENT.json](COMPONENT.json) for ownership, and [SOURCES.json](SOURCES.json) for source applicability. Start with [fixtures/example.json](fixtures/example.json). Run `verify` before adapting the reference.

Keep model/tokenizer/adapter identity and full checkpoint routing fixed across exact experiments. Quantized KV and expert skipping need a separate approximate-quality contract. Package checks establish CPU invariants only; they do not create factory qualification, runtime admission, model support or measured speed claims.
