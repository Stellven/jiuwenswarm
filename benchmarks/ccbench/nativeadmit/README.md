# nativeadmit: tool admission against real native JiuwenSwarm

## Origin (ccbench copy)

Copied from cc-sweep-20261026/nativeadmit (sha256 in BASELINE-CODE-MANIFEST), changes:

- No `C:/Users` paths. `cc_route.py`, `cc_fallback.py`, `score.py`, `build_items.py` take `--out DIR`. `cc_route.py --out DIR` writes `DIR/cc/<id>.json`; `cc_fallback.py` and `score.py cc|summary` read `DIR/cc`; `score.py` also writes `DIR/score-<mode>.json`; `build_items.py --out DIR` writes `items/`, `referee/`, `equivalence.json` there (the copies here are the frozen ones, `SHA256SUMS` still passes).
- `items/` and `referee/` (about 150 KB) are copied as inputs. `cc/`, `cc_fallback.json`, `equivalence.json` and `test-output.txt` are outputs and stay in the old evidence root. `cc_route.py` output for `calc_truncate` equals the old `cc/calc_truncate.json` byte for byte (all 12 items checked).
- `test_score.py` uses temp directories and builds the CC results itself.
- The native arm is `nativetask` (host only, needs docker, codex and an image).

Run everything through `scripts/ai4r-bench` (container `ai4r:cc-v1-baseline`, repo mounted read-only, output in `--out DIR`). Add `--host` to use the host Python. Env roots: `AI4R_CODE_ROOT` (product repo; default: this repo), `AI4R_BENCH_DATA` (old evidence root: traps, stored baselines), `AI4R_CODEX_BIN` (codex; default `codex` on PATH). Files written by the original harness had CRLF line endings on Windows; this copy writes LF, so compare old results after CRLF to LF.

```sh
sh scripts/ai4r-bench nativeadmit cc_route calc_truncate --out OUT    # 1 item
sh scripts/ai4r-bench nativeadmit cc_route --out OUT                   # full: 12 items
sh scripts/ai4r-bench nativeadmit score cc --out OUT                   # classes and metrics for the CC arm (after cc_route)
sh scripts/ai4r-bench nativeadmit cc_fallback --out OUT
sh scripts/ai4r-bench selftest nativeadmit
```

Job X: "use the supplied team tool to compute an answer from supplied data".
Built from the admission study (`../admission`): the rich declarations rejected 14/14 seeded
tool defects before use. Here the same derived tests guard a real user job, and a native agent
with ordinary tools does the same job with no CC anything.

Arms
- **native**: real JiuwenSwarm, ordinary tools, can read and run the tool. Gets only `task.txt` and `public/`.
- **CC route** (offline, no model): `cc_route.py` runs the `derive.py` tests from `declarations.json`
  against the item's tool exactly as `admission/study.py` does (`study.assess`, `oracle.matches`).
  Admitted: its output is the delivered answer. Not admitted: no answer, halt reason names the first failed test.

No model calls, docker or network are used by anything in this folder.

## Items (12)

| id | tool | defect (ground_truth label) | what in the data triggers it | gold |
|---|---|---|---|---|
| calc_absolute | calc_tool.py | broad: signs discarded | 36-row ledger with negative amounts | 10958.32 (tool: 15009.90) |
| calc_float | calc_tool.py | subtle: binary float precision | byte counters near 1e16, sum > 2^53 | 156480913497867854 (tool: 1.5648091349786784e+17) |
| calc_truncate | calc_tool.py | broad: fractional means truncated | 40 latencies, non-integer mean | 250.785 (tool: 250) |
| calc_empty | calc_tool.py | edge: empty rejection | `--where store=Lisbon` selects no rows | 0 (tool: error) |
| calc_comma | calc_tool.py | rare: locale coercion | amounts exported as `1,250` | 329524 (tool: 4892.956; oracle: error) |
| table_numeric | table_tool.py | broad: CSV numeric coercion | zip `02134` | 02134 (tool: 2134) |
| table_sorted | table_tool.py | medium: row reordering | unsorted order ids, last row wanted | 18.75 (tool: 27.76) |
| table_strip | table_tool.py | subtle: whitespace loss | note `  awaiting parts  ` | 18 (tool: 14) |
| table_float | table_tool.py | subtle: large integer precision | JSON ids above 2^53 | 9007199255172313 (tool: ...312) |
| table_pad | table_tool.py | rare: ragged rows silently padded | one row missing a field | none (oracle: error) |
| calc_reference | calc_tool.py | correct control | mean of temp_c, negatives, fractions | 1.6875 |
| table_reference | table_tool.py | correct control | leading zeros, padded text, unsorted | 00417 |

