# 20261113 Recovery Package Sources prepresentation

These files are the authored console, guides and launch helpers for the assembled Satay recovery package. The console's relative evidence/context links resolve inside the assembled package, not this source-only directory. Sources and selected raw evidence are packaged separately to avoid committing large duplicate bundles. Runtime data and authentication are excluded.

The original demo video remains at artifacts/factory/demo-incremental/demo-final.mp4. J-OM13 raw evidence remains in siminfeng. The recoverable ZIPs (v1 unchanged, v2) are under /home/muk/backup and on the Danta USB drive, each with an adjacent .sha256. They are not in Downloads; an earlier version of this note said they were. `tooling/build_package.py` rebuilds v2 from v1 plus the authored files here, re-pins sources, checks links, scans for credentials and writes the manifest. Package checksums and SOURCE-PINS.json are generated after source commits are finalized. Do not move published tags.

Service setup now has Linger=yes; process restart was tested, physical reboot was not. The package includes exact source snapshots with .shallow boundary sidecars, not full repository history.
