# Node check

A node of the task graph is done only when every required output has passed its check.

- **Where the checks come from.** A node planned from a node contract checks the outputs that contract declares: one verifier per output. A hand-written node may carry a `check`, and the task may set `constraints.node_checks` for a kind of node.
- **Seeing what each node owes.** `factory.evidence.plan_next` lists each node's outputs, their criteria and how each is checked.

## Steps

1. **Produce the output.** Finish the change in your checkout, make the build, or send the lab request.
2. **Start its check.** Call `start` with `node_id` and `output`. You can leave out `output` when the node checks only one output. What else to pass depends on the output's kind:
   - **`diff`:** the `checkout`. Pass `diff_path` only when the change is a patch file rather than the checkout's uncommitted work. Pass `verifier_inputs` for extra verifier inputs, such as `env_gate` or `markers`. The check runs in the background, so read `status` on a later turn.
   - **`source_bundle`:** `refs: {"artifact_ids": [...]}`, the stored bundles from `factory.lab_manager.source_bundle`.
   - **`image`:** `refs: {"build_attempt_id": ..., "image_id": "sha256:..."}`.
   - **`lab_request`:** `refs: {"request_id": ...}`, a request composed from this node with `node_id` and then sent.
   - **`evidence`:** `refs: {"evidence_ids": [...]}`.

   Only diffs run in the background. The other kinds are checked at once.
3. **Mark the node done.** Do this when every required output has passed. Cite each passing check's `obs_id` in `evidence_ids`.
4. **If a check fails,** read the reason, the verifier's failed checks and the reviewer's findings. Fix the output, then check it again. A newer check replaces the older one.

## What the host does

- **For a diff,** the host:
  - runs the capsule's own `verify` on the exact change, through the capsule host, which seals the capsule and checks its digests;
  - requires a pass up to the stage the node asks for;
  - runs an independent reviewer, if the output asks for review, but only once the verifier has passed.
- **What the reviewer reads.** It reads only:
  - the step and its criteria;
  - the capsule's method, which is optional: the criteria are enough on their own;
  - the verifier's checks;
  - the diff.
- **What the reviewer never reads:** your conversation, decisions or notes. A blocker finding fails the check.
- **For builds, lab requests and evidence,** the host checks the records:
  - the bundle is intact;
  - the build receipt names the image;
  - the lab request came from this node and covers its arms, checks and metrics;
  - the cited records exist.

## Limits

- **Real-model tests are the lab's job.** Nothing here runs the real model or measures speed.
- **The reviewer's judgement is not a proof.** It is advice that the host makes binding.