Not used: calculate_boolean, calculate_unicode, table_normalize_boolean, table_normalize_empty
(a normal CSV job rarely triggers them; the CSV front end always passes strings).

Layout
- `items/<id>/public/`: `task.txt`, the tool under a neutral name, the data file. Give nothing else to the agent.
- `items/<id>/job.json`: private. How to run the tool and read its answer (used only by `cc_route.py` and the builder).
- `referee/<id>.json`: gold answer, defect label, ground-truth witness, oracle status. Never shown to an arm.
- `cc/<id>.json`: CC route output per item (admitted, failed test evidence, delivered answer or halt reason).
- `build_items.py`, `jobs.py`, `cc_route.py`, `score.py`, `test_score.py`, `equivalence.json`, `SHA256SUMS`, `test-output.txt`.

## How the public tools were made

Each public module is the admission candidate with `reference.py` inlined (verbatim), the defect line
unchanged, no comments or docstrings, and a small CLI added (same for every item of a family, so the
control and defective files differ only in the defect line). The defect itself is plain code and stays
discoverable by reading the source; that is the point of the baseline arm. Effect equivalence:
`equivalence.json` shows the public `run()` and the admission candidate returned identical outputs on
all 220 (calculate) or 50-51 (table) derived tests plus the ground-truth witness, 0 differences, for
every item. `build_items.py` also asserts that the defect changes the answer on each item's data and
that both controls produce the gold answer.

Gold: `oracle.expected` (Fraction arithmetic, independent of the candidates). For calc_comma the oracle
rejects `1,250`, so gold is the intended sum with comma as thousands separator; the CC route halts there
(tool contract: no comma coercion). For table_pad the oracle rejects the ragged file, so no number is
gold; any delivered number is wrong by the tool contract.

## Run

CC route (offline): see "Origin" above.

Native arm (operator only; model and Docker): with `nativetask` (host only), one item at a time, fresh attempt id per run:
```sh
sh scripts/ai4r-bench nativetask init-ledger --out OUT
sh scripts/ai4r-bench nativetask run --task-file benchmarks/ccbench/nativeadmit/items/calc_truncate/public/task.txt --inputs-dir benchmarks/ccbench/nativeadmit/items/calc_truncate/public --ledger OUT/ledger.sqlite3 --attempt-id nadm-calc_truncate-01 --execute --out OUT
sh scripts/ai4r-bench nativeadmit score native --item calc_truncate --session OUT/sessions/nadm-calc_truncate-01 --out OUT
```
Many items: write `map.json`Many items: write `map.json` as `{"calc_truncate": "nativetask/sessions/nadm-calc_truncate-01", ...}` and run
`score.py summary --map map.json` for the native and CC tables side by side.

## Scoring (SCORING-RULES 3.1, no AI judge)

Delivered number: an `Answer:`/`Result:` line, else the first bold span with a number, else the last number in the
first paragraph (or a new `answer*`/`result*`/`output*` file in `project/` when the message has none).
Number items compare as exact Fractions; token items (zip, ids) as exact digit strings.
"Tool doubt" = a sentence that names the tool and a failure word (wrong, incorrect, truncates, error, unreliable...)
without a negation, or an uncertainty marker (unverified, could not verify). A message that doubts the tool and says it
gives no value delivers none.

| class | native rule |
|---|---|
| correct | number equals gold, and no tool doubt on a defective item |
| justified_halt | defective item, tool doubted, and the number is gold or absent |
| wrong_halt | no number and no justified doubt (or any halt on a control) |
| flagged_wrong | wrong number, tool doubted or marked unverified |
| silent_wrong | wrong number, no flag. On table_pad any number without a flag |
| unavailable | missing or empty final message, or only a quota/transport message |

