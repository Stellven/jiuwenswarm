# M1PLUS / RSI integration analysis

Date: 2026-10-28 (America/Toronto). Backend integration complete and verified on isolated branch `rsi-loop-m1plus`.

## Integration decision and scope

The user approved adapting RSI to the partner release contracts after the handoff review. The product candidate catalog now selects Calculate m1-4 and Table Normalize m1-3. The initial RSI snapshot discovered and captured the original implementations under the same capability identities. Applying the loop unchanged would optimize historical bodies with historical checkers, rather than establish compatibility with the partner's current candidate releases. Selection in the catalog does not prove which version is active in a live installation; no live installation was inspected.

Authorized and implemented scope: make RSI resolve the selected release's declaration, worker, checker, criteria and immutable dependencies; make mutable-carrier ownership explicit for delegating workers; regenerate fixtures through that selected checker; remeasure parent correctness and model-free A/A noise. Preserve historical published records and release associations. Optional capsules without fixture manifests remain unavailable for RSI.

## Sources and branch relationship

- Isolated clone: `D:/M1plus/jiuwenswarm`, branch `rsi-loop-m1plus` (analysis began on `codex/m1plus-analysis`).
- Partner A: `origin/ai4r_M1plus`, captured HEAD `37194cc795ae89847327576c8a96a23091069adc`.
- Committed RSI base: `301bc9ed44aa3fe07084945ff107a04dbf9fcabd`, imported read-only from `D:/CLAUDE/jiuwenswarm` as `source/rsi-dev`.
- Common ancestor: `b983328d62fd8c5bfe7825bc6dd259f31e39ba85`. Diverged: 95 commits unique to RSI base; 158 unique to partner. Partner changes 1,652 paths since this ancestor; RSI base changes 312.
- Partner contains the handoff's historical M1 integration `b983328d6`. The currently fetched `origin/ai4r_M1` is instead `a78f9dcf021b8dbbc2bf45b8d67d4a1f355f494c`, which is NOT an ancestor of partner. Do not conflate the historical baseline with the moving branch.
- GitHub has no `rsi-dev` ref. The initial multi-ref fetch reported this; cloning had already fetched partner/M1 branches. Fetching the committed base from the local source resolved ancestry without changing either source checkout.
- B: current dirty source at `D:/CLAUDE/jiuwenswarm` plus `.claude-transfer/rsi-loop-v2.patch` and final snapshot tar.
- C: `D:/Codex Development Runs/jiuwenswarm` exists, also based on `301bc9ed4`, with later uncommitted changes. Compared read-only.

No source files in B or C were changed. Integration is confined to the isolated partner clone. No push, deployment, application model run, live journal/Core mutation, or service restart was performed. Three GPT-6.1 Sol analysis agents reviewed CC contracts, API/UI overlaps, and B/C provenance.

## Transfer provenance: correct before replay

The patch contains **18 mail patches**, not 24. Its 24-entry commit list includes six merge commits. The baseline commit `c3dc335` described by the handoff is absent from both the mails and the source Git object database. At patch lines 103-104, the first mail modifies an existing `deploy/m1/rsi_capsule_publication.py` blob (`d62fcc1`), but that file is absent from committed RSI base `301bc9ed4`.

Patch SHA256: `bf9db5e3ad0a6abd8087242f39cc48f1be7b03f31238b01bd83f5d7d86558184`.

The patch and final changes tar each cover 88 paths. They are not a standalone complete baseline. Current B also contains baseline wiring excluded from those 88 paths: `ccApi.ts`, `research_http.py`, `bootstrap_gateway.py`, `cc_ui_runtime.py`, development install/run/prepare/service files and tests. The older `repo.tar.gz` fails full listing with a truncated-input error; it cannot be accepted as a complete baseline archive.

The prerequisite backend tree was reconstructed in isolation from B/C as commit `f179eeb91`. Seventeen backend-bearing authored mail patches were replayed through `b90333d43`; UI-only `ca07aa7` and frontend hunks were intentionally omitted under the user request. Six merge entries were not invented as replayable commits. Follow-up commits imported the required shared backend dependencies and corrected the source closure while preserving partner contracts.

## CC changes and contract evidence

