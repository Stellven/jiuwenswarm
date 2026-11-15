# Integrate a candidate into the next experiment

The package ships two pure configuration transforms and their descriptors in
COMPONENTS.json. Implementations live in the declared factory modules, while the
native mechanism lives in pinned Strata source revision
ffa80d73133ea5c548aefe57889a16e8085a938f. Seal/package identity alone does not identify
external source bytes, images, hardware or workload. Record those separately.

For prefill, supply a full-six/static-cache profile with explicit positive
`--prefill-chunk` in 256/512/1024 and explicit `--dspark none/on`. `apply_prefill`
changes only that chunk; it preserves drafting, environment, image and limits.
Confirm the effective positive chunk, full-six engagement, peak memory and placement
at runtime. Longer chunks can trade memory/TTFT against throughput; no benefit is
presumed. Compare prefill plus decode under a frozen correctness gate.

For verified drafting, supply the fixed full-six profile with `--dspark-conf 0.65`,
explicit `--dspark none/on`, no adaptive expert cache, no prefix reuse and the fixed
memory/CPU envelope. `apply_drafting` changes only none/on. Preserve confidence and
workload across arms. Require offered/accepted draft counters and full target expert
engagement; target verification alone does not prove byte identity or broad accuracy.
Retain baseline A/A variability and frozen public-task correctness evidence.

For either transform:

1. Read the baseline from retained evidence and preserve its identity. Pass its JSON
   profile to the transform, inspect changed_paths and before/after hashes, and save
   the returned profile/change receipt with evidence IDs and hypothesis.
2. Hold all other variables fixed. Check applicability against the frozen contract,
   actual source/image, and task policy. Do not combine prefill and drafting changes
   in one initial treatment. An invalid profile fails closed rather than normalizing
   away fixed obligations.
3. Where supported, `qualify_prefill` records the bounded prefill invariant and policy
   assessment against the explicit policy's supported prefill workbench release,
   without requiring a separate agent tool call. It does not qualify this whole
   analysis package. Other mechanisms still need their own supported
   verification/admission; there is no universal checker for every package capability.
4. Select only an already admitted template matching the exact treatment. A transform
   does not insert itself into a template or mutate a contract. If it does not match,
   publish a next-input artifact for operator freeze and new admission. For native
   observer runs, profile_plan supplies a proposal, not a bypass around lab admission.
5. Execute with the declared authority, leave the turn for quiet measurement, collect
   owned results and preserve failed cells. Check engagement/correctness before
   interpreting performance. Use fresh-process counterbalanced confirmation and
   report prefill, TTFT and decode separately. Finally test any combined stack directly
   against the original frozen baseline; do not multiply component speed ratios.
