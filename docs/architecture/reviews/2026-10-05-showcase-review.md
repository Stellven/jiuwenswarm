# Presentable snapshot review

**5 October 2026.** Candidate: architecture baseline `1c09e8394` plus the exact bytes below. Frozen sources remain unchanged. This is documentation evidence, not runtime acceptance.

## Scope and review

- Seven linked Markdown pages, generated canonical tables/diagrams, ten-page quick PDF and explicit SkillFuzz interaction-analysis deferral.
- A fresh Luna reviewer checked plain English, reading order and links. Adopted suggestions: clearer Obsidian entry, expansion of RSI, production-specific authority language, terminal-placement caption and separate final-evaluation reservation wording. Retained the small reading map for navigation.
- A separate fresh reviewer checked source fidelity and failure authority. Fixed omitted experimental ablations/alternate verifier, bounded experimental advance authority, wrong operator contract links and missing Screening no-winner halt.
- The review found an inherited diagram omission: Hypothesis also calls CodeSearch. Corrected the canonical overview label and generated query/result edges in all four flow variants. This does not change the 23 production input bindings. The reviewer rechecked all corrections and reported no further actionable findings in the changed scope.
- SkillFuzz interaction analysis is deferred in the planner, library and presentation. Typed structural checks remain required and do not establish semantic compatibility of capsule sets.

## Executed documentation checks

Working directory: repository root. Commands used local Python 3.12 for JSON Schema checks; bundled artifact Python for PDF generation.

| Command / inspection | Actual result |
|---|---|
| `python docs/architecture/_tools/arch_lint.py --check` | exit 0, `ok`; generated owners/projections agree |
| `python docs/architecture/_tools/validate_library.py` | exit 0; 2043 active local links; 12 capabilities; four variants each retain 23 bindings; seven showcase pages/projections agree; Hypothesis CodeSearch edges retained |
| `python docs/architecture/_tools/validate_services.py` | exit 0; 464 schema/example checks |
| `python docs/architecture/_tools/validate_handoff.py` | exit 0; 20 frozen hashes, 8 independent input contracts, 18 joins, 131 positive/missing/unknown-field checks and compiled generated schemas |
| `python docs/architecture/_tools/validate_stories.py` | exit 0; 136 documentation/story checks |
| Mermaid 11.12 parse/render with Chromium | 10 blocks parsed and rendered; zero failures: five showcase blocks plus five canonical information-flow blocks |
| PDF export and visual inspection | 10 pages; all pages rendered and inspected, updated environment page inspected again; no clipping/overlap found. Detailed core appendix is a zoom view, not a shallow slide |

Initial JSON Schema checks with bundled artifact Python failed because that runtime lacks `jsonschema`; reran them with the already installed local Python environment and obtained the results above. No dependency was installed. Poppler printed fallback-font warnings for Symbol/ArialUnicode; embedded body text and raster diagram layouts were visually checked.

## Reproduction and maintenance

- `arch_lint.py` refreshes the canonical projections and showcase together; `--check` refuses stale projections. `showcase_views.py --check` checks the presentation alone.
- Render the five showcase Mermaid blocks to `README-1.png`, `capsules-1.png`, `presentation-1.png`, `runtime-and-improvement-1.png` and `runtime-and-improvement-2.png`. Render the core canonical flow to `information-flow-4.png`.
- Run `build_showcase_pdf.py --diagrams <render-directory> --output output/pdf/m1-architecture-presentation-2026-10-05.pdf` using ReportLab, Pillow and pypdf. The exporter derives text from curated Markdown; it introduces no contracts. Font directory is configurable.
- Recheck linked owners after any contract change. Canonical status is retained; no page is promoted to locked by this review. Historical report evidence remains historical.

- Scoped `git diff --check` passed before staging; staged whitespace is checked again before commit.

## Remaining obligations

Real Codex login/refresh, API invocation, process/platform isolation, secret custody, store/crash durability, trusted measurements, full product integration and performance measurements remain unrun implementation work. SkillFuzz analysis remains deferred. This review establishes neither an unbreakable system nor full semantic PRD compliance from link counts.

## Exact candidate bytes

The review record itself is excluded from its hash table. Commit provenance pins the final record; these hashes identify the reviewed presentation and affected owners before commit.

| File | SHA-256 |
|---|---|
| `docs/architecture/presentation/showcase/capsules.md` | `048de655d87ad9e7ecbac6384de085f267f8914b7ae8642c7cb9bf01ce4b34d5` |
| `docs/architecture/presentation/showcase/data-and-permissions.md` | `fe76e53c519a959d5176e779e48f8e934577d64192f499756ac2e43d9da28618` |
| `docs/architecture/presentation/showcase/presentation.md` | `ecc6bd16ea0d26ea26071ed25746b6c0d79d1c425839b717d9c07acab7627535` |
| `docs/architecture/presentation/showcase/README.md` | `571842e2d76af8f9c19002f0033f985afca1e898449f8d17c882953b5a088104` |
| `docs/architecture/presentation/showcase/runtime-and-improvement.md` | `2f16ee439a56bb6b9ae3c5f576444cb34cd5680d62796f49b78b27377c10d67c` |
| `docs/architecture/presentation/showcase/schemas-and-connections.md` | `5a26f976ca36fb6ed31bad87c6a9fd7599427cf490c3b052950c30ffe76136fc` |
| `docs/architecture/presentation/showcase/validation-and-development.md` | `c8137f5ad9fe66452afb8b3a681fb5c332794b6badd3b30a1e93a4da581d65e7` |
| `docs/architecture/system/overall-draft.md` | `e246ae6c00586a9dff87f9b2890254af6a07d30b6ec6f8f521a9b9eb8eeed444` |
| `docs/architecture/system/information-flow.md` | `8a3f82d5ee747a8099aaec314298b7ab1ebde213e0ef22e4f4bf96a33560f4db` |
| `docs/architecture/system/planner.md` | `b67a2caff086d86001540d2d94b4fb4ca4f7074b82fc686efd71331fd2c66fdb` |
| `docs/architecture/capsule/library.md` | `b0e843e981c527f271994f79fd12aba960140be271a8d7fd9d41c57da7f531ef` |
| `docs/architecture/capsule/why.md` | `86f540276fa4a4c9bb65c915b18d3d9de33ad16211f0323561af85a2fa5c51c8` |
| `docs/architecture/_tools/showcase_views.py` | `0fdff56586e0baaa6525d11d18f2485a01a64a2bbeae157aa2555c848c8eb7c1` |
| `docs/architecture/_tools/information_views.py` | `520f176db6c17e790a7b64cc9596831af5d7b75b0769c3a4692b838b536c46f6` |
| `docs/architecture/_tools/build_showcase_pdf.py` | `eda1755279164e9d21fcdc09c0eeab36d776f87dcf741331ad0cf427953974a9` |
| `output/pdf/m1-architecture-presentation-2026-10-05.pdf` | `eb55ff0136d283c2cd7b96ab423176cf951a3b214e66f533391e23d560015d58` |
