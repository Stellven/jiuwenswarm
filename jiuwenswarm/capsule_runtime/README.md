# capsule_runtime: use capability capsules from any harness

A small runtime that loads Capability Capsules outside the AI4Research pipeline and
keeps their guarantees. It imports nothing from `runner.py`, `scheduler.py`, the run
store or executor RPC. (The capsules themselves import `packet.py`, which imports
`ProducedArtifact` from `runner.py`; that is a data class, nothing runs.)

```
python -m jiuwenswarm.capsule_runtime list
python -m jiuwenswarm.capsule_runtime describe utility.calculate
python -m jiuwenswarm.capsule_runtime admit utility.calculate
python -m jiuwenswarm.capsule_runtime invoke utility.calculate --inputs in.json --out receipt.json
python -m jiuwenswarm.capsule_runtime.mcp          # MCP server over stdio
```

```python
from jiuwenswarm.capsule_runtime import Runtime
rt = Runtime()                                    # or Runtime([extra_dir], worker_model=...)
rt.admit('utility.calculate')
result = rt.invoke('utility.calculate', {'packet': packet})
# {'status': 'delivered', 'outputs': {...}, 'receipt': {...}}
# {'status': 'halted', 'halt': {'stage', 'code', 'reason'}, 'receipt': {...}}   (never any outputs)
```

## What travels with a capsule

| Guarantee | How it holds here | Halt stage |
|---|---|---|
| **Pins** | `release.json` hashes every source file of the capsule, `packet.py` and shared dependencies. A byte that differs refuses the capsule at load, with the file named. The pins are rehashed on every call. Uses `catalog._verify_current_pins` and SHA-256 of file bytes, as `release_tool` writes them. | `pin` |
| **Admission** | `invoke` refuses a capsule not admitted in this process (`require_admission=False` waives it, explicitly). | `pin` (`not_admitted`) |
| **Input guard** | Inputs are checked against the declared ports: required and unknown ports, the port's contract schema, and `validate_packet` for packets. | `input_guard` |
| **Declared limits** | The declared wall time is enforced (a pure worker runs in a daemon thread, so the limit fires even for CPU-bound code). Declared model-call count is enforced. Output ports must match the declaration and their schemas. | `worker` |
| **Capsule checks** | The capsule's own `checks.py` runs on (inputs, outputs). Every declared acceptance check must be present and PASS. A failed verifier never returns outputs. | `verifier` |
| **Trace / packet review** | `checks/trace.py check_trace` runs if an output port named `trace` carries a manifest; `checks/packet_review.py review` runs on science review packets. No shipped capability capsule emits either, so both report `not_applicable`. | `trace` |
| **Semantic verifier** | Only for capsules whose declaration carries semantic checks or declares a model dependency (today: `research.generalist`). Same code as the product: `gate.SemanticVerifier` builds the prompt from the capsule's pinned profile instructions and criteria plus the declaration and exact output bytes only (never inputs, traces or the request, D20), `assemble_assessment` parses the reply, `checks/verifier.verifier_predicates` recomputes the mechanical predicates. Delivered only if every criterion is PASS and every predicate holds. | `semantic_verifier` |
| **Receipt** | Capsule id and version, release hash, declaration hash, input and output SHA-256, check verdicts, which verifier stages applied and why, declared effects, every model call (provider kind, model, SHA-256 of prompt, system and reply, tokens if known), timestamps, and `verifier_independent`. | |

Receipt example for a deterministic capsule:
`verifiers: {deterministic: pass, trace: not_applicable (...), packet_review: not_applicable (...), semantic: not_applicable (deterministic capsule)}`.
With a model capsule and no verifier model: `semantic: not_run (no model configured)`. This is never reported as a pass.
`require_semantic=True` (`--require-semantic`) halts instead of delivering unreviewed.

### Which verifier stages run
The declaration decides. `guarantees.checks[].kind` is `deterministic` or `semantic`; a capsule that lists a
`semantic` check, or declares `needs.injects` (a model), gets the semantic stage. The product has no per-capsule
switch beyond this (its checking profile always lists criteria), so the rule is the declaration's own. Deterministic
capsules (`calculate*`, `table_normalize*`, `markdown_report*`, `packet_report`, `summary_to_packet`) get checks.py,
trace and packet review only. `describe` and the MCP tool description list the stages.

