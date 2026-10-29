# Historical capsule release manifests

The `release.json` files below are the original v1 manifests for the packet
utility and Generalist capsules. Their source files remain in the matching
sibling directories. New candidate discovery reads immediate `*/release.json`
manifests only. Startup can load these archived source pins for exact existing
identities, but only the ordinary current check-association and admission policy
may authorize registration. The archive does not grandfather a legacy check
mismatch, admit or activate a release, or expose it as a new candidate.

`history/v2/` holds current-format manifests (with shared-runtime and dependency pins) of releases that a newer release of the same capsule name superseded, for example `utility.calculate` m1-2 after m1-3. They are verified and registered the same way. Candidate discovery reads only immediate `*/release.json`, one candidate per capsule name.
