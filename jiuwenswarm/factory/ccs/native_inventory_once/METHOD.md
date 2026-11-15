# Fresh native package inventory, one parse per distribution

This optional material-only host component changes one provenance implementation
detail. It is proposed, not applied. The calling host still enumerates the actual
current Python distributions on every call and emits the same sorted Name/Version
rows, preserving duplicates and omitting missing/empty names.

The baseline reads `d.metadata['Name']` for the filter, again for the emitted row,
and `d.version` (which reads metadata again). The proposed implementation obtains
one metadata snapshot for each distribution and reads both fields from it.
There is no cross-call or process cache. Installing/removing/updating a package is
visible at the next call. The snapshot narrows the within-distribution race between
reads; the inventory was never an atomic OS-wide package-environment transaction.

Warm actual Host profiling of the original code found 262 distributions and 786
metadata parses. Under cProfile, inventory enumeration consumed 0.323 of 0.443
seconds for one fresh call. Profiling inflates time; use the separate uninstrumented
ABBA experiment for performance claims. A cold profile also constructs schema
validators, so it is not interchangeable with the warmed call.

The benchmark compares the actual installed metadata inventory with fixed Python
and sys.path, records a canonical input/result identity, and verifies exact output
equality every round. It uses explicit ABBA order, retains raw times and reports
separate Python traced allocation peaks. Mutation/add/remove fake distributions
are negative controls against stale caching. The optional whole-Host comparison
loads an isolated code copy with this exact patch; it never edits the running host
source and retains both code identities and invocation receipts.

This does not change CC declaration, request, receipt, effect, authority, timeout,
lease or key semantics. No dependency inventory is omitted. No GPU/model quality
claim or admission certificate is produced. Applying the patch requires review by
the core host owner. Reverse this patch to roll back; no data migration is needed.
