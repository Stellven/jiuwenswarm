---
name: plan-research-workflow
description: Plan a research workflow from a request and an available capability list, with ordered steps, inputs, outputs, success criteria, and request coverage. Use for planning only, without executing the research.
---

# Plan a Research Workflow

## When to use

Use when given a research request and a list of available tools or skills
and asked to determine how the work could be carried out.
Produce a plan only. Do not invoke capabilities, run code, collect evidence,
or produce the research findings while applying this skill.

## Method

1. **Extract the requirements.** Identify the research questions, required
   deliverables, supplied materials, comparison conditions, and constraints.
   Assign short requirement IDs so the plan can show coverage explicitly.
   Keep optional improvements separate from mandatory requirements.

2. **Inventory the capabilities.** Use the supplied capability names and
   descriptions to determine supported operations, accepted inputs, outputs,
   and relevant limits. Do not invent tool arguments or assume a capability
   exists because a workflow would normally need it. If only names are given,
   use their plain meaning conservatively and flag material uncertainty.

3. **Check feasibility before sequencing.** Map each mandatory requirement
   to available capabilities and required materials. Check that outputs can
   feed subsequent inputs; matching names alone does not establish compatibility.
   Distinguish missing capabilities, missing inputs, and unclear requirements.
   If a mandatory operation has no available capability, state that the full
   request cannot be completed and name the missing operation and affected
   requirements. Do not disguise the gap as an executable step.
   If feasibility depends on unknown details, mark it undetermined and identify
   the specific information needed. State harmless assumptions explicitly.

4. **Build the supported sequence.** Order steps by their dependencies.
   Use only available capabilities for planned research actions, naming the
   capability used in each step. Include necessary preparation, analysis,
   checks, and delivery only where supported and relevant to the request.
   For comparisons, account for all requested alternatives and common
   evaluation conditions. Avoid redundant steps and unnecessary branching.
   If blocked, provide only a useful supported partial sequence, clearly labeled,
   and identify where it stops; do not imply it satisfies the full request.

5. **Specify each step.** Record its action and capability, inputs with their
   sources, concrete output, dependencies, success criteria, and requirement IDs.
   Identify inputs as supplied materials or outputs of earlier steps.
   Make success criteria observable: required evidence, completeness checks,
   validity conditions, or user-specified thresholds. Do not invent numerical
   thresholds or require a favorable research result for success.
   State what should stop or require revision if a critical check fails.

6. **Review the plan without executing it.** Confirm that every mandatory
   requirement is covered or explicitly blocked, all dependencies precede
   their consumers, every research action has a supported capability, and each
   step has an output and a check. Separate planned checks from verified facts.

## Common pitfalls

- Treating an unavailable operation as a generic “research” or manual step.
- Assuming supplied data, access, runtime support, or tool compatibility.
- Listing activities without specifying artifacts that connect the steps.
- Using “looks good” or “analysis complete” as success criteria.
- Confusing successful evaluation with proof of the desired hypothesis.
- Presenting a partial or conditional workflow as fully feasible.
- Executing a tool to resolve uncertainty when the task is planning only.

## Suggested output format

**Feasibility:** Feasible, blocked, or undetermined, with a brief reason.

**Requirements:** IDs and concise descriptions of the requested outcomes.

**Assumptions and prerequisites:** Only those that affect the plan.

| Step | Action / available capability | Inputs / source | Output | Depends on | Success criteria | Covers |
|---|---|---|---|---|---|---|

Fill the table with the ordered supported steps; omit it if none are useful.
For a partial plan, label its scope and stopping point explicitly.

**Coverage and gaps:** Identify uncovered requirement IDs, missing capabilities
or inputs, and any clarification needed to establish feasibility. State the
overall completion conditions and critical failure gates. Do not report any
step as executed or any research result as established.
