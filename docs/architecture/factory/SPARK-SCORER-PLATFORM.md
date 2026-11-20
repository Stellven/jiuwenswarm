# Spark platform amendment to the v4 execution harness

2026-11-20 UTC. Applies uniformly to every Spark candidate. Frozen input sources,
acceptance stages and thresholds remain byte-identical to the registered v4.
This is a new host/reference set, and does not establish Satay-to-Spark parity.

Evidence: `frozen-scope-only.log` and the preserved output at
`inputs/ab/portability-proof-spark-20261120/score.json`. The original CLI fails
S1 because its derived `inputs/satay/llama.cpp-stock` is absent. Inspection also
shows a pinned Satay receipt with absolute `/home/muk` tool paths, CUDA arch87,
a missing `build-stock-cuda87` binary, an absent reference, and a missing derived
Granite path. The frozen CLI exposes no platform-path or architecture overrides.
`OPS/cc-candidate-index.json` records exact code locations and all candidate hashes.
All present PREREG files match their v4 digest. Composite `work-orders.md` was not
staged; all five individual work orders are present and match their digests.

The external `tools/spark_demo/scorer_adapter.py` imports the original scorer
modules only after verifying their published v4 hashes. It substitutes ROOT,
STOCK, RECEIPT, RECEIPT_SHA256, REFERENCE, MODEL and STOCK_BIN as platform data.
It writes `scorer-spark-v4-owner/platform-overrides.json` with every replacement, frozen
source hashes and adapter source hash. The new receipt reflects the existing
pristine stock pin and the observed Spark CMake cache/binary. Its native recipe
uses sm_121 and the installed Unix Makefiles toolchain. The scorer's three-job
limit and every stage predicate remain unchanged. The runtime continuation shim
re-enters this adapter so the same overrides apply after a build. An external
context manager records every original server lifecycle to OPS/LEDGER.jsonl;
it preserves the original enter/exit and exception behavior.

Directive 2 maps `MODEL` to the owner's
`~/models/campaign/gguf/granite-3.1-1b-a400m-instruct-Q8_0.gguf`, whose SHA256
starts with `a52205df`. After the transfer completes, retain the owner's full
expected SHA256 as the single line in `OPS/scorer-portability/granite-owner.sha256`.
The adapter verifies the complete file against that receipt before any reference
or runtime command. The earlier downloaded `087517…` fixture and its metadata
remain in the historical stage and `granite-acquisition.json`. A same-host
stock reference must be generated from the owner's file.

Validation to date: metadata preparation, frozen-source digest verification,
header inspection, and three adapter tests (source drift refusal, stable receipt,
and original server lifecycle preservation). No adapted scorer build, reference
or model-runtime stage has run. Full score/reference/runtime commands require
the production `bin/capped` cgroup before proceeding.

Commands from the worktree (use new output/result directories for each run):

```bash
python3 tools/spark_demo/scorer_adapter.py prepare
# After GPU scheduling authorization, from ~/predemo-spark:
bin/capped --arm fixture-reference --engine-binary build-stock-cuda121/bin/llama-server --result-dir OPS/runs/fixture-reference -- python3 jiuwenswarm/tools/spark_demo/scorer_adapter.py reference
bin/capped --arm C1-fixture --engine-binary build-stock-cuda121/bin/llama-server --result-dir OPS/runs/C1-fixture -- python3 jiuwenswarm/tools/spark_demo/scorer_adapter.py score 1 /absolute/recorder.diff /home/user2/predemo-spark/scorer-spark-v4-owner/out/recorder
```

The second command performs the original build and runtime stages. Full scoring
must be scheduled separately from quiet benchmark runs. Scope-only operation is
available through the original `--scope-only` flag and does not run models, but
still creates and patches the scorer's private source copy.
