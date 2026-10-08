# Intent Compiler Benchmark Interface Contract

Implement the following interfaces so an external benchmark can submit one compiler test case and independently inspect its result. Follow the supplied Architecture Main/Context and their bundled compact package; use its existing client/field contracts and document concrete commands or API calls.

This contract applies equally to the runs with and without Spec Kit. The benchmark client and product interfaces must not depend on Spec Kit.

1. **Readiness and configuration:** Return application/build identity, interface and schema versions, supported compiler-only profile, and authentication, storage, model, and required enforcement readiness. Report unavailable prerequisites explicitly.

2. **Input and submission:** Accept the original research request and permitted local documents/resources through protected intake. Preserve exact source text, hashes, resource roles, and qualification/rejection reasons. Submit with a unique client request ID and approved configuration; return a run ID or structured rejection. Support reconciliation after transport loss without duplicate execution.

3. **Status and cancellation:** Expose run stage, lifecycle status, candidate versus accepted references, gate verdicts/reasons, and terminal outcome. Support explicit cancellation and finite headless execution. Halt without waiting for human input; disconnect must not cancel or replay work.

4. **Evidence export:** Allow authorized retrieval for successful, failed, and blocked attempts. Export:
   - Original/qualified inputs, candidate and accepted Intent IR and Research Brief.
   - Node/subnode contracts, actual capsule/admission/implementation pins, effective configuration, check plans, deterministic results, verifier assessments, and subnode/node gate decisions.
   - Invocation identities, ordering and durable acceptance records, input/output hashes, actual model/adapter settings, timing, calls, limits/effects, hardware readiness, and available token/cost telemetry.
   - A versioned manifest with named readable files and explicit missing/unavailable evidence.

Complete the architected node through **durably released `Research_Brief.json`**: Intention → checks/verifier/gate → Requirements → checks/verifier/gate → node finalization. Requirements consumes accepted Intent; external consumers receive only the released Brief. Preserve candidate evidence on failure. Apply no automatic repair, replay, or hidden model substitution.

Use current contracts: Intent IR 1.0.0, Research Brief 2.0.0, gate decision 2.0.0, Subnode Execution Contract 1.0.0, and enclosing Node Execution Contract 2.0.0. The architecture catalog governs all other versions and fields.

Verify the client path with one actionable request reaching a released Brief and inspectable evidence. Keep benchmark expectations and scoring outside the compiler. Do not implement downstream research stages or the benchmark suite.

This supports a compiler pilot under benchmark SU01. The existing Screening → Hypothesis case remains a separate test.
