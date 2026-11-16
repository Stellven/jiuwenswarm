# Recorded workflow replay

These HTML files replay existing factory records. No workflow is re-executed.
Download a file and open it in a browser; all playback data is embedded and no
network connection is required. The same event projector drives the host UI's
**Replay** mode.

| Recording | Recorded task | Events |
| --- | --- | ---: |
| [core.html](core.html) | Source discovery → routing/activation/aggregation → C++ generation → build → verification → source ZIP | 162 |
| [mixed.html](mixed.html) | Routing plus a scalar operation, each with its own numerical acceptance | 164 |
| [failed-oracle.html](failed-oracle.html) | Recorded numerical mismatch and downstream halt | 128 |

Use **Play**, **Pause**, **Previous**, **Next**, the timeline, and **1×/4×/16×**
speeds. Click a node to inspect its actual commands. Open **Code Diff** or
**Artifacts** after their recorded publication event. Rewinding removes later
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
