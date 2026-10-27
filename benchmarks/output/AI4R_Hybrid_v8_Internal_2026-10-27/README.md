# Report package

Open **benchmark-report.html** for the illustrated report. Charts are embedded;
no network or web server is needed to read it. Markdown and separate PNG figures
are also included. Data links refer to files inside this package.

The external view presents worker-answer performance and complete role-token
accounting. The internal view additionally preserves every verifier/gate outcome.
Neither view claims full research-workflow or frontend acceptance.

`data/originals` contains 104 byte-for-byte public input/request, original worker
answer and frozen campaign metadata files. Its manifest records their SHA-256.
`receipt-projections.json` contains 48 explicitly labeled call/dispatch projections,
not full original receipts. Full receipts and native packets remain on Spark.
The observation index retains each source receipt SHA-256; reviewer answers,
credentials, account files and auth packets are not included.

`checksums.json` covers every package file except itself. The ZIP has a separate
SHA-256 sidecar. Reports use existing measurements; no new inference was run.
