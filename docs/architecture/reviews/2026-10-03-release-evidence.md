# Frozen M1 architecture revision: evidence and handoff

## Design outcome

The package covers fixed production research, required offline RSI, and the frozen whitelist's isolated experiments. It supplies the seven coder questions through linked module cards, canonical payload/CC tables and authored service schemas, persistence/authority/security/environment contracts, spatial and temporal diagrams, and the [boundary-case index](../system/boundary-cases.md). It is a reviewed architecture checkpoint, not Muk's locked approval or an executed product release. Spec Kit, application code and runtime observations are downstream.

User deployment amendment: one Dockerized modular monolith exposes authenticated loopback HTTP endpoints to the external benchmark harness. The same Linux image runs under Linux Engine/macOS Docker Desktop. Internal restricted processes retain fixture/credential/workload boundaries. A dedicated bridge-owned persistent Codex home uses separate login and exclusive serialized custody; current documentation supports the pattern, while the pinned binary/account still require doctor checks. AuthProvider and ModelProvider are replacement boundaries. No actual credential file was inspected or imported.

The minimal current production library has eight work capabilities, one shared verifier and three reusable search operators. Ordinary extraction, deterministic intent hints, ranking/resource/arithmetic and publication helpers are modules. Planner is an isolated orchestration service, not a capsule. Puppet admission is an explicitly user-authorized exempt allowlist, with mandatory integrity and no fabricated testing/runtime authority. Saurav's provisional export adapter separates external benchmarking from scientific execution.

## Review and finding disposition

Fresh independent reviews derived all eight production producer and consumer interfaces separately. Review found and corrected scientific outcome tags/middle-zone rules; paired RSI scoring/headroom/session/final/clearance ordering; private Trial versus public Candidate; durable Gate/release ordering; effect-class/restart identity; seed availability; source clause references; runtime effect capture; and Docker/HTTP/ablation contract seams.

The [final fresh review](2026-10-03-final-fresh-review.md) re-read the actual corrections and closed F1–F5: immutable snapshot resolution, launcher/runner source_text/Binding refs, all-three RSI fixture scoring plus planted corpus, typed producer-disable refusal, and scope-specific private model-call identities/capture/cancellation. [RSI correction review](2026-10-02-rsi-contract-review.md) and [Docker author-side source audit](2026-10-02-docker-http-review.md) record additional dispositions. The latter is explicitly author-side evidence, not independent approval. Historical October1/early October2 reviews retain their original context and do not govern this checkpoint.

## Executed documentation checks

Run from repository root with Python and jsonschema installed:

| Command | Observed result |
|---|---|
| `python docs/architecture/_tools/arch_lint.py` then `--check` | canonical regeneration, field tables, positive examples, Markdown links, front matter, dependency graph and module/data diagram checks pass |
| `python docs/architecture/_tools/validate_services.py` | 419 positive/required-field/unknown-field/wrong-version/reference-format and selected conditional service-schema checks pass, including all four model-call scopes, private capture namespaces and cancellation identities |
| `python docs/architecture/_tools/validate_handoff.py` | 20 exact frozen-source hashes match; all eight independently derived module input sets agree; 18 production producer/consumer joins agree; accepted RSI Candidate/admission seam agrees; 131 generated payload positive/missing/unknown-field cases pass and all generated schemas compile |
| `git diff --check` and staged equivalent | no introduced whitespace errors; raw source attributes preserve verbatim CRLF bytes |

Fixtures are retained under [review fixtures](fixtures/2026-10-02/README.md). Interface packets are extracts, not complete admissible capsules. Reference-format checks do not prove a record exists, is in the correct run or has correct content; those semantic checks belong to the specified downstream boundary invocations. No paid model call, login, container execution, sandbox probe, native UI run, scientific experiment or RSI optimization was executed. There are no claimed runtime passes.

## Downstream obligations and reading order

Start with [source freeze](../../product/SOURCE_FREEZE.md), [policies](../policies.md), [coder requirements](../system/coder-requirements.md), [handoff cards](../system/handoff.md), [module map](../system/modules.md), [build order](../system/build-order.md), then the linked owners. Payload schemas and public service definitions are single authorities. The exact PRD heading inventory and grouped coverage retain source traceability.

Implementation must validate actual Docker/kernel/seccomp/identity/volume/IPC behavior, model auth/version/account support, binary wheel/hardware/method compatibility, all fault-injection/record-recovery cases, and native adapters on the pinned source. Unavailable/unrun mechanisms fail closed and cannot count as platform acceptance. The pending Saurav schema replaces the bounded export adapter. These are explicit implementation obligations, not undesigned black boxes. Remaining observations are in [validation obligations](../open-issues.md) and the case index.

Source and architecture hashes are pinned in the accompanying handoff checkpoint manifest. Future contract revisions require impact analysis and rechecking affected producers, consumers, diagrams and fixtures. Commits include relevant architecture/source/tooling work and preserved historical moves; unrelated video deletions and local Obsidian state are excluded.
