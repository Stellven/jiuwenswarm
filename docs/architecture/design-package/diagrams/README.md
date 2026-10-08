# Diagram views

Start at the [system view](../m1-design.md); follow its component/field routes. Mermaid in each owning document defines meaning; SVG/PNG are checked projections. Use SVG to zoom. Work, verifier and protected gate roles remain distinct.

## Diagram standards

**Show responsibility, containment, and the exact artifact that leaves each boundary.** A diagram should let a reader answer: what enters this node, which assigned capability handles it, what candidate it produces, who checks it, who decides, and what accepted output advances.

| Element | Shape and color | Label must state |
|---|---|---|
| Governed workflow boundary | Enclosing, dashed subgraph | The CC system that carries accepted artifacts between nodes |
| Node boundary | Enclosing, solid subgraph | Node objective and that its work, checks, verifier assignments and gate decisions are governed inside that node |
| Work subnode | Blue rounded/rectangular box | Work CC/capsule role, action, and named candidate output |
| Verifier subnode | Purple rounded/rectangular box | Verifier CC role and what exact subject it assesses; it assesses, never edits or accepts |
| Deterministic check | Orange diamond | What is checked and which check result is produced |
| Protected review context | Gray document/record shape | Exact candidate, accepted inputs, contract/criteria, check results and relevant observations assembled for the verifier; this is data, not another agent |
| Verifier assessment | Teal document/record shape | Typed verdict, findings/reasons, evidence and uncertainty; this is verifier output, not the verifier itself |
| Assessment validation | Orange double-line box | Schema, completeness and subject-identity validation; it does not make the gate decision |
| Protected gate | Amber hexagon or double-line box | Which check results and validated assessment it interprets, and whether it commits or halts |
| Input, candidate or accepted artifact | Green cylinder/document | Exact artifact name and whether it is input, candidate, or durably accepted output |

Put inputs and outputs outside the **node** boundary, but keep inter-node artifacts inside the enclosing workflow boundary. This makes them external to that node while showing that the governed CC workflow carries them to the next node. Only the protected gate releases an accepted reference. A candidate or assessment is never an accepted output. Use arrows for the actual data/control direction and label important handoffs. Use one visual style per responsibility; do not give context records, CCs, assessments and gate logic the same color. Put a compact legend on diagrams that introduce a style not defined here.

Keep examples visibly labeled as examples. A diagram explains the existing contract; it must not add a new stage, skip a check, combine authorities, or imply autonomous repair, replay or dispatch that the design does not permit.

