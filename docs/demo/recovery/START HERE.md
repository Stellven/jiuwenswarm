# 20261113 Satay CC Demo and Recovery prepresentation

Open `20261113 Satay CC Demo Console prepresentation.html` for the offline demonstration. It needs only a browser and the adjacent evidence directory. The page offers the architecture, methodology, original video and result sources. No inference or network access is needed to present it.

For Codex on Satay, run `bash scripts/start-codex.sh` from this extracted package. This starts a new interactive Codex session with AUTONOMOUS.md as context. It does not clone the previous chat, grant blanket permissions, or automatically start model work. Existing Codex authentication is reused, never bundled.

## What is ready

The recorded process applies a demand-fill component, builds it and evaluates it through JiuwenSwarm. That fresh 32-token comparison is preliminary. The headline improvement comes from a separate recorded 64-token experiment, J-OM13, using fill plus predictive reads. Both sources are included; they are never treated as one run.

The package includes shallow source-recovery bundles preserving exact pinned commits for the three working repositories and a separate engine bundle preserving plain, fill-only and headline source. See SOURCE-PINS.json for actual revisions and ref names. Source restoration is independently checked, without using GitHub. History beyond the pinned source snapshots is intentionally omitted; the Git bundles and adjacent .shallow files must stay together. A model, Docker base images, CUDA/JetPack and authenticated agent runtime remain installed dependencies; this is not a complete bare-metal disaster image.

## Reading order

1. PRESENTATION.md: timed story and evidence boundaries.
2. AUTONOMOUS.md: bounded continuation instructions.
3. RECOVERY.md and context/recovery/: restart and checkpoint procedures.
4. ONTOLOGY.md: contract, engine slice and work-node distinction.
5. ATTACK QUESTIONS.md: concise answers and limitations.
6. VALIDATION.md: checks actually completed, including any remaining blocker.

Everything in `context/historical/` and original evidence is an immutable historical record. It may name shelved Run 5, older disk capacity, outdated startup instructions or earlier claims. It is not the current runbook and does not enter the presentation. Current instructions are here and in the included recovery documentation.

No Danta storage has been used. Keep active work and SQLite on internal storage. Do not restore archived state over a live workspace.
