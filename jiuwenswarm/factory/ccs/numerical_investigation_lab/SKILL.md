# Investigate numerical divergence

Use this package for one bounded diagnosis job: inspect retained outputs with first_divergence, freeze replay_spec before capture, then compare_logits on captures with matching full provenance. Read METHOD.md for the schema and bounds. These tools are self-contained CPU tools and do not route through factory.api.

1. Retrieve only relevant retained input/output manifests. Preserve raw hashes. Run first_divergence; its output establishes token/finish identity only, and does not authenticate matched workload provenance.
2. Reconstruct the exact prompt IDs and common teacher-forced output prefix from the source artifacts. Independently verify immutable model, tokenizer, source/build, precision, routing and complete launch-profile manifests. Explicitly declare the sole intended treatment. Reject mismatches outside it.
3. Retain the numerical policy externally before collecting results; bind declaration_id and verify chronology. Use zero tolerances when the existing exact contract requires it. Never convert a failed exactness contract into a tolerance pass.
4. Freeze replay_spec and its hash. Use capture_plan for the source-pinned initial DS4 diagnostic, then import_capture on completed retained evidence before compare_logits. If actual engine logit capture evidence is absent, report the gap. Do not fabricate vectors or call synthetic examples live instrumentation.
5. Under separately admitted existing lab lifecycle, collect paired observer-off/on evidence, common-history full logits and capture provenance. Run compare_logits, retain receipts and raw vectors, and distinguish exact identity, tolerances, top choices, margins and quality evidence.
6. Report the first observed output divergence and numerical comparison, with unknown cause where unsupported. Attach observations to the existing investigation branch. Never launch new experiments from these tools.
