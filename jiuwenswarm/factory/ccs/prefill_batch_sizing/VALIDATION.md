# Validation of engine.size_prefill_batch

Stages, weakest first: `native CC execution` (the plan document and the arithmetic), `runtime acceptance`
(what a real capped server load printed and what it generated).

| check | stage | fails when |
|---|---|---|
| plan_format | native | the plan is not a factory.prefill-batch-plan/1 document |
| one_micro_batch | native | a planned prompt is longer than the ubatch |
| batch_covers_ubatch | native | `-b` is smaller than `-ub` |
| batch_applied | runtime | the server log's `n_batch`/`n_ubatch` differ from the plan |
| device_budget | runtime | measured CUDA0 + host compute buffers exceed the budget, or the log has no compute buffer line |
| estimate_safe | runtime | measured buffers exceed the plan's estimate by more than 2% |
| output_agreement:<request> | runtime | no baseline row, or outputs differ within the first `min_agree_chars` characters |

`verify` is done only at runtime acceptance with no failure. `plan` is done when its estimate fits the budget.

Planted faults (tests/test_prefill_batch_capabilities.py, real Spark logs and rows): server ran the default
batch; budget below the measured buffers; a prompt longer than the micro-batch; outputs diverging before the
required prefix; a log without the compute buffer line; a missing baseline row; a malformed plan. All fail.

Not seen by the verifier: speed (the lab measures it), output quality beyond the common prefix, and host
memory (the lab samples the cgroup peak).
