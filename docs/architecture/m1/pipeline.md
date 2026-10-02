---
type: design
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../system/nodes.md]
provides: [m1.run_plan]
consumes: [cc.type.run_plan, cc.type.intake, cc.type.intent_ir, cc.type.research_brief]
depends_on: [../system/nodes.md, ../types/run-plan.md, research-gates.md, ../system/lifecycle.md]
tags: [m1, design, control]
---

# The complete M1 research path

A smaller capsule inventory (15 instead of 35) is proposed in [capsule inventory proposal](capsule-inventory-proposal.md); it is not adopted. This page owns the proposed eleven-node static M1 plan: one pure source projection followed by the ten governed research/workstation steps. Startup compiles it only after all selected capsules, gates, profiles, methods and policies are admitted. Product conflicts or unsupported security profiles block only affected invocations. Partial developer invocations remain available through [verification](../system/verification.md) and do not claim M1 completion.

```mermaid
flowchart LR
    L["intake"] --> X["source"] --> I["intent"] --> R["requirement"]
    R --> S["search"]
    S --> SCR["screening"]
    SCR --> H["hypothesis"]
    H --> P["poc"]
    P --> B["benchmark"]
    B --> E["evaluation"]
    E --> REP["report"]
    REP --> D["deliver"]
```

Each arrow is conditional on that node's durable advancing Gate decision and supervisor release, as specified by [lifecycle](../system/lifecycle.md). A scientific fail proceeds through Evaluation to Report and Delivery when its infrastructure Gate passes. No capsule or view chooses a successor.

## Capsule and source map

| Step | PRD | Capsule / gate / owning contracts |
|---|---|---|
| source | 3.1 projection, architecture D4 | [extract_text](extract-text.md) / `research.accept_source_text` mechanical Gate profile |
| intent | 3.2 preparation, architecture D5 | [compile_intent](intent-capsule.md) / [accept_intent](intent-gate.md) |
| requirement | 3.2.1–3.2.7 | [compile_brief](requirement-capsule.md) / [accept_brief](brief-gate.md) |
| search | 3.3.1–3.3.6 | [search_ideas](search-capsule.md) / [accept_ideas](search-gate.md) |
| screening | 3.4.1–3.4.7 | [select_opportunity](screening.md) / [accept_card](screening-gate.md); decisions 48–53 |
| hypothesis | 3.5.1–3.5.5 | [form_hypothesis](hypothesis.md) / [accept_hypothesis](research-gates.md); decisions 41/58 |
| poc | 3.6.1–3.6.5 and 4.9 | [build_poc](poc.md) / [accept_poc](research-gates.md); measurement and package contracts |
| benchmark | 3.7.1–3.7.4 | [run_benchmark](benchmark.md) / [accept_benchmark](research-gates.md); confined process plus trusted methods |
| evaluation | 3.8.1–3.8.6 | [evaluate_results](evaluation.md) / [accept_evaluation](research-gates.md); decision 44 |
| report | 3.9.1–3.9.2 | [write_report](delivery.md) / [accept_report](research-gates.md); pinned static template |
| deliver | 3.9.3–3.9.4 | [deliver_report](delivery.md) / [accept_delivery](research-gates.md); fixed-only Gate proposal 36 |

## Plan compilation

`compile_m1_plan(admitted_library, policy, vocabulary) -> run_plan` resolves each symbolic rubric hash below from its admitted gate body and includes that gate's independent deterministic checks. It verifies every wire, named schema/version, complete dependency closure and allowed effects before freeze. Refuse missing/unresolved policy or rubric with POLICY_UNRESOLVED. Freeze commits all Bindings together; the generic script walks only that frozen plan. No separate hardcoded workflow contains stage behavior.

The JSON is a source template with symbolic admission hashes, not a validating runtime artifact. Published run_plan values contain only concrete hashes and pass the owning type checks. Every work output is its canonical named payload (deliver uses collection<path>); the separate Gate result is a Verification record, not a work payload.