### Models
Capsules that use a model call `await ctx.model(prompt, system=...) -> str`. The runtime supplies it from, in order:

1. Python: `invoke(..., worker_model=async callable(prompt, system=None) -> str)`.
2. A server-configured backend: `--worker-cmd "codex exec ..."` (prompt on stdin, reply on stdout) or
   `--worker-openai-base-url URL --worker-model NAME` (any OpenAI-compatible endpoint; key from `OPENAI_API_KEY`).
3. MCP sampling: if the MCP client declares the `sampling` capability, `ctx.model` sends `sampling/createMessage`
   to the client, so the capsule uses the calling harness's model.

With none of these, the capsule halts at stage `worker`, code `no_model`. Whatever the model, the gate enforces the
declared call limit (default one call, since declarations carry no explicit model-call field), requires a text reply,
and takes the system text only from the capsule (the caller cannot change the pinned instructions).
The semantic verifier model is a separate setting (`verifier_model=callable(prompt)->text`, `--verifier-cmd`,
`--verifier-openai-base-url/--verifier-model`). If it resolves to the same backend as the worker, the receipt says
`verifier_independent: false`.

### Admission
The protected admission executor needs the run store, a root broker and a Linux sandbox, and no shipped declaration
lists `self_tests`. `admit` therefore runs in-process cases (`admission.py`): pins and declaration load; no unrun
declared self-tests (if a capsule declares any, it is not admitted here); positive cases deliver; generic input-guard
cases halt at `input_guard`; capsule-specific bad inputs halt at `worker`; and the verifier rejects an altered copy of
each delivered output (a data change and a trust change; deterministic capsules must reject both). Model capsules are
admitted against a canned reply, which tests the guards and verifier, not the model. Admission is process-local and is
not the AI4R library admission.

## Intent as a portable capability (`intent.compiler`, alias `research.intent`, release m1-8)

```python
rt = Runtime(); rt.admit('research.intent')
rt.invoke('research.intent', {'request': 'text', 'documents': [{'name': 'a.txt', 'text': '...'}]},
          worker_model=model, verifier_model=verifier)   # delivered only if the verifier passes
```
Inputs are plain: `request` (text), optional `documents` (extracted text), optional `prior_plan_outcome`. Output: `intent` (the Intent IR). The model and verifier are the usual backends (CLI flags, MCP sampling for the worker). Intent has no `task_objective` argument. It is listed in `tools/list` with its input schema. Code: `stage_adapter.py`.

**How the pipeline runs Intent (traced).**
- Pipeline: `research/compiler.py:38-` (`IntentionCompiler.run`) binds sub-node `intent` with one input `request` (`qualified-intake:field-contract:2`, record made by `intake.py:qualify_intake`) and one output `intent` (`urn:jiuwenswarm:m1-design:intent-ir:1.0.0`). `runner.py:_decode_inputs` (~690) turns the record into the dict the carrier gets; `InvocationContext` (`runner.py:166-201`) gives `input_ref/read_blob/read_json/model`.
- Carrier: `capsules/intent_m1_8.py:8-20` builds the payload from the intake and blobs and calls `capsules/_common.py:ask` (reads `ctx.contract` inputs/outputs for the prompt).
- Declaration and release: not `capsules/assets.py` (that builds the seven science stages). Intent comes from `compiler.py:107-260` `prepare_compiler_assets` (declaration `research_assets/compiler/intent.declaration.json`, catalog sha256 pins in `research_assets/catalog.json`) plus `intent_release.py:46-` `prepare_intent_m1_8_release`, which must equal `intent_m1_8_catalog.json` byte for byte. Wall time 420 s, one model call. `releases.py:24`: implicit m1-6, capture default m1-8.
- Checks on the output: `compiler.py:~320` registers `checks/compiler.py:compiler_checks` for `intent_schema`, `source_spans`, `exact_identity` (`check_intent`, `:20-33`). Stage checks in `checks/stages.py` (ResearchChecks) do not cover Intent. Node level: host_contract/identity/limits/authority, internal_acceptance, external_output, aggregate_limits (`runner.py:802-816`, `binding.py:792`).
- Semantic verifier: yes. The Intent checking profile (`compiler.py:~150`) has criteria declared_output_conformance, internal_consistency, limitations_consistency, uncertainty_consistency, instructions from `verifier.txt`.

