# AI4R Subscription Runtime Contract

Version: 0.3 | M1 subset implemented in the uncommitted personal-branch tree; broader interfaces below remain proposed.
Template: [CONTRACT_TEMPLATE](../../../docs/code/code_sop/templates/CONTRACT_TEMPLATE.md).

## 1. Contract control (required)

| Field | Value |
| --- | --- |
| Contract identifier / document version | AI4R-CODEX-RUNTIME / 0.3 |
| Status | M1 implementation contract; later capabilities proposed |
| Provider / owner | Proposed backend codex_subscription service / Xiaoyang; module assignment confirmation pending |
| Consumers / owners | Gateway/frontend, AgentAdapter, team/scheduler and auxiliary services / Xiaoyang coordinates confirmations |
| Code entry point | Proposed service.py/session.py/text.py in jiuwenswarm/server/runtime/codex_subscription/; gateway proxies in app_web_handlers.py |
| Design / ADR | plan.md v0.1 / ADR-0001 v0.1, both proposed |
| Verified code SHA | M1 is uncommitted; use TEST_REPORT hash manifest; baseline evidence at dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 |
| Compatibility classification | New subscription RPCs plus breaking operational provider-policy change for the fresh-profile distribution; existing chat envelope retained |

## 2. Responsibility and preconditions (required)

- Behavior provided: managed account state, model catalog, subscription-only execution admission, scoped interaction/control and consistent application events.
- Caller preconditions: existing application transport authorization remains valid; selected profile/workspace is local and authorized; execution requires ready ChatGPT access.
- Provider guarantees: no API-key/provider fallback; identity checked before control; sanitized outputs; one active turn per binding; explicit unknown completion on ambiguous failure.
- Non-guarantees: login/catalog success does not guarantee quota or feature support. No embeddings/media equivalence, universal exactly-once external effects, or production approval is implied.

## 3. Inputs (required)

Proposed RPC method names below operate through the existing application request envelope. The gateway maps transport IDs to these normalized fields; it must not replace the established chat ACK protocol.

| Field / parameter | Type / schema | Required / default | Units, range, and constraints | Missing / null / invalid handling |
| --- | --- | --- | --- | --- |
| method | string | Required | codex.auth.status, codex.auth.start_login, codex.auth.cancel_login, codex.auth.logout, codex.models.list | Reject unknown operation |
| request_id | opaque non-empty string | Required for mutations | Scoped to caller/profile; retries reuse the same request | Reject invalid; duplicate returns known receipt |
| login_type | enum chatgpt or chatgptDeviceCode | start_login; default chatgpt | No apiKey or external-token login accepted | Unsupported -> INVALID_ARGUMENT |
| login_attempt_id | opaque string | cancel_login required | Must match caller's current attempt and generation | Stale -> STALE_OPERATION |
| session_id / execution_id | opaque strings | Execution/control required | Existing application identity, not frontend-selected arbitrary Codex thread IDs | Unknown or wrong owner -> INVALID_TARGET |
| expected_execution_id / interaction_id | opaque strings | Control/answer required | Must match active execution and pending interaction | Stale -> STALE_OPERATION; no other run affected |
| content / attachments / model / effort | Existing chat types | Existing chat requirements | Validate against admitted capability/catalog; no raw provider/base URL/key overrides | Unsupported -> UNSUPPORTED_CAPABILITY or INVALID_MODEL |
| decision / answers | Allowed decision enum or structured answer | Interaction response required | Only offered choices; attached to current pending request | Invalid -> INVALID_ARGUMENT; do not auto-approve |
| tool arguments | JSON matching registered schema | Tool-specific | Server supplies session/workspace identity; no authority from model-supplied path/session | Reject schema or permission violation |
| text-service input / output_schema | bounded text/transcript and optional JSON schema | Auxiliary request required | No tools by default; reject unsupported model parameters explicitly | Validation error, not silent parameter dropping |

Strings use UTF-8; timestamps use UTC ISO 8601. Relative tool paths resolve only beneath the authorized workspace. Reject unexpected key/provider/auth-token fields even if other unknown additive metadata is tolerated by existing transport.

### M1 implemented subset

The following table is authoritative for M1. The original broader proposal tables describe future work and must not be mistaken for shipped methods/guarantees. All methods reuse authenticated Gateway forwarding and existing AgentRequest/AgentResponse envelopes.