| View | Owning source | Rendered view |
|---|---|---|
| Ownership and flow | [artifact-inspection.md](../artifact-inspection.md#ownership-and-flow) | [SVG](../diagrams/artifact-inspection-1.svg) / [PNG](../diagrams/artifact-inspection-1.png) |
| Local Compose topology | [automation.md](../automation.md#local-compose-topology) | [SVG](../diagrams/automation-1.svg) / [PNG](../diagrams/automation-1.png) |
| Exact verification boundary | [capsules.md](../capsules.md#exact-verification-boundary) | [SVG](../diagrams/capsules-1.svg) / [PNG](../diagrams/capsules-1.png) |
| Full M1 phases | [delivery-phases.md](../delivery-phases.md#full-m1-phases) | [SVG](../diagrams/delivery-phases-1.svg) / [PNG](../diagrams/delivery-phases-1.png) |
| Purpose and composition | [development-tools/sidecar/README.md](../development-tools/sidecar/README.md#purpose-and-composition) | [SVG](../development-tools/sidecar/composition.svg) / [PNG](../development-tools/sidecar/composition.png) |
| AI4Research sidecar: client-validation runner | [development-tools/test-runner/README.md](../development-tools/test-runner/README.md#ai4research-sidecar-client-validation-runner) | [SVG](../diagrams/development-tools-test-runner-README-1.svg) / [PNG](../diagrams/development-tools-test-runner-README-1.png) |
| When to call the human | [failure-and-human.md](../failure-and-human.md#when-to-call-the-human) | [SVG](../diagrams/failure-and-human-1.svg) / [PNG](../diagrams/failure-and-human-1.png) |
| Delivery Phase 3 clarification before acceptance | [failure-and-human.md](../failure-and-human.md#delivery-phase-3-clarification-before-acceptance) | [SVG](../diagrams/failure-and-human-2.svg) / [PNG](../diagrams/failure-and-human-2.png) |
| Purpose and boundary | [guard-design.md](../guard-design.md#purpose-and-boundary) | [SVG](../diagrams/guard-design-1.svg) / [PNG](../diagrams/guard-design-1.png) |
| Assignments and check plans | [guard-design.md](../guard-design.md#assignments-and-check-plans) | [SVG](../diagrams/guard-design-2.svg) / [PNG](../diagrams/guard-design-2.png) |
| Output-led review and controlled disclosure | [guard-design.md](../guard-design.md#output-led-review-and-controlled-disclosure) | [SVG](../diagrams/guard-design-3.svg) / [PNG](../diagrams/guard-design-3.png) |
| What to build | [immediate-plan.md](../immediate-plan.md#what-to-build) | [SVG](../diagrams/immediate-plan-1.svg) / [PNG](../diagrams/immediate-plan-1.png) |
| Deterministic boundary | [intent-design.md](../intent-design.md#deterministic-boundary) | [SVG](../diagrams/intent-design-1.svg) / [PNG](../diagrams/intent-design-1.png) |
| Requirements CC and the second boundary | [intent-design.md](../intent-design.md#requirements-cc-and-the-second-boundary) | [SVG](../diagrams/intent-design-2.svg) / [PNG](../diagrams/intent-design-2.png) |
| Example intent-to-plan flow | [m1-design.md](../m1-design.md#from-meaning-to-a-governed-research-program) | [SVG](../diagrams/m1-design-1.svg) / [PNG](../diagrams/m1-design-1.png) |
| Execution and model routing | [m1-design.md](../m1-design.md#execution-and-model-routing) | [SVG](../diagrams/m1-design-2.svg) / [PNG](../diagrams/m1-design-2.png) |
| Where RSI connects | [m1-design.md](../m1-design.md#where-rsi-connects) | [SVG](../diagrams/m1-design-3.svg) / [PNG](../diagrams/m1-design-3.png) |
| Purpose and connections | [model-routing.md](../model-routing.md#purpose-and-connections) | [SVG](../diagrams/model-routing-1.svg) / [PNG](../diagrams/model-routing-1.png) |
| Delivery Phase 3 integration accounting | [phase-details.md](../phase-details.md#delivery-phase-3-integration-accounting) | [SVG](../diagrams/phase-details-1.svg) / [PNG](../diagrams/phase-details-1.png) |
| Deployment and boundaries | [placement.md](../placement.md#deployment-and-boundaries) | [SVG](../diagrams/placement-1.svg) / [PNG](../diagrams/placement-1.png) |
| Offline RSI | [placement.md](../placement.md#offline-rsi) | [SVG](../diagrams/placement-2.svg) / [PNG](../diagrams/placement-2.png) |
| System picture | [README.md](../README.md#system-picture) | [SVG](../diagrams/README-1.svg) / [PNG](../diagrams/README-1.png) |
| POC task internals | [m1-design.md](../m1-design.md#inside-the-poc-task) | [SVG](../diagrams/m1-design-4.svg) / [PNG](../diagrams/m1-design-4.png) |
| Search node responsibilities and handoffs | [m1-design.md](../m1-design.md#research-nodes-and-subnodes) | [SVG](../diagrams/m1-design-5.svg) / [PNG](../diagrams/m1-design-5.png) |
| Screening node responsibilities and handoffs | [m1-design.md](../m1-design.md#research-nodes-and-subnodes) | [SVG](../diagrams/m1-design-6.svg) / [PNG](../diagrams/m1-design-6.png) |
| Hypothesis node responsibilities and handoffs | [m1-design.md](../m1-design.md#research-nodes-and-subnodes) | [SVG](../diagrams/m1-design-7.svg) / [PNG](../diagrams/m1-design-7.png) |
| Evaluation node responsibilities and handoffs | [m1-design.md](../m1-design.md#research-nodes-and-subnodes) | [SVG](../diagrams/m1-design-8.svg) / [PNG](../diagrams/m1-design-8.png) |
| Delivery node responsibilities and handoffs | [m1-design.md](../m1-design.md#research-nodes-and-subnodes) | [SVG](../diagrams/m1-design-9.svg) / [PNG](../diagrams/m1-design-9.png) |
| Research path and ports | [research-design.md](../research-design.md#research-path-and-ports) | [SVG](../diagrams/research-design-1.svg) / [PNG](../diagrams/research-design-1.png) |
| Commit before successor release | [research-design.md](../research-design.md#commit-before-successor-release) | [SVG](../diagrams/research-design-2.svg) / [PNG](../diagrams/research-design-2.png) |
| Establish intent before planning | [workflow.md](../workflow.md#establish-intent-before-planning) | [SVG](../diagrams/workflow-1.svg) / [PNG](../diagrams/workflow-1.png) |
| Tasks, nodes, and verification | [workflow.md](../workflow.md#tasks-nodes-and-verification) | [SVG](../diagrams/workflow-2.svg) / [PNG](../diagrams/workflow-2.png) |

All 32 maintained views have matching [source/projection hashes](manifest.json). Rendering proves syntax/presentation, not runtime behavior.
