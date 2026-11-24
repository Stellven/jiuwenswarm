---
name: kv-reuse-lab
description: Inspect exact prefix identity, reference-counted paged token storage and architecture-specific KV size estimates. Use for CPU reference experiments and planning; runtime integration requires separate engine verification.
---

Use the package's finite native capabilities with inline JSON. Read [METHOD.md](METHOD.md) for input contracts and experiment boundaries, [COMPONENT.json](COMPONENT.json) for ownership, and [SOURCES.json](SOURCES.json) for source applicability. Start with [fixtures/example.json](fixtures/example.json). Run `verify` before adapting the reference.

Keep model/tokenizer/adapter identity and full checkpoint routing fixed across exact experiments. Quantized KV and expert skipping need a separate approximate-quality contract. Package checks establish CPU invariants only; they do not create factory qualification, runtime admission, model support or measured speed claims.
