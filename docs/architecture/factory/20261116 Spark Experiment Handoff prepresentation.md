# 20261116 Spark Experiment Handoff prepresentation

Spark is deliberately idle for the next experiment owner. The native console is stopped and disabled, the queue worker is stopped, and the idle ai4r-spark-builder container is stopped. All 144 shared queue records are terminal. No GPU compute processes or Docker containers remain running. Models, images, caches, source worktrees and evidence were preserved.

## Access and retained state

Use existing authorized access: `ssh user2@100.105.127.48`.

```sh
export ROOT=/home/user2/software-factory-spark-20261113
export SRC="$ROOT/sources/native-workflow-integration-20261116"
export PY="$ROOT/native-workflow-service-env/bin/python"
export PYTHONPATH="$SRC:$ROOT/native-agent-dependencies-20261116"
cd "$SRC"
git status --short
git fetch cloud
```

Use `integration/native-cc-workflows` in Stellven/jiuwenswarm. Update only a clean, unused checkout with a fast-forward; another owner may have started work after this handoff. No dependency or driver installation is needed for the retained setup.

| Item | Location under ROOT |
| --- | --- |
| Completed three-prompt task/configuration | native-design-review-balanced-20261117/task.json and workflow-config.json |
| Committed STRATA checkout | native-design-review-balanced-20261117/factory/agent-workspace/strata |
| Earlier failed-warmup phase | native-design-review-20261117 |
| Shared library and source inventory | experiment-library/library.sqlite and sources.json |
| Build/GPU evidence | each campaign's factory/builds and factory/throughput-spool |
| Handouts and source/evidence archives | design-review-20261117 |
| Static console | native-workflow-live-20261116/console |
| Separate GGML dependency | sources/strata-ggml, revision 3cf03257f219afbe7334045ff7c6a06ac68c627d |

The frozen task identifies the model pack, tokenizer, baseline image and asset inventory. Preserve read-only model mounts. The native builder image is sha256:d893d61a6f641fdeb6d20ce33870868d3ffd497746531a233d988427deff7f87.

## Review existing evidence

Replay needs neither the queue worker nor a build daemon.

```sh
systemctl --user start native-cc-factory.service
curl --fail http://127.0.0.1:5175/healthz
# On your own computer, in a separate terminal:
# ssh -N -L 127.0.0.1:5175:127.0.0.1:5175 user2@100.105.127.48
```

Open `http://127.0.0.1:5175/review?run=design-review-adaptation`. Other retained graph IDs are `design-review-continuation` and `design-review`. GET/replay launches no work. Explicit graph closure records cancelled even when all leaves completed: inspect leaf completion, cleanup and scientific verdict separately.

After review, stop the console with `systemctl --user stop native-cc-factory.service` and close your own SSH forwarding terminal. The service remains disabled and will not start automatically on login.

## Prepare a fresh native experiment

The old tasks are completed and their deadlines are expired. Do not rerun their preparation scripts, reset counters or edit their contracts to obtain a new campaign. The one-off design-review preparer and older port/mission defaults are historical examples, not general native experiment launchers.

Choose a unique TASK and unused EXP directory under ROOT/experiments. Create a fresh owned checkout at EXP/factory/agent-workspace/strata using `git clone --no-hardlinks` from the retained repository, and create a new local branch at the chosen full source commit. Leave earlier task checkouts unchanged.

Author EXP/task.json using the completed task as a schema example. Review these fields before registration:

| Field | Fresh task requirement |
| --- | --- |
| task_id, objective, budget | New identity, research question, finite turns/duration and stopping rule. |
| source.subpath / pre_integration_commit | strata / the selected seed commit in the new owned checkout. |
| constraints.build_request and resources.build_request_template | New owned source path, commit and unique image tag; retain reviewed GGML/toolchain identities. Keep both copies consistent. |
| constraints.throughput_campaign and resources.throughput_policy | Same frozen comparator, suite, gates, fresh absolute deadline and total GPU allowance. Reserve confirmation capacity. |
| contract_id and nested contract.contract_id | Fresh consistent identity, with matching suite metadata. |
| resources.native_workflow_config | EXP/workflow-config.json. |
| resources.experiment_library | Shared index root and explicit admitted sources from sources.json, including the new factory.sqlite. |
| source/comparator metadata | Distinguish the chosen starting commit from the source/image used as the comparison baseline. |
| constraints.attempt_limits / allowed_effects | Explicit bounded build/lab attempts and only required effects. |
| resources.review_lineage | Remove old predecessor charges for a genuinely new campaign, or explicitly record a continuation without resetting its budget. |

The retained suite evaluates unchanged-quantization decode throughput on three prompts. A changed-quantization or different quality question needs an appropriate prospectively frozen quality gate.

