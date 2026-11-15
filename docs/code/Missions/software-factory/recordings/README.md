# Verified production recordings

The primary presentation is [ascend-inner-stages.zip](ascend-inner-stages.zip),
corrected C5 run `11a6ce02166b4618baea6db59aaf44ec`. Its 132 original events,
15 stage instances and 54 artifacts record Ascend/CANN source generation and
separate CPU reference validation. Playback does not execute another factory task.

## Start the existing host UI

Install the Python dependencies once, then build and start the host with one
command from the repository root:

```sh
python -m pip install -r jiuwenswarm/software_factory/requirements-demo.txt
python -m jiuwenswarm.software_factory.demo --build
```

Open [the corrected C5 walkthrough](http://127.0.0.1:5175/?view=workflow&lng=en&recording=11a6ce02166b4618baea6db59aaf44ec).
Subsequent starts can use `python -m jiuwenswarm.software_factory.demo` with the
verified existing frontend build. The existing host sidebar, Workflow page and
API share port 5175.

**Start walkthrough / Continue** streams original events to the next actual
publication checkpoint. **Pause**, event/stage navigation and checkpoint
selection expose the corresponding recorded prefix. Backend SSE uses original
timestamps at 1×/4×/16×; browser timers do not advance the graph. **Run log** shows
the recorded worker PID, chronological stage activity, full references,
entrypoints, published files, and complete external-command stdout/stderr with
raw-file downloads. Source and downloads follow their recorded publication.

## Corrected C5 evidence

The complete workflow library was captured before the first task event. Its
canonical SHA-256 is
`c3e5a4c28656f2b8be1176964b4e05971efef8d82972461f57e060541cda2a1c`.
It retains 16 workflows, 26 subworkflows and 29 complete child references,
including these three actual multi-child parents:

| Frozen parent reference | Declared child stages | C5 partial selection |
| --- | --- | --- |
| `function_extraction/function_extraction` | `discover`, `extract` | `extract` for each of three source operations |
| `scalar_implementation/scalar_lowering` | `extract`, `lower` | `lower` for SwiGLU and aggregation |
| `cooperative_implementation/cooperative_lowering` | `extract`, `lower` | `lower` for routing |

Six `workflow.expanded` receipts bind these partial selections to actual nodes
and frozen parent hashes. Selection and excluded siblings use full paths;
the same canonical stage executing through another parent does not select that
sibling.

The published [27-file CANN source ZIP](../deliverables/ascend-source/ascend-generated-source.zip)
has SHA-256
`30c509c862799b14cf5e80aea6c291ee653f7f574d004ca92316f2fceae07449`.
The separate CPU reference compiled and passed 352 numerical comparisons.
Native compilation, device execution, native numerical equivalence and full-model
inference remain `NOT_RUN` in the recorded native manifest.

## Historical recordings

| Bundle | Original run | Preserved scope |
| --- | --- | --- |
| [core.zip](core.zip) | `6db7a2b968c8434eaa9a508a6d16a7cf` | C3 routing, activation and aggregation source construction with CPU validation |
| [normalization.zip](normalization.zip) | `02446be989844a3fb7e43dc9bd6a8e0a` | C3 normalization from the real elementwise source module with CPU validation |
| [mixed.zip](mixed.zip) | `b152d434c8e14b01adc8c4aa40ad83f2` | C3 task-selected operators with an independent numeric oracle |
| [native-target.zip](native-target.zip) | `baf3d77a8301423180ccda45fb11c66b` | Native/model/original-comparison request with its actual blocked outcome |
| [archive/ascend-source-before-inner-pool.zip](archive/ascend-source-before-inner-pool.zip) | `528acf3c90ff4d7c95e67d4fcff15c01` | C4 source generation before the multi-child pool correction |

C3 retains its original pool and task-driven path differences. C4 remains an
archive of the earlier singleton-pool implementation. Neither receives C5's
workflow library or partial-selection claims retrospectively.

All bundles preserve original requests, source commit
`13eedf552417a6a791a7d13c6597e24300ee3a09`, raw event bytes, process metadata,
recipes and artifact hashes. Explicit content-addressed path maps relocate files
without rewriting historical identities. Ownership remains `local-operator`;
the local launcher uses that authority, while protected host accounts retain
separate access checks. Replay and artifact routes are read-only.
