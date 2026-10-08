# Local intent workflow

This package implements the Intent Compilation and Verification Slice in
`docs/architecture/build-package/immediate-plan.md`. Its accepted artifact is
`intent.v1`, not `Research_Brief.json` or completion of Delivery Phase 1.

From the repository root, launch the explicitly labeled offline wiring profile:

```powershell
python -m jiuwenswarm.research serve --profile mock --state-dir .runtime/research
```

Open `http://127.0.0.1:5173/research` and paste the credential from
`.runtime/research/session.token`. The packaged page works without an npm
build. When the existing React build is present, its Research navigation
uses the same API. The service keeps working when the browser closes.

In a second local terminal:

```powershell
$env:AI4RESEARCH_TOKEN = Get-Content -Raw .runtime/research/session.token
python -m jiuwenswarm.research smoke --output .runtime/research-smoke.json
python -m jiuwenswarm.research submit --text 'Study numerical stability using only supplied data.' --request-id example-1 --wait
python -m jiuwenswarm.research reconcile example-1
python -m jiuwenswarm.research retrieve <run-id> --output .runtime/run-bundle.json
```

Headless refusals return nonzero JSON with a run identity and evidence
reference. A lost submit response is reconciled by request identity; the
client never retries the compiler. Cancellation is explicit. Interrupted
work is paused on restart without replay. Corrected work uses a new request
identity and `--parent-run-id <old-run-id>`.

Omit `--profile mock` to select the static Codex bridge. The bridge requires
the prepared, pinned `openai-codex-cli-bin==0.144.4` runtime and an authenticated
ChatGPT subscription in its dedicated `<state-dir>/model/codex-home` profile.
The operator may authenticate that isolated profile using the prepared CLI's
normal login command with `CODEX_HOME` set to that directory. Research never
copies credentials or resumes a chat thread. Missing runtime/authentication
blocks visibly and never falls back to mock. Each producer/reviewer invocation
starts a fresh thread with tools disabled, and its host rejects tool requests.
The run freezes an opaque authentication-context hash. A missing identity or
account change blocks execution and release; account IDs, email addresses and
credentials are not written into run evidence.

`--global-config <file>` and `--config <file>` load the `research` section of
explicit JSON/YAML configuration; project values override global values and
explicit command arguments override both. YAML loading requires the already
installed PyYAML runtime. See `config.example.yaml`. The resolved configuration,
role models, request, implementation closure, fidelity rubric, time/call limits
and seed availability are frozen in each run. Clients cannot disable gates or
change profiles. Token usage, cost and seed control are recorded as unavailable
when the provider cannot supply them.

Run data lives in private SQLite/files under `--state-dir`. The separately
stored product identity defaults to `~/.ai4research-account/profile.json`; set
the operator-owned `AI4R_ACCOUNT_HOME` to place the profile outside a replaceable
workspace. Session credentials and OS identity are separate from product
identity. Accepted retrieval rechecks evidence hashes and the durable release
proof. Library standing and admission records remain inspectable under
`<state-dir>/library`; only operator code can activate/suspend/deprecate/roll
back versions. A changed implementation is admitted inactive and cannot run
until explicitly activated. The client API has no standing-write operation.

For preprepared images, `compose.yaml` publishes only `127.0.0.1:5173`. Supply
`AI4RESEARCH_TOKEN` securely and set `AI4R_PROFILE=mock` for the wiring campaign.
The optional benchmarker is an authenticated ordinary client; it mounts only
its campaign output, never workflow state or evaluation fixtures. The base
image contains the dependency-free workflow/page; a real-model image must
already contain the pinned runtime. Startup installs or downloads nothing.
The application container does not implement scientific POC confinement.

Offline verification:

```powershell
$env:AI4R_CHALLENGE_RESULTS_PATH = 'tmp/research-offline-evidence/intent-challenges.json'
python -m unittest discover -s tests/research -v
node --test jiuwenswarm/channels/web/frontend/tests/researchIntent.test.mjs
python scripts/evaluate_intent_fidelity.py --dry-run --output tmp/research-fidelity-preparation
```

The fixed challenge labels precede evaluation, and the result file records
each observed outcome and false acceptance/refusal. Scripted assessments and
mock runs establish wiring, integrity and refusal behavior only. They do not
measure real-model fidelity. Separate invocations provide protected context
and evidence separation, not independent provider errors or calibrated truth.
The fidelity preparation command persists the fixed fixtures, thresholds and
implementation pins without model calls. Use a new output directory for each
preparation. It reports `PREPARED_NOT_MEASURED`, never a fidelity pass. Real
measurement requires the separate explicit `--execute-model` operation and a
prepared authenticated bridge; it has not been run as part of offline checks.
