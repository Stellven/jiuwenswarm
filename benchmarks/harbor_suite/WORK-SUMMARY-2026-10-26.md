# Work summary — October 26, 2026

America/Toronto session checkpoint. Case authoring and the initial Harbor
integration predate this summary; today's work concentrated on getting authentic
local runs working, preserving evidence, and documenting what remains blocked.

## Observed results

- **CC01 `evaluate-boundary`: passed** evidence, binding and deterministic content
  through implemented `research.evaluation m1-5`, GPT-6.1-Sol/medium, one call.
  Retained 295 original files; 19,704 input / 824 output tokens.
- **Matched plain Codex baseline:** same public assignment/schemas/model/effort,
  one call within 120 seconds. Format passed; content failed because complete
  measurements were marked missing. Retained 17 files; 16,726 / 937 tokens.
  This single development comparison does not establish general CC improvement.
- **CC02 `valid-pinned`: passed** static binding and execution through implemented
  `research.screening m1-4`; all 20 native checks passed. One model call,
  19,000 / 677 tokens; about 32 seconds application completion. Retained 337
  original files. Broader scientific interpretation still requires human review.
- Its first Harbor observer returned HTTP 502 at the old 30-second proxy timeout.
  GET-only collection recovered the same completed request without a second POST
  or model call. The failed observer remains retained; this is one trial.
- Verifier and pipeline prerequisites were investigated, but those cases have
  not passed live validation. No full case, suite, or end-to-end research pipeline
  result is established. Independent admission calibration remains NOT_RUN.

## Repairs and deployment

- Confirmed inference can use the existing host Codex account; account identifiers
  matched the desktop account. No auth cache copied or new sign-in required.
- Restored Docker Desktop and the persistent WSL runtime. Qualified an owned
  foreground relay through a long-lived Windows-to-WSL parent.
- Added bounded helper-stage/exit diagnostics, an exclusive relay lifetime lock,
  and a protected probe that cannot invoke the model. The exact OS/process cause
  of the original lost exception remains unproven.
- Added operator-only append-only acknowledgements for two historical unknowns
  after local containment observations. Original outcomes/ledger/guard remain
  unchanged; same-ID replay stays unknown and fresh unresolved claims block.
- Closed evaluation snapshot/profile export joins and strengthened selected
  Ref/hash/schema validation. CC02 now handles native Ref aliases/subnode context
  without rewriting bodies or weakening the authored scientific criteria.
- Increased authenticated evaluation POST transport timeout to 660 seconds while
  preserving native execution budgets; streamed original ZIP exports and added
  same-ID GET reconciliation for server errors.
- Added GET-only completed-evaluation collection with original-record/request/
  archive validation and isolated read-only copies of historical database state.
- Rebuilt/deployed matching app and receiver images, aligned operator metadata,
  and restored AI4R Bench Hub branding and the Test Cases column. Last check:
  app HTTP 200, hub 14 jobs, no active runs/unfinished claims/unreleased leases.
  Ordinary runner credentials need native refresh before a future campaign.

Focused validation included recovery/relay/route, snapshot/history, proxy/
reconciliation and collection checks. These overlapping test groups passed;
they are software checks, not additional benchmark trials.

## Remaining work and handoff

VF01 needs an adopted output schema, admitted producer/check assets and authentic
source invocation. VF02 additionally needs independently approved semantic labels
and scheduler capture. Pipeline01 needs its scientific executor/Builder and
restricted runtime; Pipeline02 needs the protected fault controller/audit.
CC02 still has six unmeasured controls; CC01 extraction needs a document binding.
These are AI4R runtime/admission gaps, not capabilities supplied by Harbor.

RSI/MR live cases were excluded. All 374 inventoried related files, including
349 original RSI source/artifact hashes, remained unchanged. No Spark/Qwen
inference run or remote service change is claimed for this session.

Created a local operator handoff and a separate ZIP of all
ten authored cases / 69 variants with per-file hashes and installation guidance.
Added external case-root selection for preparation, validation and comparison
tools so assets can live outside the product checkout. Original case copies
remain intact pending a deliberate merge cleanup. This packaging work launched
no new model calls. The ZIP's CRC and extracted hashes passed for all 141 case
files; all ten definitions / 69 variants loaded. The six included CC/verifier/
pipeline families passed 80 oracle unit checks from the extracted release, and
one CC task froze successfully from that external root. External-loading,
selection and comparison regression checks passed 34 tests (one platform skip).
These are offline checks, not additional live benchmark results.
See [current validation status](SERIAL-VALIDATION-STATUS.md)
for historical results. The public [benchmark README](README.md) replaces the
agent handoff in the integration branch and documents general setup and use.
The ten-case ZIP is included as public development material, not held out.
