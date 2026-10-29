# Screening CC versus plain Codex: development pilot

Updated October 26, 2026 (America/Toronto).

The tested component is the existing implemented `research.screening` `m1-4`,
not a replacement capsule. Its declaration SHA-256 is
`1f8f0e2f036d7b8d629ec8241e7279e71b60f43c66ab95ce04be37d6af8602e5`.
Only `cc01-transfer / screen-missing` was selected: one of that case's three
development variants. This is not a full-suite or end-to-end research result.

## Matched assignment and result

Both arms were frozen against the same task, three typed input values and Refs,
output schemas, and one tool-free call with a 120-second allowance. The common
assignment SHA-256 is
`b05e93674e158f020f33fb2a079e99d6b1800fe37455e295d42ab307c530a6db`.
The model-bound CC generation was checked byte-for-byte against the already
completed baseline assignment; no baseline rerun followed the routing fix.

| Arm | Observed result | Mechanical content / format | Usage |
| --- | --- | --- | --- |
| Plain native Codex, tool-free | Completed; observed GPT-6.1-Sol / medium | Both pass; subjective reasoning quality still requires review | 17,366 input / 1,431 output tokens; 22.406 seconds for the native call |
| AI4Research Screening CC | Framework call and relay request reached the selected host route; outcome unknown | Not scored; no final outputs | Effective model, tokens and monetary cost unobserved |

No CC improvement or regression in reasoning quality can be concluded from this
pair. Availability and evidence failure must remain separate from task quality.
Monetary cost was unavailable for both arms. The baseline's private native
receipt was validated by the operator-side runner; its credential-free Harbor
grader independently checked original-answer consistency, schema and content.

## What failed and what was fixed

Initial setup attempts are retained separately. An assumed Docker network name
failed before its worker started. An early source Brief then referenced a text
fixture where real qualified intake lineage was required. Preparation now uses
the actual intake owner and full parent resource disposition before freezing.
An earlier plain baseline used those older input bytes and is diagnostic only.

The qualified CC attempt exposed missing frozen account model choice for E3:
its private run fell back to `codex-cli-default` and failed authentication.
E3 now carries the actual source capture's immutable account model choice,
with runtime/source/account ownership checks. Private trace capture/export also
now retains request-owned originals instead of uncaptured ordinary-run file
aliases. Public grader files now use readable permissions; private receipts
remain private. App and runner were rebuilt together. The Screening capsule's
scoring implementation and scientific expectations were not changed.

The final call requested `local-host-codex61:gpt-6.1-sol`. Relay request
`091e3fb77fb14875b6e0956ad5b3071c` remains `outcome_unknown`. Its diagnostic says
`backend_error` after 107 ms, with no captured stdout receipt, native turn ID or
terminal evidence. The swallowed underlying exception cannot be reconstructed
from retained metadata. No relay-owned helper/model process was currently
observed, but provider completion cannot be established. No further inference
was issued and neither unknown outcome was reclassified.

## Current state and evidence

- [AI4R Bench Hub](http://127.0.0.2:5175/) remains available with the centered
  title and **Test Cases** label. The app remains at `127.0.0.1:5175`.
- The owned idle relay was stopped. Its original four completed requests and
  fifth unknown request remain unchanged; the active Harbor guard is retained.
- App drainage: zero active runs, unfinished claims or unreleased leases.
- All 349 retained RSI hashes and the earlier scientific unknown ledger match.
- Results are retained under
  `D:/Codex Development Runs/harbor-deployment-20261025/cc-model-bound-run-20261026/`:
  `final-state.json`, `shared-assignment-proof.json`, and 241 hash-verified files
  in `retained-original-results/` with `retained-original-manifest.json`.
- Actual Harbor jobs: `plain-codex-screening-qualified-20261026` and
  `ai4r-cc-screening-model-bound-20261026`. Earlier failed jobs remain visible.

The current catalog uses development built-in authorization; independent
pre-admission calibration remains NOT_RUN. No formal M1 acceptance, held-out
transfer result, GPU execution, or passing verifier comparison is claimed.

See [COMPARISONS.md](COMPARISONS.md) for the common CC/verifier comparison
protocol and [HOST-CODEX-INTEGRATION.md](../../deploy/m1/HOST-CODEX-INTEGRATION.md)
for deployment and custody requirements. At this checkpoint inference stopped.
Subsequent supported operator acknowledgement preserved the unknown result and
authorized distinct new work after local containment checks; the original
request was never replayed. Later evaluation and binding variants passed. This
Screening fixture remains unscored. See [current status](SERIAL-VALIDATION-STATUS.md).
