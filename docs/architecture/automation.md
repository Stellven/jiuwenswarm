# Automated development and platform benchmarking

**Required shape:** a benchmarker drives the workflow exactly as an authenticated user client does. It submits bounded work, observes status, retrieves permitted artifacts, and records terminal outcomes. It cannot write authoritative run state, insert accepted outputs, bypass the Verifier (Evaluator Gate), or mount the hidden RSI fixture store. Detailed commands, APIs and fixtures belong to Spec Kit.

## Local Compose topology

```mermaid
flowchart LR
    U[User browser or CLI] -->|Loopback authenticated endpoint| W
    B[Optional benchmarker container] -->|Same client contract| W
    subgraph Local[Single workstation Compose deployment]
        W[Workflow application service]
        B
        S[(Private run state and artifacts)]
        O[(Benchmark campaign outputs)]
        W --> S
        B --> O
    end
    W -->|Audited model access| M[Configured model endpoint]
```

The workflow application remains one service. The optional benchmarker is an external client, not another research worker or distributed compute host. User-facing exposure is one loopback endpoint, retaining the PRD's port 5173 as the default unless the implementation agreement documents a deliberate local override. UI and control API share that endpoint. Internal module calls need no assigned TCP ports.

Within Compose, the benchmarker addresses the workflow by service DNS and its **container** application port; its own `localhost` is not the workflow service. The application may listen on its container interface; only loopback host publication is permitted. No benchmarker inbound port is needed. An authenticated private network endpoint for the client does not authorize LAN exposure. Keep model IPC as a restricted socket/named-pipe equivalent, never a public model-adapter TCP listener. Do not expose SQLite, artifact storage, fixture oracle, or Docker socket as client services.

The benchmarker gets a scoped credential permitting submit/status/retrieval in the declared evaluation workspace. It has no gate-policy, activation, referee or arbitrary configuration-write authority. The host/launcher selects approved profile definitions; the client supplies their identifiers and allowed per-run inputs. Normal M1 submission cannot disable mandatory controls. Declared ablations run only in the isolated evaluation profile and carry invalid-for-product/admission labels.

The workflow owns its state/artifact volumes; the benchmarker owns campaign output. Supplied inputs are registered through the same controlled resource-import path as user inputs. A fixture mount, where needed, contains only the campaign's visible inputs and is read-only; it never grants the benchmarker direct access to release state or grants POC code access to campaign expectations. Retrieve permitted bundle exports through the client boundary. Package/model/image preparation happens before the run; startup does not silently download datasets or change frozen dependencies.

## Client contract and campaign behavior

| Operation | Meaning that must be stable |
|---|---|
| Readiness | Distinguish service liveness from model/authentication, storage and required-security readiness. Declare an unavailable prerequisite rather than measuring a mock as a real model run. |
| Submit | Original objective, permitted resources, explicit product/evaluation mode, approved profile identity, requested seed where supported. Return one run identity; ambiguous transport completion does not automatically resubmit. |
| Observe | Read correlated status and events, with reconnect/poll support. Transport disconnection never cancels or duplicates research work. |
| Finish/retrieve | Structured terminal status, detailed verdict/reason, accepted result references and allowed Run Bundle. Headless failures never wait for a human. |
| Cancel | Explicit authenticated control action; preserve work already performed and cancellation evidence. It cannot undo external effects. |

The submission contract must support client request identity and reconciliation after uncertain delivery, so automation can discover whether a run was created before retrying. Spec Kit chooses the concrete mechanism. Separate client transport recovery from forbidden automatic capsule retries. For TRIAL-1, allow one active run and sequential campaign cases; no concurrent-run orchestration is needed.

Provide a simple documented launch/run/retrieve path and a smoke mode using labeled mocks. A model-backed mode exercises the actual bridge, compiler, verifier and durable release. Both use the same runner and client adapter. A Compose campaign command should return non-success when required cases or prerequisites fail, preserve per-case records, and allow cleanup of replaceable containers without deleting evidence. Exact CLI syntax and Compose service definitions are implementation work, not executable promises in this design.

Campaigns freeze the task set, expected outcomes, profiles, component pins and analysis policy before measurement. Run matched inputs/configurations, preserve repetitions and requested/effective seeds, failures, elapsed time and available calls/cost. Label model nondeterminism and provider gaps. Cases can continue after a terminal failed run according to campaign policy; the failed workflow itself cannot continue. Scientific benchmark deltas remain inside the user's research protocol; campaign pass rates and latency are platform measures.

## Development capabilities worth establishing early

Use shared invocation, output validation, trusted evidence-context assembly, Verifier execution, release persistence and export builders across the trial and full M1. Native UI, CLI and benchmark adapters should call one application use-case boundary rather than reimplementing workflow decisions. Supply inspectable effective configuration and fixture-based mock adapters; protect real runtime paths from test-only verdict injection. Deliberately exercise loss of model access, artifact substitution, storage failure, malformed verifier output and browser/client disconnect through the same boundary.

Keep admission tooling capable of validating/pinning the two trial CCs now and additional capabilities later. Preserve exact dependency identities and per-attempt evidence. A port/type compatibility check and a frozen reference graph will be useful for both planner integration and RSI comparison. These capabilities are architectural needs; Spec Kit selects private APIs, diagnostics, thresholds and test mechanisms.

## Benchmark and RSI handoff

Export versions, exact effective configuration, run identity, admitted outputs, observations and limitations in an audience-scoped manifest. Platform benchmarker analyzes exports; Data Foundation prepares them; offline RSI consumes only explicitly approved development material. The RSI referee/oracle remains a protected independent path. Platform evaluation must stay within the master PRD: no expanded model access, uncontrolled benchmark downloads, training or hidden-feedback leakage. Detailed campaigns belong to their owning specification.
