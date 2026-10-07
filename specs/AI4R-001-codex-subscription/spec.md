> **Historical AI4R-001 record:** identities, decisions and observations below retain their original scope. Current M1 design and registration use the repository design-package and M1 TASKS; old review/approval cards do not govern new v2 work.

# Feature Specification: Personal Codex Subscription Runtime

**Feature Branch**: `ai4r_xiaoyang`

**Feature Directory**: `specs/AI4R-001-codex-subscription/`

**Created**: 2026-09-28

**Version / Status**: 0.2 / Requirements confirmed by Xiaoyang; technical design approval remains separate

**Input**: Xiaoyang requests Codex App Server integration across the frontend and backend so the entire project operates through a Codex subscription instead of model-provider API keys. Each person runs the application locally and signs in with their own account. Xiaoyang is the author and Code Team Lead and requests the Spec Kit workflow.

## User Scenarios & Testing

### User Story 1 — Start without a model API key (Priority: P1)

A person installs or opens JiuwenSwarm on their own computer, signs in to their ChatGPT account, and can see whether Codex subscription access is ready.

**Why this priority**: All other work depends on usable account access without an API-key setup requirement.

**Independent Test**: In an isolated clean application profile with no model-provider API keys, complete sign-in, inspect account readiness, restart the application, then sign out.

**Acceptance Scenarios**:

1. **Given** a signed-out local profile, **when** the person starts onboarding, **then** they can sign in without entering a model-provider API key (AC-01).
2. **Given** valid subscription access, **when** the person restarts the app, **then** the account state is restored or an actionable sign-in prompt appears; no key fallback is attempted (AC-01, AC-04).
3. **Given** a signed-in profile, **when** the person signs out, **then** subsequent model work requires sign-in and the app stops representing the account as ready (AC-04).

### User Story 2 — Complete existing work using the subscription (Priority: P1)

A person uses existing chat, agent, and project workflows with visible progress, results, tool interactions, and saved conversations, without configuring a separate model service.

**Why this priority**: The requested outcome concerns the whole project's operation, not just an additional login button or one successful chat response.

**Independent Test**: Execute the baseline capability inventory using a subscription account in a profile without model-provider keys; map each capability to observable evidence.

**Acceptance Scenarios**:

1. **Given** a ready account, **when** a user submits a task, **then** streamed progress and a final result appear in the correct session (AC-02).
2. **Given** a task needing supported tools, permissions, or user input, **when** that interaction occurs, **then** the user can respond and execution resumes correctly (AC-03).
3. **Given** multiple local conversations or team tasks, **when** they run or resume, **then** results, cancellation, and history remain associated with the correct conversation (AC-03, AC-07).

### User Story 3 — Recover and migrate without hidden API use (Priority: P1)

Users start with a fresh application profile, without importing legacy settings, projects, or conversations. They receive useful messages when authentication, subscription availability, connectivity, or the local runtime prevents execution.

**Independent Test**: Start with a fresh application profile; exercise expired access, quota exhaustion, offline operation, cancellation, and runtime restart without any successful fallback to a key-based provider.

**Acceptance Scenarios**:

1. **Given** a fresh application profile, **when** the app opens for the first time, **then** subscription onboarding requires neither legacy configuration nor a model-provider API key (AC-01, AC-06).
2. **Given** an unavailable or expired account or exhausted subscription allowance, **when** work is requested, **then** the failure is explicit and the app gives a recovery action without charging a different provider (AC-04, AC-06).

### Edge Cases

- Login canceled, account changed, expired authorization, subscription access unavailable, or quota exhausted.
- Missing Codex executable, incompatible runtime version, runtime crash, network interruption, and restart during a turn.
- Concurrent sessions, interrupted tool approvals, canceled turns, and reconnects without duplicate actions.
- First-run setup is interrupted; subsequent restarts must retain conversations created in the new application profile.
- A capability depends on embeddings, media generation, speech, or external search that has not yet been mapped to an equivalent subscription-supported workflow.

## Requirements

### Functional Requirements

