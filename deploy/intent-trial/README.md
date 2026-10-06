# Bounded local Intent trial

This single application serves the existing native frontend at `/intent-trial`
and the authenticated `/api/intent-trial` use case. It has only two authored CCs.
It produces accepted intermediate Intent or a durable halt, never a Research
Brief, research graph or full-M1 acceptance claim.

The supported real execution boundary is a non-root POSIX container with private
Unix-domain model IPC. The adapter has no TCP listener. The application binds
127.0.0.1 only. Compose uses host networking to retain this loopback boundary;
Docker hosts that do not support host networking are environment-blocked until
the same boundary is provided and verified. Do not publish it on all interfaces.
Windows source mode remains useful for offline checks and displays unavailable
security; it does not silently replace protected IPC with TCP.

From repository root, build the native frontend with `npm --prefix
jiuwenswarm/channels/web/frontend run build`, then start with:

```powershell
.venv/Scripts/python.exe -m jiuwenswarm.ai4research.service --state-dir D:/private/intent-trial-state --workspace D:/research/intent-trial-workspace
```

State/profile custody must be outside the workspace. Local source mode on
Windows cannot establish the real execution boundary. On a supported Docker
host, run `docker compose -f deploy/intent-trial/compose.yml up --build`. A
successful build is not proof of model-backed or security acceptance.

Real definition eligibility also requires `--admission-receipt` pointing to the
current retained definition check and independent scope-review evidence. It binds
both exact CC identities, unskipped self-test outcomes and review reasons. Missing
or changed evidence leaves definitions unadmitted. This is provisional definition
eligibility; semantic fidelity and connected acceptance require actual measurements.
The current local receipt and raw inputs are retained with M0-SYSTEM runtime
evidence. Copy that whole evidence folder unchanged to private host custody and
set `TRIAL_DEFINITION_EVIDENCE_DIR` to its absolute path for Compose. The read-only
evidence mount grants no gate authority.

The trusted host bootstrap stores a 24-hour local session token in
`STATE/session.token` with private POSIX permissions. It stores only token hashes
in identity SQLite. Use this token in the native session field; it stays in
browser memory. It is distinct from model login. Sign in through the model-account
button, using the application's dedicated Codex profile; no IDE credential or
chat history is imported. Connect again to inspect actual model/auth/storage/
security readiness. Missing readiness yields an environment-blocked run.

The minimal sequential client never prompts and never invokes the model directly:

```powershell
.venv/Scripts/python.exe -m jiuwenswarm.ai4research.headless --token-file D:/private/intent-trial-state/session.token --text-file objective.txt --request-id my-unique-request
```

Exit 0 means exact accepted intermediate Intent, 2 a terminal halt, and 3 client
unavailability or an unresolved transport outcome. A lost submit response is
reconciled by the same request identity through retrieval, without resubmission.
Changed payload under the same identity is rejected. Closing a browser leaves
server-owned work running. Restart pauses unfinished work without replay;
corrected input starts fresh linked work.

Development tests use explicitly labelled scripted model fixtures. They prove
local wiring and controls only. Real acceptance requires the frozen challenge
corpus, actual approved model/account, supported container IPC and current
M0-SYSTEM evidence. Compiler/verifier provider errors can be correlated.

The separate development measurement command consumes locked independent subjects
and preserves all 27 verifier observations, including wrong labels and false
acceptance/refusal. It cannot create production accepted output:

```powershell
.venv/Scripts/python.exe -m jiuwenswarm.ai4research.characterization --state-dir D:/private/intent-trial-state --workspace D:/research/intent-trial-workspace --admission-receipt CURRENT_EVIDENCE/definition-admission.json --corpus tests/fixtures/ai4research/intent/characterization/locked-candidates.json --output-dir D:/private/new-characterization-run
```

Stop the service before this command takes the same state lease. It never resumes
or overwrites a campaign, does not invoke the compiler, and has no mock CLI route.
Inside the image the locked corpus is `/app/characterization/locked-candidates.json`.
Real supported IPC, account and custody are prerequisites. This measurement does
not replace ordinary-client connected compiler/verifier acceptance and refusal.