| Method / field | Input | Result | Failure / caller handling |
| --- | --- | --- | --- |
| codex.auth.status | No credentials | enabled, state, plan, error, active_runs, login_attempt_id | Readiness is not a quota guarantee; runtime failures are sanitized |
| codex.auth.login | No credentials; browser-managed ChatGPT only | signing_in, auth_url, login_attempt_id | LOGIN_PENDING or BUSY; no token passthrough and no automatic retry |
| codex.auth.cancel | Exact login_attempt_id | Sanitized current status | STALE_OPERATION leaves a newer login unchanged |
| codex.auth.logout | No credentials | Sanitized status after process shutdown and managed logout | Unknown failure is visible; old bindings remain invalid |
| codex.models.list | Signed-in account | models: id, name, default | Safe error; no legacy catalog fallback |
| chat.send | Existing session/content/mode plus optional codex_model | Existing chat.delta/final/error; facade owns application history | Text-only supported modes; explicit MILESTONE_TEXT_ONLY for unsupported equipment/media/modes |
| chat.interrupt | Existing session/intent=cancel plus target_request_id | Scoped interruption request acknowledged | STALE_OPERATION does not cancel another facade task; terminal outcome remains a stream concern |

Error codes currently include SIGN_IN_REQUIRED, SUBSCRIPTION_REQUIRED, PROFILE_IN_USE, PROFILE_CONFIG_CONFLICT, RUNTIME_UNAVAILABLE, RUNTIME_VERSION_MISMATCH, RUNTIME_DISCONNECTED, RUNTIME_ERROR, DELIVERY_UNKNOWN, RUNTIME_TIMEOUT, TURN_FAILED, CANCELED, BUSY, LOGIN_PENDING, LOGIN_FAILED, LOGIN_PROTOCOL_ERROR, INVALID_INPUT, STALE_OPERATION, NEW_SESSION_REQUIRED and ACCOUNT_IDENTITY_UNAVAILABLE. The UI currently uses a general recoverable connection/action message for account errors; complete quota/error-specific presentation remains an acceptance gap.

Bindings contain only session/thread IDs, an account-email hash and a process epoch. Since pinned account/read cannot prove workspace identity, process restart/logout invalidates continuation; saved application history remains readable. A process-level failure affects all active streams sharing that process. No resume, device-code login, tool approval, team/media parity or transparent retry is claimed in M1. URLs are transient initiating-UI data; dev WS logging stores no message bodies.

M1 cancellation refinement (v0.3): Gateway preserves target_request_id and leaves stream consumption active. A successful stop waits for the correlated provider terminal notification, including an interrupt requested before turn/start acknowledgment. The final event carries cancelled=true and partial content; the existing facade persists it. The UI accepts chat.interrupt_result only after actual success and preserves ongoing state on rejection. Same-process subsequent ordinary turns remain usable; restart identity remains the separately documented gap.

## 4. Outputs and side effects (required)

| Field / return value | Type / schema | Meaning and constraints | Behavior when no result exists |
| --- | --- | --- | --- |
| status / generation | Sanitized AccountConnection fields | Current account state and fence; no raw tokens | signed_out/runtime_unavailable rather than fabricated ready |
| login instructions | Attempt ID and browser URL or device verification URL/code | Short-lived response to initiating client only; omit from logs/persistent store | Explicit login error/canceled |
| models | Catalog of admitted IDs and supported reasoning settings | Derived from selected runtime/account, not IDE defaults | Empty with actionable error; never inject API model fallback |
| chat events | Existing chat.delta/final/tool_call/tool_result/error/processing_status and interaction forms | Preserve session, execution and agent association; bind provider thread/turn internally | No final success until terminal success confirmed |
| runtime error | Stable code plus safe message/recovery action | Fields suitable for UI and logs; raw upstream error not blindly forwarded | Explicit unknown/interrupted state if ambiguous |
| text-service result | Validated text/JSON plus available usage metadata | No invented cost or empty-success fallback | Typed error; invalid JSON is failure |

- Side effects: local App Server processes, managed auth, thread storage, application history and explicitly permitted tools/network requests.
- Ordering/determinism: preserve order per binding; no global ordering across conversations. Deduplicate by execution/item identity; model output is not deterministic.
- Resource ownership: backend lifecycle owner closes control client/workers/MCP and invalidates pending requests on logout/shutdown.

## 5. Error and failure semantics (required)

