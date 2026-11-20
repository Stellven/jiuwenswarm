# Spark GB10 demo delivery

[Open the final Factory snapshot](http://100.105.127.48:5173/#factory-run/6e52cb81f7ff9e4d1f2a8a57). For the presentation use the [seven-stop script](OPS/DEMO-SCRIPT.md). The [engineering report](report.md) links directly to its frozen local evidence.

The compressed native export contains 3,042 manifest-verified files. It includes the benchmark task, observations, analysis receipts, capsule materials, session history and a portable report. The release check extracted this archive into a fresh directory and verified the native manifest and all 71 links in the readable report. [Archive digest](OPS/final-archive-verification.json) · [Native publication receipt](OPS/final-publication.json)

To extract the native export into a new directory, run `tar --zstd -xf spark-final-snapshot-20261120.tar.zst` from this delivery folder. The exported entry points are `spark-final-snapshot-20261120/INDEX.md` and `spark-final-snapshot-20261120/report.md`.
