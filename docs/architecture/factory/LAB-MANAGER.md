# Lab manager and lab agents

The factory's software agents build things; a lab tests them. The lab manager (`factory.lab_manager`, code in `jiuwenswarm/factory/lab_manager.py`) is how a software agent asks a lab for a test, without running the lab itself.

```
software agent ── lab task + subjects ──▶ lab manager ── package ──▶ lab mailbox ◀── lab agent
               ◀── lab_report evidence ──             ◀── report, answers ───────
```

## What moves

| Document | Format | Written by | Holds |
|---|---|---|---|
| Lab task | `factory.lab-task/1` ([schema](../../../jiuwenswarm/factory/schemas/lab-task-1.schema.json)) | software agent | Which subjects fill which contract arms, the tests (a contract check, contract metrics or both, on named arms and requests, optionally an A/B comparison), steps, deliverables (files, sections, raw samples) and constraints |
| Subject | inside the lab task | software agent | A result under test, named by identity: `container_image` (tag and image id), `native_build` (executable digest), `source` (commit), `artifact` (digest) or `stock`. With `build_attempt_id` the lab manager checks the identity against the build receipt. With `transfer: attach` its bytes travel with the package (below) |
| Lab package | `factory.lab-package/1` | lab manager | The lab task, the full contract snapshot and its SHA-256, the checked subjects with any payload digests, and the originating task. Its id is a digest of its content, and it is stored as a task artifact |
| Payload | a file in the mailbox | lab manager | The bytes of a subject marked `transfer: attach`: a container image as a `docker save` archive, or the stored artifact named by `identity.artifact_id` (for example a native build tarball). Its SHA-256 is sealed in the package |
| Message | `factory.lab-message/1` | both sides | One step of the conversation (below) |
| Lab report | `factory.lab-report/1` ([schema](../../../jiuwenswarm/factory/schemas/lab-report-1.schema.json)) | lab agent | Outcome, summary, setup and deviations, results per test, arm, request and metric (value or samples, with unit and interval), check verdicts, tests not run with reasons, attached files with digests, limits |

## Shipping the engine

A lab task can be written in YAML. To have the lab test an engine image the factory holds, name it and mark it for transfer:

```yaml
subjects:
  stock:
    kind: container_image
    identity: {id: "sha256:9454516f…", tag: "factory/llamacpp:deepseek-stock-20261120"}
    transfer: attach
```

`compose` runs `docker save`, checks that the archive holds that image id, stores the archive as a task artifact and seals its digest into the package. `send` uploads it with the request. The lab agent's `fetch` downloads it, checks the digest and the image id (without Docker, from the archive's `manifest.json` or `index.json`; both the classic and the containerd image store are handled) and, with `--load`, runs `docker load` and checks the loaded id again.

## Shipping source instead: the lab builds the image

The factory and the lab may have different architectures (an x86 workstation and an arm64 DGX Spark). Then ship source (`lab_build.py`, capability `source_bundle`):

