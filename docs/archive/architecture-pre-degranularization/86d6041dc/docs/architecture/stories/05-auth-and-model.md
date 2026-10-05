# Container login and a model turn

## Starting item

The installer starts the digest-pinned application container with a dedicated named CODEX_HOME volume. Desktop Codex's profile is separate. `cc/model_auth.py` calls the configured `cc/adapters/codex_auth.py` AuthProvider; device URL/code goes only to authenticated local setup. Codex writes and refreshes its own cache in the volume.

The bridge holds one exclusive persistent-profile lock. It mounts the whole home directory so the managed process can replace files atomically. The design neither watches/copies tokens between profiles nor requires copying auth.json back after each run. [Model authentication](../system/model-auth.md) owns this decision, the inspected transport reuse and downstream version/account checks.

## A production model turn

Requirement's runner handler has a reserved Observation identity and authorized inputs. Its trusted broker builds ModelCallContext and a services-v1 model_bridge_request using scope `{kind:run, run_id:R1}`, request M1, obs_id O-brief-1 and turn 1. These identity fragments illustrate fields; the full wire schema includes session, model, deadline, operation and scoped prompt reference.

| Connection | Proposed code | Item and custody |
|---|---|---|
| Skill handler → broker | `cc/runner/handlers/` → `cc/runner/broker.py` | Prompt bytes from authorized inputs; no login file |
| Broker → protected bridge | `cc/model.py` → `cc/adapters/model_bridge.py` | Closed scoped request with committed public_artifact prompt Ref |
| Bridge → Codex | Existing subscription transport wrapped by adapter | Serialized text turn, selected configured model, tools disabled |
| Bridge → authorized capture writer | Supervisor/evidence collector | Raw response bytes committed before complete result |
| Bridge → broker → handler | ModelProvider result | Same scope, committed reply Ref and payload hash; wrapper validates parsed output |

Record hash identifies the capture record; reply_content_sha256 identifies its underlying bytes. They are checked separately, not required to equal each other. The model response cannot choose the next capsule or issue a Gate PASS.

## Private calls and cancellation

RSI controller scope carries controller session/attempt and uses rsi_private capture. Oracle scope additionally pins query, TrialRef, case, arm and repeat, using oracle_private capture. No pre-Candidate call invents Candidate/run IDs. Ordinary benchmark retrieval cannot resolve these namespaces. Routing selection is run-only; private calls use their session-pinned model.

Cancel/status use distinct management request IDs and target the existing turn with the same scope/obs_id/turn. ModelProvider cancellation collects bounded remaining capture, then kills/reaps its owned transport child when needed. It never cancels desktop Codex or repeats an uncertain turn. Missing required reply capture cannot return complete.

## Failure and replacement cases

- Container recreation reuses the persistent volume under the same exclusive custody; doctor checks current auth before research.
- A second container/login writer cannot acquire the profile lock and returns AUTH_PROFILE_IN_USE.
- Refresh interruption, corrupt/revoked cache or unsupported model gives a truthful auth/model failure and explicit local recovery; no automatic personal-profile import.
- A delayed response or expired deadline retains attempted-call evidence and stops the affected step; no paid retry is inferred.
- A replacement ModelProvider/AuthProvider must preserve the common identity, capture, cancellation and custody contracts or fail readiness.
- Unrestricted tool mode is confined to the allowed experimental native worker profile. A Docker container or --yolo flag alone is not the security check.

[Environment](../system/environment.md#model-call-scope-and-private-capture) and [services schema](../contracts/services-v1.schema.json) are the request/capture authorities. Login, refresh, container locking and native cancellation behavior remain unexecuted implementation obligations.
