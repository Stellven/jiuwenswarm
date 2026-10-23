# M1 capability DAG planning

Typed planning is required M1 functionality. The normal `research.planner`
assembles a graph from the admitted catalog; no separately admitted optional
Planner is needed. Read [Core typed Planner](typed-planner-m1.md) for current
behavior, bounded correction, gates, release migration and evidence limits.
The [previous optional-Planner proposal](history/2026-10-23-optional-planner-original.md)
is preserved as historical context and is superseded on this point.

Generalist and utility capsules remain separate optional feature branches.
Merge desired capsules, qualify their checking assets, then use the existing
Library admission and activation process. Source installation alone grants no
standing. The core Planner sees every selectable admitted capsule's complete
pinned declaration, including newly admitted optional capsules.

Optional packet capsules use `urn:ai4r:work-packet:1.0.0`. Compatibility requires
real matching schemas and bound artifacts, not implicit conversion of scientific
outputs. Low trust propagates; checks do not establish scientific truth.
`ai4r_capability_dag_v1` remains readable for previously selected profiles, and
uses the same core Planner. Fresh profiles use `ai4r_integrated_policy_v2`.
