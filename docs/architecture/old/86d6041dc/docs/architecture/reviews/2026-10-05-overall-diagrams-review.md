---
type: review
status: draft
tags: [diagram, report, adversarial, evidence]
---

# Whole-system diagram and development-guide update

The user's requested reading view is [today's whole system](../system/overall-draft.md). The updated PDF contains eight bullet-report sections and two actual rendered Mermaid overview pages. Large-format diagram pages preserve labels; editable Mermaid and canonical owner links remain in the vault. This supersedes the earlier seven-page PDF presentation, not the underlying architecture contracts.

## Scope and findings

A fresh bounded reviewer compared the two diagrams with pipeline, Search/POC, planner, experiments, deployment, Gate/lifecycle and RSI owners. It reread corrected claims and report section 08 against process/authority/coder/verification policies. No product execution or exhaustive full-PRD review ran.

| Finding | Fixed reading view |
|---|---|
| Both production Search operators were incorrectly labelled conditional | Both are solid CC nodes, explicitly required per query. Dynamic placement applies only to approved isolated plans; available library identity is distinct from per-run presence. |
| A feature box suggested compiler/router/Code Mode all feed plan validation | Removed the universal arrow. Caption separately places compiler before proposal, routing within model calls and Code Mode within its isolated worker/Gate boundary. |
| External user box implied TUI runs on the host | Host API/browser/terminal attachment outside; CLI/TUI runtime explicitly inside the container. |

Reviewer targeted reread confirmed the corrections and section 08's depth/testing/development claims. No additional source correction found within that scope. Coordinator also separated entry/configuration from the supervisor label so the overview does not imply two execution authorities.

## Executed documentation evidence

Working directory: repository root on Windows; bundled Python/reportlab/pypdf, Mermaid CLI dependency 11.12.0 with cached Chromium, and bundled Poppler.

- Two new Mermaid blocks parsed and rendered, zero failures. Inspected generated images, then final PDF diagram pages. The eight text pages were inspected in the updated all-page contact sheet. No clipping, overlapping labels or missing visible glyphs observed.
- PDF reopened: ten pages, with eight A4 text pages and two larger-format overview pages. Diagram-page links lead to editable Mermaid; original linked pattern/owner sources remain.
- arch_lint generation and --check: ok after adding the required version field and removing prohibited semicolons in labels.
- validate_library: 1798 active file/heading links before adding this review record; twelve overview CC identities equal the canonical inventory. Final count rerun before commit.
- validate_services: 464 checks; validate_handoff: twenty frozen hashes, eight input pairs, eighteen joins, RSI seam and 131 payload checks; validate_stories: 136 checks.
- git diff --check: passed before this record; final staged check before commit.

The overview deliberately omits secondary input fan-in, repeated telemetry/event edges, per-model-call lines and separate Gate boxes for each work node. Insets are identified as support views, not later stages. They cannot replace exact port contracts or grant permissions. Current scope, shared interface ownership and runtime validation obligations are unchanged.

PDF SHA-256: `0b4d7cd1d6a2e4788e258b68132be136d1da798021836c60d171163022074b05`.

Mermaid owner-view SHA-256: `5b4ebc63fd5fbd8866465a37f0f1f5d227d5bc6165e4550fa9433c03f8177e06`.

## Subsequent information-flow audit and centralized presentation

The user then requested actual complete information dependencies and observability/RSI-cut variants. The new system/information-flow.md projects all 23 required pipeline bindings directly from the canonical fixture; the four variants preserve the same binding set. Search operators, CodeSearch, trusted measurements, StageContext, publisher, store/release, protected model and external I/O are expanded. The planner remains a separate conditional overlay; static production wiring is not generalized to every experiment.

Fresh review found publisher fan-in incomplete, PASS_WITH_KNOWN_LIMITATIONS missing from the advance condition and recovery language too broad. Corrections include all publisher refs plus authorized destination/request/release; ADVANCE accepts the two permitted Gate verdicts; new-attempt recovery is restricted to environment or reviewed partial-effect cases with unchanged pins. Ordinary failed checks produce Verification; only predecision invocation unavailability follows the direct halt branch. A missing Verification evaluates the Gate on existing Observation; a committed release is reused without re-execution. Reviewer reread confirmed these corrections except the pending predecision-label rename, which the coordinator subsequently made exactly as requested.

Presentation entry is docs/architecture/presentation/showcase/README.md. It links canonical pages rather than duplicate editable copies, giving a shallow route and question-to-owner table. The PDF now has eight report sections and four diagram appendix pages (twelve pages total), including a large-format core wiring zoom map and failure/recovery. Earlier hashes/page counts above describe their earlier candidates.

## Final quick presentation artifact

The sharing index now starts with a six-page point-form PDF: decisions, all CCs, conditional system tracks, failure/recovery, testing/development and a detailed core wiring appendix. The twelve-page report remains a longer reference. Source Markdown and diagrams are canonical-linked derived views, not independently editable contract copies. Final PDF pages were reopened and rendered; the quick six-page contact sheet was visually inspected, including corrected sequential page numbers. The detailed core map is explicitly a zoom appendix, not the shallow explanation.

Current quick PDF SHA-256: `c714477548417052b3aac95e64ce91f404dcfe69548c92e2dc096619569875e1`.

Current detailed PDF SHA-256: `0db26d06a741b011cd3df0a6df781386149872748eec730e2aa81e0dc51b5c57`.

Final documentation checks: 1840 active links; 12 overview CC identities; four variants with all 23 required input bindings and publication inputs; 464 service checks; 20 source hashes; 8 input pairs/18 joins; 131 payload checks; 136 story checks. These remain documentation checks, not runtime acceptance. Final Mermaid checks: seven blocks parsed/rendered, zero failures. Git staged diff check passed.
