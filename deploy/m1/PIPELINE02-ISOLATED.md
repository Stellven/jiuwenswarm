# Pipeline02 isolated startup

The native cache-study protocol runs generated Python against the supplied
LRU traces. It retains original per-trace hits/misses and independently computes
`miss_ratio` in fractions. Request counts do not establish latency improvements.
The four recovery variants use a protected dependency denial, actual cancellation
API, and actual observer/collector process interruption. The controller's key and
private labels are never product inputs. Readiness and unit checks alone do not
establish a successful end-to-end benchmark.

The optional cached build requires the exact retained dependency image. Tag it
locally before building `Dockerfile.pipeline02-fast` (normal deployment can still
use the standard app Dockerfile):

```sh
docker tag sha256:f31901c0b25c0856399b17c56bc50f9971d6bc86a7e07e00d57418cd0d7ab9ba ai4r-pipeline02-dependencies:f31901c0
docker image inspect --format '{{.Id}}' ai4r-pipeline02-dependencies:f31901c0
docker build --network none -f deploy/m1/Dockerfile.pipeline02-fast --target app -t ai4r-pipeline02-app .
docker build --network none -f deploy/m1/Dockerfile.pipeline02-fast --target root-runner -t ai4r-pipeline02-runner .
```

Use an allowlisted public-source TAR context if local checkout caches cannot be
read by Docker. The build never needs private benchmark labels or credentials.

Run these operator commands on the Linux Docker host as root after the two images
are frozen and built. No command below builds an image. Use a new project and
new directory; the helper refuses existing deployment volumes. It imports the
checked-in `local_model_operator.py` beside it and uses its supported custody
checks and provisioning. It never loads RSI state, accounts, or auth caches.

Required inputs:

- Exact app and root-runner image IDs, `sha256:...`.
- Fresh project `ai4r-pipeline02-...` and root-private deployment directory.
- Existing public `cache-traces.json` file, readable by app UID10001.
- Dedicated existing suite directory, eventually containing `bundle/`.
- The existing relay's actual catalog, session, and socket-directory paths under
  `/home/s50066325/.local/share/ai4r/ai4r-codex-text-20261025/model-control`.
  The known source paths are `catalog.json`, `private/session.json`, and
  `socket-export/` under that relay root. Do not replace or alter the relay. Only the validated
  catalog/session configuration is copied into a fresh read-only app volume;
  only the socket directory is bound read-only.
- Optional already-owned finite cgroup branch via `--cgroup-host` if required by
  the selected qualified execution configuration.

```sh
python3 deploy/m1/pipeline02_isolated_operator.py stage \
  --directory "$DEPLOYMENT" --project "$PROJECT" \
  --app-image "$APP_IMAGE_ID" --runner-image "$RUNNER_IMAGE_ID" \
  --public-data "$CACHE_TRACES" --suite-root "$SUITE_ROOT" \
  --relay-catalog "$RELAY_CATALOG" --relay-session "$RELAY_SESSION" \
  --relay-sockets "$RELAY_SOCKET_DIRECTORY"
python3 deploy/m1/pipeline02_isolated_operator.py start --directory "$DEPLOYMENT"
python3 deploy/m1/pipeline02_isolated_operator.py select-model --directory "$DEPLOYMENT" --model-id "$LOCAL_MODEL_ID"
python3 deploy/m1/pipeline02_isolated_operator.py initialize --directory "$DEPLOYMENT"
python3 deploy/m1/pipeline02_isolated_operator.py grant --directory "$DEPLOYMENT"
python3 deploy/m1/pipeline02_isolated_operator.py start-runner --directory "$DEPLOYMENT"
python3 deploy/m1/pipeline02_isolated_operator.py controller-setup --directory "$DEPLOYMENT"
```

The app is published only at `127.0.0.1:5180`; its Origin is
`http://127.0.0.1:5180`. Within the private Compose network the runner uses
`http://ai4r:5173` and HTTP authority `127.0.0.1:5180`.

`start` creates only fresh prefixed volumes, initializes the dispatch-control
root with root0755 `app/requests` and UID10001-owned0700 `app/events`, and starts
the app. The app receives `JIUWENSWARM_M1_CACHE_DATASET` and
`AI4R_PROTECTED_DISPATCH_CONTROL=/run/ai4r-benchmark-control/app` before capture.
Native startup creates its own account/session in the new account volume.
`stage` reports enabled local model IDs from the actual catalog. `select-model`
uses the supported protected native `agent-status.sock` ModelSettingsOwner
operation as UID10001 for this fresh account and verifies actual relay readiness.
Choose the reported GPT-6.1-Sol ID explicitly; no API key or RSI account is used.
`initialize` invokes the actual native catalog initializer as UID10001, records
its real response privately, then recreates the isolated app. `grant` invokes
the existing root-only finite runner issuer and leaves the token only in the
fresh credential volume, owned by UID11001. It records the app's actual build ID
in runner settings. No token, bootstrap URL, or session capability is printed.

`controller-setup` creates an exclusive raw Ed25519 seed and native controller,
bridge, and suite configs under root-only `/operator`. It prints only the public
key and suite-config path. It refuses replacing an existing seed/config. The
root-only `/custody` volume retains actual fault-controller observations.
Freeze the returned public key into the original task using the existing
`benchmarks.harbor_suite.prepare --controller-public-key` option before launch.
The bundle is read from `/suite/bundle`; actual evidence is retained under
`/results`. The app cannot mount `/operator`, `/custody`, `/results`, or `/suite`.

After the original task has been frozen and validated, launch each exact task
through the native root controller (the task key comes from its frozen index):

```sh
docker compose -p "$PROJECT" -f "$DEPLOYMENT/compose.json" exec -T --user 0:0 \
  root-runner /opt/venv/bin/python -m benchmarks.harbor_suite.protected_controller \
  --suite-config /operator/suite.json --task-key "$FROZEN_TASK_KEY" \
  --identity "$UNIQUE_ORCHESTRATOR_TRIAL_ID"
```

Use the existing native runner readiness/doctor command before measured work.
Run it as the root supervisor that owns `/results`, with the exact frozen case:

```sh
docker compose -p "$PROJECT" -f "$DEPLOYMENT/compose.json" exec -T --user 0:0 \
  root-runner /opt/venv/bin/python -m jiuwenswarm.research_sidecar.sequential doctor \
  --cases "/suite/bundle/cases/$FROZEN_TASK_KEY.json" --inputs /suite/bundle/inputs \
  --output /results --json
```

Initialization, container liveness, or a created grant never establishes an
accepted research result. The helper neither creates accepted receipts nor
claims activation/readiness based on directory or service presence.

If a native gate stops the workflow before the planned fault, the controller
captures the actual terminal status and artifact manifest, then releases the same
observer to collect the original run. It records `fault_not_applied` and reports
`controller_complete: false`; it creates no fault effect or signed fault custody.
Preserve that partial outcome and report the recovery condition as unexercised.