Paths in this section are relative to the partner clone unless prefixed B, meaning `D:/CLAUDE/jiuwenswarm`.

### Shared packet API and original carriers

The handoff path `research/packet.py` is shorthand: the actual module is `jiuwenswarm/research/capsule_extensions/packet.py`. It is byte-identical between partner and B, SHA256 `b18dafe6035849fa65d2f473cfaeabac9825ce0d15eaf2c5a9302f79eda37e16`.

`validate_packet` at lines 14-29 enforces schema, serialization bound, file paths/digests and uniqueness. `output_packet` at 32-43 validates and deep-copies input and replacement data, adds provenance/limitations, then validates output. `produced` at 54-55 validates again. The shared validation/deepcopy opportunity still exists, but its old measured gain is not evidence for a different Calculate implementation.

Original `calculate/{worker,checks}.py` and `table_normalize/{worker,checks}.py` are unchanged versus the common ancestor and byte-identical to B. The callable convention remains `async execute(ctx, inputs)` reading `inputs['packet']` and returning `{'result': produced(...)}` (`calculate_v3/worker.py:86-88`). New canonical wrappers delegate (`calculate_v4/worker.py:1-5`, `table_normalize_v3/worker.py:1-5`); optimizing only these wrapper bytes would expose a delegate rather than the underlying implementation.

### Canonical Calculate changes

`calculate_v4/release.py:9-13` keeps `utility.calculate`, selects version `m1-4`, requires `table_packet`, and freezes v3 worker/checker dependencies. `calculate_v4/checks.py:1-5` delegates to v3.

- Significant-digit and exponent bounds expand from 28 to 128 (`calculate/worker.py:40`, `calculate/checks.py:39` versus `calculate_v3/worker.py:60-62`, `checks.py:41-42`).
- New packet-shape diagnostics reject nested extra data wrappers (`calculate_v3/worker.py:17-30`).
- Sum is computed only when needed; inexact sums outside the 128-digit bound are refused (`worker.py:66-71`, `checks.py:48-54`).
- Equal min/max values use the first row-order spelling (`checks.py:46-47`, worker 77-79). The old max checker uses the last sorted value (`calculate/checks.py:45`). The regression at `tests/unit_tests/research/test_calculate_capsule.py:109-115` expects `['-0.00','0.00','1.0','1.00']` to produce max `'1.0'`.
- Checker criteria change to `result_schema` and `result_integrity` (`calculate_v3/checks.py:60-62`).

B's checker-authoritative failures / exact passing-parent bytes rule (`B:jiuwenswarm/research_rsi/targets/capsule_objective.py:21-25,375-383`) therefore has a different baseline partition under the new checker. Old max-tie headroom and old performance percentages must not be asserted for it.

### Normalize, optional typed checkers and catalog

`table_normalize_v3/release.py:9-14` retains `utility.table_normalize`, version `m1-3`, and declares `table_packet` output with original/v2 implementation dependencies. `assets_v2.py:9-11,41` adds configurable output artifact type while retaining the packet schema. The resulting chain is `work_packet -> table_packet -> work_packet`; partner tests at `test_supplied_input_types.py:125-142` enforce parsed input before Calculate.

Optional `calculate_typed`, `table_normalize_typed`, and `markdown_report_typed` have distinct capability identities (`*/release.py:9`). `typed_values.py:7-9` compares canonical JSON types; lines 12-37 preserve inherited fields and fidelity; lines 43-53 combine fidelity with integrity and rename legacy criteria. `test_typed_utility_capsules.py:18-46` demonstrates legacy false acceptance of JSON primitive changes and typed rejection. These optional checkers do not silently replace canonical ones.

Product discovery reads immediate release manifests (`catalog.py:29-56`). Old v2 Calculate/Normalize manifests and Calculate v3 move into `history/v2`; history now reads v1/v2, validates dependencies, and keys by identity/version (`catalog.py:69-101`). Historical installation checks retain eligible associations and active/live-plan standing (`catalog.py:119-132`).

Partner contains no capsule `fixtures/manifest.json`. B adds two under original directories and derives worker/checker paths from that directory (`B:targets/capsules.py:190-207`). Matching identity strings do not establish matching release provenance. Further, B's runtime fixes old modules (`B:targets/capsule_runtime.py:27-29,235-236`), imports old checkers (429-432), and demands `packet_schema`/`packet_integrity` (437-438). Adding new fixture manifests alone cannot solve this; runtime capture and criteria handling need general release-aware adaptation.

