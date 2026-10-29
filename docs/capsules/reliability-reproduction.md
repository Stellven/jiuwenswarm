# Reproducing isolated capsule checks

Run these commands from the repository root in PowerShell. The host needs Docker
and PowerShell; Python, the SDK, Codex CLI and test dependencies stay in the
existing verification image. These commands do not start another application or
mount application credentials. The normal app/runner pair remains unchanged.

```powershell
./deploy/m1/check-capsules.ps1 -Group capabilities -Build -RepeatCount 2
./deploy/m1/check-capsules.ps1 -Group replay
./deploy/m1/check-capsules.ps1 -Group status
./deploy/m1/check-capsules.ps1 -Group planner
./deploy/m1/check-capsules.ps1 -Group builder
./deploy/m1/check-capsules.ps1 -Group benchmark
./deploy/m1/check-capsules.ps1 -Group completion
./deploy/m1/check-capsules.ps1 -Group executor
```

Build once, then reuse that image. `-Image NAME` selects an existing verification
image; the launcher resolves and runs its immutable image ID. `-Group all` runs
the union of the named groups once, without duplicate test files. This is a
development check set, not the entire repository suite or a scientific campaign.

For a smaller reproduction, select one test in a group:

```powershell
./deploy/m1/check-capsules.ps1 -Group replay -Case tests/unit_tests/research/test_evaluation_replay.py::test_actual_verifier_rejection_halts_valid_replay_with_call_evidence
```

Each invocation prints its evidence directory. `-Output C:/Temp/my-new-check`
chooses a new directory; existing evidence is never overwritten. Repeats use
separate fresh containers and evidence directories. Repeating a test measures
repeatability; it does not increase the number of distinct covered cases.

| Evidence | Meaning |
| --- | --- |
| `launch.json` | Exact Docker argument list, image tag/ID, architecture and repeat index |
| `source-manifest.json` | Raw SHA256 for the captured source, fixtures, contracts, check tooling and dependency files |
| `pytest.log` | Full output, including failures and warnings |
| `junit.xml` | Per-test outcomes, durations and skip reasons, if pytest completed publication |
| `result.json` | Exact pytest arguments, Python version, counts, elapsed time, exit status and evidence-file hashes |

The source mount is read-only, networking is disabled, and each container has a
4 GiB/256 PID envelope. SDK logs and executor resources use temporary storage.
`-TimeoutSeconds` bounds the complete group, including imports; the default is
600 seconds. Timeout/interruption retains evidence and terminates the test
process group. A source-file change during a run invalidates its passing status.
The explicit SyntaxWarning filter covers an upstream SDK dependency; the other
ordinary pytest checks remain active.

The results distinguish the following claims:

- Capability groups execute the actual capsule and check code with deterministic
  inputs and controlled model responses. They check calculation, preservation of
  input data, task identity, file safety and provenance.
- Replay checks prove that malformed evidence stops before inference, and that
  an independently recorded verifier FAIL blocks advancement and product
  acceptance. Their model responses are controlled; they do not measure live
  verifier judgment quality or actual scheduler release.
- Status checks exercise original dispatch chronology, interruptions, recovery,
  cancellation, read-only projections and rejection of substituted evidence.
- Completion checks inspect the pinned native Codex profile and exercise the
  governed completion boundary. They do not sign in or make live model calls.
- Builder/Benchmark checks exercise the bounded agent loop, tested-byte custody
  and protocol mechanics. They do not establish an accepted live Pi candidate
  or measured scientific improvement.

The separate authenticated PDF summary run and its recovered archive are recorded
in [the M1 execution note](m1-local-process.md). Live repeated single-capsule
quality testing still needs the protected E2/E3 profile/assets/runtime authoring
path. The current product capture has no evaluation profile; passing development
checks do not activate one or turn test outputs into product results.

## Recorded October 26 result

Source `176a0ae8` passed **215 selected tests**, with no failures, errors or skips:
capabilities 38; replay 8; status/recovery 31; Planner 26; Builder 42;
Benchmark/protocol 32; completion boundary 28; M1 executor/provenance 10.
The groups partition this run; earlier overlapping totals are not added.
[Exact receipt and evidence](verification-20261026/reliability/summary.json).

Both negative controls behaved as required: a 10-second group timeout returned
124; a temporary source change invalidated a test-passing run and returned 2.
The probe was removed. Earlier two capability repetitions each passed 38 checks
on matching captured source, before the final custody correction.

The app image was rebuilt and restarted. Authenticated readiness and status of
the existing completed PDF run passed without new model calls. Wait for app
initialization before issuing a runner grant: native startup replaces the parent
session and revokes earlier grants. An early grant in this check returned HTTP401;
a fresh scoped grant after startup passed. Keep credentials in the private volume
and use the existing issuer/refresh mechanism. A successful frontend HTTP200
alone does not establish authenticated research readiness.
