# Reduce fresh package provenance parsing

Use this optional component when actual Host profiling identifies repeated Python
metadata parsing as a measurable fixed cost. Read METHOD.md and COMPONENT.json.

Keep the inventory fresh each call. Do not substitute an unbounded process cache,
an inventory recorded only at worker startup, or a stale key replay for real work.
Review the patch against the current target SHA; run patch applicability checks,
package equivalence/negative controls, actual-environment ABBA timing, and an
isolated whole-Host comparison. Keep profiling and allocation tracing separate
from the uninstrumented latency comparison. Preserve output inventory exactly.

This material does not grant authority to modify the core host. Coordinate with its
owner before applying; no protocol changes are needed. Report CPU overhead only.