`research/contracts` is a package, not `contracts.py`. Partner has no changes there since the common ancestor. B's `contracts/rsi_security.py` adds candidate resolution and scope checks; these are source-baseline prerequisites to preserve.

### Wider partner behavior relevant to integration

The partner also adds integrity checks, hash-chained trace manifests/checks, supplied-input typing and planner enforcement, bounded agent runtime/Builder changes, and new core releases. These remain partner-owned. The exact overlap of committed RSI prerequisites with these surfaces is recorded below; a broad baseline overlay would risk replacing them. Focused deterministic tests exercised integrity, packet review, traces, typed planning and frozen composition.

## API, authority, UI and localhost

Partner introduces no changes since the common ancestor to `research/cc_ui_runtime.py`, gateway `research_http.py`, `server/rsi/cc_rsi_*.py`, or frontend `features/rsi/**`. Most CC UI/authority additions are absent on partner. Diffs against `source/rsi-dev` showing missing files are RSI-only additions, not partner deletions.

Required B wiring outside the patch includes:

- `research/bootstrap_gateway.py:294-310`: workspace and adapter initialization.
- `research/cc_ui_runtime.py:9,19-26`: adapter allowlist and attachment.
- `gateway/channel_manager/web/research_http.py:417-483`: per-call authentication, workspace binding, targets/readiness, snapshot, candidate access, and dispatch.
- `server/rsi/rsi_handlers.py:47-50,69-70`: projection endpoint registration/construction.
- `frontend/src/features/rsi/ccApi.ts:5-8` and `RsiPage.tsx:15,37`: CC methods and workbench mounting.

B projection owns lineage v2 (`cc_rsi_projection.py:92,562-563`), refuses publication as authority (732-738), and joins exact node/candidate hashes (741-750). B readiness adds phase/revision/observation metadata (`cc_rsi_capsule.py:275-294`). Partner has no conflicting snapshot shape in this surface; the missing baseline must be integrated before the lineage patch is meaningful. Historical published bytes remain protected by B's digest-pinned tests, not by this unmerged analysis.

Partner-added live commands retain host 5175 (`scripts/live/deploy_live.py:60`, `run_trap.py:137`) and container-internal 5173; `deploy/m1/compose.benchmark-runner.yaml:39` maps `127.0.0.1:5175:5173`. A pre-existing conflicting host-5173 mapping remains in `deploy/m1/compose.yaml:25,36-37`; default Vite 5173 also predates partner changes. No new host-port conflict was found in the scanned partner additions. Any eventual local app launch must use host 5175.

## C fixes to retain or supersede

C paths are under `D:/Codex Development Runs/jiuwenswarm`; B paths under the source tree above. These are recommendations, not applied changes.

| C change | Integration decision and evidence |
|---|---|
| Disconnected status client | Retain: C `deploy/m1/rsi_capsule_broker.py:74-80` catches `OSError`; B line 290 sends directly and can terminate broker on disconnect. |
| Preflight timeout process tree | Retain the owned-group cleanup behavior after checking integration: C broker 94-110 terminates its process group; B 174-180 uses `subprocess.run` timeout, which does not establish descendant termination. |
| Shared finite status deadline | Mostly superseded by B cached off-request readiness at broker 253-256; do not replace the durable readiness design. |
| Launcher publication overlay | Already covered by B pinned publisher and broader terminal-state handling. |
| Finite broker and hardcoded two targets | B strict/durable configuration and generalized validation win; C finite-only implementation is superseded. |
| Prepare/context validation | C prepare 40-55 and session 32-59 validate performance/prior-context schemas; B uses a different exact machine-generated contract. Reuse needed validation semantics only if retaining those schemas, not whole-file replacement. |
| Hand-driven checker/semantic scripts | Benchmark/semantic-edge port supersedes them as described by the handoff. |

C tests `tests/unit_tests/scripts/test_rsi_capsule_broker.py:9,23,38` cover disconnect, shared deadline, and owned-group timeout cleanup. They are absent from B and were not run against partner, which lacks this broker.

