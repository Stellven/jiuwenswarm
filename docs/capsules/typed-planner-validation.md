# Typed Planner validation — October 23, 2026

- Windows: 109 passing selected checks (103 in the integrated suite, five native
  trace/index export checks, one additional typed-cycle repair pipeline check).
- Linux/WSL: 39 passing Planner, catalog, bootstrap and installed-release checks.
- Fresh Linux development-profile capture and repeat capture preserve identical
  state; static default confirmed. This does not grant production qualification.
- `freeze_planner_release.py --check`, Ruff F checks and Git whitespace checks pass.
- Controlled transport tests exercise real Compiler, scoped runner calls,
  deterministic checks, independent semantic rejection, protected gates and
  Binder freeze. Both malformed JSON and a typed graph cycle can be corrected
  once. Exhausted repairs and rejected reviews do not freeze or accept a DAG.
- Generic graphs and an eight-node scientific graph validate from exact supplied
  contracts; bad pins, incompatible schemas, missing coverage/checks, cycles,
  effect/budget/resource excess and scientific bypass attempts fail.
- Foreign artifacts cannot be attached to Planner attempt events. Original
  rejected candidates/diagnostics remain unaccepted but retained in run exports.
- The existing native trace test expected obsolete eager packet copies. It now
  checks the current v2 index, exact deferred packet export and foreign-run
  rejection; the production trace-capture function is unchanged.

The initial broad run retained two failures: Windows long-path handling masked
an outdated native trace test assertion, and the finite-run test requires the
pinned OpenJiuwen runtime. Rechecking with a short temporary path and on Linux
identified the trace test mismatch above; its corrected five cases pass. The
finite-run/native-runtime test remains unrun successfully in these isolated
environments because the pinned OpenJiuwen distribution is absent. No fake
runtime installation, qualification receipt or model result was substituted.

Docker's Linux daemon is unavailable on this machine. Live Docker containers,
authenticated model planning quality, full scientific execution, SSH deployment,
ARM64 and Spark execution were not verified in this revision. Controlled
candidate tests establish host boundaries, not model intelligence or research
quality. Production catalog calibration and connected tests remain separate.

Deployment usability (`e296d2b`) was pushed to remote `ai4r_M1` through the user's
existing authenticated SSH connection. HTTPS credentials were unavailable.
The Planner feature remains isolated on `m1/required-typed-planner`.
