# Brief: match one engine's recorded decisions to the choices of its node types

You are given one file, `validation/choices/packet-<engine>.yaml`. It is all you need. Do not read any other file
under `validation/`, and do not read the engine's source.

## What the packet holds

- `parts`: the parts of one inference engine that recorded design decisions. Each part has what it `does`, the node
  `types` it is an instance of, and its `decisions`, each with an id (`D001`, ...). A part may carry `corrections`:
  where a later reader found the record wrong against the source, judge by the correction.
- `candidates`: for each node type, its list of `choices`. A choice names something that whoever builds an engine
  has to decide, in words that do not depend on one engine. Each has an `id` such as `expert-cache#03`.

## What to do

For every decision, look only at the candidates of that part's own `types`. Give the decision one verdict:

- `covered`: one choice plainly names this decision. A reader who knew only the choice would say "yes, that is what
  this engine decided here". Name that choice.
- `loosely`: a choice names something near it, but a reader would have to stretch it. Name the nearest choice.
- `none`: no choice of the part's types names it, even if a choice of some other type would.
- `engine_specific`: it is not a design choice a generic node type should list: the value of one constant, a
  workaround for a defect, a naming or packaging detail.

Rules:

- One decision gets at most one choice: the best one. Do not spread a decision over several.
- Several decisions may name the same choice.
- A decision that bundles two things is judged on its main point.
- Be strict. When you hesitate between `covered` and `loosely`, write `loosely`. When you hesitate between `loosely`
  and `none`, write `none`. The purpose is to find which choices engines really decide, not to make the list look
  complete.
- Judge every decision. The count in the packet's `decisions` field is the number of rows you must write.

## What to write

One file, `validation/choices/map-<engine>.yaml`, and nothing else:

```yaml
engine: <engine>
map:
- {d: D001, choice: "model-conversion#02", fit: covered}
- {d: D002, choice: "model-conversion#06", fit: loosely}
- {d: D003, choice: null, fit: none}
- {d: D004, choice: null, fit: engine_specific}
```

Write the file with a script or directly, as you prefer, but keep any scratch file inside
`validation/choices/scratch-<engine>/` and delete it when done. Then reply with the four totals and, in one or two
sentences, anything about the choices that made the judging hard (for example two choices of one type that say
nearly the same thing).
