# Validation of eval.paired_accuracy

Stages, weakest first: `native CC execution` (the run is internally consistent and was analysed by the
plan), `runtime acceptance` (it came from real loads, the arms answered in the scored format, and it passes).

| check | stage | fails when |
|---|---|---|
| state_format | native | the state is not a muse-paired-accuracy/1 document |
| order_fixed | native | the state's order digest is not the seeded order of the dataset |
| planned_checkpoints | native | looks or the critical value differ from the planned 50/100/160/250/430 and z 2.65 |
| margin_pinned | native | the run used a different margin than the contract's |
| rows_prefix:<arm> | native | an arm's rows are not exactly the first n questions of the order (a gap, a reorder, a hand-picked set) |
| answer_keys:<arm> | native | a row's answer differs from the dataset key, or `correct` is not `pick == answer` |
| canonical_prompts:<arm> | native | a row was scored on a prompt other than the canonical one (so the arms are not paired) |
| paired | native | fewer than 50 questions answered by both arms |
| recomputed_checkpoints | native | the checkpoints recomputed from the rows differ from the ones the run reported (peeking at an unplanned count, a later stop than the first decision) |
| decision_claimed | native | the state's decision is not the one the rows give |
| letter_mass:<arm> | runtime | inconclusive when the mean probability on A-D is under `min_letter_mass` (default 0.5) |
| server_loads | runtime | an arm has no recorded server load |
| distinct_models | runtime | (with `server_logs`) the two loads read the same model file |
| non_inferiority | runtime | the decision is `fail`; inconclusive when it is `continue` or `report` |

`verify` is done only when every check passes at runtime acceptance, i.e. a `pass` against the pinned margin.

Planted faults (tests/test_paired_accuracy.py, on a synthetic dataset): a checkpoint at an unplanned count,
z = 1.96, a gap in one arm's rows, a prompt that differs between arms, a flipped answer key, a run that kept
going after a decision, a low letter mass, and a candidate that truly loses 15 points. Each fails (or is
inconclusive) for the stated reason; a clean run passes.

## What verify cannot see

- Whether the model's weights are the ones the contract names beyond the file path (pin the pack digests in the
  node's inputs).
- Contamination: MMLU is public and may be in the training data. The comparison is paired, so contamination
  shifts both arms; it does not make the absolute accuracy meaningful.
- Server-side batching effects on numerics are not modelled; both arms run with the same slots and batch.
