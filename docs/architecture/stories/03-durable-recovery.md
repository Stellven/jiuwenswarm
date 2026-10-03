# A passing Gate cannot be saved

## Starting item and failure point

R1's Screening attempt 1 has committed a card Artifact, raw capture and work Observation O1. All required Gate checks pass in memory. Inject failure into the Verification write in `cc/store.py`, before durable publication.

The Gate host is the Verification decision owner. The runner's successful work result, the semantic verifier's assessment, an engine journal entry and a UI event are each insufficient to release Hypothesis. The [lifecycle](../system/lifecycle.md), [system records](../system/records.md) and [store](../system/storage.md) define the authority and recovery sequence.

## What connects and what remains stopped

| Order | Proposed code and connection | Expected durable observation |
|---|---|---|
| 1 | `cc/runner/pipeline.py` → supervisor/store | O1 and card exist with exact attempt/Binding/capture refs |
| 2 | `cc/gate.py` → `cc/checks/runner.py` and shared verifier | Actual check/judge evidence is retained; any judge call has its own reserved identity/capture |
| 3 | Gate → `cc/store.py` | Verification commit fails: STORE_UNAVAILABLE; no success ref |
| 4 | `cc/adapters/swarmflow.py` / generic script → halt host | Non-success envelope; no Hypothesis dispatch |
| 5 | Supervisor → system-record/incident sink | Halt with known evidence if a sink is writable; otherwise truthful non-durable diagnostics |
| 6 | `cc/adapters/runview.py` / local terminal | Read committed state and expose explicit review requirement |

The hypothetical downstream invocation count at the injected point must be zero. This is an expected integration observation, not an executed result in this document.

## Explicit recovery and no repeated work

After restoring storage, an authenticated operator records terminal review and requests resume with unchanged pins. Recovery reads actual committed records rather than trusting the journal cache.

If Verification is absent, Gate recovery operates on O1. It does not rerun Screening. A committed assessment/judge call is reused through its exact reserved identity; an uncertain paid judge turn cannot be silently repeated. A new effectful call requires explicit attributable restart under the normal attempt rules. Resume cannot infer that a missing Observation or reply means no effects occurred.

If a complete advancing Verification already exists and only its response was lost, recovery returns and validates that same record. If release is absent, supervisor commits it. If release exists but engine reply was lost, supervisor validates it and proceeds without executing work or judge again.

## Other crash locations

| Injected point | Result |
|---|---|
| Temporary output batch written, before rename | No committed output; quarantine staging and inspect partial execution |
| Rename succeeds, response lost | Same batch identity returns existing refs; no second write |
| Verification committed, release write fails | Verification remains evidence; successor stays stopped until release commits |
| Release committed, engine journal stale | Exact durable release governs replay; cache is rebuilt |
| Old attempt's PASS offered for a new attempt | Refuse wrong identity; no advance |
| Correctness repair needs new capsule, metric or input | Preserve R1; launch a new run with new pins |
| Environment failure needs another work execution | Human-approved new attempt under R1/step, with distinct reservation/obs_id |

A duplicate transport request with identical identity attaches to existing work; changed bytes conflict. No silent model/experiment retry is authorized by these recovery stories. [Boundary cases](../system/boundary-cases.md) gives the independent injection points.
