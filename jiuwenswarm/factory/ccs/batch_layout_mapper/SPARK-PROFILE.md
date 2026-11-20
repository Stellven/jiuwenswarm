# Spark activation profile

These settings are a source-derived Spark validation profile. Hold the stock, candidate gate-unset and candidate gate-enabled flags matched for each comparison, and retain the effective settings, logs, output parity and counters. Run under the approved capped wrapper. The strict stock reference keeps its documented four-slot configuration.

| Capsule | Matched stock control and candidate flags | Gate-on evidence |
| --- | --- | --- |
| Mapper | Strict A fallback. For active probe use A with `-np 1 -c 4096 --ctx-checkpoints 0 -b 2047 -ub 512` in all three arms. Use the exact uncached 2048-token prompt to cross the logical cut. Confirm effective widths and retained emission under this profile. | `LLAMA_BATCH_LAYOUT=1`. Require `active n_batch=2047 n_ubatch=512 limit=1536`, contiguous planned spans, a changed cut and positive decisions/rows. For the ordinary splitter, stock spans of 2047/1 predict five physical microbatches and aligned spans of 1536/512 predict four. Check actual spans before attributing an effect. Confirm no rolling checkpoint path is exercised in the active probe. Run the capsule's small boundary sweep separately. |