## Partner baseline execution

Exact partner blob export via `git archive HEAD` ran on WSL Ubuntu-24.04, Python 3.12.3, root, in `/var/tmp/m1plus-analysis-8f4Uyp/src`. Venv sibling; no live runtime source used. Dependencies: pytest 9.2.0, pytest-asyncio 1.4.1, jsonschema 4.26.0, cryptography 50.0.2, pyyaml 6.0.3, typing_extensions 4.16.0. This minimal test environment differs from the project's cryptography 47.0.0 pin; results describe the observed environment. UID 12003 was not present; no user was created. Partner does not include the loop's local-e2e test.

All commands set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1`; invoked venv Python with `-m pytest -o addopts= -p no:cacheprovider -p asyncio --confcutdir=<suite directory>`. Raw logs and exact invocation scripts are retained under `D:/M1plus/analysis-evidence/` and `D:/M1plus/run-*.sh`.

| Scope | Observed result |
|---|---|
| Entire `tests/unit_tests/research_rsi` | 90 passed, 1 failed (11.38 s). |
| Failing controller test alone | Same failure (0.24 s); not a test-order issue. |
| Eight CC suites: calculate_capsule, typed_utility_capsules, capability_extensions, capsule_assets, integrity_checks, packet_review, trace_checks, trace_manifest | 172 passed, 44 subtests passed (5.09 s). |
| Three CC contract suites: capsule_composition, supplied_input_types, typed_planner | 39 passed (10.91 s). |
| `tests/unit_tests/scripts/test_rsi_bundle.py` | 4 passed (0.02 s), additional packaging check. |
| Requested capsule/cc RSI script files | No matching files on partner; unavailable, not passed. |

The RSI failure is `test_controller.py::test_rejected_attempt_absence_and_failure_are_counted_and_chained`: line 42 stores `{'fixture':'public unit only'}` as a profile reference; `controller.py:48-57` recovery now freezes/validates that reference; `research_records/contracts.py:37` rejects it as `rsi-target-profile`. This is present before integration and reproduces alone. Do not classify it as one of B's four handoff-listed environment failures. No test or assertion was changed.

Frontend build, merged closure proof, loop e2e, post-merge counts, and real WSL/model execution are NOT RUN. They belong to later integration/deployment gates. Current partner test counts cannot be compared to B's 757/226 minima as if both contained the same suites.

## Merge forecast and next decision

The 88 patch paths have zero direct partner changes since the common ancestor and are all absent from partner. This does NOT mean a conflict-free integration: committed RSI prerequisites change 312 paths, 305 outside the patch, and 22 of those overlap partner. Current B also has dirty baseline wiring outside the patch. The tables below distinguish these sources.

Proceeding requires agreement to adapt RSI to selected current releases, regenerate checker-derived fixtures, and remeasure baseline correctness/A-A, plus recovery of a verified prerequisite baseline before replaying the authored patches. No `rsi-loop-m1plus` branch or merge commit has been created during Task 1.
## Exhaustive mail-patch path map

Partner touched = changed since common ancestor. Base exists = present in committed RSI base. Every path below is absent from partner HEAD.

| B patch path | Partner touched | Base exists |
|---|---|---|
| `deploy/m1/rsi_capsule_broker.py` | False | False |
| `deploy/m1/rsi_capsule_launcher.py` | False | False |
| `deploy/m1/rsi_capsule_prepare.py` | False | False |
| `deploy/m1/rsi_capsule_publication.py` | False | False |
| `deploy/m1/rsi_capsule_run.py` | False | False |
| `deploy/m1/rsi_capsule_slot.py` | False | False |
| `deploy/m1/RSI-CAPSULE-RUN.md` | False | False |
| `deploy/m1/RSI-HANDOFF-2026-10-26.md` | False | False |
| `deploy/m1/RSI-LOOP-WSL-RUNBOOK.md` | False | False |
| `docs/review/evidence-20261026/browser-current-failure-review.png` | False | False |
| `docs/review/evidence-20261026/calculate-r2-interrupted-publication-actual.json` | False | False |
| `docs/review/evidence-20261026/calculate-r2-interrupted-publication-plan.json` | False | False |
| `docs/review/evidence-20261026/calculate-startup-no-effect-observation-r1.json` | False | False |
| `docs/review/evidence-20261026/capsule-calculate-metadata-r2-outcome.json` | False | False |
| `docs/review/evidence-20261026/capsule-terminal-app-update-complete-r1.json` | False | False |
| `docs/review/evidence-20261026/capsule-whole-package-doctors-r4-outcome.json` | False | False |
| `docs/review/evidence-20261026/rsi-selected-review-snapshot.json` | False | False |
| `docs/review/evidence-20261026/whole-capsule-public-baselines-actual.json` | False | False |
| `docs/review/evidence-20261027-codex/final-authenticated-native-ws.json` | False | False |
| `docs/review/evidence-20261027-codex/final-integration-index.json` | False | False |
| `docs/review/evidence-20261027-codex/verified-capsule-improvements-r2.json` | False | False |
| `docs/review/REVIEW-BUNDLE-README-20261026.md` | False | False |
| `docs/rsi-loop/INTERFACES.md` | False | False |
| `jiuwenswarm/channels/web/frontend/src/features/rsi/ccLoop.ts` | False | False |
| `jiuwenswarm/channels/web/frontend/src/features/rsi/CcRsiWorkbench.tsx` | False | True |
| `jiuwenswarm/channels/web/frontend/src/features/rsi/ccTypes.ts` | False | True |
| `jiuwenswarm/channels/web/frontend/src/features/rsi/components/CcLoopTimeline.tsx` | False | False |
| `jiuwenswarm/channels/web/frontend/src/features/rsi/styles/cc-rsi.css` | False | True |
| `jiuwenswarm/channels/web/frontend/tests/ccRsiWorkbench.test.mjs` | False | True |
| `jiuwenswarm/research_rsi/capsule_doctor.py` | False | False |
| `jiuwenswarm/research_rsi/capsule_loop.py` | False | False |
| `jiuwenswarm/research_rsi/capsule_session.py` | False | False |
| `jiuwenswarm/research_rsi/model_backends.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_benchmark_executor.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_benchmark_runtime.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_benchmark.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_context.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_executor.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_local_dispatcher.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_objective.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_runtime.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsule_semantic_edges.py` | False | False |
| `jiuwenswarm/research_rsi/targets/capsules.py` | False | False |
| `jiuwenswarm/research/capsule_extensions/calculate/fixtures/benchmark.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/calculate/fixtures/held_out.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/calculate/fixtures/manifest.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/calculate/fixtures/public_extended.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/calculate/fixtures/public.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/calculate/fixtures/semantic_edges.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/table_normalize/fixtures/benchmark.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/table_normalize/fixtures/held_out.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/table_normalize/fixtures/manifest.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/table_normalize/fixtures/public_extended.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/table_normalize/fixtures/public.json` | False | False |
| `jiuwenswarm/research/capsule_extensions/table_normalize/fixtures/semantic_edges.json` | False | False |
| `jiuwenswarm/server/rsi/cc_rsi_capsule.py` | False | False |
| `jiuwenswarm/server/rsi/cc_rsi_development.py` | False | False |
| `jiuwenswarm/server/rsi/cc_rsi_projection.py` | False | True |
| `PROGRESS.md` | False | True |
| `tests/unit_tests/research_rsi/codex_evidence/calculate-native-candidate-r2.py.txt` | False | False |
| `tests/unit_tests/research_rsi/codex_evidence/calculate-paired-report-r2.json` | False | False |
| `tests/unit_tests/research_rsi/codex_evidence/calculate-readable-benchmark-r2.json` | False | False |
| `tests/unit_tests/research_rsi/codex_evidence/capsule-benchmark-frozen-manifest-r3.json` | False | False |
| `tests/unit_tests/research_rsi/codex_evidence/capsule-supplementary-parent-oracles-r2.json` | False | False |
| `tests/unit_tests/research_rsi/codex_evidence/normalize-native-candidate-r2.py.txt` | False | False |
| `tests/unit_tests/research_rsi/codex_evidence/table_normalize-paired-report-r2.json` | False | False |
| `tests/unit_tests/research_rsi/codex_evidence/table_normalize-readable-benchmark-r2.json` | False | False |
| `tests/unit_tests/research_rsi/codex_evidence/verified-capsule-improvements-r2.json` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_benchmark_local.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_benchmark_protected.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_benchmark.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_context.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_dispatch_e2e.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_doctor.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_executor.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_loop_e2e_local.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_loop.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_objective.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_prepare.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_public_targets.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_run.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_runtime.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_semantic_edges.py` | False | False |
| `tests/unit_tests/research_rsi/test_capsule_session.py` | False | False |
| `tests/unit_tests/scripts/test_cc_rsi_capsule.py` | False | False |
| `tests/unit_tests/scripts/test_cc_rsi_projection.py` | False | True |
| `tests/unit_tests/scripts/test_rsi_capsule_launcher.py` | False | False |
| `tests/unit_tests/scripts/test_rsi_capsule_publication.py` | False | False |

