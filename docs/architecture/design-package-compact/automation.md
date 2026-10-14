# Automated development and platform benchmarking

**Reading level: human potential.** Question answered: How do authenticated clients connect, observe and recover without release authority?

## Local Compose topology

```mermaid
flowchart TB
    U[User browser or CLI] <-->|http://127.0.0.1:5173| H[Host loopback publication]
    B[Optional benchmarker container] -->|Same client contract| Web
    subgraph Local[Single workstation Compose deployment]
        subgraph W[Workflow application image and container]
            direction LR
            UI[Built web frontend assets]
            Web[Web server and control API]
            Runtime[Workflow runtime and local modules]
            UI -->|Same-origin UI and API| Web
            Web --> Runtime
        end
        B
        S[(Private run state and artifacts)]
        O[(Benchmark campaign outputs)]
        H <-->|Host 5173 to container 5173| Web
        Runtime --> S
        B --> O
    end
    Runtime -->|Audited model access| M[Configured model endpoint]
```

## Client contract and campaign behavior

The workflow application exposes one versioned, authenticated client boundary for supported UI/CLI clients and external clients such as the optional benchmarker or development sidecar. On the container network, clients reach it through the configured application service name and container port `5173` by default; browser users reach the same UI/control service through the host-loopback publication described above. The product boundary provides a readiness/capability response containing the client-contract version, target instance/build identity, supported operations and prerequisite states. A client verifies target and compatibility before submission; mismatch or missing required capability blocks the operation. Readiness distinguishes HTTP/process liveness from storage, authentication, model and required-isolation readiness. The [client field contract](reference/other-contracts.md#client-and-model-boundaries) defines shared readiness/submission/status/evidence information. Route names, transport encoding and internal adapters remain implementation choices within that contract. The separately scoped development-sidecar connection contract relies on this product boundary and adds no privileged product endpoint.

| Operation | Meaning that must be stable |
|---|---|
| Readiness | Verify target instance/build and client-contract compatibility; distinguish service liveness from model/authentication, storage and required-security readiness. Declare an unavailable prerequisite rather than measuring a mock as a real model run. |
| Submit | After readiness and compatibility pass, submit the original objective, permitted resources, explicit product/evaluation mode, approved profile identity and requested seed where supported. Return one run identity; ambiguous transport completion does not automatically resubmit. |
| Observe | Read correlated status and events, with reconnect/poll support. Transport disconnection never cancels or duplicates research work. |
| Finish/retrieve | Structured terminal status, detailed verdict/reason, accepted result references and allowed Run Bundle. Headless failures never wait for a human. |
| Cancel | Explicit authenticated control action; preserve work already performed and cancellation evidence. It cannot undo external effects. |

Hardware inventory reference. Benchmark clients run a host-side inventory collector before every test and repeat. Submit accepts an optional `evaluation` block `{campaign_id, run_id, inventory_id}`. The application does not read or judge the inventory. It echoes the three identities in the readiness-to-export manifest so the exported run bundle links to the pre-test hardware record. Readiness also reports `evaluation_profile` (the approved profile identity or `none`) and `fault_injection` (`available` or `unavailable`). Product profiles always report `none` and `unavailable`.

## Evaluation-profile entry points

The platform benchmark needs four operations the user client does not have. They exist only when the launcher starts the application with an approved evaluation profile. They use a separate `evaluation_profile` credential scope. Product profiles do not list them in readiness, and a request for one is refused. Anything they produce is labeled `invalid_for_product` and cannot be admitted, activated or used as RSI material. They are development seams, outside product startup and every milestone exit. A client that finds one missing reports a dependency block and does not fall back to another path.

| Operation | What the application does | Never |
|---|---|---|
| Node replay | Accepts a frozen node bundle (pinned declaration and exact output, plus host-only records) and runs the verifier path on it. Returns tier verdicts, gate decision, downstream action | Pass host-only records to the semantic verifier, or run the producing capsule |
| Single-CC invocation | Runs one admitted capsule and its pinned check bundle with an externally supplied binding. Returns output and check results | Release a gate, start another node, or let the capsule choose its model route |
| Fault injection | Applies faults declared in the evaluation profile definition (delayed gate persistence, swapped artifact). The client supplies only a fault identity | Accept a fault definition from a client, or exist in a product profile |
| Checkpoint observation | Writes read-only checkpoint records at declared node boundaries into the export | Reveal checkpoints to the agent or return corrective feedback |

Payload field tables, entry point numbering (E1 to E6) and the M1 pilot split are in the [benchmark runner design](development-tools/benchmark-runner/README.md#entry-points). Run-level submit, observe, retrieve and cancel need no new endpoint.

## Development capabilities worth establishing early

Use shared invocation, output validation, trusted evidence-context assembly, runtime verifier CC assessment, protected gate decision, release persistence and export builders across the slice and full M1. Native UI, CLI and benchmark adapters should call one application use-case boundary rather than reimplementing workflow decisions. Supply inspectable effective configuration and fixture-based mock adapters; protect real runtime paths from test-only verdict injection. Deliberately exercise loss of model access, artifact substitution, storage failure, malformed verifier output and browser/client disconnect through the same boundary.

## Benchmark and RSI evidence connections

Export versions, exact effective configuration, run identity, admitted outputs, observations and limitations in an audience-scoped manifest. Platform benchmarker analyzes exports; Data Foundation prepares them; offline RSI consumes only explicitly approved development material. The RSI referee/oracle remains a protected independent path. Platform evaluation must stay within the master PRD: no expanded model access, uncontrolled benchmark downloads, training or hidden-feedback leakage. Detailed campaigns belong to their owning specification.
