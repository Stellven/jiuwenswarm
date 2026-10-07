> **Historical AI4R-001 record:** identities, decisions and observations below retain their original scope. Current M1 design and registration use the repository design-package and M1 TASKS; old review/approval cards do not govern new v2 work.

# Test and Acceptance Report: AI4R-001

Version: 0.8 | Recorded: 2026-09-28 | Template: [TEST_REPORT_TEMPLATE](https://github.com/Stellven/jiuwenswarm/blob/918df5e4081ed35d53257dfccd33119a7b639c57/docs/code/code_sop/templates/TEST_REPORT_TEMPLATE.md).
Scope: historical preparation/R001-R004 and the user-accepted M1 browser demo. Xiaoyang accepted localhost:5173 and explicitly requested direct publication on 2026-09-28. Detailed personal-account case traces were not supplied; fixture evidence and human acceptance remain separately identified. The publication rows below supersede earlier pending-demo-acceptance statements; full-project acceptance remains incomplete.

## 1. Verification target and acceptance basis (required)

- Task registry / artifact mode / test executor / execution time and time zone: [TASK v0.8](TASK.md); Spec Kit; Codex assistant; 2026-09-28, America/Toronto. Exact per-command times were not retained for every check.
- Risk level and verification scope: high-risk migration; these checks establish selected baseline behavior, bounded product integration with a fake provider, React component behavior and signed-out process ownership. They are insufficient for full subscription replacement acceptance.
- Acceptance source: [spec.md v0.2, Success Criteria](../../../specs/AI4R-001-codex-subscription/spec.md#success-criteria), active AC-01–AC-04 and AC-06–AC-08, confirmed by Xiaoyang; AC-05 is retired.
- Approved technical design and `write_code.md`: [native plan v0.3](../../../specs/AI4R-001-codex-subscription/plan.md) M1 addendum; [write_code v0.9](write_code.md); presented login/basic-chat milestone authorized by Xiaoyang in TASK Section 4. Broader G1-G4 remain unresolved.
- Verification work items: [native tasks v0.3](../../../specs/AI4R-001-codex-subscription/tasks.md), completed research R001-R004 and M1 M001-M006; broader T001-T033 remain unchecked.
- Merge target: `ai4r_main_branch`.
- Target baseline B: `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483`, fetched from `origin/ai4r_main_branch` during 2026-09-28 preparation; exact fetch time not retained.
- Tested implementation commit C: pending implementation commit. HEAD is `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483`, which excludes the uncommitted M1 implementation.
- Publication implementation C: `97c1bd6930497c2a97cedeca82c49b62650b56c8`; post-commit tests below ran against this source. Subsequent publication records change documentation only. Earlier manifests and working-tree descriptions are historical evidence.
- Actual execution target: working tree on HEAD/B with the manifest-identified M1 changes; fake provider for integration tests, real packaged App Server for signed-out probes. No integration commit exists.
- Relationship to final merge contents: implementation, full integration verification and final review remain required; no commit, push, PR or merge in this stage.

| Acceptance ID | Approved requirement/threshold source | Related case / check | Actual observation | Status |
| --- | --- | --- | --- | --- |
| AC-01 | Registered spec v0.2 | M1 profile/account/React fixtures and signed-out process probe | Partial evidence; actual sign-in/restart product journey not run | Not run for full AC |
| AC-02 | Registered spec v0.2 | M1 service and real facade/history tests with fake provider | Streaming association and persisted final history pass in fixtures; real socket journey passes with a synthetic provider; personal-account model journey pending | Not run for full AC |
| AC-03 | Registered spec v0.2 | Exact cancellation and stale-control fixtures | Fixtures pass; host tools/interactions unsupported in M1 | Blocked for full AC |
| AC-04 | Registered spec v0.2 | Runtime/auth error and late-response fixtures | Partial failure coverage; quota-specific recovery and live failures remain unverified | Not run for full AC |
| AC-05 (retired) | Registered spec v0.2; [CR-01](CHANGE_REQUEST-01.md) | No legacy migration required | Removed by explicit user decision, not a pass | N/A |
| AC-06 | Registered spec v0.2 | Environment/key-account rejection, log-body removal, fresh managed process | Bounded paths have no key fallback; no actual subscription model run or full outbound audit | Not run for full AC |
| AC-07 | Registered spec v0.2 | Cross-session, stale cancellation, logout and restart fixtures | Isolation fixtures pass; restart deliberately blocks old thread continuation; shared transport failures affect active streams | Blocked for full AC |
| AC-08 | Registered spec v0.2 | C01-C20 inventory and capability tasks | Tools/team/auxiliary/embedding/media and platform equivalence remain unresolved | Blocked |

Required risk-proportionate checks are proposed in native tasks.md and quickstart Q1a/Q1b–Q6. Baseline successes and schema availability do not satisfy these acceptance rows.

## 2. Reproducible environment (required)

| Item | Actual configuration |
| --- | --- |
| Working directory | Root: `D:\research\ai_for_research\jiuwenswarm`; frontend: root plus `jiuwenswarm/channels/web/frontend` |
| Operating system / architecture | Windows AMD64; PowerShell |
| Runtime / package manager / key dependencies | Selected Python 3.11.3, pytest 9.0.3, OpenJiuwen 0.1.18, application Codex packages 0.144.4; setup uv 0.12.19; Node 22.23.3/npm 10.9.9. Initial Python 3.13.1 and Node 20.15.0 failures remain recorded below. Locks: `uv.lock` and frontend `package-lock.json`, unchanged |
| Installation and preparation commands | [ENVIRONMENT](../../governance/ENVIRONMENT.md) records pinned Spec Kit bootstrap, uv installation, locked backend/frontend setup, portable Node checksum and process-local PATH |
| Services / configuration / environment variables | `SPECIFY_FEATURE_DIRECTORY=specs/AI4R-001-codex-subscription`; `SPECIFY_FEATURE_NO_PERSIST=1`; local ignored feature pointer; M1 uses a separate profile and owned App Server process; no signed-in subscription/model scenario exercised |
| Data / model / prompt versions | Existing fixtures at C; no actual model/dataset evaluation. Spec Kit source/assets recorded in [SPEC_KIT_SETUP.json](../../governance/SPEC_KIT_SETUP.json) |
| Random seeds / sampling settings | N/A for selected deterministic baseline checks; no model sampling performed |
| Hardware / concurrency / network conditions | Local Windows machine; no performance benchmark/hardware-normalized claim. Network used for fetching/installing packages; tests/build are baseline checks |

Executable notation below: `$uvExe` is `%LOCALAPPDATA%\ai4r-tools\spec-kit-v1.0.12\Scripts\uv.exe`; `$specifyExe` is the neighboring `specify.exe`. Use the exact session-local Node path documented in ENVIRONMENT. Global runtime selection may differ.

## 3. Commands and original evidence (required)

All rows were executed on 2026-09-28. Unrecorded durations are explicitly marked. Local log root L is `%LOCALAPPDATA%\ai4r-tools\evidence\AI4R-001`; logs are local evidence, not remote attachments. Historical setup logs have fingerprints in SPEC_KIT_SETUP.json; historical M1 file fingerprints are in L/m1-code-sha256.json.

Backend command B1, run from repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit_tests/common/test_external_cli_catalog.py tests/unit_tests/common/test_external_cli_runtime.py tests/unit_tests/test_models_replace_all_merge.py tests/unit_tests/gateway/test_resolve_model_config_obj.py tests/unit_tests/symphony/test_llm.py --no-cov -q
```

| ID | Working directory | Actual complete command | Time / duration | Exit code | Case counts and observations | Log / artifact location | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-01 | Root | `git status --short --branch`; `git branch -vv`; `git remote -v` | Duration not retained | 0 | Personal branch/tracking and Stellven origin inspected; local branch aligned under explicit user authorization | Terminal output; TASK baseline | Passed |
| T-02 | Root | `& $specifyExe version`; `& $specifyExe init --help`; `& $specifyExe preset resolve spec-template` | Duration not retained | 0 | Pinned 1.0.12 CLI works; core spec template resolves | ENVIRONMENT; setup metadata | Passed |
| T-03 | Root | `& ./.specify/scripts/powershell/check-prerequisites.ps1 -PathsOnly -Json`; `git check-ignore .specify/feature.json` | Duration not retained | 0 | Registered paths resolve; local selector ignored; no branch change | Terminal output | Passed |
| T-04 | Root | `& $uvExe sync --locked --extra codex --group test` | Duration not retained | 0 | Initial Python 3.13.1 dependency install succeeded | Terminal output | Passed |
| T-05 | Root | B1 above, initially without and then with `--continue-on-collection-errors` | Diagnostic run: 17.84 s | 2 initial / 1 diagnostic | Initial collection failure; diagnostic: 74 passed, 2 failed, 1 collection error, caused by third-party pysbd invalid escapes under Python 3.13 and repository warning policy | Terminal output; no retained separate file | Failed |
| T-06 | Root | `& $uvExe sync --locked --python 3.11 --extra codex --group test` | Duration not retained | 0 | Recreated task-created environment after tests exited using existing Python 3.11.3; no lock/test/warning-policy changes | L/uv-sync-python311.log | Passed |
| T-07 | Root | B1 above under Python 3.11.3 | 30.70 s | 0 | 87 passed | L/backend-baseline-python311.log | Passed |
| T-08 | Frontend | `npm.cmd ci --no-audit --no-fund` | Duration not retained | 0 | 737 packages; original npm 10.8.1; existing deprecation notices | Terminal output | Passed |
| T-09 | Frontend | `npm.cmd run test:chat-model-selection`; `npm.cmd run test:chat-store-streaming` | Duration not retained | 0 each | Initial Node 20: 8 + 8 passed | L/test-chat-model-selection.log; L/test-chat-store-streaming.log | Passed |
| T-10 | Frontend | `npm.cmd run test:session-input`; diagnostic `node --experimental-detect-module --test tests/sessionInput.test.mjs` | Duration not retained | 1 each | Initial Node 20: 35 failures from ESM setup; diagnostic then failed in experimental mock-timer cleanup | L/test-session-input.log; diagnostic terminal output | Failed |
| T-11 | Frontend | `npm.cmd run test:chat-model-selection` | 217.4784 ms test-runner time | 0 | Selected Node 22: 8 passed | L/test-chat-model-selection-node22.log | Passed |
| T-12 | Frontend | `npm.cmd run test:chat-store-streaming` | 206.2427 ms test-runner time | 0 | Selected Node 22: 8 passed | L/test-chat-store-streaming-node22.log | Passed |
| T-13 | Frontend | `npm.cmd run test:session-input` | 3257.2103 ms test-runner time | 0 | Selected Node 22: 35 passed | L/test-session-input-node22.log | Passed |
| T-14 | Frontend | `npm.cmd run build` | Vite stage: 26.87 s Node 20 / 27.27 s Node 22 | 0 each | TypeScript/Vite passed on both; existing large-chunk/mixed-import warnings; ignored prebuild/build output | Terminal output; L/build-node22.log | Passed |
| T-15 | Root | Packaged Codex smoke check reproduced below | Duration not retained | 0 each | codex-cli 0.144.4 and app-server help available; no login/model execution | Terminal output | Passed |
| T-16 | Root | Documentation inspection: template headings/fields, UTF-8, local Markdown links, balanced fences, exact seven-principle comparison; `git diff --check` and scope inspection | Duration not retained | 0 | All seven numbered sections match each of the three task templates; required field/column coverage inspected; 15 Markdown files and 145 local links checked; seven principles unchanged. Follow-up DESIGN/PLAN rule links checked separately | Current documentation and terminal validation output | Passed |
| T-17 | Root | Packaged schema generation shown below, first stable then experimental | Duration not retained | 0 each | 337 JSON files after experimental generation; 122 distinct ClientRequest methods. Syntax evidence only; no live account/model turn | L/protocol-0.144.4/; L/protocol-0.144.4-fingerprints.json | Passed |
| T-18 | Root | Native setup-plan.ps1 -Json and setup-tasks.ps1 -Json with registered feature environment | Duration not retained | 0 each | Resolved native core templates and feature paths; no Git branch change. Drafts remain blocked on G1–G4 | Native feature artifacts; terminal output | Passed |
| T-19 | Root | Documentation audit: seven numbered-template comparisons; UTF-8/English, fences, whitespace, local links and contiguous task IDs; native check-prerequisites.ps1 -Json -RequireSpec -RequireTasks -IncludeTasks; git diff --check and branch/baseline/scope checks | Duration not retained | 0 | 15 Markdown files, 94 local links, seven matching template section sets and 33 unchecked task IDs; no detected issues. Native artifacts resolve; no extension hooks installed. Branch and recorded baseline unchanged; application source/locks unchanged | Current documents and terminal output | Passed |
| T-20 | Root | `.\.venv\Scripts\python.exe specs/AI4R-001-codex-subscription/verification/test_boundaries.py` | Test runner: 0.970 s; imports excluded | 0 | 13 offline characterization tests passed, including five counterexamples of unsafe defaults. Real installed adapter/SDK methods exercised with fake provider/workspace collaborators; not product acceptance | Terminal output; script SHA-256 in L/isolated-probe-ba5df305ece14a72bd0ad26d9dbb15b2/verified-files-sha256.json | Passed for characterization only |
| T-21 | Root | `.\.venv\Scripts\python.exe specs/AI4R-001-codex-subscription/verification/probe_app_server.py` | Tool-reported wall time 2.331 s | 0 | Two fresh-process cycles using one new isolated home: initialize, initialized, account/read(refreshToken=false). Account null both times; stdin EOF exits 0 and reader stops. Zero login operations/model turns | L/isolated-probe-ba5df305ece14a72bd0ad26d9dbb15b2/summary.json; verified-files-sha256.json | Passed for signed-out protocol/process scope |
| T-22 | Root | Updated-document heading/link/English/fence/whitespace audit; Python AST parsing; verified-file SHA-256 comparison; task checkbox and git diff --check/scope checks | Duration not retained | 0 | 14 Markdown files, 84 local links, five matching numbered-template sets; 33 original tasks unchecked, R001/R002 complete; script/evidence hashes unchanged; no issues | Terminal output; current records and manifest | Passed |
| T-23 | Root | `.\.venv\Scripts\python.exe -m unittest discover -s specs/AI4R-001-codex-subscription/verification -p test_*.py -v` | Runner 1.525 s; tool wall 7.881 s | 0 | Initial 27 passed: 13 characterization plus 14 protection/integration cases, including Node-generated allow/deny payloads consumed by Python | L/guard-prototype-20260928/python-initial.log | Passed for prototype scope |
| T-24 | Root | Same complete unittest discovery command as T-23 after adapter lifecycle review corrections | Runner 1.620 s; tool wall 7.593 s | 0 | 29 passed: 13 characterization and 16 protection cases. Added cancellation/stop waiter cleanup and foreign interaction-handler rejection checks | Terminal output; current scripts hashed in L/guard-prototype-20260928/verified-files-sha256.json | Passed for prototype scope |
| T-25 | Root | `& "$env:LOCALAPPDATA\ai4r-tools\node-v22.23.3-win-x64\node.exe" --test specs/AI4R-001-codex-subscription/verification/test_approval_frontend.mjs` | Runner 125.5316 ms | 0 | Eight passed: explicit decisions, duplicate clicks, ambiguous delivery, late ACK after session/signout change, invalid notices, stale errors, mismatched ACK, pending-request preservation | L/guard-prototype-20260928/frontend-initial.log | Passed; headless state/contract only |
| T-26 | Root | `.\.venv\Scripts\python.exe specs/AI4R-001-codex-subscription/verification/probe_app_server.py --guarded` | Tool wall 4.871 s | 0 | Two signed-out cycles through the prototype's direct curated launcher; initialized/account null; EOF exits 0; no login/model turn | L/guard-prototype-20260928/probe-initial.log; L/isolated-probe-880bfb1a786244e2b4b44a35dd3785d9/summary.json | Passed; local process scope |
| T-27 | Root | Template-heading, local-link, English/fence/whitespace audit; Python AST parsing; seven-script hash comparison; task checkbox, branch/baseline and git diff --check checks | Duration not retained | 0 | 15 Markdown files, 92 local links, six matching template section sets; seven script hashes unchanged; R001-R004 complete and original 33 tasks unchecked; no issues | Terminal output; current records and manifest | Passed |


| T-28 | Root | `& ./.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireSpec -RequireTasks -IncludeTasks` with registered feature environment; inspect requirements checklist and installed hooks | Duration not retained | 0 | Native paths resolve; 11/14 checklist items checked; three future gaps retained; no extensions.yml | Terminal output/native records | Passed for prerequisites only |
| T-29 | Root | `.venv/Scripts/python.exe -m unittest discover -s tests/unit_tests/runtime -p test_codex_subscription.py -v` before and after first implementation | Passing runner: 0.516 s | 1 initial / 0 later | Initial ModuleNotFoundError, loader error rather than executed cases; then nine passed | Terminal output | Red then passed |
| T-30 | Frontend | `npm run test:codex-subscription` | Final runner: 1.6668954 s | 1 initial / 0 final | Initial missing unbuilt component; final three actual React DOM cases passed with fake RPC | Terminal output; package.json command | Red then passed |
| T-31 | Root | `.venv/Scripts/python.exe -m pytest tests/unit_tests/runtime/test_codex_subscription.py tests/unit_tests/runtime/test_codex_integration.py --no-cov -q --log-cli-level=ERROR` | Final: 11.44 s | 2 collection attempt / 1 initial fixture / 0 final | Wrong fixture import corrected; history flush/isolation fixed; intermediate 13 passed; final 20 passed after all backend edits | Terminal output; M1 manifest | Passed; original failures retained |
| T-32 | Root | `.venv/Scripts/python.exe -m pytest tests/unit_tests/runtime/test_codex_subscription.py tests/unit_tests/runtime/test_codex_integration.py tests/unit_tests/agentserver/test_goal_history_bubble_parity.py tests/unit_tests/server/test_gateway_adapter.py --no-cov -q --log-cli-level=ERROR` | 21.44 s | 0 | 85 passed, one Authlib deprecation warning. Precedes final media_items rejection and login-attempt status projection; affected 20-case suite rerun in T-31 | Terminal output | Passed for stated tree |
| T-33 | Frontend | `npm run test:web-client-runtime-ack` | Runner: 0.1305472 s | 0 | Six existing ACK cases passed; does not directly test the new subscription wire branch | Terminal output | Passed |
| T-34 | Frontend | `npm run build` with documented Node22 PATH and output redirected to L/m1-frontend-build.log | Final Vite: 27.15 s | 0 | TypeScript and Vite passed after final frontend edits; existing large-chunk/mixed-import warnings | L/m1-frontend-build.log | Passed |
| T-35 | Root | `.venv/Scripts/python.exe specs/AI4R-001-codex-subscription/verification/probe_product.py` | Duration not retained | 0 | Two fresh signed-out production-service cycles; competing process owner rejected in each; owned processes closed. Zero login/model turns | L/m1-product-smoke-p1pqypua/summary.json | Passed for signed-out process scope |
| T-36 | Root | `.venv/Scripts/python.exe -m jiuwenswarm.codex_start --help` | Duration not retained | 0 | Explicit preview entry point accepts all/web/app; help does not start the app | Terminal output | Passed for CLI parsing only |
| T-37 | UI tool / frontend | CUA createBrowserTab('iab', local fixture URL), then listBrowsers(); temporary Vite fixture server started and stopped | Duration not retained | N/A | Browser unavailable, list empty; no rendered page or visual/browser test executed | Tool outputs; ignored local fixture | Blocked |

| T-38 | Root | Documentation audit of UTF-8/English, fences, local links and six numbered-template section sets; SHA-256 comparison with L/m1-code-sha256.json; `git diff --check`; `git branch --show-current`; `git rev-parse HEAD origin/ai4r_main_branch` | Duration not retained | 0 | 15 documents, 103 local links and six template section sets checked; no issues. All 25 M1 fingerprints unchanged; personal branch and HEAD/team baseline match. Git emitted line-ending normalization notices only | Terminal output; current files and manifest | Passed for recorded document/scope checks |


| T-39 | Root | `.venv/Scripts/python.exe -m jiuwenswarm.codex_start all` | Initial failure immediate; successful server warmup approximately 13-15 s | 1 initially; persistent service later | Initial interactive init raised EOFError; fixed with incremental prepare_workspace. Full startup then exposed native modality API probing, which is now skipped in subscription mode. Final preview HTTP200 and signed-out RPC verified | L/m1-full-startup.log; m1-full-startup-fixed.log; m1-full-startup-guarded.log; m1-preview.stdout.log and .stderr.log | Passed for final local startup; original failures retained |
| T-40 | Root | Local websockets client to ws://127.0.0.1:19000/ws with proxy=None; invoke codex.auth.status, config.get, session.list and signed-out chat.send | Duration not retained | 0 final | Initial client handshake timed out with inherited proxy; explicit loopback connection works. Account request initially got false unknown-method response; second forwarding set fixed. Final account state signed_out, subscription runtime config, session listing and SIGN_IN_REQUIRED rejection verified | Terminal output; startup routing log | Passed for actual socket/signed-out scope |
| T-41 | Root | `.venv/Scripts/python.exe specs/AI4R-001-codex-subscription/verification/probe_journey.py` | Duration not retained | 1 initial fixture attempts / 0 final | Real Gateway/AgentServer with test-only fake account/model: login/catalog, reply, rejected stale stop, confirmed stop, same-conversation follow-up, reconnect/history pass. Fixture errors corrected: work_mode, distinguishing Gateway ACK from runtime result, cursor and limit. All six user/assistant history records inspected, including stopped partial reply | L/m1-wire-run*.log; final L/m1-wire-hqdaqisd/summary.json, agent.log, gateway.log and isolated history | Passed; synthetic provider only |
| T-42 | Root | Real local socket RPC sequence codex.auth.status -> codex.auth.login -> codex.auth.status -> codex.auth.cancel with exact returned login_attempt_id | Duration not retained | 0 | Real App Server generated official HTTPS login link, reported signing_in, and cancelled back to signed_out. No sign-in completion/model request. URL/code not printed or retained in report | Terminal result; managed local profile | Passed for real login initiation/cancellation only |
| T-43 | Root | Same four-suite pytest command as T-32 on journey integration changes | 18.59 s | 0 | 89 passed, one existing Authlib warning; precedes final pre-start-ACK cancellation wait correction | L/m1-journey-regression.log | Passed for stated version |
| T-44 | Root | Same two-suite pytest command as T-31 after final early-cancel correction | 14.48 s | 0 | 25 passed, including early cancel waits for correlated terminal and same-session continuation after stop | L/m1-journey-final-backend.log | Passed |
| T-45 | Frontend | `npm run test:codex-subscription`; `npm run test:web-client-runtime-ack` with Node22 PATH | 1.731264 s / 0.1267588 s | 0 each | Five subscription tests (three React DOM, two WebClient wire/state), six ACK regressions pass. New wire cases check signed-out admission, selected model and exact per-session cancellation target | Terminal output; reproducible package scripts | Passed; no real browser rendering |
| T-46 | Frontend | `npm run build` with Node22 PATH | Vite 29.12 s | 0 | TypeScript/Vite pass; existing chunk/import warnings only | L/m1-journey-frontend-build.log | Passed |
| T-47 | UI tool | CUA getState; open_in_codex browser http://localhost:5173 | Duration not retained | N/A | No connected app/browser automation surface; opening app panel queued. No visual QA. User agreed to complete personal sign-in and notify the assistant; completion pending | Tool results/current conversation | Blocked for visual/live acceptance |
| T-48 | Root | `.\.venv\Scripts\python.exe -m pytest tests/unit_tests/runtime/test_codex_subscription.py tests/unit_tests/runtime/test_codex_integration.py --no-cov -q --log-cli-level=ERROR` | 12.96 s | 0 | 26 passed after the real preview exposed a missing goal-status method. Read-only goal polling returns an empty snapshot; goal mutations are rejected without provider calls. The running preview has not been restarted, to preserve the user login flow | L/m1-goal-poll-regression.log; L/m1-goal-poll-code-sha256.json | Passed for fixture scope; running preview still uses pre-fix backend |
| T-49 | User browser | Xiaoyang's explicit message accepting localhost:5173 and directing publication to main plus four child branches | Not recorded | N/A | User acceptance of the running M1 demo and direct publication authority. No independent function review, exact browser-case transcript or full AC pass inferred | TASK Section 4; current conversation | Accepted by user for M1 |
| T-50 | Root | `.\.venv\Scripts\python.exe -m pytest tests/unit_tests/runtime/test_codex_subscription.py tests/unit_tests/runtime/test_codex_integration.py tests/unit_tests/agentserver/test_goal_history_bubble_parity.py tests/unit_tests/server/test_gateway_adapter.py --no-cov -q --log-cli-level=ERROR` | 20.10 s | 0 | 91 passed, one existing Authlib warning; includes the latest goal-poll compatibility correction | C; L/release-backend.log | Passed |
| T-51 | Root | `.\.venv\Scripts\python.exe specs/AI4R-001-codex-subscription/verification/probe_journey.py` | Not retained | 0 | Real Gateway/AgentServer with synthetic provider: login/chat, stale-stop rejection, confirmed stop, continued chat, reconnect and retained history | C; L/release-journey.log; L/m1-wire-c38ru1_x/summary.json | Passed for fixture scope |
| T-52 | Frontend | `npm.cmd run test:codex-subscription` with Node 22.23.3 on PATH | 1.885 s runner | 0 | Five tests passed | C; L/release-frontend.log | Passed |
| T-53 | Frontend | `npm.cmd run build` with Node 22.23.3 on PATH | 31.15 s Vite stage | 0 | TypeScript and production build passed; existing chunk/import warnings retained | C; L/release-build.log | Passed |

### M1 evidence boundaries

The historical M1 manifest identifies 25 files; the current journey manifest identifies 32 files; documentation edits after these checks do not establish new runtime evidence. The initial facade history test failed because asynchronous persistence had not been flushed. Its metadata collaborator also used the default root: one synthetic fixture-session directory containing only metadata.json was inspected and moved reversibly to L/m1-test-metadata-isolation. Both fixture roots are now temporary and final tests pass. No pre-existing user data was removed.

Self-review also corrected rejected stale cancellation reaching the facade's outer cancel and old-stream cleanup closing a replacement transport after logout. Dedicated regression fixtures pass. The real process probe tests the production transport/service, not the whole app launcher or browser-to-gateway journey. T-39-T-42 now establish startup, real socket routing, synthetic journey and actual login initiation/cancellation. Browser and actual account/model validation remain required M005/M006 work. No browser automation surface was available. M1 requires an explicit launcher; the legacy launcher/settings and broader capability paths remain, so FR-002 and AC-08 are not satisfied.

Schema generation used the packaged binary, with the destination derived from L:

```python
from pathlib import Path
from codex_cli_bin import bundled_codex_path
import os, subprocess
out = Path(os.environ["LOCALAPPDATA"]) / "ai4r-tools/evidence/AI4R-001/protocol-0.144.4"
for flags in ([], ["--experimental"]):
    subprocess.run([str(bundled_codex_path()), "app-server", "generate-json-schema",
                    "--out", str(out), *flags], check=True, capture_output=True, text=True)
```

Pinned SDK/harness and application call sites were inspected as recorded in research.md. Two bounded AI document reviews identified and corrected an unsupported harness pause claim, missing durable account identity/generation reconciliation, an inconsistent test path, and model-execution proof scheduled before its adapter. These were design-document reviews, not the SOP's final implementation review or successful capability tests.

Packaged Codex smoke check used the following Python operations through `.venv\Scripts\python.exe` (stdout/stderr captured and exit codes checked):

```python
from codex_cli_bin import bundled_codex_path
import subprocess
binary = str(bundled_codex_path())
for args in [["--version"], ["app-server", "--help"]]:
    result = subprocess.run([binary, *args], text=True, capture_output=True, timeout=20)
    print(result.stdout)
    if result.returncode:
        raise SystemExit(result.returncode)
```

The portable Node archive was downloaded from the official distribution and its SHA-256 matched the official list before extraction; URL and checksum are in ENVIRONMENT. No global Node change occurred. Initial Spec Kit staging generated 30 files in a fresh directory before adoption; original asset hashes and the deliberate constitution change are in SPEC_KIT_SETUP.json. Coverage measurement was disabled for B1; no coverage percentage is claimed.

### Historical bounded verification findings (R001/R002)

- Five counterexamples are confirmed in pinned dependencies: automatic approval by default; empty approval object interpreted as allow; stale answer forwarded as provider input; SDK re-inherits a fabricated parent key despite the harness's curated environment; absent private approval hook merely warns. These passing characterization tests demonstrate defects to guard against, not successful product protections.
- Explicit denial and cancellation return DENY; duplicate pending IDs are rejected; distinct adapter instances maintain separate pending requests; a final snapshot does not duplicate streamed text. This does not prove application routing or end-to-end isolation.
- Codex running-state pause is unsupported. Dynamic tool requests are declined by the generic IO adapter. The injected leader-runtime seam returns the supplied runtime and skips native construction/memory; workspace helpers were mocked, so real leader coordination/rails remain unproven.
- The real-process probe used a new CODEX_HOME and workspace, file-only managed auth storage, allowlisted child environment and pinned binary SHA-256 `51398051c2332b6afe08dc3b9dbb4056085c197f35ca57a307ee303d450cada5`. It neither read/copied credentials nor called login, thread/start or turn/start. Evidence directories are retained; no user profile was deleted.
- G1-G4 remain open. These results justify concrete adapter requirements, not full feasibility or any active AC pass. Production source, existing tests and dependency locks remain unchanged; only isolated verification scripts and records were added/updated.

### Historical guard prototype and frontend contract (R003/R004)

The approved isolated prototype requires exact boolean decisions, matching execution/session/thread/turn/account generation, call/request IDs and an opaque one-use ticket. It rejects stale/duplicate/malformed replies before they can enter provider input. Closing the broker denies pending approvals. The adapted IO boundary rejects InteractiveInput on its chat path and rejects foreign interaction handlers. A strict pinned SDK hook check blocks a supplied start callback when the hook is missing.

The direct launcher passes an allowlisted environment to the actual process. Tests inspect its Popen boundary and run a real Python child proving fabricated provider keys, base-URL, Python path and Codex overrides are absent. The real App Server probe uses that launcher. This does NOT yet integrate the full Codex SDK/harness through the guarded transport; the original SDK.start inheritance behavior is unchanged.

Frontend coverage is a headless controller and actual Node-to-Python JSON contract exercise. It covers approval button enablement state, duplicate dispatch suppression, scoped payloads, late responses and honest delivery_unknown/expired/signed_out states. No React component, rendered button, settings layout, locale text, browser interaction, gateway authentication or WebSocket end-to-end behavior was tested. Real UI work remains T010/T013/T025/T027 and visual checks remain required.

Review corrections: explicit adapter cancel/stop delegation and rejection of an externally supplied interaction handler were added after the first run, then all Python tests reran in T-24. Frontend files and direct launcher logic did not change in that correction; T-25/T-26 remain applicable to those paths. Original R001 tests deliberately still pass as counterexamples; they do not imply installed dependencies were fixed. Human function review and final implementation review remain pending.

## 4. Coverage selected by risk (record status or explain N/A for each row)

| Scope | Related commands / cases | Status and reasoning |
| --- | --- | --- |
| Normal path for changed behavior | T-30/T-31/T-35 | Mocked account/stream/history and real signed-out process pass; signed-in product journey pending |
| Original defect reproduction and post-fix regression | T-29-T-32; review R-01-R-03 | Initial failures and stale-control/logout cleanup fixes retained; final affected tests pass |
| Boundaries, exceptions, and state after failure | T-30/T-31 | Account rejection, stale/duplicate control and late events covered; complete failure/recovery matrix pending |
| Callers and module integration | T-31/T-32/T-39-T-42 | Full launcher and real socket routing now exercised; synthetic provider journey passes; actual signed-in model and browser journey pending |
| Types, static checks, and build | T-46 | TypeScript/Vite pass; browser rendering and supported-browser compatibility pending |
| Relevant regression scope | T-32/T-33 plus historical baseline | Selected 89 backend and six ACK cases; latest affected 26 backend and five frontend cases. Overlapping suites must not be summed as unique coverage |
| Data compatibility, migration, and rollback | T-31; CR-01 | Legacy migration N/A; fresh-profile preservation fixture passes; restart continuation and full rollback journey incomplete |
| Permissions, data handling, or external service constraints | T-31/T-35 | Curated child environment, subscription-only account checks and ownership lock; no live model or full outbound audit |

## 5. Performance and research evaluation (required when applicable)

- Performance relevance: migration may affect latency/cost/capability; plan Section 7 proposes a fixed-fixture method, but no performance threshold or improvement is approved or measured.
- Fair comparison: no performance experiment conducted; unit-test/build durations are execution evidence, not an application benchmark.
- Variability handling: no repeated performance samples; insufficient evidence for any performance conclusion.

| Metric | Approved threshold / maximum allowed regression | Baseline measurement | Current measurement | Unit / sample size | Meets requirement? | Original records |
| --- | --- | --- | --- | --- | --- | --- |
| Subscription runtime latency/cost/quality, if applicable | Proposed plan method; no approved threshold invented | Not measured | Not measured | No samples | Unable to determine | No performance record |

## 6. Missing checks, failures, and risks (required)

| Unmet item | Cause and impact | Interim measure | Owner / deadline | Human decision and evidence |
| --- | --- | --- | --- | --- |
| Initial Python 3.13 and Node 20 baseline failures | Dependency/runtime compatibility; other runtime combinations remain unverified | Selected Python 3.11.3/Node 22 verified; preserve original failures | Xiaoyang / resolve other-runtime support during design | User authorized setup; no waiver of future supported-platform coverage |
| Capability equivalence | G1-G4 and C01-C20 remain incomplete; M1 is only login/basic chat | Keep whole-project tasks and AC-08 open; tools/media are explicitly rejected in M1 | Xiaoyang / before acceptance | Bounded implementation authorized; no acceptance waiver |
| Browser and live account | Startup and synthetic socket journey pass; no browser available; personal sign-in absent | Finish M005 visual verification and M006 personal sign-in; synthetic provider does not establish live model behavior | AI for available integration work; Xiaoyang for sign-in / before acceptance | No check deferral or final approval |
| Restart recovery and shared transport | Restart rejects old-thread continuation; failure closes shared process and can stop other streams | Preserve history and state limitations; resolve AC-07 before acceptance | Xiaoyang / before acceptance | No change to spec threshold |
| Legacy/default UI and feature conversion | M1 is opt-in; legacy settings/launch paths remain | Continue planned complete replacement; no FR-002 completion claim | Xiaoyang / before delivery | No scope reduction |
| Full-suite and performance coverage | Selected risk-based fixtures only; no application benchmark | Complete remaining required checks without claiming full coverage | Xiaoyang / before final verification | No performance claim |
| Independent human review and delivery | Reviewer unassigned; no implementation commit or final integration tree | Record bounded AI review now; arrange independent final review at delivery | Xiaoyang / before final review | No fabricated approval, push, PR or merge |

## 7. Version changes and conclusion (required)

Design update: plan/tasks v0.3 register the authorized M1 product milestone; directive v0.9 and runtime contract v0.3 describe its implemented subset and remaining gaps. Spec v0.2 and its thresholds are unchanged. CR-01 still retires AC-05 only.

- Changes after C and verification: M1 code/configuration/tests plus earlier research/SOP work are uncommitted; 32 current files fingerprinted in L/m1-goal-poll-code-sha256.json. Later explanatory records update measured results, traceability and limitations. They do not waive acceptance.
- Baseline changes after B: fresh fetch this turn matches recorded B; check again before delivery.
- Revalidation record: T-48 covers the subsequent goal polling compatibility correction. The live preview remains on the pre-correction backend until login completes; no deployment of that correction is claimed. T-44 final affected backend, T-45 frontend and T-46 build follow affected edits; T-43 broad regression precedes only the early-cancel wait correction covered in T-44. T-41 socket journey precedes that correction; its already-started-turn path is behaviorally unchanged. Suites overlap; do not sum counts as unique coverage.
- Verification conclusion: **Partially passed**. M1 implementation exists and bounded fixtures/build/signed-out probe pass. Full product and subscription acceptance remain incomplete.
- Behavior established by evidence: scoped account state fixtures, stream/session identity, facade history persistence, stale cancellation and logout ownership protections, React login/failure states, owned signed-out App Server lifecycle.
- Behavior not yet established: browser journey, personal account model execution, complete account/quota recovery, restart continuation, tools/team/auxiliary/media/platform parity and performance.
- Follow-up actions: finish M005 browser verification, execute M006 with personal sign-in, continue broader capability tasks and independent review/delivery gates. See [review.md](review.md) for bounded findings and human pending states.

Passing fixtures or builds is not approval to merge. Implementation progress belongs in native tasks.md and live task state in CURRENT_STATUS.

Current handoff: latest preview is running on loopback Web UI http://localhost:5173; read-only status is signed_out. Start-Codex.cmd is an additional convenience launcher, not a second running instance. Personal sign-in is required to establish real replies/quota behavior. User data and credentials are not copied into test fixtures. No remote push or commit in this stage.

### Accepted demo publication record (2026-09-28)

Implementation C is `97c1bd6930497c2a97cedeca82c49b62650b56c8`; baseline B remains `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483`. T-50–T-53 are the final post-commit checks. Xiaoyang's T-49 acceptance authorizes direct fast-forward publication to the five team branches; broader AC gaps and independent-review limitations remain. No credentials, runtime profile, node_modules or virtual environment are included. The goal-poll fix has regression evidence but was not loaded into the user's pre-acceptance backend process. Later commits contain publication records only. See [HANDOFF](HANDOFF.md) and [CODEX_DEMO](../../code/CODEX_DEMO.md).

Publication confirmation: atomic push of `295470d6d9f07cc3d81fe674e118abd453405ef1` succeeded to all five specified team refs. Read-back with `git ls-remote` matched all five SHAs. Local loopback Web UI HTTP status was 200. Later changes are publication records only; post-commit code verification T-50–T-53 remains applicable.
