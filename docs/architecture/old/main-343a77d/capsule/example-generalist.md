---
type: capsule
tags: [capsule, example, generalist]
---

# A complete example: `generalist.codex` (agent_template)

[Declaration](fields.md) defines every field. [The generalist](generalist.md) is the low-trust, do-anything capsule: broad action space, little defined behavior, used when the planner and binder have no admitted capsule that fits a step. This page shows one complete example that follows the schema.

There is no `any` port type and no way to leave `changes.effects` empty while still claiming the least reversible effect class. A generalist still has to declare something, even when that something is deliberately as wide as the schema allows. This page shows what that looks like filled in, not left blank.

## The Declaration

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "generalist.codex",
    "kind": "agent_template",
    "remote": {
      "endpoint": "harness://codex",
      "version": "0.144.4"
    },
    "owner": "muk",
    "tags": ["generalist", "fallback", "low-trust"],
    "summary": "Fill a run step that no admitted capsule fits, by writing and running a script in the sandbox, so the run continues instead of failing."
  },
  "ports": {
    "inputs": [
      {
        "name": "step_input",
        "type": "json",
        "required": true,
        "description": "Whatever the step at hand provides. Not fixed in advance.",
        "value_schema": {
          "uri": "schemas/any.schema.json",
          "sha256": "ac4fc69238d3987433e7a89ac27363cd1b477511d4391cf80cc664e79aad8a97"
        }
      }
    ],
    "outputs": [
      {
        "name": "step_output",
        "type": "json",
        "check_id": "output_matches_step_schema",
        "description": "Whatever the step at hand asks for. Not fixed in advance.",
        "value_schema": {
          "uri": "schemas/any.schema.json",
          "sha256": "ac4fc69238d3987433e7a89ac27363cd1b477511d4391cf80cc664e79aad8a97"
        }
      }
    ]
  },
  "needs": {
    "when": [],
    "external": [],
    "network": "both"
  },
  "changes": {
    "effect_class": "irreversible",
    "effects": [
      {
        "resource_key": "workspace:*",
        "scope": "run",
        "idempotent": false,
        "reversibility": "none",
        "undo": "Not knowable in advance. The step it fills decides what actually happens."
      }
    ],
    "state_kind": "session"
  },
  "guarantees": {
    "checks": [
      {
        "id": "output_matches_step_schema",
        "anchor": "deterministic",
        "target": "ports.outputs.step_output",
        "over": "outputs",
        "applies_at": "both",
        "runner": {
          "ref": "checks/generalist_checks.py:is_json_value",
          "sha256": "92f2da29d05a7d52cd18468d074aa180503cb8e31945bb4a79af8ea29d7f0b1e"
        },
        "description": "The output parses as JSON and matches the port's declared value_schema. The step's own checks, applied at the gate, are what really judge it.",
        "author": "muk"
      }
    ],
    "failure_modes": [
      {
        "reason_code": "GENERALIST_STEP_UNFILLABLE",
        "when": "The sandboxed script cannot produce output matching the step's ports within budget.",
        "retriable": false
      }
    ]
  },
  "evolution": {
    "rsi": "none",
    "notes": "Weights and behavior are fixed. This capsule improves only by more admitted capsules existing for it to defer to, never by RSI changing it."
  }
}
```

## Why every field is this wide, not narrower

- **`ports` are `json`, not a domain type.** There is no `any` or `unknown` port type. Rule `no_any_type` forbids it. The way to declare "could be anything" is a `json` port with a `value_schema` that itself accepts anything, `{}`. It is still pinned by hash, so it cannot quietly change under this `decl_hash`. It just says "anything" instead of something narrower.
- **`changes.effects` cannot be empty here.** Rule `effect_class_matches_effects` ties the two together: with no declared effects, only `pure` or `read_only` is allowed. To honestly claim `irreversible`, at least one effect with `reversibility: none` is required. The one here, `workspace:*`, is deliberately broad. It stands for "we do not know what this touches," not for one specific path.
- **`needs.network` is `both`.** The generalist may need to read or write over the network, depending on the step. There is no narrower honest answer.
- **`evolution.rsi` is `none`.** `generalist.md` says its weights are fixed and it improves only by more admitted capsules existing for it to defer to, never by changing itself. `none` is not caution here. It is what the capsule actually is.

## Why this is `generalist.codex`, not just `generalist`

[`generalist.md`](generalist.md#any-agentic-system-with-no-new-kind-and-no-use-of-role) covers this. Codex, Claude Code, and openJiuwen's own agent are each their own Declaration, not one Declaration that flexes at run time. `identity.remote` pins one harness and one version, because a harness cannot be hashed as a file the way code can. A sibling capsule, `generalist.claude_code`, would have the same shape as the one above, differing only in `identity.name` and `identity.remote`. "The generalist can go to any agentic system" is Symphony's selection picking among however many of these are admitted, not one capsule silently switching harnesses underneath a fixed `decl_hash`.

No new `capsule_kind` and no new use of `Binding.role` were needed for this. `kind: agent_template` already covers how the runner calls it, whichever harness backs it.

## Level, and where it is not written

This capsule's trust level is `exempt`. That is not a field in the Declaration above. `trust.md` is explicit: level is written by admission into the [Verdict](../schemas/verdict.md), and `exempt` is granted by naming the capsule in the policy, not by the capsule declaring itself untested. Nothing here says `exempt`. The policy does.

## One gap this example does not paper over

`generalist.md` says it is enrolled on checks that it "refuses a protected write." That is a check about the call's behavior, not about the value of `step_output`. The schema does not document what `Check.target` should be for a check with `over: each_call`, the shape used for behavioral checks like this one. The one check in this Declaration is the mechanical shape check only. The behavioral enrollment check `generalist.md` describes is not expressible here yet, not because it was left out by choice, but because the syntax for it is not written down anywhere in the current schema.
