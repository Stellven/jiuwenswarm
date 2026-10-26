# M1 reliability checkpoint â€” October 26, 2026

Working code was pushed to [ai4r_M1 at `ab0d9c7f`](https://github.com/Stellven/jiuwenswarm/commit/ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7).
The tested implementation is `a138e435fe0f6e33a0684ac0458404e3d3d1700b`.

- **319 selected Docker checks passed**, zero failures/errors/skips, unchanged source.
- An independent fresh Git archive passed **28 focused checks** and the Planner pin check. These selections overlap.
- Two finite-startup failures reproduce on the previous M1 in the same image; retained as historical limits.
- **No new live ML acceptance, independent ML score, complete ML journey or upstream opponent comparison was run.** This is a software checkpoint, not completed benchmark acceptance or proven accuracy gain.

Read [the full report](m1-report.md), [verification summary](verification-summary.json),
and [the notebook activity](notebook/Activities/2026-10-26%20M1%20Reliability%20and%20ML%20Readiness%20Checkpoint.md).
[Original raw evidence on M1](https://github.com/Stellven/jiuwenswarm/tree/ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7/docs/capsules/verification-20261026/ml-readiness/).

The update includes opt-in host-bound evidence review, explicit source-preserving
adapters, new immutable utility releases, protected E2/E3 preparation and bounded
ML task/budget tooling. Evidence-aware E2 remains explicitly unavailable before
a model call; historical output-only replay still works. New runtime commands
require rebuilding from the published source; the existing signed-in app was not
replaced.

The local notebook update has seven pre-edit backups, three exact prompt captures,
and validation with **zero errors**, including **14,290 unchanged archive rows**.
Only the current note, prompts and maintenance receipts are published here.
Byte hashes are in [the export manifest](export-manifest.json). Existing design,
PRD source, unrelated README and Paper2Agent work were preserved.
