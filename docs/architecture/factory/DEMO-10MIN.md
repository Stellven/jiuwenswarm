# Ten-minute CC-only demonstration

This is a ten-minute presentation of **recorded real-agent execution**, with live read-only evidence inspection. It is not a ten-minute new build/inference run. Attempt 2 took approximately 706 seconds across three turns; queue waits and build/inference make an uncut replay exceed ten minutes. The schedule below follows the handoff exactly. No new GPU/build work is needed. RSI profiling and the next optimization belong to the next presenter.

## Prepare the presentation terminal

From the repository root, set these shell variables and read helpers. These helpers read exported bundles only:

```sh
export A1=factory-aeaa9acc88d34a3ab1375154da98c385
export A2=factory-d4b71bcce337406b96f627d469bec092
export B1="artifacts/factory/evidence/$A1"
export B2="artifacts/factory/evidence/$A2"
export BO=artifacts/factory/evidence/operator-live-jobs-1
export BUILD=3216f10925b74aca8bfc8be140e65b7b
export LAB=cabd3a09443f493899c756ab0ce1a671
export ADMISSION=admission:78856fb9c5c49df9a0550cd1342b810dab29f02dfee36929827780fe1f276aa2
artifact() {
  .venv/bin/python - "$B2" "$1" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
item=next(a for a in json.loads((root/'artifacts.json').read_text()) if a['artifact_id']==sys.argv[2])
if item['exported_path']:
    print((root/item['exported_path']).read_text())
else:
    print('Not included; see omissions.json')
PY
}
record() {
  .venv/bin/python - "$1" "$2" <<'PY'
import json,sys
from pathlib import Path
for r in json.loads(Path(sys.argv[1]).read_text()):
    if sys.argv[2] in (r.get('obs_id'),r.get('decision_id'),r.get('eval_id'),r.get('attempt_id')):
        print(json.dumps(r,indent=2))
PY
}
```

The original recordings are `artifacts/factory/recording/demo-run1.{typescript,timing}` and `demo-run2.{typescript,timing}`. They are terminal output from `script -T`, with model/tool detail in the exported session. Use the line ranges below as recording excerpts; do not describe them as a screen capture of tool calls they do not display. Optional full replay outside the timed presentation:

```sh
scriptreplay --timing artifacts/factory/recording/demo-run2.timing --typescript artifacts/factory/recording/demo-run2.typescript --divisor 30
```

## Running order

