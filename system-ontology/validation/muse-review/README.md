# Read-throughs of the Muse design for what it still said about Strata (2026-11-18)

The Muse design (`examples/systems/muse/`) is derived from the description of Strata. An intake run on 2026-11-18
stopped on a contradiction inside it: the model selects 8 of 256 experts, and a node carried over unchanged from
Strata still said 10 of 512. The rules of `tools/so_leftovers.py` then found 88 such places. These three files are
what readers found after the rules, each time on the description as it then stood.

| File | Read after | Entries | Of which plainly wrong |
|---|---|---|---|
| `review-1.yaml` | the rules were applied | 141 | 78 |
| `review-2.yaml` | the findings of the first were handled, with the source's statements kept one by one | 64 | 15 |
| `review-3.yaml` | adapted components kept no statement of the source | 15 | 4 |

Each reader was a Claude subagent (model: opus) alone in a folder with the Muse description, the model, the machine
and the target, and the same instructions. Each read all 36 components and every flow. They are not people, and
the three did not find the same things: a fourth reader would probably find more.

What was done with the findings is in `examples/systems/muse/_derive.yaml` (the adaptations, the reworded flows, the
terms that may not appear) and in `tools/so_derive.py` (what a design carries from its source). One finding was left
as it is, because it is a choice of the design and not a leftover: the component that parks other conversations,
against the statement that the first version keeps one conversation in memory.
