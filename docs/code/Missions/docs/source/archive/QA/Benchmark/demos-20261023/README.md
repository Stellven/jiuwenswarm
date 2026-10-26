# Three small AI4Research demonstrations

These are demonstrations, not M1 acceptance. Only Case 1 and Case 3 are to be run now; Case 2 was deferred by the user. Each case folder has public inputs, its case JSON and a reviewer-only folder. Reviewer folders and this builder are outside all runner/app mounts. Public copies only are published into the existing Benchmark/cases and Benchmark/inputs mounts. Explicit input rows with upload:false capture infrastructure provenance; they contain no labels, expected answers or reference scores.

Do not modify the app, fixed baseline, approved environment or protected scoring fixture to force an outcome. The CPU request may be blocked by the installed majority-baseline classification contract; the GPU case additionally needs a real approved CUDA/PyTorch executor. Preserve blocked outputs. Runner records installed build and observed model events; an additional linked run-manifest.json records checkout commit, physical host, app image, missing fields and reviewer observations without claiming the runner natively records every field.


Start with [RESULTS.md](RESULTS.md) for the actual outcomes and links. Each case folder contains case.json, public/, reviewer/, run-manifest.json and RESULT.md. Only copy/upload public inputs, never reviewer materials or build_demo_cases.py.

The runner-ready case files are under ../cases/demos-20261023/. A future deliberate rerun can use a fresh campaign ID:

```powershell
cd D:\research\ai_for_research\runs\jiuwenswarm
python deploy/m1/runner.py run --cases /cases/demos-20261023/case1-cpu.json --campaign-id cpu-demo-NEW-ID --json
python deploy/m1/runner.py run --cases /cases/demos-20261023/case3-paper.json --campaign-id paper-demo-NEW-ID --json
```

Do not launch case2-gpu.json now: the user deferred it and its required execution environment is not available in the current app. Its explicit runtime/preflight metadata must be recaptured after any future approved hardware/environment change; do not reuse stale metadata as evidence of new GPU capability.
