# CC declaration: the shared authoring format

## Intent and status

Describe one capability once for use in many nodes. Runner changes should not require reauthoring capsules. This conceptual authoring interface precedes a released machine-readable format.

Retain the previous declaration's useful group names. Its archived JSON schema includes deferred mechanisms and is not active. The owning CC task publishes a versioned format following these boundaries.

## What an author declares

| Group | Meaning to preserve |
|---|---|
| `schema_version` | Which released authoring format the declaration uses |
| `identity` | Stable capability identity, version, provenance, execution form, and implementation reference |
| `summary` | What the capability does, in plain language, independently of a particular workflow |
| `ports` | Named inputs and outputs, their meaning, and references to their data contracts |
| `needs` | Preconditions, dependencies, tools, packages, resources, and requested access |
| `changes` | What state or resources the capability may modify, and whether repetition is safe |
| `guarantees` | Promises callers may rely on, with checking hooks where useful |

Distinguish known-code tools from model/skill-backed capabilities using the existing harness. Implementation references identify actual code or skills; runs record exact versions. Compute hashes and other bookkeeping rather than making authors fill them in.

Ports establish shared input/output meanings and reference task-owned data formats. Explain stable public interfaces; let the owning agents define temporary formats between private steps. Do not embed every schema in the declaration.

Needs include dependencies on internally called CCs. Those calls use the CC runner within the parent's scope. Run policy grants access and limits; declarations cannot grant permission. Changes make effects explicit so orchestration can judge whether correction or resumption may safely repeat them.

Guarantees describe the capability's responsibility. A checking hook does not imply a separate verifier CC must run after every invocation. Distinguish checks useful when developing a capsule from checks required for a live result. Verification selection for an invocation belongs to fixed-stage configuration or the frozen plan.

## What belongs elsewhere

| Fact | Owner |
|---|---|
| This run's objective and constraints | Accepted requirements contract |
| Node dependencies, concrete inputs, verification attachments | Fixed pipeline configuration or frozen DAG |
| Allowed permissions, execution limits, repair policy | Run configuration and orchestration |
| Attempt status, model calls, outputs, verification results | Runtime records |
| Detailed acceptance conditions and test procedures | Owning Spec Kit artifacts |

Keep provider credentials and model-routing policy out of declarations. Do not require RSI metadata for this stage. Do not turn the declaration into a copy of task state or the whole plan.

## Example in words

A POC builder takes an accepted hypothesis, baseline code, and constraints. It produces intervention artifacts using scoped tools. It may change the POC workspace, not the hypothesis. The workflow assigns verification before benchmarking.

A benchmark executes baseline and treatment and produces measurement evidence. Its declaration makes repeat execution visible as an effect. A successful process exit does not prove the hypothesis.

## Compatibility

Keep released meanings stable. Compatible extensions should not require reauthoring; breaking changes need a version and migration. Explain unsupported declarations rather than silently reinterpreting them. The owning task decides validation and serialization and reconciles field names with the PRD before release.
