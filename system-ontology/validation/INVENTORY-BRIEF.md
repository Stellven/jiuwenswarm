# Brief: a parts inventory of one inference engine

We are building an evidence base of what parts real inference engines have, at the same depth for every engine, so
that generic node types can be induced from it and tested against it. Your job is one engine's inventory. It is
evidence, not a classification: describe the engine as it is, and do not try to make it resemble any other engine
or any scheme of types.

## Rules

- Read-only. Do not build, run, install, download or modify anything under `<refs>`.
- Work from the implementation. Earlier notes and an earlier, shallower parts list are given as a starting point;
  both may be wrong or incomplete. Where they say "not read", read it now. Confirm what you keep.
- A part is a unit with one job: it owns some state, or makes a decision while the engine runs, or performs a
  computation the model defines, or moves data between places, or sits on the engine's boundary. Do not make one
  part per source file, and do not merge two jobs because they share a file. Typically 25 to 45 parts.
- Cover the whole engine: offline preparation; loading; memory planning at startup and memory management while
  running; anything that caches, places or moves weights; the step or token loop; the model's computation;
  per-sequence state of every kind; prompt reading; drafting, checking and committing; sampling and any constraint
  on output; serving, batching and scheduling across requests; anything spanning devices or machines; other input
  kinds (image, audio); configuration and calibration; telemetry. If the engine has no such part, say so under
  `absent`.
- Record what is outside the engine but lives in its repository (benchmarks, test harnesses, client apps, build
  bookkeeping) under `outside_engine`, not under `parts`.
- Use plain words. Where the engine has its own name for something, give it once in `engine_name`.

## Output

One YAML file at the path you are given. Quote any text that contains a colon, comma, `#` or quote.

```yaml
engine: "<name>"
revision: "<commit or version read>"
basis: "which directories and files were read in code, which only in documents, and what was not read"
concurrency: single            # single | batched : does one step of the engine serve one sequence or several
models: "which model families it serves, and what is unusual about them (experts, recurrent state, lookup tables, draft heads, other input kinds)"
parts:
  - id: "short-kebab-id"
    engine_name: "what the engine calls it, if anything"
    does: "one sentence: the one job"
    not: "what is easily mistaken for its job, if anything"
    runs: [startup]            # any of offline, startup, per_request, per_step, per_layer, background, on_demand
    takes: [{from: "<part id or outside: client | operator | model_files | storage | os>", what: "..."}]
    gives: [{to: "<part id or outside>", what: "..."}]
    owns_state: ["state it alone keeps consistent, in plain words"]
    exists_because: "the property of the model, the machine or the workload that makes this part necessary; or 'every engine needs it'"
    output_effect: none        # none | numeric (last bits may differ) | changes_output
    output_effect_when: "the condition, when not none; and compared with what"
    decisions:                 # the choices that shape its behaviour, one line each, WITHOUT the values chosen
      - "..."
    when_things_go_wrong: ["what it does when a resource is short, a read fails, a limit is hit"]
    must_never: ["rules it must never break"]
    evidence: ["file paths, with line ranges where useful"]
    read: code                 # code | docs | inferred
absent:
  - {job: "...", why: "why this engine has no such part"}
outside_engine:
  - {name: "...", what: "..."}
surprises: ["things about this engine that a scheme built from other engines would probably get wrong"]
not_read: "what you did not read"
```

Every `takes.from` and `gives.to` that is a part must be the id of a part in your list.

## Final message

The number of parts, how many are `read: code`, the three surprises that matter most, and what you did not read.
