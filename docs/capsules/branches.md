# Branch handoff

Base: latest checked `ai4r_M1`, `bfc30ba291c762d09f464c3e6a6c25f011826a33`.
All branches are local, committed and unpushed.

| Branch | Functional change | Dependency |
| --- | --- | --- |
| `deployment-usability` | Repository-owned local/SSH build, stage, start, inspect, verified result retrieval and safe temporary-resource expiry | M1 only |
| `capsules/planner-foundation` | Opt-in typed DAG planning, explicit evidence coverage and separately qualified/activated optional capsules; existing default workflows retained | M1 only |
| `capsules/generalist-m1` | Low-trust fallback producing task-bound files/data and bounded expression results, with frozen-task checking and gap provenance | Foundation |
| `capsules/table-normalize-m1` | Explicit JSON/CSV table parsing that preserves values/types/order and verifies original-source equality | Foundation |
| `capsules/calculate-m1` | Explicit count/sum/mean/min/max with reproducible decimal arithmetic and independent recomputation | Foundation |
| `capsules/markdown-report-m1` | Deterministic Markdown and manifest from supplied content, preserving evidence and trust | Foundation |
| `capsules/development-guide` | Documents capsule development/release and a proposed fixed factory lifecycle with bounded adaptive agents | Foundation |
| `capsules/m1-integration-check` | Combined merge rehearsal and actual utility-composition test for review; does not change M1 or activate candidates | Selected branches above |

Merge foundation first, then any desired capsule branch independently. Each
capsule's extra diff contains only its own package, guide and tests. Deployment
is independent. The integration branch is a convenience to inspect the combined
result, not an extra required feature or a replacement for the maintained M1.

Source/fixture checks are distinct from real model, independent calibration,
live Docker, ARM64 and native Spark checks. These latter checks need connected
runtime evidence and are not claimed complete. Docker Desktop was unavailable
on this workstation. See the [validation receipt](validation.md) for actual checks.

## Later integration supersession

This page records the original branch handoff. The foundation's optional-Planner
framing is superseded by the required core `research.planner`.
[Current candidate status](../../deploy/m1/INTEGRATION-STATUS.md) records combined
local source, the shared M1 deployment revert, exact verification and future merge
order. Do not follow this historical table as the current deployment state.
