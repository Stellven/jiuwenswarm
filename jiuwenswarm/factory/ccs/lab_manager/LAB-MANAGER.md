# Lab manager: how to get a result tested

You do not run the lab. You say what to test, the lab manager sends it to a lab agent, and the lab agent delivers a report. This works the same whether the lab agent is a person at the machine, a coding agent, the factory's own queue or a lab command, on this machine or another one.

Until a lab agent is set up, requests the factory's own lab queue can run (format-1 contracts on images the factory built) are worked by that queue automatically; `status` shows the route. Everything else waits for a lab agent.

## Steps

1. **Draft** (format-2 contracts): `draft_task` with `arm_subjects` (contract arm → subject name) and `subjects`. It returns a lab task that runs every contract check and metric on those arms, plus any problems. Remove the tests you do not need and add `steps` the lab must follow.
2. **Compose**: `compose` with the lab task (an object or YAML text). It is checked against the task's pinned contract and each subject is checked against its build receipt. Fix every problem it reports; it seals nothing until the lab task is valid. A subject with `transfer: attach` is shipped with the package: a container image as a `docker save` archive, or the stored artifact named by `identity.artifact_id`.
3. **Send**: `send` with the package id and an `idem_key`. Sending again with the same key returns the same request.
4. **Follow**: `status`. A request is `requested`, then `accepted` or `rejected`, then `running`, then `reported` or `failed`. `cancel` asks the lab to stop.
5. **Ask**: `ask` at any time, also after the report. Put what you want under `wants` (`files`, `metrics`, `tests`) when it is data the report may hold; a lab can answer those at once. Read the answer with `reply`.
6. **Report**: `report` checks the report against the package and records it as `lab_report` evidence. Cite that evidence id in decisions. A report that fails the check is recorded with `valid: false` and its problems; do not use its numbers.

## Lab task

```yaml
schema: factory.lab-task/1
lab_task_id: ewc-ttft-01
purpose: Decide whether to keep the expert weight cache build.
contract: {id: star-deepseek-v2}
subjects:
  stock:     {kind: native_build, identity: {executable_sha256: "<sha256>"}, build_attempt_id: "<attempt>"}
  candidate: {kind: native_build, identity: {executable_sha256: "<sha256>", artifact_id: "<stored build tarball>"},
              build_attempt_id: "<attempt>", transfer: attach}
arms:
  A:  {subject: stock}
  C1: {subject: candidate, env: {LLAMA_EXPERT_WEIGHT_CACHE: "1"}}
tests:
  - {id: parity, check: gate_unset_parity, arms: [C1]}
  - {id: ttft, measure: [client_ttft_ms], arms: [A, C1], requests: [p512, p2048]}
deliverables: {raw_samples: true, files: [{name: ttft-samples}], sections: [setup, results, deviations]}
constraints: {lab_profile: spark-gb10}
```

## Source instead of an image

When the lab machine has another architecture (an x86 factory, an arm64 lab), ship source: `source_bundle` with your checkout, the `base` commit the lab can fetch (upstream or your fork; `include_base: true` ships the history too) and a lab recipe (for example `llama-server-cuda-sm121`). Put the returned `subject` in the lab task. The lab rebuilds exactly your tree (it checks the git tree hash), builds natively in a warm build directory and reports the image it built under `builds`.

A subject is named by identity (image id, executable digest, source commit, artifact digest), never by a path. Mark it `transfer: attach` when the lab does not already have it. Arm names come from the contract. A test runs a contract check, measures contract metrics, or both.

## What it does not do

- It does not judge a result. The contract's acceptance rules and your decision do that, from the recorded report.
- It does not make a lab agent honest. It checks that the report answers the package and that its files match their digests; the numbers are the lab's statement.