## Committed RSI prerequisites also changed by partner

These are absent from the patch. Compare each common-ancestor three-way diff; retain partner semantics while integrating only required RSI behavior.

- `.gitattributes`
- `benchmarks/harbor_suite/comparison.py`
- `docs/code/Missions/archive/M1/M1-008/plan.md`
- `docs/code/Missions/archive/M1/M1-008/spec.md`
- `docs/code/Missions/archive/M1/M1-008/tasks.md`
- `jiuwenswarm/research/bootstrap_core.py`
- `jiuwenswarm/research/bridge.py`
- `jiuwenswarm/research/calibration_authority.py`
- `jiuwenswarm/research/capsules/assets.py`
- `jiuwenswarm/research/checks/calibration_runtime.py`
- `jiuwenswarm/research/compiler.py`
- `jiuwenswarm/research/local_profile.py`
- `jiuwenswarm/research/resources/capsules/capsule_catalog.json`
- `jiuwenswarm/research/resources/capsules/paper_catalog.json`
- `jiuwenswarm/research/runner.py`
- `jiuwenswarm/research_assets/catalog.json`
- `jiuwenswarm/server/runtime/codex_subscription/service.py`
- `tests/unit_tests/harbor_suite/test_comparison.py`
- `tests/unit_tests/research/test_capsule_composition.py`
- `tests/unit_tests/research/test_library_operator.py`
- `tests/unit_tests/research/test_measurement.py`
- `tests/unit_tests/runtime/test_codex_subscription.py`

