# The released Intent and Requirements stages, run on four queries (2026-11-19)

Until this day the intake trials (`../A`, `../B`, `../C`) were played by Claude subagents that followed the design
pages. These are runs of the factory's own released stages.

## What was run

The repository's portable capsule runtime (`jiuwenswarm/capsule_runtime`), which runs the released Intent stage
(`research.intent`, m1-8) and Requirements stage (`research.requirements`, m1-9) outside the pipeline: the pinned
prompts, the product's deterministic checks and its semantic verifier. On Windows, from the repository root.

- Model for the worker and for the verifier: `gpt-6.1-sol`, reasoning effort `medium`, the product's fixed model and
  effort (`jiuwenswarm/research/fixed_subscription.py`), called through the Codex command line the way the
  repository's benchmark harness calls it (`codex_call.py`).
- Time allowed: the wall time each stage declares, 420 s for Intent and 180 s for Requirements. Within it
  `run_stage.py` gives the model command 415 s and 175 s, and the Codex call 410 s and 170 s.
- Queries A, B and C are the stored queries of the earlier trials, byte for byte. D is new: the request of C with
  the files as they stood on the morning of 2026-11-19 (the target with the bench owner's answers, the model files
  the bench runs, the machine, the Muse design's system level and node level). A few sentences of the design were
  corrected after the runs.
- The request says what to do with the files. Every request ends "Take them as the statement of what is wanted", and
  those of C and D say the files describe "the engine itself at two levels: the system as a whole and its nodes".
  What the stage did with the files may follow from that wording. No other wording was tried.

## What this is not

- Not the product. The full product starts only on Linux, in its container, with a signed-in subscription and an
  operator configuration, and it has no way to stop after the compiler. Not exercised here: the run store, the
  gates, the release of a node, uploads and document extraction.
- One call per stage. The product asks the model once more after an invalid reply; the portable runtime does not.
- The worker and the verifier are the same model through the same command; the product requires them independent.
- The prompt is joined as the portable runtime joins it, not inside the product's payload tags.
- Each Intent was run twice (`round2/` holds the second run); D three times, because its first run was rejected and
  was repeated at once. The Requirements stage was run once, on the Intents of the first run.

## Files

| File | What it is |
|---|---|
| `intent_in_<Q>.json` | The request and the attached files, as given to the runtime |
| `intent_<Q>_result.json`, `requirements_<Q>_result.json` | The runtime's result: the output when delivered, and the receipt with the checks, the verifier's findings and the checksums of the model calls |
| `rejected_intent_<Q>.json`, `rejected_intent_D_repeat.json`, `round2/` | The second run of every Intent, and for every rejected Intent what the worker had replied. A rejected reply is not an output of the stage |
| `rejected-replies/` | The same replies of the first run as the model wrote them, and B's rejected Requirements reply |
| `codex_call.py`, `run_stage.py`, `analyse.py` | How the model was called, how a stage was run, and how the results were counted. Paths of the machine they were run on are replaced by placeholders (`<user>`, `<work>`), so they do not run as they are |

The prompts and replies of every model call are kept outside the repository. On 2026-11-23 the machine paths inside the
stored results were replaced by placeholders; the checksums recorded inside the receipts were computed over the
original text and no longer match it.

## What came out

The table and the points below are the first run. The second run follows them.

| | A: target, model, machine | B: A and the 44 generic node types | C: A and the Muse design at two levels (the version of the earlier trial, before it was derived again on 2026-11-18) | D: as C, files of 2026-11-19 |
|---|---|---|---|---|
| Intent: checks | pass | pass | pass | **rejected, twice** |
| Intent: verifier | accepted | accepted | accepted | not reached |
| Readiness | needs clarification | needs clarification | needs clarification | (reply: needs clarification) |
| Uncertainties, blocking | 10 of 10 | 12 of 12 | 10 of 10 | (replies: 7 of 7, 7 of 8) |
| Requirements | delivered | **rejected by a check** | delivered | not run |
| Brief: mandatory requirements, constraints, targets | 3, 3, 0 | | 5, 7, 1 | |
| Brief: unresolved, blocking | 10 of 10 | | 10 of 10 | |

- **The verifier's verdict on every delivered output is `PASS_WITH_KNOWN_LIMITATIONS`**, for the Intents and for the
  two Briefs. The limitation it states: in this runtime it is given the output and not the contents of the files the
  output refers to.
- **Every run says needs clarification.** In A all ten blocking uncertainties are items the target file marks
  `UNSET` (seven) or `status: proposed` (three). The stand-in readers of the earlier trials had called A and B ready.
- **B: none of the 44 node types is used.** The file appears once, as one entry of context, with a quotation of its
  first 435 characters. The same as in the earlier trial.
- **C: the engine description is used, as a source of uncertainties and of scope.** Six of the ten uncertainties
  draw on it: the conflict between the model (8 of 256 experts) and the node that still said 10 of 512; the conflict
  between the first-version exclusions and inherited parts; an HTTP front in the design while the target leaves the
  form unset. The system level's coverage sentence became a mandatory requirement and two out-of-scope items of the
  Brief. No node became a constraint or a target.
- **D: rejected for a quotation position.** Both replies give a quotation that ends beyond the end of a file
  (`target.yaml` 0 to 9,000 of 8,420 characters; `machine.yaml` 0 to 1,800 of 1,770). The contradiction of C is gone
  from the replies; both name the unchosen memory budget and 128 GB against 127 GB allocatable. The first also names a
  sentence of the design that still said the experts are three times the machine's memory (corrected since).
- **Most quotations are coarse.** Of the 43 positions the three delivered Intents give in attached files, 34 start
  at character 0 and 27 end at a multiple of ten. The 9 that start inside a file are all in C's `target.yaml`. The
  check accepts any position inside the file; it does not compare the quoted text with the entry. So for most
  entries the quotations do not show which sentence the entry rests on, and the counts of cited characters say
  little.
- **B's Requirements was rejected** by the check of target comparisons: the Brief made the context length a
  mandatory quantitative target while the target file gives it no value.

## The second run

| Query | First run | Second run |
|---|---|---|
| A | delivered: needs clarification, 10 of 10 blocking | rejected; the reply says needs clarification, 10 of 10 blocking |
| B | delivered: needs clarification, 12 of 12 blocking; node types cited once, as context | delivered: needs clarification, 8 of 9 blocking; node types cited once, as context |
| C | delivered: needs clarification, 10 of 10 blocking; 2 conflicts | rejected; the reply says needs clarification, 12 of 15 blocking; 5 conflicts |
| D | rejected, twice | rejected |

- Of the nine replies of the Intent stage, five were rejected and four delivered. Every rejection has the same
  cause: a quotation that ends beyond the end of a file (`machine.yaml` 0 to 1,800 or 1,900 of 1,770 characters;
  `target.yaml` 0 to 4,228 of 4,120, or 0 to 8,800 or 9,000 of 8,420). Which query is delivered changed from one run to
  the next, so a single run of this stage on these inputs says little about whether it will go through.
- What repeats in all nine replies: the request needs clarification. In both runs of B the node types are cited
  once, as context. In both replies to C the conflict between 8 of 256 and 10 of 512 experts is named; none of the
  three replies to D names it. All three replies to D name the unchosen memory budget and 128 GB against 127 GB; two
  of them name the design's sentence on three times the machine's memory.
- What does not repeat: the number of uncertainties (7 to 15), and whether any entry other than context and scope
  cites the engine's description. In one rejected reply to D a constraint cites the node level.

