# Broad Strata campaign handoff

This bundle retains the broad throughput investigation, the original failed A/A,
nonpromoting configuration diagnostics, and the fixed-placement source/build/A/A
chain. Read EXPORT-INDEX.json and the exported records for final task outcomes.
The detailed evidence-citing report is
[source/docs/architecture/factory/SPARK-BROAD-CAMPAIGN-RSI-RESULTS.md](source/docs/architecture/factory/SPARK-BROAD-CAMPAIGN-RSI-RESULTS.md).
Historical experiments keep their original gates; later diagnostics do not rescore
them. A fixed-placement diagnostic is not a proven throughput optimization.

The first broad A/A had identical sampled eight-question answers and different
free-generation speed tokens. Startup showed8957 versus8959 GPU expert slots
under identical flags. Available-memory-based placement is an observed confounder,
not a demonstrated cause of every token difference. The verified fixed A/A
retained exact tokens and all40 layer hashes across four processes; its combined
rate ratio was0.997328. This establishes bounded repeatability, not a speed gain.
Drafting reached16.704 decode tokens/s in diagnostics but its combined rate ratio
was0.960921. All ten experiments completed with no accepted throughput gain. Fixed-placement
lookahead reduced combined throughput by3.55%; the final CPU6 treatment reduced
it by1.35%. The final factory suite passed1000 tests with1 skipped in151.32s.
The individual final records retain the exact gates, timings and failed attempts. The original A/A remains
failed. Configuration screens after it are explicitly exploratory and cannot
promote defaults or establish model equivalence.

The opt-in source component pins the requested expert budget or fails safely.
It requires one CUDA GPU/group/member and static caching. It prints effective
budget, every layer's expert placement hash, and an aggregate hash. Its source
revision is89ae0ee6123597636ef162dec826230186c00f3b. The resulting fixed-placement
image passed its separate A/A; consult its retained build/image identity and raw
receipts for the exact workload and interpretation. Later fixed-placement screens
have their own new contracts and must retain all remaining mismatch or null results.

Native prefill, decode and combined throughput exclude startup, tokenization and
transport. Repeated prompts favor warm caches; fresh processes do not make storage
cold. Eight-question screens are small exploratory quality checks. Equal tokens
on a bounded A/A do not establish general numerical or semantic equivalence.
Additional full-generation quality and independent balanced confirmation are
required before broader claims. Earlier DS4_PROF exit139 remains unresolved.

The engine.strata_throughput_workbench job combines evidence recovery, native
configuration preparation, experiment methods, exact admitted-template inspection,
and guarded loop lifecycle. The source-bearing engine.strata_fixed_placement CC
contains its component, patch, integration method, provenance and build request.
Profile verification and package sealing do not certify runtime performance.
Agent decisions remain distinct from host admission, resource guards and cleanup.
CC overhead metrics count receipts and lifecycle categories; synthetic developer
checks remain distinct from live GPU and agent evidence.

The standalone agent image is refreshed after final source changes and all
GPU measurements have stopped. See the final image receipt and actual standalone
Docker smoke for this bundle; historical source-bound missions retain their
original image identities. refresh-agent-image.py imports the new broad,
workbench, telemetry, evidence and fixed-placement modules, conditionally checks
the fixed-screen module, seals the capsule catalog, and imports the actual Jiuwen
facade without a source bind. Before overwriting fixed-name output receipts it
archives earlier image/build/smoke evidence by content hash. The refreshed image
identity and standalone smoke live in final-role-images.json. Until that receipt
exists for this final source, source-bound mission execution does not demonstrate
that the standalone image contains these final changes.

After root/operator declares every lab complete:

```sh
VENV/bin/python SOURCE/deploy/spark/refresh-agent-image.py --root ROOT --tag factory/agent:cc-dgx-spark-broad-final
VENV/bin/python SOURCE/deploy/spark/finalize-broad-campaign.py --root ROOT
VENV/bin/python SOURCE/deploy/spark/finalize-broad-campaign.py --root ROOT --output ROOT/handoff-broad-final --execute
```

Substitute the retained workspace paths for VENV, SOURCE and ROOT. The packaging
script defaults to a read-only plan, discovers completed parents and their loop
children, includes future fixed-screen tasks, and refuses active attempts before
execution. It exports each task through the sanitized read-only exporter and
verifies its manifest. The final portable verifier needs only Python's standard
library: run `python3 verify.py` after extracting the archive. It checks the full
file set, SHA256 identities and all nested evidence manifests.

The bundle is a focused working-tree source overlay and evidence package, not a
complete Git checkout or self-contained runtime installation. Task exports omit
artifacts above50MiB and explicitly list missing/omitted evidence. Image identities
are receipts; Docker images require a separately authorized archive. Model weights,
credentials, private environments, shared queues and the live mission database are
excluded. Source hashes preserve exact reviewed bytes; sanitized exported receipts
may have hashes different from their originals.

CLEANUP-INVENTORY.json lists task-owned preparation paths and retained image
references. It performs no deletion, cache pruning, image removal or shared queue
cleanup. Keep source candidate, build receipts, failed attempts and raw evidence
until their retention policy is explicitly decided.