- **What travels** is a source bundle (`factory.lab-source/1`): the base commit of any repository, branch or fork, the binary diff from it to the tree under test (uncommitted and untracked files included), the name of a lab build recipe, extra `-D` flags, and source dependencies described the same way (each passed to CMake as `-D<VAR>=<dir>`, for example a Strata build's ggml). The base history can travel too (`include_base`) when the lab cannot reach the repository.
- **The lab rebuilds the exact tree.** It fetches the base commit (depth 1) or reads the shipped history, applies the diff and refuses to build unless the result has the git tree hash sealed in the package.
- **Recipes belong to the lab.** A bundle names one (`llama-server-cuda-sm121`, `llama-server-cpu`, or the lab's own in `$FACTORY_LAB_RECIPES`); it cannot bring build commands. Extra flags must look like `-DNAME=value`.
- **Warm slots make rebuilds fast.** Each (repository, base, recipe, flags) keeps a checkout and build directory. A new diff resets the checkout to the base (only the files that differ are rewritten), applies the diff and builds incrementally. The image context also stays in the slot, with the toolkit libraries in their own layer, so Docker reuses it. Ninja and ccache are used when installed.
- **The lab reports what it built** under `builds` (tree, image id, executable digest, seconds per phase, warm or cold); the lab manager rejects a report whose build is not the sealed tree.

```bash
jiuwenswarm-factory lab-agent serve --adapter command --build-sources --command "RUNNER {package} {output} {payloads}"
python -m jiuwenswarm.factory.lab_build recipes            # what this lab can build
```

Measured on 2026-11-22: a factory on x86_64 (WSL on a workstation) bundled the expert weight cache candidate (the 11-20 direct-seed diff, 6 files, +797 lines) against stock llama.cpp `9048bad`: a **61 KB** bundle, sent over Tailscale in under a second, against 3.1 GB for the image. The Spark lab assembled, checked and built it:

| Build on the Spark (aarch64, CUDA 13, sm_121, Ninja, -j12) | Compile | Image | Total |
|---|---|---|---|
| Cold slot (configure and full build) | 160 s | 22 s | 186 s |
| Warm slot, next diff (one file changed) | 4.1 s | 21.5 s | 26 s |
| Warm slot, layered image context reused | 4.0 s | 0.8 s | **4.8 s** |

Each built image ran `llama-server --version` on the Spark, and the x86 factory recorded each report as valid `lab_report` evidence.

**Or cross-compile on the factory.** `labkit/cross/` holds a CMake toolchain and a build script that build the same arm64 CUDA llama-server on x86_64 (see its README for setup and timings). The result runs on the Spark and finds the GB10; ship its `app/` directory as a stored artifact (`transfer: attach`). On the workstation tested (WSL limited to 2 CPUs) a clean cross build took 28 minutes against 164 s on the Spark, so letting the arm64 lab build is the default; cross-compiling pays on a large x86 build server or to compile-check a diff before it takes a lab slot. With ccache installed in the lab (a static aarch64 binary needs no root), a new slot rebuilds in about 6 s instead of 164 s.

## The mailbox

The mailbox (`lab_mailbox.py`) is a directory, by default `$FACTORY_HOME/lab-mailbox`, or `$FACTORY_LAB_MAILBOX`. Each request gets `requests/<request_id>/` with `package.json`, `messages/` and content-addressed `files/`. A message may only name files already in the request's `files/`.

- **The factory sends** `request`, `question` and `cancel`.
- **The lab sends** `accepted`, `rejected`, `progress`, `answer`, `report`, `failed` and `cancelled`.
- **State is folded from the lab's messages:** `requested`, then `accepted` or `rejected`, then `running`, then `reported` or `failed`. A cancel turns an open request into `cancel_requested` until the lab confirms `cancelled`. Questions and answers can come at any time, also after the report.
- **Each side only creates its own files** (`factory-000001.json`, `lab-000001.json`) and never rewrites one. A message appears only when complete. So the directory can be synced both ways between machines with `rsync` or `scp` without conflicts. A lab off the factory machine needs only the directory.
- **Malformed files and out-of-order messages are listed and ignored**, never folded into the state.

### Over HTTP

For a lab on another machine, serve the mailbox (`lab_http.py`):

```bash
# on the machine that keeps the mailbox, bound to its Tailscale address
jiuwenswarm-factory lab-server --host 100.x.y.z --port 8790     --factory-token-file factory.token --lab-token-file lab.token
# on the factory machine and on the lab machine
export FACTORY_LAB_MAILBOX=http://100.x.y.z:8790 FACTORY_LAB_TOKEN_FILE=<its token file>
```

Everything else stays the same: the lab manager and `lab-agent` accept a directory or an address.

- **Two tokens, two roles.** Only the factory token opens requests and posts factory messages; only the lab token posts lab messages. A wrong token gets 401, a wrong role 403.
- **Large files resume.** Uploads go in 64 MiB chunks and continue from the bytes the server already has; downloads continue with HTTP ranges. A file is installed only when its whole content matches its digest, and every download is checked again.
- **No TLS of its own.** Run it on a private network such as Tailscale (WireGuard-encrypted) and bind it to that address, not to all interfaces.

## Routing: the lab CC system until a lab agent exists

`$FACTORY_LAB_ROUTE` decides who works a request:

| Route | What happens |
|---|---|
| `queue` | The factory's own lab queue, the system behind `factory.lab_client`, works every request it can run, in process, each time the lab manager is asked for `status` or `report`. No separate lab agent runs |
| `mailbox` | Requests wait for a lab agent reading the mailbox |
| `auto` (default) | `queue` for a local mailbox, `mailbox` for an HTTP one |

A request the queue cannot run (a format-2 contract, a subject that is not a factory-built image) is left open for a lab agent, and `status` says why. Planning is unchanged: the task graph's measure steps still call `factory.lab_client`, so testing runs on the lab CC system as before.

## Capabilities

`draft_task`, `compose`, `send`, `status`, `cancel`, `ask`, `reply` and `report` (see `ccs/lab_manager/LAB-MANAGER.md` for the agent-facing steps). Each returns one `result` object.

`report` checks the report against the package:

- every test is answered or listed as not run;
- results use the test's arms, metrics and requests, in the contract's units;
- raw samples and deliverable files and sections are present when asked;
- `completed` means nothing was skipped;
- attachments match their digests.

It then records the report as a `lab_report` observation, with the report and files as artifacts. A report that fails these checks is still recorded, as `valid: false` with its problems, so the failure is visible. Agents cannot publish `lab_request`, `lab_report` or `lab_answer` evidence themselves.

## Lab agents until a real one exists

There is no autonomous lab agent yet. `lab_agent.py` gives any lab agent the same steps, and checks a report against the package before posting it. Run it as `jiuwenswarm-factory lab-agent ...` or `python -m jiuwenswarm.factory.lab_agent ...`. It has three stand-ins:

| Stand-in | How it runs | Use |
|---|---|---|
| Operator | `lab-agent inbox`, `show`, `accept`, `progress`, `answer`, `report <request> report.json --file name=path` | A person or a coding agent at the lab machine. This is the role the lead engineer played on 2026-11-20, running the Spark contract under the memory-capped runner and importing results by hand; now it follows a recorded protocol |
| Queue | `lab-agent serve --adapter queue` | The factory's own lab queue runs format-1 contracts on container images the factory built, as `factory.lab_client` did. It rejects what it cannot run, with the reason |
| Command | `lab-agent serve --adapter command --command "RUNNER {package} {output}"` | Any lab script: it reads the package, runs the lab and writes `report.json` and `files/`. The identity fields are filled in and the report is checked before it is posted |

`--profile spark-gb10` limits a lab agent to requests for its machine. Every stand-in answers questions that ask only for files, metrics or tests already in its report; other questions wait for the operator.

## Tested between two machines

On 2026-11-22 the factory on the DGX Spark composed two lab tasks from YAML for the stock llama.cpp DeepSeek image (`docker save` archive, 3.14 GB) and sent them through a lab server on the Spark's Tailscale address:

- A lab agent on the Spark (command stand-in) fetched the archive over HTTP, checked it, ran `docker load` and `llama-server --version`, and posted a report. The factory checked it against the sealed package and recorded it as `lab_report` evidence (valid, `partial`: no model was loaded, so the measurement is listed as not run).
- A lab agent on a Windows workstation fetched the same archive over Tailscale (through a relay at about 3 MB/s, 17 minutes, interrupted once at 344 MB and resumed with a range request) and checked its digest and image id without Docker. It answered a factory question (the image's CUDA version) and posted its report with an inspection file back over HTTP; the factory recorded both as evidence.

The first run also found a real defect, since fixed: Docker's containerd image store names an image by its OCI index digest, not its config digest.

## Limits

- The lab is trusted for its numbers. The lab manager checks that a report answers its package and that files match their digests; the mailbox directory and the server's tokens are the trust boundary.
- The queue stand-in measures only what the factory lab queue records (reference parity, engagement checks, decode ms per token, A/B gate and ratio). It is not an independent lab.
- `factory.lab_client` remains the planned path for testing. The lab manager reaches the same queue through the `queue` route, and reaches other machines through the mailbox.