**What the adapter does.**
- Pins: `prepare_compiler_assets(..., intent_version='m1-8')` runs against an in-memory store, so the same catalog hash checks apply. The runtime repeats them on every call and also hashes the imported `intent_m1_8.py` and `_common.py`. Any difference halts at `pin` (`asset_integrity`).
- Store: `StageStore` is content addressed with the product's refs (`blob:<sha256>`). The request becomes a blob, documents become source blobs, and a `qualified-intake` record is validated by the product contract. The profile/workspace/directory refs are marker blobs; Intent never reads them.
- Checks that run outside the pipeline: `intent_schema`, `source_spans`, and the identity part of `exact_identity`, by calling the product's `compiler_checks` unchanged. The output port is also validated against `intent-ir` by the worker gate.
- Verifier: the product's `SemanticVerifier` with the pinned Intent profile, plus the mechanical predicates, through the usual semantic stage. Intent is `semantic_required`: no verifier model means a `no_model` halt, never a delivery.
- Reported `not_applicable_outside_pipeline` in the receipt (never PASS): the observation half of `exact_identity` (needs the runner's invocation record), the host_* checks, and internal_acceptance/external_output/aggregate_limits (run records and gates). The runtime enforces its own wall time and model-call limit instead.
- Limits: no `resource_refs` (uploaded data files) are accepted; documents are text only.

**RSI.** Load another Intent release the same way as any capsule only after it has its own pinned catalog; RSI is deterministic-capsule only for now, so Intent is not an RSI target.

## Requirements as a portable capability (`requirements.compiler`, alias `research.requirements`, release m1-9)

```python
intent = rt.invoke('research.intent', {'request': text}, worker_model=m, verifier_model=v)['outputs']['intent']
rt.invoke('research.requirements', {'request': text, 'intent': intent}, worker_model=m, verifier_model=v)  # -> outputs['brief']
```
Inputs: `intent` (the Intent IR, normally from `research.intent`), `request` (the same text), optional `documents`, optional `policy` (default-policy record; omitted means the product default: `single_gpu`, no automatic retries; other values are refused as in the fixed compiler), optional `prior_plan_outcome`. Output: `brief` (Research Brief, schema 3.0.0). Same adapter, store, verifier rule and serving as Intent.

**How the pipeline runs it (traced).** `compiler.py:IntentionCompiler.run` runs sub-node `requirements` only after Intent is internally accepted, with three inputs: `intent` (`intent-ir`, the accepted ref), `intake` (`qualified-intake`) and `defaults` (`default-policy`); one output `brief` (`research-brief` 3.0.0). The carrier is `capsules/requirements_m1_9.py` (prompt `requirements_m1_9.txt`, helper `_common.py`). Release: `releases.py` lists m1-8 (implicit) and m1-9 (capture default is m1-8); the portable runtime serves m1-9, the current explicit release, built by `requirements_release.py` and compared with `requirements_m1_9_catalog.json`. Checks: `checks/compiler.py:compiler_checks` runs `check_brief` for `brief_schema`, `source_identity`, `requirement_coverage`. The Requirements checking profile has the three generic criteria plus `requirement_link_completeness`.

**What the adapter does.**
- Pins: the product's `prepare_compiler_assets(requirements_version='m1-9')` on an in-memory store, on every call, plus a hash of the imported `requirements_m1_9.py`, `_common.py`, `checks/compiler.py` and `target_comparisons.py` against the pinned bytes. Any difference halts at `pin` (`asset_integrity`).
- Inputs: request and documents become blobs and a `qualified-intake` record; the Intent and the policy become records with the product's refs. The supplied Intent must pass the product's `check_intent` (schema, spans, identity) against this request and these documents; otherwise the call halts at `input_guard` (`intent_input_invalid`) before any model call.
- Checks run unchanged: `brief_schema`, `source_identity`, `requirement_coverage` (the Intent coverage rule, mandatory-requirement links, default-policy authority, ref allowlist).
- Verifier: required (`semantic_required`), same as Intent. No verifier model is a `no_model` halt.
- `not_applicable_outside_pipeline`: `accepted_intent_input` (the pipeline's Intent has passed internal acceptance and its semantic review; a supplied Intent is only re-checked mechanically), the host_* checks, and internal_acceptance, external_output, aggregate_limits.
- Limits: no uploaded data files (`resource_refs`), text documents only.

## Evaluation as a portable capability (`research.evaluation`, release m1-5)

Inputs: `brief` (Research Brief 3.0.0), `hypothesis_blueprint`, `benchmark_payload`. The payload's `blueprint_ref.sha256` must be the SHA-256 of the canonical blueprint bytes, otherwise the call halts at `input_guard` (`blueprint_payload_mismatch`). Output: `evaluation_verdict`.

- Pipeline: `capsules/evaluation.py` (carrier), declaration and pins from `capsules/assets.py:build_research_assets` (compared with `capsule_catalog.json`), checks `checks/stages.py:ResearchChecks('evaluation')` (async, run unchanged): `evaluation_verdict_schema`, `refs_match_inputs`, `blueprint_rules_disjoint`, `rule_recomputation`, `finding_coverage`, `registered_rule_only`. The verdict is recomputed from the blueprint rules and the payload numbers by the product (`validate_scientific_verdict`).
- Pins: the product's catalog check (it covers every research stage's bytes, so a changed byte in any stage file refuses this capsule too), plus hashes of the imported `evaluation.py`, `_common.py` and the five check modules.
- Verifier: required (one output port, one review).
- Not applicable outside the pipeline: `input_provenance` (the pipeline feeds an accepted blueprint and a payload measured by the protected benchmark; here the caller supplies both, so nothing says the numbers were measured), the host_* checks, internal_acceptance, external_output, aggregate_limits.

## Screening as a portable capability (`research.screening`, release m1-4)

Inputs: `brief`, `candidate_set` (ideas with ids, titles, summaries, citations, assumptions, risks). The pinned rubric is bound as the third input from the release bytes, as in the pipeline. Outputs: `screening_result`, `opportunity_card`.

- Pipeline: `capsules/screening.py:ScreeningCarrier` (the pure `ranking.py` ranks the model's scores and picks Top-1; prompt and rubric are pinned body files), checks `ResearchChecks('screening')` (16 checks including ranking recomputation, rubric pin, citation membership, card match).
- Host record: the carrier calls `ctx.record_host('screening_result', ref)`; here an in-memory sink takes it (`StageCtx.host_records`).
- Output refs are content addressed (`blob:<sha256>`), as in the product, so the card's `screening_ref` equals the result's output ref.
- Pins: catalog check plus hashes of `screening.py`, `_common.py`, `ranking.py` (equal to the pinned `ranking_parent.txt`) and the check modules. Verifier: required, one review per output port.
- Not applicable outside the pipeline: `input_provenance` (the pipeline's candidate set comes from the protected Search stage), `host_record_custody`, the host_* checks, internal_acceptance, external_output, aggregate_limits.
- Served releases: m1-4 only. m1-5 and m1-6 are other releases of the same stage and are not wired.

## Which pipeline stages are portable

All portable stages share `stage_adapter.py`: pins from the product's own catalog check plus a hash of the imported worker and check sources, the product's checks run unchanged, the semantic verifier is required, and checks that need run records or gates are listed in the receipt as `not_applicable_outside_pipeline`.

| Capsule | Portable | Checks run | Not applicable outside the pipeline, and why | Verifier |
|---|---|---|---|---|
| `research.intent` (m1-8) | yes | intent_schema, source_spans, exact_identity (identity half) | observation half of exact_identity (needs the runner's invocation record); host_*; internal_acceptance, external_output, aggregate_limits (gates) | semantic, required |
| `research.requirements` (m1-9) | yes | brief_schema, source_identity, requirement_coverage; plus `check_intent` on the supplied Intent | accepted_intent_input (Intent's earlier acceptance and review); host_*; gates | semantic, required |
| `research.evaluation` (m1-5) | yes | all 6 declared checks (schema, refs, rule disjointness, recomputation, coverage, registered rules) | input_provenance (numbers not shown to be measured by the protected benchmark); host_*; gates | semantic, required |
| `research.screening` (m1-4) | yes | all 16 declared checks (ranking, rubric pin, scores, citations, card) | input_provenance (candidate set from protected Search); host_record_custody; host_*; gates | semantic, required (2 ports) |
| `research.hypothesis` | no | | the checks compare the blueprint with captured baseline and validation resource snapshots (files, revision, environment lock) that only the protected resource capture produces | |
| `research.paper_summary` | no | | its source-identity and citation checks read the run-input binding and buffer custody in the run store (`run_inputs.local_document_refs`); a rewrite would not be the product check | |
| `research.paper_summary_delivery`, `research.delivery` | no | | checks need current-run accepted summary/Brief and the advancing gate decisions (`is_accepted`, gate index) | |
| `research.search` | no | | governed connectors and the protected search scope | |
| `workflow.planner`, `workflow.paper_planner` | no | | checks read the library snapshot and plan policy | |
| `research.builder`, `research.benchmark` | no | | protected executor, sandbox and execution receipts | |

## What stays in AI4R
The run store and custody, the scheduler and plans, the protected executor and sandbox, the gates and the decision
records, calibration, and the pipeline-stage capsules marked "no" in the table above. Those stages read and write host refs
through `ctx.store`, `ctx.read_blob`, `ctx.input_ref`, `ctx.executor` and `ctx.connectors`, which this runtime does not
provide. See the survey in the hand-off report for what each would need.

## Register the MCP server

The server admits every loaded capsule at startup and serves one tool per capability. The tool name is the capability id,
the input schema comes from the declared ports, the description is the summary plus the guarantees and verifier stages.
Model capsules take an extra `task_objective` argument and are listed only when a worker backend is configured or the
client supports sampling. The result is the invoke result as JSON text; `isError` is true for a halt.

**JiuwenSwarm.** MCP servers are `mcp.servers` entries in `config.yaml` (template at `jiuwenswarm/resources/config.yaml:1494`),
read by `jiuwenswarm/common/config.py:2546` (`get_mcp_servers`, merged with `mcp/state.json`) and `:2593`, converted to a runtime
config by `jiuwenswarm/common/mcp_config.py:107` (`build_mcp_server_config`, stdio branch `:141`) and registered at
`jiuwenswarm/server/runtime/agent_adapter/interface_deep.py:5245`:

```yaml
mcp:
  servers:
    - name: capsules
      enabled: true
      transport: stdio
      command: python
      args: ["-m", "jiuwenswarm.capsule_runtime.mcp"]
      cwd: /path/to/jiuwenswarm-agentic
      env:
        PYTHONPATH: /path/to/jiuwenswarm-agentic
```

**Claude Code** (sampling is supported by the protocol; whether your build forwards it is client-dependent, so give the server a backend too if in doubt):

```
claude mcp add capsules --env PYTHONPATH=/path/to/jiuwenswarm-agentic -- python -m jiuwenswarm.capsule_runtime.mcp
# with a worker and a separate verifier model:
claude mcp add capsules -- python -m jiuwenswarm.capsule_runtime.mcp \
    --worker-openai-base-url http://localhost:8000/v1 --worker-model my-worker \
    --verifier-cmd "codex exec -"
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.capsules]
command = "python"
args = ["-m", "jiuwenswarm.capsule_runtime.mcp", "--require-semantic", "--verifier-cmd", "codex exec -"]
env = { PYTHONPATH = "/path/to/jiuwenswarm-agentic" }
```

## Risks and limits
- The time limit abandons a runaway worker thread; it cannot kill it. A model-backed worker stays on the caller's event
  loop, so its limit only fires if the worker awaits.
- Pins check bytes on disk at load and at each call, but Python may load a stale `.pyc` whose source mtime and size were
  forged. Treat the host filesystem as trusted; use read-only installs.
- Extra directories must follow the built-in layout (`release.json`, `release.py`, `worker.py`, `checks.py`, a sibling
  `packet.py`). They are mounted as a child package of `jiuwenswarm.research`, so relative imports like `...contracts` resolve.
- The MCP server is hand written JSON-RPC, not the `mcp` SDK, because the repo locks mcp 1.29 while hosts may carry 2.x, whose server API differs.
- Semantic review quality is the model's. A mechanical predicate failure or malformed reply halts, but a wrong PASS from the model passes.
- The generalist's own checks do not detect arbitrary extra keys in `data` (free-form by design); admission records this per capsule.
- `check_trace` and `packet_review` have no producer among today's capability capsules; the stages are wired and unit-checked only.

Tests: `python -m pytest tests/unit_tests/capsule_runtime -q -p no:cacheprovider`.
