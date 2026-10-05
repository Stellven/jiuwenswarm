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

## Superseding flow correction after f46f88255

The user corrected the whole-system presentation: intake -> intent capsules/Gates -> requirement capsules/Gates -> planner-created DAG -> binding/freeze -> local capsule/Gate execution -> ordinary Delivery processing and user retrieval. SwarmFlow supplies required fixed outer positions; planned nodes become fixed before execution. Failed Gates halt all later work dispatch, including ready sibling branches.

The new owning page is `m1/control-flow.md`. Existing fixed research wiring and experimental-only planner entry are labelled baseline/superseded, not silently promoted to new contract readiness. Intent identities, revised requirement/planner ports, profile contracts and affected fixtures remain connected design work.

One shared semantic verifier identity serves multiple Gate profiles/call sites. All Gate-role capsules have `evolution.rsi: none` and `evolution.may_change: []`; the shared verifier and RSI controller owners now state this rule. Fixed referee pins support interpretable work-version comparisons, not a statistical success-rate claim from a small fixture suite.

A Luna review found ambiguous grouped requirement/Gate ordering, a stale requirement-input row, unclear shared-verifier diagram identity and missing whole-run failure edges in the DAG detail. All were corrected: per-call ordering label, explicit baseline warning, shared verifier labels/zero mutable components and failure arrows to whole-run halt.

Final checks: `arch_lint.py --check` passed; `validate_library.py` passed with 2075 active links, derived-view freshness and corrected-flow assertions. Mermaid parsed/rendered nine blocks with zero failures. The eight-page PDF was rebuilt and all rendered pages visually inspected; the main and DAG-detail views now match the corrected flow. Old schema/producer tests remain baseline evidence only. No implementation, new released wire schema or runtime acceptance is claimed.

Final candidate hashes (review record excluded):

- `docs/architecture/m1/control-flow.md`: `bd5b0c47d66544e37eaceeb86f1ac94555d6a2de6a0146ef0f4bb722eab24e08`
- `docs/architecture/presentation/showcase/presentation.md`: `14ab38f5d02bcbfd5a77138c644fda3c658028a5be9202e92f0ee713b3007d87`
- `docs/architecture/presentation/showcase/capsules.md`: `47a562a0641a6068f3d8425901daa73595f946971e2ca91ed677e6d37f2b7a39`
- `docs/architecture/capsule/gate-capsules.md`: `383f6c97ab823a64f523ee54e47b3468c82d71c404214fe7f30d4760913e5f92`
- `docs/architecture/capsule/rsi-engine.md`: `1797a32af26f6699bd1ee30b03c3500e403eb01e7e217e6ff60d8642131fef32`
- `output/pdf/m1-architecture-presentation-2026-10-05.pdf`: `33dc58ed32dac48a50275b0146bfa4048f726ab65a6f331b85bdc033f7b86675`

## Connected Markdown correction after 86d6041dc

Rebuilt all four `system/information-flow.md` variants from the fixed intake/intent/requirements preparation and planned/frozen DAG owner. Required evidence, model bridge, sealed retrieval, ordinary Delivery and optional display/RSI branches now follow that flow. The old 23-binding research view is archived, not used as whole-system authority.

Revised the overall/system diagrams, atlas, complete temporal sequence, planner authority, node definition, environment scope, root reading path and showcase links. Retained typed research contracts under `system/research-contract-map.md`; their canary remains enabled separately from current main-flow checks. Repeated main/DAG graphs and filtered flow views are generated from the control-flow owner. No PRD source was edited.

The user clarified the distinction: a CC is reusable library capability; a node is its hot-path task-specific bound use; `research.verifier` is a CC checking the result of that node. A trusted builder automatically prepares declaration-specific test instances, binds them immediately after work calls and pins them before execution. Every Gate-role capsule has zero RSI-mutable components. Exact revised builder/intent/requirement entry wire contracts remain pending; old schema tests do not establish those new interfaces.

A fresh Luna audit found remaining fixed-template planner scope, an eight-step temporal loop, misleading old atlas fan-in ownership and conditional verifier wording. Current planner/nodes/environment prose and diagrams were corrected. The diagram now distinguishes deterministic-first Gate checks from semantic verifier invocation when those checks pass. Explicit recovery retains the lifecycle's committed-state reconciliation; no new permanent no-resume product rule was inferred.

Final structural checks: architecture lint/check passed; active navigation/projection checks passed with 2083 links; four filtered views preserve fixed preparation, planned/frozen execution, Gates and ordinary delivery. Mermaid parsed/rendered 23 blocks across showcase, information flow, overall/system diagrams, atlas and temporal sequences with zero failures. The eight-page PDF was refreshed and visually inspected; the core information map was inspected separately as a zoom view. Scoped whitespace check passed. These are documentation checks, not runtime, platform or completed new-wire-contract acceptance.

Current owning files and output hashes:

- `docs/architecture/system/information-flow.md`: `1dca5b7bcf9acea7adb1d0c29627ba1c75839e9d4c968010614199600f568412`
- `docs/architecture/system/planner.md`: `8b570ddbdbc91a3bc572637efe7e2f2de491e820b34dd223b946371640af1843`
- `docs/architecture/system/nodes.md`: `9c30bd1f488295a562a9d701fe376ec0c44432f3b243aab6d05bdbe9df88bcdb`
- `docs/architecture/capsule/gate-capsules.md`: `a3b2943c06eb9d6fcc13290d75071cc94b5fdc185103b927b777849b640f1259`
- `docs/architecture/_tools/information_views.py`: `94d9f4597a047d6c01a0436236320d421ce8429139ab2875b66a3482696d78c8`
- `output/pdf/m1-architecture-presentation-2026-10-05.pdf`: `75e945fb66bafcc285c0bb23b558c662e530cbf64aed9812f837a6fe13a5e616`

### Final single-intent and terminology update

All current main-flow views now contain exactly one intent compilation capsule followed by its Gate. The generator/checks enforce that shape. Node labels now say task-specific bound CC use; the shared verifier is explicitly a CC checking node results, with automatic declaration-derived test preparation and zero Gate RSI mutation. Both PDF names now point to the same current eight-page snapshot rather than retaining contradictory diagram sets.

Final lint and navigation checks passed with 2090 active links. Twenty-three current Mermaid blocks parsed/rendered with zero failures. All PDF pages were inspected after the single-intent correction. The revised interface/builder contracts remain pending architecture work, not completed runtime results.

- `docs/architecture/m1/control-flow.md`: `1b041ca6575ff163299d3b8c53110c4119181afb192c79e17297db19a9af2ab1`
- `docs/architecture/system/information-flow.md`: `781a043567a6e11a43b5c46dcd2e9844b57dcc3229d81d3e4de2240e7a0267f3`
- `output/pdf/m1-architecture-presentation-2026-10-05.pdf`: `99cdeaa7b63457c3058ba9d4e1e5db3737b3cdf131ce97147eb553c83e3f373b`
- `output/pdf/m1-architecture-current-state-2026-10-05.pdf`: `99cdeaa7b63457c3058ba9d4e1e5db3737b3cdf131ce97147eb553c83e3f373b`
