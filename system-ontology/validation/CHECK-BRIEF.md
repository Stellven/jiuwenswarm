# Brief for an independent check of the node types against one engine

You check a draft of generic node types against the parts inventory of one real engine. You did not write the types.
Be strict: the purpose is to find where the types are wrong or incomplete, not to confirm them.

## What to read

1. `ontology/node-types.draft.yaml` — the node types. The header comment defines the fields, the five levels of
   `effect_on_output` and the two strengths of `rules`.
2. `validation/inventory/<engine>.yaml` — the engine's parts. `validation/INVENTORY-BRIEF.md` explains its fields.
   `validation/inventory/<engine>.corrections.yaml` lists entries an earlier reader found wrong against the source;
   where it corrects an entry, judge by the correction.
3. `validation/reference-assignment.yaml` — under `<engine>`, the node type each part was assigned to. Under `also`,
   parts that do two jobs and the second type that counts for them.

You may read the engine's source (read-only, nothing is built or run) to settle a doubt about whether the inventory
is right. Do not read other files under `validation/` (earlier rounds, other raters, the held-out engine).

## What to judge

### 1. Decision coverage

For every entry in every part's `decisions`, compare it with the `choices` of the part's assigned type only (and of
the `also` type where one is given). Give each decision one verdict:

- `covered`: a choice plainly names this decision.
- `loosely`: a choice names something near it, but a reader would have to stretch it.
- `not_covered`: no choice of that type names it. This holds even when a choice of another type would.
- `engine_specific`: not a design choice a generic type should list: one constant's value, a workaround for a defect,
  a naming or packaging detail.

### 2. Claims

For every part, check each statement of its assigned type against what the inventory records for that part
(`does`, `output_effect`, `output_effect_when`, `must_never`, `when_things_go_wrong`, `decisions`).

- A `must` rule is contradicted when this engine's part does not keep it.
- A `should` rule is not contradicted by an engine that relaxes it. It is contradicted only when it is wrong as a
  correctness rule. Record a relaxation the type does not mention under `relaxations`.
- `effect_on_output` claims the set of levels the node's own work reaches: its arithmetic, the precision it stores,
  the content it writes (from draft 0.7; see the header and `output_principles`). It is contradicted when the part's
  own work reaches a level the type does not list, or when a listed condition is false of this engine. Use the level
  definitions in the header, not your own.
- Two things are not contradictions, and go under `new_causes` with `kind: own` or `kind: through`:
  a cause of the node's own effect at a level the type does list but under a condition it does not name; and an
  effect the part has only through another node (by deciding a step's width, a cut, a placement, what is resident,
  what stored state survives, which setting is on) that neither `affects_output_through` nor `output_principles`
  names. If you cannot tell whether an effect is the node's own or through another node, say so in the entry.
- `summary`, `not`, `takes`, `gives`, `state` are contradicted when the part plainly is an instance and does otherwise.

Where the inventory itself looks wrong, check the source and record the finding under `inventory_errors` instead of
counting a contradiction.

### 3. Assignments

Name every part whose assigned type is wrong, the better type or `none`, and why.

## What to write

One file, `validation/<round>/check-<engine>.yaml`:

```yaml
engine: <engine>
decision_coverage:
  totals: {decisions: N, covered: N, loosely: N, not_covered: N, engine_specific: N}
  per_type:
    - {type: "<type>", decisions: N, covered: N, loosely: N, not_covered: N, engine_specific: N}
  loosely:            # every decision judged loosely
    - {part: "<part>", type: "<type>", decision: "<short>", nearest_choice: "<the choice stretched>"}
  not_covered:        # every decision judged not_covered, none left out
    - {part: "<part>", type: "<type>", decision: "<short>", kind: "<sizing|placement|policy|timing|threshold|failure|precedence|format>", missing_choice: "<the choice in generic words, no engine names or numbers>"}
contradictions:
  - {part: "<part>", type: "<type>", claim: "<the statement, quoted>", evidence: "<what the inventory or source records>", fix: "<the rewording that would be true of this engine and still say something>"}
new_causes:
  - {part: "<part>", type: "<type>", kind: "<own|through>", level: "<level>", cause: "<the cause in generic words>", evidence: "<what the inventory or source records>"}
relaxations:
  - {part: "<part>", type: "<type>", rule: "<the should rule>", how: "<how this engine relaxes it>"}
wrong_assignments:
  - {part: "<part>", assigned: "<type>", better: "<type or none>", why: "<one or two sentences>"}
inventory_errors:
  - {part: "<part>", field: "<field>", recorded: "<what it says>", source_shows: "<what the source shows, with file>"}
```

The totals must equal the sums over `per_type`, and the number of entries under `loosely` and `not_covered` must
equal their totals. Check that the file parses.
