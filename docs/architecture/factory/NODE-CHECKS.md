# Node checks

Every node of the task graph is verified before it can close. Each output gets its own check, as in M1, where a node has one verifier subnode per output. The checks are cheap. The agent that did the work never approves its own change: an independent reviewer with a separate context does that.

Code: `jiuwenswarm/factory/node_check.py`. Agent-facing capsule: `ccs/node_check/` (`factory.node_check`, with `start` and `status`). Where this fits: [INTEGRATION.md](INTEGRATION.md).

## Where a node's checks come from

- **A node planned from a node contract** ([NODE-CONTRACTS.md](NODE-CONTRACTS.md)) checks the outputs that contract declares, one verifier each, with the contract's criteria.
- **A hand-written node** may carry `check: {verifier, stage, review}`. This means one `diff` output named `change`. Alternatively it may carry `check: {outputs: [...]}`.
- **A task** may set a check for every node of a kind with `constraints.node_checks`, so the agent cannot leave it off.

A node's checks are fixed once the node exists.

## The done rule

A node with checks becomes done only when it cites, for every required output, that output's **latest** `node_check` observation, and that check:
- has finished,
- passed, and
- used the same settings.

A newer failing check replaces an older pass. When job reconciliation finds a checked node's job has succeeded, it marks the node blocked, not done, until its checks pass.

Only the host writes `node_check` observations. The agent's scoped store refuses that kind, and refuses ids that contain `:`.

## How each output kind is checked

| Kind | How it is checked | Speed |
|---|---|---|
| `diff` | The host runs the capsule's own `verify` on the exact change, up to the required stage. Then, if asked, the independent reviewer looks at it | Seconds for the verifier; one model call for the review, in the background |
| `evidence` | The cited records must exist. If the output asks for review, the reviewer reads those records | Immediate; review in the background |
| `source_bundle` | Each named lab source bundle must be stored and intact, and readable as `factory.lab-source/1` | Immediate |
| `image` | A successful build attempt of this task whose receipt names the image | Immediate |
| `lab_request` | A request composed from this node and sent through the lab manager, whose lab task covers the node's arms, checks and metrics | Immediate |

**For a diff:**
- **Uncommitted work** is the checkout's staged, unstaged and untracked changes against `HEAD`. The verifier reads them in the checkout itself. The host refuses the check if the commit or the working diff changes while it runs.
- **A patch file** (`diff_path`) is checked against the checkout it applies to.
- **Review comes last:** the reviewer runs only after the verifier passes, so failing work costs nothing to review.

**Caching:** a check of the same work, settings and reviewer returns the earlier result. If a different check ran in between, the earlier result is recorded again so that it becomes the latest.

## The independent reviewer

The reviewer works like a code reviewer: someone other than the author. It does not need a capsule. The node's objective and criteria are enough, and the capsule's method makes the review sharper when there is one.

- **What it reads:** only a packet, holding:
  - the task objective;
  - the node's step: id, kind, objective, requirement ids and the output;
  - the output's criteria;
  - the method, validation and guide materials of the first helpful capsule that has them, each truncated at 24 KB;
  - the verifier's checks;
  - the diff (truncated at 120 KB, and recorded when that happens) or the cited records.
- **What it never sees:** the building agent's conversation, decisions, hypotheses, notes or session log.
- **How it runs:** in its own process, as a fresh, ephemeral session in an empty temporary directory, with no factory or agent environment variables.
- **What it returns:** JSON with a `verdict`, a `summary` and `findings`. Each finding has a severity of `blocker`, `major` or `minor`.
- **How the host turns that into pass or fail:**
  - a `fail` verdict fails the check;
  - so does any blocker finding, even when the verdict is `pass`;
  - so does a reply that doesn't match the schema.
- **What is kept:** the exact packet and the reply are stored as artifacts.

**Choosing the reviewer.** The host uses the first of these that is set:
1. `FACTORY_REVIEW_CMD`, a command that reads the prompt on stdin;
2. `FACTORY_REVIEW_OPENAI_BASE_URL` with `FACTORY_REVIEW_MODEL`, for any OpenAI-compatible endpoint, with the key in `FACTORY_REVIEW_API_KEY`;
3. the `codex` CLI, run as `codex exec --ephemeral -s read-only` with the review schema. `FACTORY_REVIEW_MODEL` picks the model.

A different or cheaper model than the builder's is a good choice.

## Tested on the DGX Spark

One real node check ran on the Spark. It checked the expert weight cache diff from the 2026-11-20 demo (direct seed, 6 files, about 49 KB) on stock llama.cpp `9048bad`. It used the real `engine.build_expert_weight_cache.verify` and a fresh Codex reviewer. A second copy had a planted bug: a bounds check replaced by `return true`. The results are in the PR description.

## Limits

- **The reviewer gives an opinion, not a proof.** The host makes its verdict binding, but it can miss bugs or flag false ones.
- **The reviewer can read the filesystem.** It is never given the builder's context, but its read-only sandbox still lets it read files. Run it as another user or in a container if that matters.
- **Large diffs are reviewed in part.** A very large diff is truncated, and the record says so.
- **The lab does the expensive checks.** Real-model parity and speed come after the deliver node.
