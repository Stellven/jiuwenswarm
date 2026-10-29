# Diagram views

The embedded Mermaid blocks in the owning Markdown documents define meaning. These SVG/PNG views are generated projections of those blocks. Use SVG for zooming. Where a palette is used, blue is work, purple verification, amber protected infrastructure, and green records. Optional development-tool diagrams describe a separate lane.

| View | Owning source | Rendered view |
|---|---|---|
| System connections | [m1-design.md](../m1-design.md#system-connections) | [SVG](../diagrams/m1-design-1.svg) / [PNG](../diagrams/m1-design-1.png) |
| Container access | [placement.md](../placement.md#container-access) | [SVG](../diagrams/placement-1.svg) / [PNG](../diagrams/placement-1.png) |

All 2 maintained diagrams parse and render with Mermaid CLI 12.0.0. [Projection hashes](manifest.json) bind each view to its source block. Rendering establishes syntax and presentation, not runtime behavior. Historical diagrams are excluded.
