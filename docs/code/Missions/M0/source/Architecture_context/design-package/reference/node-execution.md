# Node and Subnode Execution Contracts

**AI reference.** Field tables are the main design interface. The enclosing [Node Execution Contract field table](field-catalog.md#node-execution-contract) specifies information and ownership; implementation agents realize its interoperable representation. The [Subnode critical schema](schemas/subnode-execution-contract.schema.json) retains exact authority/dispatch fields because omissions or competing scope meanings affect trusted execution.

## Enclosing node

A node is a PRD workflow responsibility, such as Intention Compiler. Its protected contract binds external inputs/outputs, objective, requirement coverage, admitted internal CC assignments, fixed dependencies/checking profiles, maximum authority and aggregate limits. It may contain multiple work and verifier subnodes and protected gates. Fixed grouping does not synthesize a new CC.

Required information: `schema_version`, `id`, `run_id`, `node_id`, `attempt_id`, `revision`, `objective`, `requirement_ids`, `inputs`, `outputs`, `input_refs`, `required_outputs`, `evidence_obligations`, `node_limits`, `authority_ceiling`, `subnodes`, `gate_assignments`, `guard_profile_ref`, `policy_ref`, `configuration_ref`, `template_ref`. [Field meanings and consumers](field-catalog.md#node-execution-contract) are authoritative.

Subnode assignments identify role, exactly one declaration, template, prerequisites and requiredness. Templates name ports, pins and checking responsibilities before execution; internal outputs become concrete refs only after protected acceptance. The parent pins templates, not future concrete children. Child contracts point to the parent, avoiding reciprocal content-hash cycles. Frozen templates preserve future compatibility without pretending future artifacts already exist.

The node gate aggregates required internal acceptance, observed work/review, external output coverage, effective effects and combined budgets. A final metadata check does not perform another semantic interpretation. Failed internal acceptance, missing evidence or persistence failure blocks successor nodes.

## Concrete subnode

Protected binder → runner, check-plan builder and gate. One subnode binds exactly one CC; verifier assignments also have their own subnode contracts and restricted read-only authority. Work outputs receive deterministic then semantic checking; verifier output ends with mechanical validation, with no recursive verifier chain.

| Required fields | Meaning / why needed |
|---|---|
| `schema_version`, `id`, `run_id`, `node_id`, `subnode_id`, `attempt_id`, `revision`, `node_contract_ref` | Exact child identity and enclosing authority; reject swapped parent/run/attempt |
| `objective`, `requirement_ids` | Assigned obligation; fixed work uses predefined profile IDs |
| `bindings` | Exactly one admitted declaration/body/dependency/admission pin, role, effective authority and invocation limits |
| `inputs`, `outputs` | Named contract/version/required ports; concrete accepted input references |
| `input_refs`, `required_outputs` | Derived inventories matching ports, not independently authored alternatives |
| `evidence_obligations` | Required observations and checking evidence; absence blocks |
| `subnode_limits` | Bounds this CC assignment; the parent reserves separate verifier spend |
| `guard_profile_ref`, `policy_ref`, `configuration_ref`, `template_ref` | Independently owned frozen checking/authority/configuration/template identities |

Authority names `network`, `network_allowlist`, `resource_reads`, `write_roots`, `tools`. Effective authority is the intersection of admission, parent node, subnode and run policy. Empty lists grant nothing; `network: none` requires an empty allowlist. No permission pooling. Unsupported composite/merged CC dispatch remains rejected.

Bound check plans reference concrete contracts and exact inputs; contracts pin guard profiles. Runtime records identify parent and subject/producing subnode; node-level records explicitly use null subnode scope. A schema-valid CC-authored contract still has no binding authority. Implementers choose private classes, algorithms and transport routes within these constraints.

## Verification scope and version migration

The old `node-execution-contract:1.0.0` described a CC-sized assignment; it is retired from maintained examples and becomes `subnode-execution-contract:1.0.0` with explicit parent scope. The enclosing Node Execution Contract is the `2.0.0` field contract. Gate decisions and affected public field contracts use `2.0.0`; unchanged critical artifact/assessment schemas retain `1.0.0`. Resolve versions per catalog entry, never by one global assumption. Historical snapshots remain unchanged and must not be mixed with current inputs.
