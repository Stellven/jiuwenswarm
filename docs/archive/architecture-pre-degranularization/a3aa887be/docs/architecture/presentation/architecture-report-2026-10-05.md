# M1 architecture report: current reading route

The [showcase](showcase/README.md) is the current point-form report source. It replaces the former fixed-chain manuscript. [Presentation index](README.md) links both refreshed PDFs.

## Architecture decisions

1. [System](showcase/presentation.md): Dockerized monolith, fixed SwarmFlow preparation and planned/frozen execution.
2. [Capsules](showcase/capsules.md): reusable CCs, task-specific nodes and the shared verifier capsule.
3. [Runtime](showcase/runtime-and-improvement.md): automatic declaration-derived Gate tests, local execution, durable advancement and halt/recovery.
4. [Data](showcase/data-and-permissions.md): inputs, evidence, permissions, ordinary Delivery and user retrieval.
5. [Contracts](showcase/schemas-and-connections.md): existing schemas and the exact revised interfaces still requiring reconciliation.
6. [Validation](showcase/validation-and-development.md): actual documentation evidence versus pending implementation checks.

[Current information-flow views](../system/information-flow.md) and [temporal sequence](../system/temporal.md) show data and control order. [Control-flow owner](../m1/control-flow.md) is authoritative; this report adds no API or product rule.
