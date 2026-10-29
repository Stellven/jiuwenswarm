# Local Harbor results viewer

The workstation viewer is at **http://127.0.0.2:5175**. AI4Research remains at
**http://127.0.0.1:5175/chat/new**. Both listeners bind separate loopback addresses
on the single authorized localhost port, 5175. No application restart, Docker
port replacement, public listener, model invocation or runner change is needed.

`harbor_viewer.py` uses the installed Harbor **0.24.0** frontend and APIs. Its
small ASGI adapter combines job lists and comparisons across configured roots,
then dispatches job/trial/file requests to Harbor with the original root.
Windows extended-length UNC paths preserve access to deeply nested WSL files.
The adapter denies state-changing HTTP methods and live container streams.
Native launch/sign-in controls are not supported by this browse-only service.

## Start, inspect and stop

Run in PowerShell 7 in the normal Windows operator session that can access
`\\wsl.localhost\Ubuntu-24.04`. The viewer uses a hidden Windows Python process;
it is not a Windows service and does not automatically start after login.

```powershell
$viewerScript = 'D:\Codex Development Runs\jiuwenswarm-benchmark-suite\deploy\m1\harbor-viewer.ps1'
$viewerConfig = 'D:\Codex Development Runs\harbor-deployment-20261025\viewer\config.json'
$harborPython = 'D:\Codex Development Runs\.harbor-pilot-runtime\venv\Scripts\python.exe'
& $viewerScript -Action Start -Config $viewerConfig -RuntimePython $harborPython
& $viewerScript -Action Status -Config $viewerConfig
# Stop only the viewer process whose PID and command line match this config:
& $viewerScript -Action Stop -Config $viewerConfig
```

PID and stdout/stderr logs live beside the operational config. Stopping retains
all original jobs, archives, app containers and runner state. A busy listener or
unavailable WSL source is diagnosed rather than changing another service.
`GET /viewer/sources` reports available roots, provenance and discovered jobs.
`GET /api/health` reports viewer process health.

## Original data and new jobs

The operational config lists original WSL roots first, followed by retained
Windows archive fallbacks. Duplicate job names appear once; the first available
root containing that job is authoritative. No result files are copied,
rewritten or reconstructed by the viewer. Source availability and job discovery
are refreshed on every request; use **Refresh table** to see newly created jobs.

Currently configured original controller directories are:

| Source | WSL jobs root |
| --- | --- |
| CC and its paired baseline | `/home/s50066325/ai4r-codex-cc-harbor-20261025/jobs` |
| Corrected paper pilot | `/home/s50066325/ai4r-codex-text-harbor-20261025-corrected/jobs` |
| Initial paper pilot | `/home/s50066325/ai4r-codex-text-harbor-20261025/jobs` |
| Earlier integrated Codex pilot | `/home/s50066325/ai4r-codex-harbor-20261025/live/jobs` |

The CC archive fallback is
`harbor-deployment-20261025/cc-live-run/retained-original-results/jobs`.
Future actual Harbor jobs in the CC root, including paired Codex baseline jobs,
are discovered automatically once their job config/result files exist. If a
controller uses a different root, add its exact path and provenance to the
config's `sources` array. Config changes do not require a viewer restart.
Non-Harbor reports or proposed jobs do not become Harbor trials by being listed
in operational reports; they must have actual persisted Harbor job structure.

## Read the recorded outcome

An original filesystem source is not proof that a trial is running. Archive
fallbacks are retained history. Harbor timestamps and files report recorded
state; the viewer does not query the app's active-run state or launch work.
An incomplete record can also mean an interrupted controller, so inspect the
operator's run status before treating it as live execution.

Harbor trial completion means orchestration finished. Named reward dimensions
and verifier output determine what was measured. For the real paper job
`ai4r-codex-paper-corrected-20261025`, trial `paper__f7WPSmE` records
`evidence_integrity=1`, `live_integration=1`, **`execution_completed=0`**.
Its native scalar result of 1 is not scientific success. The paper execution
halted at `plan_infeasible` and was scientifically not scored; see
[HOST-CODEX-INTEGRATION.md](HOST-CODEX-INTEGRATION.md).
Missing native model, token or cost fields remain unavailable in Harbor; the
viewer does not fabricate them from separate summaries.

## Verified setup

The installed viewer rendered the three original Harbor jobs in the browser,
including the corrected paper job. Read-only smoke checks passed for the HTML,
job/trial details, named rewards, verifier output and original file listing
(55 entries), including a 3,261-byte original artifact whose UNC path exceeds
260 characters. Both 5175 listeners were confirmed loopback-only, and the
existing app's `/chat/new` still returned HTTP 200.

The owned viewer's start/stop/start lifecycle was exercised without modifying
the app or results. Its method guard was inspected in source; no request was
sent to a benchmark-launch endpoint. No RSI files were changed.
