# Capability capsule field reference

**Reading level: AI reference.** [Capsules](../capsules.md) explains execution/lifecycle; [authoring](authoring.md) explains capability forms. This inventory and the [current schema](../reference/schemas/capsule-declaration.schema.json) define one reconciled format, version 1.0.0. Historical source versions remain provenance, not interchangeable current JSON.

## Meaning and required groups

Required root groups: `schema_version`, `identity`, `ports`, `needs`, `changes`, `guarantees`, `budget`, `evolution`, `coverage`.

A declaration describes a reusable capability and its pinned implementation, never a task or run. A node objective, artifact binding, effective permissions, verifier assignment and release decision belong to protected runtime records.

| Group / fields | Meaning and applicability |
|---|---|
| `schema_version` | Explicit current declaration-format version |
| `identity.name`, `version_label`, `kind`, `summary` | Stable name, implementation label, execution style and task-independent purpose. Required; summary is at most 400 characters |
| `identity.carrier.{ref,sha256}`, `body[].{path,sha256}` **or** `remote.{endpoint,version,interface_version_range,fingerprint}` | Local leaf implementation/closure or a pinned remote interface. A composite has neither and uses members/structure/wiring. Packaging/schema support is not runtime eligibility |
| Optional `identity.load_mode`, `overlays[].{kind,ref,sha256,source}` | Loading/experience layer pins; consumers must explicitly support them before use |
| Optional `identity.lineage.{parent,co_parents,relation,builder,build_trigger,context_capsules,diagnosis_inputs,builder_ref,provenance}` | Parentage and construction context; required when publishing an RSI child. Provenance identifies model, prompt and trajectory or records unavailable values |
| `ports.inputs[]`, `ports.outputs[]`: `{name,artifact_type,schema_ref,required,description,check_ids}` | Typed input/output contract, applicability and declared check association. Outputs are nonempty; port names are unique per direction |
| `needs.when[]`: `{id,check,state_source,evaluable_at,on_unknown,on_unavailable}`; optional freshness/parity | Predicate structure and availability. Unknown never silently passes; deferred checks must run at dispatch. Empty lists require applicability justification |
| `needs.external[]`: `{kind,identifier,pin}` or `{kind,identifier,floating:{purpose,role,contracts}}` | Dependency identity; pins identify captured packages/data/models/services/capsules/secrets. Floating intent is explicit and must resolve/pin under policy before governed use |
| `needs.network.{mode,direction,allowlist}` | Authorization and traffic direction are separate. Declared bridge injection does not grant direct network access |
| `needs.resources[] {resource_key,mode}`; `injects[] {service_key,interface_version_range}` | Scoped state needs and typed injected services |
| Optional `needs.model` | Tool-calling/context/modalities/family requirements; does not independently choose a model route |
| `changes.effect_class`; `effects[] {id,resource_key,op,scope,idempotent,reversibility,undo,risk,assurance}` | Declared effects, repeat safety, undo and risk. Runner intersects with policy/contract before effects; declarations grant no permission |
| `changes.provides[] {service_key,interface_version,commutative}`; `invariants[] {id,statement,check_id}` | Provided services and checked invariants, empty when inapplicable |
| `guarantees.checks[] {id,kind,target,runner,anchor,over,author,written_before_body,held_out,signal_source,owner,assurance}` | Declared checks and strength/independence; runner is pinned. Required nonempty inventory; producer-authored checks do not set mandatory runtime policy |
| `guarantees.acceptance`, `evals`, `unanchored` | Declared check IDs, evaluation suite/metric/threshold/held-out information, and explicitly unsupported claims |
| Optional `guarantees.quality.{criterion,judge,target_rate,window,min_observations}`; `exempt.{reason:generalist}` | Measured quality needs samples. Exemption is policy-controlled library eligibility, never exemption from runtime gates |
| `budget.per_call`, `enforcement`, `on_exhaust` | Required wall-time/invocation ceilings; optional token/cost/tool/iteration dimensions. Enforcement keys exactly match declared dimensions, with truthful hard/between-call/post-hoc modes. Unsupported measurements cannot be claimed enforced |
| Composite `members[] {role,decl_hash}`, `structure {type,direction,nodes,edges}`, `wiring[] {from,to}` | Exact member pins, finite DAG and typed boundary wiring. Roles may repeat declaration hashes; graph, effects and checking closure remain traceable |
| `evolution.frozen`, `notes_for_builder`; `coverage.undeclared_notes` | Contract promises, advisory builder notes and deliberate omissions. Server-side RSI allowlists/protected closure enforce mutation, not author promises |
| Optional `ext` | Namespaced diagnostic extensions with no permission or acceptance meaning |

All groups above are present; applicable optional substructures are omitted when unused, and inapplicable collections are explicit empty arrays. The schema enforces exact shape, local/remote/composite distinction and closed core. Admission checks semantic validity, supported styles, dependency closure, output/check compatibility, network/effect safety and applicability justification. Metadata never promises a future feature is implemented.

## Execution styles and consumers

Tool/code CCs execute pinned code under the runner. Agent/prompt CCs use bounded model/tool interaction through governed context. MCP/A2A adapters pin remote interfaces and use only supported authenticated effects. Composite/member metadata is future context only; M1 admission/binding rejects composite execution and internal CC dispatch. Composition and merging remain later work. Runtime verifier CCs produce assessments; deterministic domain-check CCs produce check data; neither owns release. Ordinary private helper functions remain inside the responsible CC.

Admission reads identity/closure and safety; discovery/planning reads purpose, ports and prerequisites; binding/runner uses typed contracts, effects and limits; checking reads guarantees and actual evidence; RSI reads lineage/frozen promises alongside protected profiles. Unsupported obligations block admission/binding, not silent omission.

## Reconciliation from preserved sources

The original [machine schema](../sources/capsule.schema.json), [v2.10b semantic description](../sources/capsule-semantic-v2.10b.md) and [historical policy](../sources/policy-m1.json) remain byte-identical. Current changes resolve their mismatches:

- Use one structured port vocabulary (`artifact_type`, `schema_ref`, `check_ids`) rather than competing `type/check` forms.
- Preserve structured predicates, resources/injects, service/invariant declarations and detailed effects/check ownership.
- Record network direction and authorization separately; neither is inferred from the other.
- Use explicit per-call budget dimensions/enforcement and structured generalist exemption.
- Preserve lineage, advisory notes, overlays and composition without importing obsolete source maturity labels as M1 phase commitments.
- Current required groups implement M1 boundaries; historical minimal requiredness and staged policy are not active format authority. Empty inapplicable needs must be justified; no fictitious predicate is added merely to satisfy an old profile.
- `schema_version` 1.0.0 identifies this architecture-owned format; it is not a claim that a historical v2.10b/implementation v2.11 artifact is byte-compatible. Importers must explicitly map/validate historical declarations. No blanket old-runtime compatibility is promised.

Derived declaration/contract hashes, eligibility flags, bindings, observations and gate decisions are protected/derived records. They are not author-entered declaration fields. Builder notes, coverage notes and `ext` are ignored for guarantees; canonical contract hashing must include authored port/need/effect/guarantee/budget/composition promises while excluding advisory notes, with the hashing profile pinned in runtime evidence.
