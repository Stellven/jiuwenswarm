---
name: expert-weight-streaming
description: Build a pinned CPU expert-weight integration with independently gated hardware admission.
---

Read METHOD.md. Call native capabilities with an `inputs` JSON object. Material reads and call receipts use the existing CC v2 Host, including sealed release identities. No capability launches an engine or grants hardware authority.

Use Friday JiuwenSwarm/Codex native discovery on this package root. Compose with the existing source_workbench, Builder and Lab Manager. Use task-owned source writes with expected hashes and localcommit at expected HEAD only when authorized. Retain both release identities, source/tree and patch digests, build/image identity and independent lab receipts. Use a self-contained task-owned Git clone with its own .git directory; a linked worktree is rejected by source_workbench. Spark Builder now supports build_target=llama-server with dependency pinned to the same source (embedded ggml). Lab uses the independently pinned llama-server-v1 contract. Stock qualification and hardware admission remain separate gates. Do not launch through another scheduler or treat the authored checks as acceptance. CC 3 remains pending profile evidence.