```json
{
  "steps": [
    {
      "step_id": "source",
      "capsule_name": "research.extract_text",
      "gate_capsule_name": "research.accept_source_text",
      "inputs": {
        "intake": "launcher.intake"
      },
      "judge_inputs": [],
      "step_checks": []
    },
    {
      "step_id": "intent",
      "capsule_name": "research.compile_intent",
      "gate_capsule_name": "research.accept_intent",
      "inputs": {
        "source_text": "source.source_text"
      },
      "judge_inputs": [
        "source_text.text"
      ],
      "step_checks": [
        {
          "id": "intent_fidelity",
          "anchor": "judged",
          "target": "ports.outputs.intent_ir",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/intent_fidelity.md",
            "sha256": "<the admitted research.accept_intent's hash of this file>"
          },
          "description": "Every goal, outcome and constraint is stated in the prompt, and nothing central to the prompt is missing.",
          "author": "muk"
        }
      ]
    },
    {
      "step_id": "requirement",
      "capsule_name": "research.compile_brief",
      "gate_capsule_name": "research.accept_brief",
      "inputs": {
        "intake": "launcher.intake",
        "intent_ir": "intent.intent_ir"
      },
      "judge_inputs": [
        "intake.prompt"
      ],
      "step_checks": [
        {
          "id": "brief_objective_faithful",
          "anchor": "judged",
          "target": "ports.outputs.research_brief",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/brief_objective_faithful.md",
            "sha256": "<the admitted research.accept_brief's hash of this file>"
          },
          "description": "The objective states what the user asked for, chooses no solution, and the scope adds nothing the request did not say.",
          "author": "muk"
        }
      ]
    },
    {
      "step_id": "search",
      "capsule_name": "research.search_ideas",
      "gate_capsule_name": "research.accept_ideas",
      "inputs": {
        "research_brief": "requirement.research_brief",
        "intake": "launcher.intake"
      },
      "judge_inputs": [
        "research_brief"
      ],
      "step_checks": [
        {
          "id": "ideas_grounded",
          "anchor": "judged",
          "target": "ports.outputs.idea_set",
          "over": "outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/ideas_grounded.md",
            "sha256": "<the admitted research.accept_ideas's hash of this file>"
          },
          "description": "Every idea's summary and mechanism follow from the chunks it cites, with nothing speculative.",
          "author": "muk"
        },
        {
          "id": "ideas_answer_brief",
          "anchor": "judged",
          "target": "ports.outputs.idea_set",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/ideas_answer_brief.md",
            "sha256": "<the admitted research.accept_ideas's hash of this file>"
          },
          "description": "Every idea advances the Brief's objective and needs nothing out of its scope or against its constraints.",
          "author": "muk"
        }
      ]
    },
    {
      "step_id": "screening",
      "capsule_name": "research.select_opportunity",
      "gate_capsule_name": "research.accept_card",
      "inputs": {
        "idea_set": "search.idea_set",
        "research_brief": "requirement.research_brief"
      },
      "judge_inputs": [
        "idea_set",
        "research_brief"
      ],
      "step_checks": [
        {
          "id": "card_grounded",
          "anchor": "judged",
          "target": "ports.outputs.opportunity_card",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/card_grounded.md",
            "sha256": "<admitted gate body hash>"
          },
          "description": "Apply the independently authored card_grounded criterion defined by the stage Gate contract.",
          "author": "independent_referee"
        },
        {
          "id": "card_answers_brief",
          "anchor": "judged",
          "target": "ports.outputs.opportunity_card",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/card_answers_brief.md",
            "sha256": "<admitted gate body hash>"
          },
          "description": "Apply the independently authored card_answers_brief criterion defined by the stage Gate contract.",
          "author": "independent_referee"
        }
      ]
    },
    {
      "step_id": "hypothesis",
      "capsule_name": "research.form_hypothesis",
      "gate_capsule_name": "research.accept_hypothesis",
      "inputs": {
        "opportunity_card": "screening.opportunity_card",
        "research_brief": "requirement.research_brief",
        "intake": "launcher.intake"
      },
      "judge_inputs": [
        "opportunity_card",
        "research_brief",
        "intake"
      ],
      "step_checks": [
        {
          "id": "hypothesis_grounded",
          "anchor": "judged",
          "target": "ports.outputs.hypothesis_blueprint",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/hypothesis_grounded.md",
            "sha256": "<admitted gate body hash>"
          },
          "description": "Apply the independently authored hypothesis_grounded criterion defined by the stage Gate contract.",
          "author": "independent_referee"
        },
        {
          "id": "hypothesis_falsifiable",
          "anchor": "judged",
          "target": "ports.outputs.hypothesis_blueprint",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/hypothesis_falsifiable.md",
            "sha256": "<admitted gate body hash>"
          },
          "description": "Apply the independently authored hypothesis_falsifiable criterion defined by the stage Gate contract.",
          "author": "independent_referee"
        }
      ]
    },
    {
      "step_id": "poc",
      "capsule_name": "research.build_poc",
      "gate_capsule_name": "research.accept_poc",
      "inputs": {
        "hypothesis_blueprint": "hypothesis.hypothesis_blueprint",
        "research_brief": "requirement.research_brief",
        "intake": "launcher.intake"
      },
      "judge_inputs": [
        "hypothesis_blueprint",
        "research_brief",
        "intake"
      ],
      "step_checks": [
        {
          "id": "poc_matches_blueprint",
          "anchor": "judged",
          "target": "ports.outputs.poc_bundle",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/poc_matches_blueprint.md",
            "sha256": "<admitted gate body hash>"
          },
          "description": "Apply the independently authored poc_matches_blueprint criterion defined by the stage Gate contract.",
          "author": "independent_referee"
        }
      ]
    },
    {
      "step_id": "benchmark",
      "capsule_name": "research.run_benchmark",
      "gate_capsule_name": "research.accept_benchmark",
      "inputs": {
        "poc_bundle": "poc.poc_bundle",
        "hypothesis_blueprint": "hypothesis.hypothesis_blueprint"
      },
      "judge_inputs": [
        "poc_bundle",
        "hypothesis_blueprint"
      ],
      "step_checks": [
        {
          "id": "benchmark_protocol_faithful",
          "anchor": "judged",
          "target": "ports.outputs.benchmark_payload",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/benchmark_protocol_faithful.md",
            "sha256": "<admitted gate body hash>"
          },
          "description": "Apply the independently authored benchmark_protocol_faithful criterion defined by the stage Gate contract.",
          "author": "independent_referee"
        }
      ]
    },
    {
      "step_id": "evaluation",
      "capsule_name": "research.evaluate_results",
      "gate_capsule_name": "research.accept_evaluation",
      "inputs": {
        "benchmark_payload": "benchmark.benchmark_payload",
        "hypothesis_blueprint": "hypothesis.hypothesis_blueprint",
        "research_brief": "requirement.research_brief"
      },
      "judge_inputs": [
        "benchmark_payload",
        "hypothesis_blueprint",
        "research_brief"
      ],
      "step_checks": [
        {
          "id": "evaluation_grounded",
          "anchor": "judged",
          "target": "ports.outputs.evaluation_verdict",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/evaluation_grounded.md",
            "sha256": "<admitted gate body hash>"
          },
          "description": "Apply the independently authored evaluation_grounded criterion defined by the stage Gate contract.",
          "author": "independent_referee"
        }
      ]
    },
    {
      "step_id": "report",
      "capsule_name": "research.write_report",
      "gate_capsule_name": "research.accept_report",
      "inputs": {
        "evaluation_verdict": "evaluation.evaluation_verdict",
        "benchmark_payload": "benchmark.benchmark_payload",
        "research_brief": "requirement.research_brief",
        "idea_set": "search.idea_set",
        "opportunity_card": "screening.opportunity_card",
        "hypothesis_blueprint": "hypothesis.hypothesis_blueprint"
      },
      "judge_inputs": [
        "evaluation_verdict",
        "benchmark_payload",
        "research_brief",
        "idea_set",
        "opportunity_card",
        "hypothesis_blueprint"
      ],
      "step_checks": [
        {
          "id": "report_faithful",
          "anchor": "judged",
          "target": "ports.outputs.research_report",
          "over": "inputs_and_outputs",
          "applies_at": "node",
          "runner": {
            "ref": "rubrics/report_faithful.md",
            "sha256": "<admitted gate body hash>"
          },
          "description": "Apply the independently authored report_faithful criterion defined by the stage Gate contract.",
          "author": "independent_referee"
        }
      ]
    },
    {
      "step_id": "deliver",
      "capsule_name": "research.deliver_report",
      "gate_capsule_name": "research.accept_delivery",
      "inputs": {
        "research_report": "report.research_report",
        "poc_bundle": "poc.poc_bundle",
        "benchmark_payload": "benchmark.benchmark_payload"
      },
      "judge_inputs": [
        "research_report",
        "poc_bundle",
        "benchmark_payload"
      ],
      "step_checks": []
    }
  ],
  "launcher_inputs": {
    "intake": "intake"
  }
}
```

## Additional evidence and delivery binding

Report's trusted read-only stage-context service is specified by [Delivery](delivery.md#template-and-complete-inputs). It is bound by the runner to the current run and captures every referenced previous Observation/Verification, including non-blocking limitations. It cannot select another run or rewrite input Artifacts. Delivery receives the explicit benchmark payload as well as report and POC, so raw empirical data are not guessed from a markdown report.

Shared contracts and owner blockers are indexed in [coverage](../prd/coverage.md), [modules](../system/modules.md) and [black boxes](../system/blackboxes.md). The coder may independently build modules against provisional contracts, but must not mark the complete path accepted while a required owner decision or security platform remains unresolved.