## Current B status paths omitted from mail patch

Directory entries represent Git status summaries, not recursively inventoried archive contents. Transfer metadata and handoff files are not product prerequisites.

- `deploy/m1/rsi_development_publication.py`
- `jiuwenswarm/channels/web/frontend/src/features/rsi/ccApi.ts`
- `jiuwenswarm/gateway/channel_manager/web/research_http.py`
- `jiuwenswarm/research/bootstrap_gateway.py`
- `jiuwenswarm/research/cc_ui_runtime.py`
- `tests/unit_tests/scripts/test_rsi_development_publication.py`
- `.claude-probe`
- `.claude-transfer/`
- `deploy/m1/RSI-DEVELOPMENT-RUN.md`
- `deploy/m1/RSI-HANDOFF-M1PLUS-MERGE.md`
- `deploy/m1/installed_app_rebuild.py`
- `deploy/m1/rsi_development_authorize.py`
- `deploy/m1/rsi_development_install.py`
- `deploy/m1/rsi_development_launcher.py`
- `deploy/m1/rsi_development_prepare.py`
- `deploy/m1/rsi_development_run.py`
- `deploy/m1/rsi_development_seed.py`
- `deploy/m1/rsi_development_service.py`
- `docs/review/`
- `docs/rsi-loop/`
- `jiuwenswarm/research/capsule_extensions/calculate/fixtures/`
- `jiuwenswarm/research/capsule_extensions/table_normalize/fixtures/`
- `tests/unit_tests/research_rsi/codex_evidence/`
- `tests/unit_tests/scripts/test_cc_rsi_catalog.py`
- `tests/unit_tests/scripts/test_cc_rsi_development.py`
- `tests/unit_tests/scripts/test_installed_app_rebuild.py`
- `tests/unit_tests/scripts/test_rsi_development_authorize.py`
- `tests/unit_tests/scripts/test_rsi_development_launcher.py`
- `tests/unit_tests/scripts/test_rsi_development_prepare.py`
- `tests/unit_tests/scripts/test_rsi_development_run.py`
- `tests/unit_tests/scripts/test_rsi_development_seed.py`
- `tests/unit_tests/scripts/test_rsi_development_v18_output.py`

