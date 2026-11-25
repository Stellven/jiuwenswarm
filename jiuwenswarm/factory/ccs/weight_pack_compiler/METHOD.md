# Method: requantize a pack with stock llama-quantize

The node owes two evidence outputs: a **recipe** (checked by `verify_recipe`) and the **pack** (checked by
`verify_pack`). The worker decides the recipe; `plan_recipe` only drafts one from the census. Run the steps in
order and keep every command, log and JSON result with the task. Pass absolute paths to every capability.

## 1. Census

Read the source headers, never the data:

```sh
python helpers/recipe.py /packs/nvfp4/muse-00001-of-00009.gguf --target q2_k --out /work/draft.json
```

Confirm from the draft's `role_census`: routed experts (`blk.N.ffn_{gate,up,down}_exps.weight`) are NVFP4 in the
layers the ingest node converted (and whatever the checkpoint kept, e.g. BF16 in layers 0 and 61); every
routed expert weight has a `[n_expert]` F32 `.scale`; attention, norms, router, shared experts, embeddings and
output have the types you expect. A surprise here is a question for the ingest node, not something to fix here.

## 2. Recipe

Call `plan_recipe` with the ingest manifest (it carries the per-file sha256, so nothing is re-hashed), the
imatrix from `pin_inputs`, the output prefix on the disk you were granted, and `disk_grant_bytes`. Read what
it drafted and decide:

- every routed expert goes to the target; every other tensor is **pinned to its source type** with an anchored
  `--tensor-type` pattern. Unpinned tensors would get the Q2_K mixture (Q4_K/Q6_K bumps, Muse's Q8_0 bump for
  latent and attention-gate tensors) and change type;
- a tensor whose row length (`ne[0]`) is not a multiple of the target block (256 for Q2_K) is refused: stock
  would silently write Q4_0 (then F16). Choose another type for that tensor and say why;
- the imatrix is named with its sha256 and passed as `--imatrix`. Stock does not require one for Q2_K in a
  `Q2_K` file, the capsule does (below 3.5 bpw);
- `--keep-split` keeps the input sharding so each output shard can be checked and copied on its own.

Edit the recipe JSON if you change anything; keep `argv` and `tensors` consistent (the verifier replays the
argv against every tensor).

## 3. verify_recipe

Call `verify_recipe` with the recipe, `target` (required; the contract pins it, `q2_k` here), `pack_manifest`
(required: the source manifest or first shard) and the disk grant. The verifier takes neither the target nor the
source types from the recipe: the recipe's target must equal the requested one, its tensor table must equal the
source headers, and the routed experts must actually change from their source type to the target. Any failing
check is a gate: do not start the conversion (VALIDATION.md).

## 4. Time one layer first

```sh
"${recipe.probe.argv[@]}"          # layers 0..L only, the rest pruned; same pins, same imatrix
```

Run the probe argv from the recipe under `/usr/bin/time -v` with the same niceness as the full run. It writes a
small pack (`*-probe.gguf`). Project: `full_seconds ~= probe_seconds * total_routed_layers /
converted_routed_layers`. If the projection does not fit the node's time limit, stop and report it with
the probe numbers; do not start a run that cannot finish. Delete the probe pack before the full run. A
`--dry-run` with the full argv is a cheap extra check: it prints every tensor's chosen type and the final size
without writing.

## 5. Full requantization

```sh
nice -n 10 ionice -c3 "${recipe.argv[@]}" 2>&1 | tee /work/quantize.log
```

Watch free space on the output disk against the grant while it runs; stop the process if the grant would be
exceeded. Keep the log: it lists every tensor's source and target type, any `applying manual override` line and
any `falling back to` warning (there must be none). Never load the result while it is being written.

## 6. verify_pack

Call `verify_pack` with the first output shard, `source_pack`, `target` and `expect_bytes_range` (all three
required; the contract pins the target and the range, 250-320 GB for the Muse Q2 pack) and the recipe. Every
tensor type is judged against the source pack headers; the recipe is used only for its target (it must agree),
the shard layout, the size estimate and the imatrix record. Then `publish_manifest` (hash on) writes the manifest with per-file sha256;
hashing ~300 GB takes a while, so do it once, after `verify_pack` passes.

## 7. Coherence smoke

Load the Q2 pack with the wired base engine E0 (stock plus the expert scale wiring, the `wire_expert_scales`
node's build; the stock 9048bad8 graph passes `nullptr` for the per-expert `.scale` tensors, SOURCE-MAP.md, so
it cannot judge a pack that carries them) under the memory cap (never uncapped on the shared Spark) and run the
eight held-out prompts greedily. Report coherent text and the top-1 token agreement with the NVFP4 pack on the
same E0 build as measured numbers, not as a claim. If the NVFP4 pack is incoherent on E0 too, report that rather
than blaming the requantization.
