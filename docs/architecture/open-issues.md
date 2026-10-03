---
type: home
status: draft
tags: [open, validation, conflicts]
---

# Implementation and acceptance obligations

The authoritative dispositions for D1–D13 and issues 1–58 are in [decisions](decisions.md). This page contains only facts architecture cannot settle through a sourced, replaceable default: a product conflict, unavailable safety proof, or implementation validation. Missing owner prose alone is no longer a black-box reason.

## Product and security conflicts

| ID | Condition | Affected area | Decision needed outside architecture |
|---|---|---|---|
| 57 | The Docker Linux execution profile has not yet demonstrated required generated-code filesystem, network, credential and hidden-fixture isolation on Linux Engine and macOS Docker Desktop. | Generated POC and RSI hidden execution | Implement and run the pinned image/kernel/profile negative probes in [deployment](system/deployment.md). Failure returns `UNSUPPORTED_SECURITY_PROFILE`; it does not satisfy platform acceptance. |

## Implementation validation

| ID | Fact to prove | Acceptance evidence |
|---|---|---|
| 19 | Native spans available for CcBackend/tool/skill calls without a team worker | One local run showing span identity and its join to CC run/step/attempt records; otherwise keep CC records authoritative |
| 22 | Existing `compile_intent` code conforms to `source_text → intent_ir` | Component invocation and fixtures after coding; architecture does not claim it ran |
| 25 | Native browser run view renders a non-team CC run | First integrated run on the pinned OpenJiuwen version |
| 26 | `chat.send → AgentRuntime.stream → CC entry adapter` preserves run/request identity | Instrumented local integration trace |
| 40a | Linux runner and oracle enforce the documented negative boundaries | Doctor probes for paths, network, credentials, process escape, fixtures and IPC authentication |
| 43 | Each supported matrix entry has a closed binary-only, hash-pinned wheelhouse | Manifest resolver plus clean offline installation |
| 54 | Each checked effect/permission field maps to `denied`, `mediated`, `observed` or `unsupported` on every backend | Backend enforcement matrix and injected violations |
| 58 | Each measurement method has a trusted adapter, workload/hardware coverage and validation fixture | Registry evidence per method; missing coverage blocks only the selecting experiment |

## Recheck set

A changed decision reopens its owner and every producer, consumer, Gate profile, Binding/run plan, seam, record, coverage row and graph edge. Runtime evidence is never inferred from architecture lint. The October 2 installer custody clause resolves the old root-free bootstrap conflict; deployment validation remains required. External replies are outside this work. Architecture commits preserve provenance and do not claim implementation acceptance.