- **FR-001**: Users MUST operate with their own account on their own machine; this task MUST NOT create a shared-account server.
- **FR-002**: The shipped model-execution path MUST use the user-selected Codex App Server integration with subscription authentication. Adding another optional provider while leaving key-based execution as the operational default does not meet the objective.
- **FR-003**: Onboarding and settings MUST expose sign-in, sign-out, readiness, and actionable failures without requiring a model-provider API key.
- **FR-004**: Existing chat, agent/tool, team, background, memory/retrieval, and media-related capabilities MUST be inventoried and assessed before the design claims whole-project coverage. Missing equivalence MUST remain an explicit gap; no feature may be silently removed or declared supported.
- **FR-005**: Streaming, task completion, errors, user interactions, cancellation, and history MUST retain correct session association.
- **FR-006**: The application MUST support a fresh first-run experience without importing legacy configuration, projects, or conversations. Legacy-data migration and migration records are out of scope. Authentication failure MUST NOT trigger API-key fallback. Fresh first-run behavior MUST NOT reset newly created data on subsequent launches or automatically delete pre-existing local data.
- **FR-007**: Account credentials MUST stay in the supported local authentication mechanism; frontend state, ordinary logs, version control, and documentation MUST NOT contain usable credentials.
- **FR-008**: Required tests MUST include protocol/lifecycle checks, settings and session behavior, fresh-profile initialization, failure paths, and real local subscription validation. Native task generation MUST retain these verification tasks.
- **FR-009**: A successful main-chat demonstration MUST NOT establish that every project capability works. Whole-project completion requires the capability evidence defined by AC-08.

### Key Entities

- **Local account connection**: one person's subscription sign-in, readiness, failure state, and lifecycle on their machine.
- **Project conversation**: session identity, history, task progress, interactions, and results created in the new application profile.
- **Runtime operation**: running, waiting for input/approval, completed, canceled, or failed work tied to a conversation.
- **Capability coverage entry**: existing user behavior, its current dependency, intended subscription behavior, and verification evidence or an unresolved gap.

## Success Criteria

Xiaoyang confirmed spec v0.2 in the current conversation before requesting the design. These acceptance definitions govern design and testing; no acceptance test has run yet.

| ID | Observable outcome | Verification and pass condition |
| --- | --- | --- |
| AC-01 | A new local user can reach a signed-in ready state without a model-provider API key | Clean-profile sign-in/restart scenario passes with all such key settings absent |
| AC-02 | A user receives streamed output and a final result in the selected conversation | End-to-end task records show progress, final state, and correct history; no other session receives its output |
| AC-03 | Tool interactions, user decisions, and cancellation remain usable | Controlled interaction scenarios complete, decline, or cancel as requested without duplicate actions |
| AC-04 | Unavailable authentication, quota, network, or runtime produces an honest recoverable state | Each named failure fixture displays the correct state/recovery action and initiates no key-provider fallback |
| AC-05 (retired in v0.2) | Legacy configuration/data migration is out of scope | Not applicable under [CR-01](../../docs/tasks/AI4R-001/CHANGE_REQUEST-01.md); ID retained for traceability, not reused |
| AC-06 | Model operation requires zero model-provider API keys and exposes no credentials | Clean-profile execution plus outbound-call/configuration/log review finds no key requirement, fallback, or credential disclosure |
| AC-07 | Multiple local conversations remain isolated through stop/resume/reconnect | Concurrent-session and restart scenarios preserve their respective inputs, outputs, and control actions |
| AC-08 | Every capability in the agreed baseline inventory has demonstrated coverage | Every inventory row has equivalent behavior and passing evidence; unresolved or unsupported rows prevent a whole-project completion claim unless Xiaoyang explicitly changes scope |

### Measurable Outcomes

- **SC-001**: Zero model-provider API keys required for the supported product operation (AC-01, AC-06).
- **SC-002**: All agreed acceptance scenarios have reproducible results tied to the implementation and team baseline.
- **SC-003**: All baseline capability inventory entries are accounted for, with no silent loss of functionality (AC-08).
- **SC-004**: No loss of newly created project/history data or cross-session result leakage in the agreed restart and concurrency fixtures.

## Assumptions

- Users have their own eligible subscription access and network connectivity. Access must be verified on the actual account; it is not inferred from a model name or installed CLI.
- The existing local Windows/web application is the first validation environment; other currently supported deployment/platform paths remain part of the inventory and require an explicit coverage decision.
- The selected Codex integration is a user constraint. Its ability to cover every existing project capability remains a technical feasibility question, not an assumed fact.
- Application frontend/backend communication still exists. Replacing model-provider API-key operation does not mean removing the application's own interfaces.
- Authentication to external resources such as source-control accounts is separate from model-provider keys. Key-dependent search/media services remain visible in the inventory and require a documented disposition before claiming full coverage.
- Shared-server hosting and sharing one person's subscription credentials are outside this local-per-user deployment scope.

- Fresh first-run scope: legacy configuration, project/history import, and migration records are not required. This is a first-use assumption, not a reset-on-every-launch requirement or authorization to delete existing local files. Decision: [CR-01](../../docs/tasks/AI4R-001/CHANGE_REQUEST-01.md).
