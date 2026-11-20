# Spark activation profile

These settings are a source-derived Spark validation profile. Hold the stock, candidate gate-unset and candidate gate-enabled flags matched for each comparison, and retain the effective settings, logs, output parity and counters. Run under the approved capped wrapper. The strict stock reference keeps its documented four-slot configuration.

| Capsule | Matched stock control and candidate flags | Gate-on evidence |
| --- | --- | --- |
| Predictor | Strict A fallback. For active probe use A with `-np 1 -c 4096` in all three arms, native MoE cache disabled. Admission requires causal text prefill and actual mapped expert selected-copy callbacks. | `LLAMA_EXPERT_PREDICT=1`. One active and one stats marker, forecast activity, hits and misses, waste, lead samples and lead time with greedy parity. Test 2048 tokens first. The literal `bytes_useful_at_consumption=0` does not establish avoided physical I/O. Run separate inactive tests for default slots and native cache. |
