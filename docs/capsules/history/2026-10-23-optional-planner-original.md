# Optional M1 capability DAG

This is the user-authorized October 23 extension of M1, based on
`ai4r_M1` at `bfc30ba291c762d09f464c3e6a6c25f011826a33`.
The received PRD and historical design sources remain unchanged.

The existing integrated scientific/PDF policy remains the default. The new
`ai4r_capability_dag_v1` policy allows compatible capsules in any acyclic order,
including repeated instances of a capsule. It retains exact declaration pins,
typed ports, frozen inputs, coverage, effects, resources, independent checking
and one attempt per node. One checked terminal leaf covers all deliverables.
Scientific work still requires Scientific Evaluation and scientific Delivery.
The node limit is **12**, matching the current public schema, rather than the
16 suggested during planning. There may be at most two Generalist assignments.

`workflow.capability_planner` is a separate one-shot native Planner candidate.
It uses the existing model connection. Installing this source does not admit
or activate it, and does not replace the working default Planner.

## Installation and selection

1. Merge `capsules/planner-foundation` first. Merge any desired capsule branches
   independently; they add separate package directories and tests.
2. Inside the app's operator environment, list source-installed candidates:
   `python -m jiuwenswarm.research.capsule_extensions.operator list --store "$JIUWENSWARM_M1_STATE"`.
3. Prepare a selected candidate's exact immutable assets/action references:
   `python -m jiuwenswarm.research.capsule_extensions.operator prepare --store "$JIUWENSWARM_M1_STATE" --name workflow.capability_planner`.
   Preparation grants no standing. Repeat with each desired capsule name.
4. Independently qualify the returned check bundle and semantic profile through
   the existing protected checking-asset calibration workflow. Capture actual
   evidence; local unit tests are not substitute calibration receipts.
5. Use the existing Linux human operator commands
   `python -m jiuwenswarm.research.library_operator associate-checks|admit|standing --request-ref '<JSON Ref>'`
   with the respective returned references. Check each result before the next
   command. Admission requires qualified checks; activation requires admitted
   exact bytes. Missing evidence remains blocked rather than receiving a fake PASS.
6. Select the new protected policy before intake. For an explicitly authored
   fresh local profile, `capture_local_profile(..., capability_dag=True)` captures
   it. Bind its returned configuration and bootstrap paths with the existing
   `JIUWENSWARM_M1_CONFIG` and `JIUWENSWARM_M1_BOOTSTRAP_BINDINGS` settings.
   Do not edit an existing captured profile in place. The ordinary container
   launcher continues to use its existing default profile.
7. Restart the app when idle. Only exact active releases are registered; a
   missing capability Planner blocks the new policy without changing old work.

This delivery does not supply new calibration labels, silently migrate a
deployment or claim connected model/container validation. Qualification must
be completed in the existing implementation workflow with actual credentials.

## Interoperability and trust

Optional work capsules share `urn:ai4r:work-packet:1.0.0`, containing bounded
JSON data, UTF-8 file text/digests, provenance and limitations. No host paths,
ambient filesystem access or permissions are encoded in a packet. A captured
compatible inventory artifact or accepted predecessor supplies the packet.
The Planner cannot synthesize artifact Refs or convert unrelated scientific
ports implicitly. Bridging to an incompatible specialist requires an explicit
admitted adapter; arbitrary ordering never removes type/dependency constraints.

Low-trust inputs stay low trust through utility transformations. Generalist
task checks establish bounded conformance, not scientific truth or reusable
specialist certification. Capsule branches document their additional semantics.

Source manifests freeze each optional release. Startup verifies them before
loading code. Candidate capture never changes Library standing. An active
release mismatch fails closed; update it under a new version and requalify it.
Frozen legacy POC instruction bytes have explicit line-ending rules so Windows
and Linux checkouts produce the same release identities. The independent PDF
Planner is versioned `paper-m1-6` for the changed protected Binder closure;
paper Summary/Delivery and scientific capsule identities are preserved.
