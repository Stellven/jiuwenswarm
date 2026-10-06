# Source freeze and current working baseline

The [October 2 manifest](source-freeze-2026-10-02.json) is preserved as historical freeze evidence; its paths describe that original repository layout. Sources now live together under `docs/architecture/sources/product/`.

The [October 5 master draft](prd-m1-full-2026-10-05.txt) is the current working product input for this review, selected in response to the user's October 6 Luna findings. It adds authority rules, clarified Brief/Blueprint criteria, Builder delegation, telemetry semantics, mandatory stage-exit order and completion rules. Main's inspected register still references October 2; do not claim it has already been upgraded remotely.

Read [source index](README.md), [review resolution](../../review-resolution.md), and [amendments](../../principles.md#decisions-and-source-amendments). Exact current source bytes/hashes and original locations are recorded in the [package manifest](../../package-manifest.json). A draft adoption for this local design is not a claim that every team register has been synchronized.

Received files remain verbatim. New revisions get a new identity and source disposition. Authorized architecture decisions are explicit exceptions, not silent PRD rewrites. Compatible owner contributions refine master requirements; incomplete or broader proposals never weaken invariants, domain restrictions or required stage exits.
