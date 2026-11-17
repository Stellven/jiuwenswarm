# 20261117 CC Workflow RSI Demo Guide prepresentation

Use the Qualification companion record for final scientific outcomes. This guide describes how to inspect the actual system without starting another experiment.

## Access

Spark: user2@100.105.127.48 over Tailscale SSH. The native service listens on Spark loopback port 5175. Forward it with:

```powershell
ssh -N -L 127.0.0.1:5175:127.0.0.1:5175 user2@100.105.127.48
```

Open http://127.0.0.1:5175/review?run=design-review-adaptation for the final adaptation graph. Open /review?run=design-review-continuation for the first completed candidate cycle. Open /review?run=design-review for the preserved earlier graph in the same task. The original graph console is at /. A GET or browser refresh does not execute a node.

## Ten-minute walkthrough

1. State the lineage: relevant M1 capabilities retained, obsolete POC removed, CCv2 and dynamic workflows integrated.
2. Show the selected task and catalog. Explain package, capability, reusable subworkflow and workflow roles using one actual builder capability.
3. Follow strata-candidate-cycle into construct-and-evaluate, candidate-construction and candidate-screen. Inspect exact node IDs, selected releases and the result-channel producer binding.
4. Show graph revision reasons and collected evidence. The original graph stays stopped; the continuation retains the same task budget and the valid A/A reference.
5. Inspect build receipt, source revision and immutable image identity. For confirmation, verify the same builder result supplies its candidate identity.
6. Read the independent verdict and its individual gates. Compare exact outputs, baseline stability, per-case regressions and conservative throughput gain.
7. Show retained failed steps and reaped cleanup. Explain the history-artifact discovery and resumed-turn controller repairs with their regression tests.
8. Close with bounded claims and next decisions, using the Results companion rather than an inferred success from green execution nodes.

## Reproduction boundaries

The package contains source snapshots, source patches, selected sealed CC bundles, task/suite/config definitions, read-only graph/catalog/events exports, independent qualification data and selected raw logs. It excludes credentials, model weights, dependency environments, mutable databases and Docker layers. SHA256 manifest entries identify the packaged bytes. The source snapshot is a working-tree snapshot over the recorded platform base, not a pushed revision.

Running the preparation/controller scripts executes real admitted work and consumes resources. The saved task is a record of a bounded run, not reusable authorization: reproduction needs fresh task identities, deadlines, paths, admitted model assets, image digests and an available native build/GPU queue. Keep historical tasks immutable. Retain the frozen accuracy and performance gates when comparing candidates; changing a protocol creates a separately recorded experiment.

Full live stores are under /home/user2/software-factory-spark-20261113/native-design-review-20261117 and native-design-review-balanced-20261117. The native platform source is sources/native-workflow-integration-20261116 under the same root. The candidate engine source is owned by the balanced task under factory/agent-workspace/strata. The factory platform runs the updated source; promotion of a candidate engine into another serving runtime is a separate fact reported in Qualification.

Historical migration artifacts use the earlier 0.2.0-proposal vocabulary and are labeled as offline evidence. The supported live catalog is exported separately as schema version 0.2.0. The historical-reconciliation folder includes the original downloaded inputs and a self-contained offline probe; run it with Python and jsonschema to reproduce the declaration checks without executing CCs.

The current stop operation records the graph status as cancelled even when every engineering call is already completed. In this run that means the graph was explicitly closed after collection; inspect leaf completion, zero pending cleanup and the independent scientific verdict separately. A clearer closed-state label is a future UI/state-model improvement.

The separate GGML dependency checkout is also required for a native rebuild and is not included in the archive. Its pinned revision is 3cf03257f219afbe7334045ff7c6a06ac68c627d, currently under /home/user2/software-factory-spark-20261113/sources/strata-ggml on Spark. The admitted native builder image is sha256:d893d61a6f641fdeb6d20ce33870868d3ffd497746531a233d988427deff7f87. These dependencies and exact build requests are retained in Qualification; the archive is a source/evidence handoff, not an offline appliance image.
