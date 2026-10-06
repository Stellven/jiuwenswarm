# Data model context: M0-001

Normative field semantics are owned by [TASK §4](TASK.md#m0-if-001-at-r1). This record names relationships and validation constraints without a second schema.

- `ModelInvocation` is consumed with exact source/contract/input identity and supported revision.
- `CompletionObservation` is produced as candidate/observation until required checking and protected durable acceptance.
- User, workspace, run, node, attempt and subordinate invocation identities are distinct; each observed call binds its actual CC/model/configuration pins.
- Artifact reference and persisted bytes are linked by SHA256; path alone is insufficient. Accepted subject is immutable.
- Declared limits/effects are distinct from observed effects and available telemetry; unavailable/null has explicit reason and is never zero.
- Verification assessment/findings and protected gating decision are separate records bound to the same exact subject.
- Future accepted input references are instantiated under frozen templates before dispatch; they are not fabricated known values at graph freeze.
- Failure, cancellation, unknown delivery and pause-on-restart retain observations and never imply automatic retry.
- Schema migration and evidence revalidation follow the owning agreement revision.
