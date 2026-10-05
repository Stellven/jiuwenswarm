---
id: arch.standards
type: standard
level: present
status: draft
version: 1
provides: [arch.standards]
depends_on: [README.md, terms.md, contracts/principles.md]
prd: []
prd_note: authoring standard for this library
tags: [standards, format, presentation]
---

# Page format standard

Every page has the same bones, so a reader (or a coding agent) always knows where to look, and pages look good on screen and in slides. `python _tools/check_format.py` [checks](capsule/fields.md#term-check) this standard.

## Every page

1. **Front matter:** `id`, `type`, `level` (`present` or `detail`), `status` (`draft`, `checked`), `version`, `provides`, `depends_on`, `prd` (clause numbers) and `prd_note` when `prd` is empty.
2. **H1** is the first heading. Under it, in this order:
   - `PRD: 3.2, 4.7.1` (clause numbers, same as front matter),
   - `> Answers: <the one question this page answers>`.
   Generated and standard pages (types `generated`, `index`, `standard`) are exempt from the `PRD:` and `Answers` lines; the `PRD:` line is also left out where `prd: []`.
3. **One home per fact.** If it is defined elsewhere, link it. Do not copy tables.
4. **Links** are relative. Every link and anchor must resolve.
5. **Status words** are the ones in [terms](decisions.md#key-terms). Unknowns are `PENDING_SOURCE` or `PENDING_DESIGN` and are listed in [decisions](decisions.md#open).
6. **No names of people or teams.** No "owner", "owns" or "maintainer". Say where a fact is defined, where it lives and who decides.
7. **Names** are working names ([naming note](README.md)).

## Page types and required sections

| `type` | Used for | Required `##` sections, in order |
|---|---|---|
| `present` pages (`home`, `design`, `plan`, `ledger`, `stories`) | what we show | at least one diagram or table before any prose over 5 lines; a closing line linking the detail pages |
| `capability` | one CC | What it does; Where it sits; [Declaration](capsule/fields.md#term-declaration); Checks; Tests; Acceptance seeds |
| `gate-profile` | a [GateProfile](schemas/profiles.md#term-gateprofile) of the shared verifier | Criteria; Acceptance seeds |
| `module` | an [ordinary module](capabilities/README.md#term-ordinary-module) (not a [capsule](capsule/capsule.md#term-capability-capsule)) | What it does; Interface; Tests; Acceptance seeds |
| `module-spec` | one or more [blocks](system/modules.md#term-block) in [modules](system/modules.md). Done when its [V rows](system/test-surfaces.md#term-v-row) pass | Purpose; Interface; Behavior; Failure; Tests |
| `type` (payload) | one [payload type](types/types.md#term-payload-type) | fixed by the type generator (Fields, Type checks, Example) |
| `reference` | background, benchmark and fixture guidance | none |
| `index`, `generated`, `standard` | indexes, generated pages, standards. Exempt from the `Answers` and `PRD:` lines | none |

Meaning of the section names:

- **What it does:** plain words, 3 to 6 lines.
- **Where it sits:** flow node, input and output types (linked), [Gate](verification.md#term-gate) profile, build step.
- **Declaration:** the Declaration JSON, abridged to the fields that matter.
- **Checks:** a table: check, source, meaning.
- **Interface:** the messages and APIs, each with a `Schema:` line linking the def (`execution-v1.schema.json#runner_request`). No message without a def.
- **Behavior:** ordered [phases](system/lifecycle.md#term-phase) or a small table. A diagram if more than 4 [steps](system/nodes.md#term-step).
- **Failure:** a table: situation, outcome, recovery.
- **Tests:** what is checked and with which fakes. Links to V rows in [test surfaces](system/test-surfaces.md).
- **Acceptance seeds:** table with stable ids `cap.<page>.AC-nn`, source clause or story, observable criterion, level (BLOCK, [BOUNDARY](v-model.md#term-boundary), [SYSTEM](v-model.md#term-system)).

## Writing style

- Plain technical English. Short sentences. Active voice. One idea per sentence.
- Define a term once, in [terms](terms.md). Use it the same way everywhere.
- Prefer a table or a numbered list to a paragraph. Present pages use tables of at most 5 columns. Wide reference matrices (for example schema or boundary tables) are allowed on detail pages.
- Say what happens, then why. Use "must" only for rules we check.
- Numbers carry units. Times are UTC.
- Present pages: at most about 150 lines. Detail pages: at most about 300, unless generated.

## Diagram style

- Mermaid only, ASCII only, no semicolons in labels. One idea per diagram, at most about 25 [nodes](system/nodes.md#term-node).
- Direction: flows go top to bottom, call maps go left to right.
- Shared classes (copy the block):

```text
classDef cc fill:#FFF1D6,stroke:#B86E00,color:#172D45;
classDef gate fill:#EEE4F6,stroke:#754A91,color:#172D45;
classDef halt fill:#FBE3E3,stroke:#B03030,color:#172D45;
```

- Orange = capsule, purple = Gate, red = halt. Dotted line = optional or derived. Label every edge with the data or action.
- A diagram never holds a fact that is not also in a table or text on the same page.

## Messages and fixtures

Follow [message design principles](contracts/principles.md). Each boundary between modules has a generated [boundary sheet](contracts/boundaries.md) with a valid and a rejected example.

## V model

Every design page has a paired test level ([v-model](v-model.md)). A capability, Gate profile or module page that defines behavior has [acceptance seeds](system/test-surfaces.md#term-acceptance-seed). A module-spec page is done when its V rows in [test surfaces](system/test-surfaces.md) pass; it needs no acceptance seeds. A page that defines a message has [boundary sheets](contracts/principles.md#term-boundary-sheet). V levels: BLOCK is unit, BOUNDARY is integration, SYSTEM is system and acceptance.

## Slides and PDF

Present-level pages are the slide source. Keep each page's first screen to: title, `Answers` line, one diagram or table. `_tools/build_pdf.py` builds the PDF from those pages.
