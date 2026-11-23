# System Ontology

A format for describing an inference engine, the descriptions written in it so far, and the programs that check
and use them. Work in progress on the branch `ontology-development`.

The format has two description levels and one per-machine record:

| What | File kind |
|---|---|
| What is given: model, hardware, environment | `model`, `hardware`, `environment` |
| System level: one engine as a whole | `system` |
| Node level: one component, true on every machine | `component` |
| One engine on one machine | `engine_spec` |
| Reusable optimisation hypotheses, and results | `mechanism`, `workload_profile`, `evidence` |

**Status of the node level.** The component descriptions carried too much implementation detail (parameter values,
call interfaces, source line references). The revision under review defines generic node types and keeps Strata as
the worked example: `NODE-ONTOLOGY-revised.md` (draft 0.9). The checked format still uses the component
descriptions.

## Read first

| File | What it is |
|---|---|
| `EXAMPLE.md` | Worked examples: real excerpts at system level and node level, with notes on how to read them |
| `NODE-ONTOLOGY-revised.md` | The revised node level under review: 44 generic node types, Strata as the worked example, and how the draft was checked. Generated |
| `METHOD-assessment.md` | How the assessment numbers are obtained, with the throughput figure worked step by step |

## Contents

| Path | What it is |
|---|---|
| `ontology/schema.yaml`, `schema-reference.md` | Every field of every file kind; the reference is generated and includes a complete small example |
| `ontology/dictionary.yaml`, `dictionary.md` | 310 terms, one meaning each |
| `ontology/node-types.draft.yaml` | The node types, draft 0.9. Generated from the earlier draft and `validation/thin/amendments-0.9.yaml` |
| `examples/systems/strata/nodes.yaml` | Strata's node level under the node types: each part names its type and how Strata settles that type's choices. Generated |
| `validation/` | The evidence behind the node types: parts inventories of six engines, the readers' results of every check, and `criteria.yaml`, which states each check before its result |
| `ontology/metadata-alignment.md`, `unified-dictionary.*` | Names shared with the CC declaration and IR schemas of this repository; a first increment of one dictionary for both. These read `docs/architecture/design-package/reference/` and change nothing in it |
| `ontology/quantities.yaml`, `predicates.yaml`, `rules.yaml` | Registered quantities, the predicates a mechanism may use, and tables the checker reads |
| `examples/given/` | Model, hardware and environment descriptions. The Muse model's parameter counts and attention dimensions are read from the headers of the model files on the DGX Spark (`records/`); the machine's rates are measured on it. A second model description is the lower-precision file that is on the Spark |
| `examples/systems/strata/` | Strata in two levels: 9 top-level blocks, 51 components, 100 flows. `STRATA.md` is generated |
| `examples/systems/muse/` | The Muse engine as a design: 36 components derived from Strata by `_derive.yaml`. `MUSE-ON-SPARK.md` is generated. `nodes.yaml` is the same design under the node types, generated from `node-assignment.yaml`, which gives each node's type with a quote from the component's own responsibility and a pin of that text; `so_nodetypes.py example` refuses a node whose text changed since it was read (`repin` lists them) |
| `examples/systems/ds4/` | ds4, written by a task that took no part in the design, to test whether the format can be used by others |
| `examples/specs/`, `examples/knowledge/` | Engine specs, mechanisms and reported evidence |
| `validation/open-findings.yaml` | The results that are open and known, each with its result line, the reason and whose it is |
| `runs/` | Outputs (`runs/README.md` says which are current and which are superseded): the figures for the Muse model on DGX Spark (`muse-assessment-08-budget-80`, `-128`), the back-test on Strata (`strata-backtest-02`) |
| `tools/` | The programs below |

## Run everything

One command runs every step in the order the steps depend on each other, and then plants known faults in a temporary
copy to see that each is reported:

```bash
python tools/so_run_all.py
```

```bash
python tools/so_run_all.py --no-selftest
```

The first takes about ten minutes, the second about two. Each step ends as `ok`, as `open` (the tool reports
something known and recorded in `validation/open-findings.yaml`: a target the project has not finished setting, a
pass mark the stored reader answers do not meet), or as `CHANGED` or `BROKEN`. After the steps every file is compared
with what it was before: the steps regenerate files, and with unchanged inputs nothing may differ. The last line says
`RAN THROUGH` only when nothing is broken or changed, no file differs and the self-test behaves as written.

This directory can be run on its own. Three steps read the factory's design package in the repository this directory
is part of (`docs/architecture/design-package`); without it they are shown as skipped, and the two documents that
compare this vocabulary with the factory's are left as they are.

