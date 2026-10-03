---
type: index
status: draft
version: 3
owner: muk
sources: [../policies.md, ../open-issues.md]
provides: [system.blackboxes]
consumes: []
depends_on: [environment.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
tags: [system, validation]
---

# No undefined M1 system responsibilities

All in-scope components have concrete owning designs in [module map](modules.md), [handoff](handoff.md) and [coverage](../prd/coverage.md). The name of this page remains for older links; it no longer indexes implementation-free black boxes.

The [deployment](deployment.md) and [environment](environment.md) specify one Linux image/profile on Linux Docker Engine or macOS Docker Desktop, plus doctor probes. Generated-code and hidden-oracle execution remain unavailable on any profile whose checks do not pass. This is a failure contract, not a claim of validated platform support. Downstream runtime evidence belongs in [acceptance obligations](../open-issues.md).

Saurav's pending external benchmark schema has a [provisional export adapter](benchmark-export.md). A new schema affects that boundary, not unrelated research-stage schemas. Later owner sources enter the [source-change queue](../../product/SOURCE_FREEZE.md#later-arrivals).

Missing prose is resolved with a sourced replaceable design. A genuine requirement conflict is recorded with affected consumers and a concrete safe outcome; it is not hidden behind a module named "TBD". The fresh AI review checks that each coding question has an answer and that unrun security checks are never represented as passed.
