# Optional historical references

These pinned versions are reference material, never required build input. They remain immutable in Git and are not updated when the maintained design changes. Use the [current package](README.md) for product and architecture decisions.

| Reference | What it preserves |
|---|---|
| [Original architecture directory](https://github.com/Stellven/jiuwenswarm/tree/343a77dbd5e6dcd18de2e57794cc992d36c2f35c/docs/architecture) | Earlier overview, B1 design, capsule discussions and diagrams before replacement by the current design. Useful for understanding superseded reasoning. |
| [Original architecture overview](https://github.com/Stellven/jiuwenswarm/blob/343a77dbd5e6dcd18de2e57794cc992d36c2f35c/docs/architecture/OVERVIEW.md) | Historical source referenced by the AI4R-001 records. It does not govern Intent Compilation and Verification Slice (formerly TRIAL-1). |
| [Package before this cleanup](https://github.com/Stellven/jiuwenswarm/tree/62d1fe7069baf15379487fdd6cf20e3c459263ad/docs/architecture/build-package) | Exact October 6 PRD/design package before navigation and coverage simplification. Includes the earlier owner-oriented coverage map. |

No archived source is a fallback requirement. Adopt a historical idea only through an explicit current design decision. Retain existing coding identities when reconciling older records; their source assumptions must be checked against the current PRD and decisions.

## Muk cleanup checkpoint

On 2026-10-06, pinned Git snapshot `0e560729374cfb35119a9d5b42b43860c5d513ad`, retained by branch `archive/muk-design-before-cleanup-2026-10-06`, preserved the muk architecture tree, product captures and task supplement before removal from active reading paths. It contains exact local draft bytes and older nested snapshots. Files already absent locally remain recoverable from parent `b710bed752e66a21c993e77d90fa588598140924`.

These are optional historical references, not another maintained design. Inspect specific original files without restoring them into active directories:

```text
git show 0e560729374cfb35119a9d5b42b43860c5d513ad:docs/architecture/immediate-plan.md
git show 0e560729374cfb35119a9d5b42b43860c5d513ad:docs/tasks/M1/TASKS.md
git show b710bed752e66a21c993e77d90fa588598140924:docs/product/prd-m1-full-2026-10-02.txt
```

The snapshot branch is local until explicitly published. Preserve that ref when transferring the cleanup to another checkout. No snapshot supplies missing current requirements; use the [maintained reading route](README.md#human-super-important-read-understand-the-whole-system).

## Final docs cleanup â€” October 7, 2026

Removed the superseded `docs/archive/` tree, proposed `docs/adr/0001-codex-subscription-runtime.md`, and task-local `docs/tasks/AI4R-001/OVERVIEW.md`. Native coding records and historical execution results remain; incoming design links now point to pinned versions. These documents add no current architecture requirements.

Tracked originals are preserved at `f600f00a8a4d1f2cc2224ba68a6abeec69395ffa` on `ai4r_muk`: [retired architecture archive](https://github.com/Stellven/jiuwenswarm/tree/f600f00a8a4d1f2cc2224ba68a6abeec69395ffa/docs/archive), [proposed ADR](https://github.com/Stellven/jiuwenswarm/blob/f600f00a8a4d1f2cc2224ba68a6abeec69395ffa/docs/adr/0001-codex-subscription-runtime.md), [task overview](https://github.com/Stellven/jiuwenswarm/blob/f600f00a8a4d1f2cc2224ba68a6abeec69395ffa/docs/tasks/AI4R-001/OVERVIEW.md). Before editing or removal, exact local bytes were copied and SHA256-verified outside the checkout at `architecture-checks-2026-10-07/muk-before-final-docs-cleanup/`; `preservation.json` records the checkpoint, paths, sizes and hashes. Keep that local preservation folder when transferring uncommitted work.

The [current status](README.md) distinguishes adopted design, pending coding registration and unestablished runtime acceptance. Received PRD and CC source snapshots retain their bytes; the current receipt is indexed separately. Local history and backups are optional provenance, never fallback requirements.

## Final branch cleanup â€” October 7, 2026

Checkpoint `98cc3db956ee49884991fa50c4f26b9e7ec9a0d9` preserves the retired SOP handbook/ZIP/manifest and old `output/pdf/m1-architecture-2026-10-05.pdf`. Use live SOP sources and this design-package. Historical task observations are retained, with retired-template links pinned to their actual original revision. Removed demo videos are preserved in that checkpoint; current usage pages no longer advertise absent media. Empty verification placeholder removed. Local Obsidian workspace state remains on disk but is untracked/ignored.

Exact pre-edit local bytes and SHA256 hashes are preserved outside the checkout at `architecture-checks-2026-10-07/before-final-branch-cleanup/`. Already-absent videos are recorded by checkpoint Git blob identities. No original PRD/CC source or historical runtime outcome was changed. Git history is optional provenance, never a parallel architecture authority.
