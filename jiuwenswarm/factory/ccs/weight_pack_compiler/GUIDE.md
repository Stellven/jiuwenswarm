# Pack compiler: guide for the worker

A pack compiler turns one GGUF weight pack into another at a chosen precision with the **stock**
`llama-quantize`. This capsule is the method for doing that well: how to decide the precision of each tensor
(the recipe), how to drive the stock tool, and how the result is checked. It ships no finished recipe; the
worker reads the census and decides.

## Parts

- **Precision allocator (recipe)** - which type each tensor gets. For the Muse Q2 node: routed experts to
  Q2_K, everything else kept. `helpers/recipe.py` drafts it from the census; you own it.
- **Tensor converter** - one stock `llama-quantize` invocation built from the recipe's argv. No engine change.
- **Pack writer and publisher** - the tool writes the shards; `verify_pack` checks them; `publish_manifest`
  writes the manifest with sha256 for the next node.

## Rules of thumb

1. Pin everything you do not mean to change. The ftype's mixture (and Muse's own bumps) otherwise decides.
2. Anchor every pattern (`^...$`): stock matches with `regex_search`, so `attn_q` also hits `attn_q_a`.
   Stock lower-cases the pattern, so avoid `\D`, `\W`, `\S`; spell layers out (`(1|2|3)`).
3. Requantizing is lossy twice. Use the imatrix even when stock does not insist.
4. Measure before you commit hours: run the probe (one layer), project, then decide.
5. Carry, do not recompute: the `[n_expert]` `.scale` and `.input_scale` tensors are 1D and stock copies
   them; the verifier compares their bytes with the source.
6. Every number in a report (time, bytes, agreement) is a measurement with its command and log.

## Samples

- `samples/recipe_entry.json` - one tensor entry and one pin, labelled.
- `samples/quantize_run.sh` - probe, projection, full run under nice/ionice with a disk watch.

See METHOD.md for the steps, VALIDATION.md for the gates and SOURCE-MAP.md for the stock anchors.