| Error condition | Representation / type / code | Observable result and side effects already incurred | Retry allowed and conditions | Caller responsibility |
| --- | --- | --- | --- | --- |
| Missing/incompatible binary | RUNTIME_UNAVAILABLE / INCOMPATIBLE_RUNTIME | Execution not admitted | Retry after repair/version validation | Show setup guidance |
| No valid subscription account | AUTH_REQUIRED / AUTH_EXPIRED | No new model run; prior run outcome retained | User signs in; no automatic API fallback | Preserve input/history |
| Quota refusal | QUOTA_LIMITED | Report provider refusal and safe reset information if supplied | Only explicit later retry | Do not claim fixed allowance or buy credits |
| Transport/runtime lost mid-turn | EXECUTION_UNKNOWN | Partial output/effects may exist | Reconcile thread before any continuation; no blind replay | Show interrupted state |
| Stale cancel or decision | STALE_OPERATION | No effect on newer run | Refresh state; new request only for intended run | Never apply to active run by convenience |
| Denied/unsupported tool | PERMISSION_DENIED / UNSUPPORTED_CAPABILITY | No host tool execution | Only after valid policy/capability change | Explain failure, do not fabricate result |
| Invalid auxiliary schema/controls | INVALID_OUTPUT / UNSUPPORTED_PARAMETER | No valid result supplied | Bounded validation retry only without side effects | Surface failure to caller |

Operational timeout and reconnection defaults are in plan §4. Server requests are not ordinary notifications: each approval/question must receive exactly one valid response or an explicit cancellation. Tool side effects need receipts and reconciliation. Control calls are idempotent by scoped request ID; model turns are not assumed inherently idempotent.

## 6. Compatibility, versions, and migration (required)

- Version currently in use: first introduction; current OpenAIAccount RPC path remains baseline evidence only.
- Differences: managed App Server login/catalog, strict subscription provider policy, bound control identities and sanitized auth messages.
- Affected consumers: frontend settings/onboarding/chat, gateway control, main/code adapter, team leader/members, scheduler and auxiliary consumers in research C01–C20.
- Migration steps and executors: legacy data/configuration migration N/A under CR-01. Implementation replaces operational callers/defaults for the fresh distribution; no old data conversion.
- Activation/rollback: activate after G1–G4, approved design and acceptance; keep separate persistent profile. Failure stops admission; no silent reactivation of key providers.
- Deprecation: old model-key setup is removed from the shipped flow; exact source cleanup is implementation work, not a promise to support old RPC consumers.

## 7. Examples and executable verification (required)

Expected normalized examples, not executed wire traces:

```json
{"method":"codex.auth.start_login","request_id":"login-1","login_type":"chatgpt"}
{"state":"login_pending","generation":1,"login_attempt_id":"attempt-1","auth_url":"https://example.invalid/expected-login-only"}
```

The example URL is deliberately nonfunctional; the actual URL comes only from managed runtime login.

| ID | Input / initial state | Expected output / error / state | Test path and test name | Design acceptance criterion |
| --- | --- | --- | --- | --- |
| CT-01 | Signed-out fresh profile; start login | Pending instructions for initiating client; ready only after matching completion and account read | To add: tests/unit_tests/gateway/test_codex_subscription_handlers.py::test_login_generation | AC-01/06 |
| CT-02 | Old login completes after logout | Remains signed out; generation unchanged by stale callback | To add: runtime/test_codex_lifecycle.py::test_logout_wins | AC-04/07 |
| CT-03 | Decision/cancel targets another execution | STALE_OPERATION; no execution elsewhere | To add: runtime/test_codex_session_adapter.py::test_stale_control | AC-03/07 |
| CT-04 | Parent env contains model key and custom provider config | Child policy rejects/removes them; no outbound legacy request | To add: runtime/test_codex_subscription_policy.py::test_contaminated_environment | AC-06 |
| CT-05 | Duplicate host tool call with ambiguous response | Existing receipt reconciled; no automatic duplicate effect | To add: runtime/test_codex_tool_bridge.py::test_duplicate_dispatch | AC-03 |

Test paths abbreviated after the first row share tests/unit_tests/. Actual results belong only in TEST_REPORT.

## 8. Contract approval and activation (required)

| Document version | Decision-maker / role | Decision and scope | Time and time zone | Evidence location | Effective SHA |
| --- | --- | --- | --- | --- | --- |
| 0.1 | Xiaoyang / Lead | Pending | Pending | plan §8 | Not effective |
| 0.1 | Consumer owners, assignment coordinated by Xiaoyang | Pending confirmation; no independent assignment invented | Pending | TASK owner register | Not effective |

## 9. Change log (required when changes occur)

| Version | Behavior change | Compatibility impact | Design / ADR | Renewed approval required? |
| --- | --- | --- | --- | --- |
| 0.2 | Register actual M1 methods and honest restart/control/error limits | New staged entrypoint; no change to whole-project ACs | plan v0.2 M1 | User authorized the presented milestone; this records implementation detail, not unseen human review |
| 0.1 | Initial proposed boundary | New RPC and subscription-only policy | plan v0.1 / ADR-0001 | Initial approval required |