| Presentation time | Exact commands/screens | Evidence and recording segment | Label / speaking point |
|---|---|---|---|
| 0:00–1:00 — task and six CC roles | `cat "$B2/records/tasks.json"`; `cat "$B2/capsule-releases.json"`; show `cc.yaml` for engine_component, integration_skill, engine_inspector, builder, lab_client and evidence under `$B2/capsules/` | Task `$A2`; `demo-run2.typescript` lines 23–27 (01:24:26–27 UTC, facade and stream start). | **Live read-only inspection of recorded execution.** Component and integration_skill supply passive material; inspector checks actual flags/config; Builder submits durable work; lab_client goes through Manager; evidence shares task-scoped records. Material reads grant no execution authority. |
| 1:00–2:00 — baseline and component | `cat "$B2/contracts/qwen36-greedy-v1.json"`; `cat "$B2/capsules/engine_component/component.yaml"`; `cat "$B1/source/351b2550a941444f94f545444d848d03.diff"` | Integration `690e4713a55bae8dd6b40de3ccbdc8d7ea7e05f8`; baseline `campaign/llamacpp:jetson-up1108-om11`, image `sha256:2dcf9fe7e9ae051caf6607ee67db3dc5442f680480a62356ebbec8582cac2754`; run1 recording lines 45–53 terminal summary. | **Recorded integration, live evidence inspection.** Patch 09 adds xfill thread names. Baseline hash belongs to identical greedy continuation of one fixed prompt, not accuracy. Pre-freeze `-lv 4` and candidate-only xfill amendment is explicit. |
| 2:00–4:30 — skill-guided integration and repair | `cat "$B2/capsules/integration_skill/REPAIR.md"`; `record "$B1/records/observations.json" ea7c11f954974b1cb63ff5170e593266`; `record "$B2/records/observations.json" abcedeb4176b4740acb2daf2bf094dd5`; `record "$B2/records/decisions.json" "$A2:decision:2"`; `record "$B2/records/observations.json" 04d617543cbb45c28a74e3ddbcd32b0a` | Failure `CONFIG_REJECTED: expert_config: invalid LLAMA_EXPERT_PREGATE_K=48 (range 1..32)`; corrected K=8; artifact `e25248518f9549c69640be5e84e7af23`. Run2 lines 28–34 (01:24:33–01:26:47; first turn); use `$B2/session.jsonl` for actual CC material/tool events. | **Recorded real agent.** Attempt 1 ended inconclusive after three opaque inspector errors; operator repaired the tool. Attempt 2 retained this evidence via explicit read_tasks grant, then repaired one runtime field after a real binary rejection. Do not imply the operator fix was autonomous. |
| 4:30–6:30 — Builder evidence | `cat "$B2/builds/$BUILD/build-record.json"`; `artifact "$BUILD:prep"`; `record "$B2/records/observations.json" "$BUILD:build-result"`; `cat "$B2/image-identity.json"`; `cat "$BO/operator-live-jobs-receipt.jsonl"` | Build `$BUILD`, `:receipt`, `:build-record`, `:prep`, `:build-result`; 124 s, cache_hit true. Run2 lines 34–35 show first-turn finish/wait/next turn (01:26:47–01:30:26). Operator receipt is separate from the agent. | **Recorded actual build**, not fixture output. Show pinned dependencies, arm64/jetson-orin identity and durable attempt history. Docker access denied in F08, so current identity display is from historical build record. Operator cancellation cleanup is limited to the recorded `cleanup_state`. |
| 6:30–8:45 — Manager and lab | `record "$B2/records/decisions.json" "$A2:decision:5"`; `artifact "$ADMISSION"`; `artifact "$LAB:cmd.txt"`; `artifact "$LAB:result.json"`; `artifact "$LAB:threads.summary.json"`; `record "$B2/records/evaluations.json" "$LAB:evaluation"` | Admission `$ADMISSION`; lab `$LAB`; `:stdout.txt`, `:stderr.txt`, `:worker.json`; run2 lines 35–54 (01:30:26–01:36:03; turns 2–3) and line 62 evaluation. | **Recorded real inference, same-host local image admission.** One admission input rejection repaired. execution_outcome ok, correctness pass, evidence complete; all six engagement checks true, including xfill threads. stdout hash `7a154179236463bc4c0628b2b24765bdebb6b51810885773b22359d7f2b608a8` equals frozen reference and historical J-OM11. 745 ms/token is n=1, not a benchmark. |
| 8:45–9:30 — connected artifact chain | `cat "$B2/INDEX.md"`; `.venv/bin/python -m jiuwenswarm.factory.export --verify "$B2"`; `cat "$B2/omissions.json"`; `sed -n '55,63p' artifacts/factory/recording/demo-run2.typescript` | Component → commit → build → image → admission → lab → evaluation in INDEX. Terminal `accept`, decision `$A2:decision:6`, run2 lines 55–63. | **Live verification of recorded bytes.** Manifest and secrets scan cover included files. The >50 MiB image archive is listed, not bundled; original-to-sanitized hash mapping is explicit. Capsule release hashes describe the export-time checkout. |
| 9:30–10:00 — handoff to RSI | Show `artifacts/factory/COMPLETION-REPORT.md` and the three evidence bundle INDEX files. No command submits work. | `$B1`, `$B2`, `$BO`; source diff, configuration, image ID, failure history and evaluation remain reviewable. No new recording segment; closing handoff slide/terminal view. | **Presenter handoff.** RSI profiling, a second optimization and performance-improvement claims are excluded. Both readiness flags remain reviewer-owned PENDING-REVIEW. |

## Fixture boundary and rehearsal status

`tests/factory/fixtures/lab/` and fake job tools support offline tests. They are **fixtures**, never substituted for the accepted run's artifacts in this presentation. Unit-test fault injection covers cases not shown live; the completion report lists them individually.

The table allocates exactly 10:00 and supplies commands/excerpts for rehearsal. F08 has not performed a timed presenter rehearsal or created a new ten-minute recording; the two existing recordings are longer historical executions. The presenter should pre-open large JSON files and select the named fields to keep within each allocation. Do not claim a completed ten-minute rehearsal until one is recorded and reviewed.
