# Evidence-bound hypothesis proposal

The agent supplies its own mechanism and measurable prediction; this capability does not choose from a fixed candidate list. `propose` validates bounded structured input and persists an immutable `hypothesis_proposal` observation in the current task. The deterministic observation ID is `hypothesis-proposal-<hypothesis_id>`. Identical replay returns the original proposal; conflicting reuse fails. No experiment, contract, grant or acceptance is created.

Required hypothesis fields: `mechanism`; `applicability` with `hardware`, `model`, `source_revision`, `limits`; `evidence_ids`; `primary_source_urls`; `changed_variable` with one `name`, `baseline`, `candidate`; `prediction`; `required_counters`; `falsification`; `correctness_obligations`. Text is bounded, citations are 0..10 HTTPS URLs, evidence references are 1..20 observations/artifacts, counter/obligation lists are 1..20 items, and total hypothesis JSON is at most32KiB. Evidence is resolved only in the current task and explicitly readable tasks, with source task and record hash retained.

URLs are retained as citations and never fetched. Primary-source classification, paper claims, hardware/model transfer, causality and stated variable isolation remain unverified agent assertions. A one-variable shape cannot establish that the proposed intervention actually changes only one mechanism. Host admission and a separately frozen contract must check this before execution. The receipt always states proposed/unmeasured, citations_unverified, no performance/correctness evaluation and no execution/promotion authority.

Candidate bridging to methodology ablation remains a separate reviewed integration: an operator-frozen template must explicitly list the proposed hypothesis ID. Existing builtin candidates and scored contracts keep their policies. A proposal itself is never an accepted optimization.

A hypothesis may originate entirely from scoped local profiling or source evidence. In that case supply `primary_source_urls: []`; cited scoped evidence IDs and a nonempty source revision remain required. Supplied URLs retain the same unverified citation labels and are never fetched.