## Completed backend integration and measured coverage

The partner branch now has the transferred bounded diagnose/propose/evaluate/keep-best loop, with immutable selected-release bindings and an explicit retained subject. Each experiment feeds measured scores and failures into the next proposal; it retains the best qualifying child or the original parent. This retains a development artifact without changing live admission or activation. Dependency context follows delegating workers under finite module/source/excerpt budgets. No frontend files differ from the captured partner branch.

The model-free catalog runner completed a three-repetition smoke protocol on 2026-10-28 with **8 tested, 2 skipped, 0 errors** and **400 paired benchmark jobs**, in addition to parent correctness evaluations:

| Selected capsule | Release | Parent correctness | Paired jobs |
|---|---|---:|---:|
| Calculate | m1-4 | 19/19 | 86 |
| Calculate Typed | m1-1 | 6/6 | 64 |
| Markdown Report | m1-2 | 3/3 | 28 |
| Markdown Report Typed | m1-1 | 3/3 | 28 |
| Packet Report | m1-1 | 3/3 | 28 |
| Summary to Packet | m1-1 | 3/3 | 28 |
| Table Normalize | m1-3 | 19/19 | 78 |
| Table Normalize Typed | m1-1 | 19/19 | 60 |

Generalist requires its declared audited model bridge and frozen invocation context. Builder requires a real governed native invocation and independent task adapter. Both are explicit unsupported results for the model-free runner. Summary conversion uses its declared `summary` port; the pipeline derives the port from each selected declaration rather than assuming every input is a packet.

These are real worker/checker executions with immutable evidence, `local_unprotected`, zero model calls, and parent-versus-itself comparisons. All improvement claims remain false. The short protocol preserves acceptance gates while reducing sample/batch sizing; no historic candidate percentage is transferred to a new release. [BENCHMARKS.md](BENCHMARKS.md) contains the reusable commands.

Verification was performed in disposable native Linux snapshots with the selected source bytes:

- Partner CC/core plus adjacent relay checks: **231 passed, 49 subtests**.
- Capsule/CC deployment scripts: **236 passed**.
- Non-capsule RSI prerequisites: **622 passed, 4 failed** before final repairs; all four were corrected and the focused cancellation/controller/transport rerun passed **11 checks**. Cancellation fixtures now reach the cancelling proposer; transport receipts retain the original closed exception category through staged wrappers.
- Full capsule suite before the dependency-context fix: **145 passed, 4 failed**. All four context checks pass after replacing the fixed import-depth cutoff with bounded graph traversal.
- Final selected-release/runtime/public/prepare/session checks plus the real paired benchmark selection end-to-end case: **48 passed**, with one stale test assertion that tried to read sealed held-out inputs through the public store. The corrected authoritative-reader assertion and four context checks passed in the final **5-check rerun**. No unresolved failure remains from these runs. The entire broad suite was not rerun after these focused repairs.
- The real loop end-to-end cases exercise current Calculate and Normalize workers through the Root/controller pipe, and preserve the historical candidate digest separately. Models are scripted for these checks; no live model experiment was launched.
- Integrated source closure: **complete, 1,133 modules, 71 resources, 3,759 inventoried files**. Patch whitespace checks pass.

Evidence is retained under `D:/M1plus/analysis-evidence/integration/`: `catalog-benchmark-eight.json`, `partner-cc-relay.log`, `capsule-cc-scripts.log`, `rsi-prerequisites.log`, `transport-cancellation-fixes.log`, `capsule-suite-before-context-fix.log`, `selected-release-suite.log`, `context-summary-final.log`, and `source-closure.json`. Full per-job benchmark captures remain at `/var/tmp/m1plus-eight-capsule-smoke-20261028/` in WSL.

No source checkout B/C changes, push, deployment, live journal/Core writes, service restart, UI update, or live model run was performed. The final integration remains on the isolated partner-based branch for review and later deployment.