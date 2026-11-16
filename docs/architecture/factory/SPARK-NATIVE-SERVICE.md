# Native factory service on Spark

The operator authorized GPU qualification and conditional live cutover on
2026-11-16. Qualification passed and the native service is active; see the
[qualification record](qualifications/20261116-spark-native.json).
Multiworkflow composition remains workflow-team owned. Native CC
contracts and Lab Manager retain admission, job identity, resource cleanup and
independent evidence collection. The console does not introduce another scheduler.

## Service

`python -m jiuwenswarm.software_factory.cc_server --config CONFIG --static CONSOLE`
serves the native workflow console and API on loopback port **5175**. It rejects
remote operator API calls and does not trust forwarded client addresses. Use an
SSH tunnel for remote access:

```sh
ssh -N -L 5175:127.0.0.1:5175 user2@100.105.127.48
```

Open `http://127.0.0.1:5175`. The subsequent goal-driven campaign scopes the live
console to run `throughput-goal`; see the
[agent campaign guide](NATIVE-THROUGHPUT-AGENT.md). The earlier `spark-native-e2e`
qualification graph remains in its original configuration/store. Inspect
collected CC receipts and recorded event replay in the selected task. Replay
does not execute work. Health is a service readiness check, never scientific
acceptance.

Build the console from the web frontend's installed dependencies:

```sh
node jiuwenswarm/channels/web/frontend/scripts/build-factory.mjs /deployment/console
```

Spark deployment paths are under `/home/user2/software-factory-spark-20261113`:

- Source: `sources/native-workflow-integration-20261116`.
- Permanent Python environment: `native-workflow-service-env`.
- Initial service configuration, static console, qualification record and rollback command:
  `native-workflow-live-20261116`.
- Current service configuration and agent-driven throughput campaign:
  `native-throughput-goal-20261116` (`workflow-config.json` and `service.env`).
- Task, source build, raw GPU evidence and durable queue receipts:
  `native-workflow-qualification-20261116`.
- User service: `native-cc-factory.service`.

The service uses the existing shared Spark job queue and worker. Do not launch a
second worker or move mutable experiment stores into Git. Configuration selects
sealed releases and one task. The initial qualification task had a four-hour workflow deadline
and an aggregate allowance of three build attempts and four lab attempts, including
failures and cancellation. It is not an unlimited autonomous research campaign.
The current throughput task has separate limits documented in the agent campaign
guide: two hours, three builds, five comparisons and twelve GPU processes.
Future work requires a fresh bounded task/configuration; do not edit historical
contracts or reuse exhausted authorization. Source editing, scored benchmark
campaigns and other capabilities need their corresponding task inputs and grants.

## Qualification meaning

The acceptance workload is frozen before execution: the full six-expert DeepSeek
model, a 1471-token prompt, and a 16-token greedy continuation repeated twice per
process. Two fresh GPU processes must agree on every output token and finish
reason. Lab Manager independently verifies the sealed protocol, asset identity,
runtime image and resource evidence. This demonstrates the factory execution
path; it is not task accuracy, a long-context qualification, a numerical-oracle
qualification or a speedup claim.

Additional gates cover a fresh native ARM64/CUDA source build, workflow-client
restart, evidence-backed graph extension, wrong-image rejection before GPU
submission, cancellation of a running GPU job, exact container cleanup, and
service restart with durable records. A terminal job is not proof that its
container is gone. The live GPU check exposed and fixed that distinction in
Strata Lab Manager reconciliation.

## Rollback

The old `ai4r-spark-ai4r-1` container and all its volumes are retained. The prepared
`native-workflow-live-20261116/rollback.sh` stops/disables the new user service and
starts that exact old container. Before rollback during future work, stop and
collect owned workflow jobs through the API; stopping the web service alone does
not cancel queue jobs. Never delete the old volumes or globally reap containers.

The machine-local `qualification.json` records actual acceptance and cutover
status. A small source-controlled qualification record accompanies a successful
cutover; raw logs, model files, images and stores remain on Spark.
