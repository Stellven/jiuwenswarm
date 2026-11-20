# Expert demand predictor builder helpers

Run these commands from the capsule directory. Each helper accepts `--help`. The tests use synthetic inputs.

## Read activation and load mode

```sh
~/predemo/venv-factory/bin/python helpers/check_markers.py /absolute/path/on.server.log --require-active --require-mmap
```

Capture the log at `-lv 4` through orderly server exit. The helper counts active, inactive and stats lines and lists distinct effective load modes. The flags require one active line and the sole effective mode `mmap`. Inspect settings, fallback reasons and stats values in the original log. Omit the flags when checking gate-off and ineligible runs.

## Prepare and compare matched one-shot runs

```sh
~/predemo/venv-factory/bin/python helpers/parity_template.py plan /absolute/stock/bin /absolute/candidate/bin /absolute/model.gguf /absolute/results -- -ngl 0
~/predemo/venv-factory/bin/python helpers/parity_template.py compare /absolute/results
```

`plan` prints three commands wrapping `~/predemo/one_shot.sh` on port 5175. In an authorized real shell, create a fresh output directory and run those commands sequentially, then run `compare`. The harness starts and stops its server. The commands share one set of flags, `-lm mmap` and `-lv 4`. Gate treatment is unset, unset and exact `1`, respectively. Use a fresh run directory for each placement. The template uses the harness's fixed greedy request. Use the authorized contract runner for a different frozen workload and retain its byte comparison of the required output. `compare` checks decoded content as UTF-8 bytes and exact integer token IDs. Check activation separately.

## Replay a small synthetic trace

```sh
~/predemo/venv-factory/bin/python helpers/replay_score.py helpers/synthetic_trace.jsonl --layers 2 --bytes-per-expert 4096
```

Supply one JSON object per line with a string `request`, zero-based integer `microbatch` and `layer`, and a nonempty list of nonnegative integer `experts`. Order complete requests chronologically with contiguous microbatches and all layers. The scorer freezes the rule, builds forecasts before visiting their targets and uses at most two completed microbatches of history from the same request. Run it on the held-out requests after normalization. The uniform byte cost estimates simulated waste from false positives. Use real byte inventories and separate readiness evidence for contract claims. The bundled trace yields 4 hits, 3 misses and 28,672 simulated wasted bytes.

## Adapt the C++ samples

The four standalone examples cover exact-value gate reads, INFO formatting, frequency ranking with stable ties, and separate ID and byte accounting. Review the guide and stock calling conventions before adapting them. [Validation results](../VALIDATION.md)

For a gate-unset arm, use `check_markers.py LOG --name expert_demand_predictor
--expect-silent`. It exits nonzero for any line carrying the prefix, including
unrecognized marker kinds.
