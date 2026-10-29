# Docker-only evaluation pilot authoring

`evaluation_pilot_cli` prepares protected evaluation configuration and exact request templates. It does not execute either request, call a model, write a gate decision, or grant product acceptance. Phase 1 creates a profile-only startup. Phase 2 consumes one actual source contract and successful observation produced under that exact phase-1 configuration, then creates one fresh E3 request and one E2 request replaying the captured output bytes. This is fixture-tested preparation tooling; the Compose workflow has not been validated end to end against a live app run.

Run the commands inside the Compose app container. All output directories must be new paths beneath `/var/lib/ai4r/operator`.

## Capture phase 1

```sh
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml exec -T --user 10001:10001 ai4r \
  python -m jiuwenswarm.research.evaluation_pilot_cli profile \
  --profile-id ml-diagnostic-20261026 \
  --candidate research.evaluation@m1-5 \
  --verifier research.verifier@<exact-installed-version> \
  --output-dir /var/lib/ai4r/operator/ml-diagnostic-phase1
```

Repeat `--candidate name@version` for each exact installed candidate. The command resolves identities against the immutable snapshot captured by the currently bound startup. If more than one verifier declaration is installed, `--verifier name@version` is required to select an exact pin; the command never picks one implicitly. It writes `config.json`, `bootstrap.json`, and `pilot.json` in the new directory.

Restart the app against that explicit profile before producing source observations:

```sh
export AI4R_OPERATOR_CONFIG=/var/lib/ai4r/operator/ml-diagnostic-phase1/config.json
export AI4R_BOOTSTRAP_BINDINGS=/var/lib/ai4r/operator/ml-diagnostic-phase1/bootstrap.json
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml up -d ai4r
```

The normal authenticated app flow must produce a genuine capsule run and observation under this exact phase-one configuration. This Compose-to-source step has not been validated. If the active app policy cannot produce that source contract, stop: do not synthesize a contract or observation to continue.

## Inspect and capture phase 2

```sh
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml exec -T --user 10001:10001 ai4r \
  python -m jiuwenswarm.research.evaluation_pilot_cli \
  --config /var/lib/ai4r/operator/ml-diagnostic-phase1/config.json \
  --bootstrap /var/lib/ai4r/operator/ml-diagnostic-phase1/bootstrap.json \
  sources --profile-dir /var/lib/ai4r/operator/ml-diagnostic-phase1
```

Choose a listed source contract and its successful observation from the JSON. Both identifiers must be the record IDs shown there. Then author the bounded E3/E2 scope:

```sh
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml exec -T --user 10001:10001 ai4r \
  python -m jiuwenswarm.research.evaluation_pilot_cli \
  --config /var/lib/ai4r/operator/ml-diagnostic-phase1/config.json \
  --bootstrap /var/lib/ai4r/operator/ml-diagnostic-phase1/bootstrap.json \
  scope --profile-dir /var/lib/ai4r/operator/ml-diagnostic-phase1 \
  --source-contract-id <listed-contract-record-id> \
  --observation-id <listed-successful-observation-record-id> \
  --output-port <listed-output-port> \
  --campaign-id ml-diagnostic-20261026 \
  --output-dir /var/lib/ai4r/operator/ml-diagnostic-phase2
```

`requests.json` contains the request bodies and exact asset paths/hashes. The command makes no API request. Review the refs and limits before submitting them through the existing authenticated evaluation API.

Restart with the generated phase-2 startup only when ready to run that evaluation profile:

```sh
export AI4R_OPERATOR_CONFIG=/var/lib/ai4r/operator/ml-diagnostic-phase2/config.json
export AI4R_BOOTSTRAP_BINDINGS=/var/lib/ai4r/operator/ml-diagnostic-phase2/bootstrap.json
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml up -d ai4r
```

E2 replay currently supports output-only verifier profiles. Evidence-aware v2 profiles are explicitly unavailable for evaluation replay until that path passes the host-built evidence projection. Every profile and scope is marked `invalid_for_product`. These diagnostic records do not constitute Benchmark acceptance or alter previously captured refs.
