# October 25 integration and restart checkpoint

The user requested all our features on latest `ai4r_M1`, capsule demonstrations,
repairs and whole-system testing. They selected Docker as the live target and
asked to restart the machine before that testing. Work is saved for continuation.

Merge `c737213bc3249470dfde75a1deecf1b5dc73cb80` joins remote M1
`809351f8993661a9fdc6e4e635d48f3d262f991b` and Builder branch `db34c50d`.
The integration branch is `m1/all-features-20261025` in the existing
`jiuwenswarm-m1-reviewed-integration` checkout. `ffa0b381` additionally fixes
contract export of ordinary text/ZIP outputs without masking byte-custody errors.
Local `ai4r_M1` and the remote have not yet been advanced to this candidate.

All seven capsule feature branches and both deployment feature branches are
ancestors. Existing Planner, utility capsules, deployment operations, metric
protocol and explicit model-selection behavior are retained. New immutable
releases are Builder `m1-16`, classification Benchmark `m1-8-agent-pi`, and Pi
Benchmark `pi-m1-2`. Builder/Benchmark and Planner/PDF source-pin checks pass.
The two different historical `m1-13` Builder implementations are distinguished
by pinned carrier identity for receipt, operation and recovery handling.

Integration testing found and fixed an actual Pi registration lookup using
`cc_name`/`cc_version` instead of LibraryService's `name`/`version` fields.
It also found the export bug above. The request-allocation unit test now states
its isolated scope, supplies its trusted preparation stub, and uses a bounded
event wait rather than hanging indefinitely on invalid placeholder inputs.

## Evidence so far

- **10 actual Linux executor integration checks passed**, with raw receipts and
  captured proof/log bytes in `verification-20261025/kernel`. These exercise
  actual namespace isolation, UID/capability drop, network denial, memory/pid/
  wall limits and cancellation. An obsolete RPC fixture now separately checks
  refusal without original active-attempt resources. Production guards remain.
- The controlled test layout used an outer bubblewrap mount namespace to map
  Ubuntu's actual `/usr/bin/python3.12` to the image's `/usr/local/bin/python3`.
  No host interpreter symlink or production setting was changed. Cgroup tests
  used the explicitly owned `ai4r-merge20261025-executor` delegation. These are
  real kernel mechanics, not an installed application or model acceptance.
- Installed the actual SDK distribution from an owned local Git clone at exact
  `9e3390195a9ea15235b2b5f7412cb2aa440622cc`. Pip retained genuine VCS provenance.
  Installation used `--no-deps`; the complete dependency closure remains
  unqualified. This resolves the earlier absent-distribution pin check.
- The full research unit suite was split across four bounded shards after
  diagnostic runs. Shard 3 stopped at **89 passed, 12 failed**: older dedicated
  CLI Builder qualification/launcher fixtures and a control-profile fixture
  need investigation (including a missing `/opt/ai4r/...` installed asset).
  Shards 0/1/2 were interrupted for the requested restart; their partial logs
  are not passing suite receipts. Prior October 23 results do not validate this
  merge. No completed all-capsule suite is claimed.
- The actual whole-system procedure failed closed with
  `AI4R_FOUNDATION_TARGET_REQUIRED`. No authenticated campaign, Codex-built Pi
  candidate, accepted live verifier assessments or scientific measurements ran.

## Continue after restart

1. Check the saved source HEAD and clean worktree; read
   `verification-20261025/restart-state.json` and the four shard logs.
2. Confirm ordinary Docker API access after the user's restart. Both Windows
   contexts previously had missing daemon pipes. Docker Desktop processes were
   present but its service was stopped; attempting `Start-Service` was denied.
   Do not reset Docker data, fabricate service readiness, or weaken confinement.
3. Use the checked-in two-image operations on localhost **5175**, retaining exact
   app/runner image identities. Bind the genuine installed target and complete
   the existing model authentication. No API key or fabricated credential.
4. Investigate shard failures, rerun capsule workers and their independent
   checks, then run protected installation/system procedures and the campaign.
   The current native Builder replaces the dedicated CLI Builder, but historical
   launcher behavior must remain honestly distinguished from current acceptance.
5. Pi requires its own explicit checking-asset calibration/admission; the normal
   catalog calibration currently prepares only seven core scientific stages.
   Do not treat authored Pi pins or kernel tests as admission or activation.
6. Promote the integrated source onto `ai4r_M1` after resolving source failures,
   document exact completed tests, and update the notebook's current baseline.
   RSI and model-router implementation remain outside this task.

Exact completed and interrupted reports are retained in
[verification-20261025](verification-20261025/). Temporary shard helpers were
saved in that directory for reproducibility; they are verification tools, not
product startup dependencies.
