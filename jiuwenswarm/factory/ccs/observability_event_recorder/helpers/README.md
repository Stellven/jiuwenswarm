# Recorder evidence helpers

Run these tools with `~/predemo/venv-factory/bin/python` from the capsule directory, or use absolute script paths. Each tool has `--help` and returns a nonzero status when a requested check fails.

## Marker and load mode check

```sh
python helpers/check_markers.py on.server.log --expect active --load-mode mmap
python helpers/check_markers.py off.server.log --expect off
python helpers/check_markers.py bad.server.log --expect inactive
```

The checker prints matching INFO lines, their occurrence counts and every reported effective load mode. Omit `--load-mode` if the contract does not require one. Run the capture with `-lv 4`. Coverage and parity are separate checks.

## Same-configuration parity

```sh
python helpers/parity.py plan /path/to/stock/bin /path/to/candidate/bin \
  /path/to/model.gguf /path/to/existing/empty-captures /path/to/fresh-trace.jsonl \
  -- -ngl 0 -lm mmap
python helpers/parity.py check /path/to/existing/empty-captures
```

`plan` prints commands for `~/predemo/one_shot.sh` on port 5175, including a single fixed engine configuration, explicit gate state and verbosity. Review the commands and run them sequentially only in an authorized real shell. The one-shot runner starts a server, opens a loopback port and requests server shutdown. Use the contract's runner if it requires a different request or launch setup. Check the runner exit, each log and the completed trace independently. `check` compares the captured token ID arrays and the UTF-8 bytes of the decoded content field. For a contract that specifies a separate raw stdout artifact, compare those exact bytes too.

## JSONL coverage and loss

```sh
python helpers/check_jsonl.py trace.jsonl dispatch.json
python helpers/check_jsonl.py overflow.jsonl overflow-dispatch.json --expect-loss
```

Build the manifest independently of the recorder from actual successful eligible dispatches. The file is a JSON array such as `[[0,3],[0,7],[1,3],[1,7]]`, with one pair per expected microbatch and layer. The helper expects JSONL rows with `type: event`, integer `microbatch` and `layer` fields, and one final `type: summary` row with integer `expected`, `written` and `lost` counters. It rejects duplicate or unexpected keys and checks that the missing key count equals reported loss. The default requires no loss. The overflow mode requires positive, accounted loss. Check request and phase joins, expert IDs, ordering, timing, byte attribution and the cause of loss against independent evidence.

For a gate-unset arm, use `check_markers.py LOG --name runtime_event_recorder
--expect-silent`. It exits nonzero for any line carrying the prefix, including
unrecognized marker kinds.
