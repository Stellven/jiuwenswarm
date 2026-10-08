# Placement, evidence, and reuse

**Reading level: human potential.** Question answered: Where do frontend, runtime, evidence, models and isolated execution live?

## Deployment and boundaries

**Required now.** Use one authorized local execution host with Python services, the existing TypeScript web UI, SQLite authoritative run state and filesystem artifacts. Product identity is user-scoped, distinct from the local OS account; durable account/profile state survives run/workspace deletion. M1 keeps one active authorized execution context, without enterprise multi-tenant administration. Keep internal modules distinct without making them separate services. One container may contain several native processes.

## Data foundation

**Required now.** The run-state module owns durable lifecycle, frozen graph, attempts, decisions, and accepted artifact references. The scheduler and control plane use that authority. Native queues, journals, caches, and UI traces are projections or dispatch aids.

## Offline RSI

The [human-callback policy](failure-and-human.md#offline-rsi-is-a-separate-callback-policy) distinguishes ordinary candidate feedback, session faults and explicit activation. Runtime Evaluator Gate, offline referee and fixture oracle are different roles, defined in [the glossary](glossary.md).

## Native reuse

**Required now.** Start from native UI/transport, SwarmFlow scheduling, Symphony agent/harness components, existing model integration, storage, and diagnostics. Historical integration audits are source leads, not proven integrations or current policy. [Human callback](failure-and-human.md#pattern-and-reuse-evidence) records current inspected native interaction leads.

## Container startup, IPC and storage obligations

The application image pins frontend assets, runtime dependencies and shipped CC versions. Its entrypoint validates configuration, persistent-store access, session authentication and required security before accepting work; it serves inspection and explicit readiness failures when execution prerequisites are unavailable. Startup does not require a separate UI script or spawn a new experimental image for each POC.

## Dependency preparation and provisioning

| Owner / time | Input → required result | Failure |
|---|---|---|
| Protected environment preparation, before research | Approved frameworks/platform → reviewed environment catalog; exact direct/transitive package versions, hashes and offline package availability | Unsupported platform or incomplete closure makes that catalog entry unavailable |
| Resource qualification / Hypothesis | Supplied baseline/data and compatible catalog → captured resources and selected immutable environment lock | No compatible prepared entry blocks before Builder |
| Builder | Accepted Blueprint and selected lock → unchanged lock as `requirements.txt`, bounded scripts and readable POC manifest | Undeclared imports, changed lock or unpinned transitive package blocks packaging acceptance |
| Trusted Benchmark provisioner | Accepted bundle/lock → containment checks, exact package verification and installation in unprivileged isolated environment | Missing/hash-mismatched package or provisioning failure halts; no resolver upgrade or automatic repair |
| Restricted scientific executor | Provisioned environment/frozen protocol → baseline then treatment measurements and raw evidence | Generated code cannot install, discover dependencies, access secrets or alter the baseline |

Protected preparation is outside Builder and generated-code permissions. M1 uses prepared package bytes; supplying a new framework requires protected preparation and a new linked run, rather than dynamic installation during work. A Python virtual environment provides dependency separation; filesystem/process/network confinement remains separately enforced. Exact locks enable reconstruction but do not prove scientific validity or package safety.

## Connected behavior summary

One authorized local host; one application image bundles frontend assets, same-origin web/control API and runtime. Multiple protected native processes are allowed. Image entrypoint starts services and validates configuration/storage/authentication/isolation. No host UI script or separate frontend container is required. Browser reaches `http://127.0.0.1:5173`; publish `127.0.0.1:5173:5173`. Container-interface listening enables forwarding/private clients, never LAN access. This is D6's exception to literal process-loopback wording.

Private sidecar/benchmarker uses application service DNS/container port, compatibility/readiness handshake and separately scoped credentials. It cannot mount state/fixtures or control gate policy. Optional tooling is not an M1 prerequisite.

Package approved Codex CLI/bridge inside the Linux application image; operator provisions existing subscription authentication through protected configuration. Use owned Unix-domain IPC and ephemeral credential, not adapter TCP or a broad host home mount. Native supported workstation uses equivalent protected IPC. Missing subscription/runtime/device blocks execution; no silent host proxy/mock fallback. Provider credentials, gate state and hidden data are inaccessible to POC code.

Persist SQLite lifecycle, immutable files/evidence and account/profile state separately from replaceable image/workspace. Hidden RSI store has separate custody. Account defaults → local machine → project overrides resolve before run freeze; no override widens policy. Native memory holds compact reasoning references. Files/decision must persist before release; orphans grant none. Browser disconnect preserves execution; restart pauses without replay.

Generated POC uses a restricted local identity, scoped copies of baseline/data and `/workspace/poc/`, denied undeclared network/tools and observed limits. Container packaging/venv/import scanning alone do not prove confinement. No Docker socket or per-POC orchestration. Forbidden generated modules include `os`, `sys`, `subprocess`, `requests`, `urllib`, `shutil`; trusted infrastructure operations are distinct.

Trusted provisioning rejects archive traversal/links/undeclared files and unresolved direct/transitive pins. Use approved prepared package bytes; any permitted origin/content-pinned fetch belongs to protected preparation before the run; POC gains no network authority. Missing/conflicting dependencies halt without repair. Baseline copy stays read-only; treatment cannot alter protocol. Model and isolation readiness must be proved; unavailable enforcement blocks.

Verify startup without UI helper, same-origin access, denied LAN/unauthenticated access, persistent inspection after recreation, denied secret/control/fixture/network access and IPC readiness. Exact OS/container mechanisms belong to implementation specifications. Optional cloud profile persistence is not a cloud research-data/worker service.

Startup enables lossless trajectory capture, required trace retention and sandbox activity logs; boot checks deny restricted identity access to hidden fixtures. Native one-time local browser token bootstrap stays out of logs/exports; private clients use separately scoped credentials.