Seal the selected capabilities with the existing preparer:

```sh
"$PY" -m jiuwenswarm.software_factory.cc_prepare \
  --config "$EXP/workflow-config.json" --task-id "$TASK" \
  --package "$SRC/jiuwenswarm/factory/ccs/source_workbench" \
  --package "$SRC/jiuwenswarm/factory/ccs/builder" \
  --package "$SRC/jiuwenswarm/factory/ccs/throughput_campaign" \
  --package "$SRC/jiuwenswarm/factory/ccs/evidence" \
  --grant process.exec --grant workspace.write --grant gpu.use
```

Before registration, set workflow-config.json's deadline to the same fresh absolute epoch as the task policy. The preparer refuses to overwrite an existing configuration.

Create a new session environment with FACTORY_HOME=EXP/factory, FACTORY_WORKSPACE=EXP/factory/agent-workspace, FACTORY_TASK_ID=TASK, FACTORY_PYTHON and FACTORY_HOST_PYTHON set to PY, and JIUWENSWARM_DATA_DIR=EXP/factory/agent-data. Keep the PYTHONPATH above. Set SIMINFENG_ROOT to /home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source, JOBQ_DIR to that directory's sibling jobq, JIUWENSWARM_SKIP_DOTENV=1, and empty DOCKER_PREFIX/DOCKER_CMD_PREFIX. Save public absolute paths in EXP/service.env; do not copy credentials into it. Use your own approved factory authentication/profile.

## Start one worker and execute the new approved task

Inspect `nvidia-smi`, `docker ps` and the shared queue's job-*.json states first. Coordinate with the current owner if jobs are queued/running. Check for an existing worker with `pgrep -af '[l]ab-source/bin/jobq worker'`. Start exactly one worker in a dedicated foreground terminal:

```sh
JOBQ_DIR=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/jobq \
  /home/user2/rsi-expert-streaming-001/factory-env/bin/python \
  /home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source/bin/jobq worker
```

This is the existing shared worker, not another scheduler. For a build that needs the retained named buildx builder, bootstrap it on demand with `docker buildx inspect ai4r-spark-builder --bootstrap`; it is unnecessary for evidence review.

After reviewing the new task/config and loading the new environment:

```sh
"$PY" -m jiuwenswarm.factory.cli --home "$EXP/factory" init "$EXP/task.json"
"$PY" -m jiuwenswarm.factory.cli --home "$EXP/factory" auth-status
# If signed out, use the login command interactively with your approved account.
"$PY" -m jiuwenswarm.factory.cli --home "$EXP/factory" run "$TASK" \
  --grant process.exec --grant workspace.write --grant gpu.use
```

The last command launches real admitted work. resources.native_workflow_config selects the native workflow front door. The controller waits for durable jobs; the agent collects the same graph's results. Use strata-candidate-cycle for the collected builder-result-to-screen edge, and strata-independent-confirmation with an explicit binding to that builder result for unchanged-candidate confirmation.

For a new task's UI, leave the historical console service stopped and run this in a separate terminal with the new environment:

```sh
"$PY" -m jiuwenswarm.software_factory.cc_server \
  --config "$EXP/workflow-config.json" \
  --static "$ROOT/native-workflow-live-20261116/console"
```

Use port 5175 only. The retained user service still points to the historical review config, not your new task. CLI status works without a console: `"$PY" -m jiuwenswarm.factory.cli --home "$EXP/factory" status "$TASK" --json`.

## Reuse and close

Search for reusable-strata-f5075a16 or reusable-strata-84864456. The records identify optional source starting points, published branches, exact commits, patches and measurements. See [reusing experiments](<20261116 Reusing Factory Experiments prepresentation.md>) and experiments/20261116-strata-candidates.json. A missed gate preserves research value; reuse does not imply acceptance or inherited authority.

At the end, stop/collect the owned workflow through its native API. If interrupted, use the task's cancel command and reconcile results. Stopping a console/controller alone does not cancel durable jobs. Wait for owned attempts to be terminal, containers absent and cleanup complete. Inspect the whole shared queue before stopping its worker with Ctrl+C. Preserve failures, commits and evidence; include the new store in the next session's admitted library inventory.

Once the queue is drained, stop the console, stop the foreground worker, run `docker buildx stop ai4r-spark-builder` if it was started, and close your own tunnel. Verify no GPU compute processes or owned containers remain. Do not prune images/volumes, delete assets/evidence, rewrite history or drop host caches as routine cleanup.

Shared Docker, SSH/Tailscale, desktop graphics, model/auth services and pre-existing interactive Codex sessions were left intact. They are outside this campaign's process ownership. Any new owner should check the live machine rather than treating this dated idle snapshot as a reservation.
