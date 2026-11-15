# Demo and reference CCs: role and limits

Reviewed alongside the active factory library, not counted as factory capabilities.
The factory controller discovers `jiuwenswarm/factory/ccs` explicitly
([controller.py](../../../../jiuwenswarm/factory/controller.py), `configure_agent`).
The four demo packages, eleven local reference declarations and thirteen upstream
reference declarations are separate roots. Repeated IDs are versions/copies of
examples, not additional independently qualified tools. Exact declaration paths,
hashes, bindings and capability names are in [INVENTORY.json](INVENTORY.json).

This is source review. No dependency installation, new service/image launch, MAPIE
run or upstream verification run was performed for this review. Existing test code
is evidence of intended coverage, not a newly executed test result.

## Four demo packages

| CC | Capabilities/materials and purpose | Dependencies/effects and verification | Role, limitations and improvement |
|---|---|---|---|
| `demo.compute_service` | Served `api`; synthetic multiplication with health endpoint | Pinned image binding; process execution, network listening and network requests. Docker build script binds an application image, not merely a base image. | Example of packaging a long-lived application and managing readiness/stop. No inference or Spark qualification. Keep it as a service-lifecycle fixture; avoid presenting HTTP timing as inference performance. |
| `demo.service_client` | `benchmark` writes client-duration metrics and a retained series; preserves partial results on request failure | Native Python, host-issued environment handle and network.request. `tests/ccv2/test_demo_ccs.py` exercises HTTP success, empty workload and partial results. | Useful template for independently retained observations. It records returned values rather than independently establishing multiplication correctness. A future real inference client needs token accounting, workload identity, concurrency and a separate correctness verifier. |
| `demo.workspace_inspect` | `inspect` inventories bounded files and structural JSON/CSV/YAML metadata; produces a report and artifact | Native Python, assigned workspace handle, workspace.read; optional YAML. Skips symlinks/dependency folders; bounds file count, structured-file count and size. Tests cover errors, empty/truncated inventories and unchanged workspace bytes. | Useful read-only discovery pattern. It does not discover dependency ownership, certify repository safety or qualify a CC. Report omissions explicitly; a factory intake tool would additionally need source provenance and applicability. |
| `demo.methodology` | Passive `method` and `limits` materials | No bindings/capabilities; tests verify readable materials and refusal to execute a material as a tool | Demonstrates that a complete CC may be instructional rather than executable. The method specifies discovery, start, handles, observation and stop. Useful packaging pattern; synthetic content is not an inference research method. |

Sources: `demo/ccs/*/cc.yaml`, accompanying `client.py`, `inspect.py`, image build
script/server, `METHOD.md`/`LIMITS.md`, and `tests/ccv2/test_demo_ccs.py`.

## Nine distinct reference identities

| CC identity | Actual capabilities/materials | Role in the broader factory idea | Verification/applicability and gaps |
|---|---|---|---|
| `text.trim` | `trim`: ASCII-whitespace transformation | Small deterministic function/package and cross-runner fixture | CPU/native; fixture input/answer files. A protocol conformance example, not a factory optimization. |
| `cc.examples.portable` | `trim`, `empty`, `echo`, `write-text` | Multi-capability package, artifact output, valid empty completion and alternative image binding | Native Python plus optional Dockerfile/image declaration. Useful tests of transport/packaging; declarations alone do not establish all platforms or image execution. |
| `example.method_library` | Passive `SKILL.md` material | Packages reusable methodology without a fake executable capability | Readability/identity are meaningful checks. Method efficacy still needs task-specific evidence. Copies appear in both `library` and `method_library` directories. |
| `native_code_delegation` | `repair` delegates a bounded worktree repair and regression test | Closest reference pattern for assigning an implementation task to another coding agent | Requires host-registered `code_agent`, workspace resource, read/write/process effects. The declaration is not an installed coding agent or proof of a successful Strata repair. Needs actual delegate identity, source diff, test receipt and build/product linkage. |
| `example.http_product` | Served `api` plus separately bound `inspect` | One package can expose a running product and finite tools; host owns lifecycle | Synthetic native HTTP product, with an image alternative in protocol examples. Startup readiness does not imply scientific validity. Not a model server. Several copies share this ID. |
| `lab.client` | `benchmark`, `observe` | Separate measurement and observability operations in one package | Native client and assigned environment; synthetic request durations only. `observe` explicitly has no internal tracer. This is a useful precedent for reporting absent telemetry rather than fabricating counters. |
| `mapie_split_conformal` | `fit_calibrate`, `predict_intervals`, `evaluate`; requirements lock | Concrete external-library method packaged as several related capabilities with artifact flow | Uses actual MAPIE SplitConformalRegressor, NumPy and sklearn rather than a hand-written substitute. Could inform calibrated cost-model uncertainty, but does not predict experts or prove calibrated Spark estimates. Requires representative train/calibration/test separation. Pickled model artifacts require trusted provenance: digest integrity does not make arbitrary pickle safe. Current dependency locks must be admitted in an isolated environment before factory use. |
| `strata_native_product_inspection` | `inspect_product` | Demonstrates separation of a CC inspection tool from a native engine product containing zero CC declarations | Worker checks exact older Strata source pin `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`, uses its real manifest loader, verifies payloads and never executes the fixture entrypoint. This is synthetic product inspection, not the current Spark runtime pin or inference correctness. A useful future adapter must explicitly support the delivered product format/revision. |
| `examples.easy_results` | `produce`, `review` with explicit policy | Separates production of a retained result from later requested verification, without rerunning the producer | Upstream reference only; producer writes a caller-provided synthetic score and reviewer compares it with a threshold. `guarantees` is a declaration, not proof. Reuse the separation of responsibilities, not the synthetic scoring rule. It is not currently installed in the factory catalog. |

Local references are under `tests/ccv2/examples` and
`tests/ccv2/protocol_examples`. Upstream references are under
`AI4Research-Notebook/Designs/CC Protocols/{examples,reference/examples}` in the
read-only Muxite checkout at `e897ff47a89a2f0e07db1e63b399d45abf0cc02e`.
They are implementation examples, not automatically admitted factory dependencies.

## Copies and archived material

Ten additional manifests under local `.demo-verify-*` test scratch are generated
sealed copies. They were excluded from maintained-library counts and left intact.
Likewise, `artifacts/factory/evidence/**/capsules`, built demo artifacts and upstream
historical release stores preserve prior evidence, rather than adding new current
packages. Request YAML files describe desired work; they are not executable CCs.
No archived bytes were changed or removed in this review.

The most useful patterns to carry into the factory are multi-capability packages,
passive methodology materials, explicit coding delegation, independent review of
retained results, and external-library artifact pipelines. Each still needs domain
verification, source/environment identity and an appropriate task admission policy.