## Tools

Deterministic programs; none calls a model. Python 3.10 or later with PyYAML and jsonschema. Run from this
directory. Every tool prints English; the labels of the checker are terms of `ontology/dictionary.md`.

| Tool | What it does |
|---|---|
| `tools/so_run_all.py` | Every step below in order, the comparison of every file before and after, and the self-test |
| `tools/so_selftest.py` | Plants known faults in a temporary copy and reports any that the tools do not report; `--list` names them. It also shows two things the tools are known not to find |
| `tools/so_check.py` | `validate`; `system <id>`; `check <spec id>`; `match --model --hardware`. `system` checks names, references and structure, whether the machine has what the components ask for, and, for a derived design, that the files are what the derivation writes now. It does not judge whether a sentence is true of the engine |
| `tools/so_derive.py` | Derives a new engine's description from an existing one. Every text it writes was either written for the new engine in `_derive.yaml`, or is the source's text and is listed in `_derive.kept.yaml` as read, with the reason and a pin of the text that was read. It changes no text by itself and writes nothing when anything is wrong. `--unread` prints the source's texts that are not listed |
| `tools/so_leftovers.py` | Word patterns for what a derived description may still say about its source: the source model's numbers and features, the source machine's kinds of memory, the source engine's name, implementation identifiers, listed terms. Built from the descriptions on both sides. They find the usual wordings only; what cannot be compared is reported, not skipped |
| `tools/so_assess.py` | Figures for a model on a machine under a target's memory budget, for an engine that keeps part of the experts in memory and reads the rest from storage. It is not an assessment of a design's quality: the design contributes its node types (from `nodes.yaml`, required) and any decision that gives a number the program reads; every other figure is the same for any design (`runs/muse-assessment-08-budget-80`) |
| `tools/so_backtest.py` | Compares the memory-bandwidth upper bound with the speeds an existing engine reports, under a pass condition printed before the result; exits 1 on FAIL (`runs/strata-backtest-02`) |
| `tools/so_demo.py` | Puts one named fault into a temporary copy and prints what the checker reports, for showing one case |
| `tools/so_measured.py` | Sets what the assessment computed beside what was measured on the machine, from the records in `runs/muse-measured-*`; every verdict word is decided by the two numbers on its line |
| `tools/so_assemble.py` | Merges a system written area by area into one description |
| `tools/so_nodetypes.py` | Node types: `thin` writes the draft, `example <engine>` writes an engine's node level, `check` checks both against the dictionary and the engines examined, `doc` writes `NODE-ONTOLOGY-revised.md` |
| `tools/so_nodetypes_experiments.py`, `so_nodetypes_validate.py`, `so_inventory.py` | Inputs and scoring for the checks of the node types |
| `tools/so_intake_trial.py` | Trial of the ontology as part of a query to the Intention Compiler: assembles the query, turns a reader's quotes into spans, validates against the factory's schemas and scores what was taken up (`validation/intake/`) |
| `tools/so_docs.py` | Generates the reference, the dictionary and the system documents, and checks the vocabulary |
| `tools/spark_kit/` | Scripts to run on the target machine: memory and storage read rates (`probe.py`), a running endpoint's speeds (`measure.py`), the headers of model files (`gguf_header.py`) |

A single step can be run alone, for example:

```bash
python tools/so_check.py system sys/muse-on-spark
```

## Keep in mind

- Strata was read, not run. What is said about it on DGX Spark comes from its own document.
- The Muse engine is a design. Nothing of it is built.
- Of the assessment's figures, only the memory-bandwidth speed is an upper bound. The decode, first-token and
  cache figures are estimates that assume each token's choice of experts is independent of the previous token's,
  and they depend on the target's budget and on assumed parameters that the output lists.
- Measured by us on the DGX Spark: storage read rates and memory size, on 2026-11-13 and again on 2026-11-19; the
  figures use the later measurement. Measured by others: Strata's speeds.
- Strata's component descriptions cite `engines/strata-notes/`, the notes of facts they were written from. Those
  notes are not in this directory.
- A pass of the checks means that names, references and structure agree and that the files are what the tools
  write. It does not mean that a sentence is true of the engine, and it says nothing of whether the design suits
  the model.
- The tools were run on Windows and on Linux (a DGX Spark, on 2026-11-19), with the same result on both. Files
  whose bytes are pinned by a checksum are stored unconverted (`.gitattributes`); other files regenerated on
  another system may differ in line endings, which `so_run_all.py` does not count as a difference.
