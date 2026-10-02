---
type: design
status: draft
version: 1
owner: muk
sources: [../types/intake.md, ../types/source-text.md, ../capsule/runner.md]
provides: [research.extract_text, research.accept_source_text]
consumes: [cc.type.intake]
depends_on: [../types/intake.md, ../types/source-text.md, ../capsule/gate-host.md]
tags: [m1, capsule, adapter, composition]
---

# `research.extract_text`: project intake to composable text

This pure adapter projects `intake.prompt` into one [`source_text`](../types/source-text.md). It exists because intent compilation consumes text semantics, not the rest of the intake package. A later planner may bind any compatible text extractor to the same compiler port.

## Declaration contract

- Kind: `tool`.
- Input: required `intake: intake`.
- Output: required `source_text: source_text`.
- Effect class/state: `pure` / `none`; no network, filesystem or model call.
- Output values: `text = intake.prompt`, `source_ref = prompt`, `source_kind = prompt`, `offset_basis = unicode_codepoint`, and `content_sha256` over the UTF-8 prompt bytes.
- Check `prompt_projection_exact` compares input/output bytes and metadata. There are no capability-specific failure modes because missing or malformed input is refused by normal port/type validation.

`research.accept_source_text` uses the common Gate API with a mechanical profile: schema, hash and exact projection checks; zero semantic criteria. This is the same gate-profile rule used by every governed step, not an exception.

## Replacement boundary

Another extractor may replace this one when it emits the same `source_text` version. A converter between text versions is an ordinary adapter capsule. Compiler code, IntentIR and the run supervisor do not change.

