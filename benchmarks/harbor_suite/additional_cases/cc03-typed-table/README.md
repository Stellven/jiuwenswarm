# Typed table normalization CC

Opt-in development case `cc03-typed-table` targets the implemented optional
`utility.table_normalize_typed@m1-1`. Its declared input `packet` and output
`result` both use `urn:ai4r:work-packet:1.0.0`. The protected criteria record the
authored declaration and implementation references. Preparation does not admit
or activate the candidate. Requalify and freeze new criteria if its bytes change.

Four variants cover an ordinary CSV, leading-zero/quoted-newline edge behavior,
JSON integer/boolean/null distinctions, and a malformed row refusal. Success is
exact independently checked content plus separately checked original E3 binding
and provenance. A correct refusal is expected-behavior success, not productive
completion. Missing original records remain unavailable. These local fixtures
are development material, not external benchmark or held-out results.

The default ten-case/69-variant release is unchanged. Select this registered
extension explicitly with `--case cc03-typed-table` and `--cases-root` pointing
to this file's grandparent (`additional_cases`). `validate` runs its oracle
fixtures; `prepare` freezes ordinary Harbor tasks. A live isolated variant needs
an actual admitted E3 source contract/observation and fresh prepared evaluation
overlay for the exact request, inputs, current implementation and declaration.
Use the existing evaluation-pilot profile/source/scope authoring and Harbor
evaluation binding, not direct worker calls or a fabricated observation.

Only `public/packet-*.json` belongs in the worker's inputs. `referee/` and oracle
labels remain with the grader. The captured source `packet` reference must match
the actual original public JSON bytes, or a protected overlay must pin the actual
supported publication. Never invent source/runtime identities to make it pass.

Plain-Codex content comparisons can reuse `evaluate_content` with identical
public packet, full port schemas, model/effort and budgets for the three valid
variants. Use the comparator's explicit content-evaluator API; its default
evaluator remains the original CC01 case. Keep binding conformance separate.
The malformed refusal requires a matching explicit refusal-output contract for
the baseline and is not automatically a comparable ordinary output task.
