# Factory-generated source projects

The primary delivery is the corrected C5 [Ascend/CANN source project](ascend-source/source/README.md)
and its [source ZIP](ascend-source/ascend-generated-source.zip), published by run
`11a6ce02166b4618baea6db59aaf44ec`. All 27 extracted files match the published ZIP,
whose SHA-256 is
`30c509c862799b14cf5e80aea6c291ee653f7f574d004ca92316f2fceae07449`.
It includes CANN runtime support and generated routing, SwiGLU and aggregation
sources, together with source and generation manifests.

The [corrected recording](../recordings/README.md) retains the full pre-task
workflow library (`c3e5a4c28656f2b8be1176964b4e05971efef8d82972461f57e060541cda2a1c`),
three real multi-child subworkflows and six actual partial child selections.
Its separate CPU reference compiled and passed 352 numerical comparisons.
The native manifest records compilation, device execution, native numerical
equivalence and full-model inference as `NOT_RUN`; CPU reference results do not
establish those native acceptance layers. Follow the package README for the
required CANN toolchain and target configuration.

The earlier CPU source projects remain historical outputs of their original C3
tasks and pool:

| Project | Source-selected operations | Recorded run |
| --- | --- | --- |
| [core](core/source/README.md) | Routing, SwiGLU, expert-output aggregation | `6db7a2b968c8434eaa9a508a6d16a7cf` |
| [normalization](normalization/source/README.md) | Weighted RMS normalization | `02446be989844a3fb7e43dc9bd6a8e0a` |
| [mixed_oracle](mixed_oracle/source/README.md) | Routing and scalar scaling, with independent per-operation acceptance | `b152d434c8e14b01adc8c4aa40ad83f2` |

Each contains the exact published source ZIP and extracted project. Build these
CPU projects from their source directories:

```sh
cmake -S . -B build -DSTRATA_CORE_BACKEND=CPU
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

Start the integrated host with
`python -m jiuwenswarm.software_factory.demo --build` and open
[the corrected C5 walkthrough](http://127.0.0.1:5175/?view=workflow&lng=en&recording=11a6ce02166b4618baea6db59aaf44ec)
to inspect source diffs, actual stage receipts, complete process logs and
publication-gated downloads. Guided playback streams recorded events through
read-only backend SSE without rerunning the factory. Setup details and the C4
archive are in [recordings](../recordings/README.md).
