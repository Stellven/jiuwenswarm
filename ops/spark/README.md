# DGX Spark records

This folder keeps the inputs and records behind the 2026-11-20 DGX Spark (GB10) run, in which JiuwenSwarm applied builder capsules to llama.cpp running DeepSeek V4.1 Flash.

- [`prompts/`](prompts/): the fixed 512- and 2048-token prompts and their token manifest. The task contract [`star-deepseek-v1`](../../jiuwenswarm/factory/contracts/star-deepseek-v1.md) measures against them.
- [`P4-PROTOCOL.md`](P4-PROTOCOL.md): the timing and page-cache protocol used for the measured comparisons.
- [`SPARK-ACTIVATION-PROFILES.md`](SPARK-ACTIVATION-PROFILES.md): the matched stock and candidate flags used to check that each capsule's change really engaged.
- [`demo-20261120/`](demo-20261120/README.md): the engineering report, the headline numbers and the overnight records behind them.

Host paths in these records are written with placeholders: `~` is the Spark operator's home directory (so `~/predemo-spark/` is the demo checkout and its inputs), `<factory-workspace>` is the factory workspace that held the converted model, sources and run directories, and `<spark-tailnet-ip>` is the Spark's private network address. Digests of records that contained those paths were recomputed after the substitution.

The Spark operator tooling (the memory-capped runner, benchmark clients, report generators, evidence importers and demo scripts) is not part of this change. It was written for one shared machine and one campaign. It remains on branch `demo/cc-star-ui-20261120`, where the records above link to it.
