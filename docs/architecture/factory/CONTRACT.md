# Task contracts, format 2

A contract fixes what a run must hold to count: the engine and model under test, the workload, the arms compared, how each metric is taken and when output counts as unchanged. A task pins one contract file by its SHA-256; changing a pinned contract is refused, and a frozen contract changes only as a new version.

Format 2 (`"schema": "factory.contract/2"`) is the format for new contracts. Its schema is `jiuwenswarm/factory/schemas/contract-2.schema.json`, and `jiuwenswarm/factory/contract_v2.py` checks it. The worked example is [`star-deepseek-v2.json`](../../../jiuwenswarm/factory/contracts/star-deepseek-v2.json), the DGX Spark contract of 2026-11-20 rewritten in format 2.

Format-1 contracts keep working unchanged, so recorded runs keep the contract they ran under. Format 1 is the older JSON with `tolerance` or an `adapter` field, for example `star-deepseek-v1.json`. Format 2 runs only through the [lab manager](LAB-MANAGER.md); the factory lab queue refuses it.

## Sections

| Section | What it fixes |
|---|---|
| `contract_id`, `version`, `title`, `purpose` | Identity and the question the contract answers |
| `scope` | What the result covers and what it does not |
| `target` | The machine profile, such as `spark-gb10`, and its requirements |
| `subject` | The engine (name, source, revision) and the model (file names, sizes, digests or why they are not asserted) |
| `inputs` | Every other file the run reads, such as prompts and templates, by logical name, media type, size and SHA-256, plus `repo_path` when the file is kept here |
| `workload` | Tool, argv, environment and requests. A request names an input and carries the tool's parameters as `params`, and facts to confirm as `expect` |
| `arms` | Every configuration compared, each with a role (`baseline`, `reference`, `yardstick`, `candidate`, `combined`), the arm it derives from and every deviation |
| `measurement` | The primary metric, each metric's unit, direction and how it is taken, the protocol (repeats, order, first-request discard, cold load, quiet machine, confidence) and derived quantities with the metrics and arms they use |
| `correctness` | The output equivalence required, the reference arm and its frozen output digest, and the named checks with the arms or roles they apply to |
| `acceptance` | Plain rules for when a result counts |
| `limits` | Memory, CPUs, admission and watchdog memory, wall clock, GPU launches |
| `execution` | Who runs it: `lab_agent` (through the lab manager) or `factory_lab` |
| `revisions`, `provenance` | Changes made before freezing, and the contracts this one derives from |
| `extensions` | Anything else, under a namespace such as `spark.binding` |

## Rules that keep the format stable

- **Files are named, not located.** A contract gives a file's name, size and digest. The lab that runs it maps names to paths in its own binding, and `contract_v2.resolve` fills the placeholders `{model}`, `{model_dir}`, `{output_dir}` and `{input:<name>}`. `verify_inputs` checks each bound file's size and digest. An absolute host path anywhere outside `extensions` is an error, so one contract runs on any machine of its target profile and never exposes a home directory.
- **Everything is cross-checked.** Arm, check and request ids are unique. A `from` names a real arm. The primary metric is declared. Derived quantities use declared metrics and arms. Checks apply to arms or roles in use. Requests name declared inputs. A frozen reference carries its run and time. `contract_v2.problems` lists every failure, not only the first.
- **Equivalence uses named levels:** `byte_identical_output`, `bit_exact_tokens`, `numeric`, `distribution_exact`, `approximate` or `not_required`. They are the same levels an engine part can be described by, so an outside description of engine parts can later be compared against a contract without changing it.
- **New needs go in `extensions`, not in new top-level fields.** Unknown top-level fields are refused. Adding an optional field to a section keeps format 2. Changing what a field means needs `factory.contract/3`.
- **Freezing happens once.** `contract_v2.freeze` records the reference output digest, its run and the time once. After that the contract changes only as a version+1 file.

## Writing one

1. Copy `star-deepseek-v2.json` and change the identity, purpose and scope.
2. List the model files and every input with its digest: `sha256sum` on the committed bytes, not on a Windows checkout with CRLF line endings.
3. Declare the arms and say how each deviates.
4. Declare each metric with its unit and how it is taken, and the checks a run must pass.
5. Run `python -c "import json; from jiuwenswarm.factory import contract_v2 as c; print(c.problems(json.load(open('<file>'))))"` until it prints `[]`.
