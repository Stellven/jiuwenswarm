# Architecture snapshots before library thinning

These are read-only copies of the architecture tree at four commits immediately before the 2026-10-05 library-thinning change (`9b0c440d7`). Each copy retains its original `docs/architecture/` layout so diagrams and adjacent design pages remain together. The current architecture is maintained separately under `docs/architecture/`.

| Snapshot | Source commit | Description | Files |
|---|---|---|---:|
| [`1c09e8394`](1c09e8394/docs/architecture/README.md) | `1c09e83940b445563e44cc185c10330986d40d4f` | Centralize presentation and add complete information flow diagrams | 254 |
| [`f46f88255`](f46f88255/docs/architecture/README.md) | `f46f88255d22a871fe29d170073481be32a022db` | Publish linked M1 architecture snapshot and defer capsule interaction analysis | 262 |
| [`86d6041dc`](86d6041dc/docs/architecture/README.md) | `86d6041dcd196cd58d5d240c87a91a5352f09b2e` | Correct showcase to gated intent and requirements then bound DAG execution | 263 |
| [`a3aa887be`](a3aa887be/docs/architecture/README.md) | `a3aa887be0dc00d070497c4466f86def98d94a5c` | Reconcile M1 information flow and Markdown around fixed preparation and planned DAG | 269 |

The last snapshot is the complete architecture state immediately before thinning. The earlier snapshots preserve the presentation and flow revisions as they developed. Use the source commit IDs to compare changes in Git. Snapshot bytes come from Git blobs; no generators or link rewrites were applied.

## Most important architecture reading

Start with these in the final pre-thinning snapshot (`a3aa887be`):

1. [Information flow](a3aa887be/docs/architecture/system/information-flow.md) — the end-to-end stages, their handoffs, and the planned DAG.
2. [System connections diagram](a3aa887be/docs/architecture/system/diagram.md) — how components and data connect.
3. [Production pipeline](a3aa887be/docs/architecture/m1/pipeline.md) and [control flow](a3aa887be/docs/architecture/m1/control-flow.md) — what runs and how work advances.
4. [Planner](a3aa887be/docs/architecture/system/planner.md) — how a plan is proposed, validated, and bound.
5. [CC runner](a3aa887be/docs/architecture/capsule/runner.md) and [verification](a3aa887be/docs/architecture/system/verification.md) — how a capsule runs and its result is checked.
6. [Deployment](a3aa887be/docs/architecture/system/deployment.md), [durable records](a3aa887be/docs/architecture/system/records.md), and [observability](a3aa887be/docs/architecture/system/observability.md) — where it runs, what it preserves, and how to inspect it.

For a quick orientation, read the [architecture home](a3aa887be/docs/architecture/README.md), then the information-flow and connections diagrams. The other pages explain the main execution, verification, and operational boundaries. The rest of each snapshot is supporting detail; the list above marks the documents most useful for understanding the design.