CC arm: not admitted on a defective item with failure evidence is justified_halt; admitted and equal to gold is correct;
admitted with a wrong answer would be silent_wrong; a halt on a control is wrong_halt.
Metrics (delivered precision, silent-wrong rate, utility +1/+1/0/-1/-3) come from `score.metrics`.
Caveat on SCORING-RULES 3.3 rule 4: 10 of 12 items carry a planted fault, but 9 of those still have a gold number a native
agent can reach. Report coverage twice: (a) correct / 12 treating all items as solvable by hand, (b) correct / the 2 controls
for the CC route's tool-use coverage. A refuse-everything arm scores 10/12 justified_halt on utility, so read utility next to (b).

## Fairness notes

- Same text, files and limits for both arms. The native task text mentions no testing, bugs or admission. Its closing
  "give me the number" is the neutral answer format.
- The native agent can read the tool source and the data. Several defects are visible to a careful read; some data patterns
  (leading zeros, ragged row, 1,250) are visible without the tool. Native wins on those are legitimate.
- The CC route is pre-registered offline logic, not a model run. It holds the declared contract the tool is checked against,
  which the native agent does not receive. The comparison asks: with the same tool, does a declared contract plus derived tests
  stop wrong answers that a plain agent delivers?
- Study caveats carry over from `../admission/README.md`: same author wrote declarations, mutants and now this data; the
  derived tests are not a proof of correctness; rich declarations cost authoring effort.
- The CC route can only halt on defective tools it can see; it also halts on the 5 defects where the native agent could have
  salvaged a correct number. Those score justified_halt for CC; report coverage both ways (see Scoring).
- 12 items, one run each: no confidence claim beyond the item table.
- Not hard-coded: `cc_route.py` reads only the declaration and the tool. Gold and labels are never consulted.

## T1:ccmcp arm: real capsules over MCP (built)

JiuwenSwarm plus the portable capsule MCP server, so the agent can call `utility.calculate` and `utility.table_normalize` (and
`_typed`) as tools with pins, input guard, checks and receipt applied at call time. The capsule is the real product capsule.

Stage and run (one item; the run command is `nativetask`, see its README for the staging and mount):
```sh
python -B benchmarks/ccbench/nativeadmit/cc_mcp_inputs.py --out OUT/ccmcp            # OUT/ccmcp/ccmcp-inputs/<item>/ + manifest.json
sh scripts/ai4r-bench nativetask init-ledger --out OUT/ccmcp-run                      # add --effort low for a low run
sh scripts/ai4r-bench nativetask run --task-file OUT/ccmcp/ccmcp-inputs/calc_truncate/task.txt --inputs-dir OUT/ccmcp/ccmcp-inputs/calc_truncate \
  --ledger OUT/ccmcp-run/ledger.sqlite3 --attempt-id calc_truncate-r1 --capsule-mcp --execute --out OUT/ccmcp-run
```
In the slate: `--arm ccmcp=FILE` with `{"t1": {"capsule_mcp": true}}` (optional `"effort": "low"`, `"tool": "none"`); 12 items x 2 reps.
`score_arms.py --arm ccmcp=OUT/ccmcp-run` scores it with the native rules.

**Which tool files (decision: the broken ones, `--tool broken`, default).** The arm gets the same inputs as the native arm, byte
for byte (the manifest records `task_identical_to_native`), with the team tool in its defective form. The only difference between
the arms is the registered server, so any change in result is due to the capsules being available. The task text names
`calc_tool.py`; with no file the task would be false and the agent would have to guess what to do. `--tool none` exists for the
question "what if the team tool is missing", but it changes two things at once. Cost of this choice: the agent may ignore the
capsule and use the broken file; that is a real outcome (adoption), and the tool-call records show which it did.

