# Weight placement planner helpers

Run these from the capsule directory with the factory Python
(`python` from its virtualenv). Each script offers `--help`.

- Inspect an existing log and require active, exit stats, and effective mmap.

  ```sh
  python helpers/check_markers.py run.server.log \
    --name weight_placement_planner --expect-active --load-mode mmap
  ```

  The JSON reports counts by marker and every effective loader mode in order,
  with the last mode selected for the optional check. Inspect earlier lines
  for retries and reconcile assignment details separately.

- Check the plan file's size, version, row count, field names and types.

  ```sh
  python helpers/validate_plan.py plan.json
  ```

  Resolve regexes, overlapping matches, backend names, and model identity
  against the pinned engine, and evaluate capacity against the admission
  ledger.

- In an authorized real shell, compare one-shot server completion tokens
  using the same model and common flags. The wrapper uses port 5175 and the
  supplied `$FACTORY_ONE_SHOT`, which starts and stops its own server.
  Set the absolute file and binary paths and use a fresh output directory.

  ```sh
  python helpers/parity.py \
    --stock-bin "$STOCK_BIN" --candidate-bin "$CANDIDATE_BIN" --model "$MODEL" \
    --output gate-off --name weight_placement_planner --gate LLAMA_PLACEMENT_PLAN \
    --clear-env LLAMA_ARG_PLACEMENT_PLAN --load-mode mmap \
    --common-arg=-ngl --common-arg=0 --common-arg=-fit --common-arg=off \
    --common-arg=-lm --common-arg=mmap
  ```

  For the active control use a new output directory and add `--active
  --candidate-arg=--placement-plan --candidate-arg="$PLAN"
  --stock-arg=-ot --stock-arg="$STOCK_OVERRIDES"`. Clear or pin any
  inherited configuration variables affecting placement. Supply only the
  treatment and its stock equivalent as side-specific arguments. The helper
  requires the active and stats markers and equal effective load modes.
  Keep both logs and response files for assignment reconciliation and perform
  the separate byte-for-byte greedy stdout checks specified in METHOD.md.

For a gate-unset arm, use `check_markers.py LOG --name weight_placement_planner
--expect-silent`. It exits nonzero for any line carrying the prefix, including
unrecognized marker kinds.
