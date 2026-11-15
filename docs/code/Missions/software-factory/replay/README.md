# Recorded workflow replay

The primary presentation is corrected C5 run
`11a6ce02166b4618baea6db59aaf44ec` in
[ascend-inner-stages.zip](../recordings/ascend-inner-stages.zip).
After the one-time Python dependency setup in [recordings](../recordings/README.md),
build and start the existing host with one command:

```sh
python -m jiuwenswarm.software_factory.demo --build
```

Open [the corrected walkthrough](http://127.0.0.1:5175/?view=workflow&lng=en&recording=11a6ce02166b4618baea6db59aaf44ec).
**Start walkthrough / Continue** stops at the next actual published receipt;
**Pause**, stage/event stepping and checkpoint selection retain the exact visible
event prefix. Read-only backend SSE paces original timestamps at the selected
speed. Browser timers do not advance the graph, and no workflow is re-executed.

C5 preserves the pre-task full workflow library
`c3e5a4c28656f2b8be1176964b4e05971efef8d82972461f57e060541cda2a1c`,
three real multi-child subworkflows, and six actual partial child selections.
**Run log** includes the recorded worker PID, in-process stage activity and
entrypoints, all external commands, full stdout/stderr and published raw logs.
The 27-file CANN [source ZIP](../deliverables/ascend-source/ascend-generated-source.zip)
has SHA-256 `30c509c862799b14cf5e80aea6c291ee653f7f574d004ca92316f2fceae07449`.
Separate CPU validation passed 352 comparisons; native compilation, device
execution, native equivalence and full-model inference remain `NOT_RUN`.

These standalone HTML files retain historical C3 runs and their original pool;
the earlier C4 source recording is retained in
[recordings/archive](../recordings/archive/ascend-source-before-inner-pool.zip).
Their metadata is not upgraded to C5's corrected hierarchy. The HTML files are
manual offline fallbacks. Download a file and
open it in a browser; all data is embedded and no network connection is required.
They use the same event-prefix projector as the integrated page.

| Recording | Recorded task | Events |
| --- | --- | ---: |
| [core.html](core.html) | Source discovery → routing/activation/aggregation → C++ generation → build → verification → source ZIP | 162 |
| [mixed.html](mixed.html) | Routing plus a scalar operation, each with its own numerical acceptance | 164 |
| [failed-oracle.html](failed-oracle.html) | Recorded numerical mismatch and downstream halt | 128 |

Use **Previous**, **Next**, the timeline, or **Final result** in the offline files.
Click a node to inspect its actual commands. Open **Code Diff** or **Source**
after their recorded publication event. Rewinding removes later
source and execution states. The recording preserves the original run ID,
timestamps, source commit, execution recipe and artifact SHA-256 values.

Browsers with enterprise policies that prohibit local HTML can serve this
directory through an approved local web server or use the integrated Workflow
page. The replay has no execution endpoint and makes no network requests.

## Export another existing run

```sh
python -m jiuwenswarm.software_factory.replay_export \
  --run-dir .factory-runs/RUN_ID --output recorded-workflow.html
```

The exporter checks the retained event stream, graph revisions, artifact bytes
and captured source recipe. It writes the replay outside the original recording.
Original STRATA source attribution and license are available in the replay and
the embedded source ZIP.
