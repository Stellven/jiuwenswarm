# Architecture entry

| Package | Use |
|---|---|
| [design-package](design-package/README.md) | Maintained full architecture; human explanation, detailed responsibilities and AI reference |
| [design-package-compact](design-package-compact/README.md) | Same M1 and authoritative contracts, with less explanatory prose |

Start with the assigned package README. Both are portable; compare only matched versions during experiments. The PRD remains verbatim in both. The full package owns architectural changes; synchronize shared content into compact.

The [very condensed design](very-condensed-design.md) is a preserved comparison experiment from before the three-level revision. It is not current guidance for the restored shared contracts. The maintained package defines the bounded Intent Compilation and Verification Slice and complete M1 architecture.

Product requirements belong to the PRD; detailed realization and evidence belong to TASKS/TASK/Spec Kit. Superseded architecture and generated snapshots are retained only as optional [pinned history](design-package/history.md). Local editor workspace state is not a project document.

Extra intent and evolving context may be kept in the Git-ignored local `notes/` folder as Obsidian-compatible Markdown. Notes are outside the review package and main delivery; material decisions must be reflected in the maintained design. Shared vault settings remain versioned, while pane/session state stays local.

## Current design-depth experiment

The [experiment registry and original protocol](experiments/README.md) preserve the first pair. The [October 8 comparison](experiments/m1-contract-review-2026-10-08/README.md) freezes the repaired full design and a stronger compact input with identical contracts, examples and source decisions. It is an experimental input, not maintained architecture. The older very-condensed design remains unchanged. Design authors use [design method](design-package/design-method.md) for depth, tiered human review and change impact.