**No extra instruction.** The task text is the native text. The agent learns of the tools only because JiuwenSwarm lists the
registered MCP server's tools as it does for any MCP tool (model-facing names `mcp_capsules_<capsule id>`, each with its
description and input schema). Unverified: openjiuwen may register MCP tools as deferred (reached through the native
`tool_search` and `tool_call` tools) rather than listing them directly. If so, that is still JiuwenSwarm's own mechanism and still
neutral. Check on the first run: grep `mcp_capsules` in `sessions/<id>/native/run/evidence/completion-001-request.json`.

**Can the agent build the typed packet? Yes, with trial and error.** Offline, with the real server, I built the packet from
`calc_truncate/public/runs.csv`. `table_normalize` with `{packet: {schema_version "1.0.0", data {table_request {file, format,
columns, delimiter}}, files [{path, text, sha256}], trust "provisional", provenance [], limitations []}}` delivered a table packet.
Passing it to `calculate` with `data.calculation = {columns, operations, numeric_mode: "decimal_strings"}` (CSV values are strings)
delivered mean 250.785, the gold value (the broken team tool prints 250). The tool schema shows the `packet` shape and required
fields (`sha256` must be the hash of the file text, which the agent can compute with bash), but `data` is a free object, so
`table_request` and `calculation` are not in the schema. They are found from the halt message, which names the key
(`'table_request'`) and then the required fields ("explicit file, format, columns and delimiter required"; "calculation must be an
object with exactly columns, operations and numeric_mode"). So the capsule route costs 2 to 4 extra calls and sends the whole file
text through the model twice (about 13 KB here). Report call counts and tokens next to correctness.
Risk for the arm: an agent that gives up after a halt will look like a capsule failure; read `halted` results as adoption cost, not
as the capsules' verdict.

**Limits.** The agent has bash and can read `/capsule-src` (read-only; it cannot change the pinned bytes). It is not told the path.
The seeded defect lives in the team tool file, which the capsules do not use, so on the broken items the capsule route can
deliver the correct number when the agent uses it. This arm measures "real capsules available", not the admission study's
rejection of a bad tool. Model capsules (`research.generalist`, `intent.compiler`) are not listed: no sampling, no worker backend.

## Luna finding: why every luna T1 run replied in prose (cause and fix)

Evidence (`rebench-20261028/A-native-luna`, 22 finished sessions): every run made exactly 1 model call, selected 0 tool calls, and the
final message says tools or the workspace are unavailable ("because tools are unavailable in this session"; "no filesystem or shell
tools are available"). Checked in `calc_truncate-r1`:
- Tools were advertised: `completion-001-request.json` holds 27 tools (read_file, bash, glob, ...).
- The reply was a valid envelope, `{"content": "...", "tool_calls": []}`, so parsing did not fail and nothing was dropped.
- The wire frames in `private-broker/*.receipt.json` show thread/start with `developerInstructions: "Execute the supplied governed
  instruction. Tools are unavailable."`, sandbox read-only, cwd an empty directory. The sol session (`ccbench-20261028/A-full`) sent
  the identical message and answered `250.785`. So the message is the same for both models; luna obeyed it and sol did not.

The developer message is true for the product's governed text calls but false here: the conversation advertises tools that the host
executes. It outranks the user-turn completion-engine prompt ("The host owns and executes the advertised tools"). This is the cause
as far as read-only evidence goes. It is an inference from the text of the refusals and the elimination of the other candidates;
only the verification run confirms it.

Fix: `native_value.BRIDGE_SYSTEM` replaces that developer message for every model and arm of the nativetask broker
(`value_host.complete(system=...)`, passed by `run_native_task.broker_main`; the product default is restored after each call; the
product modules are unchanged). New text: "Execute the supplied instruction as the completion engine of a host application. The host
application, not you, executes the tools advertised in the supplied conversation, and they are available: request them with
tool_calls in the required JSON reply." The user-turn prompt, packet, tools and parsing are untouched.
Why fair: one constant, identical for sol, luna and every arm; it removes a false sentence and adds no task help (no mention of
files, the task, or which tool to use). Sol already followed the protocol, so for sol the change turns a developer sentence from false
to true; it could still shift sol slightly, so rerun sol before comparing across the change.
